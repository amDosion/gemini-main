"""Shared byte limits for server-side user/provider media loading."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Tuple

import httpx

DEFAULT_REMOTE_MEDIA_MAX_BYTES = int(
    os.getenv("REMOTE_MEDIA_MAX_BYTES", str(32 * 1024 * 1024))
)


class MediaTooLargeError(ValueError):
    """Raised before returning media that exceeds the configured byte cap."""


def _limit_message(max_bytes: int) -> str:
    return f"media exceeds {max_bytes // (1024 * 1024)}MB limit"


def _content_length_exceeds(headers: httpx.Headers, max_bytes: int) -> bool:
    value = headers.get("content-length")
    if not value:
        return False
    try:
        return int(value) > max_bytes
    except (TypeError, ValueError):
        return False


def decode_base64_data_url_limited(
    data_url: str,
    *,
    max_bytes: int = DEFAULT_REMOTE_MEDIA_MAX_BYTES,
) -> Tuple[bytes, str]:
    if not str(data_url or "").startswith("data:"):
        raise ValueError("expected data URL")
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError as exc:
        raise ValueError("invalid data URL") from exc

    mime_type = header.split(":", 1)[1].split(";", 1)[0] if ":" in header else ""
    encoded_compact = "".join(str(encoded or "").split())
    # Base64 expands by 4/3. Reject clearly oversized payloads before decode.
    encoded_limit = ((max_bytes + 2) // 3) * 4 + 8
    if len(encoded_compact) > encoded_limit:
        raise MediaTooLargeError(_limit_message(max_bytes))

    raw = base64.b64decode(encoded_compact)
    if len(raw) > max_bytes:
        raise MediaTooLargeError(_limit_message(max_bytes))
    return raw, mime_type or "application/octet-stream"


async def read_httpx_response_limited(
    response: httpx.Response,
    *,
    max_bytes: int = DEFAULT_REMOTE_MEDIA_MAX_BYTES,
) -> bytes:
    if _content_length_exceeds(response.headers, max_bytes):
        raise MediaTooLargeError(_limit_message(max_bytes))

    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise MediaTooLargeError(_limit_message(max_bytes))
        chunks.append(chunk)
    return b"".join(chunks)


def read_httpx_response_limited_sync(
    response: httpx.Response,
    *,
    max_bytes: int = DEFAULT_REMOTE_MEDIA_MAX_BYTES,
) -> bytes:
    if _content_length_exceeds(response.headers, max_bytes):
        raise MediaTooLargeError(_limit_message(max_bytes))

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise MediaTooLargeError(_limit_message(max_bytes))
        chunks.append(chunk)
    return b"".join(chunks)


def read_path_bytes_limited(
    path: Path,
    *,
    max_bytes: int = DEFAULT_REMOTE_MEDIA_MAX_BYTES,
) -> bytes:
    size = path.stat().st_size
    if size > max_bytes:
        raise MediaTooLargeError(_limit_message(max_bytes))
    return path.read_bytes()
