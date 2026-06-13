"""
OpenAI 图片生成器

处理 OpenAI 的图片生成操作（GPT Image）。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ...utils.log_sanitization import summarize_text_for_log, summarize_url_for_log
from ._shared import (
    build_async_client,
    call_image_api_with_fanout,
    coerce_openai_image_max_retries,
    coerce_openai_image_timeout,
    elapsed_ms,
    enhance_openai_image_prompt,
    image_response_to_results,
    normalize_image_api_kwargs,
    with_openai_image_client_options,
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
        self.image_timeout = coerce_openai_image_timeout(kwargs.get("image_timeout"))
        self.image_max_retries = coerce_openai_image_max_retries(kwargs.get("image_max_retries"))
        self.client = build_async_client(
            api_key=api_key,
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3),
            client=kwargs.get("client"),
        )
        
        logger.info(
            "[OpenAI ImageGenerator] Initialized with base_url=%s",
            summarize_url_for_log(self.base_url),
        )
    
    async def generate_image(
        self,
        prompt: str,
        model: str = "gpt-image-2",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        使用 OpenAI GPT Image 生成图片
        
        Args:
            prompt: 图片描述文本
            model: 使用的模型，默认使用 gpt-image-2
            **kwargs: 额外参数:
                - size (str): 图片尺寸 ('1024x1024', '1536x1024', '1024x1536', 'auto')
                - quality (str): 图片质量 ('auto', 'low', 'medium', 'high')
                - background (str): 背景 ('auto', 'opaque', 'transparent')
                - output_format (str): 输出格式 ('png', 'jpeg', 'webp')
                - n (int): 生成图片数量 (1-10)
        
        Returns:
            图片结果列表（统一格式，即使只有一张图片也返回列表）
        """
        operation_start = time.perf_counter()
        try:
            logger.info(
                "[OpenAI ImageGenerator] Image generation: model=%s, prompt=%s",
                model,
                summarize_text_for_log(prompt, label="prompt"),
            )
            enhanced_prompt = None
            effective_prompt = prompt
            if kwargs.get("enhance_prompt") or kwargs.get("enhancePrompt"):
                enhance_start = time.perf_counter()
                enhanced_prompt = await enhance_openai_image_prompt(
                    self.client,
                    prompt,
                    model_hint=kwargs.get("enhance_prompt_model") or kwargs.get("enhancePromptModel"),
                    thinking_level=(
                        kwargs.get("enhance_prompt_thinking_level")
                        or kwargs.get("enhancePromptThinkingLevel")
                    ),
                    )
                if enhanced_prompt:
                    effective_prompt = enhanced_prompt
                logger.info(
                    "[OpenAI ImageGenerator] Prompt enhancement phase completed "
                    "(elapsed_ms=%.2f, requested=true, enhanced=%s, enhanced_len=%s)",
                    elapsed_ms(enhance_start),
                    bool(enhanced_prompt),
                    len(enhanced_prompt or ""),
                )

            request_kwargs = self._normalize_generate_kwargs(model, kwargs)
            requested_count = self._requested_image_count(request_kwargs)
            self._log_generation_request_options(
                model=model,
                request_kwargs=request_kwargs,
                prompt=effective_prompt,
                enhanced_prompt_used=bool(enhanced_prompt),
            )

            api_start = time.perf_counter()
            response = await self._call_generate_image_api(
                prompt=effective_prompt,
                model=model,
                request_kwargs=request_kwargs,
            )
            logger.info(
                "[OpenAI ImageGenerator] Images Generate API completed "
                "(elapsed_ms=%.2f, model=%s, n=%s, size=%s, quality=%s, output_format=%s)",
                elapsed_ms(api_start),
                model,
                request_kwargs.get("n", 1),
                request_kwargs.get("size"),
                request_kwargs.get("quality"),
                request_kwargs.get("output_format"),
            )

            parse_start = time.perf_counter()
            results = self._response_to_results(response, request_kwargs)
            logger.info(
                "[OpenAI ImageGenerator] Response conversion completed (elapsed_ms=%.2f, images=%s)",
                elapsed_ms(parse_start),
                len(results),
            )

            if not results:
                # 无任何可用图片(全部腿失败或响应无图像负载)才算硬失败。
                raise RuntimeError("OpenAI image response did not contain a usable image payload.")

            if len(results) < requested_count:
                # 部分成功: 扇出为 n=1 的并发腿后, 个别腿可能因上游 502/429 失败。
                # 不丢弃已完成且已计费的图片——返回部分结果并记录警告。
                logger.warning(
                    "[OpenAI ImageGenerator] Partial image result: %s/%s images returned "
                    "(model=%s). Some fan-out legs failed upstream; surfacing completed images.",
                    len(results),
                    requested_count,
                    model,
                )

            if enhanced_prompt:
                for result in results:
                    result["enhanced_prompt"] = enhanced_prompt
            
            logger.info(
                "[OpenAI ImageGenerator] Image generated: %s image(s) (total_elapsed_ms=%.2f)",
                len(results),
                elapsed_ms(operation_start),
            )
            
            return results
        
        except Exception as e:
            logger.error(
                "[OpenAI ImageGenerator] Image generation error: %s",
                summarize_text_for_log(e, label="error"),
            )
            raise

    async def _call_generate_image_api(
        self,
        *,
        prompt: str,
        model: str,
        request_kwargs: Dict[str, Any],
    ) -> Any:
        image_client = self._image_request_client()
        count = self._requested_image_count(request_kwargs)

        async def _single(n: int) -> Any:
            # 扇出时每次只请求 1 张; 透传其余参数(size/quality/output_format 等)。
            single_kwargs = {**request_kwargs, "n": n}
            return await image_client.images.generate(
                model=model,
                prompt=prompt,
                **single_kwargs,
            )

        # 详见 call_image_api_with_fanout: 订阅/OAuth 网关不支持原生 n>1, 故扇出为并发 n=1。
        return await call_image_api_with_fanout(_single, count)

    def _response_to_results(self, response: Any, request_kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        return image_response_to_results(response, request_kwargs)

    def _requested_image_count(self, request_kwargs: Dict[str, Any]) -> int:
        try:
            return max(1, int(request_kwargs.get("n") or 1))
        except (TypeError, ValueError):
            return 1

    def _normalize_generate_kwargs(self, model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_image_api_kwargs(model, kwargs)

    def _image_request_client(self):
        return with_openai_image_client_options(
            self.client,
            timeout=self.image_timeout,
            max_retries=self.image_max_retries,
        )

    def _log_generation_request_options(
        self,
        *,
        model: str,
        request_kwargs: Dict[str, Any],
        prompt: str,
        enhanced_prompt_used: bool,
    ) -> None:
        logger.info(
            "[OpenAI ImageGenerator] Request options: model=%s size=%s n=%s quality=%s "
            "output_format=%s base_url=%s image_timeout=%ss image_max_retries=%s "
            "prompt_len=%s enhanced_prompt_used=%s",
            model,
            request_kwargs.get("size"),
            request_kwargs.get("n", 1),
            request_kwargs.get("quality"),
            request_kwargs.get("output_format"),
            summarize_url_for_log(self.base_url),
            self.image_timeout,
            self.image_max_retries,
            len(prompt or ""),
            enhanced_prompt_used,
        )
