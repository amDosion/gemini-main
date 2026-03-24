"""
Grok 聊天处理器

处理 Grok 的聊天相关操作（流式和非流式）。
使用 AsyncOpenAI 客户端（grok2api 提供 OpenAI 兼容接口）。
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)

# grok2api 聊天接口支持的参数
CHAT_ALLOWED_OPTION_KEYS = {
    "temperature",
    "max_tokens",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "stop",
    "n",
    "tools",
    "tool_choice",
    "response_format",
    "reasoning_effort",
}


def _filter_allowed_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Filter kwargs to only include allowed keys."""
    return {k: v for k, v in kwargs.items() if k in CHAT_ALLOWED_OPTION_KEYS}


class ChatHandler:
    """
    Grok 聊天处理器

    使用 AsyncOpenAI 客户端连接 grok2api 的 OpenAI 兼容聊天接口。
    """

    def __init__(self, client: AsyncOpenAI):
        """
        初始化聊天处理器

        Args:
            client: AsyncOpenAI 客户端实例
        """
        self.client = client
        logger.info("[Grok ChatHandler] Initialized")

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
            prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
            completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            total_tokens = usage.get("total_tokens")
        else:
            prompt_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)

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

    @classmethod
    def _prepare_messages(cls, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare messages, handling attachments for multimodal content."""
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

    @classmethod
    def _normalize_multimodal_content(cls, content: Any, attachments: List[Any]) -> Any:
        """Normalize content with image attachments into multimodal format."""
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
            parts.append({"type": "image_url", "image_url": {"url": url}})

        if not attachments:
            return content
        if len(parts) == 0:
            return str(content or "").strip()
        return parts

    @staticmethod
    def _resolve_attachment_url(attachment: Any) -> str:
        if not isinstance(attachment, dict):
            return ""
        for key in ("url", "temp_url", "tempUrl", "file_uri", "fileUri", "base64_data", "base64Data"):
            value = attachment.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _is_image_attachment(attachment: Any, url: str) -> bool:
        mime_type = ""
        if isinstance(attachment, dict):
            mime_type = str(attachment.get("mime_type") or attachment.get("mimeType") or "").strip().lower()
        if mime_type.startswith("image/"):
            return True
        lowered_url = str(url or "").strip().lower()
        if lowered_url.startswith("data:image/"):
            return True
        clean_url = lowered_url.split("?", 1)[0].split("#", 1)[0]
        return clean_url.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))

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
            logger.info(f"[Grok ChatHandler] Chat request: model={model}, messages={len(messages)}")

            supported_params = _filter_allowed_kwargs(kwargs)
            prepared_messages = self._prepare_messages(messages)

            # Map enable_thinking to reasoning_effort
            if kwargs.get("enable_thinking"):
                supported_params["reasoning_effort"] = "high"

            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=prepared_messages,
                **supported_params
            )

            usage = self._normalize_usage(response.usage)
            choice = response.choices[0]
            content = choice.message.content or ""

            # Handle thinking/reasoning content if present
            reasoning_content = ""
            if hasattr(choice.message, "reasoning_content"):
                reasoning_content = choice.message.reasoning_content or ""
            elif hasattr(choice.message, "reasoning"):
                reasoning_content = choice.message.reasoning or ""

            result = {
                "content": content,
                "role": "assistant",
                "usage": usage,
                "model": response.model,
                "finish_reason": choice.finish_reason or "stop",
            }
            if reasoning_content:
                result["reasoning_content"] = reasoning_content

            logger.info(
                f"[Grok ChatHandler] Chat response: "
                f"tokens={result['usage']['total_tokens']}, "
                f"finish_reason={result['finish_reason']}"
            )

            return result

        except Exception as e:
            logger.error(f"[Grok ChatHandler] Chat error: {e}", exc_info=True)
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
            logger.info(f"[Grok ChatHandler] Stream chat request: model={model}, messages={len(messages)}")

            supported_params = _filter_allowed_kwargs(kwargs)
            prepared_messages = self._prepare_messages(messages)

            # Map enable_thinking to reasoning_effort
            if kwargs.get("enable_thinking"):
                supported_params["reasoning_effort"] = "high"

            stream = await self.client.chat.completions.create(
                model=model,
                messages=prepared_messages,
                stream=True,
                stream_options={"include_usage": True},
                **supported_params
            )

            final_usage = None
            final_finish_reason = None

            async for chunk in stream:
                # Capture usage from tail chunk
                if hasattr(chunk, "usage") and chunk.usage:
                    final_usage = chunk.usage

                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason:
                    final_finish_reason = choice.finish_reason

                # Reasoning/thinking chunk
                reasoning_content = None
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    reasoning_content = delta.reasoning_content
                elif hasattr(delta, "reasoning") and delta.reasoning:
                    reasoning_content = delta.reasoning

                if reasoning_content:
                    yield {
                        "content": reasoning_content,
                        "chunk_type": "reasoning",
                    }

                # Content chunk
                if delta.content:
                    yield {
                        "content": delta.content,
                        "chunk_type": "content",
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
                logger.warning("[Grok ChatHandler] Stream finished without usage payload; defaulting to zeros")

            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "finish_reason": finish_reason,
            }

            logger.info(
                f"[Grok ChatHandler] Stream completed: "
                f"tokens={total_tokens}, "
                f"finish_reason={finish_reason}"
            )

        except Exception as e:
            logger.error(f"[Grok ChatHandler] Stream error: {e}", exc_info=True)
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e),
            }
            yield self._build_error_done_chunk()
