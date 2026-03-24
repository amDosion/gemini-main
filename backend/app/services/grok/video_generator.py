"""
Grok 视频生成器

处理 Grok 的视频生成操作（grok-imagine-1.0-video）。
使用 httpx 调用 grok2api 的 /videos 端点。
"""
from __future__ import annotations
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "grok-imagine-1.0-video"
DEFAULT_SECONDS = 6

SIZE_TO_ASPECT = {
    "1280x720": "16:9",
    "720x1280": "9:16",
    "1792x1024": "3:2",
    "1024x1792": "2:3",
    "1024x1024": "1:1",
}

ASPECT_RATIO_TO_SIZE = {
    "16:9": "1280x720",
    "9:16": "720x1280",
    "3:2": "1792x1024",
    "2:3": "1024x1792",
    "1:1": "1024x1024",
}

QUALITY_TO_RESOLUTION = {
    "standard": "480p",
    "high": "720p",
}


class VideoGenerator:
    """
    Grok 视频生成器

    使用 httpx 调用 grok2api 的视频生成端点。
    """

    def __init__(self, api_key: str, base_url: str, timeout: float = 600.0):
        """
        初始化视频生成器

        Args:
            api_key: API key for Bearer auth
            base_url: grok2api base URL (e.g. http://localhost:8000/v1)
            timeout: Request timeout in seconds (video gen can be slow)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.info(f"[Grok VideoGenerator] Initialized with base_url={self.base_url}")

    def _resolve_size(self, kwargs: Dict[str, Any]) -> str:
        """Resolve video size from kwargs."""
        size = kwargs.get("size") or kwargs.get("image_resolution")
        if size and size in SIZE_TO_ASPECT:
            return size
        aspect_ratio = kwargs.get("aspect_ratio") or kwargs.get("image_aspect_ratio")
        if aspect_ratio and aspect_ratio in ASPECT_RATIO_TO_SIZE:
            return ASPECT_RATIO_TO_SIZE[aspect_ratio]
        return "1792x1024"

    def _resolve_seconds(self, kwargs: Dict[str, Any]) -> int:
        """Resolve video duration in seconds."""
        seconds = kwargs.get("seconds") or kwargs.get("duration_seconds")
        if seconds is not None:
            try:
                value = int(seconds)
                return max(6, min(value, 30))
            except (TypeError, ValueError):
                pass
        return DEFAULT_SECONDS

    def _resolve_quality(self, kwargs: Dict[str, Any]) -> str:
        """Resolve video quality."""
        quality = kwargs.get("quality", "standard")
        if quality in QUALITY_TO_RESOLUTION:
            return quality
        return "standard"

    async def generate_video(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用 grok-imagine-1.0-video 生成视频

        Args:
            prompt: 视频描述文本
            model: 模型名称 (grok-imagine-1.0-video)
            **kwargs: 额外参数:
                - size (str): 视频尺寸
                - seconds (int): 视频时长 (6-30)
                - quality (str): 视频质量 (standard/high)
                - aspect_ratio (str): 宽高比
                - reference_images: 参考图片

        Returns:
            包含 url/mime_type/filename 等字段的统一视频结果
        """
        try:
            logger.info(f"[Grok VideoGenerator] Video generation: model={model}, prompt={prompt[:80]}...")

            size = self._resolve_size(kwargs)
            seconds = self._resolve_seconds(kwargs)
            quality = self._resolve_quality(kwargs)

            request_body: Dict[str, Any] = {
                "prompt": prompt,
                "model": model,
                "size": size,
                "seconds": seconds,
                "quality": quality,
            }

            # Handle reference images
            ref_images = kwargs.get("reference_images")
            if ref_images:
                raw_refs = ref_images.get("raw", []) if isinstance(ref_images, dict) else ref_images
                if isinstance(raw_refs, list) and raw_refs:
                    first_ref = raw_refs[0]
                    ref_url = ""
                    if isinstance(first_ref, dict):
                        ref_url = (
                            first_ref.get("url")
                            or first_ref.get("temp_url")
                            or first_ref.get("tempUrl")
                            or ""
                        )
                    elif isinstance(first_ref, str):
                        ref_url = first_ref
                    if ref_url:
                        request_body["image_reference"] = {"image_url": ref_url}

            url = f"{self.base_url}/videos"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()

            # Parse response
            video_url = data.get("url", "")
            if not video_url:
                raise RuntimeError("Grok video response did not contain a video URL.")

            result = {
                "url": video_url,
                "mime_type": "video/mp4",
                "filename": f"{data.get('id', 'grok_video')}.mp4",
                "duration": seconds,
                "duration_seconds": seconds,
                "model": model,
                "video_size": size,
                "status": data.get("status", "completed"),
            }

            logger.info(f"[Grok VideoGenerator] Video generated: url={video_url[:80]}...")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"[Grok VideoGenerator] HTTP error: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[Grok VideoGenerator] Video generation error: {e}", exc_info=True)
            raise
