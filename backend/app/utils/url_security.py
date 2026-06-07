"""URL security helpers for outbound HTTP fetches (SSRF + redirect protection)."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import httpcore
import httpx

# Bound DNS resolution for async callers so a slow/hostile resolver cannot stall
# an event-loop worker. Sync callers (run in worker threads) keep blocking
# semantics but gain a per-socket default timeout below.
_DEFAULT_DNS_TIMEOUT_SECONDS = 5.0


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


def _prevalidate_url(url: str) -> tuple[str, Optional[str], int]:
    """
    Run the cheap, resolver-free SSRF checks.

    Returns:
        (raw_url, host_needing_dns, port). When ``host_needing_dns`` is None the
        URL is already fully validated (IP literal) and no DNS lookup is needed.
    """
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
        return raw_url, None, 0

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return raw_url, host, port


def _check_resolved_addr_infos(addr_infos) -> None:
    """Validate getaddrinfo results against the disallowed-IP policy."""
    resolved_ips = {
        ipaddress.ip_address(info[4][0])
        for info in addr_infos
        if info and len(info) >= 5 and info[4]
    }
    if not resolved_ips:
        raise UnsafeURLError("URL 主机解析失败")
    if any(_is_disallowed_ip(ip_obj) for ip_obj in resolved_ips):
        raise UnsafeURLError("URL 指向受限网络地址")


def _getaddrinfo(host: str, port: int):
    return socket.getaddrinfo(
        host,
        port,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )


def _resolve_single_allowed_ip(host: str, port: int) -> str:
    """Resolve ``host`` and return a single allowed IP to connect to (W02R-016).

    Performs the SSRF policy check on the resolution result and returns one
    validated IP. The caller connects to exactly this IP, eliminating the
    check-then-reconnect DNS-rebinding window. Raises ``UnsafeURLError`` for a
    disallowed host/IP or a failed resolution.
    """
    ip_literal = _try_parse_ip_host(host)
    if ip_literal is not None:
        if _is_disallowed_ip(ip_literal):
            raise UnsafeURLError("URL 指向受限地址")
        return str(ip_literal)

    if _is_disallowed_hostname(host):
        raise UnsafeURLError("URL 主机不被允许")

    try:
        addr_infos = _getaddrinfo(host, port)
    except socket.gaierror as exc:
        raise UnsafeURLError("URL 主机解析失败") from exc

    _check_resolved_addr_infos(addr_infos)

    for info in addr_infos:
        if info and len(info) >= 5 and info[4]:
            return str(info[4][0])
    raise UnsafeURLError("URL 主机解析失败")


def validate_outbound_http_url(url: str) -> str:
    """Validate outbound URL against SSRF risks and return normalized raw URL.

    Synchronous variant: safe to call from worker threads (e.g. read_webpage).
    Async callers should prefer :func:`validate_outbound_http_url_async` so a
    slow resolver cannot stall the event loop.
    """
    raw_url, host, port = _prevalidate_url(url)
    if host is None:
        return raw_url

    try:
        addr_infos = _getaddrinfo(host, port)
    except socket.gaierror as exc:
        raise UnsafeURLError("URL 主机解析失败") from exc

    _check_resolved_addr_infos(addr_infos)
    return raw_url


async def validate_outbound_http_url_async(
    url: str,
    *,
    resolve_timeout: float = _DEFAULT_DNS_TIMEOUT_SECONDS,
) -> str:
    """Async, event-loop-safe SSRF validator.

    Runs the blocking ``getaddrinfo`` in the default executor under a bounded
    ``asyncio.wait_for`` so a slow or hostile DNS resolver cannot stall a worker.
    A timeout is treated as a resolution failure (fail-closed).
    """
    raw_url, host, port = _prevalidate_url(url)
    if host is None:
        return raw_url

    loop = asyncio.get_running_loop()
    try:
        addr_infos = await asyncio.wait_for(
            loop.run_in_executor(None, _getaddrinfo, host, port),
            timeout=resolve_timeout,
        )
    except asyncio.TimeoutError as exc:
        raise UnsafeURLError("URL 主机解析超时") from exc
    except socket.gaierror as exc:
        raise UnsafeURLError("URL 主机解析失败") from exc

    _check_resolved_addr_infos(addr_infos)
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
    # W02R-016: pin DNS resolution to a validated IP at connect time so a
    # rebinding flip between validation and connect cannot reach an internal host.
    _ensure_client_pinned(client)
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


def sync_get_with_redirect_guard(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: float = 30.0,
    max_redirects: int = 5,
) -> httpx.Response:
    """Canonical synchronous SSRF-safe GET (sync counterpart of
    :func:`get_with_redirect_guard`).

    Validates the initial URL and re-validates EVERY redirect hop, and pins the
    connection to the validated IP at connect time (W02R-016) via a dedicated
    pinned httpx sync transport — so a public URL cannot 302 into a private host
    and a DNS-rebinding flip cannot reach an internal address. The pinning is
    scoped to this client only (no global socket state). Returns httpx.Response.
    """
    current_url = validate_outbound_http_url(url)
    redirect_count = 0

    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        _ensure_sync_client_pinned(client)
        while True:
            response = client.get(current_url, headers=headers)
            if response.status_code not in _REDIRECT_STATUS_CODES:
                return response

            location = response.headers.get("Location") or response.headers.get("location")
            if redirect_count >= max_redirects:
                raise UnsafeURLError(f"重定向次数超过限制 ({max_redirects})")
            current_url = resolve_safe_redirect_url(current_url, location or "")
            redirect_count += 1


class _PinningAsyncBackend(httpcore.AsyncNetworkBackend):
    """httpcore backend that resolves+validates the host and connects to that
    exact IP (W02R-016).

    Because resolution, SSRF validation, and the TCP connect happen atomically
    here, there is no second resolution for a DNS-rebinding attacker to flip.
    httpcore still drives TLS with ``server_hostname`` = the original hostname,
    so SNI and certificate verification remain correct.
    """

    def __init__(self) -> None:
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        pinned_ip = _resolve_single_allowed_ip(host, int(port))
        return await self._inner.connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, *args, **kwargs):  # pragma: no cover - not used
        raise UnsafeURLError("unix-socket egress is not allowed")

    async def sleep(self, seconds: float) -> None:  # pragma: no cover - passthrough
        await self._inner.sleep(seconds)


def _ensure_client_pinned(client: httpx.AsyncClient) -> None:
    """Inject the SSRF/rebinding-safe network backend into an httpx client's pool.

    Fail-closed: if the expected httpx/httpcore internals are not present (e.g.
    after a library upgrade), raise rather than silently fetch without pinning.
    """
    transport = getattr(client, "_transport", None)
    pool = getattr(transport, "_pool", None)
    if pool is None or not hasattr(pool, "_network_backend"):
        raise UnsafeURLError("无法为出站连接启用 SSRF 固定后端（httpx 内部结构不兼容）")
    if not isinstance(pool._network_backend, _PinningAsyncBackend):
        pool._network_backend = _PinningAsyncBackend()


class _PinningSyncBackend(httpcore.NetworkBackend):
    """Synchronous mirror of :class:`_PinningAsyncBackend` (W02R-016)."""

    def __init__(self) -> None:
        self._inner = httpcore.SyncBackend()

    def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        pinned_ip = _resolve_single_allowed_ip(host, int(port))
        return self._inner.connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    def connect_unix_socket(self, *args, **kwargs):  # pragma: no cover - not used
        raise UnsafeURLError("unix-socket egress is not allowed")

    def sleep(self, seconds: float) -> None:  # pragma: no cover - passthrough
        self._inner.sleep(seconds)


def _ensure_sync_client_pinned(client: httpx.Client) -> None:
    """Inject the SSRF/rebinding-safe sync backend into an httpx.Client pool.

    Fail-closed: raise if the expected httpx/httpcore internals are absent rather
    than silently connecting without pinning.
    """
    transport = getattr(client, "_transport", None)
    pool = getattr(transport, "_pool", None)
    if pool is None or not hasattr(pool, "_network_backend"):
        raise UnsafeURLError("无法为出站连接启用 SSRF 固定后端（httpx 内部结构不兼容）")
    if not isinstance(pool._network_backend, _PinningSyncBackend):
        pool._network_backend = _PinningSyncBackend()
