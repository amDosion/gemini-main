"""Shared Google video asset download helpers."""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .video_common import normalize_gemini_file_name
from ..coordinators.video_generation_coordinator import VideoGenerationCoordinator


async def download_google_video_asset_for_user(
    db: Session,
    user_id: str,
    *,
    provider_file_name: Optional[str] = None,
    provider_file_uri: Optional[str] = None,
    gcs_uri: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> Tuple[bytes, str]:
    coordinator = VideoGenerationCoordinator(
        api_key=None,
        user_id=user_id,
        db=db,
    )
    payload = await coordinator.download_video_asset(
        provider_file_name=provider_file_name or normalize_gemini_file_name(provider_file_uri),
        provider_file_uri=provider_file_uri,
        gcs_uri=gcs_uri,
        mime_type=mime_type,
    )
    binary = payload.get("video_bytes")
    resolved_mime = str(payload.get("mime_type") or mime_type or "video/mp4").strip() or "video/mp4"
    if not isinstance(binary, (bytes, bytearray)):
        raise RuntimeError("Google video asset download returned an unsupported payload.")
    return bytes(binary), resolved_mime
