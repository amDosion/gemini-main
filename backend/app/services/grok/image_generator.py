"""
Grok 图片生成器

处理 Grok 的图片生成操作（grok-imagine-1.0）。
使用 httpx 直接调用 grok2api 的 /images/generations 端点。
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging

import httpx

logger = logging.getLogger(__name__)

ALLOWED_SIZES = {
    "1024x1024",
    "1280x720",
    "720x1280",
    "1792x1024",
    "1024x1792",
}

# Aspect ratio to size mapping (for frontend compatibility)
ASPECT_RATIO_TO_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "3:2": "1792x1024",
    "2:3": "1024x1792",
}

DEFAULT_MODEL = "grok-imagine-1.0"


class ImageGenerator:
    """
    Grok 图片生成器

    使用 httpx 调用 grok2api 的图片生成接口。
    """

    def __init__(self, api_key: str, base_url: str, timeout: float = 120.0):
        """
        初始化图片生成器

        Args:
            api_key: API key for Bearer auth
            base_url: grok2api base URL (e.g. http://localhost:8000/v1)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.info(f"[Grok ImageGenerator] Initialized with base_url={self.base_url}")

    def _resolve_size(self, kwargs: Dict[str, Any]) -> str:
        """Resolve image size from kwargs (size, aspect_ratio, image_aspect_ratio)."""
        size = kwargs.get("size") or kwargs.get("image_resolution")
        if size and size in ALLOWED_SIZES:
            return size

        aspect_ratio = kwargs.get("aspect_ratio") or kwargs.get("image_aspect_ratio")
        if aspect_ratio and aspect_ratio in ASPECT_RATIO_TO_SIZE:
            return ASPECT_RATIO_TO_SIZE[aspect_ratio]

        return "1024x1024"

    def _resolve_n(self, kwargs: Dict[str, Any]) -> int:
        """Resolve number of images from kwargs."""
        n = kwargs.get("n") or kwargs.get("number_of_images")
        if n is not None:
            try:
                count = int(n)
                return max(1, min(count, 10))
            except (TypeError, ValueError):
                pass
        return 1

    async def generate_image(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        使用 grok-imagine-1.0 生成图片

        Args:
            prompt: 图片描述文本
            model: 模型名称 (grok-imagine-1.0)
            **kwargs: 额外参数:
                - size (str): 图片尺寸
                - n (int): 生成图片数量 (1-10)
                - aspect_ratio (str): 宽高比
                - number_of_images (int): alias for n

        Returns:
            图片结果列表（统一格式）
        """
        try:
            logger.info(f"[Grok ImageGenerator] Image generation: model={model}, prompt={prompt[:50]}...")

            size = self._resolve_size(kwargs)
            n = self._resolve_n(kwargs)

            request_body = {
                "prompt": prompt,
                "model": model,
                "n": n,
                "size": size,
                "response_format": "url",
            }

            url = f"{self.base_url}/images/generations"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()

            # Parse response: {"created": ..., "data": [{"url": "..."} or {"b64_json": "..."}]}
            results = []
            for item in data.get("data", []):
                image_url = item.get("url")
                if not image_url:
                    b64 = item.get("b64_json")
                    if b64:
                        image_url = f"data:image/png;base64,{b64}"

                if not image_url:
                    continue

                results.append({
                    "url": image_url,
                    "mime_type": "image/png",
                    "revised_prompt": item.get("revised_prompt", ""),
                })

            if not results:
                raise RuntimeError("Grok image response did not contain a usable image payload.")

            logger.info(f"[Grok ImageGenerator] Image generated: {len(results)} image(s)")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"[Grok ImageGenerator] HTTP error: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[Grok ImageGenerator] Image generation error: {e}", exc_info=True)
            raise
