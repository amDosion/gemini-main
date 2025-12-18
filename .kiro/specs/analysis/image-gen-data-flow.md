# 图片生成模式（Gen）完整数据流程

## 1. 流程图

```mermaid
flowchart TD
    subgraph 前端["前端 (Frontend)"]
        A[用户输入提示词] --> B[调用 LLM API 生成图片]
        B --> C[LLM 返回临时 URL]
        C --> D[下载图片创建 Blob URL]
        D --> E[立即显示图片<br/>uploadStatus=pending]
        E --> F[调用 uploadFileAsync]
    end

    subgraph 后端API["后端 API (Backend)"]
        F --> G[保存文件到 backend/temp/]
        G --> H[创建 upload_tasks 记录<br/>status=pending]
        H --> I[task_id 入队 Redis]
        I --> J[返回 task_id]
    end

    subgraph Redis["Redis 队列"]
        I --> K[upload:queue:normal<br/>LPUSH task_id]
    end

    subgraph Worker["Worker 池 (5个并发)"]
        K --> L[BRPOP 获取任务]
        L --> M[获取分布式锁]
        M --> N[限流检查 10req/s]
        N --> O[查询数据库任务详情]
        O --> P[读取临时文件]
        P --> Q[获取存储配置]
        Q --> R[上传到兰空图床]
        R --> S{上传成功?}
        S -->|是| T[更新 upload_tasks<br/>status=completed]
        S -->|否| U[重试或移入死信队列]
        T --> V[删除临时文件]
        V --> W[⭐ 写入永久 URL 到<br/>chat_sessions.messages]
        W --> X[释放分布式锁]
    end

    subgraph 数据库["PostgreSQL 数据库"]
        H --> DB1[(upload_tasks)]
        T --> DB1
        W --> DB2[(chat_sessions.messages<br/>attachments.url = 永久URL<br/>attachments.uploadStatus = completed)]
    end

    subgraph 云存储["兰空图床"]
        R --> Cloud[(永久存储)]
    end

    style A fill:#e1f5fe
    style E fill:#c8e6c9
    style T fill:#c8e6c9
    style U fill:#ffcdd2
    style Cloud fill:#fff9c4
    style W fill:#fff176
    style DB2 fill:#fff176
```

---

## 2. 详细步骤与文件对应

```mermaid
flowchart LR
    subgraph Step1["步骤 1-4: 前端生成与显示"]
        direction TB
        S1[imageGenHandler.ts<br/>handleImageGen] --> S2[llmService.generateImage]
        S2 --> S3[fetch 下载图片]
        S3 --> S4[URL.createObjectURL]
    end

    subgraph Step2["步骤 5: 提交上传任务"]
        direction TB
        S5[storageUpload.ts<br/>uploadFileAsync] --> S6[POST /api/storage/upload-async]
    end

    subgraph Step3["步骤 6-7: 后端接收入队"]
        direction TB
        S7[storage.py<br/>upload_file_async] --> S8[保存到 backend/temp/]
        S8 --> S9[创建 UploadTask]
        S9 --> S10[redis_queue.enqueue]
    end

    subgraph Step4["步骤 8-15: Worker 处理"]
        direction TB
        S11[upload_worker_pool.py<br/>_worker_loop] --> S12[redis_queue.dequeue]
        S12 --> S13[_process_task]
        S13 --> S14[StorageService.upload_file]
        S14 --> S15[_handle_success]
    end

    Step1 --> Step2 --> Step3 --> Step4
```

---

## 3. 文件路径清单

### 前端文件

| 步骤 | 文件路径 | 函数/方法 |
|------|----------|-----------|
| 1-4 | `D:\gemini-main\gemini-main\frontend\hooks\handlers\imageGenHandler.ts` | `handleImageGen()` |
| 5 | `D:\gemini-main\gemini-main\frontend\services\storage\storageUpload.ts` | `uploadFileAsync()` |

### 后端文件

| 步骤 | 文件路径 | 函数/方法 |
|------|----------|-----------|
| 6-7 | `D:\gemini-main\gemini-main\backend\app\routers\storage.py` | `upload_file_async()` |
| 7 | `D:\gemini-main\gemini-main\backend\app\services\redis_queue_service.py` | `enqueue()` |
| 8-15 | `D:\gemini-main\gemini-main\backend\app\services\upload_worker_pool.py` | `_worker_loop()`, `_process_task()` |
| 13 | `D:\gemini-main\gemini-main\backend\app\services\storage_service.py` | `upload_file()` |

### 数据模型

| 文件路径 | 说明 |
|----------|------|
| `D:\gemini-main\gemini-main\backend\app\models\db_models.py` | `UploadTask`, `ChatSession` 模型 |

### 临时文件目录

| 路径 | 说明 |
|------|------|
| `D:\gemini-main\gemini-main\backend\temp\` | 上传前的临时文件存储 |

---

## 4. 数据流转图

```mermaid
sequenceDiagram
    participant User as 用户
    participant FE as 前端<br/>imageGenHandler.ts
    participant API as 后端 API<br/>storage.py
    participant Redis as Redis<br/>redis_queue_service.py
    participant Worker as Worker 池<br/>upload_worker_pool.py
    participant Storage as 云存储<br/>storage_service.py
    participant DB as PostgreSQL

    User->>FE: 输入提示词
    FE->>FE: 调用 LLM 生成图片
    FE->>FE: 下载图片，创建 Blob URL
    FE->>User: 立即显示图片 (pending)
    
    FE->>API: POST /upload-async (File)
    API->>API: 保存到 backend/temp/
    API->>DB: INSERT upload_tasks (pending)
    API->>Redis: LPUSH task_id
    API->>FE: 返回 task_id
    
    Worker->>Redis: BRPOP 获取任务
    Redis->>Worker: task_id
    Worker->>DB: 查询任务详情
    Worker->>Worker: 读取临时文件
    Worker->>Storage: 上传到兰空图床
    Storage->>Worker: 返回永久 URL
    Worker->>DB: UPDATE status=completed
    Worker->>Worker: 删除临时文件
    Worker->>DB: UPDATE chat_sessions.messages
    
    User->>FE: 刷新页面
    FE->>DB: 查询会话
    DB->>FE: 返回永久 URL
    FE->>User: 显示云存储图片
```

---

## 5. 永久 URL 写入数据库流程（关键步骤）

这是整个流程中最关键的一步：Worker 上传成功后，需要将云存储的永久 URL 写入 `chat_sessions.messages` 表中。

```mermaid
flowchart TD
    subgraph Worker["Worker 处理成功后"]
        A[上传到兰空图床成功] --> B[获取永久 URL]
        B --> C[更新 upload_tasks 表<br/>status=completed<br/>target_url=永久URL]
        C --> D[删除临时文件]
        D --> E{session_id 存在?}
        E -->|是| F[调用 _update_session_attachment]
        E -->|否| G[跳过会话更新]
    end

    subgraph 更新会话["_update_session_attachment 方法"]
        F --> H[查询 chat_sessions 表]
        H --> I[深拷贝 messages JSON]
        I --> J[遍历查找 message_id]
        J --> K[遍历查找 attachment_id]
        K --> L{找到附件?}
        L -->|是| M[更新附件字段:<br/>url = 永久URL<br/>uploadStatus = completed]
        L -->|否| N[记录警告日志]
        M --> O[flag_modified 标记变更]
        O --> P[db.commit 提交]
    end

    subgraph 数据库["PostgreSQL"]
        P --> DB[(chat_sessions 表<br/>messages JSON 字段)]
    end

    style A fill:#c8e6c9
    style M fill:#fff176
    style DB fill:#fff176
```

### 5.1 数据库表结构

**`chat_sessions` 表的 `messages` 字段结构：**

```json
{
  "messages": [
    {
      "id": "msg-xxx",
      "role": "model",
      "content": "这是生成的图片",
      "attachments": [
        {
          "id": "att-xxx",
          "type": "image",
          "url": "https://cdn.lsky.pro/xxx.png",  // ⭐ 永久 URL（上传成功后更新）
          "uploadStatus": "completed",             // ⭐ 状态（pending → completed）
          "filename": "generated-1234567890.png"
        }
      ]
    }
  ]
}
```

### 5.2 关键代码位置

**文件**: `D:\gemini-main\gemini-main\backend\app\services\upload_worker_pool.py`

```python
# 第 290-330 行：_update_session_attachment 方法
async def _update_session_attachment(
    self, db, session_id: str, message_id: str, attachment_id: str, url: str, worker_name: str
):
    """更新会话附件"""
    from sqlalchemy.orm.attributes import flag_modified
    import copy

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    messages = copy.deepcopy(session.messages or [])
    
    for msg in messages:
        if msg.get('id') == message_id and msg.get('attachments'):
            for att in msg['attachments']:
                if att.get('id') == attachment_id:
                    att['url'] = url                    # ⭐ 写入永久 URL
                    att['uploadStatus'] = 'completed'  # ⭐ 更新状态
                    break
    
    session.messages = messages
    flag_modified(session, 'messages')  # ⭐ 标记 JSON 字段已修改
    db.commit()                          # ⭐ 提交到数据库
```

### 5.3 为什么需要 `flag_modified`？

SQLAlchemy 的 JSON 字段在原地修改时**不会自动检测变化**。必须使用以下方式之一：

1. **`flag_modified(session, 'messages')`** - 手动标记字段已修改
2. **重新赋值** - `session.messages = new_messages`

本项目同时使用了两种方式确保更新生效。

---

## 6. upload_tasks 表更新流程

Worker 处理任务时，会多次更新 `upload_tasks` 表的状态和字段。

```mermaid
flowchart TD
    subgraph 创建任务["API 创建任务"]
        A[POST /upload-async] --> B[INSERT upload_tasks]
        B --> C[status = pending<br/>source_file_path = 临时文件路径<br/>filename = 文件名<br/>priority = normal<br/>retry_count = 0<br/>created_at = 当前时间戳]
    end

    subgraph Worker处理["Worker 处理任务"]
        D[Worker 获取任务] --> E[UPDATE status = uploading]
        E --> F[上传到云存储]
        F --> G{上传成功?}
        G -->|是| H[UPDATE<br/>status = completed<br/>target_url = 永久URL<br/>completed_at = 当前时间戳]
        G -->|否| I{retry_count < 3?}
        I -->|是| J[UPDATE<br/>status = pending<br/>retry_count += 1<br/>error_message = 错误信息]
        I -->|否| K[UPDATE<br/>status = failed<br/>error_message = 错误信息<br/>completed_at = 当前时间戳]
    end

    C --> D
    J --> D

    style C fill:#e3f2fd
    style H fill:#c8e6c9
    style K fill:#ffcdd2
```

### 6.1 upload_tasks 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR | 任务 ID（UUID） |
| `session_id` | VARCHAR | 关联的会话 ID |
| `message_id` | VARCHAR | 关联的消息 ID |
| `attachment_id` | VARCHAR | 关联的附件 ID |
| `source_file_path` | VARCHAR | 临时文件路径（`backend/temp/upload_xxx.png`） |
| `source_url` | VARCHAR | 源 URL（从 URL 下载时使用） |
| `filename` | VARCHAR | 原始文件名 |
| `storage_id` | VARCHAR | 云存储配置 ID |
| `priority` | VARCHAR | 优先级（`high`/`normal`/`low`） |
| `status` | VARCHAR | 状态（`pending`/`uploading`/`completed`/`failed`） |
| `target_url` | VARCHAR | ⭐ 云存储永久 URL（上传成功后填入） |
| `error_message` | VARCHAR | 错误信息（失败时填入） |
| `retry_count` | INTEGER | 重试次数 |
| `created_at` | BIGINT | 创建时间戳（毫秒） |
| `completed_at` | BIGINT | 完成时间戳（毫秒） |

### 6.2 状态变更时机

| 状态 | 触发时机 | 更新字段 |
|------|----------|----------|
| `pending` | API 创建任务 | `id`, `session_id`, `message_id`, `attachment_id`, `source_file_path`, `filename`, `priority`, `created_at` |
| `uploading` | Worker 开始处理 | `status` |
| `completed` | 上传成功 | `status`, `target_url`, `completed_at` |
| `failed` | 重试次数耗尽 | `status`, `error_message`, `completed_at` |
| `pending`（重试） | 上传失败但未达最大重试 | `status`, `retry_count`, `error_message` |

### 6.3 关键代码位置

**文件**: `D:\gemini-main\gemini-main\backend\app\services\upload_worker_pool.py`

```python
# 第 230-250 行：_handle_success 方法
async def _handle_success(self, db, task: UploadTask, url: str, worker_name: str):
    now = int(datetime.now().timestamp() * 1000)
    
    # ⭐ 更新 upload_tasks 表
    task.status = 'completed'
    task.target_url = url           # 永久 URL
    task.completed_at = now
    db.commit()
    
    # 删除临时文件
    if task.source_file_path and os.path.exists(task.source_file_path):
        os.remove(task.source_file_path)
    
    # 更新 chat_sessions.messages
    if task.session_id and task.message_id and task.attachment_id:
        await self._update_session_attachment(...)

# 第 260-300 行：_handle_failure 方法
async def _handle_failure(self, db, task_id: str, error: str, worker_name: str):
    task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
    
    retry_count = (task.retry_count or 0) + 1
    task.retry_count = retry_count
    task.error_message = f"{error} (重试 {retry_count}/{self.max_retries})"
    
    if retry_count < self.max_retries:
        # 重试
        task.status = 'pending'
        db.commit()
        await redis_queue.enqueue(task_id, 'low')
    else:
        # 最终失败
        task.status = 'failed'
        task.completed_at = int(datetime.now().timestamp() * 1000)
        db.commit()
        await redis_queue.move_to_dead_letter(task_id)
```

---

## 7. 状态流转图

```mermaid
stateDiagram-v2
    [*] --> pending: 创建任务
    pending --> uploading: Worker 开始处理
    uploading --> completed: 上传成功
    uploading --> pending: 重试 (retry_count < 3)
    uploading --> failed: 重试次数耗尽
    failed --> pending: 手动重试
    completed --> [*]
    
    note right of pending: upload_tasks.status = pending
    note right of uploading: upload_tasks.status = uploading
    note right of completed: upload_tasks.status = completed<br/>upload_tasks.target_url = 永久URL<br/>chat_sessions.messages 已更新
    note right of failed: upload_tasks.status = failed<br/>移入死信队列
```

---

## 8. 关键代码位置

### 8.1 前端：图片生成处理

**文件**: `D:\gemini-main\gemini-main\frontend\hooks\handlers\imageGenHandler.ts`

```typescript
// 第 30-50 行：调用 LLM 生成图片
const results = await llmService.generateImage(text, attachments);

// 第 52-70 行：下载图片创建 Blob URL
const response = await fetch(res.url);
const blob = await response.blob();
displayUrl = URL.createObjectURL(blob);

// 第 85-110 行：提交上传任务到 Redis 队列
const result = await storageUpload.uploadFileAsync(file, {
  sessionId: context.sessionId,
  messageId: context.modelMessageId,
  attachmentId: r.id
});
```

### 8.2 前端：上传服务

**文件**: `D:\gemini-main\gemini-main\frontend\services\storage\storageUpload.ts`

```typescript
// 第 280-320 行：异步上传方法
async uploadFileAsync(file: File, options: {...}): Promise<{taskId, status}> {
  const response = await fetch(`/api/storage/upload-async?${params}`, {
    method: 'POST',
    body: formData,
  });
}
```

### 8.3 后端：上传 API

**文件**: `D:\gemini-main\gemini-main\backend\app\routers\storage.py`

```python
# 第 450-520 行：异步上传端点
@router.post("/upload-async")
async def upload_file_async(...):
    # 保存到 backend/temp/
    temp_path = os.path.join(TEMP_DIR, f"upload_{task_id}_{file.filename}")
    
    # 创建数据库记录
    task = UploadTask(...)
    db.add(task)
    
    # 入队 Redis
    queue_position = await redis_queue.enqueue(task_id, priority)
```

### 8.4 后端：Redis 队列服务

**文件**: `D:\gemini-main\gemini-main\backend\app\services\redis_queue_service.py`

```python
# 第 50-80 行：入队方法
async def enqueue(self, task_id: str, priority: str = "normal") -> int:
    await self._redis.lpush(queue_key, task_id)

# 第 85-100 行：出队方法
async def dequeue(self, timeout: int = 5) -> Optional[str]:
    result = await self._redis.brpop([QUEUE_HIGH, QUEUE_NORMAL, QUEUE_LOW], timeout)
```

### 8.5 后端：Worker 池

**文件**: `D:\gemini-main\gemini-main\backend\app\services\upload_worker_pool.py`

```python
# 第 100-160 行：Worker 主循环
async def _worker_loop(self, worker_id: int):
    task_id = await redis_queue.dequeue(timeout=5)
    await self._process_task(task_id, worker_name)

# 第 170-270 行：处理单个任务
async def _process_task(self, task_id: str, worker_name: str):
    content = await self._get_file_content(task)
    result = await StorageService.upload_file(...)
    await self._handle_success(db, task, url, worker_name)
```

---

## 9. 配置文件

| 文件路径 | 说明 |
|----------|------|
| `D:\gemini-main\gemini-main\backend\.env` | Redis 连接配置、Worker 数量等 |
| `D:\gemini-main\gemini-main\backend\app\core\config.py` | 配置类定义 |

### 关键配置项

```bash
# D:\gemini-main\gemini-main\backend\.env
REDIS_HOST=192.168.50.175
REDIS_PORT=6379
REDIS_PASSWORD=941378
UPLOAD_QUEUE_WORKERS=5
UPLOAD_QUEUE_MAX_RETRIES=3
UPLOAD_QUEUE_RATE_LIMIT=10
```
