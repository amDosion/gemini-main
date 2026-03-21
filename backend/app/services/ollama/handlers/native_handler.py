"""
Ollama 原生 API 处理器

处理 Ollama 原生 API 调用（/api/* 端点）。
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
import httpx
from cachetools import TTLCache

from ...common.errors import (
    OperationError,
    ErrorContext,
    ExecutionTimer
)
from ..ollama_types import OllamaModelInfo

logger = logging.getLogger(__name__)


class NativeOllamaHandler:
    """
    Ollama 原生 API 处理器
    
    负责处理所有原生 Ollama API 调用。
    """
    
    # 模型信息缓存配置
    CACHE_MAX_SIZE = 100
    CACHE_TTL_SECONDS = 3600
    
    def __init__(self, api_key: str, base_url: str, **kwargs):
        """
        初始化原生 API 处理器
        
        Args:
            api_key: API 密钥
            base_url: 原生 API 基础 URL（不包含 /v1）
            **kwargs: 额外参数
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        
        # 构建认证头
        headers = {}
        if api_key and api_key != "ollama":
            headers["Authorization"] = f"Bearer {api_key}"
        
        # 创建 httpx 客户端
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=kwargs.get("timeout", 120.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            )
        )
        
        # 模型信息缓存
        self._model_cache: TTLCache = TTLCache(
            maxsize=self.CACHE_MAX_SIZE,
            ttl=self.CACHE_TTL_SECONDS
        )
        
        logger.info(f"[Ollama NativeHandler] Initialized with base_url={self.base_url}")
    
    async def _call_api(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用原生 Ollama API 的通用方法
        
        Args:
            method: HTTP 方法
            endpoint: API 端点路径
            **kwargs: httpx 请求参数
        
        Returns:
            API 响应 JSON
        """
        timer = ExecutionTimer()
        
        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        
        except httpx.HTTPStatusError as e:
            context = ErrorContext(
                provider_id="ollama",
                client_type="secondary",
                operation="native_api_call",
                execution_time_ms=timer.elapsed_ms,
                additional_context={
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": e.response.status_code
                }
            )
            raise OperationError(
                message=f"Native API call failed: {e.response.status_code} - {e.response.text}",
                context=context,
                original_error=e,
                recoverable=True
            )
        
        except Exception as e:
            context = ErrorContext(
                provider_id="ollama",
                client_type="secondary",
                operation="native_api_call",
                execution_time_ms=timer.elapsed_ms,
                additional_context={
                    "method": method,
                    "endpoint": endpoint
                }
            )
            raise OperationError(
                message=f"Native API call error: {str(e)}",
                context=context,
                original_error=e,
                recoverable=True
            )
    
    async def get_model_info(self, model: str, force_refresh: bool = False) -> OllamaModelInfo:
        """
        获取模型详细信息（支持缓存）
        
        Args:
            model: 模型名称
            force_refresh: 强制刷新缓存
        
        Returns:
            OllamaModelInfo 对象
        """
        # 检查缓存
        if not force_refresh and model in self._model_cache:
            cached_info: OllamaModelInfo = self._model_cache[model]
            if cached_info.capabilities and not cached_info.capabilities.is_expired():
                logger.debug(f"[Ollama NativeHandler] Using cached model info for {model}")
                return cached_info
        
        # 调用 /api/show
        logger.info(f"[Ollama NativeHandler] Fetching model info for {model}")
        response_data = await self._call_api(
            method="POST",
            endpoint="/api/show",
            json={"name": model}
        )
        
        # 解析为 OllamaModelInfo
        model_info = OllamaModelInfo.from_api_response(response_data)
        
        # 缓存结果
        self._model_cache[model] = model_info
        return model_info
    
    async def get_available_models_detailed(self) -> List[Dict[str, Any]]:
        """
        获取可用模型详细列表（调用 /api/tags）
        
        Returns:
            模型列表
        """
        response = await self._call_api(
            method="GET",
            endpoint="/api/tags"
        )
        return response.get("models", [])
    
    async def get_running_models(self) -> List[Dict[str, Any]]:
        """
        获取当前运行中的模型列表（调用 /api/ps）
        
        Returns:
            运行中的模型列表
        """
        response = await self._call_api(
            method="GET",
            endpoint="/api/ps"
        )
        return response.get("models", [])
    
    async def embed(
        self,
        texts: List[str],
        model: str = "all-minilm"
    ) -> List[List[float]]:
        """
        文本向量化（调用 /api/embed）
        
        Args:
            texts: 要向量化的文本列表
            model: 向量化模型
        
        Returns:
            嵌入向量列表
        """
        if not texts:
            return []
        
        logger.info(f"[Ollama NativeHandler] Embedding {len(texts)} texts with model {model}")
        
        response = await self._call_api(
            method="POST",
            endpoint="/api/embed",
            json={
                "model": model,
                "input": texts
            }
        )
        
        embeddings = response.get("embeddings", [])
        logger.info(f"[Ollama NativeHandler] Generated {len(embeddings)} embeddings")
        return embeddings
    
    async def pull_model(
        self,
        model: str,
        insecure: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        拉取/下载模型（流式进度输出）
        
        Args:
            model: 模型名称
            insecure: 是否允许不安全的连接
        
        Yields:
            进度更新字典
        """
        logger.info(f"[Ollama NativeHandler] Pulling model: {model}")
        
        async with self.client.stream(
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
                    except json.JSONDecodeError:
                        continue
        
        logger.info(f"[Ollama NativeHandler] Model {model} pulled successfully")
    
    async def delete_model(self, model: str) -> bool:
        """
        删除本地模型
        
        Args:
            model: 模型名称
        
        Returns:
            是否成功
        """
        logger.info(f"[Ollama NativeHandler] Deleting model: {model}")
        
        await self._call_api(
            method="DELETE",
            endpoint="/api/delete",
            json={"name": model}
        )
        
        # 清除缓存
        if model in self._model_cache:
            del self._model_cache[model]
        
        logger.info(f"[Ollama NativeHandler] Model {model} deleted successfully")
        return True
    
    async def copy_model(self, source: str, destination: str) -> bool:
        """
        复制模型（创建别名）
        
        Args:
            source: 源模型名称
            destination: 目标模型名称
        
        Returns:
            是否成功
        """
        logger.info(f"[Ollama NativeHandler] Copying model: {source} -> {destination}")
        
        await self._call_api(
            method="POST",
            endpoint="/api/copy",
            json={
                "source": source,
                "destination": destination
            }
        )
        
        logger.info(f"[Ollama NativeHandler] Model copied successfully: {destination}")
        return True
    
    async def pull_model(
        self,
        model: str,
        insecure: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        拉取/下载模型（流式进度输出）
        
        Args:
            model: 模型名称
            insecure: 是否允许不安全的连接
        
        Yields:
            进度更新字典
        """
        logger.info(f"[Ollama NativeHandler] Pulling model: {model}")
        
        async with self.client.stream(
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
                            logger.debug(f"[Ollama NativeHandler] Pull progress: {percent:.1f}%")
                    except json.JSONDecodeError:
                        continue
        
        logger.info(f"[Ollama NativeHandler] Model {model} pulled successfully")
    
    async def generate_with_options(
        self,
        prompt: str,
        model: str,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        使用高级选项生成文本（调用原生 /api/generate）
        
        Args:
            prompt: 提示词
            model: 模型名称
            options: 高级选项
            **kwargs: 额外参数
        
        Returns:
            生成的文本
        """
        logger.info(f"[Ollama NativeHandler] Generate with options for model {model}")
        
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        if options:
            request_data["options"] = options
        
        response = await self._call_api(
            method="POST",
            endpoint="/api/generate",
            json=request_data
        )
        
        return response.get("response", "")
    
    async def close(self):
        """关闭 HTTP 客户端连接"""
        await self.client.aclose()
        logger.debug("[Ollama NativeHandler] Client closed")
