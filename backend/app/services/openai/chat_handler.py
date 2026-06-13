"""
OpenAI 聊天处理器

处理 OpenAI 的聊天相关操作（流式和非流式）。
"""
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai.types.chat import ChatCompletion

from ...utils.log_sanitization import summarize_text_for_log, summarize_url_for_log
from ..common.openai_compatible_multimodal import (
    is_image_attachment,
    normalize_multimodal_content,
    resolve_attachment_url,
)
from ._shared import CHAT_ALLOWED_OPTION_KEYS, build_async_client, filter_allowed_kwargs

logger = logging.getLogger(__name__)


class ChatHandler:
    """
    OpenAI 聊天处理器
    
    负责处理所有聊天相关的操作。
    """
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        """
        初始化聊天处理器
        
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
        
        logger.info(
            "[OpenAI ChatHandler] Initialized with base_url=%s",
            summarize_url_for_log(self.base_url),
        )

    @staticmethod
    def _normalize_usage(usage: Any) -> Dict[str, int]:
        """Normalize usage payload to prompt/completion/total token triple."""
        if not usage:
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
        else:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)

        if prompt_tokens is None:
            prompt_tokens = input_tokens
        if completion_tokens is None:
            completion_tokens = output_tokens

        prompt_tokens = int(prompt_tokens or 0)
        completion_tokens = int(completion_tokens or 0)
        total_tokens = int(total_tokens or (prompt_tokens + completion_tokens))

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    @staticmethod
    def _build_error_done_chunk() -> Dict[str, Any]:
        return {
            "content": "",
            "chunk_type": "done",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "finish_reason": "error",
        }

    @staticmethod
    def _resolve_attachment_url(attachment: Any) -> str:
        return resolve_attachment_url(attachment)

    @staticmethod
    def _is_image_attachment(attachment: Any, url: str) -> bool:
        return is_image_attachment(attachment, url)

    @classmethod
    def _normalize_multimodal_content(
        cls,
        content: Any,
        attachments: List[Any],
    ) -> Any:
        return normalize_multimodal_content(content, attachments)

    @classmethod
    def _prepare_messages(cls, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            next_message = dict(message)
            attachments = next_message.pop("attachments", None)
            if isinstance(attachments, list) and attachments:
                next_message["content"] = cls._normalize_multimodal_content(
                    next_message.get("content", ""),
                    attachments,
                )
            prepared.append(next_message)
        return prepared
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送聊天请求并获取完整响应（非流式）
        
        Args:
            messages: 消息列表
            model: 模型标识符
            **kwargs: 额外参数
            
        Returns:
            聊天响应字典
        """
        try:
            logger.info("[OpenAI ChatHandler] Chat request: model=%s, messages=%s", model, len(messages))

            supported_params = filter_allowed_kwargs(
                kwargs,
                allowed_keys=CHAT_ALLOWED_OPTION_KEYS,
            )
            prepared_messages = self._prepare_messages(messages)

            # Call OpenAI API
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=prepared_messages,
                **supported_params
            )

            usage = self._normalize_usage(response.usage)
            
            # Convert to unified format
            result = {
                "content": response.choices[0].message.content or "",
                "role": "assistant",
                "usage": usage,
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason or "stop"
            }
            
            logger.info(
                "[OpenAI ChatHandler] Chat response: tokens=%s, finish_reason=%s",
                result["usage"]["total_tokens"],
                result["finish_reason"],
            )
            
            return result
        
        except Exception as e:
            logger.error(
                "[OpenAI ChatHandler] Chat error: %s",
                summarize_text_for_log(e, label="error"),
            )
            raise
    
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        发送聊天请求并流式返回响应

        Args:
            messages: 消息列表
            model: 模型标识符
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        try:
            # ✅ 记录 max_tokens 以便调试
            max_tokens = kwargs.get("max_tokens") if "max_tokens" in kwargs else "default"
            logger.info(
                "[OpenAI ChatHandler] Stream chat request: model=%s, messages=%s, max_tokens=%s",
                model,
                len(messages),
                max_tokens,
            )

            supported_params = filter_allowed_kwargs(
                kwargs,
                allowed_keys=CHAT_ALLOWED_OPTION_KEYS,
            )
            prepared_messages = self._prepare_messages(messages)

            # Call OpenAI API with streaming
            stream = await self.client.chat.completions.create(
                model=model,
                messages=prepared_messages,
                stream=True,
                stream_options={"include_usage": True},
                **supported_params
            )

            final_usage = None
            final_finish_reason = None

            # Stream chunks
            async for chunk in stream:
                # Capture usage even when this is a usage-only tail chunk.
                if hasattr(chunk, "usage") and chunk.usage:
                    final_usage = chunk.usage

                # Some providers emit tail usage chunk with empty choices.
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason:
                    final_finish_reason = choice.finish_reason

                # Content chunk
                if delta.content:
                    yield {
                        "content": delta.content,
                        "chunk_type": "content"
                    }

            finish_reason = final_finish_reason or "stop"
            if final_usage:
                usage = self._normalize_usage(final_usage)
                prompt_tokens = usage["prompt_tokens"]
                completion_tokens = usage["completion_tokens"]
                total_tokens = usage["total_tokens"]
            else:
                prompt_tokens = 0
                completion_tokens = 0
                total_tokens = 0
                logger.warning("[OpenAI ChatHandler] Stream finished without usage payload; defaulting usage to zeros")

            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "finish_reason": finish_reason
            }

            logger.info(
                f"[OpenAI ChatHandler] Stream completed: "
                f"tokens={total_tokens}, "
                f"finish_reason={finish_reason}"
            )
        
        except Exception as e:
            # ✅ 改进错误处理：对于 402 错误（积分不足），提供更友好的错误信息
            error_str = str(e)
            if "402" in error_str or "credits" in error_str.lower() or "afford" in error_str.lower():
                # 提取错误详情
                if "but can only afford" in error_str:
                    # 解析可负担的 tokens
                    try:
                        import re
                        match = re.search(r"can only afford (\d+)", error_str)
                        if match:
                            affordable = int(match.group(1))
                            requested_match = re.search(r"requested up to (\d+) tokens", error_str)
                            requested = int(requested_match.group(1)) if requested_match else None
                            
                            logger.error(
                                "[OpenAI ChatHandler] Credit limit exceeded: requested=%s tokens, "
                                "affordable=%s tokens. Please reduce max_tokens or add credits to your account.",
                                requested,
                                affordable,
                            )
                            # 抛出更友好的错误
                            error_msg = (
                                f"Insufficient credits: You requested {requested} tokens but can only afford {affordable}. "
                                f"Please reduce max_tokens in your request or add credits to your OpenAI-compatible account."
                            )
                            yield {
                                "content": "",
                                "chunk_type": "error",
                                "error": error_msg
                            }
                            yield self._build_error_done_chunk()
                            return
                    except Exception:
                        pass
            
            logger.error(
                "[OpenAI ChatHandler] Stream error: %s",
                summarize_text_for_log(e, label="error"),
            )
            # Yield error chunk
            yield {
                "content": "",
                "chunk_type": "error",
                "error": "OpenAI stream chat failed"
            }
            yield self._build_error_done_chunk()
