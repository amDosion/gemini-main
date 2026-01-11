"""
Chat Handler Module

Handles chat-related operations (streaming and non-streaming).
"""

import logging
import asyncio
from typing import Dict, Any, List, AsyncGenerator

from .sdk_initializer import SDKInitializer
from .message_converter import MessageConverter
from .response_parser import ResponseParser
from .config_builder import ConfigBuilder

logger = logging.getLogger(__name__)

# 使用新版 google-genai SDK
try:
    from google.genai import types as genai_types
    GENAI_TYPES_AVAILABLE = True
except ImportError:
    GENAI_TYPES_AVAILABLE = False


class ChatHandler:
    """
    Handles chat operations using Google Gemini models.
    
    Provides:
    - Non-streaming chat (chat)
    - Streaming chat (stream_chat)
    """
    
    def __init__(self, sdk_initializer: SDKInitializer):
        """
        Initialize chat handler.
        
        Args:
            sdk_initializer: SDK initializer instance
        """
        self.sdk_initializer = sdk_initializer
    
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat request and get a complete response (non-streaming).
        
        Uses the google-genai SDK's generate_content() API for text generation.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: Model identifier (e.g., 'gemini-pro', 'gemini-1.5-pro')
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        
        Returns:
            Dict containing content, role, usage, model, finish_reason
        """
        try:
            # 确保 SDK 已初始化
            self.sdk_initializer.ensure_initialized()
            
            logger.info(f"[Chat Handler] Chat request: model={model}, messages={len(messages)}")
            
            # 转换消息格式
            contents = MessageConverter.build_contents(messages)
            
            # 构建配置
            config = ConfigBuilder.build_generate_config(**kwargs)
            
            # 调用新版 SDK
            response = self.sdk_initializer.client.models.generate_content(
                model=model,
                contents=contents,
                config=config if config else None
            )
            
            # 解析响应
            result = ResponseParser.parse_generate_content_response(response, model)
            
            logger.info(
                f"[Chat Handler] Chat response: "
                f"tokens={result['usage']['total_tokens']}, "
                f"finish_reason={result['finish_reason']}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"[Chat Handler] Chat error: {e}", exc_info=True)
            raise
    
    async def stream_chat_sse(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        使用官方 SDK 的 SSE (Server-Sent Events) 流式生成
        
        基于官方文档中的 generate_content_stream 方法，使用 SSE 协议实现流式输出。
        
        Args:
            messages: 标准消息格式 [{"role": "user"|"model", "content": str}]
            model: 模型名称 (如 'gemini-2.0-flash')
            **kwargs: 额外参数（temperature, max_tokens 等）
        
        Yields:
            {"content": str, "chunk_type": "content"} - 内容块
            {"chunk_type": "done", "usage": {...}} - 完成块
            {"chunk_type": "error", "error": str} - 错误块
        """
        try:
            # 确保 SDK 已初始化
            self.sdk_initializer.ensure_initialized()
            
            logger.info(f"[Chat Handler] SSE Stream chat: model={model}, messages={len(messages)}")
            
            # 转换消息格式为官方 SDK 格式
            contents = MessageConverter.build_contents(messages)
            
            # 构建配置
            config = ConfigBuilder.build_generate_config(**kwargs)
            
            # 使用官方 SDK 的流式生成方法
            # 这个方法使用 SSE (Server-Sent Events) 协议，URL 包含 ?alt=sse 参数
            stream = self.sdk_initializer.client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config if config else None
            )
            
            total_text = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            finish_reason = "stop"
            
            # 迭代 SSE 流，每个 chunk 包含部分生成的文本
            for chunk in stream:
                chunk_text = ""
                
                # 提取文本内容
                try:
                    if hasattr(chunk, 'text') and chunk.text:
                        chunk_text = chunk.text
                    elif hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        chunk_text += part.text
                except Exception as e:
                    logger.warning(f"[Chat Handler] Failed to extract text from SSE chunk: {e}")
                
                # 发送文本块
                if chunk_text:
                    total_text += chunk_text
                    yield {
                        "content": chunk_text,
                        "chunk_type": "content"
                    }
                
                # 提取使用统计信息
                try:
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        metadata = chunk.usage_metadata
                        if hasattr(metadata, 'prompt_token_count'):
                            usage["prompt_tokens"] = metadata.prompt_token_count
                        if hasattr(metadata, 'candidates_token_count'):
                            usage["completion_tokens"] = metadata.candidates_token_count
                        if hasattr(metadata, 'total_token_count'):
                            usage["total_tokens"] = metadata.total_token_count
                except Exception as e:
                    logger.warning(f"[Chat Handler] Failed to extract usage from SSE chunk: {e}")
                
                # 提取完成原因
                try:
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                            finish_reason = candidate.finish_reason.lower()
                except Exception as e:
                    logger.warning(f"[Chat Handler] Failed to extract finish_reason from SSE chunk: {e}")
            
            # 发送完成块
            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
                "finish_reason": finish_reason
            }
            
            logger.info(f"[Chat Handler] SSE Stream completed: length={len(total_text)}")
        
        except Exception as e:
            logger.error(f"[Chat Handler] SSE Stream error: {e}", exc_info=True)
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }
    
    async def stream_chat_with_typewriter_effect(
        self, 
        messages: List[Dict[str, Any]], 
        model: str,
        delay: float = 0.02,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        实现打字机效果的流式聊天
        
        基于官方文档中的打字机效果实现，逐字符发送内容。
        
        Args:
            messages: 标准消息格式
            model: 模型名称
            delay: 字符间延迟（秒）
            **kwargs: 额外参数
        
        Yields:
            每个字符作为单独的块发送
        """
        try:
            # 首先获取完整响应
            full_response = await self.chat(messages, model, **kwargs)
            full_text = full_response.get('content', '')
            
            # 逐字符发送，模拟打字机效果
            for char in full_text:
                yield {
                    "content": char,
                    "chunk_type": "content"
                }
                # 异步延迟
                await asyncio.sleep(delay)
            
            # 发送完成块
            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": full_response.get('usage', {}).get('prompt_tokens', 0),
                "completion_tokens": full_response.get('usage', {}).get('completion_tokens', 0),
                "total_tokens": full_response.get('usage', {}).get('total_tokens', 0),
                "finish_reason": full_response.get('finish_reason', 'stop')
            }
            
        except Exception as e:
            logger.error(f"[Chat Handler] Typewriter effect error: {e}", exc_info=True)
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }
    
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        enable_search: bool = False,
        enable_thinking: bool = False,
        enable_code_execution: bool = False,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        使用 google-genai SDK 异步 API 进行流式聊天
        
        Args:
            messages: 标准消息格式 [{"role": "user"|"model", "content": str}]
            model: 模型名称
            enable_search: 启用 Google Search
            enable_thinking: 启用 Thinking Mode
            enable_code_execution: 启用 Code Execution
            enable_grounding: 启用 Grounding
            **kwargs: 额外参数（temperature, max_tokens 等）
        
        Yields:
            {"content": str, "chunk_type": "content"} - 内容块
            {"chunk_type": "done", "usage": {...}} - 完成块
            {"chunk_type": "error", "error": str} - 错误块
        """
        try:
            # 输入验证
            if not messages or not isinstance(messages, list):
                raise ValueError("messages must be a non-empty list")
            if not model or not isinstance(model, str):
                raise ValueError("model must be a non-empty string")
            
            # 确保 SDK 已初始化
            self.sdk_initializer.ensure_initialized()
            
            logger.info(
                f"[Chat Handler] Stream chat (Async SDK): model={model}, "
                f"messages={len(messages)}, search={enable_search}, thinking={enable_thinking}"
            )
            
            # 构建配置（包含工具）
            config = ConfigBuilder.build_generate_config_with_tools(
                enable_search=enable_search,
                enable_thinking=enable_thinking,
                enable_code_execution=enable_code_execution,
                enable_grounding=enable_grounding,
                **kwargs
            )
            
            logger.info(f"[Chat Handler] Async SDK config: {config}")
            
            # 分离历史消息和当前消息
            if len(messages) == 0:
                raise ValueError("At least one message is required")
            
            history_messages = messages[:-1]
            current_message = messages[-1]
            
            # 转换历史消息为 SDK 格式
            if not GENAI_TYPES_AVAILABLE:
                raise RuntimeError("google.genai.types not available")
            
            history = []
            for msg in history_messages:
                role = msg['role']
                content = msg['content']
                history.append(
                    genai_types.Content(
                        role=role,
                        parts=[genai_types.Part(text=content)]
                    )
                )
            
            # 使用异步 API 创建聊天会话
            async_chat = self.sdk_initializer.client.aio.chats.create(
                model=model,
                config=config,
                history=history
            )
            
            # 发送当前消息并异步流式接收响应
            current_content = current_message['content']
            response_stream = await async_chat.send_message_stream(message=current_content)
            
            total_text = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            finish_reason = "stop"
            
            # 异步迭代流
            async for chunk in response_stream:
                # 提取文本
                chunk_text = ""
                try:
                    if hasattr(chunk, 'text'):
                        chunk_text = chunk.text
                    elif hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            parts = candidate.content.parts
                            if parts and hasattr(parts[0], 'text'):
                                chunk_text = parts[0].text
                except Exception as e:
                    logger.warning(f"[Chat Handler] Failed to extract text from chunk: {e}")
                
                if chunk_text:
                    total_text += chunk_text
                    yield {
                        "content": chunk_text,
                        "chunk_type": "content"
                    }
                
                # 提取 usage
                try:
                    if hasattr(chunk, 'usage_metadata'):
                        metadata = chunk.usage_metadata
                        if hasattr(metadata, 'prompt_token_count'):
                            usage["prompt_tokens"] = metadata.prompt_token_count
                        if hasattr(metadata, 'candidates_token_count'):
                            usage["completion_tokens"] = metadata.candidates_token_count
                        if hasattr(metadata, 'total_token_count'):
                            usage["total_tokens"] = metadata.total_token_count
                except Exception as e:
                    logger.warning(f"[Chat Handler] Failed to extract usage: {e}")
                
                # 提取 finish_reason
                try:
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'finish_reason'):
                            reason = candidate.finish_reason
                            reason_map = {
                                1: "stop", 2: "length", 3: "safety",
                                4: "recitation", 5: "other"
                            }
                            finish_reason = reason_map.get(reason, "stop")
                except Exception as e:
                    logger.warning(f"[Chat Handler] Failed to extract finish_reason: {e}")
            
            # Done 块
            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
                "finish_reason": finish_reason
            }
            
            logger.info(f"[Chat Handler] Stream completed (Async SDK): length={len(total_text)}")
        
        except Exception as e:
            logger.error(f"[Chat Handler] Stream error (Async SDK): {e}", exc_info=True)
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }
