"""Workflow history image preview/download helpers with strict URL trust boundaries."""

from __future__ import annotations

import base64
import binascii
import io
import json
import mimetypes
import re
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote_to_bytes, urlparse

import httpx

from ...utils.url_security import UnsafeURLError, validate_outbound_http_url

_WORKFLOW_IMAGE_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_WORKFLOW_IMAGE_MAX_REDIRECTS = 5
_WORKFLOW_IMAGE_REQUEST_TIMEOUT_SECONDS = 20.0
_DEFAULT_LOOPBACK_PORT = 21574
PREVIEW_MAX_LIMIT = 100


def _format_origin_host(hostname: str) -> str:
    host = str(hostname or "").strip()
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _normalized_http_port(parsed_url) -> int:
    try:
        if parsed_url.port:
            return int(parsed_url.port)
    except ValueError:
        pass
    return 443 if str(parsed_url.scheme or "").lower() == "https" else 80


def _normalize_http_origin(raw_origin: str) -> str:
    raw = str(raw_origin or "").strip()
    if not raw:
        raise ValueError("empty base url")
    parsed = urlparse(raw)
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme not in {"http", "https"}:
        raise ValueError("base url must use http/https")
    if parsed.username or parsed.password:
        raise ValueError("base url must not include credentials")
    host = str(parsed.hostname or "").strip().strip(".").lower()
    if not host:
        raise ValueError("base url missing hostname")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("base url must not include path/query/fragment")

    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid base url port") from exc

    default_port = 443 if scheme == "https" else 80
    if parsed_port is None or parsed_port == default_port:
        netloc = _format_origin_host(host)
    else:
        netloc = f"{_format_origin_host(host)}:{parsed_port}"
    return f"{scheme}://{netloc}"


def resolve_trusted_workflow_history_base_url(
    configured_base_url: Optional[str],
    fallback_port: Optional[int] = None,
) -> str:
    configured = str(configured_base_url or "").strip()
    if configured:
        return _normalize_http_origin(configured)

    safe_port = _DEFAULT_LOOPBACK_PORT
    if fallback_port is not None:
        try:
            parsed = int(fallback_port)
            if parsed > 0:
                safe_port = parsed
        except Exception:
            safe_port = _DEFAULT_LOOPBACK_PORT
    return _normalize_http_origin(f"http://127.0.0.1:{safe_port}")


def is_same_origin_http_url(target_url: str, trusted_base_url: str) -> bool:
    parsed_target = urlparse(str(target_url or "").strip())
    parsed_base = urlparse(str(trusted_base_url or "").strip())
    target_scheme = str(parsed_target.scheme or "").strip().lower()
    base_scheme = str(parsed_base.scheme or "").strip().lower()
    if target_scheme not in {"http", "https"} or base_scheme not in {"http", "https"}:
        return False

    target_host = str(parsed_target.hostname or "").strip().strip(".").lower()
    base_host = str(parsed_base.hostname or "").strip().strip(".").lower()
    if not target_host or not base_host:
        return False

    return (
        target_scheme == base_scheme
        and target_host == base_host
        and _normalized_http_port(parsed_target) == _normalized_http_port(parsed_base)
    )


def validate_workflow_history_image_url(candidate_url: str, trusted_base_url: str) -> str:
    normalized = str(candidate_url or "").strip()
    if not normalized:
        raise ValueError("empty image url")

    parsed = urlparse(normalized)
    if str(parsed.scheme or "").strip().lower() not in {"http", "https"}:
        raise ValueError("unsupported image url format")

    if is_same_origin_http_url(normalized, trusted_base_url):
        return normalized

    try:
        return validate_outbound_http_url(normalized)
    except UnsafeURLError as exc:
        raise ValueError(f"unsafe image url: {exc}") from exc


def _resolve_workflow_image_redirect_url(
    current_url: str,
    location: str,
    trusted_base_url: str,
) -> str:
    location_value = str(location or "").strip()
    if not location_value:
        raise ValueError("redirect missing location")
    try:
        next_url = str(httpx.URL(current_url).join(location_value))
    except Exception as exc:
        raise ValueError("invalid redirect location") from exc
    return validate_workflow_history_image_url(next_url, trusted_base_url)


def build_workflow_image_request_headers(
    target_url: str,
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
) -> Dict[str, str]:
    request_headers = {
        "User-Agent": "WorkflowHistoryImageDownloader/1.0",
        "Accept": "image/*,*/*",
    }

    if is_same_origin_http_url(target_url, trusted_base_url):
        for key in ("Authorization", "Cookie"):
            value = inherited_headers.get(key) if isinstance(inherited_headers, dict) else None
            if isinstance(value, str):
                safe_value = value.replace("\r", "").replace("\n", "").strip()
                if safe_value:
                    request_headers[key] = safe_value
    return request_headers


def _decode_data_image_url(data_url: str) -> tuple[bytes, str]:
    raw_value = str(data_url or "").strip()
    if not raw_value.startswith("data:image/"):
        raise ValueError("not data image url")
    if "," not in raw_value:
        raise ValueError("invalid data url")
    header, payload = raw_value.split(",", 1)
    mime_type = str(header[5:].split(";", 1)[0] or "image/png").strip().lower()
    if ";base64" in header.lower():
        try:
            binary = base64.b64decode(payload, validate=False)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid base64 image payload") from exc
        return binary, mime_type
    return unquote_to_bytes(payload), mime_type


def _download_workflow_image_binary(
    image_url: str,
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
    max_bytes: Optional[int] = None,
) -> tuple[bytes, str, str]:
    raw = str(image_url or "").strip()
    if not raw:
        raise ValueError("empty image url")

    safe_max_bytes: Optional[int] = None
    if max_bytes is not None:
        try:
            parsed_limit = int(max_bytes)
            if parsed_limit > 0:
                safe_max_bytes = parsed_limit
        except Exception:
            safe_max_bytes = None

    if raw.startswith("data:image/"):
        binary, mime_type = _decode_data_image_url(raw)
        if safe_max_bytes is not None and len(binary) > safe_max_bytes:
            raise ValueError(f"file too large (> {safe_max_bytes} bytes)")
        return binary, mime_type, raw

    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        target_url = raw
    elif raw.startswith("/"):
        target_url = f"{trusted_base_url.rstrip('/')}{raw}"
    else:
        raise ValueError("unsupported image url format")

    current_url = validate_workflow_history_image_url(target_url, trusted_base_url)
    redirect_count = 0

    try:
        with httpx.Client(timeout=_WORKFLOW_IMAGE_REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
            while True:
                request_headers = build_workflow_image_request_headers(
                    current_url,
                    trusted_base_url,
                    inherited_headers,
                )
                response = client.get(current_url, headers=request_headers)

                if response.status_code in _WORKFLOW_IMAGE_REDIRECT_STATUS_CODES:
                    if redirect_count >= _WORKFLOW_IMAGE_MAX_REDIRECTS:
                        raise ValueError(f"redirects exceeded limit ({_WORKFLOW_IMAGE_MAX_REDIRECTS})")
                    current_url = _resolve_workflow_image_redirect_url(
                        current_url,
                        response.headers.get("location", ""),
                        trusted_base_url,
                    )
                    redirect_count += 1
                    continue

                response.raise_for_status()
                binary = response.content
                content_type = str(response.headers.get("Content-Type") or "application/octet-stream")
                break
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"http status {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ValueError(f"http request failed: {exc}") from exc

    if safe_max_bytes is not None and len(binary) > safe_max_bytes:
        raise ValueError(f"file too large (> {safe_max_bytes} bytes)")
    return binary, content_type, current_url


def _guess_image_extension(original_url: str, mime_type: str) -> str:
    parsed = urlparse(str(original_url or ""))
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix

    normalized_mime = str(mime_type or "").split(";", 1)[0].strip().lower()
    guessed = mimetypes.guess_extension(normalized_mime) or ""
    if guessed.lower() == ".jpe":
        guessed = ".jpg"
    if guessed.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}:
        return ".jpg" if guessed.lower() == ".jpeg" else guessed.lower()
    return ".png"


def _sanitize_download_file_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "").strip())
    return normalized.strip("._") or "image"


def _summarize_manifest_source_url(image_url: str) -> str:
    raw = str(image_url or "").strip()
    if raw.lower().startswith("data:image/"):
        prefix = raw.split(",", 1)[0]
        return f"{prefix},...[len={len(raw)}]"
    if len(raw) > 320:
        return f"{raw[:320]}...[len={len(raw)}]"
    return raw


def build_workflow_images_zip(
    execution_id: str,
    image_urls: List[str],
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
) -> tuple[bytes, Dict[str, Any]]:
    manifest_items: List[Dict[str, Any]] = []
    seen_urls = set()
    used_names = set()
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        index = 0
        for raw_url in image_urls:
            candidate = str(raw_url or "").strip()
            if not candidate or candidate in seen_urls:
                continue
            seen_urls.add(candidate)
            index += 1

            try:
                binary, mime_type, resolved_url = _download_workflow_image_binary(
                    image_url=candidate,
                    trusted_base_url=trusted_base_url,
                    inherited_headers=inherited_headers,
                )
                extension = _guess_image_extension(candidate, mime_type)
                file_name = _sanitize_download_file_name(f"image-{index:02d}{extension}")
                dedupe_idx = 2
                while file_name in used_names:
                    file_name = _sanitize_download_file_name(f"image-{index:02d}-{dedupe_idx}{extension}")
                    dedupe_idx += 1
                used_names.add(file_name)
                zip_file.writestr(file_name, binary)
                manifest_items.append(
                    {
                        "sourceUrl": _summarize_manifest_source_url(candidate),
                        "resolvedUrl": _summarize_manifest_source_url(resolved_url),
                        "fileName": file_name,
                        "status": "downloaded",
                        "size": len(binary),
                        "mimeType": str(mime_type or "").split(";", 1)[0].strip(),
                    }
                )
            except Exception as exc:
                manifest_items.append(
                    {
                        "sourceUrl": _summarize_manifest_source_url(candidate),
                        "status": "skipped",
                        "error": str(exc),
                    }
                )

        downloaded_count = sum(1 for item in manifest_items if item.get("status") == "downloaded")
        skipped_count = sum(1 for item in manifest_items if item.get("status") != "downloaded")
        manifest = {
            "executionId": execution_id,
            "downloadedCount": downloaded_count,
            "skippedCount": skipped_count,
            "generatedAt": int(time.time() * 1000),
            "images": manifest_items,
        }
        zip_file.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    return zip_buffer.getvalue(), manifest


def build_workflow_image_previews(
    execution_id: str,
    image_urls: List[str],
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
    limit: Optional[int] = None,
    max_bytes_per_image: Optional[int] = None,
    max_total_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    safe_limit: Optional[int] = None
    if limit is not None:
        try:
            parsed_limit = int(limit)
            if parsed_limit > 0:
                safe_limit = min(parsed_limit, PREVIEW_MAX_LIMIT)
        except Exception:
            safe_limit = None
    previews: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    seen_urls = set()
    total_bytes = 0

    for raw_url in image_urls:
        candidate = str(raw_url or "").strip()
        if not candidate or candidate in seen_urls:
            continue
        seen_urls.add(candidate)
        if safe_limit is not None and len(previews) >= safe_limit:
            break

        try:
            binary, mime_type, resolved_url = _download_workflow_image_binary(
                image_url=candidate,
                trusted_base_url=trusted_base_url,
                inherited_headers=inherited_headers,
                max_bytes=max_bytes_per_image,
            )
            normalized_mime = str(mime_type or "").split(";", 1)[0].strip().lower() or "image/png"
            if not normalized_mime.startswith("image/"):
                raise ValueError(f"unsupported preview mime type: {normalized_mime}")
            projected_total = total_bytes + len(binary)
            if max_total_bytes is not None and projected_total > max_total_bytes:
                raise ValueError(f"preview payload too large (> {max_total_bytes} bytes)")
            total_bytes = projected_total
            data_url = f"data:{normalized_mime};base64,{base64.b64encode(binary).decode('ascii')}"
            previews.append(
                {
                    "index": len(previews) + 1,
                    "sourceUrl": _summarize_manifest_source_url(candidate),
                    "resolvedUrl": _summarize_manifest_source_url(resolved_url),
                    "mimeType": normalized_mime,
                    "size": len(binary),
                    "dataUrl": data_url,
                }
            )
        except Exception as exc:
            skipped.append(
                {
                    "sourceUrl": _summarize_manifest_source_url(candidate),
                    "error": str(exc),
                }
            )

    return {
        "executionId": execution_id,
        "count": len(previews),
        "skippedCount": len(skipped),
        "generatedAt": int(time.time() * 1000),
        "images": previews,
        "skipped": skipped,
    }


__all__ = [
    "build_workflow_image_previews",
    "build_workflow_image_request_headers",
    "build_workflow_images_zip",
    "is_same_origin_http_url",
    "resolve_trusted_workflow_history_base_url",
    "validate_workflow_history_image_url",
]
