"""
Chat Handler Module

Handles chat-related operations (streaming and non-streaming).
"""

import logging
import asyncio
from typing import Dict, Any, List, AsyncGenerator, Set, Optional
import json
import hashlib

from ..client_pool import get_client_pool
from ....core.sdk_executor import run_in_sdk_thread
from .message_converter import (
    MessageConverter,
    decode_inline_attachment_bytes,
    extract_inline_data_url_payload,
    is_allowed_provider_file_uri,
)
from .response_parser import ResponseParser
from .config_builder import ConfigBuilder
from ...common.errors import (
    ProviderError,
    APIKeyError,
    ModelNotFoundError,
    InvalidRequestError,
    OperationError,
    ErrorContext
)
from ...common.progress_tracker import progress_tracker
from ....utils.log_sanitization import summarize_text_for_log, summarize_url_for_log

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
    
    def __init__(self, *, api_key=None, use_vertex=False, project=None, location=None, http_options=None):
        """
        Initialize chat handler.

        Args:
            api_key: Google API key
            use_vertex: Whether to use Vertex AI
            project: GCP project ID (for Vertex AI)
            location: GCP location (for Vertex AI)
            http_options: HTTP options for client
        """
        self._api_key = api_key
        self._use_vertex = use_vertex
        self._project = project
        self._location = location
        self._http_options = http_options

    @staticmethod
    def _to_json_compatible(value: Any) -> Any:
        """Convert SDK/custom objects into JSON-compatible structures."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [ChatHandler._to_json_compatible(item) for item in value]
        if isinstance(value, dict):
            return {str(key): ChatHandler._to_json_compatible(item) for key, item in value.items()}
        if hasattr(value, "model_dump"):
            try:
                return ChatHandler._to_json_compatible(value.model_dump())
            except Exception as _exc:  # fallthrough to next strategy
                logger.debug("[_to_json_compatible] model_dump() failed: %s", _exc)
        if hasattr(value, "to_dict"):
            try:
                return ChatHandler._to_json_compatible(value.to_dict())
            except Exception as _exc:  # fallthrough to next strategy
                logger.debug("[_to_json_compatible] to_dict() failed: %s", _exc)
        if hasattr(value, "dict"):
            try:
                return ChatHandler._to_json_compatible(value.dict())
            except Exception as _exc:  # fallthrough to next strategy
                logger.debug("[_to_json_compatible] dict() failed: %s", _exc)
        if hasattr(value, "__dict__"):
            try:
                return ChatHandler._to_json_compatible(vars(value))
            except Exception as _exc:  # fallthrough to str() fallback
                logger.debug("[_to_json_compatible] vars() failed: %s", _exc)
        return str(value)

    @staticmethod
    def _to_preview_text(value: Any, limit: int = 500) -> str:
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
        return text[:limit]

    @staticmethod
    def _extract_function_call_name(function_call: Any) -> Optional[str]:
        name = getattr(function_call, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
        if isinstance(function_call, dict):
            dict_name = function_call.get("name")
            if isinstance(dict_name, str) and dict_name.strip():
                return dict_name.strip()
        return None

    @staticmethod
    def _extract_function_call_args(function_call: Any) -> Dict[str, Any]:
        raw_args = getattr(function_call, "args", None)
        if raw_args is None and isinstance(function_call, dict):
            raw_args = function_call.get("args") or function_call.get("arguments")

        if isinstance(raw_args, dict):
            return dict(raw_args)

        if raw_args is None:
            return {}

        try:
            return dict(raw_args)
        except Exception as _exc:
            # Warn: non-dict args that cannot be coerced will cause the LLM to
            # receive an empty argument map, which is more visible than silently
            # stringifying and producing an invalid tool call.
            logger.warning(
                "[_extract_function_call_args] Cannot coerce args to dict "
                "(type=%s): %s — returning empty dict",
                type(raw_args).__name__,
                _exc,
            )
            return {}

    @staticmethod
    def _is_browser_tool_name(tool_name: str) -> bool:
        normalized = str(tool_name or "").strip().lower()
        return normalized in {"web_search", "read_webpage", "selenium_browse"}

    @staticmethod
    def _build_browser_operation_id(
        *,
        user_id: Optional[str],
        call_id: str,
        tool_name: str,
    ) -> str:
        normalized_user = str(user_id or "anonymous").strip() or "anonymous"
        normalized_tool = str(tool_name or "browser").strip().lower() or "browser"
        normalized_call = str(call_id or "call").strip() or "call"
        return f"browser:{normalized_user}:{normalized_tool}:{normalized_call}"

    @staticmethod
    async def _emit_browser_progress(
        operation_id: Optional[str],
        *,
        step: str,
        details: str,
        progress: Optional[int],
    ) -> None:
        if not operation_id:
            return
        await progress_tracker.send_progress(
            operation_id=operation_id,
            step=step,
            status="in_progress",
            details=details,
            progress=progress,
        )

    @staticmethod
    async def _complete_browser_progress(operation_id: Optional[str]) -> None:
        if not operation_id:
            return
        await progress_tracker.send_complete(operation_id)

    @staticmethod
    async def _fail_browser_progress(operation_id: Optional[str], error: str) -> None:
        if not operation_id:
            return
        await progress_tracker.send_error(operation_id, error)

    @staticmethod
    def _extract_function_call_id(function_call: Any) -> Optional[str]:
        call_id = getattr(function_call, "id", None)
        if isinstance(call_id, str) and call_id.strip():
            return call_id.strip()
        if isinstance(function_call, dict):
            dict_id = function_call.get("id")
            if isinstance(dict_id, str) and dict_id.strip():
                return dict_id.strip()
        return None

    @staticmethod
    def _build_function_call_dedup_key(name: str, args: Dict[str, Any], call_id: Optional[str]) -> str:
        if call_id:
            return f"id:{call_id}"
        try:
            args_serialized = json.dumps(args, ensure_ascii=False, sort_keys=True)
        except Exception:
            args_serialized = str(args)
        args_hash = hashlib.sha256(args_serialized.encode("utf-8")).hexdigest()[:10]
        return f"sig:{name}:{args_hash}"
    
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
            # 从统一池获取客户端
            client = get_client_pool().get_client(
                api_key=self._api_key,
                vertexai=self._use_vertex,
                project=self._project,
                location=self._location,
                http_options=self._http_options,
            )

            logger.info(
                "[Chat Handler] Chat request: model=%s, messages=%s",
                summarize_text_for_log(model, label="model"),
                len(messages),
            )

            # 转换消息格式
            contents = MessageConverter.build_contents(messages)

            # 构建配置
            config = ConfigBuilder.build_generate_config(**kwargs)

            # 调用新版 SDK（同步方法），放到专用 SDK 线程池中避免阻塞事件循环。
            response = await run_in_sdk_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=config if config else None,
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
            logger.error(
                "[Chat Handler] Chat error: %s",
                summarize_text_for_log(e, label="chat_error"),
            )
            # Convert Google SDK errors to ProviderError
            converted_error = self._convert_error(e, model, "chat")
            raise converted_error
    
    def _convert_error(self, error: Exception, model: str, operation: str) -> Exception:
        """
        Convert Google SDK errors to ProviderError subclasses.
        
        Args:
            error: Original exception
            model: Model name
            operation: Operation name (e.g., 'chat', 'stream_chat')
            
        Returns:
            Converted ProviderError or original error if conversion not needed
        """
        # Check if it's a Google SDK error
        error_type = type(error).__name__
        error_module = type(error).__module__
        
        if error_module.startswith('google.genai.errors'):
            # Create error context
            context = ErrorContext(
                provider_id="google",
                client_type="single",
                operation=operation,
                model=model
            )
            
            # Extract error details
            error_str = str(error)
            status_code = None
            if hasattr(error, 'status_code'):
                status_code = error.status_code
            
            # Check error type and status code
            if status_code == 400:
                if 'API key' in error_str or 'API_KEY' in error_str:
                    return APIKeyError(context=context, original_error=error)
                else:
                    return InvalidRequestError(
                        message=f"Invalid request: {error_str}",
                        context=context,
                        original_error=error
                    )
            elif status_code == 404:
                if 'model' in error_str.lower() or 'not found' in error_str.lower():
                    return ModelNotFoundError(context=context, original_error=error)
                else:
                    return InvalidRequestError(
                        message=f"Resource not found: {error_str}",
                        context=context,
                        original_error=error
                    )
            elif status_code == 429:
                return OperationError(
                    message=f"Rate limit exceeded: {error_str}",
                    context=context,
                    original_error=error,
                    recoverable=True
                )
            else:
                # Generic operation error
                return OperationError(
                    message=f"Operation failed: {error_str}",
                    context=context,
                    original_error=error,
                    recoverable=status_code and status_code >= 500  # Server errors are recoverable
                )
        
        # Return original error if not a Google SDK error
        return error
    
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
            # 从统一池获取客户端
            client = get_client_pool().get_client(
                api_key=self._api_key,
                vertexai=self._use_vertex,
                project=self._project,
                location=self._location,
                http_options=self._http_options,
            )

            logger.info(
                "[Chat Handler] SSE Stream chat: model=%s, messages=%s",
                summarize_text_for_log(model, label="model"),
                len(messages),
            )

            # 转换消息格式为官方 SDK 格式
            contents = MessageConverter.build_contents(messages)

            # 构建配置
            config = ConfigBuilder.build_generate_config(**kwargs)

            # 使用官方 SDK 的流式生成方法
            # 这个方法使用 SSE (Server-Sent Events) 协议，URL 包含 ?alt=sse 参数
            stream = client.models.generate_content_stream(
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
                    logger.warning(
                        "[Chat Handler] Failed to extract text from SSE chunk: %s",
                        summarize_text_for_log(e, label="sse_chunk_error"),
                    )
                
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
                    logger.warning(
                        "[Chat Handler] Failed to extract usage from SSE chunk: %s",
                        summarize_text_for_log(e, label="sse_usage_error"),
                    )
                
                # 提取完成原因
                try:
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                            finish_reason = candidate.finish_reason.lower()
                except Exception as e:
                    logger.warning(
                        "[Chat Handler] Failed to extract finish_reason from SSE chunk: %s",
                        summarize_text_for_log(e, label="sse_finish_reason_error"),
                    )
            
            # 发送完成块
            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
                "finish_reason": finish_reason
            }
            
            logger.info("[Chat Handler] SSE Stream completed: length=%s", len(total_text))
        
        except Exception as e:
            logger.error(
                "[Chat Handler] SSE Stream error: %s",
                summarize_text_for_log(e, label="sse_stream_error"),
            )
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
            logger.error(
                "[Chat Handler] Typewriter effect error: %s",
                summarize_text_for_log(e, label="typewriter_error"),
            )
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
        enable_browser: bool = False,
        user_id: str = None,
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
            enable_browser: 启用 Browser Tools (web_search, read_webpage, selenium_browse)
            **kwargs: 额外参数（temperature, max_tokens 等）

        Yields:
            {"content": str, "chunk_type": "content"} - 内容块
            {"chunk_type": "tool_call", ...} - 工具调用块
            {"chunk_type": "done", "usage": {...}} - 完成块
            {"chunk_type": "error", "error": str} - 错误块
        """
        try:
            # 输入验证
            if not messages or not isinstance(messages, list):
                raise ValueError("messages must be a non-empty list")
            if not model or not isinstance(model, str):
                raise ValueError("model must be a non-empty string")
            
            # 从统一池获取客户端
            client = get_client_pool().get_client(
                api_key=self._api_key,
                vertexai=self._use_vertex,
                project=self._project,
                location=self._location,
                http_options=self._http_options,
            )
            
            logger.info(
                f"[Chat Handler] Stream chat (Async SDK): model={model}, "
                f"messages={len(messages)}, search={enable_search}, thinking={enable_thinking}, browser={enable_browser}"
            )

            mcp_session_id = kwargs.get("mcp_session_id")
            mcp_manager = None
            mcp_tool_names: Set[str] = set()
            preloaded_function_declarations = kwargs.get("additional_function_declarations")
            mcp_function_declarations: List[Dict[str, Any]] = []

            if isinstance(preloaded_function_declarations, list) and preloaded_function_declarations:
                for decl in preloaded_function_declarations:
                    if not isinstance(decl, dict):
                        continue
                    name = decl.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    mcp_tool_names.add(name)
                    mcp_function_declarations.append(
                        {
                            "name": name,
                            "description": decl.get("description", ""),
                            "parameters": decl.get("parameters"),
                        }
                    )
                logger.info(
                    "[Chat Handler] Reusing preloaded MCP tools: count=%s",
                    len(mcp_function_declarations),
                )
                if mcp_session_id:
                    try:
                        from ...mcp.mcp_manager import get_mcp_manager

                        mcp_manager = get_mcp_manager()
                    except Exception as e:
                        logger.warning(
                            "[Chat Handler] Failed to get MCP manager for preloaded tools: %s",
                            summarize_text_for_log(e, label="mcp_manager_error"),
                        )

            elif mcp_session_id:
                try:
                    from ...mcp.mcp_manager import get_mcp_manager

                    mcp_manager = get_mcp_manager()
                    gemini_tools = await mcp_manager.get_gemini_tools(mcp_session_id)
                    for tool_group in gemini_tools:
                        if not isinstance(tool_group, dict):
                            continue
                        for decl in tool_group.get("function_declarations", []):
                            if not isinstance(decl, dict):
                                continue
                            name = decl.get("name")
                            if not name:
                                continue
                            mcp_tool_names.add(name)
                            mcp_function_declarations.append(
                                {
                                    "name": name,
                                    "description": decl.get("description", ""),
                                    "parameters": decl.get("parameters"),
                                }
                            )
                    logger.info(
                        "[Chat Handler] MCP tools loaded: session=%s, tool_count=%s",
                        summarize_text_for_log(mcp_session_id, label="mcp_session_id"),
                        len(mcp_tool_names),
                    )
                except Exception as e:
                    logger.warning(
                        "[Chat Handler] Failed to load MCP tools for session=%s: %s",
                        summarize_text_for_log(mcp_session_id, label="mcp_session_id"),
                        summarize_text_for_log(e, label="mcp_tools_error"),
                    )
                    mcp_manager = None
                    mcp_tool_names = set()
                    mcp_function_declarations = []

            config_kwargs = dict(kwargs)
            if mcp_function_declarations:
                config_kwargs["additional_function_declarations"] = mcp_function_declarations

            # 构建配置（包含工具）
            config = ConfigBuilder.build_generate_config_with_tools(
                enable_search=enable_search,
                enable_thinking=enable_thinking,
                enable_code_execution=enable_code_execution,
                enable_grounding=enable_grounding,
                enable_browser=enable_browser,
                **config_kwargs
            )
            
            logger.info(
                "[Chat Handler] Async SDK config: %s",
                summarize_text_for_log(config, label="async_sdk_config"),
            )
            
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
                hist_attachments = msg.get('attachments', [])
                if hist_attachments:
                    # Build multi-modal parts using the same logic as the
                    # current-message path so history attachments are correctly
                    # forwarded to the SDK.
                    hist_parts = []
                    for att in hist_attachments:
                        part = self._build_attachment_part(att)
                        if part:
                            hist_parts.append(part)
                    hist_parts.append(genai_types.Part(text=content))
                    history.append(
                        genai_types.Content(role=role, parts=hist_parts)
                    )
                else:
                    history.append(
                        genai_types.Content(
                            role=role,
                            parts=[genai_types.Part(text=content)]
                        )
                    )
            
            # 使用异步 API 创建聊天会话
            async_chat = client.aio.chats.create(
                model=model,
                config=config,
                history=history
            )
            
            # 发送当前消息并异步流式接收响应（支持函数调用循环）
            current_content = current_message['content']
            current_attachments = current_message.get('attachments', [])
            total_text = ""
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            finish_reason = "stop"

            # 构建多模态消息内容（文本 + 附件）
            if current_attachments:
                message_parts = []
                for att in current_attachments:
                    part = self._build_attachment_part(att)
                    if part:
                        message_parts.append(part)
                message_parts.append(genai_types.Part(text=current_content))
                current_message_content = message_parts
                logger.info(
                    f"[Chat Handler] 多模态消息: {len(message_parts)} parts "
                    f"({len(current_attachments)} attachments + 1 text)"
                )
            else:
                current_message_content = current_content

            # 函数调用循环（最多 5 次迭代）
            max_iterations = 5

            for iteration in range(max_iterations):
                logger.info(
                    "[Chat Handler] Function call loop iteration %s/%s",
                    iteration + 1,
                    max_iterations,
                )

                response_stream = await async_chat.send_message_stream(message=current_message_content)
                function_calls: List[Dict[str, Any]] = []
                seen_function_call_keys: Set[str] = set()

                # 异步迭代流
                async for chunk in response_stream:
                    chunk_text = ""
                    thinking_text = ""

                    # ✅ 始终检查 candidates 以检测函数调用和提取文本
                    # 不能依赖 chunk.text，因为当有 function_call 时它可能为空
                    try:
                        if hasattr(chunk, 'candidates') and chunk.candidates:
                            candidate = chunk.candidates[0]
                            if hasattr(candidate, 'content') and candidate.content:
                                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                    for part in candidate.content.parts:
                                        # ✅ 检测 thought parts（Gemini Thinking Mode）
                                        thought_value = getattr(part, 'thought', None)
                                        if thought_value and hasattr(part, 'text') and part.text:
                                            thinking_text += part.text
                                        # 提取普通文本
                                        elif hasattr(part, 'text') and part.text:
                                            chunk_text += part.text
                                        # 检测函数调用
                                        if hasattr(part, 'function_call') and part.function_call:
                                            raw_call = part.function_call
                                            call_name = self._extract_function_call_name(raw_call)
                                            if not call_name:
                                                continue
                                            call_args = self._extract_function_call_args(raw_call)
                                            call_id = self._extract_function_call_id(raw_call)
                                            dedup_key = self._build_function_call_dedup_key(
                                                name=call_name,
                                                args=call_args,
                                                call_id=call_id
                                            )
                                            if dedup_key in seen_function_call_keys:
                                                continue
                                            seen_function_call_keys.add(dedup_key)
                                            normalized_call_id = call_id or f"auto_{iteration}_{len(function_calls) + 1}_{hashlib.sha1(dedup_key.encode('utf-8')).hexdigest()[:10]}"
                                            function_calls.append(
                                                {
                                                    "call_id": normalized_call_id,
                                                    "name": call_name,
                                                    "args": call_args,
                                                }
                                            )
                                            logger.info(
                                                "[Chat Handler] Detected function_call: name=%s call_id=%s",
                                                summarize_text_for_log(call_name, label="function_name"),
                                                summarize_text_for_log(normalized_call_id, label="function_call_id"),
                                            )

                        # 直接检查 chunk.function_calls（某些 SDK 响应路径）
                        if hasattr(chunk, 'function_calls') and chunk.function_calls:
                            for raw_call in chunk.function_calls:
                                call_name = self._extract_function_call_name(raw_call)
                                if not call_name:
                                    continue
                                call_args = self._extract_function_call_args(raw_call)
                                call_id = self._extract_function_call_id(raw_call)
                                dedup_key = self._build_function_call_dedup_key(
                                    name=call_name,
                                    args=call_args,
                                    call_id=call_id
                                )
                                if dedup_key in seen_function_call_keys:
                                    continue
                                seen_function_call_keys.add(dedup_key)
                                normalized_call_id = call_id or f"auto_{iteration}_{len(function_calls) + 1}_{hashlib.sha1(dedup_key.encode('utf-8')).hexdigest()[:10]}"
                                function_calls.append(
                                    {
                                        "call_id": normalized_call_id,
                                        "name": call_name,
                                        "args": call_args,
                                    }
                                )
                                logger.info(
                                    "[Chat Handler] Detected function_call (direct): name=%s call_id=%s",
                                    summarize_text_for_log(call_name, label="function_name"),
                                    summarize_text_for_log(normalized_call_id, label="function_call_id"),
                                )
                    except Exception as e:
                        logger.warning(
                            "[Chat Handler] Failed to extract from chunk: %s",
                            summarize_text_for_log(e, label="chunk_error"),
                        )

                    # ✅ 先 yield thinking chunk，再 yield content chunk
                    if thinking_text:
                        yield {
                            "content": thinking_text,
                            "chunk_type": "reasoning"
                        }

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
                        logger.warning(
                            "[Chat Handler] Failed to extract usage: %s",
                            summarize_text_for_log(e, label="usage_error"),
                        )

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
                        logger.warning(
                            "[Chat Handler] Failed to extract finish_reason: %s",
                            summarize_text_for_log(e, label="finish_reason_error"),
                        )

                # 如果没有函数调用，退出循环
                if not function_calls:
                    logger.info("[Chat Handler] No function calls detected, exiting loop")
                    break

                # 执行函数调用并发送响应
                logger.info("[Chat Handler] Detected %s function call(s)", len(function_calls))

                # 导入浏览器工具
                try:
                    from .browser import AVAILABLE_TOOLS
                except ImportError:
                    logger.error("[Chat Handler] Browser tools not available")
                    break

                function_response_parts = []

                for func_call in function_calls:
                    func_name = func_call["name"]
                    func_args = dict(func_call.get("args") or {})
                    call_id = func_call["call_id"]
                    browser_operation_id = (
                        self._build_browser_operation_id(
                            user_id=user_id,
                            call_id=call_id,
                            tool_name=func_name,
                        )
                        if self._is_browser_tool_name(func_name)
                        else None
                    )

                    logger.info(
                        "[Chat Handler] Executing function: name=%s args=%s",
                        summarize_text_for_log(func_name, label="function_name"),
                        summarize_text_for_log(func_args, label="function_args"),
                    )

                    # 通知前端正在执行工具
                    tool_call_chunk = {
                        "content": "",
                        "chunk_type": "tool_call",
                        "call_id": call_id,
                        "tool_type": "function_call",
                        "tool_name": func_name,
                        "tool_args": func_args
                    }
                    if browser_operation_id:
                        tool_call_chunk["browser_operation_id"] = browser_operation_id
                    yield tool_call_chunk

                    if browser_operation_id:
                        await self._emit_browser_progress(
                            browser_operation_id,
                            step="Queued",
                            details=f"准备执行 {func_name}",
                            progress=5,
                        )

                    # 执行工具
                    if func_name in AVAILABLE_TOOLS:
                        tool_func = AVAILABLE_TOOLS[func_name]
                        try:
                            import inspect
                            # 对于 selenium_browse，传递 user_id 以实现会话隔离
                            if func_name == "selenium_browse" and user_id:
                                func_args["user_id"] = user_id

                            if browser_operation_id:
                                step = {
                                    "web_search": "Searching Web",
                                    "read_webpage": "Reading Webpage",
                                    "selenium_browse": "Launching Browser",
                                }.get(func_name, "Running Browser Tool")
                                await self._emit_browser_progress(
                                    browser_operation_id,
                                    step=step,
                                    details=f"{func_name} 正在执行",
                                    progress=30 if func_name != "selenium_browse" else 20,
                                )

                            if inspect.iscoroutinefunction(tool_func):
                                result = await tool_func(**func_args)
                            else:
                                result = tool_func(**func_args)

                            # 处理 selenium_browse 返回的结构化响应 (Dict with content, screenshot, error)
                            screenshot_base64 = None
                            if isinstance(result, dict):
                                # selenium_browse 返回 {"content": str, "screenshot": base64, "error": str}
                                if result.get("error"):
                                    response_data = {"error": result["error"]}
                                else:
                                    response_data = {"output": result.get("content", "")}
                                    screenshot_base64 = result.get("screenshot")
                            else:
                                # 其他工具返回字符串
                                response_data = {"output": result}

                            logger.info(
                                "[Chat Handler] Function executed successfully: name=%s",
                                summarize_text_for_log(func_name, label="function_name"),
                            )

                            # 通知前端工具执行结果（包含截图 URL）
                            tool_result_chunk = {
                                "content": "",
                                "chunk_type": "tool_result",
                                "call_id": call_id,
                                "tool_name": func_name,
                                "tool_result": response_data.get("output", response_data.get("error", ""))[:500]  # 截断显示
                            }
                            if browser_operation_id:
                                tool_result_chunk["browser_operation_id"] = browser_operation_id
                            if response_data.get("error"):
                                tool_result_chunk["tool_error"] = response_data.get("error")
                            # 如果有截图，上传到存储并发送 URL 给前端
                            screenshot_url = None
                            if screenshot_base64 and user_id:
                                try:
                                    import base64
                                    from datetime import datetime
                                    from app.routers.storage import upload_to_active_storage_async

                                    image_bytes = base64.b64decode(screenshot_base64)
                                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

                                    upload_result = await upload_to_active_storage_async(
                                        content=image_bytes,
                                        filename=filename,
                                        content_type="image/png",
                                        user_id=user_id
                                    )

                                    if upload_result.get("success"):
                                        if browser_operation_id:
                                            await self._emit_browser_progress(
                                                browser_operation_id,
                                                step="Uploading Screenshot",
                                                details="浏览截图已生成，正在上传",
                                                progress=85,
                                        )
                                        screenshot_url = upload_result.get("url")
                                        tool_result_chunk["screenshot_url"] = screenshot_url
                                        logger.info(
                                            "[Chat Handler] Screenshot uploaded: %s",
                                            summarize_url_for_log(screenshot_url),
                                        )
                                    else:
                                        logger.warning(
                                            "[Chat Handler] Screenshot upload failed: %s",
                                            summarize_text_for_log(
                                                upload_result.get("error"),
                                                label="screenshot_upload_error",
                                            ),
                                        )
                                        # 上传失败时回退到 base64（但仅在截图较小时）
                                        if len(screenshot_base64) < 500000:  # < 500KB
                                            tool_result_chunk["screenshot"] = screenshot_base64
                                except Exception as e:
                                    logger.warning(
                                        "[Chat Handler] Screenshot upload error: %s",
                                        summarize_text_for_log(e, label="screenshot_upload_error"),
                                    )
                            elif screenshot_base64:
                                # 没有 user_id 时使用 base64（仅在截图较小时）
                                if len(screenshot_base64) < 500000:
                                    tool_result_chunk["screenshot"] = screenshot_base64

                            if browser_operation_id:
                                await self._emit_browser_progress(
                                    browser_operation_id,
                                    step="Finalizing",
                                    details=f"{func_name} 执行完成，正在整理结果",
                                    progress=95,
                                )
                                await self._complete_browser_progress(browser_operation_id)
                            yield tool_result_chunk

                        except Exception as e:
                            response_data = {"error": str(e)}
                            screenshot_base64 = None
                            logger.error(
                                "[Chat Handler] Function failed: name=%s error=%s",
                                summarize_text_for_log(func_name, label="function_name"),
                                summarize_text_for_log(e, label="function_error"),
                            )
                            if browser_operation_id:
                                await self._fail_browser_progress(browser_operation_id, str(e))
                            yield {
                                "content": "",
                                "chunk_type": "tool_result",
                                "call_id": call_id,
                                "tool_name": func_name,
                                "tool_result": str(e)[:500],
                                "tool_error": str(e),
                                **(
                                    {"browser_operation_id": browser_operation_id}
                                    if browser_operation_id else {}
                                ),
                            }
                    elif mcp_manager and mcp_session_id and func_name in mcp_tool_names:
                        screenshot_base64 = None
                        try:
                            mcp_result = await mcp_manager.call_tool(
                                session_id=mcp_session_id,
                                tool_name=func_name,
                                arguments=func_args
                            )
                            if mcp_result.success and not mcp_result.is_error:
                                normalized_result = self._to_json_compatible(mcp_result.result)
                                response_data = {"output": normalized_result}
                                preview_text = self._to_preview_text(normalized_result)
                            else:
                                error_text = mcp_result.error or "MCP tool call failed"
                                response_data = {"error": error_text}
                                preview_text = error_text

                            tool_result_chunk = {
                                "content": "",
                                "chunk_type": "tool_result",
                                "call_id": call_id,
                                "tool_name": func_name,
                                "tool_result": preview_text
                            }
                            if response_data.get("error"):
                                tool_result_chunk["tool_error"] = response_data.get("error")
                            yield tool_result_chunk
                            logger.info(
                                "[Chat Handler] MCP function executed: name=%s",
                                summarize_text_for_log(func_name, label="function_name"),
                            )
                        except Exception as e:
                            response_data = {"error": str(e)}
                            logger.error(
                                "[Chat Handler] MCP function failed: name=%s error=%s",
                                summarize_text_for_log(func_name, label="function_name"),
                                summarize_text_for_log(e, label="mcp_function_error"),
                            )
                            yield {
                                "content": "",
                                "chunk_type": "tool_result",
                                "call_id": call_id,
                                "tool_name": func_name,
                                "tool_result": str(e)[:500],
                                "tool_error": str(e),
                            }
                    else:
                        response_data = {"error": f"Unknown function: {func_name}"}
                        screenshot_base64 = None
                        logger.warning(
                            "[Chat Handler] Unknown function: %s",
                            summarize_text_for_log(func_name, label="function_name"),
                        )
                        yield {
                            "content": "",
                            "chunk_type": "tool_result",
                            "call_id": call_id,
                            "tool_name": func_name,
                            "tool_result": response_data["error"][:500],
                            "tool_error": response_data["error"],
                        }

                    # 创建函数响应 Part
                    response_part = genai_types.Part.from_function_response(
                        name=func_name,
                        response=response_data
                    )
                    function_response_parts.append(response_part)

                    # 如果有截图，创建图片 Part 并添加到响应中
                    # 根据 Browser_as_a_tool.ipynb，截图应该和函数响应一起发送给模型
                    if screenshot_base64:
                        try:
                            import base64
                            image_bytes = base64.b64decode(screenshot_base64)
                            image_part = genai_types.Part.from_bytes(
                                data=image_bytes,
                                mime_type="image/png"
                            )
                            function_response_parts.append(image_part)
                            logger.info("[Chat Handler] Added screenshot image to response")
                        except Exception as e:
                            logger.warning(
                                "[Chat Handler] Failed to add screenshot: %s",
                                summarize_text_for_log(e, label="screenshot_error"),
                            )

                # 将函数响应作为下一条消息发送
                current_message_content = function_response_parts
                logger.info(
                    "[Chat Handler] Sending %s function response(s) back to model",
                    len(function_response_parts),
                )

            # Done 块
            yield {
                "content": "",
                "chunk_type": "done",
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
                "finish_reason": finish_reason
            }

            logger.info("[Chat Handler] Stream completed (Async SDK): length=%s", len(total_text))
        
        except Exception as e:
            logger.error(
                "[Chat Handler] Stream error (Async SDK): %s",
                summarize_text_for_log(e, label="stream_error"),
            )
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }

    @staticmethod
    def _build_attachment_part(attachment: Dict[str, Any]):
        """
        从附件字典构建 genai_types.Part（用于多模态消息）

        支持的附件数据源（按优先级）：
        1. fileUri → file_data Part（Google Files API）
        2. url/tempUrl (data: URL) → inline_data Part（Base64）
        3. base64Data → inline_data Part（纯 Base64 字符串）

        Args:
            attachment: 附件字典，包含 mimeType、fileUri、url、tempUrl、base64Data 等字段

        Returns:
            genai_types.Part 或 None（如果无法构建）
        """
        if not GENAI_TYPES_AVAILABLE:
            logger.warning("[Chat Handler] genai_types not available, cannot build attachment part")
            return None

        mime_type = attachment.get('mimeType', 'image/png')

        # Priority 1: fileUri (Google Files API)
        file_uri = attachment.get('fileUri')
        if file_uri:
            if not is_allowed_provider_file_uri(file_uri):
                logger.warning("[Chat Handler] Attachment: rejected unsupported fileUri")
                return None
            logger.info(
                "[Chat Handler] Attachment: file_data uri=%s",
                summarize_url_for_log(str(file_uri)),
            )
            return genai_types.Part(
                file_data=genai_types.FileData(
                    file_uri=file_uri,
                    mime_type=mime_type
                )
            )

        # Priority 2: url or tempUrl with Base64 Data URL
        url = attachment.get('url') or attachment.get('tempUrl')
        if url:
            try:
                data_url_payload = extract_inline_data_url_payload(
                    url,
                    fallback_mime_type=mime_type,
                    source="attachment data URL",
                )
            except ValueError as exc:
                logger.warning("[Chat Handler] Attachment: rejected data URL: %s", exc)
                return None
            if data_url_payload:
                actual_mime, base64_str = data_url_payload
                image_bytes = decode_inline_attachment_bytes(
                    base64_str,
                    source="attachment data URL",
                )
                logger.info(
                    "[Chat Handler] Attachment: inline_data from data URL (mime=%s, size=%s bytes)",
                    actual_mime,
                    len(image_bytes),
                )
                return genai_types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=actual_mime
                )

        # Priority 3: base64Data field (pure Base64 string or data URL)
        base64_data = attachment.get('base64Data')
        if base64_data:
            try:
                data_url_payload = extract_inline_data_url_payload(
                    base64_data,
                    fallback_mime_type=mime_type,
                    source="attachment base64Data",
                )
                if data_url_payload:
                    actual_mime, base64_str = data_url_payload
                    image_bytes = decode_inline_attachment_bytes(
                        base64_str,
                        source="attachment base64Data",
                    )
                    logger.info(
                        "[Chat Handler] Attachment: inline_data from base64Data (mime=%s, size=%s bytes)",
                        actual_mime,
                        len(image_bytes),
                    )
                    return genai_types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=actual_mime
                    )
                image_bytes = decode_inline_attachment_bytes(
                    base64_data,
                    source="attachment base64Data",
                )
                logger.info(
                    "[Chat Handler] Attachment: inline_data from raw base64 (mime=%s, size=%s bytes)",
                    mime_type,
                    len(image_bytes),
                )
                return genai_types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                )
            except ValueError as exc:
                logger.warning("[Chat Handler] Attachment: rejected base64Data: %s", exc)
                return None

        logger.warning(
            "[Chat Handler] Attachment: no usable data found (mimeType=%s, hasUrl=%s, hasBase64=%s)",
            mime_type,
            bool(url),
            bool(base64_data),
        )
        return None
