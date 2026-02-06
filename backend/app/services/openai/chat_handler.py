"""
OpenAI 聊天处理器

处理 OpenAI 的聊天相关操作（流式和非流式）。
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

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
        
        # Create AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3)
        )
        
        logger.info(f"[OpenAI ChatHandler] Initialized with base_url={self.base_url}")
    
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

            # ✅ 过滤掉 OpenAI API 不支持的参数
            # top_k 只有 Gemini 等部分 API 支持，OpenAI API 不支持
            supported_params = {}
            for key, value in kwargs.items():
                if key not in ['top_k']:  # 排除不支持的参数
                    supported_params[key] = value

            # Call OpenAI API
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **supported_params
            )
            
            # Convert to unified format
            result = {
                "content": response.choices[0].message.content or "",
                "role": "assistant",
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
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

            # ✅ 过滤掉 OpenAI API 不支持的参数
            # top_k 只有 Gemini 等部分 API 支持，OpenAI API 不支持
            supported_params = {}
            for key, value in kwargs.items():
                if key not in ['top_k']:  # 排除不支持的参数
                    supported_params[key] = value

            # Call OpenAI API with streaming
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **supported_params
            )
            
            # Stream chunks
            async for chunk in stream:
                # Skip empty chunks
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Content chunk
                if delta.content:
                    yield {
                        "content": delta.content,
                        "chunk_type": "content"
                    }
                
                # Done chunk (last chunk with usage info)
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield {
                        "content": "",
                        "chunk_type": "done",
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                        "finish_reason": chunk.choices[0].finish_reason or "stop"
                    }
                    
                    logger.info(
                        f"[OpenAI ChatHandler] Stream completed: "
                        f"tokens={chunk.usage.total_tokens}, "
                        f"finish_reason={chunk.choices[0].finish_reason}"
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
                                f"Please reduce max_tokens in your request or add credits to your OpenRouter account."
                            )
                            yield {
                                "content": "",
                                "chunk_type": "error",
                                "error": error_msg
                            }
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
