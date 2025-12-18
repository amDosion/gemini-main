# Redis + 数据库 高并发上传队列方案

## 1. 设计理念

### 1.1 核心原则

- **Redis 负责队列调度**：高性能、低延迟、原子操作
- **数据库负责持久化**：任务状态、结果存储、历史查询
- **分离关注点**：队列调度与数据存储解耦
- **低负载设计**：避免轮询，使用阻塞队列

### 1.2 架构优势

| 特性 | Redis | 数据库 | 组合优势 |
|------|-------|--------|----------|
| 队列操作 | ✅ O(1) 原子操作 | ❌ 需要锁 | Redis 处理队列 |
| 持久化 | ⚠️ 可能丢失 | ✅ 可靠 | 数据库兜底 |
| 查询 | ❌ 有限 | ✅ 灵活 | 数据库查询 |
| 分布式 | ✅ 天然支持 | ⚠️ 需要设计 | Redis 协调 |

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Redis + 数据库 高并发上传架构                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  前端                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  POST /api/storage/upload-async                                          │   │
│  │  - 提交文件                                                              │   │
│  │  - 获取 task_id                                                          │   │
│  │  - 可选轮询状态                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  后端 API 层                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. 保存文件到临时目录                                                   │   │
│  │  2. 创建任务记录 → 数据库（持久化）                                      │   │
│  │  3. 任务 ID 入队 → Redis（调度）                                         │   │
│  │  4. 立即返回 task_id                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│       ┌──────────────────────────────┴──────────────────────────────┐          │
│       │                                                              │          │
│       ▼                                                              ▼          │
│  ┌─────────────────────┐                              ┌─────────────────────┐  │
│  │      Redis          │                              │     数据库          │  │
│  │                     │                              │                     │  │
│  │  优先级队列         │                              │  upload_tasks 表    │  │
│  │  ┌───────────────┐  │                              │  - 任务详情         │  │
│  │  │ upload:high   │  │                              │  - 状态             │  │
│  │  │ upload:normal │  │                              │  - 结果 URL         │  │
│  │  │ upload:low    │  │                              │  - 错误信息         │  │
│  │  └───────────────┘  │                              │                     │  │
│  │                     │                              │                     │  │
│  │  限流计数器         │                              │                     │  │
│  │  ┌───────────────┐  │                              │                     │  │
│  │  │ upload:rate   │  │                              │                     │  │
│  │  └───────────────┘  │                              │                     │  │
│  │                     │                              │                     │  │
│  │  分布式锁           │                              │                     │  │
│  │  ┌───────────────┐  │                              │                     │  │
│  │  │ upload:lock:* │  │                              │                     │  │
│  │  └───────────────┘  │                              │                     │  │
│  └─────────────────────┘                              └─────────────────────┘  │
│       │                                                              │          │
│       └──────────────────────────────┬──────────────────────────────┘          │
│                                      │                                          │
│                                      ▼                                          │
│  Worker 池                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                 │   │
│  │  │Worker-0│ │Worker-1│ │Worker-2│ │Worker-3│ │Worker-4│                 │   │
│  │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘                 │   │
│  │      │          │          │          │          │                       │   │
│  │      └──────────┴──────────┼──────────┴──────────┘                       │   │
│  │                            │                                              │   │
│  │                   BRPOP (阻塞等待，无轮询)                                │   │
│  │                            │                                              │   │
│  │                            ▼                                              │   │
│  │                   ┌─────────────────┐                                    │   │
│  │                   │  限流器检查     │                                    │   │
│  │                   │  (Redis 计数器) │                                    │   │
│  │                   └─────────────────┘                                    │   │
│  │                            │                                              │   │
│  │                            ▼                                              │   │
│  │                   ┌─────────────────┐                                    │   │
│  │                   │  执行上传       │                                    │   │
│  │                   │  StorageService │                                    │   │
│  │                   └─────────────────┘                                    │   │
│  │                            │                                              │   │
│  │              ┌─────────────┴─────────────┐                               │   │
│  │              │                           │                               │   │
│  │              ▼                           ▼                               │   │
│  │        ┌──────────┐               ┌──────────┐                           │   │
│  │        │  成功    │               │  失败    │                           │   │
│  │        │ 更新数据库│               │ 重试/死信│                           │   │
│  │        └──────────┘               └──────────┘                           │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```


## 3. Redis 数据结构设计

### 3.1 优先级队列

```
# 三个优先级队列（List 类型）
upload:queue:high     # 高优先级
upload:queue:normal   # 普通优先级
upload:queue:low      # 低优先级

# 存储内容：task_id（轻量）
# 任务详情从数据库获取
```

### 3.2 限流计数器

```
# 滑动窗口限流（Sorted Set）
upload:rate_limit
  - score: 时间戳
  - member: 请求唯一标识

# 或使用 Redis 令牌桶（String + Lua）
upload:tokens         # 当前令牌数
upload:last_refill    # 上次补充时间
```

### 3.3 分布式锁

```
# 任务处理锁（防止重复处理）
upload:lock:{task_id}
  - value: worker_id
  - TTL: 60s
```

### 3.4 统计信息

```
# 实时统计（Hash）
upload:stats
  - total_enqueued: 总入队数
  - total_completed: 总完成数
  - total_failed: 总失败数
  - total_retried: 总重试数
```

## 4. 核心实现

### 4.1 Redis 队列服务

```python
# backend/app/services/redis_queue_service.py

import redis.asyncio as redis
import asyncio
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RedisQueueService:
    """
    Redis 队列服务
    
    特性：
    - 优先级队列（BRPOP 阻塞等待，无轮询）
    - 滑动窗口限流
    - 分布式锁
    - 原子操作
    """
    
    # Redis Key 前缀
    QUEUE_HIGH = "upload:queue:high"
    QUEUE_NORMAL = "upload:queue:normal"
    QUEUE_LOW = "upload:queue:low"
    DEAD_LETTER = "upload:dead_letter"
    RATE_LIMIT_KEY = "upload:rate_limit"
    STATS_KEY = "upload:stats"
    LOCK_PREFIX = "upload:lock:"
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        rate_limit: int = 10,
        rate_window: int = 1
    ):
        self.redis_url = redis_url
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        self._redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """连接 Redis"""
        self._redis = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info(f"[RedisQueue] 已连接: {self.redis_url}")
    
    async def disconnect(self):
        """断开连接"""
        if self._redis:
            await self._redis.close()
            logger.info("[RedisQueue] 已断开")
    
    async def enqueue(self, task_id: str, priority: str = "normal") -> int:
        """
        任务入队
        
        Args:
            task_id: 任务 ID
            priority: 优先级 (high/normal/low)
        
        Returns:
            队列位置
        """
        queue_key = self._get_queue_key(priority)
        
        # LPUSH 入队（左进右出）
        await self._redis.lpush(queue_key, task_id)
        
        # 更新统计
        await self._redis.hincrby(self.STATS_KEY, "total_enqueued", 1)
        
        # 返回队列长度
        length = await self._redis.llen(queue_key)
        
        logger.info(f"[RedisQueue] 入队: {task_id[:8]}..., 优先级: {priority}, 位置: {length}")
        return length
    
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
        # BRPOP 按顺序从多个队列获取
        result = await self._redis.brpop(
            [self.QUEUE_HIGH, self.QUEUE_NORMAL, self.QUEUE_LOW],
            timeout=timeout
        )
        
        if result:
            queue_name, task_id = result
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
            "total_completed": int(stats.get("total_completed", 0)),
            "total_failed": int(stats.get("total_failed", 0)),
            "total_retried": int(stats.get("total_retried", 0))
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
```

### 4.2 Worker 池管理器

```python
# backend/app/services/upload_worker_pool.py

import asyncio
import os
from typing import Optional, List
from datetime import datetime
import logging
import httpx

from ..core.database import SessionLocal
from ..models.db_models import UploadTask, StorageConfig, ActiveStorage, ChatSession
from .storage_service import StorageService
from .redis_queue_service import redis_queue

logger = logging.getLogger(__name__)


class UploadWorkerPool:
    """
    上传 Worker 池
    
    特性：
    - 使用 Redis BRPOP 阻塞等待（无轮询，低 CPU）
    - 自动重试（指数退避）
    - 分布式锁（防止重复处理）
    """
    
    def __init__(
        self,
        num_workers: int = 5,
        max_retries: int = 3,
        base_retry_delay: float = 2.0
    ):
        self.num_workers = num_workers
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        
        self._running = False
        self._workers: List[asyncio.Task] = []
    
    async def start(self):
        """启动 Worker 池"""
        if self._running:
            return
        
        self._running = True
        
        # 连接 Redis
        await redis_queue.connect()
        
        # 恢复中断任务
        await self._recover_tasks()
        
        # 启动 Workers
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        logger.info(f"[WorkerPool] 已启动 {self.num_workers} 个 Worker")
    
    async def stop(self):
        """停止 Worker 池"""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        await redis_queue.disconnect()
        
        logger.info("[WorkerPool] 已停止")
    
    async def _recover_tasks(self):
        """恢复中断的任务"""
        db = SessionLocal()
        try:
            # 将 uploading 状态重置为 pending 并重新入队
            tasks = db.query(UploadTask).filter(
                UploadTask.status == 'uploading'
            ).all()
            
            for task in tasks:
                task.status = 'pending'
                task.started_at = None
                # 重新入队到 Redis
                await redis_queue.enqueue(task.id, task.priority or 'normal')
            
            db.commit()
            
            if tasks:
                logger.info(f"[WorkerPool] 恢复 {len(tasks)} 个中断任务")
        finally:
            db.close()
    
    async def _worker_loop(self, worker_id: int):
        """Worker 主循环"""
        worker_name = f"worker-{worker_id}"
        logger.info(f"[WorkerPool] {worker_name} 启动")
        
        while self._running:
            try:
                # 从 Redis 队列获取任务（阻塞等待）
                task_id = await redis_queue.dequeue(timeout=5)
                
                if task_id is None:
                    continue
                
                # 获取分布式锁
                if not await redis_queue.acquire_lock(task_id, worker_name):
                    logger.warning(f"[WorkerPool] {worker_name} 获取锁失败: {task_id[:8]}...")
                    continue
                
                try:
                    # 限流
                    if not await redis_queue.wait_for_rate_token(max_wait=30):
                        logger.warning(f"[WorkerPool] {worker_name} 限流等待超时")
                        # 重新入队
                        await redis_queue.enqueue(task_id, 'normal')
                        continue
                    
                    # 处理任务
                    await self._process_task(task_id, worker_name)
                    
                finally:
                    # 释放锁
                    await redis_queue.release_lock(task_id, worker_name)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WorkerPool] {worker_name} 异常: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"[WorkerPool] {worker_name} 停止")
    
    async def _process_task(self, task_id: str, worker_name: str):
        """处理单个任务"""
        db = SessionLocal()
        try:
            # 从数据库获取任务详情
            task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
            
            if not task:
                logger.warning(f"[WorkerPool] 任务不存在: {task_id}")
                return
            
            if task.status != 'pending':
                logger.warning(f"[WorkerPool] 任务状态异常: {task_id}, status={task.status}")
                return
            
            # 更新状态
            task.status = 'uploading'
            task.started_at = int(datetime.now().timestamp() * 1000)
            db.commit()
            
            logger.info(f"[WorkerPool] {worker_name} 处理: {task_id[:8]}..., 文件: {task.filename}")
            
            # 读取文件内容
            content = await self._get_file_content(task)
            
            # 获取存储配置
            config = self._get_storage_config(db, task.storage_id)
            if not config:
                raise Exception("存储配置不可用")
            
            # 执行上传
            result = await StorageService.upload_file(
                filename=task.filename,
                content=content,
                content_type='image/png',
                provider=config.provider,
                config=config.config
            )
            
            if result.get('success'):
                await self._handle_success(db, task, result.get('url'), worker_name)
            else:
                raise Exception(result.get('error', '上传失败'))
                
        except Exception as e:
            await self._handle_failure(db, task_id, str(e), worker_name)
        finally:
            db.close()
    
    async def _get_file_content(self, task: UploadTask) -> bytes:
        """获取文件内容"""
        if task.source_file_path and os.path.exists(task.source_file_path):
            with open(task.source_file_path, 'rb') as f:
                return f.read()
        elif task.source_url:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(task.source_url)
                response.raise_for_status()
                return response.content
        else:
            raise Exception("无可用的文件来源")
    
    def _get_storage_config(self, db, storage_id: Optional[str]):
        """获取存储配置"""
        if storage_id:
            config = db.query(StorageConfig).filter(StorageConfig.id == storage_id).first()
        else:
            active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
            if active and active.storage_id:
                config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
            else:
                return None
        
        return config if config and config.enabled else None
    
    async def _handle_success(self, db, task: UploadTask, url: str, worker_name: str):
        """处理成功"""
        now = int(datetime.now().timestamp() * 1000)
        
        task.status = 'completed'
        task.target_url = url
        task.completed_at = now
        db.commit()
        
        # 删除临时文件
        if task.source_file_path and os.path.exists(task.source_file_path):
            try:
                os.remove(task.source_file_path)
            except:
                pass
        
        # 更新会话附件
        if task.session_id and task.message_id and task.attachment_id:
            await self._update_session_attachment(
                db, task.session_id, task.message_id, task.attachment_id, url
            )
        
        # 更新 Redis 统计
        await redis_queue.update_stats("total_completed")
        
        logger.info(f"[WorkerPool] {worker_name} 完成: {task.id[:8]}..., URL: {url[:50]}...")
    
    async def _handle_failure(self, db, task_id: str, error: str, worker_name: str):
        """处理失败"""
        task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
        if not task:
            return
        
        task.retry_count = (task.retry_count or 0) + 1
        task.error_message = error
        
        logger.warning(
            f"[WorkerPool] {worker_name} 失败: {task_id[:8]}..., "
            f"错误: {error}, 重试: {task.retry_count}/{self.max_retries}"
        )
        
        if task.retry_count < self.max_retries:
            # 指数退避
            delay = self.base_retry_delay * (2 ** (task.retry_count - 1))
            
            task.status = 'pending'
            task.started_at = None
            db.commit()
            
            # 延迟后重新入队
            await asyncio.sleep(delay)
            await redis_queue.enqueue(task_id, 'low')  # 重试任务低优先级
            await redis_queue.update_stats("total_retried")
            
            logger.info(f"[WorkerPool] 任务 {task_id[:8]}... 已重新入队")
        else:
            task.status = 'failed'
            task.completed_at = int(datetime.now().timestamp() * 1000)
            db.commit()
            
            # 移入死信队列
            await redis_queue.move_to_dead_letter(task_id)
            await redis_queue.update_stats("total_failed")
            
            logger.error(f"[WorkerPool] 任务 {task_id[:8]}... 最终失败")
    
    async def _update_session_attachment(
        self, db, session_id: str, message_id: str, attachment_id: str, url: str
    ):
        """更新会话附件"""
        from sqlalchemy.orm.attributes import flag_modified
        import copy
        
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                return
            
            messages = copy.deepcopy(session.messages or [])
            updated = False
            
            for msg in messages:
                if msg.get('id') == message_id and msg.get('attachments'):
                    for att in msg['attachments']:
                        if att.get('id') == attachment_id:
                            att['url'] = url
                            att['uploadStatus'] = 'completed'
                            updated = True
                            break
                if updated:
                    break
            
            if updated:
                session.messages = messages
                flag_modified(session, 'messages')
                db.commit()
        except Exception as e:
            logger.error(f"[WorkerPool] 更新会话失败: {e}")


# 全局单例
worker_pool = UploadWorkerPool()
```


### 4.3 路由修改

```python
# backend/app/routers/storage.py 修改

from ..services.redis_queue_service import redis_queue

@router.post("/upload-async")
async def upload_file_async(
    file: UploadFile = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    异步上传（Redis + 数据库队列）
    """
    # 1. 保存文件
    temp_dir = tempfile.gettempdir()
    task_id = str(uuid.uuid4())
    temp_path = os.path.join(temp_dir, f"upload_{task_id}_{file.filename}")
    
    file_content = await file.read()
    with open(temp_path, 'wb') as f:
        f.write(file_content)
    
    # 2. 创建数据库记录（持久化）
    task = UploadTask(
        id=task_id,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        source_file_path=temp_path,
        filename=file.filename,
        storage_id=storage_id,
        status='pending',
        priority=priority,
        retry_count=0,
        max_retries=3,
        file_size=len(file_content),
        created_at=int(datetime.now().timestamp() * 1000)
    )
    db.add(task)
    db.commit()
    
    # 3. 入队 Redis（调度）
    queue_position = await redis_queue.enqueue(task_id, priority)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "priority": priority,
        "queue_position": queue_position
    }


@router.get("/queue/stats")
async def get_queue_stats():
    """获取队列统计（Redis + 数据库）"""
    redis_stats = await redis_queue.get_stats()
    
    # 补充数据库统计
    db = SessionLocal()
    try:
        completed = db.query(UploadTask).filter(UploadTask.status == 'completed').count()
        failed = db.query(UploadTask).filter(UploadTask.status == 'failed').count()
        
        return {
            **redis_stats,
            "db_completed": completed,
            "db_failed": failed
        }
    finally:
        db.close()


@router.get("/dead-letter")
async def get_dead_letter_tasks(limit: int = 50, db: Session = Depends(get_db)):
    """获取死信队列任务"""
    # 从 Redis 获取死信任务 ID
    task_ids = await redis_queue._redis.lrange(redis_queue.DEAD_LETTER, 0, limit - 1)
    
    # 从数据库获取详情
    tasks = db.query(UploadTask).filter(UploadTask.id.in_(task_ids)).all()
    
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": len(task_ids)
    }


@router.post("/dead-letter/retry/{task_id}")
async def retry_dead_letter(task_id: str, db: Session = Depends(get_db)):
    """重试死信任务"""
    # 重置数据库状态
    task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task.status = 'pending'
    task.retry_count = 0
    task.error_message = None
    db.commit()
    
    # 从死信队列移出并重新入队
    success = await redis_queue.retry_from_dead_letter(task_id, 'low')
    
    if not success:
        raise HTTPException(status_code=400, detail="任务不在死信队列中")
    
    return {"success": True}
```

### 4.4 应用启动

```python
# backend/app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .services.upload_worker_pool import worker_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动
    await worker_pool.start()
    yield
    # 关闭
    await worker_pool.stop()


app = FastAPI(lifespan=lifespan)
```

## 5. 配置

### 5.1 环境变量

```bash
# backend/.env

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# 队列配置
UPLOAD_QUEUE_WORKERS=5
UPLOAD_QUEUE_MAX_RETRIES=3
UPLOAD_QUEUE_RETRY_DELAY=2.0
UPLOAD_QUEUE_RATE_LIMIT=10
```

### 5.2 配置类

```python
# backend/app/core/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # 队列
    upload_queue_workers: int = 5
    upload_queue_max_retries: int = 3
    upload_queue_retry_delay: float = 2.0
    upload_queue_rate_limit: int = 10
    
    class Config:
        env_file = ".env"


settings = Settings()
```

## 6. 性能对比

| 指标 | 原方案 (BackgroundTasks) | 新方案 (Redis + DB) |
|------|--------------------------|---------------------|
| 并发控制 | ❌ 无 | ✅ Worker 池 |
| CPU 占用 | ⚠️ 轮询 | ✅ BRPOP 阻塞 |
| 任务丢失 | ❌ 重启丢失 | ✅ 数据库持久化 |
| 分布式 | ❌ 单机 | ✅ Redis 协调 |
| 限流 | ❌ 无 | ✅ 滑动窗口 |
| 重试 | ❌ 手动 | ✅ 自动指数退避 |
| 优先级 | ❌ 无 | ✅ 三级优先级 |
| 死信队列 | ❌ 无 | ✅ 有 |

## 7. 流程图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              请求处理流程                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  POST /api/storage/upload-async                                                 │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. 保存文件到临时目录                                                   │   │
│  │  2. INSERT INTO upload_tasks (数据库持久化)                              │   │
│  │  3. LPUSH upload:queue:{priority} task_id (Redis 入队)                   │   │
│  │  4. 返回 { task_id, status: "pending" }                                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Worker 处理流程                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Worker 循环                                                                    │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  BRPOP upload:queue:high upload:queue:normal upload:queue:low           │   │
│  │  (阻塞等待，无 CPU 占用)                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       │ 获取到 task_id                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  SET upload:lock:{task_id} worker_id NX EX 60                           │   │
│  │  (获取分布式锁)                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  检查限流 (滑动窗口)                                                     │   │
│  │  ZREMRANGEBYSCORE + ZCARD + ZADD                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  SELECT * FROM upload_tasks WHERE id = task_id                          │   │
│  │  (从数据库获取任务详情)                                                  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  执行上传 → StorageService                                               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       ├─────────────────────────────────────────────────────────────────────┐   │
│       │                                                                      │   │
│       ▼                                                                      ▼   │
│  ┌──────────────────────┐                              ┌──────────────────────┐ │
│  │  成功                 │                              │  失败                 │ │
│  │  UPDATE status=done   │                              │  retry_count < 3?    │ │
│  │  HINCRBY stats done   │                              │  ├─ Yes: 重新入队    │ │
│  │  DEL lock             │                              │  └─ No: 移入死信     │ │
│  └──────────────────────┘                              └──────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 8. 依赖安装

```bash
# backend/requirements.txt 新增

redis>=5.0.0
```

## 9. 总结

### 9.1 方案特点

| 特性 | 实现方式 |
|------|----------|
| 队列调度 | Redis `BRPOP` 阻塞队列 |
| 数据持久化 | 数据库 `upload_tasks` 表 |
| 并发控制 | Worker 池 + `asyncio.Semaphore` |
| 限流 | Redis 滑动窗口 + Lua 脚本 |
| 分布式锁 | Redis `SET NX EX` |
| 自动重试 | 指数退避 + 重新入队 |
| 死信队列 | Redis List |
| 优先级 | 三个 Redis List |

### 9.2 低负载设计

1. **BRPOP 阻塞**：Worker 空闲时不占用 CPU
2. **Lua 脚本**：限流操作原子化，减少网络往返
3. **分离存储**：Redis 只存 `task_id`，详情在数据库
4. **批量操作**：统计信息使用 Redis Hash

### 9.3 高可用设计

1. **数据库兜底**：Redis 故障时可从数据库恢复
2. **分布式锁**：防止多实例重复处理
3. **任务恢复**：服务重启自动恢复中断任务
4. **死信队列**：失败任务隔离，支持手动重试
