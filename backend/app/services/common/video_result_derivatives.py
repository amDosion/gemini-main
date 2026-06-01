"""Provider-neutral derivatives for generated video results."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

from ...models.db_models import MessageAttachment
from ...utils.attachment_handler import is_base64_url
from ...utils.url_security import get_with_redirect_guard, validate_outbound_http_url
from ..gemini.base.video_common import (
    LoadedSourceVideo,
    is_google_provider_video_uri,
    parse_data_url,
    to_data_url,
)
from ..gemini.base.video_frame_bridge import extract_last_frame_image
from ..storage.local_provider import resolve_local_public_file_path
from .attachment_service import AttachmentService, safe_persist_ai_result

logger = logging.getLogger(__name__)


def _first_non_empty_string(*values: Any) -> str:
    for value in values:
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    return ""


def _video_payload_source(payload: Dict[str, Any], explicit_source_url: Optional[str] = None) -> Dict[str, str]:
    source = _first_non_empty_string(
        explicit_source_url,
        payload.get("url"),
        payload.get("videoUrl"),
        payload.get("video_url"),
        payload.get("file_uri"),
        payload.get("fileUri"),
        payload.get("gcs_uri"),
        payload.get("gcsUri"),
        payload.get("provider_file_uri"),
        payload.get("providerFileUri"),
        payload.get("provider_file_name"),
        payload.get("providerFileName"),
    )
    return {
        "source": source,
        "mime_type": _first_non_empty_string(payload.get("mime_type"), payload.get("mimeType"), "video/mp4"),
        "filename": _first_non_empty_string(payload.get("filename"), payload.get("name")),
        "attachment_id": _first_non_empty_string(payload.get("attachment_id"), payload.get("attachmentId")),
        "provider_file_name": _first_non_empty_string(payload.get("provider_file_name"), payload.get("providerFileName")),
        "provider_file_uri": _first_non_empty_string(payload.get("provider_file_uri"), payload.get("providerFileUri")),
        "gcs_uri": _first_non_empty_string(payload.get("gcs_uri"), payload.get("gcsUri")),
        "file_uri": _first_non_empty_string(payload.get("file_uri"), payload.get("fileUri")),
    }


def _last_frame_filename(video_filename: str) -> str:
    stem = Path(video_filename or "video").stem.strip() or "video"
    return f"{stem}-last-frame.png"


async def _load_temp_attachment_source(
    attachment_service: AttachmentService,
    *,
    attachment_id: str,
    user_id: str,
    fallback_mime_type: str,
) -> Optional[Tuple[bytes, str]]:
    attachment = (
        attachment_service.db.query(MessageAttachment)
        .filter(MessageAttachment.id == attachment_id, MessageAttachment.user_id == user_id)
        .first()
    )
    if not attachment:
        return None

    source = _first_non_empty_string(
        attachment.url if attachment.upload_status == "completed" else "",
        attachment.temp_url,
        attachment.url,
        attachment.file_uri,
        attachment.google_file_uri,
    )
    if not source:
        return None

    return await load_video_result_bytes(
        attachment_service,
        source=source,
        user_id=user_id,
        fallback_mime_type=attachment.mime_type or fallback_mime_type,
    )


async def load_video_result_bytes(
    attachment_service: AttachmentService,
    *,
    source: str,
    user_id: str,
    fallback_mime_type: str = "video/mp4",
    provider_file_name: str = "",
    provider_file_uri: str = "",
    gcs_uri: str = "",
) -> Tuple[bytes, str]:
    normalized_source = str(source or "").strip()
    if not normalized_source:
        raise ValueError("Generated video result is missing a downloadable source.")

    if is_base64_url(normalized_source):
        video_bytes, mime_type = parse_data_url(normalized_source)
        return video_bytes, mime_type or fallback_mime_type

    if normalized_source.startswith("/api/temp-images/"):
        attachment_id = normalized_source.split("/api/temp-images/", 1)[1].split("?", 1)[0].split("#", 1)[0].strip("/")
        loaded = await _load_temp_attachment_source(
            attachment_service,
            attachment_id=attachment_id,
            user_id=user_id,
            fallback_mime_type=fallback_mime_type,
        )
        if loaded is None:
            raise ValueError(f"Temporary video attachment was not found: {attachment_id}")
        return loaded

    if normalized_source.startswith("/api/storage/local-files/"):
        file_path = resolve_local_public_file_path(normalized_source)
        if file_path is None or not file_path.exists() or not file_path.is_file():
            raise ValueError("Local generated video file is no longer available.")
        mime_type = mimetypes.guess_type(str(file_path))[0] or fallback_mime_type
        return file_path.read_bytes(), mime_type

    if (
        normalized_source.startswith("gs://")
        or normalized_source.startswith("files/")
        or is_google_provider_video_uri(normalized_source)
        or provider_file_name
        or provider_file_uri
        or gcs_uri
    ):
        from ..gemini.base.video_asset_download import download_google_video_asset_for_user
        from ..gemini.base.video_common import normalize_gemini_file_name

        resolved_provider_file_name = provider_file_name or normalize_gemini_file_name(normalized_source) or ""
        resolved_provider_file_uri = provider_file_uri or (
            normalized_source if normalized_source.startswith("files/") else ""
        )
        resolved_gcs_uri = gcs_uri or (normalized_source if normalized_source.startswith("gs://") else "")
        video_bytes, mime_type = await download_google_video_asset_for_user(
            attachment_service.db,
            user_id,
            provider_file_name=resolved_provider_file_name or None,
            provider_file_uri=resolved_provider_file_uri or resolved_provider_file_name or None,
            gcs_uri=resolved_gcs_uri or None,
            mime_type=fallback_mime_type,
        )
        return video_bytes, mime_type or fallback_mime_type or "video/mp4"

    safe_url = validate_outbound_http_url(normalized_source)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response, _final_url = await get_with_redirect_guard(client, safe_url, max_redirects=5)
        response.raise_for_status()
        mime_type = (
            response.headers.get("content-type")
            or fallback_mime_type
            or "video/mp4"
        ).split(";", 1)[0].strip()
        return response.content, mime_type or "video/mp4"


async def safe_persist_video_last_frame_derivative(
    attachment_service: AttachmentService,
    *,
    video_payload: Dict[str, Any],
    session_id: str,
    message_id: str,
    user_id: str,
    source_url: Optional[str] = None,
    storage_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Extract the final video frame and persist it as a normal image attachment."""

    source = _video_payload_source(video_payload, explicit_source_url=source_url)
    if not source["source"]:
        return None

    try:
        video_bytes, video_mime_type = await load_video_result_bytes(
            attachment_service,
            source=source["source"],
            user_id=user_id,
            fallback_mime_type=source["mime_type"] or "video/mp4",
            provider_file_name=source["provider_file_name"],
            provider_file_uri=source["provider_file_uri"],
            gcs_uri=source["gcs_uri"],
        )
        frame = await asyncio.to_thread(
            extract_last_frame_image,
            LoadedSourceVideo(video_bytes=video_bytes, mime_type=video_mime_type or "video/mp4"),
        )
        frame_data_url = to_data_url(frame.image_bytes, frame.mime_type)
        processed = await safe_persist_ai_result(
            attachment_service,
            log_label="视频尾帧",
            log_with_traceback=False,
            ai_url=frame_data_url,
            mime_type=frame.mime_type or "image/png",
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            prefix="video-last-frame",
            storage_id=storage_id,
            filename=_last_frame_filename(source["filename"]),
        )
        if processed is None:
            return None

        return {
            "kind": "video_last_frame",
            "role": "last_frame",
            "url": processed.get("display_url") or "",
            "attachment_id": processed.get("attachment_id") or "",
            "upload_status": processed.get("status") or "pending",
            "task_id": processed.get("task_id"),
            "mime_type": processed.get("mime_type") or frame.mime_type or "image/png",
            "filename": processed.get("filename") or _last_frame_filename(source["filename"]),
            "session_id": processed.get("session_id") or session_id,
            "message_id": processed.get("message_id") or message_id,
            "user_id": processed.get("user_id") or user_id,
            "cloud_url": processed.get("cloud_url") or "",
            "derived_from_attachment_id": source["attachment_id"],
            "derived_from_video_url": source["source"],
        }
    except Exception as exc:
        logger.warning("[VideoDerivative] 视频尾帧派生失败: %s", exc)
        return None
