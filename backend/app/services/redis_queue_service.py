"""
Redis 队列服务

特性：
- 优先级队列（BRPOP 阻塞等待，无轮询）
- 滑动窗口限流
- 分布式锁
- 原子操作
"""

import redis.asyncio as redis
import asyncio
import time
import json
from typing import Optional, Dict, Any
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)


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

    async def connect(self):
        """连接 Redis"""
        try:
            # 隐藏密码的 URL 用于日志
            safe_url = self.redis_url
            if '@' in safe_url:
                # redis://:password@host:port/db -> redis://:***@host:port/db
                parts = safe_url.split('@')
                safe_url = parts[0].rsplit(':', 1)[0] + ':***@' + parts[1]
            
            logger.info(f"[RedisQueue] 正在连接: {safe_url}")
            
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # 测试连接
            await self._redis.ping()
            
            logger.info(f"[RedisQueue] ✅ 已连接: {safe_url}")
        except Exception as e:
            logger.error(f"[RedisQueue] ❌ 连接失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def disconnect(self):
        """断开连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("[RedisQueue] 已断开")

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
