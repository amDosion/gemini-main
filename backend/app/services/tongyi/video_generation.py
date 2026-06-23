"""
Tongyi DashScope video generation service.

Supports Wan 2.7 / HappyHorse style video-synthesis models:
- text-to-video: *-t2v
- image-to-video: *-i2v
- reference-to-video: *-r2v
- video edit: *-videoedit / *-video-edit
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Iterable, List, Optional

import httpx

from ..common.video_extension_chain import (
    is_video_extension_strategy,
    load_video_bytes_from_source,
    normalize_video_extension_count,
    run_last_frame_video_extension_chain,
)
from ..common.video_prompt_enhancement import (
    apply_video_prompt_enhancement_metadata,
    enhance_video_prompt_bundle,
)
from ..gemini.base.video_common import to_data_url
from .base import DASHSCOPE_BASE_URL
from .prompt_optimizer.video_optimizer import VideoPromptOptimizer

logger = logging.getLogger(__name__)

VIDEO_SYNTHESIS_ENDPOINT = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/video-generation/video-synthesis"
TASK_ENDPOINT = f"{DASHSCOPE_BASE_URL}/api/v1/tasks"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}


def is_tongyi_video_model(model_id: str) -> bool:
    model = str(model_id or "").strip().lower()
    return (
        "happyhorse" in model
        or model.startswith("wan2.7-t2v")
        or model.startswith("wan2.7-i2v")
        or model.startswith("wan2.7-r2v")
        or model.startswith("wan2.7-videoedit")
        or model.startswith("wan2.7-video-edit")
    )


class TongyiVideoGenerationService:
    """DashScope async task wrapper for video synthesis models."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 120.0,
        poll_interval: float = 15.0,
        poll_timeout: float = 900.0,
        user_id: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.user_id = user_id

    async def generate_video(self, prompt: str, model: str, **kwargs: Any) -> Dict[str, Any]:
        if not is_tongyi_video_model(model):
            raise ValueError(f"Unsupported Tongyi video model: {model}")

        extension_count = normalize_video_extension_count(kwargs)
        enhancement = await enhance_video_prompt_bundle(
            prompt=prompt,
            request_kwargs=dict(kwargs),
            extension_count=extension_count,
            enhance_requested=self._is_prompt_enhancement_requested(kwargs),
            enhance_prompt=lambda value: self._maybe_enhance_prompt(value, kwargs),
        )
        effective_prompt = enhancement.effective_prompt
        request_kwargs = enhancement.request_kwargs
        extension_count = normalize_video_extension_count(request_kwargs)
        if extension_count > 0:
            continuation_model = self._resolve_continuation_model(model)
            segment_seconds = self._resolve_duration(continuation_model.lower(), request_kwargs) or 5

            async def generate_segment(segment_prompt: str, segment_model: str, segment_kwargs: Dict[str, Any]) -> Dict[str, Any]:
                return await self._generate_video_once(
                    prompt=segment_prompt,
                    model=segment_model,
                    kwargs=segment_kwargs,
                    enhanced_prompt=None,
                )

            result = await run_last_frame_video_extension_chain(
                provider_name="tongyi",
                prompt=effective_prompt,
                model=model,
                request_kwargs=request_kwargs,
                extension_count=extension_count,
                generate_segment=generate_segment,
                continuation_model=continuation_model,
                segment_seconds=segment_seconds,
                continuation_trim_seconds=0.0,
                treat_source_video_as_existing_base=is_video_extension_strategy(
                    request_kwargs.get("video_input_strategy") or request_kwargs.get("videoInputStrategy")
                ),
                user_id=self.user_id,
            )
            return apply_video_prompt_enhancement_metadata(result, enhancement)

        return await self._generate_video_once(
            prompt=effective_prompt,
            model=model,
            kwargs=request_kwargs,
            enhanced_prompt=enhancement.enhanced_prompt,
        )

    async def _generate_video_once(
        self,
        *,
        prompt: str,
        model: str,
        kwargs: Dict[str, Any],
        enhanced_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_kwargs = await self._prepare_dashscope_frame_media(dict(kwargs), model)
        payload = self._build_payload(prompt=prompt, model=model, kwargs=normalized_kwargs)
        if enhanced_prompt:
            payload.setdefault("parameters", {})["prompt_extend"] = False
        logger.info("[TongyiVideo] Creating video synthesis task: model=%s", model)
        task_response = await self._post_task(payload)
        task_id = self._extract_task_id(task_response)
        logger.info("[TongyiVideo] Created task_id=%s", task_id)

        result = await self._poll_task(task_id)
        output = result.get("output") if isinstance(result.get("output"), dict) else {}
        status = str(output.get("task_status") or "").upper()
        if status != "SUCCEEDED":
            message = output.get("message") or output.get("code") or f"task status={status or 'UNKNOWN'}"
            raise RuntimeError(f"Tongyi video task failed: {message}")

        video_url = self._extract_video_url(result)
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        duration = usage.get("output_video_duration") or usage.get("duration") or kwargs.get("seconds")
        result_payload = {
            "url": video_url,
            "mime_type": "video/mp4",
            "filename": f"{task_id}.mp4",
            "duration": duration,
            "duration_seconds": duration,
            "job_id": task_id,
            "task_id": task_id,
            "model": model,
            "status": "completed",
            "video_size": self._resolve_resolution(normalized_kwargs),
        }
        if enhanced_prompt:
            result_payload["enhanced_prompt"] = enhanced_prompt
            result_payload["prompt_enhancement_strategy"] = "local_llm"
        return result_payload

    def _resolve_continuation_model(self, model: str) -> str:
        normalized = str(model or "").strip()
        lower = normalized.lower()
        if "-i2v" in lower:
            return normalized
        if "-t2v" in lower:
            return normalized.replace("-t2v", "-i2v")
        if "-r2v" in lower:
            return normalized.replace("-r2v", "-i2v")
        if "-video-edit" in lower:
            return normalized.replace("-video-edit", "-i2v")
        if lower.endswith("videoedit"):
            return f"{normalized[:-len('videoedit')]}i2v"
        return normalized

    async def _prepare_dashscope_frame_media(self, kwargs: Dict[str, Any], model: str) -> Dict[str, Any]:
        for key in ("source_image", "sourceImage", "last_frame_image", "lastFrameImage"):
            value = kwargs.get(key)
            if value:
                kwargs[key] = await self._ensure_dashscope_video_media(value, fallback_mime_type="image/png")

        reference_images = kwargs.get("reference_images")
        if isinstance(reference_images, dict) and reference_images.get("raw") is not None:
            raw = reference_images.get("raw")
            raw_items = raw if isinstance(raw, list) else [raw]
            reference_images = dict(reference_images)
            reference_images["raw"] = [
                await self._ensure_dashscope_video_media(item, fallback_mime_type="image/png")
                for item in raw_items
                if item
            ]
            kwargs["reference_images"] = reference_images
        return kwargs

    async def _ensure_dashscope_video_media(
        self,
        media: Any,
        *,
        fallback_mime_type: str,
    ) -> Any:
        url = self._media_url(media)
        if not url:
            return media
        if url.startswith(("http://", "https://", "data:", "oss://")):
            return media

        content, mime_type = await load_video_bytes_from_source(
            media,
            fallback_mime_type=fallback_mime_type,
            user_id=self.user_id,
        )
        data_url = to_data_url(content, mime_type)

        if isinstance(media, dict):
            updated = dict(media)
            updated["url"] = data_url
            updated["mime_type"] = mime_type
            return updated
        return {"url": data_url, "mime_type": mime_type}

    async def _maybe_enhance_prompt(self, prompt: str, kwargs: Dict[str, Any]) -> Optional[str]:
        if not self._is_prompt_enhancement_requested(kwargs):
            return None

        model_hint = (
            kwargs.get("enhance_prompt_model")
            or kwargs.get("enhancePromptModel")
            or kwargs.get("prompt_optimize_model")
            or kwargs.get("promptOptimizeModel")
        )
        optimizer = VideoPromptOptimizer(self.api_key)
        try:
            result = await optimizer.optimize(
                prompt,
                model=str(model_hint).strip() if model_hint else None,
            )
        finally:
            await optimizer.close()

        enhanced = str(getattr(result, "optimized_prompt", "") or "").strip()
        original = str(prompt or "").strip()
        if getattr(result, "success", False) and enhanced and enhanced != original:
            return enhanced
        return None

    def _is_prompt_enhancement_requested(self, kwargs: Dict[str, Any]) -> bool:
        return self._resolve_bool(
            kwargs,
            "enhance_prompt",
            "enhancePrompt",
            "enable_prompt_optimize",
            "enablePromptOptimize",
            default=False,
        )

    def _build_payload(self, *, prompt: str, model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        model_lower = model.lower()
        input_payload: Dict[str, Any] = {"prompt": prompt}
        negative_prompt = kwargs.get("negative_prompt") or kwargs.get("negativePrompt")
        if negative_prompt:
            input_payload["negative_prompt"] = negative_prompt
        audio_url = kwargs.get("audio_url") or kwargs.get("audioUrl")
        if audio_url:
            input_payload["audio_url"] = audio_url

        media = self._build_media(model_lower, kwargs)
        if media:
            input_payload["media"] = media

        parameters: Dict[str, Any] = {
            "resolution": self._resolve_resolution(kwargs),
            "prompt_extend": self._resolve_bool(
                kwargs,
                "prompt_extend",
                "promptExtend",
                "enhance_prompt",
                "enhancePrompt",
                default=True,
            ),
            "watermark": self._resolve_bool(kwargs, "watermark", default=False),
        }
        duration = self._resolve_duration(model_lower, kwargs)
        if duration is not None:
            parameters["duration"] = duration
        ratio = kwargs.get("ratio") or kwargs.get("aspect_ratio") or kwargs.get("image_aspect_ratio")
        if ratio and str(ratio).lower() not in {"source", "auto", "input", "original"} and not self._is_image_to_video(model_lower):
            parameters["ratio"] = str(ratio)
        seed = kwargs.get("seed")
        if seed is not None:
            seed_value = int(seed)
            if seed_value >= 0:
                parameters["seed"] = seed_value

        return {
            "model": model,
            "input": input_payload,
            "parameters": parameters,
        }

    def _build_media(self, model_lower: str, kwargs: Dict[str, Any]) -> List[Dict[str, str]]:
        if self._is_text_to_video(model_lower):
            return []
        if self._is_image_to_video(model_lower):
            source_video = self._media_url(kwargs.get("source_video"))
            audio_url = self._media_url(kwargs.get("audio_url") or kwargs.get("audioUrl"))
            if source_video:
                media = [{"type": "first_clip", "url": source_video}]
                last_frame = self._media_url(kwargs.get("last_frame_image"))
                if last_frame:
                    media.append({"type": "last_frame", "url": last_frame})
                if audio_url:
                    media.append({"type": "driving_audio", "url": audio_url})
                return media

            source_image = self._media_url(kwargs.get("source_image"))
            if not source_image:
                source_image = self._first_reference_image_url(kwargs)
            if not source_image:
                raise ValueError("Tongyi image-to-video requires a source image or source video attachment.")
            media = [{"type": "first_frame", "url": source_image}]
            last_frame = self._media_url(kwargs.get("last_frame_image"))
            if last_frame:
                media.append({"type": "last_frame", "url": last_frame})
            if audio_url:
                media.append({"type": "driving_audio", "url": audio_url})
            return media
        if self._is_video_edit(model_lower):
            source_video = self._media_url(kwargs.get("source_video"))
            if not source_video:
                raise ValueError("Tongyi video edit requires a source video attachment.")
            media = [{"type": "video", "url": source_video}]
            for url in self._reference_image_urls(kwargs):
                media.append({"type": "reference_image", "url": url})
            return media

        media: List[Dict[str, str]] = []
        source_video = self._media_url(kwargs.get("source_video"))
        if source_video:
            media.append({"type": "reference_video", "url": source_video})
        source_image = self._media_url(kwargs.get("source_image"))
        if source_image:
            media.append({"type": "reference_image", "url": source_image})
        for url in self._reference_image_urls(kwargs):
            media.append({"type": "reference_image", "url": url})
        if not media:
            raise ValueError("Tongyi reference-to-video requires at least one reference image or video attachment.")
        return media[:10]

    async def _post_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(VIDEO_SYNTHESIS_ENDPOINT, json=payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Tongyi video task creation failed: HTTP {response.status_code} {response.text[:500]}"
                ) from exc
            return response.json()

    async def _poll_task(self, task_id: str) -> Dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout
        while True:
            result = await self._get_task(task_id)
            output = result.get("output") if isinstance(result.get("output"), dict) else {}
            status = str(output.get("task_status") or "").upper()
            if status in TERMINAL_STATUSES:
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Tongyi video task timed out: {task_id}")
            await asyncio.sleep(self.poll_interval)

    async def _get_task(self, task_id: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{TASK_ENDPOINT}/{task_id}", headers=headers)
            response.raise_for_status()
            return response.json()

    def _extract_task_id(self, response: Dict[str, Any]) -> str:
        output = response.get("output") if isinstance(response.get("output"), dict) else {}
        task_id = str(output.get("task_id") or "").strip()
        if not task_id:
            raise RuntimeError(f"Tongyi video task response did not include task_id: {response}")
        return task_id

    def _extract_video_url(self, response: Dict[str, Any]) -> str:
        output = response.get("output") if isinstance(response.get("output"), dict) else {}
        candidates = [
            output.get("video_url"),
            output.get("url"),
            output.get("output_video_url"),
        ]
        results = output.get("results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    candidates.extend([item.get("video_url"), item.get("url")])
        for candidate in candidates:
            if candidate:
                return str(candidate)
        raise RuntimeError(f"Tongyi video task succeeded but no video URL was returned: {response}")

    def _reference_image_urls(self, kwargs: Dict[str, Any]) -> List[str]:
        reference_images = kwargs.get("reference_images")
        if not isinstance(reference_images, dict):
            return []
        raw = reference_images.get("raw") or []
        if not isinstance(raw, list):
            raw = [raw]
        return [url for url in (self._media_url(item) for item in raw) if url]

    def _first_reference_image_url(self, kwargs: Dict[str, Any]) -> Optional[str]:
        urls = self._reference_image_urls(kwargs)
        return urls[0] if urls else None

    def _media_url(self, media: Any) -> Optional[str]:
        if not media:
            return None
        if isinstance(media, str):
            return media
        if isinstance(media, dict):
            for key in ("url", "temp_url", "tempUrl", "oss_url", "ossUrl", "provider_file_uri", "providerFileUri"):
                value = media.get(key)
                if value:
                    return str(value)
        return None

    def _resolve_resolution(self, kwargs: Dict[str, Any]) -> str:
        value = str(
            kwargs.get("resolution")
            or kwargs.get("image_resolution")
            or kwargs.get("imageResolution")
            or "1080P"
        ).strip()
        upper = value.upper()
        aliases = {
            "1K": "720P",
            "720": "720P",
            "720P": "720P",
            "2K": "1080P",
            "1080": "1080P",
            "1080P": "1080P",
        }
        return aliases.get(upper, "1080P")

    def _resolve_duration(self, model_lower: str, kwargs: Dict[str, Any]) -> Optional[int]:
        raw = kwargs.get("duration") or kwargs.get("duration_seconds") or kwargs.get("seconds")
        if raw is None:
            if self._is_video_edit(model_lower):
                return None
            raw = 5

        duration = int(str(raw))
        if duration <= 0:
            return None if self._is_video_edit(model_lower) else self._min_duration(model_lower)

        return max(self._min_duration(model_lower), min(duration, self._max_duration(model_lower, kwargs)))

    def _resolve_bool(self, kwargs: Dict[str, Any], *keys: str, default: bool) -> bool:
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

    def _is_text_to_video(self, model: str) -> bool:
        return model.endswith("-t2v") or "-t2v" in model

    def _is_image_to_video(self, model: str) -> bool:
        return model.endswith("-i2v") or "-i2v" in model

    def _is_video_edit(self, model: str) -> bool:
        return "videoedit" in model or "video-edit" in model

    def _is_reference_to_video(self, model: str) -> bool:
        return model.endswith("-r2v") or "-r2v" in model

    def _min_duration(self, model: str) -> int:
        return 3 if "happyhorse" in model else 2

    def _max_duration(self, model: str, kwargs: Dict[str, Any]) -> int:
        if "happyhorse" in model:
            return 15
        if self._is_video_edit(model):
            return 10
        if self._is_reference_to_video(model) and self._media_url(kwargs.get("source_video")):
            return 10
        return 15
