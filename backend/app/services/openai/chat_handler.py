"""
OpenAI 聊天处理器

处理 OpenAI 的聊天相关操作（流式和非流式）。
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

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
        
        logger.info(f"[OpenAI ChatHandler] Initialized with base_url={self.base_url}")

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
        if not isinstance(attachment, dict):
            return ""
        for key in (
            "url",
            "temp_url",
            "tempUrl",
            "file_uri",
            "fileUri",
            "base64_data",
            "base64Data",
        ):
            value = attachment.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _is_image_attachment(attachment: Any, url: str) -> bool:
        mime_type = ""
        if isinstance(attachment, dict):
            mime_type = str(
                attachment.get("mime_type")
                or attachment.get("mimeType")
                or ""
            ).strip().lower()
        if mime_type.startswith("image/"):
            return True
        lowered_url = str(url or "").strip().lower()
        if lowered_url.startswith("data:image/"):
            return True
        clean_url = lowered_url.split("?", 1)[0].split("#", 1)[0]
        return clean_url.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))

    @classmethod
    def _normalize_multimodal_content(
        cls,
        content: Any,
        attachments: List[Any],
    ) -> Any:
        parts: List[Dict[str, Any]] = []

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    item_type = str(item.get("type") or "").strip().lower()
                    if item_type == "text":
                        text_value = str(item.get("text") or "").strip()
                        if text_value:
                            parts.append({"type": "text", "text": text_value})
                        continue
                    if item_type == "image_url" and isinstance(item.get("image_url"), dict):
                        image_url = str(item["image_url"].get("url") or "").strip()
                        if image_url:
                            parts.append({"type": "image_url", "image_url": {"url": image_url}})
                        continue
                item_text = str(item or "").strip()
                if item_text:
                    parts.append({"type": "text", "text": item_text})
        else:
            text_value = str(content or "").strip()
            if text_value:
                parts.append({"type": "text", "text": text_value})

        for attachment in attachments:
            url = cls._resolve_attachment_url(attachment)
            if not url or not cls._is_image_attachment(attachment, url):
                continue
            parts.append({
                "type": "image_url",
                "image_url": {
                    "url": url,
                },
            })

        if not attachments:
            return content
        if len(parts) == 0:
            return str(content or "").strip()
        return parts

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
            logger.info(f"[OpenAI ChatHandler] Chat request: model={model}, messages={len(messages)}")

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
                f"[OpenAI ChatHandler] Chat response: "
                f"tokens={result['usage']['total_tokens']}, "
                f"finish_reason={result['finish_reason']}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI ChatHandler] Chat error: {e}", exc_info=True)
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
            max_tokens_info = f", max_tokens={kwargs.get('max_tokens', 'default')}" if 'max_tokens' in kwargs else ""
            logger.info(f"[OpenAI ChatHandler] Stream chat request: model={model}, messages={len(messages)}{max_tokens_info}")

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
                                f"[OpenAI ChatHandler] Credit limit exceeded: "
                                f"requested={requested} tokens, affordable={affordable} tokens. "
                                f"Please reduce max_tokens or add credits to your account."
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
            
            logger.error(f"[OpenAI ChatHandler] Stream error: {e}", exc_info=True)
            # Yield error chunk
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }
            yield self._build_error_done_chunk()
