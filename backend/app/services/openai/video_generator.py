"""
OpenAI 视频生成器

处理 OpenAI 的视频生成操作（Sora）。
"""
from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional, Tuple

import httpx

from ...utils.url_security import get_with_redirect_guard, validate_outbound_http_url

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sora-2"
DEFAULT_SECONDS = "4"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_POLL_TIMEOUT_SECONDS = 900.0
TERMINAL_STATUSES = {"completed", "failed", "canceled", "cancelled"}

ALLOWED_MODELS = {"sora-2", "sora-2-pro"}
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
        size = self._normalize_size(
            normalized_model,
            kwargs.get("size"),
            kwargs.get("resolution") or kwargs.get("image_resolution"),
            kwargs.get("aspect_ratio") or kwargs.get("image_aspect_ratio"),
        )
        seconds = self._normalize_seconds(kwargs.get("seconds"), kwargs.get("duration_seconds"))

        reference_source = self._extract_reference_source(kwargs.get("reference_images"))
        reference_path: Optional[Path] = None
        if reference_source:
            reference_bytes, reference_mime_type = await self._load_reference_bytes(reference_source)
            reference_path = self._write_reference_temp_file(reference_bytes, reference_mime_type)

        try:
            video = await asyncio.to_thread(
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

            video = await asyncio.to_thread(self._poll_video_sync, video_id)
            status = self._get_status(video) or "unknown"
            if status != "completed":
                raise RuntimeError(self._extract_failure_message(video, video_id, status))

            video_bytes = await asyncio.to_thread(self._download_video_sync, video_id)
            duration_seconds = int(seconds)
            return {
                "url": self._to_data_url(video_bytes, "video/mp4"),
                "mime_type": "video/mp4",
                "filename": f"{video_id}.mp4",
                "duration": duration_seconds,
                "duration_seconds": duration_seconds,
                "job_id": video_id,
                "model": normalized_model,
                "video_size": size,
                "status": status,
            }
        finally:
            if reference_path:
                try:
                    reference_path.unlink(missing_ok=True)
                except Exception:
                    logger.warning("[OpenAI VideoGenerator] Failed to cleanup reference temp file: %s", reference_path)

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

    async def _load_reference_bytes(self, reference_source: Dict[str, Any]) -> Tuple[bytes, str]:
        url = str(reference_source.get("url") or "").strip()
        fallback_mime_type = str(reference_source.get("mime_type") or "").strip() or "image/png"
        if not url:
            raise ValueError("Reference image is missing a usable URL.")

        if url.startswith("data:"):
            return self._parse_data_url(url)

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
        if normalized in {"image/jpeg", "image/jpg"}:
            return ".jpg"
        if normalized == "image/webp":
            return ".webp"
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

    def _poll_video_sync(self, video_id: str) -> Any:
        import time

        start_time = time.time()
        last_status: Optional[str] = None

        while True:
            video = self.client.videos.retrieve(video_id)
            status = self._get_status(video) or "unknown"
            if status != last_status:
                logger.info("[OpenAI VideoGenerator] job=%s status=%s", video_id, status)
                last_status = status
            if status in TERMINAL_STATUSES:
                return video
            if time.time() - start_time > self.poll_timeout:
                raise TimeoutError(f"Timed out waiting for OpenAI video job {video_id}")
            time.sleep(self.poll_interval)

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
