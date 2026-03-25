"""
Grok 图片编辑器

处理 Grok 的图片编辑操作（grok-imagine-1.0-edit）。
使用 httpx 发送 multipart form data 调用 grok2api 的 /images/edits 端点。
"""
from __future__ import annotations
import base64
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "grok-imagine-1.0-edit"

ALLOWED_SIZES = {
    "1024x1024",
    "1280x720",
    "720x1280",
    "1792x1024",
    "1024x1792",
}

ASPECT_RATIO_TO_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "3:2": "1792x1024",
    "2:3": "1024x1792",
}


class ImageEditor:
    """
    Grok 图片编辑器

    使用 httpx 调用 grok2api 的图片编辑接口（multipart form data）。
    """

    def __init__(self, api_key: str, base_url: str, timeout: float = 120.0):
        """
        初始化图片编辑器

        Args:
            api_key: API key for Bearer auth
            base_url: grok2api base URL (e.g. http://localhost:8000/v1)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.info(f"[Grok ImageEditor] Initialized with base_url={self.base_url}")

    def _resolve_size(self, kwargs: Dict[str, Any]) -> str:
        """Resolve image size from kwargs."""
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

    async def _load_image_bytes(self, source: Any) -> bytes:
        """Load image bytes from URL or data URI."""
        if isinstance(source, str):
            source = source.strip()
            if source.startswith("data:"):
                # data:image/png;base64,...
                _, encoded = source.split(",", 1)
                return base64.b64decode(encoded)
            if source.startswith(("http://", "https://")):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(source)
                    response.raise_for_status()
                    return response.content
        if isinstance(source, bytes):
            return source
        raise ValueError(f"Unsupported image source type: {type(source)}")

    def _extract_reference_images(self, kwargs: Dict[str, Any]) -> List[Any]:
        """Extract reference images from kwargs."""
        ref_images = kwargs.get("reference_images")
        if not ref_images:
            return []
        if isinstance(ref_images, dict):
            raw = ref_images.get("raw", [])
            if isinstance(raw, list):
                return raw
            return [raw] if raw else []
        if isinstance(ref_images, list):
            return ref_images
        return [ref_images]

    async def edit_image(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        使用 grok-imagine-1.0-edit 编辑图片

        Args:
            prompt: 编辑描述文本
            model: 模型名称 (grok-imagine-1.0-edit)
            **kwargs: 额外参数:
                - reference_images: 参考图片列表 (URLs, data URIs, or bytes)
                - size (str): 输出图片尺寸
                - n (int): 生成图片数量 (1-10)

        Returns:
            图片结果列表（统一格式）
        """
        try:
            logger.info(f"[Grok ImageEditor] Image edit: model={model}, prompt={prompt[:50]}...")

            size = self._resolve_size(kwargs)
            n = self._resolve_n(kwargs)
            raw_references = self._extract_reference_images(kwargs)

            url = f"{self.base_url}/images/edits"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            # Build multipart form data
            form_data = {
                "prompt": prompt,
                "model": model,
                "n": str(n),
                "size": size,
                "response_format": "url",
            }

            files = []
            for i, ref in enumerate(raw_references[:16]):
                ref_url = ""
                if isinstance(ref, dict):
                    ref_url = (
                        ref.get("url")
                        or ref.get("temp_url")
                        or ref.get("tempUrl")
                        or ref.get("raw_url")
                        or ref.get("rawUrl")
                        or ""
                    )
                elif isinstance(ref, str):
                    ref_url = ref

                if not ref_url:
                    continue

                try:
                    img_bytes = await self._load_image_bytes(ref_url)
                    files.append(("image", (f"image_{i}.png", img_bytes, "image/png")))
                except Exception as load_err:
                    logger.warning(f"[Grok ImageEditor] Failed to load reference image {i}: {load_err}")
                    continue

            if not files:
                raise ValueError("At least one reference image is required for image editing.")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    data=form_data,
                    files=files,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            # Parse response
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
                raise RuntimeError("Grok image edit response did not contain a usable image payload.")

            logger.info(f"[Grok ImageEditor] Image edited: {len(results)} image(s)")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"[Grok ImageEditor] HTTP error: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[Grok ImageEditor] Image edit error: {e}", exc_info=True)
            raise
