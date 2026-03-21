"""
Shared helpers for Google Veo video generation.

This module centralizes request normalization so Gemini API and Vertex AI
services use the same provider-mode contract.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import httpx

from ...common.google_model_catalog import VEO_VIDEO_MODELS
from ....utils.url_security import get_with_redirect_guard, validate_outbound_http_url

DEFAULT_VIDEO_MODEL = "veo-3.1-generate-preview"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_RESOLUTION = "720p"
DEFAULT_DURATION_SECONDS = 8
VIDEO_EXTENSION_DURATION_SECONDS = 7
SUPPORTED_ASPECT_RATIOS = {"16:9", "9:16"}
SUPPORTED_RESOLUTIONS = {"720p", "1080p", "4k"}
VEO31_VIDEO_MODELS = {
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
}
VEO2_VIDEO_MODELS = {
    "veo-2.0-generate-001",
}
REFERENCE_IMAGE_MODELS = {
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
}
FIRST_LAST_FRAME_MODELS = {
    "veo-3.1-generate-preview",
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
}
VIDEO_EDIT_MASK_MODELS = {
    "veo-2.0-generate-001",
}
VIDEO_MASK_MODE_ALIASES = {
    "INSERT": "INSERT",
    "REPLACE": "INSERT",
    "BACKGROUND": "INSERT",
    "BACKGROUND_REPLACE": "INSERT",
    "BACKGROUND-REPLACE": "INSERT",
    "REMOVE": "REMOVE",
    "REMOVE_OBJECT": "REMOVE",
    "REMOVE-OBJECT": "REMOVE",
    "REMOVE_STATIC": "REMOVE_STATIC",
    "REMOVE-STATIC": "REMOVE_STATIC",
    "OUTPAINT": "OUTPAINT",
}
RESOLUTION_ALIASES = {
    "1K": "720p",
    "720P": "720p",
    "1280X720": "720p",
    "1280*720": "720p",
    "720X1280": "720p",
    "720*1280": "720p",
    "2K": "1080p",
    "1080P": "1080p",
    "1920X1080": "1080p",
    "1920*1080": "1080p",
    "1080X1920": "1080p",
    "1080*1920": "1080p",
    "1792X1024": "1080p",
    "1792*1024": "1080p",
    "1024X1792": "1080p",
    "1024*1792": "1080p",
    "4K": "4k",
    "2160P": "4k",
    "3840X2160": "4k",
    "3840*2160": "4k",
    "2160X3840": "4k",
    "2160*3840": "4k",
}
MAX_REFERENCE_IMAGES = 3
VEO31_EXTENSION_OUTPUT_ADDED_SECONDS = 7
VEO31_MAX_VIDEO_EXTENSIONS = 20
VEO31_MAX_SOURCE_VIDEO_SECONDS = 141
VEO31_MAX_OUTPUT_VIDEO_SECONDS = 148


@dataclass(frozen=True)
class LoadedReferenceImage:
    image_bytes: bytes
    mime_type: str
    reference_type: Optional[str] = None


@dataclass(frozen=True)
class LoadedSourceVideo:
    video_bytes: bytes
    mime_type: str


@dataclass(frozen=True)
class ProviderVideoAssetRef:
    provider_file_name: Optional[str] = None
    provider_file_uri: Optional[str] = None
    gcs_uri: Optional[str] = None


@dataclass(frozen=True)
class SourceVideoUriRef:
    uri: str
    mime_type: Optional[str] = None


def normalize_gemini_file_name(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("files/"):
        suffix = raw[len("files/"):].strip().strip("/")
        if not suffix:
            return None
        return f"files/{suffix.split(':', 1)[0].split('/', 1)[0]}"
    if raw.startswith("https://"):
        parsed = urlparse(raw)
        marker = "/files/"
        if marker in parsed.path:
            suffix = parsed.path.split(marker, 1)[1].strip("/")
            if suffix:
                return f"files/{suffix.split(':', 1)[0].split('/', 1)[0]}"
    return None


def is_google_provider_video_uri(value: Optional[str]) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    return bool(
        raw.startswith("gs://")
        or raw.startswith("files/")
        or normalize_gemini_file_name(raw)
    )


def _extract_source_image_candidate(source_image: Any) -> Optional[Dict[str, Any]]:
    if not source_image:
        return None

    raw_source = source_image.get("raw", source_image) if isinstance(source_image, dict) else source_image
    if raw_source is None:
        return None

    if isinstance(raw_source, str):
        url = raw_source.strip()
        if url:
            return {"url": url, "mime_type": None}
        return None

    if not isinstance(raw_source, dict):
        return None

    url = (
        raw_source.get("url")
        or raw_source.get("imageUrl")
        or raw_source.get("image_url")
        or raw_source.get("raw_url")
        or raw_source.get("rawUrl")
        or raw_source.get("temp_url")
        or raw_source.get("tempUrl")
    )
    if isinstance(url, str) and url.strip():
        return {
            "url": url.strip(),
            "mime_type": raw_source.get("mime_type") or raw_source.get("mimeType"),
        }
    return None


def _extract_mask_image_candidate(source_image: Any) -> Optional[Dict[str, Any]]:
    if not source_image:
        return None
    if isinstance(source_image, dict):
        for key in ("mask", "video_mask_image", "videoMaskImage", "mask_image", "maskImage", "raw"):
            if key in source_image and source_image.get(key):
                return _extract_source_image_candidate(source_image.get(key))
    return _extract_source_image_candidate(source_image)


def normalize_model(model: Optional[str]) -> str:
    candidate = str(model or DEFAULT_VIDEO_MODEL).strip()
    short_name = candidate.split("/")[-1]
    lowered = short_name.lower()
    if lowered in {item.lower() for item in VEO_VIDEO_MODELS}:
        return short_name
    if lowered.startswith("veo-") and "generate" in lowered:
        return short_name
    raise ValueError(f"Unsupported Google video model: {model}")


def normalize_aspect_ratio(value: Optional[str]) -> str:
    candidate = str(value or DEFAULT_ASPECT_RATIO).strip()
    if candidate not in SUPPORTED_ASPECT_RATIOS:
        raise ValueError(
            f"Unsupported Google video aspect ratio '{candidate}'. Supported values: {sorted(SUPPORTED_ASPECT_RATIOS)}"
        )
    return candidate


def normalize_resolution(value: Optional[str]) -> str:
    candidate = str(value or DEFAULT_RESOLUTION).strip()
    normalized = RESOLUTION_ALIASES.get(candidate.upper(), candidate.lower())
    if normalized not in SUPPORTED_RESOLUTIONS:
        raise ValueError(
            f"Unsupported Google video resolution '{candidate}'. Supported values: {sorted(SUPPORTED_RESOLUTIONS)}"
        )
    return normalized


def normalize_duration_seconds(
    seconds: Optional[Any],
    duration_seconds: Optional[Any],
) -> int:
    raw_value = seconds if seconds is not None else duration_seconds
    if raw_value is None:
        return DEFAULT_DURATION_SECONDS
    try:
        candidate = int(str(raw_value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported Google video duration value: {raw_value}") from exc
    if candidate <= 0:
        raise ValueError(f"Unsupported Google video duration value: {raw_value}")
    return candidate


def normalize_video_extension_duration_seconds(
    duration_seconds: int,
    *,
    model: Optional[str] = None,
    has_source_video: bool,
) -> int:
    if has_source_video and is_veo31_model(model or ""):
        return DEFAULT_DURATION_SECONDS
    return duration_seconds


def is_veo31_model(model: str) -> bool:
    return str(model or "").strip().split("/")[-1] in VEO31_VIDEO_MODELS


def is_veo2_model(model: str) -> bool:
    return str(model or "").strip().split("/")[-1] in VEO2_VIDEO_MODELS


def validate_generation_constraints(
    *,
    model: str,
    api_mode: str,
    resolution: str,
    duration_seconds: int,
    has_source_video: bool,
    reference_image_count: int,
) -> None:
    if reference_image_count > MAX_REFERENCE_IMAGES:
        raise ValueError(
            f"Google video generation supports at most {MAX_REFERENCE_IMAGES} reference images."
        )

    if resolution == "4k" and not is_veo31_model(model):
        raise ValueError("Google video 4K output currently requires a Veo 3.1 model.")

    if reference_image_count > 0 and not is_reference_image_model(model):
        raise ValueError("Google video reference images currently require a Veo 3.1 model.")

    if is_veo31_model(model):
        requires_eight_seconds = (
            has_source_video
            or reference_image_count > 0
            or resolution in {"1080p", "4k"}
        )
        if requires_eight_seconds and duration_seconds != DEFAULT_DURATION_SECONDS:
            raise ValueError(
                "Veo 3.1 requires an 8-second duration when using video extension, reference images, 1080p, or 4K."
            )
        if has_source_video and api_mode == "gemini_api" and resolution != "720p":
            raise ValueError("Gemini API Veo 3.1 video extension currently requires 720p output resolution.")


def normalize_video_mask_mode(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value or "").strip().upper().replace("-", "_")
    if not normalized:
        return None
    return VIDEO_MASK_MODE_ALIASES.get(normalized)


def build_filename(model: str, resolution: str, aspect_ratio: str) -> str:
    safe_model = model.replace("/", "-")
    safe_ratio = aspect_ratio.replace(":", "x")
    return f"{safe_model}-{resolution}-{safe_ratio}.mp4"


def to_data_url(video_bytes: bytes, mime_type: str = "video/mp4") -> str:
    return f"data:{mime_type};base64,{base64.b64encode(video_bytes).decode('utf-8')}"


def _extract_reference_candidates(reference_images: Any) -> List[Dict[str, Any]]:
    if not reference_images:
        return []

    raw_reference = reference_images.get("raw") if isinstance(reference_images, dict) else reference_images
    if raw_reference is None:
        return []
    if not isinstance(raw_reference, list):
        raw_reference = [raw_reference]

    candidates: List[Dict[str, Any]] = []
    for item in raw_reference:
        if isinstance(item, str):
            url = item.strip()
            if url:
                candidates.append({"url": url, "mime_type": None, "reference_type": None})
            continue
        if not isinstance(item, dict):
            continue
        url = (
            item.get("url")
            or item.get("raw_url")
            or item.get("rawUrl")
            or item.get("temp_url")
            or item.get("tempUrl")
        )
        if isinstance(url, str) and url.strip():
            candidates.append(
                {
                    "url": url.strip(),
                    "mime_type": item.get("mime_type") or item.get("mimeType"),
                    "reference_type": item.get("reference_type") or item.get("referenceType"),
                }
            )
    return candidates


async def load_reference_images(
    reference_images: Any,
) -> List[LoadedReferenceImage]:
    loaded: List[LoadedReferenceImage] = []
    for candidate in _extract_reference_candidates(reference_images):
        image_bytes, mime_type = await load_reference_bytes(
            candidate["url"],
            fallback_mime_type=candidate.get("mime_type"),
        )
        loaded.append(
            LoadedReferenceImage(
                image_bytes=image_bytes,
                mime_type=mime_type,
                reference_type=_normalize_reference_type(candidate.get("reference_type")),
            )
        )
    return loaded


async def load_source_image(
    source_image: Any,
) -> Optional[LoadedReferenceImage]:
    candidate = _extract_source_image_candidate(source_image)
    if not candidate:
        return None

    image_bytes, mime_type = await load_reference_bytes(
        candidate["url"],
        fallback_mime_type=candidate.get("mime_type"),
    )
    return LoadedReferenceImage(
        image_bytes=image_bytes,
        mime_type=mime_type,
    )


async def load_mask_image(
    source_image: Any,
) -> Optional[LoadedReferenceImage]:
    candidate = _extract_mask_image_candidate(source_image)
    if not candidate:
        return None

    image_bytes, mime_type = await load_reference_bytes(
        candidate["url"],
        fallback_mime_type=candidate.get("mime_type"),
    )
    return LoadedReferenceImage(
        image_bytes=image_bytes,
        mime_type=mime_type,
    )


def _extract_source_video_candidate(source_video: Any) -> Optional[Dict[str, Any]]:
    if not source_video:
        return None

    raw_source = source_video.get("raw", source_video) if isinstance(source_video, dict) else source_video
    if raw_source is None:
        return None

    if isinstance(raw_source, str):
        url = raw_source.strip()
        if url:
            return {"url": url, "mime_type": None}
        return None

    if not isinstance(raw_source, dict):
        return None

    url = (
        raw_source.get("url")
        or raw_source.get("videoUrl")
        or raw_source.get("video_url")
        or raw_source.get("raw_url")
        or raw_source.get("rawUrl")
        or raw_source.get("temp_url")
        or raw_source.get("tempUrl")
    )
    if isinstance(url, str) and url.strip():
        return {
            "url": url.strip(),
            "mime_type": raw_source.get("mime_type") or raw_source.get("mimeType"),
        }
    return None


def extract_source_video_uri_ref(
    source_video: Any,
) -> Optional[SourceVideoUriRef]:
    if not source_video:
        return None

    raw_source = source_video.get("raw", source_video) if isinstance(source_video, dict) else source_video
    if raw_source is None:
        return None

    if isinstance(raw_source, str):
        candidate = raw_source.strip()
        if candidate and (
            candidate.startswith("gs://")
            or candidate.startswith("files/")
            or candidate.startswith("https://generativelanguage.googleapis.com/")
            or candidate.startswith("https://") and "/files/" in candidate
        ):
            return SourceVideoUriRef(uri=candidate, mime_type=None)
        return None

    if not isinstance(raw_source, dict):
        return None

    uri = (
        raw_source.get("provider_file_uri")
        or raw_source.get("providerFileUri")
        or raw_source.get("gcs_uri")
        or raw_source.get("gcsUri")
        or raw_source.get("provider_file_name")
        or raw_source.get("providerFileName")
        or raw_source.get("file_uri")
        or raw_source.get("fileUri")
        or raw_source.get("uri")
    )
    if not isinstance(uri, str) or not uri.strip():
        return None

    return SourceVideoUriRef(
        uri=uri.strip(),
        mime_type=raw_source.get("mime_type") or raw_source.get("mimeType"),
    )


async def load_source_video(
    source_video: Any,
) -> Optional[LoadedSourceVideo]:
    candidate = _extract_source_video_candidate(source_video)
    if not candidate:
        return None

    video_bytes, mime_type = await load_binary_bytes(
        candidate["url"],
        fallback_mime_type=candidate.get("mime_type"),
        default_mime_type="video/mp4",
    )
    return LoadedSourceVideo(video_bytes=video_bytes, mime_type=mime_type)


def _normalize_reference_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    candidate = str(value).strip().upper()
    if candidate in {"ASSET", "STYLE"}:
        return candidate
    return None


async def load_reference_bytes(
    url: str,
    *,
    fallback_mime_type: Optional[str] = None,
) -> Tuple[bytes, str]:
    return await load_binary_bytes(
        url,
        fallback_mime_type=fallback_mime_type,
        default_mime_type="image/png",
    )


async def load_binary_bytes(
    url: str,
    *,
    fallback_mime_type: Optional[str] = None,
    default_mime_type: str,
) -> Tuple[bytes, str]:
    normalized_url = str(url or "").strip()
    if not normalized_url:
        raise ValueError("Video generation input is missing a usable URL.")
    if normalized_url.startswith("data:"):
        return parse_data_url(normalized_url)

    safe_url = validate_outbound_http_url(normalized_url)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response, _ = await get_with_redirect_guard(client, safe_url, max_redirects=5)
        response.raise_for_status()
        mime_type = (
            response.headers.get("content-type")
            or fallback_mime_type
            or default_mime_type
        ).split(";")[0].strip()
        return response.content, mime_type or default_mime_type


def parse_data_url(data_url: str) -> Tuple[bytes, str]:
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError as exc:
        raise ValueError("Malformed data URL for Google video input.") from exc

    mime_type = "image/png"
    if header.startswith("data:"):
        header_body = header[5:]
        mime_type = header_body.split(";", 1)[0] or mime_type
    return base64.b64decode(encoded), mime_type


def infer_mime_type(filename: Optional[str], fallback: str = "image/png") -> str:
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or fallback


def save_bytes_to_temp_file(content: bytes, suffix: str) -> Path:
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return Path(temp_file.name)


def suffix_for_mime_type(mime_type: Optional[str]) -> str:
    normalized = str(mime_type or "").split(";", 1)[0].strip().lower()
    if normalized in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if normalized == "image/webp":
        return ".webp"
    if normalized == "image/png":
        return ".png"
    guessed = mimetypes.guess_extension(normalized)
    return guessed or ".bin"


def is_reference_image_model(model: str) -> bool:
    return str(model or "").strip().split("/")[-1] in REFERENCE_IMAGE_MODELS


def supports_first_last_frame_model(model: str) -> bool:
    return str(model or "").strip().split("/")[-1] in FIRST_LAST_FRAME_MODELS


def supports_video_edit_mask_model(model: str) -> bool:
    return str(model or "").strip().split("/")[-1] in VIDEO_EDIT_MASK_MODELS


def build_resolution_map(resolution: str, aspect_ratio: str) -> str:
    if resolution == "4k":
        return "3840*2160" if aspect_ratio == "16:9" else "2160*3840"
    if resolution == "1080p":
        return "1920*1080" if aspect_ratio == "16:9" else "1080*1920"
    return "1280*720" if aspect_ratio == "16:9" else "720*1280"


def extract_provider_video_asset_ref(video_payload: Any) -> ProviderVideoAssetRef:
    if video_payload is None:
        return ProviderVideoAssetRef()

    provider_file_name = str(
        getattr(video_payload, "name", None)
        or getattr(video_payload, "provider_file_name", None)
        or (video_payload.get("name") if isinstance(video_payload, dict) else "")
        or (video_payload.get("provider_file_name") if isinstance(video_payload, dict) else "")
        or (video_payload.get("providerFileName") if isinstance(video_payload, dict) else "")
        or ""
    ).strip() or None
    provider_file_uri = str(
        getattr(video_payload, "uri", None)
        or getattr(video_payload, "provider_file_uri", None)
        or getattr(video_payload, "gcs_uri", None)
        or (video_payload.get("uri") if isinstance(video_payload, dict) else "")
        or (video_payload.get("provider_file_uri") if isinstance(video_payload, dict) else "")
        or (video_payload.get("providerFileUri") if isinstance(video_payload, dict) else "")
        or (video_payload.get("gcs_uri") if isinstance(video_payload, dict) else "")
        or (video_payload.get("gcsUri") if isinstance(video_payload, dict) else "")
        or (video_payload.get("file_uri") if isinstance(video_payload, dict) else "")
        or (video_payload.get("fileUri") if isinstance(video_payload, dict) else "")
        or ""
    ).strip() or None
    normalized_gemini_file_name = normalize_gemini_file_name(provider_file_name or provider_file_uri)
    gcs_uri = provider_file_uri if provider_file_uri and provider_file_uri.startswith("gs://") else None

    return ProviderVideoAssetRef(
        provider_file_name=normalized_gemini_file_name or provider_file_name,
        provider_file_uri=provider_file_uri,
        gcs_uri=gcs_uri,
    )
