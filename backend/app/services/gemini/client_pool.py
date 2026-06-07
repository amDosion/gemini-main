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

import functools
import hashlib
import logging
import os
import threading
from typing import Dict, Optional, Any, Union
from datetime import datetime

from .http_options import HttpOptions, HttpOptionsDict, HttpRetryOptions

logger = logging.getLogger(__name__)

try:
    from google import genai as google_genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    google_genai = None
    GOOGLE_GENAI_AVAILABLE = False


@functools.lru_cache(maxsize=64)
def _compute_http_fingerprint(payload: tuple) -> str:
    """SHA-256 digest of a hashable HttpOptions payload tuple.

    Bounded by lru_cache(maxsize=64); thread-safe under CPython's GIL
    and semantically clean — no manual dict manipulation needed.
    """
    return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()[:16]


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

        self._clients: Dict[str, Any] = {}  # google.genai.Client instances
        self._client_metadata: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            'total_clients': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'rejected_due_to_max_size': 0,
        }
        self._default_http_options = self._build_default_http_options()
        # 防 OOM：池规模上限。每个 google.genai.Client 含 httpx + httpcore
        # 连接池 ≈ 2.4 MB RSS；不限上限时 1K 独立 api_key 即 ~2.3 GB。
        # 默认 200 适用于"少量稳定 api_key + 少量 Vertex 项目"场景；
        # 多租户 / per-user-key 场景应通过 GEMINI_POOL_MAX_SIZE 主动调高
        # 并配合监控 hit_rate 评估。
        self._max_size = self._read_env_int("GEMINI_POOL_MAX_SIZE", default=200)
        self._initialized = True

        logger.info(
            "[GeminiClientPool] Client pool initialized with HTTP defaults: "
            f"timeout={self._default_http_options.timeout}, "
            f"retry_attempts={getattr(self._default_http_options.retry_options, 'attempts', None)}, "
            f"max_size={self._max_size}"
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
        - Vertex AI 模式 (vertexai=True): 使用官方 google.genai.Client (vertexai=True)

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
            - Vertex AI 模式: google.genai.Client (vertexai=True)

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

        # 快速路径：缓存命中（使用锁保护 stats 更新的原子性）
        with self._lock:
            if cache_key in self._clients:
                self._stats['cache_hits'] += 1
                logger.debug(
                    f"[GeminiClientPool] Cache hit for {cache_key}",
                    extra={'cache_key': cache_key, 'total_hits': self._stats['cache_hits']}
                )
                return self._clients[cache_key]

            # OOM 防护：池规模上限检查（lock 内执行，与 cache hit 路径互斥）
            if len(self._clients) >= self._max_size:
                self._stats['rejected_due_to_max_size'] += 1
                raise RuntimeError(
                    f"GeminiClientPool size limit reached "
                    f"(max_size={self._max_size}, active={len(self._clients)}). "
                    f"Tune via GEMINI_POOL_MAX_SIZE env var, or check whether "
                    f"per-user api_key explosion is expected for this deployment."
                )

            # 创建新客户端（根据 vertexai 标志选择不同的实现）
            try:
                if vertexai:
                    # ✅ Vertex AI 模式：直接创建 google.genai.Client (raw SDK client)
                    logger.debug(f"[GeminiClientPool] Creating Vertex AI client (vertexai=True)")
                    if not GOOGLE_GENAI_AVAILABLE:
                        raise RuntimeError(
                            "google-genai SDK is not available. "
                            "Please install: pip install google-genai>=1.55.0"
                        )

                    resolved_project = project or os.environ.get('GOOGLE_CLOUD_PROJECT')
                    resolved_location = location or os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')

                    if not (resolved_project and resolved_location):
                        raise ValueError(
                            'Missing project or location! To use Vertex AI, '
                            'provide project and location arguments or set environment variables.'
                        )

                    client_kwargs = {
                        "vertexai": True,
                        "project": resolved_project,
                        "location": resolved_location,
                    }
                    if credentials:
                        client_kwargs["credentials"] = credentials
                        logger.info("[GeminiClientPool] Using Vertex AI with service account credentials")
                    else:
                        logger.info("[GeminiClientPool] Using Vertex AI ADC mode (project/location)")

                    genai_http_options = self._to_genai_http_options(effective_http_options)
                    if genai_http_options is not None:
                        client_kwargs["http_options"] = genai_http_options

                    client = google_genai.Client(**client_kwargs)
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
                    # 不再记录 api_key 前缀（即便是 8 字符也会泄漏 Google AI key
                    # 同源项目共享前缀的熵）。诊断只需要"是否配置"语义。
                    'api_key_configured': bool(api_key),
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
            if value > 0:
                return value
            logger.warning(
                "[GeminiClientPool] Invalid value for %s=%r (must be >0), using default=%d",
                name, raw, default,
            )
            return default
        except (TypeError, ValueError):
            logger.warning(
                "[GeminiClientPool] Cannot parse %s=%r as int, using default=%d",
                name, raw, default,
            )
            return default

    @staticmethod
    def _read_env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            value = float(raw)
            if value > 0:
                return value
            logger.warning(
                "[GeminiClientPool] Invalid value for %s=%r (must be >0), using default=%g",
                name, raw, default,
            )
            return default
        except (TypeError, ValueError):
            logger.warning(
                "[GeminiClientPool] Cannot parse %s=%r as float, using default=%g",
                name, raw, default,
            )
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
            # 之前 silent return None 会让 timeout / retry 配置静默丢失。
            # get_client() 已在 line 142 / 180 raise 同样错误，这里保持一致：
            # 任何路径触达此方法时 SDK 不可用都必须 fail-fast。
            raise RuntimeError(
                "google-genai SDK is not available; cannot convert HttpOptions. "
                "Please install: pip install google-genai>=1.55.0"
            )

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
            'max_size': self._max_size,
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'rejected_due_to_max_size': self._stats.get('rejected_due_to_max_size', 0),
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
            # 必须能从 credentials 上拿到稳定的 service-account email 作为 fingerprint。
            # 不再 fallback 到 repr(credentials)：默认 repr 含进程内存地址，进程重启即变；
            # 且若未来 google-auth 给 Credentials 加自定义 __repr__，可能泄漏 token state。
            cred_identity = (
                getattr(credentials, "service_account_email", None)
                or getattr(credentials, "_service_account_email", None)
            )
            if not cred_identity:
                raise ValueError(
                    "Cannot derive stable cache identity from credentials object — "
                    "service_account_email is required. Use "
                    "google.oauth2.service_account.Credentials.from_service_account_info()."
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
        # Delegates to module-level _compute_http_fingerprint which is decorated
        # with functools.lru_cache(maxsize=64). That helper is thread-safe under
        # CPython's GIL and avoids the manual FIFO dict eviction that would
        # otherwise require its own lock (finding svc-gemini-12).
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
        return _compute_http_fingerprint(payload)


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
