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
import hashlib
import os
from typing import Dict, Optional, Any, Union
from datetime import datetime

from .agent.client import Client as VertexAIClient
from .agent.types import HttpOptions, HttpOptionsDict, HttpRetryOptions

logger = logging.getLogger(__name__)

try:
    from google import genai as google_genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    google_genai = None
    GOOGLE_GENAI_AVAILABLE = False


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
        self._default_http_options = self._build_default_http_options()
        self._initialized = True

        logger.info(
            "[GeminiClientPool] Client pool initialized with HTTP defaults: "
            f"timeout={self._default_http_options.timeout}, "
            f"retry_attempts={getattr(self._default_http_options.retry_options, 'attempts', None)}"
        )

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
        - Gemini API 模式 (vertexai=False): 使用官方 google.genai.Client
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
        effective_http_options = self._normalize_http_options(http_options)
        cache_key = self._generate_cache_key(
            api_key,
            vertexai,
            project,
            location,
            credentials,
            http_options=effective_http_options,
        )

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
                        http_options=effective_http_options
                    )
                else:
                    # ✅ Gemini API 模式：统一在主池内创建官方 google.genai.Client
                    logger.debug(f"[GeminiClientPool] Creating Gemini API client (vertexai=False)")
                    if not api_key:
                        raise ValueError(
                            "api_key is required for Gemini API mode (vertexai=False)"
                        )
                    if not GOOGLE_GENAI_AVAILABLE:
                        raise RuntimeError(
                            "google-genai SDK is not available. "
                            "Please install: pip install google-genai>=1.55.0"
                        )
                    # 显式指定 vertexai=False，避免环境变量导致模式串扰
                    client_kwargs = {
                        "vertexai": False,
                        "api_key": api_key,
                    }
                    genai_http_options = self._to_genai_http_options(effective_http_options)
                    if genai_http_options is not None:
                        client_kwargs["http_options"] = genai_http_options
                    client = google_genai.Client(**client_kwargs)

                self._clients[cache_key] = client
                self._client_metadata[cache_key] = {
                    'created_at': datetime.now().isoformat(),
                    'api_key_prefix': api_key[:8] if api_key else 'none',
                    'vertexai': vertexai,
                    'project': project,
                    'location': location,
                    'client_type': 'VertexAI' if vertexai else 'GeminiAPI',
                    'http_timeout': effective_http_options.timeout,
                    'http_retry_attempts': (
                        effective_http_options.retry_options.attempts
                        if effective_http_options.retry_options else None
                    ),
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

    def _build_default_http_options(self) -> HttpOptions:
        timeout = self._read_env_int("GEMINI_TIMEOUT", default=30000)

        retry_options = HttpRetryOptions(
            attempts=self._read_env_int("GEMINI_RETRY_ATTEMPTS", default=3),
            initial_delay=self._read_env_float("GEMINI_RETRY_INITIAL_DELAY", default=1.0),
            max_delay=self._read_env_float("GEMINI_RETRY_MAX_DELAY", default=60.0),
            exp_base=self._read_env_float("GEMINI_RETRY_EXP_BASE", default=2.0),
            jitter=self._read_env_bool("GEMINI_RETRY_JITTER", default=True),
        )

        return HttpOptions(
            timeout=timeout,
            retry_options=retry_options,
        )

    @staticmethod
    def _read_env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = int(raw)
            return value if value > 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _read_env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
            return value if value > 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _read_env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _normalize_http_options(
        self,
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]],
    ) -> HttpOptions:
        if isinstance(http_options, dict):
            http_options = HttpOptions(**http_options)

        defaults = self._default_http_options
        user_opts = http_options or HttpOptions()
        use_default_timeout = getattr(user_opts, "use_default_timeout", True)

        merged_headers: Dict[str, str] = {}
        if defaults.headers:
            merged_headers.update(defaults.headers)
        if user_opts.headers:
            merged_headers.update(user_opts.headers)

        return HttpOptions(
            api_version=user_opts.api_version or defaults.api_version,
            base_url=user_opts.base_url or defaults.base_url,
            headers=merged_headers or None,
            timeout=(
                user_opts.timeout
                if user_opts.timeout is not None or not use_default_timeout
                else defaults.timeout
            ),
            retry_options=user_opts.retry_options or defaults.retry_options,
        )

    def _to_genai_http_options(self, options: Optional[HttpOptions]):
        if not options:
            return None
        if not GOOGLE_GENAI_AVAILABLE:
            return None

        retry_options = None
        if options.retry_options:
            retry_options = google_genai.types.HttpRetryOptions(
                attempts=options.retry_options.attempts,
                initial_delay=options.retry_options.initial_delay,
                max_delay=options.retry_options.max_delay,
                exp_base=options.retry_options.exp_base,
                jitter=options.retry_options.jitter,
            )

        return google_genai.types.HttpOptions(
            api_version=options.api_version,
            base_url=options.base_url,
            headers=options.headers,
            timeout=options.timeout,
            retry_options=retry_options,
        )

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
        credentials = None,
        http_options: Optional[HttpOptions] = None,
    ) -> str:
        """
        生成缓存键

        策略：
        - Vertex AI: vertex:{project}:{location}:{credential_fingerprint}
        - Gemini API: gemini:{api_key_fingerprint}

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
            # 尽量使用 credentials 的稳定标识（service account email），并做哈希脱敏
            cred_identity = (
                getattr(credentials, "service_account_email", None)
                or getattr(credentials, "_service_account_email", None)
                or repr(credentials)
            )
            cred_fingerprint = hashlib.sha256(str(cred_identity).encode("utf-8")).hexdigest()[:16]
        else:
            key_source = api_key or "none"
            cred_fingerprint = hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:16]

        if vertexai:
            return (
                f"vertex:{project}:{location}:{cred_fingerprint}:"
                f"http={self._http_options_fingerprint(http_options)}"
            )
        else:
            return f"gemini:{cred_fingerprint}:http={self._http_options_fingerprint(http_options)}"

    @staticmethod
    def _http_options_fingerprint(http_options: Optional[HttpOptions]) -> str:
        if not http_options:
            return "none"
        retry = http_options.retry_options
        retry_tuple = (
            retry.attempts if retry else None,
            retry.initial_delay if retry else None,
            retry.max_delay if retry else None,
            retry.exp_base if retry else None,
            retry.jitter if retry else None,
        )
        payload = (
            http_options.api_version,
            http_options.base_url,
            tuple(sorted((http_options.headers or {}).items())),
            http_options.timeout,
            retry_tuple,
        )
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()[:16]


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
