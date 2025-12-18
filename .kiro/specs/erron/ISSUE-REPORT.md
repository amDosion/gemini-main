# 🔴 CRITICAL ISSUE: Worker Pool Not Processing Upload Tasks

## 问题概述 (Problem Summary)

**现象**: 前端调用异步上传 API (`/api/storage/upload-async`) 返回 200 成功，但后端 Worker 池没有处理任何任务，数据库中的任务记录不完整。

**影响**: 用户生成的图片无法上传到云存储，功能完全不可用。

**发生时间**: 2025-12-17

---

## 系统架构 (System Architecture)

### 技术栈
- **前端**: React + TypeScript + Vite
- **后端**: FastAPI (Python) + Uvicorn
- **数据库**: PostgreSQL (192.168.50.115:5432/gemini-ai)
- **队列**: Redis (192.168.50.175:6379/db0)
- **云存储**: 兰空图床 (Lsky Pro)

### 异步上传架构 (方案 E - Redis 队列 + Worker 池)

```
前端生成图片
    ↓
调用 /api/storage/upload-async
    ↓
后端保存文件到 temp 目录
    ↓
创建数据库记录 (upload_tasks 表)
    ↓
任务 ID 入队 Redis
    ↓
Worker 池从 Redis 取出任务
    ↓
Worker 上传文件到云存储
    ↓
更新数据库记录 (target_url)
```

---

## 详细问题描述 (Detailed Problem Description)

### 1. 前端日志 (Frontend Logs)

```
[1] → 发送请求: POST /api/storage/upload-async?session_id=f1c9d8be...&message_id=e8cc1da7...&attachment_id=ce9bf24f...
[1] → 发送请求: POST /api/storage/upload-async?session_id=f1c9d8be...&message_id=e8cc1da7...&attachment_id=e0c89193...
[1] ← 收到响应: 200 /api/storage/upload-async?...&attachment_id=ce9bf24f...
[1] ← 收到响应: 200 /api/storage/upload-async?...&attachment_id=e0c89193...
```

**观察**:
- ✅ 前端成功发送了 2 个上传请求
- ✅ 后端返回 200 状态码
- ❌ 但后端**完全没有日志输出**

### 2. 后端日志 (Backend Logs)

```
[0] [WorkerPool] worker-0 started
[0] [WorkerPool] worker-1 started
[0] [WorkerPool] worker-2 started
[0] [WorkerPool] worker-3 started
[0] [WorkerPool] worker-4 started
[0] [WorkerPool] worker-0 waiting for task...
[0] [WorkerPool] worker-1 waiting for task...
[0] [WorkerPool] worker-2 waiting for task...
[0] [WorkerPool] worker-3 waiting for task...
[0] [WorkerPool] worker-4 waiting for task...
[0] [WorkerPool] worker-0 waiting for task...
[0] [WorkerPool] worker-1 waiting for task...
... (持续每 5 秒输出 "waiting for task")
```

**观察**:
- ✅ Worker 池成功启动 (5 个 Worker)
- ✅ Worker 正在循环等待任务
- ❌ **缺失的日志**: 应该看到但没有看到
  - `[UploadAsync] received upload request`
  - `[UploadAsync] file saved: {temp_path}`
  - `[UploadAsync] task created: {task_id}`
  - `[UploadAsync] enqueued to Redis, position: {pos}`
  - `[WorkerPool] worker-X got task: {task_id}`
  - `[WorkerPool] worker-X processing: {task_id}`

### 3. 数据库状态 (Database Status)

运行 `python backend/check_upload_tasks.py`:

```
总记录数: 2

按状态统计:
  - pending: 2 条

最近 2 条任务:

  任务 ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    文件名: generated-1765983068898-1.png
    状态: pending
    优先级: None          ❌ 应该是 'normal'
    重试次数: None        ❌ 应该是 0
    会话ID: f1c9d8be...
    消息ID: e8cc1da7...
    附件ID: ce9bf24f...
    源文件路径: NULL      ❌ 应该有 temp 目录路径
    目标URL: NULL
    创建时间: 1765983069118
```

**观察**:
- ✅ 数据库有记录被创建
- ❌ **关键字段缺失**:
  - `priority` 是 NULL (应该是 'normal')
  - `retry_count` 是 NULL (应该是 0)
  - `source_file_path` 是 NULL (应该有临时文件路径如 `C:\Users\xxx\AppData\Local\Temp\upload_xxx.png`)

### 4. Redis 队列状态 (Redis Queue Status)

运行 `python backend/diagnose_system.py`:

```
1. Redis 连接测试:
  ✅ Redis 连接成功
  - 高优先级队列: 0 个任务
  - 普通优先级队列: 0 个任务
  - 低优先级队列: 0 个任务
  - 死信队列: 0 个任务

  队列统计:
    - 总入队: 10
    - 总出队: 0
    - 总完成: 6
    - 总失败: 0

3. 数据一致性检查:
  数据库中 pending 任务: 2 个

  前 2 个 pending 任务 ID:
    ❌ xxxxxxxx... 不在 Redis 队列中
    ❌ xxxxxxxx... 不在 Redis 队列中

  一致性: 0/2 个任务在 Redis 中
```

**观察**:
- ✅ Redis 连接正常
- ❌ Redis 统计显示 "总入队: 10"，但当前队列全部为空
- ❌ Redis 统计显示 "总完成: 6"，但数据库中任务仍是 pending
- ❌ **数据不一致**: 数据库有 2 个 pending 任务，但 Redis 队列中没有

---

## 核心矛盾 (Core Contradiction)

### 矛盾点 1: API 被调用但没有日志

**证据链**:
1. 前端日志显示 POST 请求发送
2. 前端收到 200 响应
3. 数据库有新记录产生
4. **但后端日志完全没有 `/api/storage/upload-async` 的日志输出**

**预期日志位置**: `backend/app/routers/storage.py` 第 477-493 行

```python
@router.post("/upload-async")
async def upload_file_async(...):
    # ✅ 详细日志：记录接收到的所有参数
    print(f"[UploadAsync] received upload request:")  # ← 应该输出但没有
    print(f"  - filename: {file.filename}")
    print(f"  - priority: {priority}")
    ...
```

### 矛盾点 2: 数据库记录不完整

**正常流程应该设置的字段** (`storage.py` 第 496-508 行):

```python
task = UploadTask(
    id=task_id,
    session_id=session_id,
    message_id=message_id,
    attachment_id=attachment_id,
    source_file_path=temp_path,      # ❌ 数据库中是 NULL
    filename=file.filename,
    storage_id=storage_id,
    priority=priority,                # ❌ 数据库中是 NULL
    retry_count=0,                    # ❌ 数据库中是 NULL
    status='pending',
    created_at=int(datetime.now().timestamp() * 1000)
)
```

**实际数据库记录**: 所有标记 ❌ 的字段都是 NULL

### 矛盾点 3: Redis 统计异常

- Redis 显示 "总入队: 10"
- 但当前队列全部为空 (0 个任务)
- Redis 显示 "总出队: 0"
- 但 Redis 显示 "总完成: 6"

**逻辑冲突**: 如果有 6 个任务完成，应该有出队记录，但出队数是 0。

---

## 可能的原因分析 (Possible Root Causes)

### 假设 1: 代码热重载问题 ❌

**理论**: Uvicorn 的 `--reload` 模式可能导致旧代码还在运行

**反驳**:
- 已经完全重启服务 (关闭 + 重新启动)
- Worker 池的新日志 "worker-X started" 正常显示 (证明新代码生效)
- 但 `/upload-async` 的日志没有输出 (旧代码也应该有某种日志)

### 假设 2: 有其他代码路径创建数据库记录 ❌

**理论**: 可能有其他 API 或代码直接操作数据库

**排查结果**:
```bash
# 搜索所有创建 UploadTask 的地方
grep -r "UploadTask(" backend/

结果：
backend/app/routers/storage.py       # /upload-async 和 /upload-from-url
backend/app/models/db_models.py      # 模型定义
backend/app/migrations/              # 数据库迁移
```

**反驳**:
- 只有 2 个 API 创建 UploadTask: `/upload-async` 和 `/upload-from-url`
- 两个 API 都会设置 `priority` 和 `retry_count`
- 但数据库记录这两个字段是 NULL

### 假设 3: 前端调用了错误的 API 端点 ❓

**理论**: 前端可能没有调用 `/upload-async`，而是其他端点

**需要验证**:
- 前端代码在 `frontend/hooks/handlers/imageGenHandler.ts` 第 99 行
  ```typescript
  const result = await storageUpload.uploadFileAsync(file, {...});
  ```
- `storageUpload.uploadFileAsync` 在 `frontend/services/storage/storageUpload.ts` 第 413 行
  ```typescript
  const response = await fetch(`${API_BASE}/storage/upload-async?${params.toString()}`, {
    method: 'POST',
    body: formData,
  });
  ```

**结论**: 前端确实调用的是 `/upload-async`

### 假设 4: FastAPI 路由冲突或覆盖 ⚠️

**理论**: 可能有多个路由注册到同一个路径

**需要验证**:
```python
# 搜索所有 @router.post 装饰器
grep -r "@router.post" backend/app/routers/

结果：
storage.py:186:@router.post("/upload")
storage.py:441:@router.post("/upload-async")         # ← 我们的路由
storage.py:538:@router.post("/upload-from-url")
storage.py:618:@router.post("/retry-upload/{task_id}")
```

**反驳**: 没有路由冲突

### 假设 5: 数据库记录由前端直接创建 ❌

**理论**: 前端可能使用浏览器 IndexedDB/localStorage 创建记录

**反驳**:
- 前端使用的是 Dexie.js (IndexedDB 封装)
- 搜索前端代码没有发现直接插入 `upload_tasks` 的逻辑
- 前端和后端使用不同的数据库 (前端 IndexedDB, 后端 PostgreSQL)

---

## 已执行的诊断步骤 (Diagnostic Steps Taken)

### 1. ✅ 验证 Redis 连接

**脚本**: `backend/test_redis_connection.py`

**结果**:
```
✅ Ping 成功: PONG
✅ 写入成功
✅ 读取成功: test_value_1734458468
✅ Redis 连接完全正常
```

### 2. ✅ 验证 Worker 池工作

**脚本**: `backend/test_worker_processing.py`

**结果**:
```
[3] 创建测试任务...
  ✅ 任务已创建: 45eb2263...

[4] 手动入队到 Redis...
  ✅ 任务已入队
  普通队列长度: 0 → 0  # ← 立即被 Worker 取走

[5] 监控任务处理 (30 秒)...
  [1秒] 队列: 0 | 状态: pending | 错误: 无可用的文件来源 (重试 1/3)
```

**结论**:
- ✅ Worker 池正在运行并处理任务
- ✅ 任务入队后立即被取走
- ⚠️ 任务因为缺少 `source_file_path` 失败 (测试任务预期行为)

### 3. ✅ 验证日志输出

**修改**: 使用 `sys.stderr.write()` + `flush()` 强制输出

**结果**:
```
[0] [WorkerPool] worker-0 started
[0] [WorkerPool] worker-1 started
...
[0] [WorkerPool] worker-0 waiting for task...
```

**结论**: Worker 池日志正常输出

### 4. ❌ 完整流程测试失败

**操作**: 前端生成 2 张图片

**预期**:
1. 后端日志显示 `[UploadAsync] received upload request`
2. 后端日志显示 `[UploadAsync] enqueued to Redis`
3. Worker 日志显示 `[WorkerPool] worker-X got task`
4. 数据库任务状态变为 `completed`
5. 数据库任务有 `target_url`

**实际**:
1. ❌ 后端完全没有 UploadAsync 日志
2. ❌ Worker 一直显示 "waiting for task"
3. ❌ 数据库任务状态仍是 `pending`
4. ❌ 数据库任务字段不完整 (priority, retry_count, source_file_path 都是 NULL)

---

## 关键代码文件 (Key Code Files)

### 1. 后端 API 路由

**文件**: `backend/app/routers/storage.py`

**关键函数**: 第 442-535 行

```python
@router.post("/upload-async")
async def upload_file_async(
    file: UploadFile = File(...),
    session_id: str = Query(None),
    message_id: str = Query(None),
    attachment_id: str = Query(None),
    storage_id: str = Query(None),
    priority: str = Query('normal'),
    db: Session = Depends(get_db)
):
    """
    异步上传文件到云存储（不阻塞前端）

    返回：
    {
        "task_id": "task-xxx",
        "status": "pending",
        "priority": "normal",
        "queue_position": 5
    }
    """
    # ✅ 详细日志：记录接收到的所有参数
    print(f"[UploadAsync] received upload request:")  # ← 应该输出但没有
    print(f"  - filename: {file.filename}")
    print(f"  - priority: {priority}")
    print(f"  - session_id: {session_id[:8] if session_id else 'None'}...")
    print(f"  - message_id: {message_id[:8] if message_id else 'None'}...")
    print(f"  - attachment_id: {attachment_id[:8] if attachment_id else 'None'}...")

    # 1. 保存文件到临时目录
    temp_dir = tempfile.gettempdir()
    task_id = str(uuid.uuid4())
    temp_path = os.path.join(temp_dir, f"upload_{task_id}_{file.filename}")

    file_content = await file.read()
    with open(temp_path, 'wb') as f:
        f.write(file_content)

    print(f"[UploadAsync] file saved: {temp_path}")

    # 2. 创建数据库记录（持久化）
    task = UploadTask(
        id=task_id,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        source_file_path=temp_path,
        filename=file.filename,
        storage_id=storage_id,
        priority=priority,
        retry_count=0,
        status='pending',
        created_at=int(datetime.now().timestamp() * 1000)
    )

    db.add(task)
    db.commit()

    print(f"[UploadAsync] task created: {task_id[:8]}...")

    # 3. 入队 Redis（调度）
    try:
        # 确保 Redis 连接已建立
        if redis_queue._redis is None:
            print("[UploadAsync] Redis connection not initialized, connecting...")
            await redis_queue.connect()

        queue_position = await redis_queue.enqueue(task_id, priority)
        print(f"[UploadAsync] enqueued to Redis, position: {queue_position}")
    except Exception as e:
        print(f"[UploadAsync] ❌ Redis enqueue failed: {e}")
        queue_position = -1

    return {
        "task_id": task_id,
        "status": "pending",
        "priority": priority,
        "queue_position": queue_position
    }
```

### 2. Worker 池主循环

**文件**: `backend/app/services/upload_worker_pool.py`

**关键函数**: 第 119-191 行

```python
async def _worker_loop(self, worker_id: int):
    """Worker main loop"""
    import sys
    worker_name = f"worker-{worker_id}"
    msg = f"[WorkerPool] {worker_name} started\n"
    sys.stderr.write(msg)
    sys.stderr.flush()

    while self._running:
        try:
            # Dequeue task from Redis (blocking wait)
            msg = f"[WorkerPool] {worker_name} waiting for task...\n"
            sys.stderr.write(msg)
            sys.stderr.flush()
            task_id = await redis_queue.dequeue(timeout=5)

            if task_id is None:
                # Timeout, continue waiting
                continue

            msg = f"[WorkerPool] {worker_name} got task: {task_id[:8]}...\n"
            sys.stderr.write(msg)
            sys.stderr.flush()

            # ... (处理任务)
        except Exception as e:
            msg = f"[WorkerPool] {worker_name} exception: {e}\n"
            sys.stderr.write(msg)
            sys.stderr.flush()
```

### 3. 前端上传调用

**文件**: `frontend/hooks/handlers/imageGenHandler.ts`

**关键代码**: 第 79-139 行

```typescript
const uploadTask = async (): Promise<{ dbAttachments: Attachment[] }> => {
  console.log(`[imageGenHandler] 提交 ${processedResults.length} 张图片到 Redis 上传队列`);

  const uploadPromises = processedResults.map(async (r) => {
    try {
      // 确保 uploadSource 是 File 对象
      let file: File;
      if (r.uploadSource instanceof File) {
        file = r.uploadSource;
      } else if (typeof r.uploadSource === 'string') {
        const response = await fetch(r.uploadSource);
        const blob = await response.blob();
        file = new File([blob], r.filename, { type: blob.type || 'image/png' });
      } else {
        throw new Error('Invalid upload source type');
      }

      // 调用异步上传 API（提交到 Redis 队列）
      const result = await storageUpload.uploadFileAsync(file, {
        sessionId: context.sessionId,
        messageId: context.modelMessageId,
        attachmentId: r.id
      });

      console.log(`[imageGenHandler] 图片 ${r.filename} 已提交到队列，任务ID: ${result.taskId}`);
      // ...
    } catch (error) {
      console.error(`[imageGenHandler] 提交上传任务失败 (${r.filename}):`, error);
      // ...
    }
  });
  // ...
};
```

**文件**: `frontend/services/storage/storageUpload.ts`

**关键代码**: 第 388-435 行

```typescript
async uploadFileAsync(
  file: File,
  options: {
    sessionId: string;
    messageId: string;
    attachmentId: string;
    storageId?: string;
  }
): Promise<{
  taskId: string;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  message?: string;
}> {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    params.append('session_id', options.sessionId);
    params.append('message_id', options.messageId);
    params.append('attachment_id', options.attachmentId);
    if (options.storageId) {
      params.append('storage_id', options.storageId);
    }

    const response = await fetch(`${API_BASE}/storage/upload-async?${params.toString()}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '创建上传任务失败' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const result = await response.json();
    console.log('[StorageUpload] 异步上传任务已创建:', result.task_id);

    return {
      taskId: result.task_id,
      status: result.status,
      message: result.message
    };
  } catch (error) {
    console.error('[StorageUpload] 创建异步上传任务失败:', error);
    throw error;
  }
}
```

---

## 环境信息 (Environment Information)

### 系统环境

```
操作系统: Windows
项目路径: D:\gemini-main\gemini-main
Node.js: (需要确认版本)
Python: 3.14
Uvicorn: 启动命令 "uvicorn app.main:app --reload --reload-dir app --port 8000"
```

### 数据库连接

```
DATABASE_URL=postgresql+psycopg2://ai:Z6LwNUH481dnjAmp2kMRPmg8xj8CtE@192.168.50.115:5432/gemini-ai
```

### Redis 连接

```
REDIS_HOST=192.168.50.175
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=941378
```

### Python 依赖

```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
redis[hiredis]
aioredis
```

---

## 诊断脚本 (Diagnostic Scripts)

### 1. 检查数据库

```bash
python backend/check_upload_tasks.py
```

### 2. 完整系统诊断

```bash
python backend/diagnose_system.py
```

### 3. Worker 池处理测试

```bash
python backend/test_worker_processing.py
```

### 4. Redis 连接测试

```bash
python backend/test_redis_connection.py
```

### 5. 清理测试数据

```bash
python backend/clean_upload_tasks.py
```

---

## 请求帮助 (Request for Help)

### 核心问题

**为什么前端调用 `/api/storage/upload-async` 返回 200，但后端日志完全没有输出，且数据库记录不完整？**

### 需要验证的方向

1. **FastAPI 路由注册**
   - 是否有多个 `/upload-async` 路由被注册？
   - 路由是否被正确加载到应用中？
   - 如何验证运行时实际处理请求的函数？

2. **代码热重载问题**
   - Uvicorn `--reload` 是否可能导致旧代码还在运行？
   - 如何强制确保新代码生效？
   - 是否需要清理 `__pycache__` 或 `.pyc` 文件？

3. **日志系统问题**
   - `print()` 语句为什么没有输出？
   - 是否被某个中间件或日志系统拦截？
   - 如何确保日志一定输出到控制台？

4. **数据库记录来源**
   - 如何追踪是哪个代码路径创建了数据库记录？
   - 为什么记录中某些字段是 NULL？
   - 是否有其他进程或服务在操作数据库？

5. **前端请求路由**
   - 如何确认前端请求真的到达了预期的后端路由？
   - 是否可能有 nginx/代理服务器重写了请求路径？
   - 如何在 FastAPI 级别打印所有接收到的请求？

---

## 附加信息 (Additional Information)

### 完整日志文件

**位置**: `D:\gemini-main\gemini-main\.kiro\specs\erron\log.md`

**最近 200 行**: 见文件末尾

### 相关文档

1. **架构方案**: `.kiro/specs/analysis/redis-db-queue-solution.md`
2. **Worker 池诊断报告**: `.kiro/specs/analysis/worker-pool-diagnostics.md`
3. **本问题报告**: `.kiro/specs/erron/ISSUE-REPORT.md`

---

## 联系方式 (Contact)

如需更多信息或远程协助，请联系：

- **项目路径**: `D:\gemini-main\gemini-main`
- **可执行诊断脚本**: 见 "诊断脚本" 章节
- **可提供**: 完整源代码、数据库访问、Redis 访问

---

**生成时间**: 2025-12-17 23:05
**报告版本**: 1.0
