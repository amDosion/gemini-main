"""
Ollama本地模型服务实现

架构v2.0 - 双API支持:
- OpenAI兼容API: 通用聊天功能(保持向后兼容)
- 原生Ollama API: 高级功能(能力检测、工具调用、视觉、向量化)

设计决策:
1. 保留AsyncOpenAI客户端用于基础聊天(无需重写)
2. 新增httpx客户端用于原生API调用(/api/show, /api/tags等)
3. 动态能力检测替代硬编码(从/api/show获取capabilities数组)
4. TTLCache缓存模型信息(避免重复API调用)

重构说明(2026-01-02):
- 继承 BaseProviderService 以符合统一后端架构
- 保留所有现有功能(embedding, model management, thinking support)
- 维持双API架构(OpenAI兼容 + 原生Ollama)
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
import httpx
import logging
import tiktoken
from cachetools import TTLCache
from ..base_provider import BaseProviderService
from .ollama_types import (
    OllamaAPIMode,
    OllamaModelCapabilities,
    OllamaModelInfo,
    OllamaToolCallState
)

logger = logging.getLogger(__name__)


# ==================== 异常类定义 ====================

class AIServiceError(Exception):
    """AI 服务基础异常"""
    def __init__(self, message: str, provider: str = "Ollama"):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class APIKeyError(AIServiceError):
    """API Key 无效或缺失"""
    pass


class RateLimitError(AIServiceError):
    """请求频率超限"""
    pass


class ModelNotFoundError(AIServiceError):
    """模型不存在"""
    pass


class InvalidRequestError(AIServiceError):
    """请求参数无效"""
    pass


class OllamaService(BaseProviderService):
    """
    Ollama服务提供商 - 双API架构
    继承自 BaseProviderService，实现统一的后端服务接口

    API Modes:
    - OpenAI兼容模式 (/v1/*): 用于基础聊天(复用AsyncOpenAI)
    - 原生Ollama模式 (/api/*): 用于高级功能(能力检测、模型管理)
    """
    # OpenAI兼容API (默认保持向后兼容)
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    # 原生Ollama API (用于/api/show, /api/tags等)
    DEFAULT_NATIVE_BASE_URL = "http://localhost:11434"

    # 模型信息缓存配置
    CACHE_MAX_SIZE = 100  # 最多缓存100个模型
    CACHE_TTL_SECONDS = 3600  # 1小时过期

    def __init__(self, api_key: str = "ollama", api_url: Optional[str] = None,
                 organization_id: Optional[str] = None, **kwargs):
        """
        初始化Ollama服务

        Args:
            api_key: API密钥(本地可用占位符,远程服务需配置真实密钥)
            api_url: API地址(默认localhost:11434)
            organization_id: 组织ID(未使用)
            **kwargs: 其他配置参数
        """
        # 调用父类初始化
        super().__init__(api_key, api_url, **kwargs)
        
        self.organization_id = organization_id

        # 1. OpenAI兼容客户端(保持现有实现)
        openai_base_url = api_url or self.DEFAULT_BASE_URL
        if not openai_base_url.endswith("/v1"):
            openai_base_url = f"{openai_base_url.rstrip('/')}/v1"

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=openai_base_url,
            timeout=kwargs.get("timeout", 120.0)
        )

        # 2. 原生Ollama API客户端(新增)
        native_base_url = api_url or self.DEFAULT_NATIVE_BASE_URL
        if "/v1" in native_base_url:
            # 如果传入OpenAI兼容URL,转换为原生URL
            native_base_url = native_base_url.replace("/v1", "")

        # 构建认证头(支持远程Ollama服务)
        headers = {}
        if api_key and api_key != "ollama":
            headers["Authorization"] = f"Bearer {api_key}"

        self.native_client = httpx.AsyncClient(
            base_url=native_base_url.rstrip("/"),
            headers=headers,
            timeout=kwargs.get("timeout", 120.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            )
        )

        # 3. 模型信息缓存(TTLCache)
        self._model_cache: TTLCache = TTLCache(
            maxsize=self.CACHE_MAX_SIZE,
            ttl=self.CACHE_TTL_SECONDS
        )

        # 4. Token估算器(延迟加载)
        self.encoding = None

        logger.info(f"[Ollama] Initialized with OpenAI URL: {openai_base_url}, Native URL: {native_base_url}")

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

    # ==================== 原生API辅助方法 ====================

    async def _call_native_api(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用原生Ollama API的通用方法

        Args:
            method: HTTP方法 (GET, POST, DELETE等)
            endpoint: API端点路径 (如 /api/show, /api/tags)
            **kwargs: httpx请求参数 (json, params等)

        Returns:
            API响应JSON

        Raises:
            AIServiceError: API调用失败
        """
        try:
            response = await self.native_client.request(
                method=method,
                url=endpoint,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            error_msg = f"Native API call failed: {e.response.status_code} - {e.response.text}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

        except Exception as e:
            error_msg = f"Native API call error: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

    async def get_model_info(self, model: str, force_refresh: bool = False) -> OllamaModelInfo:
        """
        获取模型详细信息 (支持缓存)

        调用 /api/show 获取模型元数据和能力信息
        结果会缓存在TTLCache中(默认1小时)

        Args:
            model: 模型名称 (如 llama3.2:latest)
            force_refresh: 强制刷新缓存

        Returns:
            OllamaModelInfo: 包含模型详情和能力信息

        Raises:
            AIServiceError: 模型不存在或API调用失败
        """
        # 检查缓存
        if not force_refresh and model in self._model_cache:
            cached_info: OllamaModelInfo = self._model_cache[model]
            if cached_info.capabilities and not cached_info.capabilities.is_expired():
                logger.debug(f"[Ollama] Using cached model info for {model}")
                return cached_info

        # 调用 /api/show
        logger.info(f"[Ollama] Fetching model info for {model}")
        response_data = await self._call_native_api(
            method="POST",
            endpoint="/api/show",
            json={"name": model}
        )

        # 解析为 OllamaModelInfo
        model_info = OllamaModelInfo.from_api_response(response_data)

        # 缓存结果
        self._model_cache[model] = model_info
        logger.info(
            f"[Ollama] Model {model} capabilities: "
            f"tools={model_info.capabilities.supports_tools}, "
            f"vision={model_info.capabilities.supports_vision}, "
            f"context={model_info.capabilities.context_length}"
        )

        return model_info

    # ==================== 标准聊天接口 ====================

    async def chat(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> Dict[str, Any]:
        """
        同步聊天调用

        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数

        Returns:
            ChatResponse格式字典:
            {
                "content": str,
                "role": str,
                "usage": {...},
                "model": str,
                "finish_reason": str
            }
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            choice = response.choices[0]
            usage = response.usage or type('obj', (object,), {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            })()

            return {
                "content": choice.message.content or "",
                "role": "assistant",
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                },
                "model": response.model,
                "finish_reason": choice.finish_reason,
                "cost": 0.0  # 本地免费
            }
        except Exception as e:
            raise AIServiceError(f"Ollama调用失败: {e}")

    async def stream_chat(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天调用

        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数

        Yields:
            StreamChunk格式字典:
            {
                "content": str,
                "chunk_type": str,  # "content", "done"
                "finish_reason": Optional[str],
                "prompt_tokens": Optional[int],
                "completion_tokens": Optional[int],
                "total_tokens": Optional[int]
            }
        """
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs
            )
            # 跟踪 usage 信息
            usage = None
            model_name = model
            completion_text = ""

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # 捕获 usage 信息（在最后一个 chunk 中）
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = chunk.usage
                    logger.info(f"[Ollama] Got usage info: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")

                # 捕获实际使用的模型名
                if hasattr(chunk, 'model') and chunk.model:
                    model_name = chunk.model

                # Yield content chunk
                if delta.content:
                    completion_text += delta.content
                    yield {
                        "content": delta.content,
                        "chunk_type": "content",
                        "model": chunk.model
                    }

            # 在流结束时 yield done chunk
            if usage:
                cost = self.calculate_cost(
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    model_name
                )
                yield {
                    "content": "",
                    "chunk_type": "done",
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": cost,
                    "finish_reason": "stop"
                }
            else:
                # API 不返回 usage 信息，使用 tiktoken 估算
                logger.warning(f"[Ollama] No usage information received from API, using tiktoken to estimate tokens")

                prompt_tokens = self._estimate_tokens(messages, model_name)
                encoding = self._get_encoding(model_name)
                completion_tokens = len(encoding.encode(completion_text)) if completion_text else 0

                total_tokens = prompt_tokens + completion_tokens
                cost = self.calculate_cost(prompt_tokens, completion_tokens, model_name)

                logger.info(f"[Ollama] Estimated tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}, cost={cost:.6f}")

                yield {
                    "content": "",
                    "chunk_type": "done",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost": cost,
                    "finish_reason": "stop"
                }

        except Exception as e:
            raise AIServiceError(f"Ollama流式调用失败: {e}")

    async def get_available_models(self) -> List["ModelConfig"]:
        """
        获取可用模型列表（返回 ModelConfig 对象）

        Returns:
            List[ModelConfig]: 模型配置列表
        """
        from ..model_capabilities import ModelConfig, Capabilities
        
        try:
            models_data = await self.get_available_models_detailed()
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
            logger.warning(f"[Ollama] Failed to get models: {e}")
            # 返回空列表而不是抛出异常
            return []

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """计算成本（本地免费）"""
        return 0.0

    # ==================== 动态能力检测方法 ====================

    async def supports_function_calling(self, model: str) -> bool:
        """检测模型是否支持工具调用"""
        try:
            model_info = await self.get_model_info(model)
            return model_info.capabilities.supports_tools if model_info.capabilities else False
        except Exception as e:
            logger.warning(f"[Ollama] Failed to detect function calling support for {model}: {e}")
            return False

    async def supports_vision(self, model: str) -> bool:
        """检测模型是否支持视觉输入"""
        try:
            model_info = await self.get_model_info(model)
            return model_info.capabilities.supports_vision if model_info.capabilities else False
        except Exception as e:
            logger.warning(f"[Ollama] Failed to detect vision support for {model}: {e}")
            return False

    async def get_max_context_tokens(self, model: str) -> int:
        """获取模型最大上下文长度"""
        try:
            model_info = await self.get_model_info(model)
            return model_info.capabilities.context_length if model_info.capabilities else 4096
        except Exception as e:
            logger.warning(f"[Ollama] Failed to get context length for {model}: {e}")
            return 4096

    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "Ollama"

    # ==================== 向量化功能 ====================

    async def embed(
        self,
        texts: List[str],
        model: str = "all-minilm"
    ) -> List[List[float]]:
        """
        文本向量化 (调用原生 /api/embed)

        Args:
            texts: 要向量化的文本列表
            model: 向量化模型

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        logger.info(f"[Ollama] Embedding {len(texts)} texts with model {model}")

        try:
            response = await self._call_native_api(
                method="POST",
                endpoint="/api/embed",
                json={
                    "model": model,
                    "input": texts
                }
            )

            embeddings = response.get("embeddings", [])
            logger.info(f"[Ollama] Generated {len(embeddings)} embeddings, dimension: {len(embeddings[0]) if embeddings else 0}")
            return embeddings

        except Exception as e:
            error_msg = f"Embedding failed: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

    async def embed_single(self, text: str, model: str = "all-minilm") -> List[float]:
        """单文本向量化"""
        embeddings = await self.embed([text], model)
        return embeddings[0] if embeddings else []

    async def get_embedding_models(self) -> List[str]:
        """获取可用的向量化模型列表"""
        all_models = await self.get_available_models_detailed()

        embedding_models = []
        for model in all_models:
            name = model.get("name", "").lower()
            if any(keyword in name for keyword in ["embed", "minilm", "nomic", "bge", "e5"]):
                embedding_models.append(model.get("name"))

        if not embedding_models:
            return ["all-minilm", "nomic-embed-text", "mxbai-embed-large"]

        return embedding_models

    # ==================== 模型管理功能 ====================

    async def get_available_models_detailed(self) -> List[Dict[str, Any]]:
        """获取可用模型详细列表 (调用原生 /api/tags)"""
        try:
            response = await self._call_native_api(
                method="GET",
                endpoint="/api/tags"
            )

            models = response.get("models", [])
            logger.info(f"[Ollama] Found {len(models)} available models")
            return models

        except Exception as e:
            logger.warning(f"[Ollama] Failed to get models list: {e}")
            return []

    async def get_running_models(self) -> List[Dict[str, Any]]:
        """获取当前运行中的模型列表 (调用 /api/ps)"""
        try:
            response = await self._call_native_api(
                method="GET",
                endpoint="/api/ps"
            )

            models = response.get("models", [])
            logger.info(f"[Ollama] Found {len(models)} running models")
            return models

        except Exception as e:
            logger.warning(f"[Ollama] Failed to get running models: {e}")
            return []

    async def is_model_loaded(self, model: str) -> bool:
        """检查模型是否已加载到内存"""
        running = await self.get_running_models()
        return any(m.get("name") == model for m in running)

    # ==================== 思考模型支持 ====================

    async def stream_chat_with_reasoning(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天并支持推理过程输出

        对于支持thinking的模型，会分别输出:
        - reasoning: 推理过程
        - content: 最终回答

        Yields:
            StreamChunk格式字典，包含chunk_type区分reasoning和content
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
            in_reasoning = False

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = chunk.usage

                if hasattr(chunk, 'model') and chunk.model:
                    model_name = chunk.model

                content = delta.content or ""

                # 检测思考标记
                if "<think>" in content:
                    in_reasoning = True
                    content = content.replace("<think>", "")
                elif "</think>" in content:
                    in_reasoning = False
                    content = content.replace("</think>", "")

                if content:
                    yield {
                        "content": content,
                        "chunk_type": "reasoning" if in_reasoning else "content",
                        "model": chunk.model
                    }

            # Done chunk
            if usage:
                cost = self.calculate_cost(
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    model_name
                )
                yield {
                    "content": "",
                    "chunk_type": "done",
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": cost,
                    "finish_reason": "stop"
                }

        except Exception as e:
            raise AIServiceError(f"Ollama reasoning stream failed: {e}")

    async def supports_thinking(self, model: str) -> bool:
        """检测模型是否支持思考模式"""
        try:
            model_info = await self.get_model_info(model)
            return model_info.capabilities.supports_thinking if model_info.capabilities else False
        except Exception as e:
            logger.warning(f"[Ollama] Failed to detect thinking support for {model}: {e}")
            return False

    # ==================== 高级功能 ====================

    async def pull_model(
        self,
        model: str,
        insecure: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """拉取/下载模型 (流式进度输出)"""
        logger.info(f"[Ollama] Pulling model: {model}")

        try:
            async with self.native_client.stream(
                "POST",
                "/api/pull",
                json={"name": model, "insecure": insecure},
                timeout=None
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            yield data

                            if "completed" in data and "total" in data:
                                percent = (data["completed"] / data["total"] * 100) if data["total"] > 0 else 0
                                logger.debug(f"[Ollama] Pull progress: {percent:.1f}%")

                        except json.JSONDecodeError:
                            continue

            logger.info(f"[Ollama] Model {model} pulled successfully")

        except Exception as e:
            error_msg = f"Failed to pull model {model}: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

    async def delete_model(self, model: str) -> bool:
        """删除本地模型"""
        logger.info(f"[Ollama] Deleting model: {model}")

        try:
            await self._call_native_api(
                method="DELETE",
                endpoint="/api/delete",
                json={"name": model}
            )

            if model in self._model_cache:
                del self._model_cache[model]

            logger.info(f"[Ollama] Model {model} deleted successfully")
            return True

        except Exception as e:
            error_msg = f"Failed to delete model {model}: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

    async def copy_model(self, source: str, destination: str) -> bool:
        """复制模型 (创建别名)"""
        logger.info(f"[Ollama] Copying model: {source} -> {destination}")

        try:
            await self._call_native_api(
                method="POST",
                endpoint="/api/copy",
                json={
                    "source": source,
                    "destination": destination
                }
            )

            logger.info(f"[Ollama] Model copied successfully: {destination}")
            return True

        except Exception as e:
            error_msg = f"Failed to copy model {source} to {destination}: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

    async def generate_with_options(
        self,
        prompt: str,
        model: str,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """使用高级选项生成文本 (调用原生 /api/generate)"""
        logger.info(f"[Ollama] Generate with options for model {model}")

        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        if options:
            request_data["options"] = options

        try:
            response = await self._call_native_api(
                method="POST",
                endpoint="/api/generate",
                json=request_data
            )

            return response.get("response", "")

        except Exception as e:
            error_msg = f"Generate with options failed: {str(e)}"
            logger.error(f"[Ollama] {error_msg}")
            raise AIServiceError(error_msg)

    # ==================== 资源清理 ====================

    async def close(self):
        """关闭HTTP客户端连接"""
        if hasattr(self, 'native_client'):
            await self.native_client.aclose()
            logger.debug("[Ollama] Native client closed")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
