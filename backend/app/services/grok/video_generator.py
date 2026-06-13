"""
Grok 视频生成器

处理 Grok 的视频生成操作（grok-imagine-1.0-video）。
使用 httpx 调用 grok2api 的 /videos 端点。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from ...utils.log_sanitization import summarize_text_for_log, summarize_url_for_log
from ..common.video_extension_chain import (
    is_video_extension_strategy,
    normalize_video_extension_count,
    run_last_frame_video_extension_chain,
)
from ..common.video_prompt_enhancement import (
    apply_video_prompt_enhancement_metadata,
    enhance_video_prompt_bundle,
)

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
        logger.info(
            "[Grok VideoGenerator] Initialized with base_url=%s",
            summarize_url_for_log(self.base_url),
        )

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

    def _resolve_bool(self, kwargs: Dict[str, Any], *keys: str, default: bool = False) -> bool:
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

    async def _maybe_enhance_prompt(self, prompt: str, kwargs: Dict[str, Any]) -> Optional[str]:
        if not self._resolve_bool(kwargs, "enhance_prompt", "enhancePrompt", default=False):
            return None

        model = str(
            kwargs.get("enhance_prompt_model")
            or kwargs.get("enhancePromptModel")
            or kwargs.get("prompt_optimize_model")
            or kwargs.get("promptOptimizeModel")
            or "grok-4"
        ).strip() or "grok-4"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional video prompt enhancer. Rewrite the user's input "
                        "as one direct, visually actionable video prompt. Preserve intent, language, "
                        "subject identity, constraints, and negative instructions. Add useful motion, "
                        "camera movement, lighting, pacing, and scene continuity. Return only the prompt."
                    ),
                },
                {"role": "user", "content": f"Original prompt:\n{str(prompt or '').strip()}"},
            ],
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 120.0)) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("[Grok VideoGenerator] Prompt enhancement failed; using original prompt: %s", exc)
            return None

        enhanced = self._extract_chat_completion_text(data)
        original = str(prompt or "").strip()
        if enhanced and enhanced != original:
            return enhanced
        return None

    def _extract_chat_completion_text(self, data: Dict[str, Any]) -> Optional[str]:
        choices = data.get("choices")
        if not isinstance(choices, list):
            return None
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None

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
            logger.info(
                "[Grok VideoGenerator] Video generation: model=%s, prompt=%s",
                model,
                summarize_text_for_log(prompt, label="prompt"),
            )

            size = self._resolve_size(kwargs)
            seconds = self._resolve_seconds(kwargs)
            quality = self._resolve_quality(kwargs)
            extension_count = normalize_video_extension_count(kwargs)
            enhancement = await enhance_video_prompt_bundle(
                prompt=prompt,
                request_kwargs=dict(kwargs),
                extension_count=extension_count,
                enhance_requested=self._resolve_bool(kwargs, "enhance_prompt", "enhancePrompt", default=False),
                enhance_prompt=lambda value: self._maybe_enhance_prompt(value, kwargs),
            )
            effective_prompt = enhancement.effective_prompt
            request_kwargs = enhancement.request_kwargs
            extension_count = normalize_video_extension_count(request_kwargs)
            if extension_count > 0:
                async def generate_segment(segment_prompt: str, segment_model: str, segment_kwargs: Dict[str, Any]) -> Dict[str, Any]:
                    return await self._generate_video_once(
                        prompt=segment_prompt,
                        model=segment_model,
                        size=size,
                        seconds=seconds,
                        quality=quality,
                        kwargs=segment_kwargs,
                    )

                result = await run_last_frame_video_extension_chain(
                    provider_name="grok",
                    prompt=effective_prompt,
                    model=model,
                    request_kwargs=request_kwargs,
                    extension_count=extension_count,
                    generate_segment=generate_segment,
                    continuation_model=model,
                    segment_seconds=seconds,
                    treat_source_video_as_existing_base=is_video_extension_strategy(
                        request_kwargs.get("video_input_strategy") or request_kwargs.get("videoInputStrategy")
                    ),
                )
                return apply_video_prompt_enhancement_metadata(result, enhancement)

            result = await self._generate_video_once(
                prompt=effective_prompt,
                model=model,
                size=size,
                seconds=seconds,
                quality=quality,
                kwargs=request_kwargs,
            )
            apply_video_prompt_enhancement_metadata(result, enhancement)
            logger.info(
                "[Grok VideoGenerator] Video generated: url=%s",
                summarize_url_for_log(result.get("url", "")),
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                "[Grok VideoGenerator] HTTP error: status=%s body=%s",
                e.response.status_code,
                summarize_text_for_log(e.response.text, label="provider_error"),
            )
            raise
        except Exception as e:
            logger.error(
                "[Grok VideoGenerator] Video generation error: %s",
                summarize_text_for_log(e, label="error"),
            )
            raise

    async def _generate_video_once(
        self,
        *,
        prompt: str,
        model: str,
        size: str,
        seconds: int,
        quality: str,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        request_body: Dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "size": size,
            "seconds": seconds,
            "quality": quality,
        }

        ref_url = self._extract_image_reference_url(kwargs)
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

        video_url = data.get("url", "")
        if not video_url:
            raise RuntimeError("Grok video response did not contain a video URL.")

        return {
            "url": video_url,
            "mime_type": "video/mp4",
            "filename": f"{data.get('id', 'grok_video')}.mp4",
            "duration": seconds,
            "duration_seconds": seconds,
            "model": model,
            "video_size": size,
            "status": data.get("status", "completed"),
        }

    def _extract_image_reference_url(self, kwargs: Dict[str, Any]) -> str:
        source_image = kwargs.get("source_image") or kwargs.get("sourceImage")
        if isinstance(source_image, str):
            return source_image
        if isinstance(source_image, dict):
            value = source_image.get("url") or source_image.get("temp_url") or source_image.get("tempUrl")
            if value:
                return str(value)

        ref_images = kwargs.get("reference_images")
        if not ref_images:
            return ""
        raw_refs = ref_images.get("raw", []) if isinstance(ref_images, dict) else ref_images
        if not isinstance(raw_refs, list):
            raw_refs = [raw_refs]
        if not raw_refs:
            return ""
        first_ref = raw_refs[0]
        if isinstance(first_ref, dict):
            return str(first_ref.get("url") or first_ref.get("temp_url") or first_ref.get("tempUrl") or "")
        if isinstance(first_ref, str):
            return first_ref
        return ""
