"""
Redis 队列服务

特性：
- 优先级队列（BRPOP 阻塞等待，无轮询）
- 滑动窗口限流
- 分布式锁
- 原子操作
- 全局连接池管理（TASK-002）
"""

import redis.asyncio as redis
import asyncio
import time
import json
from typing import Optional, Dict, Any
import logging
import threading

from ...core.config import settings

logger = logging.getLogger(__name__)


class GlobalRedisConnectionPool:
    """
    全局 Redis 连接池管理器（TASK-002）
    
    在应用级别管理 Redis 连接，避免 Worker Pool 重启时频繁重建连接。
    - 应用启动时初始化连接池
    - 应用关闭时关闭连接池
    - 支持健康检查和自动重连
    """
    
    _instance: Optional['GlobalRedisConnectionPool'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.redis_url = settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._initialized = False
        self._health_check_interval = 30  # 健康检查间隔（秒）
        self._health_check_task: Optional[asyncio.Task] = None
    
    @classmethod
    def get_instance(cls) -> 'GlobalRedisConnectionPool':
        """获取全局单例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def initialize(self):
        """初始化全局连接池"""
        if self._initialized:
            logger.warning("[GlobalRedisPool] 连接池已初始化，跳过重复初始化")
            return
        
        try:
            # 隐藏密码的 URL 用于日志
            safe_url = self.redis_url
            if '@' in safe_url:
                parts = safe_url.split('@')
                safe_url = parts[0].rsplit(':', 1)[0] + ':***@' + parts[1]
            
            logger.info(f"[GlobalRedisPool] 正在初始化全局连接池: {safe_url}")
            
            # 创建连接池（使用连接池参数）
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,  # 最大连接数
                retry_on_timeout=True,  # 超时重试
                health_check_interval=30,  # 健康检查间隔
            )
            
            # 测试连接
            await self._redis.ping()
            
            self._initialized = True
            logger.info(f"[GlobalRedisPool] ✅ 全局连接池初始化成功: {safe_url}")
            
            # 启动健康检查任务
            self._start_health_check()
            
        except Exception as e:
            logger.error(f"[GlobalRedisPool] ❌ 连接池初始化失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def close(self):
        """关闭全局连接池"""
        if not self._initialized:
            return
        
        # 停止健康检查任务
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        if self._redis:
            try:
                await self._redis.close()
                logger.info("[GlobalRedisPool] ✅ 全局连接池已关闭")
            except Exception as e:
                logger.error(f"[GlobalRedisPool] ❌ 关闭连接池时出错: {e}")
            finally:
                self._redis = None
                self._initialized = False
    
    def get_connection(self) -> Optional[redis.Redis]:
        """获取 Redis 连接（从全局连接池）"""
        if not self._initialized:
            logger.warning("[GlobalRedisPool] 连接池未初始化，返回 None")
            return None
        return self._redis
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized or self._redis is None:
            return False
        
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.warning(f"[GlobalRedisPool] 健康检查失败: {e}")
            return False
    
    def _start_health_check(self):
        """启动健康检查任务"""
        async def _check_loop():
            while True:
                try:
                    await asyncio.sleep(self._health_check_interval)
                    if not await self.health_check():
                        logger.warning("[GlobalRedisPool] 连接健康检查失败，尝试重连...")
                        # 尝试重连
                        try:
                            await self._redis.close()
                        except Exception:
                            pass
                        await self.initialize()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[GlobalRedisPool] 健康检查任务出错: {e}")
                    await asyncio.sleep(self._health_check_interval)
        
        self._health_check_task = asyncio.create_task(_check_loop())
        logger.info("[GlobalRedisPool] 健康检查任务已启动")
    
    def is_initialized(self) -> bool:
        """检查连接池是否已初始化"""
        return self._initialized


class RedisQueueService:
    """
    Redis 队列服务

    使用 Redis 实现高性能任务队列：
    - 优先级队列：high > normal > low
    - BRPOP 阻塞等待：0 CPU 占用
    - 滑动窗口限流：Lua 脚本保证原子性
    - 分布式锁：SET NX EX 模式
    """

    # Redis Key 前缀
    QUEUE_HIGH = "upload:queue:high"
    QUEUE_NORMAL = "upload:queue:normal"
    QUEUE_LOW = "upload:queue:low"
    DEAD_LETTER = "upload:dead_letter"
    RATE_LIMIT_KEY = "upload:rate_limit"
    STATS_KEY = "upload:stats"
    LOCK_PREFIX = "upload:lock:"
    TASK_LOG_PREFIX = "upload:task:logs:"
    TASK_LOG_MAX_LEN = 500
    TASK_LOG_TTL_SECONDS = 7 * 24 * 60 * 60

    def __init__(self):
        self.redis_url = settings.redis_url
        self.rate_limit = settings.upload_queue_rate_limit
        self.rate_window = 1  # 1秒窗口
        self._redis: Optional[redis.Redis] = None
        self._global_pool = GlobalRedisConnectionPool.get_instance()

    async def connect(self):
        """
        连接 Redis（使用全局连接池）
        
        TASK-002: 现在使用全局连接池，而不是创建独立连接
        """
        # 如果全局连接池未初始化，先初始化
        if not self._global_pool.is_initialized():
            logger.info("[RedisQueue] 全局连接池未初始化，正在初始化...")
            await self._global_pool.initialize()
        
        # 从全局连接池获取连接
        self._redis = self._global_pool.get_connection()
        
        if self._redis is None:
            raise RuntimeError("无法从全局连接池获取 Redis 连接")
        
        # 测试连接
        try:
            await self._redis.ping()
            logger.info("[RedisQueue] ✅ 已从全局连接池获取连接")
        except Exception as e:
            logger.error(f"[RedisQueue] ❌ 连接测试失败: {e}")
            # 尝试重新初始化连接池
            try:
                await self._global_pool.close()
                await self._global_pool.initialize()
                self._redis = self._global_pool.get_connection()
                if self._redis:
                    await self._redis.ping()
                    logger.info("[RedisQueue] ✅ 重连成功")
                else:
                    raise RuntimeError("重连后仍无法获取连接")
            except Exception as reconnect_error:
                logger.error(f"[RedisQueue] ❌ 重连失败: {reconnect_error}")
                raise

    async def disconnect(self):
        """
        断开连接（TASK-002: 不再关闭连接，因为使用全局连接池）
        
        注意：现在不会真正断开连接，因为连接由全局连接池管理
        只有在应用关闭时才会关闭连接池
        """
        # 只清除本地引用，不断开全局连接池的连接
        self._redis = None
        logger.debug("[RedisQueue] 已清除本地连接引用（全局连接池保持连接）")

    def _task_log_key(self, task_id: str) -> str:
        return f"{self.TASK_LOG_PREFIX}{task_id}"

    async def append_task_log(
        self,
        task_id: str,
        level: str,
        message: str,
        source: str = "unknown",
        extra: Optional[Dict[str, Any]] = None,
    ):
        """追加任务日志（存储在 Redis，供前端查询）"""
        if self._redis is None:
            return

        entry: Dict[str, Any] = {
            "ts": int(time.time() * 1000),
            "level": level,
            "source": source,
            "message": message,
        }
        if extra:
            entry.update(extra)

        key = self._task_log_key(task_id)
        try:
            await self._redis.rpush(key, json.dumps(entry, ensure_ascii=False))
            await self._redis.ltrim(key, -self.TASK_LOG_MAX_LEN, -1)
            await self._redis.expire(key, self.TASK_LOG_TTL_SECONDS)
        except Exception:
            # 任务日志不应影响主流程
            logger.debug("[RedisQueue] append_task_log failed", exc_info=True)

    async def get_task_logs(self, task_id: str, tail: int = 200):
        """获取任务日志（默认返回最后 tail 条）"""
        if self._redis is None:
            raise RuntimeError("Redis 未连接")

        tail = max(1, min(int(tail), self.TASK_LOG_MAX_LEN))
        key = self._task_log_key(task_id)
        raw = await self._redis.lrange(key, -tail, -1)

        logs = []
        for item in raw:
            try:
                logs.append(json.loads(item))
            except Exception:
                logs.append({"ts": None, "level": "unknown", "source": "unknown", "message": str(item)})
        return logs

    async def is_task_queued(self, task_id: str) -> bool:
        """检查任务是否已存在于任意优先级队列中"""
        if self._redis is None:
            raise RuntimeError("Redis 未连接")

        for key in (self.QUEUE_HIGH, self.QUEUE_NORMAL, self.QUEUE_LOW):
            try:
                pos = await self._redis.lpos(key, task_id)
            except Exception:
                pos = None
            if pos is not None:
                return True
        return False

    async def enqueue(self, task_id: str, priority: str = "normal") -> int:
        """
        任务入队

        Args:
            task_id: 任务 ID
            priority: 优先级 (high/normal/low)

        Returns:
            队列位置
        """
        # 检查连接状态
        if self._redis is None:
            logger.error("[RedisQueue] ❌ Redis 未连接！请先调用 connect()")
            raise RuntimeError("Redis 未连接")
        
        queue_key = self._get_queue_key(priority)

        try:
            # LPUSH 入队（左进右出）
            await self._redis.lpush(queue_key, task_id)

            # 更新统计
            await self._redis.hincrby(self.STATS_KEY, "total_enqueued", 1)

            # 返回队列长度
            length = await self._redis.llen(queue_key)

            await self.append_task_log(
                task_id,
                level="info",
                message=f"enqueued to {queue_key} (priority={priority}, position={length})",
                source="queue",
            )
            logger.info(f"[RedisQueue] ✅ 入队: {task_id[:8]}..., 优先级: {priority}, 位置: {length}")
            return length
        except Exception as e:
            logger.error(f"[RedisQueue] ❌ 入队失败: {e}")
            raise

    async def dequeue(self, timeout: int = 5) -> Optional[str]:
        """
        从队列获取任务（阻塞等待）

        按优先级顺序：high > normal > low
        使用 BRPOP 阻塞，无需轮询，低 CPU 占用

        Args:
            timeout: 阻塞超时（秒）

        Returns:
            task_id 或 None
        """
        if self._redis is None:
            raise RuntimeError("Redis 未连接")

        # BRPOP 按顺序从多个队列获取
        result = await self._redis.brpop(
            [self.QUEUE_HIGH, self.QUEUE_NORMAL, self.QUEUE_LOW],
            timeout=timeout
        )

        if result:
            queue_name, task_id = result
            await self._redis.hincrby(self.STATS_KEY, "total_dequeued", 1)
            await self.append_task_log(
                task_id,
                level="info",
                message=f"dequeued from {queue_name}",
                source="queue",
            )
            logger.debug(f"[RedisQueue] 出队: {task_id[:8]}... from {queue_name}")
            return task_id

        return None

    async def move_to_dead_letter(self, task_id: str):
        """移入死信队列"""
        await self._redis.lpush(self.DEAD_LETTER, task_id)
        await self._redis.hincrby(self.STATS_KEY, "total_dead", 1)
        logger.warning(f"[RedisQueue] 移入死信: {task_id[:8]}...")

    async def retry_from_dead_letter(self, task_id: str, priority: str = "low") -> bool:
        """从死信队列重试"""
        removed = await self._redis.lrem(self.DEAD_LETTER, 1, task_id)
        if removed:
            await self.enqueue(task_id, priority)
            return True
        return False

    async def acquire_rate_token(self) -> bool:
        """
        获取限流令牌（滑动窗口）

        Returns:
            是否获取成功
        """
        now = time.time()
        window_start = now - self.rate_window

        # Lua 脚本保证原子性
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local request_id = ARGV[4]

        -- 清理过期记录
        redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

        -- 检查当前窗口请求数
        local count = redis.call('ZCARD', key)

        if count < limit then
            -- 添加新请求
            redis.call('ZADD', key, now, request_id)
            -- 设置过期时间
            redis.call('EXPIRE', key, 2)
            return 1
        else
            return 0
        end
        """

        request_id = f"{now}:{id(asyncio.current_task())}"
        result = await self._redis.eval(
            lua_script,
            1,
            self.RATE_LIMIT_KEY,
            str(now),
            str(window_start),
            str(self.rate_limit),
            request_id
        )

        return result == 1

    async def wait_for_rate_token(self, max_wait: float = 10.0) -> bool:
        """等待获取限流令牌"""
        start = time.time()

        while time.time() - start < max_wait:
            if await self.acquire_rate_token():
                return True
            await asyncio.sleep(0.1)

        return False

    async def acquire_lock(self, task_id: str, worker_id: str, ttl: int = 60) -> bool:
        """获取任务锁"""
        lock_key = f"{self.LOCK_PREFIX}{task_id}"
        return await self._redis.set(lock_key, worker_id, nx=True, ex=ttl)

    async def release_lock(self, task_id: str, worker_id: str) -> bool:
        """释放任务锁"""
        lock_key = f"{self.LOCK_PREFIX}{task_id}"

        # Lua 脚本保证原子性（只释放自己的锁）
        lua_script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        else
            return 0
        end
        """

        result = await self._redis.eval(lua_script, 1, lock_key, worker_id)
        return result == 1

    async def update_stats(self, field: str, increment: int = 1):
        """更新统计"""
        await self._redis.hincrby(self.STATS_KEY, field, increment)

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = await self._redis.hgetall(self.STATS_KEY)

        # 获取队列长度
        high_len = await self._redis.llen(self.QUEUE_HIGH)
        normal_len = await self._redis.llen(self.QUEUE_NORMAL)
        low_len = await self._redis.llen(self.QUEUE_LOW)
        dead_len = await self._redis.llen(self.DEAD_LETTER)

        return {
            "queue_high": high_len,
            "queue_normal": normal_len,
            "queue_low": low_len,
            "queue_total": high_len + normal_len + low_len,
            "dead_letter": dead_len,
            "total_enqueued": int(stats.get("total_enqueued", 0)),
            "total_dequeued": int(stats.get("total_dequeued", 0)),
            "total_completed": int(stats.get("total_completed", 0)),
            "total_failed": int(stats.get("total_failed", 0)),
            "total_retried": int(stats.get("total_retried", 0)),
            "total_dead": int(stats.get("total_dead", 0))
        }

    def _get_queue_key(self, priority: str) -> str:
        """获取队列 Key"""
        if priority == "high":
            return self.QUEUE_HIGH
        elif priority == "low":
            return self.QUEUE_LOW
        else:
            return self.QUEUE_NORMAL


# 全局单例
redis_queue = RedisQueueService()
