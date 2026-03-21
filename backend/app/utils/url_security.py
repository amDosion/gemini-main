"""URL security helpers for outbound HTTP fetches (SSRF + redirect protection)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx


class UnsafeURLError(ValueError):
    """Raised when outbound URL fails SSRF or redirect safety checks."""


_METADATA_HOSTS = {
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "instance-data.ec2.internal",
}
_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("100.100.100.200"),
}
_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


def _try_parse_ip_host(hostname: str) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    host = str(hostname or "").strip()
    if not host:
        return None
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    # 兼容非标准 IPv4 表达（例如 127.1），避免绕过。
    try:
        packed = socket.inet_aton(host)
        return ipaddress.IPv4Address(packed)
    except OSError:
        return None


def _is_disallowed_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip_obj in _METADATA_IPS:
        return True
    return any(
        (
            ip_obj.is_private,
            ip_obj.is_loopback,
            ip_obj.is_link_local,
            ip_obj.is_multicast,
            ip_obj.is_reserved,
            ip_obj.is_unspecified,
        )
    )


def _is_disallowed_hostname(hostname: str) -> bool:
    normalized = str(hostname or "").strip().strip(".").lower()
    if not normalized:
        return True
    if normalized in _METADATA_HOSTS:
        return True
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    if normalized.startswith("metadata."):
        return True
    return False


def validate_outbound_http_url(url: str) -> str:
    """Validate outbound URL against SSRF risks and return normalized raw URL."""
    raw_url = str(url or "").strip()
    if not raw_url:
        raise UnsafeURLError("url 不能为空")

    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("仅支持 http/https URL")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL 缺少主机名")
    if _is_disallowed_hostname(host):
        raise UnsafeURLError("URL 主机不被允许")

    ip_literal = _try_parse_ip_host(host)
    if ip_literal is not None:
        if _is_disallowed_ip(ip_literal):
            raise UnsafeURLError("URL 指向受限地址")
        return raw_url

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addr_infos = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise UnsafeURLError("URL 主机解析失败") from exc

    resolved_ips = {
        ipaddress.ip_address(info[4][0])
        for info in addr_infos
        if info and len(info) >= 5 and info[4]
    }
    if not resolved_ips:
        raise UnsafeURLError("URL 主机解析失败")
    if any(_is_disallowed_ip(ip_obj) for ip_obj in resolved_ips):
        raise UnsafeURLError("URL 指向受限网络地址")

    return raw_url


def resolve_safe_redirect_url(current_url: str, location: str) -> str:
    """Resolve redirect `Location` against current URL and validate target."""
    location_value = str(location or "").strip()
    if not location_value:
        raise UnsafeURLError("重定向缺少 Location")

    try:
        candidate = str(httpx.URL(current_url).join(location_value))
    except Exception as exc:  # noqa: BLE001 - normalize all parsing failures
        raise UnsafeURLError("重定向目标非法") from exc

    return validate_outbound_http_url(candidate)


async def get_with_redirect_guard(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = 5,
) -> tuple[httpx.Response, str]:
    """
    Perform GET with per-hop URL validation.

    Returns:
        (response, final_url)
    """
    current_url = validate_outbound_http_url(url)
    redirect_count = 0

    while True:
        response = await client.get(current_url, follow_redirects=False)
        if response.status_code not in _REDIRECT_STATUS_CODES:
            return response, current_url

        if redirect_count >= max_redirects:
            raise UnsafeURLError(f"重定向次数超过限制 ({max_redirects})")

        next_url = resolve_safe_redirect_url(current_url, response.headers.get("location", ""))
        current_url = next_url
        redirect_count += 1
