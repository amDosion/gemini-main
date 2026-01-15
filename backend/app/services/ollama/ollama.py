"""
Ollama Provider 协调者服务

架构v2.1 - 协调者模式:
- OpenAICompatibleHandler: OpenAI兼容API处理(/v1/*)
- NativeOllamaHandler: 原生Ollama API处理(/api/*)

使用委托模式，将所有请求分发到对应的子服务处理器。
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
from ..common.base_provider import BaseProviderService
from ..common.model_capabilities import ModelConfig
from .ollama_types import OllamaModelInfo
from ..common.errors import (
    ProviderError,
    OperationError,
    ErrorContext,
    ExecutionTimer,
    RequestIDManager
)

logger = logging.getLogger(__name__)


class OllamaService(BaseProviderService):
    """
    Ollama Provider 协调者服务
    
    统一协调所有 Ollama 子服务，使用委托模式分发请求：
    - OpenAICompatibleHandler: 处理聊天相关操作（/v1/*）
    - NativeOllamaHandler: 处理模型管理、向量化等操作（/api/*）
    """
    # OpenAI兼容API (默认保持向后兼容)
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    # 原生Ollama API (用于/api/show, /api/tags等)
    DEFAULT_NATIVE_BASE_URL = "http://localhost:11434"

    def __init__(self, api_key: str = "ollama", api_url: Optional[str] = None,
                 organization_id: Optional[str] = None, request_id: Optional[str] = None, **kwargs):
        """
        初始化 OllamaService 协调者
        
        Args:
            api_key: API 密钥
            api_url: API 地址
            organization_id: 组织 ID（未使用）
            request_id: 请求 ID（可选）
            **kwargs: 其他配置参数
                - client_selector: ClientSelector instance for dual-client mode (optional)
        """
        # 调用父类初始化
        super().__init__(api_key, api_url, **kwargs)
        
        self.organization_id = organization_id
        self.request_id = request_id or RequestIDManager.generate()
        self.client_selector = kwargs.get("client_selector")
        
        # 确定基础 URL
        openai_base_url = api_url or self.DEFAULT_BASE_URL
        if not openai_base_url.endswith("/v1"):
            openai_base_url = f"{openai_base_url.rstrip('/')}/v1"
        
        native_base_url = api_url or self.DEFAULT_NATIVE_BASE_URL
        if "/v1" in native_base_url:
            native_base_url = native_base_url.replace("/v1", "")
        native_base_url = native_base_url.rstrip("/")
        
        # 初始化子服务处理器（协调者模式）
        from .handlers.openai_compat_handler import OpenAICompatibleHandler
        from .handlers.native_handler import NativeOllamaHandler
        
        self.openai_handler = OpenAICompatibleHandler(api_key, openai_base_url, **kwargs)
        self.native_handler = NativeOllamaHandler(api_key, native_base_url, **kwargs)
        
        if self.client_selector:
            logger.info(
                f"[OllamaService] Initialized with ClientSelector: {self.client_selector.__class__.__name__}",
                extra={'request_id': self.request_id, 'operation': 'initialization'}
            )
        
        logger.info(
            f"[OllamaService] Coordinator initialized: OpenAI URL={openai_base_url}, Native URL={native_base_url}",
            extra={'request_id': self.request_id, 'operation': 'initialization'}
        )

    # ==================== 必需方法（BaseProviderService） ====================

    async def get_model_info(self, model: str, force_refresh: bool = False) -> OllamaModelInfo:
        """
        获取模型详细信息 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
            force_refresh: 强制刷新缓存
        
        Returns:
            OllamaModelInfo 对象
        """
        return await self.native_handler.get_model_info(model, force_refresh)

    async def chat(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> Dict[str, Any]:
        """
        同步聊天调用 - 委托给 OpenAICompatibleHandler
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
        
        Returns:
            聊天响应字典
        """
        return await self.openai_handler.chat(messages, model, **kwargs)

    async def stream_chat(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天调用 - 委托给 OpenAICompatibleHandler
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
        
        Yields:
            流式响应块
        """
        async for chunk in self.openai_handler.stream_chat(messages, model, **kwargs):
            yield chunk

    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表 - 委托给 NativeOllamaHandler
        
        Returns:
            ModelConfig 对象列表
        """
        from ..common.model_capabilities import ModelConfig, Capabilities
        
        try:
            models_data = await self.native_handler.get_available_models_detailed()
            result = []
            
            for model_data in models_data:
                name = model_data.get("name", "")
                if not name:
                    continue
                
                # 从模型详情中提取信息
                details = model_data.get("details", {})
                size = model_data.get("size", 0)
                
                # 推断能力
                lower_name = name.lower()
                vision = any(kw in lower_name for kw in ["vision", "llava", "bakllava", "moondream"])
                reasoning = any(kw in lower_name for kw in ["deepseek-r1", "qwq", "thinking"])
                coding = any(kw in lower_name for kw in ["code", "coder", "starcoder", "codellama"])
                
                # 构建描述
                family = details.get("family", "unknown")
                param_size = details.get("parameter_size", "")
                size_str = f"{size / (1024**3):.1f}GB" if size > 0 else ""
                description = f"Ollama {family}"
                if param_size:
                    description += f" {param_size}"
                if size_str:
                    description += f" ({size_str})"
                
                result.append(ModelConfig(
                    id=name,
                    name=name,
                    description=description,
                    capabilities=Capabilities(
                        vision=vision,
                        search=False,  # Ollama 模型通常不支持搜索
                        reasoning=reasoning,
                        coding=coding
                    ),
                    context_window=None  # 可以从 model_info 获取，但需要额外 API 调用
                ))
            
            return result
            
        except Exception as e:
            logger.warning(f"[OllamaService] Failed to get models: {e}")
            # 返回空列表而不是抛出异常
            return []

    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "Ollama"
    
    # ==================== 委托给 NativeOllamaHandler 的方法 ====================
    
    async def get_available_models_detailed(self) -> List[Dict[str, Any]]:
        """
        获取可用模型详细列表 - 委托给 NativeOllamaHandler
        
        Returns:
            模型详细列表
        """
        return await self.native_handler.get_available_models_detailed()
    
    async def get_running_models(self) -> List[Dict[str, Any]]:
        """
        获取当前运行中的模型列表 - 委托给 NativeOllamaHandler
        
        Returns:
            运行中的模型列表
        """
        return await self.native_handler.get_running_models()
    
    async def is_model_loaded(self, model: str) -> bool:
        """
        检查模型是否已加载到内存 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
        
        Returns:
            是否已加载
        """
        running = await self.native_handler.get_running_models()
        return any(m.get("name") == model for m in running)
    
    async def embed(
        self,
        texts: List[str],
        model: str = "all-minilm"
    ) -> List[List[float]]:
        """
        文本向量化 - 委托给 NativeOllamaHandler
        
        Args:
            texts: 要向量化的文本列表
            model: 向量化模型
        
        Returns:
            嵌入向量列表
        """
        return await self.native_handler.embed(texts, model)
    
    async def embed_single(self, text: str, model: str = "all-minilm") -> List[float]:
        """
        单文本向量化 - 委托给 NativeOllamaHandler
        
        Args:
            text: 文本
            model: 向量化模型
        
        Returns:
            嵌入向量
        """
        embeddings = await self.native_handler.embed([text], model)
        return embeddings[0] if embeddings else []
    
    async def get_embedding_models(self) -> List[str]:
        """
        获取可用的向量化模型列表 - 委托给 NativeOllamaHandler
        
        Returns:
            向量化模型列表
        """
        all_models = await self.native_handler.get_available_models_detailed()
        
        embedding_models = []
        for model in all_models:
            name = model.get("name", "").lower()
            if any(keyword in name for keyword in ["embed", "minilm", "nomic", "bge", "e5"]):
                embedding_models.append(model.get("name"))
        
        if not embedding_models:
            return ["all-minilm", "nomic-embed-text", "mxbai-embed-large"]
        
        return embedding_models
    
    # ==================== 动态能力检测方法 ====================
    
    async def supports_function_calling(self, model: str) -> bool:
        """
        检测模型是否支持工具调用 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
        
        Returns:
            是否支持工具调用
        """
        try:
            model_info = await self.native_handler.get_model_info(model)
            return model_info.capabilities.supports_tools if model_info.capabilities else False
        except Exception as e:
            logger.warning(f"[OllamaService] Failed to detect function calling support for {model}: {e}")
            return False
    
    async def supports_vision(self, model: str) -> bool:
        """
        检测模型是否支持视觉输入 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
        
        Returns:
            是否支持视觉
        """
        try:
            model_info = await self.native_handler.get_model_info(model)
            return model_info.capabilities.supports_vision if model_info.capabilities else False
        except Exception as e:
            logger.warning(f"[OllamaService] Failed to detect vision support for {model}: {e}")
            return False
    
    async def get_max_context_tokens(self, model: str) -> int:
        """
        获取模型最大上下文长度 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
        
        Returns:
            上下文长度
        """
        try:
            model_info = await self.native_handler.get_model_info(model)
            return model_info.capabilities.context_length if model_info.capabilities else 4096
        except Exception as e:
            logger.warning(f"[OllamaService] Failed to get context length for {model}: {e}")
            return 4096
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """计算成本（本地免费）"""
        return 0.0

    # ==================== 思考模型支持 ====================

    async def stream_chat_with_reasoning(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天并支持推理过程输出 - 委托给 OpenAICompatibleHandler（带特殊处理）
        
        对于支持thinking的模型，会分别输出:
        - reasoning: 推理过程
        - content: 最终回答
        
        Yields:
            流式响应块，包含chunk_type区分reasoning和content
        """
        # 使用 OpenAICompatibleHandler 的流式聊天，但需要检测思考标记
        in_reasoning = False
        
        async for chunk in self.openai_handler.stream_chat(messages, model, **kwargs):
            if chunk.get("chunk_type") == "content":
                content = chunk.get("content", "")
                
                # 检测思考标记
                if "<think>" in content:
                    in_reasoning = True
                    content = content.replace("<think>", "")
                elif "</think>" in content:
                    in_reasoning = False
                    content = content.replace("</think>", "")
                
                if content:
                    yield {
                        **chunk,
                        "chunk_type": "reasoning" if in_reasoning else "content",
                        "content": content
                    }
            else:
                yield chunk

    async def supports_thinking(self, model: str) -> bool:
        """
        检测模型是否支持思考模式 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
        
        Returns:
            是否支持思考模式
        """
        try:
            model_info = await self.native_handler.get_model_info(model)
            return model_info.capabilities.supports_thinking if model_info.capabilities else False
        except Exception as e:
            logger.warning(f"[OllamaService] Failed to detect thinking support for {model}: {e}")
            return False
    
    # ==================== 高级功能（委托给 NativeOllamaHandler） ====================
    
    async def pull_model(
        self,
        model: str,
        insecure: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        拉取/下载模型（流式进度输出）- 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
            insecure: 是否允许不安全的连接
        
        Yields:
            进度更新字典
        """
        async for progress in self.native_handler.pull_model(model, insecure):
            yield progress
    
    async def delete_model(self, model: str) -> bool:
        """
        删除本地模型 - 委托给 NativeOllamaHandler
        
        Args:
            model: 模型名称
        
        Returns:
            是否成功
        """
        return await self.native_handler.delete_model(model)
    
    async def copy_model(self, source: str, destination: str) -> bool:
        """
        复制模型（创建别名）- 委托给 NativeOllamaHandler
        
        Args:
            source: 源模型名称
            destination: 目标模型名称
        
        Returns:
            是否成功
        """
        return await self.native_handler.copy_model(source, destination)
    
    async def generate_with_options(
        self,
        prompt: str,
        model: str,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        使用高级选项生成文本 - 委托给 NativeOllamaHandler
        
        Args:
            prompt: 提示词
            model: 模型名称
            options: 高级选项
            **kwargs: 额外参数
        
        Returns:
            生成的文本
        """
        return await self.native_handler.generate_with_options(prompt, model, options, **kwargs)
    
    # ==================== 资源清理 ====================
    
    async def close(self):
        """关闭所有子服务处理器"""
        await self.native_handler.close()
        logger.debug("[OllamaService] All handlers closed")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
