"""
OpenAI 图片生成器

处理 OpenAI 的图片生成操作（DALL-E）。
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging

from ._shared import (
    IMAGE_ALLOWED_OPTION_KEYS,
    build_async_client,
    filter_allowed_kwargs,
    image_output_format_to_mime_type,
    map_image_aspect_ratio_to_size,
)

logger = logging.getLogger(__name__)


class ImageGenerator:
    """
    OpenAI 图片生成器
    
    负责处理所有图片生成相关的操作。
    """
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        """
        初始化图片生成器
        
        Args:
            api_key: OpenAI API key
            base_url: Optional custom API URL
            **kwargs: Additional parameters (timeout, max_retries, etc.)
        """
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.client = build_async_client(
            api_key=api_key,
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3),
            client=kwargs.get("client"),
        )
        
        logger.info(f"[OpenAI ImageGenerator] Initialized with base_url={self.base_url}")
    
    async def generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        使用 DALL-E 生成图片
        
        Args:
            prompt: 图片描述文本
            model: 使用的模型 ('dall-e-2' 或 'dall-e-3')
            **kwargs: 额外参数:
                - size (str): 图片尺寸 ('1024x1024', '1792x1024', '1024x1792')
                - quality (str): 图片质量 ('standard' 或 'hd')
                - style (str): 图片风格 ('vivid' 或 'natural')
                - n (int): 生成图片数量 (1-10)
        
        Returns:
            图片结果列表（统一格式，即使只有一张图片也返回列表）
        """
        try:
            logger.info(f"[OpenAI ImageGenerator] Image generation: model={model}, prompt={prompt[:50]}...")
            request_kwargs = self._normalize_generate_kwargs(model, kwargs)

            # Call DALL-E API
            response = await self.client.images.generate(
                model=model,
                prompt=prompt,
                **request_kwargs
            )
            
            # 转换为统一格式（列表）
            results = []
            for item in response.data:
                image_url = self._extract_image_url(item, request_kwargs)
                if not image_url:
                    continue
                results.append({
                    "url": image_url,
                    "revised_prompt": self._read_field(item, "revised_prompt"),
                    "mime_type": self._infer_result_mime_type(item, request_kwargs),
                })

            if not results:
                raise RuntimeError("OpenAI image response did not contain a usable image payload.")
            
            logger.info(f"[OpenAI ImageGenerator] Image generated: {len(results)} image(s)")
            
            return results
        
        except Exception as e:
            logger.error(f"[OpenAI ImageGenerator] Image generation error: {e}", exc_info=True)
            raise

    def _normalize_generate_kwargs(self, model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        normalized = filter_allowed_kwargs(
            kwargs,
            allowed_keys=IMAGE_ALLOWED_OPTION_KEYS,
            aliases={"number_of_images": "n"},
        )

        size = normalized.get("size")
        if not size:
            size = kwargs.get("image_resolution")
        if not size:
            size = map_image_aspect_ratio_to_size(
                model,
                kwargs.get("image_aspect_ratio") or kwargs.get("aspect_ratio"),
            )
        if size:
            normalized["size"] = str(size).strip()

        if "n" in normalized:
            try:
                count = int(normalized["n"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Unsupported OpenAI image count: {normalized['n']}") from exc
            if str(model or "").strip().lower().startswith("dall-e-3"):
                count = 1
            else:
                count = max(1, min(count, 10))
            normalized["n"] = count
        elif str(model or "").strip().lower().startswith("dall-e-3"):
            normalized["n"] = 1

        response_format = str(normalized.get("response_format") or "").strip().lower()
        if response_format and response_format not in {"url", "b64_json"}:
            normalized.pop("response_format", None)

        output_format = str(normalized.get("output_format") or "").strip().lower()
        if output_format and output_format not in {"png", "jpeg", "webp"}:
            normalized.pop("output_format", None)

        if str(model or "").strip().lower().startswith("dall-e-2"):
            normalized.pop("quality", None)
            normalized.pop("style", None)

        return normalized

    def _extract_image_url(self, item: Any, request_kwargs: Dict[str, Any]) -> Optional[str]:
        direct_url = self._read_field(item, "url")
        if isinstance(direct_url, str) and direct_url:
            return direct_url

        b64_json = self._read_field(item, "b64_json")
        if isinstance(b64_json, str) and b64_json:
            mime_type = self._infer_result_mime_type(item, request_kwargs)
            return f"data:{mime_type};base64,{b64_json}"

        return None

    def _infer_result_mime_type(self, item: Any, request_kwargs: Dict[str, Any]) -> str:
        explicit_mime = self._read_field(item, "mime_type", "mimeType")
        if isinstance(explicit_mime, str) and explicit_mime:
            return explicit_mime
        return image_output_format_to_mime_type(request_kwargs.get("output_format"))

    def _read_field(self, item: Any, *field_names: str) -> Any:
        if isinstance(item, dict):
            for field_name in field_names:
                if field_name in item:
                    return item[field_name]
            return None

        for field_name in field_names:
            value = getattr(item, field_name, None)
            if value is not None:
                return value
        return None
