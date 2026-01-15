"""
通义千问聊天服务 - DashScope SDK 实现

使用阿里云 DashScope 原生 SDK，支持高级功能:
- 网页搜索 (enable_search)
- 代码解释器 (code_interpreter plugin)
- PDF解析 (pdf_extracter plugin)
- 图片理解 (qwen-vl models)

优势:
- 100% 功能访问 (vs OpenAI 兼容 API 50%)
- 与图片服务架构统一 (都用原生 SDK)
- 支持未来所有高级功能
"""

from typing import Dict, Any, Optional, List
import logging
import asyncio
from dashscope import Generation, MultiModalConversation
import dashscope

from ..common.base_provider import BaseProviderService
from ..common.model_capabilities import ModelConfig, build_model_config
from ..common.errors import (
    ProviderError,
    OperationError,
    APIKeyError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError,
    ErrorContext,
    ExecutionTimer,
    RequestIDManager
)
from .model_manager import ModelManager

logger = logging.getLogger(__name__)


# 视觉模型列表（使用 MultiModalConversation API）
VISION_MODELS = [
    "qwen-vl-max",
    "qwen-vl-max-latest",
    "qwen-vl-max-0809",
    "qwen-vl-plus",
    "qwen-vl-plus-latest",
    "qwen-vl-plus-0809",
    "qwen2-vl-72b-instruct",
    "qwen2-vl-7b-instruct",
    "qwen2-vl-2b-instruct",
    "qwen2.5-vl-72b-instruct",
    "qwen2.5-vl-32b-instruct",
    "qwen2.5-vl-7b-instruct",
    "qwen2.5-vl-3b-instruct",
]


def is_vision_model(model_id: str) -> bool:
    """判断是否为视觉模型"""
    lower_id = model_id.lower()
    # 检查是否在视觉模型列表中，或者包含 "vl" 关键字
    return model_id in VISION_MODELS or "-vl-" in lower_id or lower_id.endswith("-vl")


class QwenNativeProvider(BaseProviderService):
    """通义千问原生 SDK Provider"""

    # 万相模型列表（静态维护）
    # 注意：这些模型无法通过 OpenAI Compatible API 获取，需要手动维护
    # 更新日期：2025-12-28
    WANX_MODELS = [
        # ========== 文生图 V2 版模型（推荐） ==========
        "wan2.6-t2i",           # 万相2.6 推荐，支持同步接口，自由选尺寸 | 0.20元/张
        "wan2.5-t2i-preview",   # 万相2.5 preview，取消单边限制 | 0.20元/张
        "wan2.2-t2i-plus",      # 万相2.2专业版，创意性、稳定性、写实质感升级 | 0.20元/张
        "wan2.2-t2i-flash",     # 万相2.2极速版 | 0.14元/张
        "wanx2.1-t2i-plus",     # 万相2.1专业版，支持多种风格 | 0.20元/张
        "wanx2.1-t2i-turbo",    # 万相2.1极速版，生成速度快 | 0.14元/张
        "wanx2.0-t2i-turbo",    # 万相2.0极速版，性价比高 | 0.04元/张

        # ========== 图像编辑模型 ==========
        "wan2.6-image",         # 万相2.6图像编辑，支持图文混合输出 | 0.20元/张
    ]

    def __init__(self, api_key: str, api_url: Optional[str] = None,
                 organization_id: Optional[str] = None, request_id: Optional[str] = None, **kwargs):
        """
        初始化通义千问 Provider

        Args:
            api_key: DashScope API Key
            api_url: API地址(可选,原生SDK不使用)
            organization_id: 组织ID(可选)
            request_id: 请求ID(可选,用于追踪)
            **kwargs: 额外参数
                - connection_mode: official(官方,启用高级功能) / proxy(代理,禁用高级功能)
                - max_concurrent: 最大并发数(默认20)
                - client_selector: ClientSelector instance for dual-client mode (optional)
        """
        self.api_key = api_key
        self.api_url = api_url
        self.organization_id = organization_id
        self.connection_mode = kwargs.get("connection_mode", "official")
        self.max_concurrent = kwargs.get("max_concurrent", 20)

        # Generate or use provided request ID
        self.request_id = request_id or RequestIDManager.generate()

        # Store ClientSelector for dual-client mode
        self.client_selector = kwargs.get("client_selector")
        if self.client_selector:
            logger.info(
                f"[Qwen Provider] Initialized with ClientSelector: {self.client_selector.__class__.__name__}",
                extra={'request_id': self.request_id, 'operation': 'initialization'}
            )

        # 设置 DashScope API Key
        dashscope.api_key = api_key
        
        # Initialize ModelManager for model listing
        self.model_manager = ModelManager(api_key, api_url)

        logger.info(
            f"[Qwen Provider] Initialized with connection_mode={self.connection_mode}",
            extra={'request_id': self.request_id, 'operation': 'initialization', 'connection_mode': self.connection_mode}
        )

    def _should_use_primary_client(self, **kwargs) -> bool:
        """
        Determine if primary client (DashScope native SDK) should be used.

        Primary client is used for:
        - Web search (enable_search)
        - Code interpreter plugin
        - PDF parsing plugin
        - Thinking models (enable_thinking)
        - Any advanced features

        Secondary client (OpenAI-compatible) is used for:
        - Basic chat without advanced features

        Args:
            **kwargs: Operation parameters

        Returns:
            True if primary client should be used, False for secondary
        """
        # If no ClientSelector, use connection_mode setting
        if not self.client_selector:
            use_primary = self.connection_mode == "official"
            logger.debug(f"[Qwen Provider] No ClientSelector, using connection_mode: {self.connection_mode} -> primary={use_primary}")
            return use_primary

        # Check for advanced features that require primary client
        requires_primary = (
            kwargs.get("enable_search") or
            kwargs.get("plugins") or
            kwargs.get("enable_thinking") or
            kwargs.get("model", "").startswith("qwen-long") or  # Long-context models
            kwargs.get("model", "").endswith("-thinking")  # Thinking models
        )

        if requires_primary:
            logger.info(f"[Qwen Provider] Advanced features detected, using primary client (DashScope native SDK)")
            return True

        # Use ClientSelector for operation-based selection
        operation_type = kwargs.get("operation_type", "chat")
        client_type = self.client_selector.select_client(
            operation_type=operation_type,
            user_preference=kwargs.get("client_preference"),
            **kwargs
        )

        use_primary = client_type == "primary"
        logger.info(f"[Qwen Provider] ClientSelector chose: {client_type} for operation={operation_type}")
        return use_primary

    # ==================== 同步 SDK 调用 (基类会自动包装成 async) ====================

    def _sync_chat(self, messages: list, model: str, **kwargs) -> Any:
        """
        同步聊天调用

        由基类通过 asyncio.to_thread 自动包装成 async

        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
                - temperature: 温度(0-2)
                - top_p: 核采样
                - max_tokens: 最大生成 tokens
                - enable_search: 启用网页搜索(官方模式)
                - plugins: 插件配置(官方模式)

        Returns:
            DashScope GenerationResponse 对象
        """
        timer = ExecutionTimer()

        try:
            # 基础参数
            params = {
                "model": model,
                "messages": messages,
                "result_format": "message",  # 使用 message 格式(与 OpenAI 兼容)
            }

            # 可选参数
            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]
            if "top_p" in kwargs:
                params["top_p"] = kwargs["top_p"]
            if "max_tokens" in kwargs:
                params["max_tokens"] = kwargs["max_tokens"]

            # 高级功能参数(仅官方模式)
            if self.connection_mode == "official":
                # 网页搜索
                if kwargs.get("enable_search"):
                    params["enable_search"] = True
                    # 搜索选项（高级配置）
                    params["search_options"] = {
                        "forced_search": True,         # 强制搜索（确保执行搜索）
                        "enable_source": True,          # 启用来源标注
                        "enable_citation": True,        # 启用引用标注
                        "citation_format": "[ref_<number>]"  # 引用格式
                    }

                # 插件系统
                plugins = kwargs.get("plugins")
                if plugins:
                    # 支持两种格式:
                    # 1. 列表: ["code_interpreter", "pdf_extracter"]
                    # 2. 字典: {"code_interpreter": {"enable": True}}
                    if isinstance(plugins, list):
                        # 转换列表为字典格式
                        params["plugins"] = {
                            plugin: {"enable": True}
                            for plugin in plugins
                        }
                    else:
                        params["plugins"] = plugins

            # 调用 DashScope SDK
            response = Generation.call(**params)

            # 错误处理
            if response.status_code != 200:
                self._handle_error(
                    error_code=response.code,
                    error_message=response.message,
                    error_map=self._get_error_map(),
                    operation="chat",
                    model=model
                )

            # 记录成功日志
            logger.info(
                "Chat request completed",
                extra={
                    'request_id': self.request_id,
                    'operation': 'chat',
                    'execution_time_ms': timer.elapsed_ms,
                    'model': model
                }
            )

            return response

        except Exception as e:
            # 如果不是我们的错误类型，包装为 OperationError
            if not isinstance(e, ProviderError):
                context = ErrorContext(
                    provider_id="qwen",
                    client_type="primary" if self.connection_mode == "official" else "secondary",
                    operation="chat",
                    request_id=self.request_id,
                    model=model,
                    execution_time_ms=timer.elapsed_ms
                )
                raise OperationError(
                    message=f"Chat operation failed: {str(e)}",
                    context=context,
                    original_error=e,
                    recoverable=True
                )
            raise

    def _sync_stream_chat(self, messages: list, model: str, **kwargs):
        """
        同步流式调用

        返回同步迭代器,基类负责 async 包装

        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
                - enable_thinking: 启用思考模式(thinking models)

        Yields:
            DashScope GenerationResponse 对象(chunk)
        """
        timer = ExecutionTimer()

        try:
            # 基础参数(与 _sync_chat 相同)
            params = {
                "model": model,
                "messages": messages,
                "result_format": "message",
                "stream": True,  # 启用流式
                "incremental_output": True,  # 增量输出
            }

            # 可选参数
            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]
            if "top_p" in kwargs:
                params["top_p"] = kwargs["top_p"]
            if "max_tokens" in kwargs:
                params["max_tokens"] = kwargs["max_tokens"]

            # 高级功能(仅官方模式)
            if self.connection_mode == "official":
                if kwargs.get("enable_search"):
                    params["enable_search"] = True

                # Thinking 模型支持
                if kwargs.get("enable_thinking"):
                    params["enable_thinking"] = True

                plugins = kwargs.get("plugins")
                if plugins:
                    if isinstance(plugins, list):
                        params["plugins"] = {
                            plugin: {"enable": True}
                            for plugin in plugins
                        }
                    else:
                        params["plugins"] = plugins

            # 调用流式 API
            responses = Generation.call(**params)

            # 迭代生成 chunk
            for response in responses:
                if response.status_code != 200:
                    # 流式中的错误
                    self._handle_error(
                        error_code=response.code,
                        error_message=response.message,
                        error_map=self._get_error_map(),
                        operation="stream_chat",
                        model=model
                    )
                yield response

            # 记录成功日志
            logger.info(
                "Stream chat request completed",
                extra={
                    'request_id': self.request_id,
                    'operation': 'stream_chat',
                    'execution_time_ms': timer.elapsed_ms,
                    'model': model
                }
            )

        except Exception as e:
            # 如果不是我们的错误类型，包装为 OperationError
            if not isinstance(e, ProviderError):
                context = ErrorContext(
                    provider_id="qwen",
                    client_type="primary" if self.connection_mode == "official" else "secondary",
                    operation="stream_chat",
                    request_id=self.request_id,
                    model=model,
                    execution_time_ms=timer.elapsed_ms
                )
                raise OperationError(
                    message=f"Stream chat operation failed: {str(e)}",
                    context=context,
                    original_error=e,
                    recoverable=True
                )
            raise

    # ==================== 多模态（视觉模型）支持 ====================

    def _sync_multimodal_chat(self, messages: list, model: str, **kwargs) -> Any:
        """
        同步多模态聊天调用（视觉模型）

        使用 MultiModalConversation API 处理图文混合输入

        Args:
            messages: 多模态消息列表，格式：
                [
                    {
                        "role": "user",
                        "content": [
                            {"image": "http://xxx.jpg"},
                            {"text": "描述这张图片"}
                        ]
                    }
                ]
            model: 视觉模型名称（如 qwen-vl-max）
            **kwargs: 额外参数

        Returns:
            DashScope MultiModalConversationResponse 对象
        """
        timer = ExecutionTimer()

        try:
            params = {
                "model": model,
                "messages": messages,
            }

            # 可选参数
            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]
            if "top_p" in kwargs:
                params["top_p"] = kwargs["top_p"]
            if "max_tokens" in kwargs:
                params["max_tokens"] = kwargs["max_tokens"]

            # 调用多模态 API
            response = MultiModalConversation.call(**params)

            # 错误处理
            if response.status_code != 200:
                self._handle_error(
                    error_code=response.code,
                    error_message=response.message,
                    error_map=self._get_error_map(),
                    operation="multimodal_chat",
                    model=model
                )

            # 记录成功日志
            logger.info(
                "Multimodal chat request completed",
                extra={
                    'request_id': self.request_id,
                    'operation': 'multimodal_chat',
                    'execution_time_ms': timer.elapsed_ms,
                    'model': model
                }
            )

            return response

        except Exception as e:
            # 如果不是我们的错误类型，包装为 OperationError
            if not isinstance(e, ProviderError):
                context = ErrorContext(
                    provider_id="qwen",
                    client_type="primary" if self.connection_mode == "official" else "secondary",
                    operation="multimodal_chat",
                    request_id=self.request_id,
                    model=model,
                    execution_time_ms=timer.elapsed_ms
                )
                raise OperationError(
                    message=f"Multimodal chat operation failed: {str(e)}",
                    context=context,
                    original_error=e,
                    recoverable=True
                )
            raise

    def _sync_stream_multimodal_chat(self, messages: list, model: str, **kwargs):
        """
        同步流式多模态聊天调用（视觉模型）

        Args:
            messages: 多模态消息列表
            model: 视觉模型名称
            **kwargs: 额外参数

        Yields:
            DashScope MultiModalConversationResponse 对象（chunk）
        """
        timer = ExecutionTimer()

        try:
            params = {
                "model": model,
                "messages": messages,
                "stream": True,
                "incremental_output": True,
            }

            # 可选参数
            if "temperature" in kwargs:
                params["temperature"] = kwargs["temperature"]
            if "top_p" in kwargs:
                params["top_p"] = kwargs["top_p"]
            if "max_tokens" in kwargs:
                params["max_tokens"] = kwargs["max_tokens"]

            # 调用流式多模态 API
            responses = MultiModalConversation.call(**params)

            # 迭代生成 chunk
            for response in responses:
                if response.status_code != 200:
                    self._handle_error(
                        error_code=response.code,
                        error_message=response.message,
                        error_map=self._get_error_map(),
                        operation="stream_multimodal_chat",
                        model=model
                    )
                yield response

            # 记录成功日志
            logger.info(
                "Stream multimodal chat request completed",
                extra={
                    'request_id': self.request_id,
                    'operation': 'stream_multimodal_chat',
                    'execution_time_ms': timer.elapsed_ms,
                    'model': model
                }
            )

        except Exception as e:
            # 如果不是我们的错误类型，包装为 OperationError
            if not isinstance(e, ProviderError):
                context = ErrorContext(
                    provider_id="qwen",
                    client_type="primary" if self.connection_mode == "official" else "secondary",
                    operation="stream_multimodal_chat",
                    request_id=self.request_id,
                    model=model,
                    execution_time_ms=timer.elapsed_ms
                )
                raise OperationError(
                    message=f"Stream multimodal chat operation failed: {str(e)}",
                    context=context,
                    original_error=e,
                    recoverable=True
                )
            raise

    def _format_multimodal_stream_chunk(self, chunk: Any) -> Dict[str, Any]:
        """
        格式化多模态流式 chunk

        MultiModalConversation 的响应格式与 Generation 略有不同

        Args:
            chunk: DashScope MultiModalConversationResponse 对象

        Returns:
            StreamChunk 格式
        """
        output = chunk.output

        # 多模态响应的 choices 结构
        choices = output.get("choices", []) if isinstance(output, dict) else getattr(output, "choices", [])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason")

        # 提取内容（多模态响应的 content 可能是列表）
        content = message.get("content", "")
        if isinstance(content, list):
            # 从列表中提取文本内容
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
            content = "".join(text_parts)

        result = {
            "content": content,
            "chunk_type": "content"
        }

        # 提取 usage 信息
        usage = chunk.usage if hasattr(chunk, "usage") else None
        if usage:
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)

            if finish_reason == "stop":
                result.update({
                    "chunk_type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "finish_reason": finish_reason
                })
                logger.info(f"[Qwen VL] Stream ended: prompt={prompt_tokens}, completion={completion_tokens}")
            else:
                result.update({
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                })
                if finish_reason:
                    result["finish_reason"] = finish_reason

        return result

    def _format_multimodal_response(self, response: Any) -> Dict[str, Any]:
        """
        格式化多模态响应为 ChatResponse

        Args:
            response: DashScope MultiModalConversationResponse 对象

        Returns:
            ChatResponse 格式
        """
        output = response.output

        # 多模态响应的 choices 结构
        choices = output.get("choices", []) if isinstance(output, dict) else getattr(output, "choices", [])
        choice = choices[0] if choices else {}
        message = choice.get("message", {})

        # 提取内容（多模态响应的 content 可能是列表）
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and "text" in item]
            content = "".join(text_parts)

        # 提取 usage 信息
        usage = response.usage if hasattr(response, "usage") else None
        usage_dict = {
            "prompt_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
            "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0
        }

        return {
            "content": content,
            "role": message.get("role", "assistant"),
            "usage": usage_dict,
            "model": "qwen-vl",
            "finish_reason": choice.get("finish_reason", "stop")
        }

    # ==================== 响应格式化 ====================

    def _format_response(self, response: Any) -> Dict[str, Any]:
        """
        格式化 DashScope 响应为 ChatResponse

        Args:
            response: DashScope GenerationResponse 对象

        Returns:
            ChatResponse 格式:
            {
                "content": str,
                "role": str,
                "usage": {...},
                "model": str,
                "finish_reason": str
            }
        """
        # 提取消息内容
        output = response.output
        choice = output.choices[0] if output.choices else {}
        message = choice.get("message", {})

        # 提取 usage 信息
        usage = response.usage
        usage_dict = {
            "prompt_tokens": usage.input_tokens if hasattr(usage, 'input_tokens') else 0,
            "completion_tokens": usage.output_tokens if hasattr(usage, 'output_tokens') else 0,
            "total_tokens": usage.total_tokens if hasattr(usage, 'total_tokens') else 0
        }

        # 安全获取 model 名称（DashScope 响应对象的 hasattr 不可靠）
        try:
            model_name = output.model if output.model else "qwen"
        except (KeyError, AttributeError):
            model_name = "qwen"

        return {
            "content": message.get("content", ""),
            "role": message.get("role", "assistant"),
            "usage": usage_dict,
            "model": model_name,
            "finish_reason": choice.get("finish_reason", "stop")
        }

    def _format_stream_chunk(self, chunk: Any) -> Dict[str, Any]:
        """
        格式化流式 chunk 为 StreamChunk

        支持 thinking 模型的 reasoning_content（推理内容）分离

        Args:
            chunk: DashScope GenerationResponse 对象(chunk)

        Returns:
            StreamChunk 格式:
            {
                "content": str,
                "chunk_type": str,  # "reasoning", "content", "done"
                "finish_reason": Optional[str],
                "prompt_tokens": Optional[int],  # 在最后的 chunk 中
                "completion_tokens": Optional[int],
                "total_tokens": Optional[int]
            }
        """
        output = chunk.output
        choice = output.choices[0] if output.choices else {}
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason")

        # Thinking 模型支持：区分 reasoning_content 和 content
        reasoning_content = message.get("reasoning_content", "")
        content = message.get("content", "")

        # 确定 chunk 类型和内容（按照官方示例的优先级）
        if reasoning_content:
            # 思考过程 chunk
            result = {
                "content": reasoning_content,
                "chunk_type": "reasoning"
            }
        elif content:
            # 回复内容 chunk
            result = {
                "content": content,
                "chunk_type": "content"
            }
        else:
            # 空 chunk（thinking 模型会产生很多空 chunk）
            result = {
                "content": "",
                "chunk_type": "content"
            }

        # 提取 usage 信息（如果存在）
        if hasattr(chunk, 'usage') and chunk.usage:
            usage = chunk.usage
            prompt_tokens = usage.input_tokens if hasattr(usage, 'input_tokens') else 0
            completion_tokens = usage.output_tokens if hasattr(usage, 'output_tokens') else 0
            total_tokens = usage.total_tokens if hasattr(usage, 'total_tokens') else (prompt_tokens + completion_tokens)

            # 只在 finish_reason == "stop" 时返回 done chunk（流真正结束）
            # thinking 模型会产生大量空 chunk，不能仅依据 content 为空判断
            if finish_reason == "stop":
                # 提取搜索结果（如果有）
                search_results = None
                try:
                    # DashScope response 对象的 hasattr 会抛出 KeyError，需要用 try/except
                    if output.search_info and 'search_results' in output.search_info:
                        search_results = output.search_info['search_results']
                        logger.info(f"[Qwen] Captured {len(search_results)} search results")
                except (KeyError, AttributeError, TypeError):
                    # search_info 不存在或没有 search_results 字段，这是正常情况
                    pass

                result.update({
                    "chunk_type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "finish_reason": finish_reason,
                    "search_results": search_results  # 新增：搜索结果
                })
                logger.info(f"[Qwen] Stream ended: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
            else:
                # 其他 chunk（有 finish_reason 但不是 stop，或无 finish_reason）
                # 附带 usage 信息但保持 content 类型
                result.update({
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                })
                if finish_reason:
                    result["finish_reason"] = finish_reason

        return result

    # ==================== 辅助方法 ====================

    def _get_error_map(self) -> Dict[str, type]:
        """
        获取 DashScope 特定的错误码映射

        Returns:
            错误码到异常类的映射
        """
        return {
            "InvalidApiKey": APIKeyError,
            "InvalidAPIKey": APIKeyError,
            "Throttling.RateQuota": RateLimitError,
            "Throttling.AllocationQuota": RateLimitError,
            "InvalidModel": ModelNotFoundError,
            "UnsupportedModel": ModelNotFoundError,
            "InvalidParameter": InvalidRequestError,
            "InvalidInput": InvalidRequestError,
        }

    def _handle_error(self, error_code: str, error_message: str, error_map: Dict[str, type],
                      operation: str = "unknown", model: Optional[str] = None):
        """
        处理 DashScope API 错误，使用统一错误处理系统

        Args:
            error_code: 错误码
            error_message: 错误信息
            error_map: 错误码到异常类的映射
            operation: 操作类型 (chat, stream_chat, multimodal_chat 等)
            model: 模型名称
        """
        # 创建错误上下文
        context = ErrorContext(
            provider_id="qwen",
            client_type="primary" if self.connection_mode == "official" else "secondary",
            operation=operation,
            request_id=self.request_id,
            model=model,
            additional_context={
                "error_code": error_code,
                "connection_mode": self.connection_mode
            }
        )

        # 查找对应的异常类
        exception_class = error_map.get(error_code)

        if exception_class == APIKeyError:
            raise APIKeyError(context=context)
        elif exception_class == RateLimitError:
            raise RateLimitError(context=context)
        elif exception_class == ModelNotFoundError:
            raise ModelNotFoundError(context=context)
        elif exception_class == InvalidRequestError:
            raise InvalidRequestError(context=context)
        else:
            # 未知错误，使用 OperationError
            raise OperationError(
                message=f"[{error_code}] {error_message}",
                context=context,
                recoverable=True
            )

    async def chat(self, messages: list, model: str, **kwargs) -> Dict[str, Any]:
        """
        异步非流式聊天

        将同步调用包装为异步

        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
                - enable_search: 启用网页搜索
                - temperature: 温度
                - max_tokens: 最大生成 tokens

        Returns:
            格式化后的 ChatResponse
        """
        loop = asyncio.get_event_loop()

        # 判断是否为视觉模型
        if is_vision_model(model):
            response = await loop.run_in_executor(
                None,
                lambda: self._sync_multimodal_chat(messages=messages, model=model, **kwargs)
            )
            return self._format_multimodal_response(response)
        else:
            response = await loop.run_in_executor(
                None,
                lambda: self._sync_chat(messages=messages, model=model, **kwargs)
            )
            return self._format_response(response)

    async def stream_chat(self, messages: list, model: str, **kwargs):
        """
        异步流式聊天

        将同步流式调用包装为异步生成器

        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
                - enable_search: 启用网页搜索
                - enable_thinking: 启用思考模式
                - temperature: 温度
                - max_tokens: 最大生成 tokens

        Yields:
            格式化后的 StreamChunk
        """
        # 在线程池中运行同步流式调用
        loop = asyncio.get_event_loop()

        # 判断是否为视觉模型
        if is_vision_model(model):
            def sync_stream():
                return self._sync_stream_multimodal_chat(messages=messages, model=model, **kwargs)

            sync_iter = await loop.run_in_executor(None, sync_stream)

            for chunk in sync_iter:
                formatted = self._format_multimodal_stream_chunk(chunk)
                yield formatted
        else:
            def sync_stream():
                return self._sync_stream_chat(messages=messages, model=model, **kwargs)

            sync_iter = await loop.run_in_executor(None, sync_stream)

            for chunk in sync_iter:
                formatted = self._format_stream_chunk(chunk)
                yield formatted

    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表（委托给 ModelManager）

        Returns:
            ModelConfig 列表（已去重和排序）
        """
        return await self.model_manager.get_available_models()

    def get_provider_name(self) -> str:
        """
        获取提供商名称

        Returns:
            提供商名称
        """
        return "Qwen"

    def supports_function_calling(self) -> bool:
        """
        是否支持函数调用

        Returns:
            True 表示支持
        """
        return True
