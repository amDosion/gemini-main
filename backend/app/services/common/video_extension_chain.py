"""Provider-neutral last-frame video extension chaining.

The chain mirrors the Google high-resolution continuation fallback:
generate a segment, extract its last frame, feed that frame into the next
image-to-video request, then concatenate the resulting segments.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote

import httpx

from ...utils.attachment_handler import is_base64_url
from ...utils.url_security import get_with_redirect_guard, validate_outbound_http_url
from ..gemini.base.video_common import LoadedSourceVideo, parse_data_url, to_data_url
from ..gemini.base.video_frame_bridge import extract_last_frame_image
from ..storage.local_provider import DEFAULT_LOCAL_URL_PREFIX, resolve_local_public_file_path

logger = logging.getLogger(__name__)

LAST_FRAME_CONTINUATION_TRIM_SECONDS = 1.0
VIDEO_EXTENSION_STRATEGY_IDS = {
    "video_extension",
    "video_continuation",
    "video_continuation_to_last_frame",
}


VideoSegmentGenerator = Callable[[str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
SourceVideoLoader = Callable[[Any], Awaitable[Tuple[bytes, str]]]


def normalize_video_extension_count(kwargs: Dict[str, Any]) -> int:
    raw_value = kwargs.get("video_extension_count")
    if raw_value is None:
        raw_value = kwargs.get("videoExtensionCount")
    if raw_value is None:
        return 0
    try:
        candidate = int(str(raw_value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported video extension count: {raw_value}") from exc
    if candidate < 0:
        raise ValueError(f"Unsupported video extension count: {raw_value}")
    return candidate


def normalize_storyboard_segments(kwargs: Dict[str, Any]) -> List[str]:
    raw_value = kwargs.get("storyboard_segments")
    if raw_value is None:
        raw_value = kwargs.get("storyboardSegments")
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        return [candidate] if candidate else []
    if not isinstance(raw_value, list):
        return []

    segments: List[str] = []
    for item in raw_value:
        if isinstance(item, str):
            segments.append(item.strip())
            continue
        if isinstance(item, dict):
            text = (
                item.get("prompt")
                or item.get("text")
                or item.get("storyboard_prompt")
                or item.get("storyboardPrompt")
                or ""
            )
            segments.append(str(text).strip())
    return segments


def is_video_extension_strategy(value: Any) -> bool:
    return str(value or "").strip() in VIDEO_EXTENSION_STRATEGY_IDS


def _extract_source_video_value(kwargs: Dict[str, Any]) -> Any:
    for key in ("source_video", "sourceVideo", "continuation_video", "continuationVideo"):
        value = kwargs.get(key)
        if value is not None:
            return value
    return None


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        candidate = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return candidate if candidate > 0 else default


def _extract_media_url(source: Any) -> str:
    if isinstance(source, str):
        return source.strip()
    if not isinstance(source, dict):
        return ""

    raw_source = source.get("raw", source)
    if isinstance(raw_source, str):
        return raw_source.strip()
    if not isinstance(raw_source, dict):
        return ""

    for key in (
        "url",
        "videoUrl",
        "video_url",
        "raw_url",
        "rawUrl",
        "temp_url",
        "tempUrl",
        "base64_data",
        "base64Data",
        "file_uri",
        "fileUri",
        "provider_file_uri",
        "providerFileUri",
        "provider_file_name",
        "providerFileName",
        "uri",
    ):
        value = raw_source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_mime_type(source: Any, fallback_mime_type: str) -> str:
    if not isinstance(source, dict):
        return fallback_mime_type
    raw_source = source.get("raw", source)
    if not isinstance(raw_source, dict):
        return fallback_mime_type
    return str(
        raw_source.get("mime_type")
        or raw_source.get("mimeType")
        or raw_source.get("content_type")
        or raw_source.get("contentType")
        or fallback_mime_type
    ).split(";", 1)[0].strip() or fallback_mime_type


async def load_video_bytes_from_source(
    source: Any,
    *,
    fallback_mime_type: str = "video/mp4",
    load_source_video: Optional[SourceVideoLoader] = None,
) -> Tuple[bytes, str]:
    if load_source_video is not None:
        loaded = await load_source_video(source)
        if loaded and isinstance(loaded[0], (bytes, bytearray)):
            return bytes(loaded[0]), str(loaded[1] or fallback_mime_type)

    url = _extract_media_url(source)
    mime_type = _extract_mime_type(source, fallback_mime_type)
    if not url:
        raise ValueError("Video extension source is missing a downloadable URL.")

    if is_base64_url(url):
        return parse_data_url(url)

    local_url = unquote(url)
    if local_url.startswith(f"{DEFAULT_LOCAL_URL_PREFIX}/"):
        local_path = resolve_local_public_file_path(local_url) or resolve_local_public_file_path(url)
        if local_path and local_path.exists() and local_path.is_file():
            return local_path.read_bytes(), mimetypes.guess_type(local_path.name)[0] or mime_type
        raise ValueError(f"Local storage video file was not found: {url[:120]}")

    # CANON-027/028: do NOT read an arbitrary local filesystem path. Legit local
    # media is served via the allow-rooted DEFAULT_LOCAL_URL_PREFIX branch above; a
    # raw absolute / file:// path from a (user/model-influenced) source is denied
    # rather than read straight off disk.
    if (
        url.startswith("/")
        or url.startswith("file://")
        or local_url.startswith("/")
        or local_url.startswith("file://")
    ):
        raise ValueError(f"Local file reference is not an allowed storage path: {url[:120]}")

    safe_url = validate_outbound_http_url(url)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response, _ = await get_with_redirect_guard(client, safe_url, max_redirects=5)
        response.raise_for_status()
        response_mime_type = (response.headers.get("content-type") or mime_type).split(";", 1)[0].strip()
        return response.content, response_mime_type or mime_type


async def build_last_frame_source_image(video_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    source_image = await asyncio.to_thread(
        extract_last_frame_image,
        LoadedSourceVideo(video_bytes=video_bytes, mime_type=mime_type),
    )
    return {
        "url": to_data_url(source_image.image_bytes, source_image.mime_type),
        "mime_type": source_image.mime_type,
    }


def build_continuation_kwargs(base_kwargs: Dict[str, Any], source_image: Dict[str, Any]) -> Dict[str, Any]:
    next_kwargs = dict(base_kwargs)
    next_kwargs["source_image"] = source_image
    next_kwargs["video_input_strategy"] = "image_to_video"
    for key in (
        "sourceImage",
        "start_frame_image",
        "startFrameImage",
        "source_video",
        "sourceVideo",
        "continuation_video",
        "continuationVideo",
        "last_frame_image",
        "lastFrameImage",
        "video_mask_image",
        "videoMaskImage",
        "mask_image",
        "maskImage",
        "use_last_frame_bridge",
        "continue_from_last_frame",
        "continueFromLastFrame",
        "video_extension_count",
        "videoExtensionCount",
    ):
        next_kwargs.pop(key, None)
    return next_kwargs


def build_extension_segment_prompts(
    *,
    prompt: str,
    request_kwargs: Dict[str, Any],
    extension_count: int,
    segment_seconds: int,
) -> List[str]:
    raw_segments = normalize_storyboard_segments(request_kwargs)
    segments = raw_segments[:extension_count]
    if extension_count > 0 and len(raw_segments) > extension_count and segments:
        segments[-1] = "\n".join(raw_segments[extension_count - 1 :]).strip()

    base_prompt = str(prompt or "").strip()
    prompts: List[str] = []
    for index in range(extension_count):
        start_seconds = index * segment_seconds
        end_seconds = start_seconds + segment_seconds
        segment_prompt = segments[index].strip() if index < len(segments) else ""
        parts = [
            base_prompt,
            "",
            "Continuation segment requirements:",
            "- Continue seamlessly from the previous segment's final frame.",
            f"- This is extension segment {index + 1} of {extension_count}, targeting the continuation timeline around {start_seconds}-{end_seconds}s.",
            "- Generate only this continuation segment; do not restart the video from the beginning.",
            "- Preserve identity, wardrobe, environment continuity, camera direction, lighting, motion direction, and pacing.",
        ]
        if segment_prompt:
            parts.extend(
                [
                    "",
                    "Strict storyboard prompt for this continuation segment:",
                    segment_prompt,
                ]
            )
        prompts.append("\n".join(parts).strip())
    return prompts


async def concatenate_video_segments(
    segments: List[Tuple[bytes, str]],
    *,
    continuation_trim_seconds: float,
) -> bytes:
    return await asyncio.to_thread(
        _concatenate_video_segments_sync,
        segments,
        continuation_trim_seconds,
    )


def _concat_list_line(path: Path) -> str:
    return f"file '{path}'\n"


def _concatenate_video_segments_sync(
    segments: List[Tuple[bytes, str]],
    continuation_trim_seconds: float,
) -> bytes:
    if not segments:
        raise ValueError("Video extension requires at least one segment.")
    if len(segments) == 1:
        return segments[0][0]

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg is required to assemble last-frame extension segments.")

    with tempfile.TemporaryDirectory(prefix="video-extension-chain-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        prepared_paths: List[Path] = []
        for index, (segment_bytes, _mime_type) in enumerate(segments):
            segment_path = tmp_root / f"segment-{index:03d}.mp4"
            segment_path.write_bytes(segment_bytes)
            if index == 0 or continuation_trim_seconds <= 0:
                prepared_paths.append(segment_path)
                continue

            trimmed_path = tmp_root / f"segment-{index:03d}-trimmed.mp4"
            subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{continuation_trim_seconds:.3f}",
                    "-i",
                    str(segment_path),
                    "-map",
                    "0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(trimmed_path),
                ],
                check=True,
                capture_output=True,
            )
            prepared_paths.append(trimmed_path)

        concat_list_path = tmp_root / "segments.txt"
        concat_list_path.write_text("".join(_concat_list_line(path) for path in prepared_paths), encoding="utf-8")
        output_path = tmp_root / "joined.mp4"
        concat_cmd = [
            ffmpeg_path,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        try:
            subprocess.run(concat_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_list_path),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )
        return output_path.read_bytes()


def _without_extension_count(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(kwargs)
    cleaned.pop("video_extension_count", None)
    cleaned.pop("videoExtensionCount", None)
    return cleaned


async def run_last_frame_video_extension_chain(
    *,
    provider_name: str,
    prompt: str,
    model: str,
    request_kwargs: Dict[str, Any],
    extension_count: int,
    generate_segment: VideoSegmentGenerator,
    continuation_model: Optional[str] = None,
    segment_seconds: int,
    load_source_video: Optional[SourceVideoLoader] = None,
    continuation_trim_seconds: float = LAST_FRAME_CONTINUATION_TRIM_SECONDS,
    treat_source_video_as_existing_base: bool = True,
) -> Dict[str, Any]:
    if extension_count <= 0:
        raise ValueError("Video extension chain requires extension_count > 0.")

    base_kwargs = _without_extension_count(request_kwargs)
    source_video = _extract_source_video_value(base_kwargs)
    segments: List[Tuple[bytes, str]] = []
    job_ids: List[str] = []
    generated_results: List[Dict[str, Any]] = []
    continued_from_video = source_video is not None and treat_source_video_as_existing_base
    segment_seconds = _coerce_positive_int(segment_seconds, 8)

    if continued_from_video:
        current_video_bytes, current_mime_type = await load_video_bytes_from_source(
            source_video,
            fallback_mime_type="video/mp4",
            load_source_video=load_source_video,
        )
        segments.append((current_video_bytes, current_mime_type))
    else:
        first_result = await generate_segment(prompt, model, base_kwargs)
        generated_results.append(first_result)
        first_bytes, current_mime_type = await load_video_bytes_from_source(
            first_result,
            fallback_mime_type=str(first_result.get("mime_type") or "video/mp4"),
        )
        current_video_bytes = first_bytes
        segments.append((current_video_bytes, current_mime_type))
        if first_result.get("job_id") or first_result.get("task_id"):
            job_ids.append(str(first_result.get("job_id") or first_result.get("task_id")))

    extension_prompts = build_extension_segment_prompts(
        prompt=prompt,
        request_kwargs=base_kwargs,
        extension_count=extension_count,
        segment_seconds=segment_seconds,
    )
    next_model = continuation_model or model

    for index in range(extension_count):
        source_image = await build_last_frame_source_image(current_video_bytes, current_mime_type)
        continuation_kwargs = build_continuation_kwargs(base_kwargs, source_image)
        segment_prompt = extension_prompts[index] if index < len(extension_prompts) else prompt
        result = await generate_segment(segment_prompt, next_model, continuation_kwargs)
        generated_results.append(result)
        current_video_bytes, current_mime_type = await load_video_bytes_from_source(
            result,
            fallback_mime_type=str(result.get("mime_type") or "video/mp4"),
        )
        segments.append((current_video_bytes, current_mime_type))
        if result.get("job_id") or result.get("task_id"):
            job_ids.append(str(result.get("job_id") or result.get("task_id")))

    joined_bytes = await concatenate_video_segments(
        segments,
        continuation_trim_seconds=continuation_trim_seconds,
    )
    last_result = dict(generated_results[-1] if generated_results else {})
    total_duration_seconds = (
        extension_count * segment_seconds
        if continued_from_video
        else (extension_count + 1) * segment_seconds
    )
    last_result.update(
        {
            "url": to_data_url(joined_bytes, "video/mp4"),
            "mime_type": "video/mp4",
            "filename": f"{provider_name}-extended-video.mp4",
            "duration": total_duration_seconds,
            "duration_seconds": total_duration_seconds,
            "total_duration_seconds": total_duration_seconds,
            "video_extension_count": extension_count,
            "video_extension_applied": extension_count,
            "segment_count": len(segments),
            "segment_join_strategy": "ffmpeg_concat_trimmed_bridge",
            "continuation_strategy": "last_frame_bridge_chain",
            "continued_from_video": continued_from_video,
            "extension_job_ids": job_ids,
            "storyboard_segments": normalize_storyboard_segments(base_kwargs),
            "model": model,
        }
    )
    for key in (
        "provider_file_uri",
        "providerFileUri",
        "provider_file_name",
        "providerFileName",
        "gcs_uri",
        "gcsUri",
        "file_uri",
        "fileUri",
    ):
        last_result.pop(key, None)
    logger.info(
        "[VideoExtensionChain] provider=%s model=%s extensions=%s segments=%s continued_from_video=%s",
        provider_name,
        model,
        extension_count,
        len(segments),
        continued_from_video,
    )
    return last_result
