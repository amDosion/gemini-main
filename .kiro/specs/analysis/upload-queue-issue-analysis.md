# Redis + 数据库上传队列问题分析报告

## 文档信息

- **创建时间**：2025-12-17
- **分析范围**：异步上传队列系统
- **相关文件**：
  - `backend/app/services/redis_queue_service.py`
  - `backend/app/services/upload_worker_pool.py`
  - `backend/app/routers/storage.py`
  - `backend/app/main.py`

---

## 1. 问题背景

在实现 Redis + 数据库高并发上传队列方案后，发现上传任务未被正常处理。用户通过前端生成图片后，任务状态一直停留在 `pending`，未能成功上传到云存储。

---

## 2. 问题排查过程

### 2.1 初始现象

| 现象 | 描述 |
|------|------|
| 任务状态 | 数据库中任务状态为 `pending`，长时间未变化 |
| Redis 队列 | 队列长度为 0（任务未入队或已被取走） |
| Worker 日志 | 控制台未显示 Worker 处理任务的日志 |
| 上传结果 | 图片未上传到云存储 |

### 2.2 排查步骤

#### 步骤 1：验证 Redis 连接

**测试脚本**：`backend/test_redis_connection.py`

```python
import redis
r = redis.Redis(host='192.168.50.175', port=6379, password='941378', db=0)
print(r.ping())  # 返回 True
```

**结论**：✅ Redis 连接正常

#### 步骤 2：验证 Worker 池启动

**后端启动日志**：

```
[WorkerPool] 正在连接 Redis...
[WorkerPool] ✅ Redis 连接成功
[WorkerPool] 正在恢复中断任务...
[WorkerPool] 正在启动 5 个 Worker...
[WorkerPool] ✅ 已启动 5 个 Worker
```

**结论**：✅ Worker 池启动成功

#### 步骤 3：检查数据库任务记录

**SQL 查询**：

```sql
SELECT id, filename, status, priority, retry_count, error_message 
FROM upload_tasks 
WHERE status = 'pending';
```

**发现**：

| id | filename | status | priority | retry_count | error_message |
|----|----------|--------|----------|-------------|---------------|
| xxx... | image-1.png | pending | NULL | NULL | NULL |
| xxx... | image-2.png | pending | NULL | NULL | NULL |

**关键发现**：`priority` 字段为 `NULL`

#### 步骤 4：分析代码逻辑

检查 `storage.py` 中的 `/upload-async` 端点：

```python
# 旧代码（问题代码）
task = UploadTask(
    id=task_id,
    source_file_path=temp_path,
    filename=file.filename,
    status='pending',
    # ❌ 缺少 priority 字段赋值
    # ❌ 缺少 Redis 入队逻辑
)
db.add(task)
db.commit()
# ❌ 没有调用 redis_queue.enqueue()
```

**结论**：❌ 旧代码未将任务入队 Redis

---

## 3. 根本原因

### 3.1 主要问题：任务未入队 Redis

**原因**：在添加 Redis 队列功能之前创建的任务，只保存到了数据库，但没有入队 Redis。

**影响**：
- Worker 池使用 `BRPOP` 从 Redis 队列获取任务
- 数据库中的任务没有对应的 Redis 队列条目
- Worker 无法感知这些任务的存在

### 3.2 次要问题：字段默认值未生效

**原因**：SQLAlchemy 模型的 `default` 参数只在 Python 层生效，数据库列没有 `DEFAULT` 约束。

```python
# models/db_models.py
class UploadTask(Base):
    priority = Column(String(20), default='normal')  # Python 层默认值
    retry_count = Column(Integer, default=0)         # Python 层默认值
```

**影响**：如果代码中遗漏赋值，字段会是 `NULL` 而非默认值。

### 3.3 次要问题：Worker 日志被缓冲

**原因**：Python 的 `print()` 和 `logger` 输出被 uvicorn 缓冲，未实时显示。

**影响**：无法通过日志监控 Worker 的实时工作状态。

---

## 4. 问题验证

### 4.1 手动入队测试

**测试脚本**：`backend/test_worker_processing.py`

```python
# 手动将 pending 任务入队 Redis
for task in pending_tasks:
    await redis_queue.enqueue(task.id, 'normal')
```

**结果**：
- 任务入队后立即被 Worker 取走（队列长度始终为 0）
- 任务状态变化：`pending` → `uploading` → `completed`
- 图片成功上传到云存储

**结论**：✅ Worker 池工作正常，问题在于任务未入队

### 4.2 完整流程测试

通过前端生成新图片，验证修复后的完整流程：

1. 前端调用 `/api/storage/upload-async`
2. 后端保存文件到临时目录
3. 后端创建数据库记录（包含 `priority`、`retry_count`）
4. 后端调用 `redis_queue.enqueue(task_id, priority)`
5. Worker 从 Redis 获取任务
6. Worker 上传到云存储
7. Worker 更新数据库状态和会话附件 URL

**结论**：✅ 完整流程正常工作

---

## 5. 解决方案

### 5.1 已实施的修复

#### 修复 1：完善入队逻辑

**文件**：`backend/app/routers/storage.py`

```python
@router.post("/upload-async")
async def upload_file_async(...):
    # 1. 保存文件
    # 2. 创建数据库记录（包含 priority、retry_count）
    task = UploadTask(
        id=task_id,
        priority=priority,      # ✅ 显式赋值
        retry_count=0,          # ✅ 显式赋值
        status='pending',
        ...
    )
    db.add(task)
    db.commit()
    
    # 3. 入队 Redis ✅
    queue_position = await redis_queue.enqueue(task_id, priority)
    
    return {"task_id": task_id, "queue_position": queue_position}
```

#### 修复 2：添加 Redis 连接检查

**文件**：`backend/app/services/redis_queue_service.py`

```python
async def enqueue(self, task_id: str, priority: str = "normal") -> int:
    # ✅ 检查连接状态
    if self._redis is None:
        logger.error("[RedisQueue] ❌ Redis 未连接！")
        raise RuntimeError("Redis 未连接")
    
    # 入队逻辑...
```

#### 修复 3：强制日志输出

**文件**：`backend/app/services/upload_worker_pool.py`

```python
async def _worker_loop(self, worker_id: int):
    import sys
    worker_name = f"worker-{worker_id}"
    
    # ✅ 使用 stderr + flush 强制输出
    msg = f"[WorkerPool] {worker_name} started\n"
    sys.stderr.write(msg)
    sys.stderr.flush()
```

### 5.2 历史任务处理

对于已存在的 `pending` 任务（`priority` 为 `NULL`），需要手动重新入队：

```python
# backend/requeue_pending_tasks.py
import asyncio
from app.core.database import SessionLocal
from app.models.db_models import UploadTask
from app.services.redis_queue_service import redis_queue

async def requeue_pending_tasks():
    await redis_queue.connect()
    
    db = SessionLocal()
    tasks = db.query(UploadTask).filter(UploadTask.status == 'pending').all()
    
    for task in tasks:
        task.priority = task.priority or 'normal'
        task.retry_count = task.retry_count or 0
        await redis_queue.enqueue(task.id, task.priority)
        print(f"已入队: {task.id[:8]}...")
    
    db.commit()
    db.close()
    await redis_queue.disconnect()

asyncio.run(requeue_pending_tasks())
```

---

## 6. 系统架构说明

### 6.1 数据流图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        异步上传队列数据流                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  前端                                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  1. 生成图片                                                     │   │
│  │  2. POST /api/storage/upload-async                               │   │
│  │  3. 获取 task_id，显示上传中状态                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                      │                                  │
│                                      ▼                                  │
│  后端 API                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  1. 保存文件到临时目录                                           │   │
│  │  2. 创建 UploadTask 记录 → PostgreSQL                            │   │
│  │  3. task_id 入队 → Redis                                         │   │
│  │  4. 返回 task_id（不阻塞）                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                      │                                  │
│       ┌──────────────────────────────┴──────────────────────────┐      │
│       │                                                          │      │
│       ▼                                                          ▼      │
│  ┌─────────────────────┐                          ┌─────────────────┐  │
│  │      Redis          │                          │   PostgreSQL    │  │
│  │                     │                          │                 │  │
│  │  upload:queue:high  │                          │  upload_tasks   │  │
│  │  upload:queue:normal│◄─────── task_id ────────►│  - id           │  │
│  │  upload:queue:low   │                          │  - status       │  │
│  │                     │                          │  - target_url   │  │
│  │  upload:stats       │                          │  - error_msg    │  │
│  │  upload:lock:*      │                          │                 │  │
│  └─────────────────────┘                          └─────────────────┘  │
│       │                                                          │      │
│       └──────────────────────────────┬──────────────────────────┘      │
│                                      │                                  │
│                                      ▼                                  │
│  Worker 池（5 个 Worker）                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  1. BRPOP 从 Redis 获取 task_id（阻塞等待）                      │   │
│  │  2. 获取分布式锁（防止重复处理）                                 │   │
│  │  3. 限流检查（10 req/s）                                         │   │
│  │  4. 从 PostgreSQL 获取任务详情                                   │   │
│  │  5. 读取文件内容（source_file_path 或 source_url）               │   │
│  │  6. 上传到云存储（兰空图床）                                     │   │
│  │  7. 更新 PostgreSQL（status、target_url）                        │   │
│  │  8. 更新会话附件 URL                                             │   │
│  │  9. 释放分布式锁                                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 错误处理流程

```
任务处理失败
    │
    ▼
retry_count < 3 ?
    │
    ├─ Yes ──► 指数退避（2s → 4s → 8s）
    │          重新入队（低优先级）
    │          更新 retry_count
    │
    └─ No ───► 标记为 failed
               移入死信队列
               等待人工处理
```

---

## 7. 配置参数

| 参数 | 环境变量 | 当前值 | 说明 |
|------|----------|--------|------|
| Redis 主机 | `REDIS_HOST` | `192.168.50.175` | Redis 服务器地址 |
| Redis 端口 | `REDIS_PORT` | `6379` | Redis 端口 |
| Redis 密码 | `REDIS_PASSWORD` | `941378` | Redis 认证密码 |
| Redis 数据库 | `REDIS_DB` | `0` | Redis 数据库编号 |
| Worker 数量 | `UPLOAD_QUEUE_WORKERS` | `5` | 并发 Worker 数量 |
| 最大重试次数 | `UPLOAD_QUEUE_MAX_RETRIES` | `3` | 任务失败重试次数 |
| 重试基础延迟 | `UPLOAD_QUEUE_RETRY_DELAY` | `2.0` | 第一次重试延迟（秒） |
| 限流速率 | `UPLOAD_QUEUE_RATE_LIMIT` | `10` | 每秒最大请求数 |

---

## 8. 监控与诊断

### 8.1 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/storage/queue/stats` | GET | 获取队列统计信息 |
| `/api/storage/upload-status/{task_id}` | GET | 查询任务状态 |
| `/api/storage/dead-letter` | GET | 获取死信队列任务 |
| `/api/storage/dead-letter/retry/{task_id}` | POST | 重试死信任务 |

### 8.2 诊断脚本

| 脚本 | 路径 | 说明 |
|------|------|------|
| Redis 连接测试 | `backend/test_redis_connection.py` | 验证 Redis 连接 |
| 数据库诊断 | `backend/check_upload_tasks.py` | 查看任务状态 |
| 系统诊断 | `backend/diagnose_system.py` | 完整系统检查 |
| Worker 测试 | `backend/test_worker_processing.py` | 测试 Worker 处理 |

### 8.3 Redis CLI 命令

```bash
# 查看队列长度
LLEN upload:queue:high
LLEN upload:queue:normal
LLEN upload:queue:low

# 查看统计信息
HGETALL upload:stats

# 查看死信队列
LLEN upload:dead_letter
LRANGE upload:dead_letter 0 -1
```

---

## 9. 总结

### 9.1 问题根因

**任务未入队 Redis**：旧代码只将任务保存到数据库，没有调用 `redis_queue.enqueue()` 将任务入队 Redis，导致 Worker 无法获取任务。

### 9.2 解决状态

| 问题 | 状态 | 说明 |
|------|------|------|
| 任务未入队 Redis | ✅ 已修复 | 添加了 Redis 入队逻辑 |
| 字段默认值 | ✅ 已修复 | 代码中显式赋值 |
| Worker 日志缓冲 | ✅ 已修复 | 使用 stderr + flush |
| 历史 pending 任务 | ✅ 已处理 | 手动重新入队 |

### 9.3 当前系统状态

- ✅ Redis 连接正常
- ✅ Worker 池运行正常
- ✅ 任务入队逻辑正常
- ✅ 上传流程正常
- ✅ 错误重试机制正常

---

## 10. 后续建议

1. **添加数据库级默认值**：通过迁移脚本为 `priority` 和 `retry_count` 列添加 `DEFAULT` 约束
2. **添加监控告警**：当死信队列长度超过阈值时发送告警
3. **添加健康检查**：定期检查 Redis 连接和 Worker 池状态
4. **日志持久化**：将 Worker 日志写入文件，便于问题排查
