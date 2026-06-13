"""Shared OpenAI-compatible multimodal message normalization."""

from __future__ import annotations

import base64
import binascii
import ipaddress
import os
import re
import socket
from typing import Any, Dict, List
from urllib.parse import urlparse


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
DEFAULT_MAX_IMAGE_REFERENCE_CHARS = 28 * 1024 * 1024
_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("100.100.100.200"),
}
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_DATA_IMAGE_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.*)$", re.DOTALL)


def _load_max_image_reference_chars() -> int:
    raw_value = os.getenv(
        "OPENAI_COMPAT_IMAGE_REFERENCE_MAX_CHARS",
        str(DEFAULT_MAX_IMAGE_REFERENCE_CHARS),
    )
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return DEFAULT_MAX_IMAGE_REFERENCE_CHARS
    return max(1024, value)


MAX_IMAGE_REFERENCE_CHARS = _load_max_image_reference_chars()


def resolve_attachment_url(attachment: Any) -> str:
    if not isinstance(attachment, dict):
        return ""
    for key in (
        "url",
        "temp_url",
        "tempUrl",
        "file_uri",
        "fileUri",
        "base64_data",
        "base64Data",
    ):
        value = attachment.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_image_attachment(attachment: Any, url: str) -> bool:
    mime_type = _attachment_mime_type(attachment)
    if mime_type.startswith("image/"):
        return True
    lowered_url = str(url or "").strip().lower()
    if lowered_url.startswith("data:image/"):
        return True
    clean_url = lowered_url.split("?", 1)[0].split("#", 1)[0]
    return clean_url.endswith(IMAGE_EXTENSIONS)


def normalize_image_reference(attachment: Any, url: str) -> str:
    raw_url = str(url or "").strip()
    if not raw_url or len(raw_url) > MAX_IMAGE_REFERENCE_CHARS:
        return ""

    lowered = raw_url.lower()
    if lowered.startswith("data:image/"):
        return _normalize_data_image_url(raw_url)

    if _looks_like_local_reference(raw_url):
        return ""

    if lowered.startswith(("http://", "https://")):
        return raw_url if _is_safe_remote_image_url(raw_url) else ""

    mime_type = _attachment_mime_type(attachment)
    if mime_type.startswith("image/"):
        payload = _normalize_raw_base64(raw_url)
        if payload:
            return f"data:{mime_type};base64,{payload}"

    return ""


def normalize_multimodal_content(content: Any, attachments: List[Any]) -> Any:
    parts: List[Dict[str, Any]] = []
    content_is_list = isinstance(content, list)

    if content_is_list:
        for item in content:
            if isinstance(item, dict):
                item_type = str(item.get("type") or "").strip().lower()
                if item_type == "text":
                    text_value = str(item.get("text") or "").strip()
                    if text_value:
                        parts.append({"type": "text", "text": text_value})
                    continue
                if item_type == "image_url" and isinstance(item.get("image_url"), dict):
                    image_url = str(item["image_url"].get("url") or "").strip()
                    safe_url = normalize_image_reference({}, image_url)
                    if safe_url:
                        parts.append({"type": "image_url", "image_url": {"url": safe_url}})
                    continue
            item_text = str(item or "").strip()
            if item_text:
                parts.append({"type": "text", "text": item_text})
    else:
        text_value = str(content or "").strip()
        if text_value:
            parts.append({"type": "text", "text": text_value})

    for attachment in attachments:
        url = resolve_attachment_url(attachment)
        if not url or not is_image_attachment(attachment, url):
            continue
        safe_url = normalize_image_reference(attachment, url)
        if not safe_url:
            continue
        parts.append({"type": "image_url", "image_url": {"url": safe_url}})

    if not attachments and not content_is_list:
        return content
    if len(parts) == 0:
        if content_is_list:
            return ""
        return str(content or "").strip()
    return parts


def _attachment_mime_type(attachment: Any) -> str:
    if not isinstance(attachment, dict):
        return ""
    return str(
        attachment.get("mime_type")
        or attachment.get("mimeType")
        or ""
    ).strip().lower()


def _looks_like_local_reference(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith("file:")
        or value.startswith(("/", "\\", "~"))
        or _WINDOWS_ABSOLUTE_PATH_RE.match(value) is not None
    )


def _try_parse_ip_host(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    host = str(hostname or "").strip()
    if not host:
        return None
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    try:
        packed = socket.inet_aton(host)
        return ipaddress.IPv4Address(packed)
    except OSError:
        return None


def _is_disallowed_hostname(hostname: str) -> bool:
    normalized = str(hostname or "").strip().strip(".").lower()
    return (
        not normalized
        or normalized == "localhost"
        or normalized.endswith(".localhost")
        or normalized in {"metadata", "metadata.google.internal"}
        or normalized.startswith("metadata.")
    )


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


def _is_safe_remote_image_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    if _is_disallowed_hostname(host):
        return False
    ip_literal = _try_parse_ip_host(host)
    return ip_literal is None or not _is_disallowed_ip(ip_literal)


def _normalize_raw_base64(value: str) -> str:
    normalized = re.sub(r"\s+", "", value)
    if not normalized or len(normalized) > MAX_IMAGE_REFERENCE_CHARS:
        return ""
    return normalized if _decode_base64_payload(normalized) is not None else ""


def _normalize_data_image_url(value: str) -> str:
    if len(value) > MAX_IMAGE_REFERENCE_CHARS:
        return ""
    match = _DATA_IMAGE_URL_RE.match(value)
    if not match:
        return ""
    mime_type = match.group(1).lower()
    payload = re.sub(r"\s+", "", match.group(2))
    if not payload or len(payload) > MAX_IMAGE_REFERENCE_CHARS:
        return ""
    if _decode_base64_payload(payload) is None:
        return ""
    return f"data:{mime_type};base64,{payload}"


def _decode_base64_payload(payload: str) -> bytes | None:
    remainder = len(payload) % 4
    if remainder == 1:
        return None
    padded = payload + ("=" * ((4 - remainder) % 4))
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (ValueError, binascii.Error):
        return None
    if len(decoded) > (MAX_IMAGE_REFERENCE_CHARS * 3 // 4):
        return None
    return decoded
