"""
Gemini Client Pool Manager

统一管理所有 Gemini Client 实例，提供自动缓存、复用和生命周期管理。

设计参考：
- client_selector.py 的单例模式
- 线程安全的实现
- 统一的缓存策略

Usage:
    pool = get_client_pool()
    client = pool.get_client(api_key="xxx", vertexai=False)
    response = client.models.generate_content(...)
"""

import threading
import logging
from typing import Dict, Optional, Any, Union
from datetime import datetime

from .agent import Client as VertexAIClient
from .agent.types import HttpOptions, HttpOptionsDict

logger = logging.getLogger(__name__)


class GeminiClientPool:
    """
    统一的 Gemini Client 池管理器（单例模式）

    职责：
    1. 管理所有 Client 实例的生命周期
    2. 基于配置自动缓存和复用
    3. 提供线程安全的访问接口
    4. 统计和监控客户端使用情况

    线程安全：是
    单例模式：是
    """

    _instance: Optional['GeminiClientPool'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化（只执行一次）"""
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._clients: Dict[str, Any] = {}  # 可以是 VertexAIClient 或 google.genai.Client
        self._client_metadata: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            'total_clients': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self._initialized = True

        logger.info("[GeminiClientPool] Client pool initialized")

    def get_client(
        self,
        api_key: Optional[str] = None,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None,
        credentials = None,  # Service account credentials (for Vertex AI)
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> Any:
        """
        获取或创建 Client 实例（带缓存）
        
        架构分离：
        - Gemini API 模式 (vertexai=False): 使用 genai_agent/client.py 的 get_genai_client()
        - Vertex AI 模式 (vertexai=True): 使用 agent/client.py 的 Client 类

        Args:
            api_key: Google API key (optional if credentials provided)
            vertexai: 是否使用 Vertex AI
            project: GCP 项目 ID（Vertex AI 需要）
            location: GCP 区域（Vertex AI 需要）
            credentials: Service account credentials (for Vertex AI ADC mode)
            http_options: HTTP 配置（可选）

        Returns:
            Client 实例（可能从缓存返回）
            - Gemini API 模式: google.genai.Client
            - Vertex AI 模式: VertexAIClient (包装器)

        Thread-safe: 是
        """
        cache_key = self._generate_cache_key(api_key, vertexai, project, location, credentials)

        # 快速路径：缓存命中（不需要锁）
        if cache_key in self._clients:
            self._stats['cache_hits'] += 1
            logger.debug(
                f"[GeminiClientPool] Cache hit for {cache_key}",
                extra={'cache_key': cache_key, 'total_hits': self._stats['cache_hits']}
            )
            return self._clients[cache_key]

        # 慢速路径：需要创建（使用锁）
        with self._lock:
            # 双重检查（其他线程可能已创建）
            if cache_key in self._clients:
                self._stats['cache_hits'] += 1
                return self._clients[cache_key]

            # 创建新客户端（根据 vertexai 标志选择不同的实现）
            try:
                if vertexai:
                    # ✅ Vertex AI 模式：使用 agent/client.py 的 Client 类
                    logger.debug(f"[GeminiClientPool] Creating Vertex AI client (vertexai=True)")
                    client = VertexAIClient(
                        api_key=api_key,
                        vertexai=True,
                        project=project,
                        location=location,
                        credentials=credentials,
                        http_options=http_options
                    )
                else:
                    # ✅ Gemini API 模式：使用 genai_agent/client.py 的 get_genai_client()
                    logger.debug(f"[GeminiClientPool] Creating Gemini API client (vertexai=False)")
                    if not api_key:
                        raise ValueError(
                            "api_key is required for Gemini API mode (vertexai=False)"
                        )
                    from .genai_agent.client import get_genai_client
                    client = get_genai_client(api_key=api_key)

                self._clients[cache_key] = client
                self._client_metadata[cache_key] = {
                    'created_at': datetime.now().isoformat(),
                    'api_key_prefix': api_key[:8] if api_key else 'none',
                    'vertexai': vertexai,
                    'project': project,
                    'location': location,
                    'client_type': 'VertexAI' if vertexai else 'GeminiAPI'
                }

                self._stats['cache_misses'] += 1
                self._stats['total_clients'] += 1

                logger.info(
                    f"[GeminiClientPool] Created new client: {cache_key} (mode={'VertexAI' if vertexai else 'GeminiAPI'})",
                    extra={
                        'cache_key': cache_key,
                        'vertexai': vertexai,
                        'total_clients': self._stats['total_clients']
                    }
                )

                return client

            except Exception as e:
                logger.error(
                    f"[GeminiClientPool] Failed to create client: {e}",
                    extra={'cache_key': cache_key, 'error': str(e), 'vertexai': vertexai}
                )
                raise

    def close_client(self, cache_key: str) -> bool:
        """
        关闭并移除指定的客户端

        Args:
            cache_key: 客户端缓存键

        Returns:
            是否成功关闭
        """
        with self._lock:
            if cache_key not in self._clients:
                logger.warning(
                    f"[GeminiClientPool] Client not found: {cache_key}",
                    extra={'cache_key': cache_key}
                )
                return False

            try:
                client = self._clients[cache_key]
                if hasattr(client, 'close'):
                    client.close()

                del self._clients[cache_key]
                if cache_key in self._client_metadata:
                    del self._client_metadata[cache_key]

                logger.info(
                    f"[GeminiClientPool] Closed client: {cache_key}",
                    extra={'cache_key': cache_key}
                )
                return True

            except Exception as e:
                logger.error(
                    f"[GeminiClientPool] Failed to close client: {e}",
                    extra={'cache_key': cache_key, 'error': str(e)}
                )
                return False

    def close_all(self) -> int:
        """
        关闭所有客户端（清理资源）

        Returns:
            关闭的客户端数量
        """
        with self._lock:
            count = 0
            for cache_key, client in list(self._clients.items()):
                try:
                    if hasattr(client, 'close'):
                        client.close()
                    count += 1
                except Exception as e:
                    logger.error(
                        f"[GeminiClientPool] Failed to close client {cache_key}: {e}"
                    )

            self._clients.clear()
            self._client_metadata.clear()

            logger.info(
                f"[GeminiClientPool] Closed all clients",
                extra={'closed_count': count}
            )
            return count

    def list_clients(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有客户端及其元数据

        Returns:
            {cache_key: metadata}
        """
        return dict(self._client_metadata)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取客户端池统计信息

        Returns:
            统计信息字典
        """
        total_requests = self._stats['cache_hits'] + self._stats['cache_misses']
        hit_rate = (
            self._stats['cache_hits'] / total_requests
            if total_requests > 0 else 0.0
        )

        return {
            'total_clients': self._stats['total_clients'],
            'active_clients': len(self._clients),
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 4),
            'clients': self.list_clients()
        }

    def _generate_cache_key(
        self,
        api_key: Optional[str],
        vertexai: bool,
        project: Optional[str],
        location: Optional[str],
        credentials = None
    ) -> str:
        """
        生成缓存键

        策略：
        - Vertex AI: vertex:{project}:{location}:{api_key[:8] or 'cred'}
        - Gemini API: gemini:{api_key[:8]}

        Args:
            api_key: API key (optional if credentials provided)
            vertexai: 是否 Vertex AI
            project: 项目 ID
            location: 区域
            credentials: Service account credentials

        Returns:
            缓存键字符串
        """
        if credentials:
            # 如果有 credentials，使用 'cred' 作为标识
            cred_id = 'cred'
        else:
            cred_id = api_key[:8] if api_key else 'none'

        if vertexai:
            return f"vertex:{project}:{location}:{cred_id}"
        else:
            return f"gemini:{cred_id}"


# ==================== 全局单例访问 ====================

_global_pool: Optional[GeminiClientPool] = None
_global_pool_lock = threading.Lock()


def get_client_pool() -> GeminiClientPool:
    """
    获取全局客户端池实例（单例）

    Returns:
        GeminiClientPool 实例

    Thread-safe: 是

    Usage:
        pool = get_client_pool()
        client = pool.get_client(api_key="xxx")
    """
    global _global_pool

    if _global_pool is None:
        with _global_pool_lock:
            if _global_pool is None:
                _global_pool = GeminiClientPool()

    return _global_pool
