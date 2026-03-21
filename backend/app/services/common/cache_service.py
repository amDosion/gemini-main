"""
Redis 缓存服务

提供统一的缓存接口，支持：
- 键值缓存（get/set/delete）
- 懒加载缓存（get_or_set）
- TTL 管理
- 缓存失效
"""
import json
import hashlib
import logging
from typing import Optional, Any, Callable, Awaitable
import redis.asyncio as redis

from ...core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis 缓存服务
    
    使用 Redis 实现高性能缓存：
    - 支持 JSON 序列化/反序列化
    - 自动 TTL 管理
    - 懒加载模式（get_or_set）
    - 缓存失效支持
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        初始化缓存服务
        
        Args:
            redis_client: Redis 客户端（如果为 None，将自动创建）
        """
        self._redis: Optional[redis.Redis] = redis_client
        self._redis_url = settings.redis_url
        self.default_ttl = 3600  # 默认 TTL：1 小时
    
    async def connect(self) -> None:
        """连接到 Redis"""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=False  # 我们需要手动处理 JSON
                )
                # 测试连接
                await self._redis.ping()
                logger.info("[CacheService] ✅ Redis 连接成功")
            except Exception as e:
                logger.error(f"[CacheService] ❌ Redis 连接失败: {e}")
                raise
    
    async def disconnect(self) -> None:
        """断开 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("[CacheService] Redis 连接已关闭")
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """
        生成缓存键
        
        Args:
            prefix: 键前缀（如 "sessions", "models"）
            *args: 位置参数（会转换为字符串）
            **kwargs: 关键字参数（会转换为 "key:value" 格式）
        
        Returns:
            格式化的缓存键（如 "cache:sessions:user123"）
        """
        key_parts = [prefix]
        
        # 添加位置参数
        for arg in args:
            if arg is not None:
                key_parts.append(str(arg))
        
        # 添加关键字参数（排序以确保一致性）
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            for key, value in sorted_kwargs:
                if value is not None:
                    key_parts.append(f"{key}:{value}")
        
        return ":".join(["cache"] + key_parts)
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
        
        Returns:
            缓存的值（如果存在），否则返回 None
        """
        if not self._redis:
            await self.connect()
        
        try:
            data = await self._redis.get(key)
            if data:
                # 解码字节并解析 JSON
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
        except json.JSONDecodeError as e:
            logger.warning(f"[CacheService] JSON 解析失败 (key={key}): {e}")
        except Exception as e:
            logger.warning(f"[CacheService] 获取缓存失败 (key={key}): {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 要缓存的值（必须是 JSON 可序列化的）
            ttl: 过期时间（秒），如果为 None 则使用默认 TTL
        
        Returns:
            是否设置成功
        """
        if not self._redis:
            await self.connect()
        
        try:
            ttl = ttl or self.default_ttl
            data = json.dumps(value, ensure_ascii=False, default=str)
            await self._redis.setex(key, ttl, data)
            return True
        except (TypeError, ValueError) as e:
            logger.warning(f"[CacheService] JSON 序列化失败 (key={key}): {e}")
            return False
        except Exception as e:
            logger.warning(f"[CacheService] 设置缓存失败 (key={key}): {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键（支持通配符，如 "cache:sessions:*"）
        
        Returns:
            是否删除成功
        """
        if not self._redis:
            await self.connect()
        
        try:
            # 检查是否是通配符模式
            if '*' in key or '?' in key:
                # 使用 SCAN 查找匹配的键
                deleted_count = 0
                async for matched_key in self._redis.scan_iter(match=key):
                    await self._redis.delete(matched_key)
                    deleted_count += 1
                logger.debug(f"[CacheService] 删除了 {deleted_count} 个匹配的缓存键: {key}")
                return deleted_count > 0
            else:
                # 单个键删除
                result = await self._redis.delete(key)
                return result > 0
        except Exception as e:
            logger.warning(f"[CacheService] 删除缓存失败 (key={key}): {e}")
            return False
    
    async def get_or_set(
        self,
        key: str,
        fetch_func: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None
    ) -> Any:
        """
        获取或设置缓存（懒加载模式）
        
        如果缓存存在，直接返回缓存值。
        如果缓存不存在，调用 fetch_func 获取数据，然后缓存并返回。
        
        Args:
            key: 缓存键
            fetch_func: 异步函数，用于获取数据（当缓存未命中时调用）
            ttl: 过期时间（秒），如果为 None 则使用默认 TTL
        
        Returns:
            缓存的值或新获取的值
        """
        # 尝试从缓存获取
        cached = await self.get(key)
        if cached is not None:
            logger.debug(f"[CacheService] 缓存命中: {key}")
            return cached
        
        # 缓存未命中，调用函数获取数据
        logger.debug(f"[CacheService] 缓存未命中，获取数据: {key}")
        try:
            value = await fetch_func()
            # 缓存数据
            await self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"[CacheService] 获取数据失败 (key={key}): {e}")
            raise
    
    async def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在
        
        Args:
            key: 缓存键
        
        Returns:
            是否存在
        """
        if not self._redis:
            await self.connect()
        
        try:
            result = await self._redis.exists(key)
            return result > 0
        except Exception as e:
            logger.warning(f"[CacheService] 检查缓存存在性失败 (key={key}): {e}")
            return False
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        获取缓存的剩余 TTL（秒）
        
        Args:
            key: 缓存键
        
        Returns:
            剩余 TTL（秒），如果键不存在则返回 None
        """
        if not self._redis:
            await self.connect()
        
        try:
            ttl = await self._redis.ttl(key)
            if ttl == -2:
                return None  # 键不存在
            elif ttl == -1:
                return -1  # 键存在但没有设置过期时间
            else:
                return ttl
        except Exception as e:
            logger.warning(f"[CacheService] 获取 TTL 失败 (key={key}): {e}")
            return None


# 全局缓存服务实例（延迟初始化）
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """
    获取全局缓存服务实例（依赖注入）
    
    Returns:
        CacheService 实例
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    return _cache_service


def get_cache_service_sync() -> CacheService:
    """
    获取全局缓存服务实例（同步版本，用于非异步上下文）
    
    Returns:
        CacheService 实例
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
