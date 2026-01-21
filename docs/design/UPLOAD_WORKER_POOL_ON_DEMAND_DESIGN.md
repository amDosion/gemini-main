# Upload Worker Pool 按需调用设计方案

## 1. 当前完整调用链

### 1.1 谁在调用 Worker？（任务来源）

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          TASK CREATION SOURCES                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  1️⃣ 用户上传文件                                                                │
│     POST /api/storage/upload-async                                              │
│     └─> storage.py:561                                                          │
│         └─> AttachmentService.process_user_upload()                            │
│             └─> AttachmentService._submit_upload_task()                        │
│                 ├─> 创建 UploadTask 记录 (DB)                                   │
│                 └─> redis_queue.enqueue(task_id, priority)                     │
│                                                                                  │
│  2️⃣ 从 URL 下载后上传                                                           │
│     POST /api/storage/upload-from-url                                           │
│     └─> storage.py:733                                                          │
│         ├─> 创建 UploadTask 记录 (DB)                                           │
│         └─> redis_queue.enqueue(task_id, priority)                             │
│                                                                                  │
│  3️⃣ AI 返回图片处理                                                             │
│     AI生成图片 -> attachment_service.py:129                                     │
│     └─> AttachmentService.process_ai_result()                                  │
│         └─> AttachmentService._submit_upload_task()                            │
│             ├─> 创建 UploadTask 记录 (DB)                                       │
│             └─> redis_queue.enqueue(task_id, priority)                         │
│                                                                                  │
│  4️⃣ Continuity Logic（连续编辑）                                                │
│     编辑模式 -> attachment_service.py:259                                       │
│     └─> AttachmentService.resolve_continuity_attachment()                      │
│         └─> AttachmentService._submit_upload_task()  (if not uploaded)         │
│             ├─> 创建 UploadTask 记录 (DB)                                       │
│             └─> redis_queue.enqueue(task_id, priority)                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 关键代码位置

| 组件 | 文件 | 行号 | 职责 |
|------|------|------|------|
| **任务入口1** | storage.py | 561 | `/upload-async` 端点 |
| **任务入口2** | storage.py | 733 | `/upload-from-url` 端点 |
| **任务入口3** | attachment_service.py | 129 | `process_ai_result()` |
| **任务入口4** | attachment_service.py | 259 | `resolve_continuity_attachment()` |
| **任务提交** | attachment_service.py | 470 | `_submit_upload_task()` |
| **Redis入队** | redis_queue_service.py | 151 | `enqueue()` |
| **Redis出队** | redis_queue_service.py | 191 | `dequeue()` (BRPOP) |
| **Worker循环** | upload_worker_pool.py | 320 | `_worker_loop()` |
| **Worker启动** | upload_worker_pool.py | 71 | `start()` 预创建5个Worker |

---

## 2. 当前架构（问题分析）

### 2.1 当前架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       CURRENT ARCHITECTURE (PROBLEMATIC)                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  API Endpoints (任务生产者)                                                      │
│  ┌──────────────────────┐                                                       │
│  │ /upload-async        │─┐                                                     │
│  │ /upload-from-url     │─┼──> AttachmentService._submit_upload_task()          │
│  │ AI result processing │─┤         │                                           │
│  │ Continuity logic     │─┘         ▼                                           │
│  └──────────────────────┘    ┌─────────────────────────┐                        │
│                              │  1. Create UploadTask   │                        │
│                              │     record in DB        │                        │
│                              │  2. redis_queue.enqueue │                        │
│                              └──────────┬──────────────┘                        │
│                                         │                                        │
│                                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     Redis Queue (upload:queue:*)                          │   │
│  │                                                                           │   │
│  │   upload:queue:high   ─┬                                                  │   │
│  │   upload:queue:normal ─┼─> BRPOP (blocking pop by priority)               │   │
│  │   upload:queue:low    ─┘                                                  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                        │
│                                         │ BRPOP (阻塞等待)                        │
│                                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    Worker Pool (启动时预创建 5 个)                         │   │
│  │                                                                           │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │   │
│  │  │Worker-0 │ │Worker-1 │ │Worker-2 │ │Worker-3 │ │Worker-4 │            │   │
│  │  │(BRPOP)  │ │(BRPOP)  │ │(BRPOP)  │ │(BRPOP)  │ │(BRPOP)  │            │   │
│  │  │waiting..│ │waiting..│ │waiting..│ │waiting..│ │waiting..│            │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘            │   │
│  │                                                                           │   │
│  │  ❌ 问题：即使没有任务，5个协程始终在阻塞等待                               │   │
│  │  ❌ 问题：每50秒输出 "Still waiting for tasks..." 日志                     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 当前问题

1. **资源浪费**：5 个 Worker 协程始终在阻塞等待，即使没有任务
2. **日志噪音**：每 50 秒输出一次 "Still waiting for tasks..." 日志
3. **固定并发**：无法根据负载动态调整 Worker 数量
4. **启动开销**：应用启动时必须初始化所有 Workers

---

## 3. 按需调用架构（懒启动 Worker）

### 3.1 核心理念

**按需调用 = 没有任务时，没有任何后台服务运行**

- 保留 Redis 队列架构
- Worker 只在有任务时启动
- 队列为空时 Worker 自动退出

### 3.2 目标架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ON-DEMAND ARCHITECTURE (LAZY WORKER)                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  API Endpoints (任务生产者)                                                      │
│  ┌──────────────────────┐                                                       │
│  │ /upload-async        │─┐                                                     │
│  │ /upload-from-url     │─┼──> AttachmentService._submit_upload_task()          │
│  │ AI result processing │─┤         │                                           │
│  │ Continuity logic     │─┘         │                                           │
│  └──────────────────────┘           │                                           │
│                                     ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                      _submit_upload_task() (修改后)                        │   │
│  │                                                                           │   │
│  │   1. 创建 UploadTask 记录 (DB)                                            │   │
│  │   2. redis_queue.enqueue(task_id, priority)                              │   │
│  │   3. ✅ 新增：worker_pool.ensure_worker_running()                         │   │
│  │      └─> 如果没有 Worker 运行，启动一个                                    │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  空闲时：                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        (无任何后台服务运行)                                 │   │
│  │                                                                           │   │
│  │                              ∅                                            │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  有任务时（懒启动 Worker）：                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                           │   │
│  │   任务入队时 → ensure_worker_running() → 启动 Worker                       │   │
│  │                                                                           │   │
│  │   ┌─────────┐                                                             │   │
│  │   │ Worker  │ ← 按需启动                                                  │   │
│  │   │ (BRPOP) │                                                             │   │
│  │   │processing│                                                            │   │
│  │   └────┬────┘                                                             │   │
│  │        │                                                                   │   │
│  │        ▼                                                                   │   │
│  │   队列为空 + 无 pending 任务 → Worker 自动退出                              │   │
│  │                                                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 详细设计

### 4.1 修改 attachment_service.py

```python
# attachment_service.py - 修改 _submit_upload_task()

from ..common.upload_worker_pool import worker_pool

async def _submit_upload_task(self, ...):
    task_id = str(uuid.uuid4())

    # 1. 创建 UploadTask 记录
    task = UploadTask(
        id=task_id,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        source_file_path=source_file_path,
        source_ai_url=source_ai_url,
        filename=filename,
        priority=priority,
        storage_id=storage_id,
        status='pending',
        created_at=int(datetime.now().timestamp() * 1000)
    )
    self.db.add(task)
    self.db.commit()

    # 2. 入队 Redis
    await redis_queue.enqueue(task_id, priority)

    # 3. ✅ 新增：确保有 Worker 在运行（懒启动）
    await worker_pool.ensure_worker_running()

    logger.info(f"[AttachmentService] 任务已入队: {task_id[:8]}...")
    return task_id
```

### 4.2 修改 upload_worker_pool.py

```python
class UploadWorkerPool:
    """
    上传 Worker 池（按需调用模式）

    特点：
    - 没有任务时不运行任何 Worker
    - 任务入队时懒启动 Worker
    - 队列为空时 Worker 自动退出
    """

    def __init__(self):
        self.max_workers = settings.upload_queue_workers  # 最大并发数
        self.max_retries = settings.upload_queue_max_retries
        self.base_retry_delay = settings.upload_queue_retry_delay
        self.idle_timeout = 10  # 队列空闲超时（秒），超时后 Worker 退出

        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._running = False

    async def ensure_worker_running(self):
        """
        确保有 Worker 在运行（懒启动）

        由 _submit_upload_task() 调用
        """
        async with self._lock:
            # 如果 Worker 没有运行，或者已完成，启动新的
            if self._worker_task is None or self._worker_task.done():
                self._running = True
                self._worker_task = asyncio.create_task(self._worker_loop())
                logger.info("[WorkerPool] ✅ Worker 已启动（按需）")

    async def _worker_loop(self):
        """
        Worker 主循环

        处理完所有任务后自动退出（按需调用模式）
        """
        worker_name = "Worker-0"
        logger.info(f"[{worker_name}] 开始处理任务...")

        idle_count = 0
        max_idle_count = self.idle_timeout // 5  # 5秒一次检查

        while self._running:
            try:
                # 从 Redis 队列获取任务（阻塞等待，最多5秒）
                task_id = await redis_queue.dequeue(timeout=5)

                if task_id:
                    # 有任务，重置空闲计数
                    idle_count = 0
                    await self._process_task(task_id, worker_name)
                else:
                    # 队列为空，增加空闲计数
                    idle_count += 1

                    # 检查是否还有 pending 任务（数据库中）
                    if idle_count >= max_idle_count:
                        if not await self._has_pending_tasks():
                            logger.info(f"[{worker_name}] 队列为空且无 pending 任务，Worker 退出")
                            break
                        else:
                            # 有 pending 任务但不在队列中，可能需要 reconcile
                            idle_count = 0  # 重置，继续等待

            except asyncio.CancelledError:
                logger.info(f"[{worker_name}] 收到停止信号")
                break
            except Exception as e:
                logger.error(f"[{worker_name}] 异常: {e}")
                await asyncio.sleep(1)

        self._running = False
        logger.info(f"[{worker_name}] 已退出")

    async def _has_pending_tasks(self) -> bool:
        """检查数据库中是否还有 pending 任务"""
        db = SessionLocal()
        try:
            count = db.query(UploadTask).filter(
                UploadTask.status.in_(['pending', 'uploading'])
            ).count()
            return count > 0
        finally:
            db.close()

    async def _process_task(self, task_id: str, worker_name: str):
        """处理单个任务（复用现有逻辑）"""
        # ... 现有的 _process_task 逻辑保持不变 ...
        pass

    async def stop(self):
        """停止 Worker（用于应用关闭时）"""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("[WorkerPool] Worker 已停止")


# 全局单例
worker_pool = UploadWorkerPool()
```

### 4.3 修改 main.py

```python
# main.py - 移除启动时的 worker_pool.start()

@app.on_event("startup")
async def startup():
    # 连接 Redis（保留）
    await redis_queue.connect()

    # ❌ 移除：不再启动时预创建 Worker
    # await worker_pool.start()

    # ✅ 恢复中断任务（可选，用于重启后恢复）
    await recover_interrupted_tasks()

    logger.info("[Startup] 应用启动完成（Worker 将按需启动）")


async def recover_interrupted_tasks():
    """恢复中断的上传任务"""
    db = SessionLocal()
    try:
        # 将 uploading 状态重置为 pending
        uploading_tasks = db.query(UploadTask).filter(
            UploadTask.status == 'uploading'
        ).all()

        for task in uploading_tasks:
            task.status = 'pending'

        db.commit()

        # 检查是否有 pending 任务需要处理
        pending_count = db.query(UploadTask).filter(
            UploadTask.status == 'pending'
        ).count()

        if pending_count > 0:
            logger.info(f"[Startup] 发现 {pending_count} 个待处理任务，启动 Worker...")
            # 将任务重新入队
            pending_tasks = db.query(UploadTask).filter(
                UploadTask.status == 'pending'
            ).all()
            for task in pending_tasks:
                await redis_queue.enqueue(task.id, task.priority or 'normal')
            # 启动 Worker
            await worker_pool.ensure_worker_running()
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown():
    await worker_pool.stop()
    await redis_queue.disconnect()
```

---

## 5. 与现有架构对比

| 特性 | 当前架构 | 按需架构 |
|------|---------|---------|
| **启动时 Worker 数** | 固定 5 个 | 0 个 |
| **空闲时 Worker 数** | 固定 5 个 | 0 个 |
| **空闲时资源占用** | 5 个协程阻塞 | 无 |
| **日志噪音** | 有（"Still waiting..."） | 无 |
| **队列支持** | 有 | 有（保留） |
| **削峰填谷** | 支持 | 支持 |
| **重启恢复** | 支持 | 支持 |

---

## 6. 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `attachment_service.py` | 入队后调用 `worker_pool.ensure_worker_running()` |
| `upload_worker_pool.py` | 重构为懒启动模式，添加 `ensure_worker_running()` 和自动退出逻辑 |
| `main.py` | 移除 `worker_pool.start()`，添加 `recover_interrupted_tasks()` |

---

## 7. 实现步骤

### Step 1: 修改 upload_worker_pool.py
1. 添加 `ensure_worker_running()` 方法
2. 修改 `_worker_loop()` 为单 Worker 模式，添加自动退出逻辑
3. 添加 `_has_pending_tasks()` 方法
4. 移除 `start()` 方法中预创建 Worker 的逻辑

### Step 2: 修改 attachment_service.py
1. 在 `_submit_upload_task()` 中入队后调用 `worker_pool.ensure_worker_running()`

### Step 3: 修改 main.py
1. 移除 `worker_pool.start()` 调用
2. 添加 `recover_interrupted_tasks()` 恢复逻辑

### Step 4: 测试验证
1. 验证空闲时无 Worker 运行
2. 验证任务入队时 Worker 能正确启动
3. 验证队列为空时 Worker 能正确退出
4. 验证重启后能恢复中断任务

---

## 8. 总结

**按需调用 = 没有任务时，没有任何后台服务运行**

- 保留 Redis 队列架构（支持削峰填谷）
- Worker 只在任务入队时启动
- 队列为空且无 pending 任务时 Worker 自动退出
- 空闲时零资源占用
