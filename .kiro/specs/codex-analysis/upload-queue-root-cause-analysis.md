# 上传队列任务长期停留 pending 的根因分析（Codex）

- 生成时间：2025-12-17
- 输入材料：
  - `.kiro/specs/analysis/upload-queue-issue-analysis.md`
  - `.kiro/specs/erron/ISSUE-REPORT.md`
- 代码核对范围（本仓库当前版本）：
  - `backend/app/routers/storage.py`（`/api/storage/upload-async` 实现）
  - `backend/app/services/upload_worker_pool.py`（WorkerPool 启动/恢复/消费队列）
  - `backend/app/services/redis_queue_service.py`（Redis 队列实现）
  - `backend/diagnose_system.py`（诊断脚本输出口径）
  - `package.json`（`npm run dev`/`npm run server` 启动方式）

## 0. 一句话结论

你们遇到的“任务一直 pending、Redis 队列为空、Worker 一直 waiting、但接口返回 200”并不矛盾：

1) **WorkerPool 只消费 Redis 队列**，所以只要“任务 ID 没有成功入队 Redis”，Worker 就永远等不到任务；
2) 即便现在代码里已经加了入队逻辑，**历史上已经写进数据库但没入队的 pending 任务并不会被自动补偿**——当前 WorkerPool 的恢复逻辑只处理 `uploading` 状态（不处理 `pending`）；
3) 报告里“接口无日志”并不能单独证明接口没执行，因为当前实现大量使用 `print()` 写 stdout，而你们的 `concurrently`/日志采集很可能主要采集了 stderr（WorkerPool 恰好把关键日志写到了 stderr）。

## 1. 现象与证据（来自两份报告）

共同现象：
- 前端调用 `POST /api/storage/upload-async?...` 返回 200。
- 数据库 `upload_tasks` 出现新记录，但状态长期为 `pending`。
- Redis 三个优先级队列长度为 0。
- WorkerPool 5 个 worker 循环打印 `waiting for task...`，没有出现 `got task` / `processing`。

关键矛盾点：
- 既然接口返回 200 且数据库有记录，按设计应该“入队 → Worker 消费 → 更新状态/URL”，但实际没有发生。

## 2. 代码事实核对（本仓库当前版本）

### 2.1 `/api/storage/upload-async` 的预期行为

在 `backend/app/routers/storage.py` 中，`/api/storage/upload-async` 现在的逻辑是：
1) 保存上传文件到临时目录（`tempfile.gettempdir()`）
2) 创建数据库任务记录 `UploadTask`（显式写入 `priority` / `retry_count` / `source_file_path`）
3) 调用 `redis_queue.enqueue(task_id, priority)` 将任务 ID 入队 Redis
4) 立即返回 `{task_id, status, priority, queue_position}`

因此：
- **如果你看到新任务的 `priority/retry_count/source_file_path` 仍是 NULL**，说明运行时并未执行到这一版逻辑（或执行的是旧版本/不同分支/不同进程）。
- **如果 WorkerPool 一直等不到任务**，说明第 3 步没有成功发生（没有入队到同一个 Redis DB）。

### 2.2 WorkerPool 的恢复逻辑缺口

在 `backend/app/services/upload_worker_pool.py` 中：
- `start()` 会先 `redis_queue.connect()`，然后调用 `_recover_tasks()`。
- `_recover_tasks()` **只会把 `status == 'uploading'` 的任务重置为 `pending` 并入队**。

也就是说：
- **历史上那些“已经是 pending 但不在 Redis 队列里”的任务，不会被自动补偿入队**。
- 这会导致你“修了入队逻辑”之后仍然看到库里一堆 pending 永远不动，从而误判“还是没修好”。

### 2.3 诊断脚本的统计口径容易误导

`backend/diagnose_system.py` 会打印：
- `total_enqueued`
- `total_dequeued`（注意：当前 `redis_queue_service.get_stats()` 并不返回该字段，所以这里永远是 0）

因此“总出队为 0”在当前实现下**不具备诊断意义**，不要用它来推断 Worker 是否消费。

## 3. 为什么一直解决不了（最可能的组合原因）

结合“接口 200 + DB 有记录 + Redis 队列空 + Worker 永远 waiting”这组证据，最可能是下面两类原因叠加：

### 原因 A：入队逻辑实际上没有生效（运行时执行的不是你以为的那段代码）
高概率触发场景：
- 后端实际运行的是旧代码（你修改的是另一个工作区/分支/文件未被 reload 生效）。
- 端口 8000 上存在多个后端实例，前端打到 A，日志看的是 B。

**验证方法（推荐优先做）：**
1) 打开 `http://localhost:8000/openapi.json`，确认是否存在 `/api/storage/upload-async`，并检查它的参数/返回结构是否包含 `priority`、`queue_position`（与当前实现一致）。
2) 在 `upload_file_async` 里临时打印 `__file__` 并 `flush=True`（或写 stderr），确认请求命中的文件路径确实是你改的那份。

> 仅凭“看不到 [UploadAsync] print”不足以下结论，因为 stdout 可能没被采集。

### 原因 B：存量 pending 任务缺少“补偿入队”机制
即使你已经把新请求的入队逻辑修好：
- 之前产生的 pending 任务仍然不会被 WorkerPool 自动拾取。
- 它们会一直挂在数据库里，让你误以为“系统还是坏的”。

**验证方法：**
- 只看“最新创建的 1~2 条任务”是否包含完整字段且能完成。
- 对旧任务做一次性补偿（见下一节），再观察 Worker 是否能消费。

## 4. 解决路径（按“最快恢复可用”排序）

### 4.1 快速确认：你到底命中了哪个后端
1) `npm run dev` 启动后，确认只启动了一份 `npm run server`（`package.json` 中它会 `cd backend && uvicorn app.main:app ...`）。
2) 用 `netstat -ano | findstr :8000` 确认 8000 只被一个 PID 占用。
3) 在后端启动日志里加一个“版本签名”（例如打印 git commit 或 storage.py 的 hash）以避免以后再次混淆。

### 4.2 一次性修复存量数据（让旧 pending 不再永远卡住）

#### 4.2.1 补齐 NULL 默认值（安全）
```sql
UPDATE upload_tasks SET priority = 'normal' WHERE priority IS NULL;
UPDATE upload_tasks SET retry_count = 0 WHERE retry_count IS NULL;
```

#### 4.2.2 将“pending 且不在 Redis”任务重新入队
思路：
- 查询 `upload_tasks.status='pending'` 的任务
- 对每个任务，如果不在 `upload:queue:*` 里，就按优先级入队

你可以：
- 临时用 Redis CLI 手工 `LPUSH upload:queue:normal <task_id>`；或
- 写一个小脚本批量补偿（建议做成一次性运维脚本/管理端点）。

**注意：**
- 如果某条任务同时满足 `source_file_path IS NULL` 且 `source_url IS NULL`，Worker 侧会报“无可用的文件来源”，这种任务**即便入队也无法成功上传**。需要：
  - 标记为 `failed` 并提示前端重新提交；或
  - 设计可恢复策略（例如能从 temp 目录按命名规则找回文件）。

### 4.3 长期修复（建议直接在代码里做）

1) **完善恢复逻辑**：WorkerPool 启动时除恢复 `uploading` 外，也应扫描 `pending` 且“不在 Redis 任意队列”的任务并补偿入队。
2) **让入队失败可观测**：`upload_file_async` 若 enqueue 失败，至少写入 `error_message`/状态，并把日志写到 stderr 或使用 logger。
3) **数据库层默认值**：给 `upload_tasks.priority/retry_count` 加 DB 默认值（你们已有 `backend/migrations/DROP_AND_RECREATE.sql` 作为开发环境方案；生产建议用迁移 ALTER）。
4) **统计口径修正**：如果要打印 `total_dequeued`，需要在 `dequeue()` 成功时更新 stats。

## 5. 验收标准（你应该看到什么）

对“新创建的任务”，满足以下全部：
- `upload_tasks` 里：`priority` 非 NULL、`retry_count` 非 NULL、且 `source_file_path` 或 `source_url` 至少一个非 NULL。
- WorkerPool 日志出现：`got task` → `processing` → `completed`（或失败进入重试/死信）。
- 任务最终 `status='completed'` 且 `target_url` 写入。
- 若绑定了 `session_id/message_id/attachment_id`，会话消息里的附件 URL 被更新。

---

如需我继续：我也可以把“补偿入队 pending 任务”的脚本/管理端点和 WorkerPool 的恢复增强直接写进代码并给出最小改动 PR 级别 patch。
