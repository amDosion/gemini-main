"""
OpenAI 视频生成器

处理 OpenAI 的视频生成操作（Sora）。
"""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote

import httpx

from ...core.sdk_executor import run_in_sdk_thread
from ...utils.url_security import get_with_redirect_guard, validate_outbound_http_url
from ...utils.attachment_handler import is_base64_url
from ..common.video_extension_chain import (
    is_video_extension_strategy,
    normalize_video_extension_count,
    run_last_frame_video_extension_chain,
)
from ..common.video_prompt_enhancement import (
    apply_video_prompt_enhancement_metadata,
    enhance_video_prompt_bundle,
)
from ..storage.local_provider import DEFAULT_LOCAL_URL_PREFIX, resolve_local_public_file_path
from ._shared import build_async_client, enhance_openai_video_prompt

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sora-2"
DEFAULT_SECONDS = "4"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_POLL_TIMEOUT_SECONDS = 900.0
TERMINAL_STATUSES = {"completed", "failed", "canceled", "cancelled"}

ALLOWED_MODELS = {
    "sora-2",
    "sora-2-pro",
    "sora-2-2025-10-06",
    "sora-2-pro-2025-10-06",
    "sora-2-2025-12-08",
}
ALLOWED_SIZES = {
    "sora-2": {"1280x720", "720x1280"},
    "sora-2-pro": {"1280x720", "720x1280", "1024x1792", "1792x1024"},
}
SIZE_BY_MODEL_AND_TIER = {
    "sora-2": {
        "1K": {"16:9": "1280x720", "9:16": "720x1280"},
    },
    "sora-2-pro": {
        "1K": {"16:9": "1280x720", "9:16": "720x1280"},
        "2K": {"16:9": "1792x1024", "9:16": "1024x1792"},
    },
}


class VideoGenerator:
    """
    OpenAI 视频生成器

    使用 Sora Videos API 创建任务、轮询状态并下载 MP4。
    """

    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = kwargs.get("timeout", 120.0)
        self.max_retries = kwargs.get("max_retries", 3)
        self.poll_interval = float(kwargs.get("poll_interval", DEFAULT_POLL_INTERVAL_SECONDS))
        self.poll_timeout = float(kwargs.get("poll_timeout", DEFAULT_POLL_TIMEOUT_SECONDS))

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai SDK is not installed. Install or upgrade the backend dependency before using Sora."
            ) from exc

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )
        self.prompt_client = build_async_client(
            api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

        logger.info(f"[OpenAI VideoGenerator] Initialized with base_url={self.base_url}")

    async def generate_video(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        **kwargs,
    ) -> Dict[str, Any]:
        logger.info(f"[OpenAI VideoGenerator] Video generation: model={model}, prompt={prompt[:80]}...")

        self._ensure_videos_resource()

        normalized_model = self._normalize_model(model)
        model_family = self._model_family(normalized_model)
        size = self._normalize_size(
            model_family,
            kwargs.get("size"),
            kwargs.get("resolution") or kwargs.get("image_resolution"),
            kwargs.get("aspect_ratio") or kwargs.get("image_aspect_ratio"),
        )
        seconds = self._normalize_seconds(kwargs.get("seconds"), kwargs.get("duration_seconds"))

        extension_count = normalize_video_extension_count(kwargs)
        operation = self._resolve_video_operation(kwargs)
        enhancement = await enhance_video_prompt_bundle(
            prompt=prompt,
            request_kwargs=dict(kwargs),
            extension_count=extension_count,
            enhance_requested=self._resolve_bool_option(kwargs, "enhance_prompt", "enhancePrompt", default=False),
            enhance_prompt=lambda value: self._maybe_enhance_prompt(value, operation, kwargs),
        )
        effective_prompt = enhancement.effective_prompt
        request_kwargs = enhancement.request_kwargs
        extension_count = normalize_video_extension_count(request_kwargs)
        if extension_count > 0:
            async def generate_segment(segment_prompt: str, segment_model: str, segment_kwargs: Dict[str, Any]) -> Dict[str, Any]:
                normalized_segment_model = self._normalize_model(segment_model)
                segment_family = self._model_family(normalized_segment_model)
                segment_size = self._normalize_size(
                    segment_family,
                    segment_kwargs.get("size") or size,
                    segment_kwargs.get("resolution") or request_kwargs.get("resolution") or request_kwargs.get("image_resolution"),
                    segment_kwargs.get("aspect_ratio") or request_kwargs.get("aspect_ratio") or request_kwargs.get("image_aspect_ratio"),
                )
                return await self._generate_video_once(
                    prompt=segment_prompt,
                    normalized_model=normalized_segment_model,
                    size=segment_size,
                    seconds=seconds,
                    request_kwargs=segment_kwargs,
                    enhanced_prompt=None,
                )

            result = await run_last_frame_video_extension_chain(
                provider_name="openai",
                prompt=effective_prompt,
                model=normalized_model,
                request_kwargs=request_kwargs,
                extension_count=extension_count,
                generate_segment=generate_segment,
                continuation_model=normalized_model,
                segment_seconds=int(seconds),
                load_source_video=self._load_source_video_bytes_for_chain,
                treat_source_video_as_existing_base=is_video_extension_strategy(
                    request_kwargs.get("video_input_strategy") or request_kwargs.get("videoInputStrategy")
                ),
            )
            return apply_video_prompt_enhancement_metadata(result, enhancement)

        return await self._generate_video_once(
            prompt=effective_prompt,
            normalized_model=normalized_model,
            size=size,
            seconds=seconds,
            request_kwargs=request_kwargs,
            enhanced_prompt=enhancement.enhanced_prompt,
        )

    async def _generate_video_once(
        self,
        *,
        prompt: str,
        normalized_model: str,
        size: str,
        seconds: str,
        request_kwargs: Dict[str, Any],
        enhanced_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        operation = self._resolve_video_operation(request_kwargs)
        image_reference_source = self._extract_image_reference_source(request_kwargs)
        source_video = (
            request_kwargs.get("source_video")
            or request_kwargs.get("sourceVideo")
            or request_kwargs.get("continuation_video")
            or request_kwargs.get("continuationVideo")
        )
        temp_paths: list[Path] = []
        if operation == "image_to_video" and image_reference_source:
            reference_bytes, reference_mime_type = await self._load_media_bytes(image_reference_source, "image/png")
            reference_path = self._write_reference_temp_file(reference_bytes, reference_mime_type)
            temp_paths.append(reference_path)
        else:
            reference_path = None

        video_reference: Any = None
        if operation in {"video_extension", "video_edit"}:
            video_reference, video_temp_path = await self._resolve_video_reference(source_video)
            if video_temp_path:
                temp_paths.append(video_temp_path)

        try:
            if operation == "video_extension":
                video = await run_in_sdk_thread(
                    self._extend_video_sync,
                    prompt,
                    seconds,
                    video_reference,
                )
            elif operation == "video_edit":
                video = await run_in_sdk_thread(
                    self._edit_video_sync,
                    prompt,
                    video_reference,
                )
            else:
                video = await run_in_sdk_thread(
                    self._create_video_sync,
                    normalized_model,
                    prompt,
                    size,
                    seconds,
                    reference_path,
                )
            video_id = self._get_video_id(video)
            if not video_id:
                raise RuntimeError("OpenAI video response did not include a video id.")

            video = await run_in_sdk_thread(self._poll_video_sync, video_id)
            status = self._get_status(video) or "unknown"
            if status != "completed":
                raise RuntimeError(self._extract_failure_message(video, video_id, status))

            video_bytes = await run_in_sdk_thread(self._download_video_sync, video_id)
            duration_seconds = int(seconds)
            result_payload = {
                "url": self._to_data_url(video_bytes, "video/mp4"),
                "mime_type": "video/mp4",
                "filename": f"{video_id}.mp4",
                "duration": duration_seconds,
                "duration_seconds": duration_seconds,
                "job_id": video_id,
                "model": normalized_model,
                "video_size": size,
                "video_input_strategy": operation,
                "status": status,
            }
            if enhanced_prompt:
                result_payload["enhanced_prompt"] = enhanced_prompt
                result_payload["prompt_enhancement_strategy"] = "local_llm"
            return result_payload
        finally:
            for temp_path in temp_paths:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    logger.warning("[OpenAI VideoGenerator] Failed to cleanup reference temp file: %s", temp_path)

    def _ensure_videos_resource(self) -> None:
        if not hasattr(self.client, "videos"):
            raise RuntimeError(
                "This openai SDK version does not expose the Videos API. Upgrade the backend openai package to a newer release."
            )

    def _normalize_model(self, model: Optional[str]) -> str:
        value = str(model or DEFAULT_MODEL).strip().lower()
        if value not in ALLOWED_MODELS:
            raise ValueError(f"Unsupported OpenAI video model: {model}")
        return value

    def _model_family(self, model: str) -> str:
        return "sora-2-pro" if "sora-2-pro" in model else "sora-2"

    def _normalize_size(
        self,
        model: str,
        explicit_size: Optional[str],
        resolution: Optional[str],
        aspect_ratio: Optional[str],
    ) -> str:
        if explicit_size:
            size = str(explicit_size).strip().lower()
            if size in ALLOWED_SIZES[model]:
                return size
            raise ValueError(f"Unsupported size '{explicit_size}' for model '{model}'")

        normalized_aspect_ratio = self._normalize_aspect_ratio(aspect_ratio)
        normalized_resolution = self._normalize_resolution_tier(resolution)
        if normalized_resolution not in SIZE_BY_MODEL_AND_TIER[model]:
            raise ValueError(f"Unsupported video resolution tier '{normalized_resolution}' for model '{model}'")
        return SIZE_BY_MODEL_AND_TIER[model][normalized_resolution][normalized_aspect_ratio]

    def _normalize_aspect_ratio(self, aspect_ratio: Optional[str]) -> str:
        value = str(aspect_ratio or "16:9").strip()
        if value not in {"16:9", "9:16"}:
            raise ValueError(f"Unsupported video aspect_ratio: {value}")
        return value

    def _normalize_resolution_tier(self, resolution: Optional[str]) -> str:
        value = str(resolution or "1K").strip().upper()
        aliases = {
            "720P": "1K",
            "1280X720": "1K",
            "720X1280": "1K",
            "1080P": "2K",
            "1920X1080": "2K",
            "1080X1920": "2K",
            "1792X1024": "2K",
            "1024X1792": "2K",
        }
        normalized = aliases.get(value, value)
        if normalized not in {"1K", "2K"}:
            raise ValueError(f"Unsupported video resolution tier: {resolution}")
        return normalized

    def _normalize_seconds(self, seconds: Optional[Any], duration_seconds: Optional[Any]) -> str:
        raw_value = seconds if seconds is not None else duration_seconds
        if raw_value is None:
            return DEFAULT_SECONDS

        try:
            value = int(str(raw_value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported video seconds value: {raw_value}") from exc

        if value <= 4:
            return "4"
        if value <= 8:
            return "8"
        return "12"

    def _resolve_video_operation(self, kwargs: Dict[str, Any]) -> str:
        strategy = str(
            kwargs.get("video_input_strategy")
            or kwargs.get("videoInputStrategy")
            or ""
        ).strip()
        if strategy in {"image_to_video", "first_frame_to_video"}:
            return "image_to_video"
        if strategy in {"video_extension", "video_continuation", "video_continuation_to_last_frame"}:
            return "video_extension"
        if strategy in {"video_edit", "masked_video_edit"}:
            return "video_edit"
        if kwargs.get("source_video") or kwargs.get("continuation_video"):
            return "video_extension"
        if kwargs.get("source_image"):
            return "image_to_video"
        if self._extract_reference_source(kwargs.get("reference_images")):
            return "image_to_video"
        return "text_to_video"

    async def _maybe_enhance_prompt(
        self,
        prompt: str,
        operation: str,
        kwargs: Dict[str, Any],
    ) -> Optional[str]:
        if not self._resolve_bool_option(kwargs, "enhance_prompt", "enhancePrompt", default=False):
            return None

        model_hint = (
            kwargs.get("enhance_prompt_model")
            or kwargs.get("enhancePromptModel")
            or kwargs.get("prompt_optimize_model")
            or kwargs.get("promptOptimizeModel")
        )
        if not str(model_hint or "").strip():
            logger.warning("[OpenAI VideoGenerator] Prompt enhancement requested without a selected text model.")
            return None

        enhanced = await enhance_openai_video_prompt(
            self.prompt_client,
            prompt,
            model_hint=str(model_hint).strip(),
            thinking_level=(
                kwargs.get("enhance_prompt_thinking_level")
                or kwargs.get("enhancePromptThinkingLevel")
            ),
            operation=operation,
        )
        if enhanced and enhanced.strip() and enhanced.strip() != str(prompt or "").strip():
            return enhanced.strip()
        return None

    def _resolve_bool_option(self, kwargs: Dict[str, Any], *keys: str, default: bool) -> bool:
        for key in keys:
            if key not in kwargs:
                continue
            value = kwargs.get(key)
            if value is None:
                continue
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        return default

    def _extract_image_reference_source(self, kwargs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        source_image = kwargs.get("source_image")
        if source_image:
            if isinstance(source_image, str):
                return {"url": source_image, "mime_type": None}
            if isinstance(source_image, dict):
                return source_image
        return self._extract_reference_source(kwargs.get("reference_images"))

    def _extract_reference_source(self, reference_images: Any) -> Optional[Dict[str, Any]]:
        if not reference_images:
            return None

        raw_reference = reference_images.get("raw") if isinstance(reference_images, dict) else reference_images
        if isinstance(raw_reference, list):
            raw_reference = raw_reference[0] if raw_reference else None

        if isinstance(raw_reference, str):
            return {"url": raw_reference, "mime_type": None}
        if isinstance(raw_reference, dict):
            url = (
                raw_reference.get("url")
                or raw_reference.get("raw_url")
                or raw_reference.get("rawUrl")
                or raw_reference.get("temp_url")
                or raw_reference.get("tempUrl")
            )
            if isinstance(url, str) and url:
                return {
                    "url": url,
                    "mime_type": raw_reference.get("mime_type") or raw_reference.get("mimeType"),
                }
        return None

    async def _resolve_video_reference(self, source_video: Any) -> Tuple[Any, Optional[Path]]:
        if not source_video:
            raise ValueError("OpenAI video submode requires a source video.")

        if isinstance(source_video, str):
            value = source_video.strip()
            if value.startswith("video_"):
                return {"id": value}, None
            content, mime_type = await self._load_media_bytes({"url": value}, "video/mp4")
            temp_path = self._write_reference_temp_file(content, mime_type)
            return temp_path, temp_path

        if isinstance(source_video, dict):
            video_id = str(
                source_video.get("id")
                or source_video.get("video_id")
                or source_video.get("videoId")
                or source_video.get("provider_file_uri")
                or source_video.get("providerFileUri")
                or source_video.get("provider_file_name")
                or source_video.get("providerFileName")
                or ""
            ).strip()
            if video_id.startswith("video_"):
                return {"id": video_id}, None

            url = (
                source_video.get("url")
                or source_video.get("temp_url")
                or source_video.get("tempUrl")
                or source_video.get("raw_url")
                or source_video.get("rawUrl")
                or source_video.get("base64_data")
                or source_video.get("base64Data")
            )
            if url:
                content, mime_type = await self._load_media_bytes(source_video, "video/mp4")
                temp_path = self._write_reference_temp_file(content, mime_type)
                return temp_path, temp_path

        raise ValueError("OpenAI video submode requires a source video id or video file reference.")

    async def _load_source_video_bytes_for_chain(self, source_video: Any) -> Tuple[bytes, str]:
        video_id = ""
        if isinstance(source_video, str):
            candidate = source_video.strip()
            if candidate.startswith("video_"):
                video_id = candidate
        elif isinstance(source_video, dict):
            video_id = str(
                source_video.get("id")
                or source_video.get("video_id")
                or source_video.get("videoId")
                or source_video.get("provider_file_uri")
                or source_video.get("providerFileUri")
                or source_video.get("provider_file_name")
                or source_video.get("providerFileName")
                or ""
            ).strip()
        if video_id.startswith("video_"):
            return await run_in_sdk_thread(self._download_video_sync, video_id), "video/mp4"
        if isinstance(source_video, str):
            return await self._load_media_bytes({"url": source_video}, "video/mp4")
        if isinstance(source_video, dict):
            return await self._load_media_bytes(source_video, "video/mp4")
        raise ValueError("OpenAI video extension requires a source video.")

    async def _load_media_bytes(self, reference_source: Dict[str, Any], fallback_mime_type: str) -> Tuple[bytes, str]:
        url = str(reference_source.get("url") or "").strip()
        fallback_mime_type = (
            str(
                reference_source.get("mime_type")
                or reference_source.get("mimeType")
                or fallback_mime_type
            ).strip()
            or fallback_mime_type
        )
        if not url:
            raise ValueError("Reference image is missing a usable URL.")

        if is_base64_url(url):
            return self._parse_data_url(url)

        if url.startswith(f"{DEFAULT_LOCAL_URL_PREFIX}/"):
            local_path = resolve_local_public_file_path(url) or resolve_local_public_file_path(unquote(url))
            if local_path and local_path.exists() and local_path.is_file():
                mime_type = mimetypes.guess_type(local_path.name)[0] or fallback_mime_type
                return local_path.read_bytes(), mime_type
            raise ValueError(f"Local storage media file not found for OpenAI video generation: {url[:80]}")

        path = Path(url)
        if path.exists() and path.is_file():
            mime_type = mimetypes.guess_type(path.name)[0] or fallback_mime_type
            return path.read_bytes(), mime_type

        safe_url = validate_outbound_http_url(url)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response, _ = await get_with_redirect_guard(client, safe_url, max_redirects=5)
            response.raise_for_status()
            mime_type = (response.headers.get("content-type") or fallback_mime_type).split(";")[0]
            return response.content, mime_type

    def _write_reference_temp_file(self, content: bytes, mime_type: Optional[str]) -> Path:
        suffix = self._suffix_for_mime_type(mime_type)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            return Path(temp_file.name)

    def _suffix_for_mime_type(self, mime_type: Optional[str]) -> str:
        normalized = (mime_type or "").split(";")[0].strip().lower()
        guessed = mimetypes.guess_extension(normalized)
        if guessed:
            return guessed
        if normalized in {"image/jpeg", "image/jpg"}:
            return ".jpg"
        if normalized == "image/webp":
            return ".webp"
        if normalized == "video/mp4":
            return ".mp4"
        if normalized == "video/webm":
            return ".webm"
        return ".png"

    def _create_video_sync(
        self,
        model: str,
        prompt: str,
        size: str,
        seconds: str,
        reference_path: Optional[Path],
    ) -> Any:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "seconds": seconds,
        }

        if reference_path:
            with reference_path.open("rb") as reference_file:
                payload["input_reference"] = reference_file
                return self.client.videos.create(**payload)

        return self.client.videos.create(**payload)

    def _extend_video_sync(
        self,
        prompt: str,
        seconds: str,
        video_reference: Any,
    ) -> Any:
        return self.client.videos.extend(
            video=video_reference,
            prompt=prompt,
            seconds=seconds,
        )

    def _edit_video_sync(
        self,
        prompt: str,
        video_reference: Any,
    ) -> Any:
        return self.client.videos.edit(
            video=video_reference,
            prompt=prompt,
        )

    def _poll_video_sync(self, video_id: str) -> Any:
        import time

        start_time = time.time()
        last_status: Optional[str] = None

        # Exponential backoff bounded by [poll_interval, 10s] with a 1.5x
        # growth factor. Sync ``time.sleep`` here is intentional — this
        # function runs inside ``asyncio.to_thread``. Starting from the
        # configured ``poll_interval`` keeps observable timing close to the
        # previous fixed-interval behavior; the cap simply avoids burning
        # poll requests on long-running jobs.
        initial_interval = max(float(self.poll_interval), 1.0)
        max_interval = max(10.0, initial_interval)
        current_interval = initial_interval

        # Hard iteration safeguard: prevents an infinite loop if the time
        # ceiling is never tripped (e.g. ``poll_timeout`` misconfigured).
        max_iterations = 600

        for _ in range(max_iterations):
            video = self.client.videos.retrieve(video_id)
            status = self._get_status(video) or "unknown"
            if status != last_status:
                logger.info("[OpenAI VideoGenerator] job=%s status=%s", video_id, status)
                last_status = status
            if status in TERMINAL_STATUSES:
                return video
            if time.time() - start_time > self.poll_timeout:
                raise TimeoutError(f"Timed out waiting for OpenAI video job {video_id}")
            time.sleep(current_interval)
            current_interval = min(current_interval * 1.5, max_interval)

        raise TimeoutError(
            f"Exceeded {max_iterations} poll iterations waiting for OpenAI video job {video_id}"
        )

    def _download_video_sync(self, video_id: str) -> bytes:
        content = self.client.videos.download_content(video_id, variant="video")
        if hasattr(content, "write_to_file"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                temp_path = Path(temp_file.name)
            try:
                content.write_to_file(temp_path)
                return temp_path.read_bytes()
            finally:
                temp_path.unlink(missing_ok=True)
        if hasattr(content, "read"):
            return content.read()
        if hasattr(content, "content"):
            return content.content
        if isinstance(content, bytearray):
            return bytes(content)
        if isinstance(content, bytes):
            return content
        raise RuntimeError(f"Unsupported video content response type: {type(content).__name__}")

    def _get_status(self, video: Any) -> Optional[str]:
        if isinstance(video, dict):
            status = video.get("status") or video.get("state")
            return str(status) if isinstance(status, str) else None
        for field in ("status", "state"):
            value = getattr(video, field, None)
            if isinstance(value, str):
                return value
        return None

    def _get_video_id(self, video: Any) -> Optional[str]:
        if isinstance(video, dict):
            video_id = video.get("id")
            return str(video_id) if isinstance(video_id, str) else None
        value = getattr(video, "id", None)
        return str(value) if isinstance(value, str) else None

    def _extract_failure_message(self, video: Any, video_id: str, status: str) -> str:
        error_message = None
        if isinstance(video, dict):
            error = video.get("error")
            if isinstance(error, dict):
                error_message = error.get("message")
            elif isinstance(error, str):
                error_message = error
        else:
            error = getattr(video, "error", None)
            if isinstance(error, dict):
                error_message = error.get("message")
            elif hasattr(error, "message"):
                error_message = getattr(error, "message", None)
            elif isinstance(error, str):
                error_message = error
        return error_message or f"OpenAI video job {video_id} finished with status '{status}'"

    def _parse_data_url(self, data_url: str) -> Tuple[bytes, str]:
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(":", 1)[1].split(";", 1)[0]
        return base64.b64decode(encoded), mime_type

    def _to_data_url(self, content: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
