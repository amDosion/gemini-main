"""Workflow history audio/video preview/download helpers with strict URL trust boundaries."""

from __future__ import annotations

import asyncio
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

from ...core.database import SessionLocal
from ..gemini.base.video_asset_download import download_google_video_asset_for_user
from ..gemini.base.video_common import is_google_provider_video_uri, normalize_gemini_file_name
from ...utils.url_security import UnsafeURLError, validate_outbound_http_url
from .workflow_history_image_service import (
    build_workflow_image_request_headers,
    is_same_origin_http_url,
    resolve_trusted_workflow_history_base_url,
)

_WORKFLOW_MEDIA_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_WORKFLOW_MEDIA_MAX_REDIRECTS = 5
_WORKFLOW_MEDIA_REQUEST_TIMEOUT_SECONDS = 30.0
PREVIEW_MAX_LIMIT = 100

_AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".pcm", ".wav", ".weba"}
_VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".ogv", ".webm"}
_AUDIO_FALLBACK_MIME = "audio/mpeg"
_VIDEO_FALLBACK_MIME = "video/mp4"


def _normalize_media_kind(media_kind: str) -> str:
    normalized = str(media_kind or "").strip().lower()
    if normalized not in {"audio", "video"}:
        raise ValueError(f"unsupported media kind: {media_kind}")
    return normalized


def _allowed_extensions(media_kind: str) -> set[str]:
    return _AUDIO_EXTENSIONS if _normalize_media_kind(media_kind) == "audio" else _VIDEO_EXTENSIONS


def _fallback_mime(media_kind: str) -> str:
    return _AUDIO_FALLBACK_MIME if _normalize_media_kind(media_kind) == "audio" else _VIDEO_FALLBACK_MIME


def _sanitize_download_file_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "").strip())
    return normalized.strip("._") or "media"


def _summarize_manifest_source_url(media_url: str) -> str:
    raw = str(media_url or "").strip()
    lowered = raw.lower()
    if lowered.startswith("data:audio/") or lowered.startswith("data:video/"):
        prefix = raw.split(",", 1)[0]
        return f"{prefix},...[len={len(raw)}]"
    if len(raw) > 320:
        return f"{raw[:320]}...[len={len(raw)}]"
    return raw


def validate_workflow_history_media_url(
    candidate_url: str,
    trusted_base_url: str,
    media_kind: str,
) -> str:
    normalized_kind = _normalize_media_kind(media_kind)
    normalized = str(candidate_url or "").strip()
    if not normalized:
        raise ValueError("empty media url")

    lowered = normalized.lower()
    if lowered.startswith(f"data:{normalized_kind}/"):
        return normalized
    if normalized_kind == "video" and is_google_provider_video_uri(normalized):
        return normalized

    if normalized.startswith("/"):
        normalized = f"{resolve_trusted_workflow_history_base_url(trusted_base_url).rstrip('/')}{normalized}"

    parsed = urlparse(normalized)
    if str(parsed.scheme or "").strip().lower() not in {"http", "https"}:
        raise ValueError("unsupported media url format")

    if is_same_origin_http_url(normalized, trusted_base_url):
        return normalized

    try:
        return validate_outbound_http_url(normalized)
    except UnsafeURLError as exc:
        raise ValueError(f"unsafe {normalized_kind} url: {exc}") from exc


def _guess_media_mime_type(original_url: str, media_kind: str) -> str:
    normalized_kind = _normalize_media_kind(media_kind)
    raw = str(original_url or "").strip()
    lowered = raw.lower()
    if lowered.startswith(f"data:{normalized_kind}/"):
        header = raw.split(",", 1)[0]
        mime = str(header.split(":", 1)[1].split(";", 1)[0] if ":" in header else "").strip().lower()
        if mime.startswith(f"{normalized_kind}/"):
            return mime
        return _fallback_mime(normalized_kind)
    if normalized_kind == "video" and is_google_provider_video_uri(raw):
        return _fallback_mime(normalized_kind)

    clean_url = raw.split("?", 1)[0].split("#", 1)[0]
    guessed, _ = mimetypes.guess_type(clean_url)
    normalized = str(guessed or "").strip().lower()
    if normalized.startswith(f"{normalized_kind}/"):
        return normalized
    return _fallback_mime(normalized_kind)


def _download_google_provider_video_binary(
    media_url: str,
    user_id: str,
    media_kind: str,
) -> tuple[bytes, str, str]:
    if _normalize_media_kind(media_kind) != "video":
        raise ValueError("provider asset download currently only supports video")
    provider_file_name = normalize_gemini_file_name(media_url)
    provider_file_uri = media_url if provider_file_name else None
    gcs_uri = media_url if str(media_url or "").strip().startswith("gs://") else None
    db = SessionLocal()
    try:
        binary, mime_type = asyncio.run(
            download_google_video_asset_for_user(
                db,
                user_id,
                provider_file_name=provider_file_name,
                provider_file_uri=provider_file_uri,
                gcs_uri=gcs_uri,
                mime_type="video/mp4",
            )
        )
    finally:
        db.close()
    return binary, mime_type, str(media_url or "").strip()


def _guess_media_extension(original_url: str, mime_type: str, media_kind: str) -> str:
    allowed = _allowed_extensions(media_kind)
    parsed = urlparse(str(original_url or ""))
    suffix = Path(parsed.path).suffix.lower()
    if suffix in allowed:
        return suffix

    normalized_mime = str(mime_type or "").split(";", 1)[0].strip().lower()
    guessed = mimetypes.guess_extension(normalized_mime) or ""
    if guessed.lower() == ".jpe":
        guessed = ".jpg"
    if guessed.lower() in allowed:
        return guessed.lower()
    return ".mp3" if _normalize_media_kind(media_kind) == "audio" else ".mp4"


def _decode_data_media_url(data_url: str, media_kind: str) -> tuple[bytes, str]:
    normalized_kind = _normalize_media_kind(media_kind)
    raw_value = str(data_url or "").strip()
    if not raw_value.lower().startswith(f"data:{normalized_kind}/"):
        raise ValueError(f"not data {normalized_kind} url")
    if "," not in raw_value:
        raise ValueError("invalid data url")
    header, payload = raw_value.split(",", 1)
    mime_type = str(header[5:].split(";", 1)[0] or _fallback_mime(normalized_kind)).strip().lower()
    if not mime_type.startswith(f"{normalized_kind}/"):
        raise ValueError(f"unsupported {normalized_kind} mime type: {mime_type}")
    if ";base64" in header.lower():
        try:
            binary = base64.b64decode(payload, validate=False)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid base64 media payload") from exc
        return binary, mime_type
    return unquote_to_bytes(payload), mime_type


def _build_workflow_media_request_headers(
    target_url: str,
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
    media_kind: str,
) -> Dict[str, str]:
    request_headers = build_workflow_image_request_headers(
        target_url=target_url,
        trusted_base_url=trusted_base_url,
        inherited_headers=inherited_headers,
    )
    request_headers["Accept"] = f"{_normalize_media_kind(media_kind)}/*,*/*"
    request_headers["User-Agent"] = "WorkflowHistoryMediaDownloader/1.0"
    return request_headers


def _resolve_workflow_media_redirect_url(
    current_url: str,
    location: str,
    trusted_base_url: str,
    media_kind: str,
) -> str:
    location_value = str(location or "").strip()
    if not location_value:
        raise ValueError("redirect missing location")
    try:
        next_url = str(httpx.URL(current_url).join(location_value))
    except Exception as exc:
        raise ValueError("invalid redirect location") from exc
    return validate_workflow_history_media_url(next_url, trusted_base_url, media_kind)


def _normalize_downloaded_media_mime_type(
    source_url: str,
    resolved_url: str,
    mime_type: str,
    media_kind: str,
) -> str:
    normalized_kind = _normalize_media_kind(media_kind)
    normalized = str(mime_type or "").split(";", 1)[0].strip().lower()
    if normalized.startswith(f"{normalized_kind}/"):
        return normalized
    guessed = _guess_media_mime_type(resolved_url or source_url, normalized_kind)
    if guessed.startswith(f"{normalized_kind}/"):
        return guessed
    raise ValueError(f"unsupported {normalized_kind} mime type: {normalized or 'application/octet-stream'}")


def download_workflow_media_binary(
    media_url: str,
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
    media_kind: str,
    max_bytes: Optional[int] = None,
    user_id: Optional[str] = None,
) -> tuple[bytes, str, str]:
    normalized_kind = _normalize_media_kind(media_kind)
    raw = str(media_url or "").strip()
    if not raw:
        raise ValueError("empty media url")

    safe_max_bytes: Optional[int] = None
    if max_bytes is not None:
        try:
            parsed_limit = int(max_bytes)
            if parsed_limit > 0:
                safe_max_bytes = parsed_limit
        except Exception:
            safe_max_bytes = None

    if raw.lower().startswith(f"data:{normalized_kind}/"):
        binary, mime_type = _decode_data_media_url(raw, normalized_kind)
        if safe_max_bytes is not None and len(binary) > safe_max_bytes:
            raise ValueError(f"file too large (> {safe_max_bytes} bytes)")
        return binary, mime_type, raw
    if normalized_kind == "video" and is_google_provider_video_uri(raw):
        if not user_id:
            raise ValueError("provider video asset requires user context")
        binary, mime_type, resolved_url = _download_google_provider_video_binary(raw, user_id, normalized_kind)
        if safe_max_bytes is not None and len(binary) > safe_max_bytes:
            raise ValueError(f"file too large (> {safe_max_bytes} bytes)")
        return binary, mime_type, resolved_url

    current_url = validate_workflow_history_media_url(raw, trusted_base_url, normalized_kind)
    redirect_count = 0

    try:
        with httpx.Client(timeout=_WORKFLOW_MEDIA_REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
            while True:
                request_headers = _build_workflow_media_request_headers(
                    target_url=current_url,
                    trusted_base_url=trusted_base_url,
                    inherited_headers=inherited_headers,
                    media_kind=normalized_kind,
                )
                response = client.get(current_url, headers=request_headers)

                if response.status_code in _WORKFLOW_MEDIA_REDIRECT_STATUS_CODES:
                    if redirect_count >= _WORKFLOW_MEDIA_MAX_REDIRECTS:
                        raise ValueError(f"redirects exceeded limit ({_WORKFLOW_MEDIA_MAX_REDIRECTS})")
                    current_url = _resolve_workflow_media_redirect_url(
                        current_url=current_url,
                        location=response.headers.get("location", ""),
                        trusted_base_url=trusted_base_url,
                        media_kind=normalized_kind,
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

    normalized_mime = _normalize_downloaded_media_mime_type(
        source_url=raw,
        resolved_url=current_url,
        mime_type=content_type,
        media_kind=normalized_kind,
    )
    return binary, normalized_mime, current_url


def resolve_workflow_media_item(media_urls: List[str], item_index: int) -> str:
    try:
        safe_index = int(item_index)
    except Exception as exc:
        raise ValueError("invalid media index") from exc
    if safe_index <= 0:
        raise ValueError("invalid media index")

    deduped: List[str] = []
    seen = set()
    for raw_url in media_urls:
        candidate = str(raw_url or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)

    if safe_index > len(deduped):
        raise ValueError("media item not found")
    return deduped[safe_index - 1]


def build_workflow_media_zip(
    execution_id: str,
    media_kind: str,
    media_urls: List[str],
    trusted_base_url: str,
    inherited_headers: Dict[str, str],
    user_id: Optional[str] = None,
) -> tuple[bytes, Dict[str, Any]]:
    normalized_kind = _normalize_media_kind(media_kind)
    manifest_items: List[Dict[str, Any]] = []
    seen_urls = set()
    used_names = set()
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        index = 0
        for raw_url in media_urls:
            candidate = str(raw_url or "").strip()
            if not candidate or candidate in seen_urls:
                continue
            seen_urls.add(candidate)
            index += 1

            try:
                binary, mime_type, resolved_url = download_workflow_media_binary(
                    media_url=candidate,
                    trusted_base_url=trusted_base_url,
                    inherited_headers=inherited_headers,
                    media_kind=normalized_kind,
                    user_id=user_id,
                )
                extension = _guess_media_extension(candidate, mime_type, normalized_kind)
                file_name = _sanitize_download_file_name(f"{normalized_kind}-{index:02d}{extension}")
                dedupe_idx = 2
                while file_name in used_names:
                    file_name = _sanitize_download_file_name(f"{normalized_kind}-{index:02d}-{dedupe_idx}{extension}")
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
            "mediaType": normalized_kind,
            "downloadedCount": downloaded_count,
            "skippedCount": skipped_count,
            "generatedAt": int(time.time() * 1000),
            "items": manifest_items,
        }
        zip_file.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    return zip_buffer.getvalue(), manifest


def build_workflow_media_previews(
    execution_id: str,
    media_kind: str,
    media_urls: List[str],
    trusted_base_url: str,
    preview_path_template: str,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    normalized_kind = _normalize_media_kind(media_kind)
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

    for raw_url in media_urls:
        candidate = str(raw_url or "").strip()
        if not candidate or candidate in seen_urls:
            continue
        seen_urls.add(candidate)
        if safe_limit is not None and len(previews) >= safe_limit:
            break

        try:
            resolved_url = validate_workflow_history_media_url(candidate, trusted_base_url, normalized_kind)
            mime_type = _guess_media_mime_type(resolved_url, normalized_kind)
            file_name = _sanitize_download_file_name(
                f"{normalized_kind}-{len(previews) + 1:02d}{_guess_media_extension(resolved_url, mime_type, normalized_kind)}"
            )
            previews.append(
                {
                    "index": len(previews) + 1,
                    "sourceUrl": _summarize_manifest_source_url(candidate),
                    "resolvedUrl": _summarize_manifest_source_url(resolved_url),
                    "mimeType": mime_type,
                    "fileName": file_name,
                    "previewUrl": preview_path_template.format(index=len(previews) + 1),
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
        "mediaType": normalized_kind,
        "count": len(previews),
        "skippedCount": len(skipped),
        "generatedAt": int(time.time() * 1000),
        "items": previews,
        "skipped": skipped,
    }


__all__ = [
    "PREVIEW_MAX_LIMIT",
    "build_workflow_media_previews",
    "build_workflow_media_zip",
    "download_workflow_media_binary",
    "resolve_trusted_workflow_history_base_url",
    "resolve_workflow_media_item",
    "validate_workflow_history_media_url",
]
