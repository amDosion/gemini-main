# Worker 池错误处理文档

## 1. 概述

本文档整理了 `UploadWorkerPool` 在处理上传任务时可能遇到的错误类型、错误处理机制以及重试策略。

## 2. 错误类型分类

### 2.1 文件来源错误

| 错误信息 | 原因 | 处理方式 |
|----------|------|----------|
| `无可用的文件来源` | `source_file_path` 和 `source_url` 都为空或无效 | 标记为失败，不重试 |
| `文件不存在` | `source_file_path` 指向的文件已被删除 | 重试（可能是临时问题） |
| `下载失败: HTTP xxx` | 从 `source_url` 下载图片时网络错误 | 重试（指数退避） |

### 2.2 存储配置错误

| 错误信息 | 原因 | 处理方式 |
|----------|------|----------|
| `未设置存储配置` | 数据库中没有激活的存储配置 | 标记为失败，不重试 |
| `存储配置不存在` | 指定的 `storage_id` 在数据库中不存在 | 标记为失败，不重试 |
| `存储配置不可用` | 存储配置已禁用（`enabled=False`） | 标记为失败，不重试 |
| `存储配置已禁用` | 同上 | 标记为失败，不重试 |

### 2.3 云存储上传错误

| 错误信息 | 原因 | 处理方式 |
|----------|------|----------|
| `上传失败` | 云存储 API 返回错误 | 重试（指数退避） |
| `兰空图床配置不完整` | 缺少 `domain` 或 `token` | 标记为失败，不重试 |
| `HTTP 401/403` | API 密钥无效或过期 | 重试（可能是临时问题） |
| `HTTP 500/502/503` | 云存储服务端错误 | 重试（指数退避） |
| `连接超时` | 网络问题或云存储服务不可达 | 重试（指数退避） |

### 2.4 数据库错误

| 错误信息 | 原因 | 处理方式 |
|----------|------|----------|
| `任务不存在` | 任务 ID 在数据库中找不到 | 跳过，不处理 |
| `任务状态异常` | 任务状态不是 `pending` | 跳过，不处理 |
| `更新会话失败` | 更新 `ChatSession.messages` 时出错 | 记录日志，任务仍标记为成功 |

### 2.5 Redis 错误

| 错误信息 | 原因 | 处理方式 |
|----------|------|----------|
| `Redis 未连接` | `redis_queue._redis` 为 `None` | 尝试重新连接 |
| `获取锁失败` | 分布式锁被其他 Worker 持有 | 跳过，任务会被其他 Worker 处理 |
| `限流等待超时` | 超过 30 秒仍未获取限流令牌 | 重新入队，稍后处理 |

## 3. 重试机制

### 3.1 重试策略

```
最大重试次数: 3 次（可配置）
重试延迟: 指数退避
  - 第 1 次重试: 2 秒后
  - 第 2 次重试: 4 秒后
  - 第 3 次重试: 8 秒后
重试优先级: low（降低优先级，避免阻塞新任务）
```

### 3.2 重试流程

```
任务失败
    │
    ▼
retry_count < max_retries ?
    │
    ├─ Yes ──► 更新状态为 pending
    │          等待 delay 秒
    │          重新入队（低优先级）
    │          更新 Redis 统计（total_retried）
    │
    └─ No ───► 更新状态为 failed
               移入死信队列
               更新 Redis 统计（total_failed）
```

### 3.3 代码实现

```python
async def _handle_failure(self, db, task_id: str, error: str, worker_name: str):
    task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
    if not task:
        return

    # 递增重试次数
    retry_count = (task.retry_count or 0) + 1
    task.retry_count = retry_count
    task.error_message = f"{error} (重试 {retry_count}/{self.max_retries})"

    if retry_count < self.max_retries:
        # 指数退避
        delay = self.base_retry_delay * (2 ** (retry_count - 1))
        
        task.status = 'pending'
        db.commit()
        
        # 延迟后重新入队
        await asyncio.sleep(delay)
        await redis_queue.enqueue(task_id, 'low')
        await redis_queue.update_stats("total_retried")
    else:
        # 最终失败
        task.status = 'failed'
        task.completed_at = int(datetime.now().timestamp() * 1000)
        db.commit()
        
        # 移入死信队列
        await redis_queue.move_to_dead_letter(task_id)
        await redis_queue.update_stats("total_failed")
```

## 4. 死信队列

### 4.1 什么是死信队列

死信队列（Dead Letter Queue）用于存储**重试次数耗尽仍然失败**的任务。这些任务需要人工干预处理。

### 4.2 死信队列操作

| 操作 | Redis Key | 说明 |
|------|-----------|------|
| 入队 | `upload:dead_letter` | `LPUSH` 任务 ID |
| 查看 | `GET /api/storage/dead-letter` | 获取死信任务列表 |
| 重试 | `POST /api/storage/dead-letter/retry/{task_id}` | 从死信队列移出并重新入队 |

### 4.3 死信任务处理建议

1. **检查错误信息**：查看 `error_message` 字段了解失败原因
2. **修复配置问题**：如果是存储配置问题，先修复配置
3. **手动重试**：调用 `/api/storage/dead-letter/retry/{task_id}` 重试
4. **清理无效任务**：如果任务确实无法处理，可以手动删除

## 5. 监控指标

### 5.1 Redis 统计

```
upload:stats (Hash)
  - total_enqueued: 总入队数
  - total_completed: 总完成数
  - total_failed: 总失败数
  - total_retried: 总重试数
  - total_dead: 死信队列数
```

### 5.2 获取统计

```bash
# API 方式
GET /api/storage/queue/stats

# Redis CLI 方式
HGETALL upload:stats
LLEN upload:queue:high
LLEN upload:queue:normal
LLEN upload:queue:low
LLEN upload:dead_letter
```

## 6. 常见问题排查

### 6.1 任务一直处于 `pending` 状态

**可能原因**：
1. Worker 池未启动
2. Redis 连接失败
3. 任务未入队 Redis

**排查步骤**：
1. 检查后端启动日志，确认 `[WorkerPool] ✅ 已启动 5 个 Worker`
2. 检查 Redis 连接，确认 `[RedisQueue] ✅ 已连接`
3. 手动将任务入队：运行 `requeue_pending_tasks.py`

### 6.2 任务失败但没有重试

**可能原因**：
1. 错误类型不支持重试（如配置错误）
2. 已达到最大重试次数

**排查步骤**：
1. 查看任务的 `error_message` 字段
2. 查看任务的 `retry_count` 字段
3. 检查死信队列

### 6.3 上传成功但会话未更新

**可能原因**：
1. `session_id`、`message_id`、`attachment_id` 为空
2. 消息尚未保存到数据库（竞态条件）
3. 附件 ID 不匹配

**排查步骤**：
1. 检查任务的关联 ID 是否正确
2. 查看后端日志中的 `[UploadTask] ⏳ 未找到附件` 信息
3. 确认前端是否正确保存了消息

## 7. 配置参数

| 参数 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| Worker 数量 | `UPLOAD_QUEUE_WORKERS` | 5 | 并发处理任务的 Worker 数量 |
| 最大重试次数 | `UPLOAD_QUEUE_MAX_RETRIES` | 3 | 任务失败后的最大重试次数 |
| 重试基础延迟 | `UPLOAD_QUEUE_RETRY_DELAY` | 2.0 | 第一次重试的延迟（秒） |
| 限流速率 | `UPLOAD_QUEUE_RATE_LIMIT` | 10 | 每秒最大请求数 |

## 8. 错误处理流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Worker 任务处理流程                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BRPOP 获取任务                                                             │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────┐                                                        │
│  │  获取分布式锁   │──── 失败 ────► 跳过，任务会被其他 Worker 处理          │
│  └────────┬────────┘                                                        │
│           │ 成功                                                             │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  等待限流令牌   │──── 超时 ────► 重新入队，稍后处理                      │
│  └────────┬────────┘                                                        │
│           │ 获取成功                                                         │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  查询任务详情   │──── 不存在 ──► 跳过                                    │
│  └────────┬────────┘                                                        │
│           │ 存在                                                             │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  检查任务状态   │──── 非 pending ──► 跳过                                │
│  └────────┬────────┘                                                        │
│           │ pending                                                          │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  获取文件内容   │──── 失败 ────► _handle_failure()                       │
│  └────────┬────────┘                                                        │
│           │ 成功                                                             │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  获取存储配置   │──── 失败 ────► _handle_failure()                       │
│  └────────┬────────┘                                                        │
│           │ 成功                                                             │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  执行上传       │──── 失败 ────► _handle_failure()                       │
│  └────────┬────────┘                                                        │
│           │ 成功                                                             │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │  _handle_success│                                                        │
│  │  - 更新任务状态 │                                                        │
│  │  - 删除临时文件 │                                                        │
│  │  - 更新会话附件 │                                                        │
│  │  - 更新统计     │                                                        │
│  └─────────────────┘                                                        │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  _handle_failure() 流程                                                     │
│       │                                                                      │
│       ▼                                                                      │
│  retry_count++                                                              │
│       │                                                                      │
│       ▼                                                                      │
│  retry_count < max_retries ?                                                │
│       │                                                                      │
│       ├─ Yes ──► status = 'pending'                                         │
│       │          sleep(delay)                                               │
│       │          enqueue(task_id, 'low')                                    │
│       │          update_stats('total_retried')                              │
│       │                                                                      │
│       └─ No ───► status = 'failed'                                          │
│                  move_to_dead_letter(task_id)                               │
│                  update_stats('total_failed')                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
