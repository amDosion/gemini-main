"""
Ollama OpenAI 兼容 API 处理器

处理 Ollama 的 OpenAI 兼容 API 调用（/v1/* 端点）。
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
import tiktoken
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)


class OpenAICompatibleHandler:
    """
    Ollama OpenAI 兼容 API 处理器
    
    负责处理所有 OpenAI 兼容 API 调用。
    """
    
    def __init__(self, api_key: str, base_url: str, **kwargs):
        """
        初始化 OpenAI 兼容 API 处理器
        
        Args:
            api_key: API 密钥
            base_url: OpenAI 兼容 API 基础 URL（应包含 /v1）
            **kwargs: 额外参数
        """
        self.api_key = api_key
        
        # 确保 base_url 以 /v1 结尾
        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        
        self.base_url = base_url
        
        # 创建 AsyncOpenAI 客户端
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=kwargs.get("timeout", 120.0)
        )
        
        # Token 估算器（延迟加载）
        self.encoding = None
        
        logger.info(f"[Ollama OpenAICompatHandler] Initialized with base_url={base_url}")
    
    def _get_encoding(self, model: str):
        """获取或初始化 tokenizer"""
        if self.encoding is None:
            try:
                self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            except KeyError:
                self.encoding = tiktoken.get_encoding("cl100k_base")
        return self.encoding
    
    def _estimate_tokens(self, messages: List[Dict[str, Any]], model: str) -> int:
        """估算消息列表的 token 数量"""
        encoding = self._get_encoding(model)
        num_tokens = 0
        for message in messages:
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(encoding.encode(str(value)))
                if key == "name":
                    num_tokens -= 1
        num_tokens += 2
        return num_tokens

    @staticmethod
    def _normalize_usage(usage: Any) -> Dict[str, int]:
        """将不同形态的 usage 对象统一为 prompt/completion/total 三元组。"""
        if not usage:
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        prompt_tokens = (
            getattr(usage, "prompt_tokens", None)
            if not isinstance(usage, dict)
            else usage.get("prompt_tokens")
        )
        completion_tokens = (
            getattr(usage, "completion_tokens", None)
            if not isinstance(usage, dict)
            else usage.get("completion_tokens")
        )
        total_tokens = (
            getattr(usage, "total_tokens", None)
            if not isinstance(usage, dict)
            else usage.get("total_tokens")
        )

        # 兼容少数 OpenAI-compatible 返回 input/output 字段命名
        if prompt_tokens is None:
            prompt_tokens = (
                getattr(usage, "input_tokens", 0)
                if not isinstance(usage, dict)
                else usage.get("input_tokens", 0)
            )
        if completion_tokens is None:
            completion_tokens = (
                getattr(usage, "output_tokens", 0)
                if not isinstance(usage, dict)
                else usage.get("output_tokens", 0)
            )

        prompt_tokens = int(prompt_tokens or 0)
        completion_tokens = int(completion_tokens or 0)
        total_tokens = int(total_tokens or (prompt_tokens + completion_tokens))

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }

    @staticmethod
    def _build_error_done_chunk() -> Dict[str, Any]:
        return {
            "content": "",
            "chunk_type": "done",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "finish_reason": "error",
        }
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        同步聊天调用
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
        
        Returns:
            聊天响应字典
        """
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            
            choice = response.choices[0]
            usage = self._normalize_usage(response.usage)
            
            logger.info(
                f"[Ollama OpenAICompatHandler] Chat completed: "
                f"tokens={usage['total_tokens']}, model={response.model}"
            )
            
            return {
                "content": choice.message.content or "",
                "role": "assistant",
                "usage": {
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"]
                },
                "model": response.model,
                "finish_reason": choice.finish_reason,
                "cost": 0.0  # 本地免费
            }
        
        except Exception as e:
            logger.error(f"[Ollama OpenAICompatHandler] Chat error: {e}", exc_info=True)
            raise
    
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天调用
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
        
        Yields:
            流式响应块
        """
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs
            )
            
            usage = None
            model_name = model
            completion_text = ""
            final_finish_reason = None
            
            async for chunk in stream:
                # 捕获 usage 信息
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = chunk.usage
                
                # 捕获实际使用的模型名
                if hasattr(chunk, "model") and chunk.model:
                    model_name = chunk.model

                # usage-only 尾块可能不带 choices
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason:
                    final_finish_reason = choice.finish_reason
                
                # Yield content chunk
                if delta.content:
                    completion_text += delta.content
                    yield {
                        "content": delta.content,
                        "chunk_type": "content",
                        "model": model_name
                    }
            
            # 在流结束时 yield done chunk
            finish_reason = final_finish_reason or "stop"
            if usage:
                normalized_usage = self._normalize_usage(usage)
                yield {
                    "content": "",
                    "chunk_type": "done",
                    "prompt_tokens": normalized_usage["prompt_tokens"],
                    "completion_tokens": normalized_usage["completion_tokens"],
                    "total_tokens": normalized_usage["total_tokens"],
                    "cost": 0.0,
                    "finish_reason": finish_reason
                }
            else:
                # API 不返回 usage 信息，使用 tiktoken 估算
                logger.warning(f"[Ollama OpenAICompatHandler] No usage information, estimating tokens")
                
                prompt_tokens = self._estimate_tokens(messages, model_name)
                encoding = self._get_encoding(model_name)
                completion_tokens = len(encoding.encode(completion_text)) if completion_text else 0
                total_tokens = prompt_tokens + completion_tokens
                
                yield {
                    "content": "",
                    "chunk_type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost": 0.0,
                    "finish_reason": finish_reason
                }
        
        except Exception as e:
            logger.error(f"[Ollama OpenAICompatHandler] Stream error: {e}", exc_info=True)
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }
            yield self._build_error_done_chunk()
