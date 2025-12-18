# upload_tasks 写入不完整：详细排查文档（含采集清单）

> 目标：把“到底是哪一条写入不完整、为什么不完整、是否命中旧后端/错数据库、以及如何修复”说清楚，并给出可执行的验证步骤。

## 1. 你说的“不完整”通常指什么

`upload_tasks` 表是“异步上传任务的持久化状态机”。它的字段并非在任何时刻都应当完整；要先区分 **任务类型** + **任务阶段**，否则会把“正常为空”误判为“写入异常”。

### 1.1 两类任务来源（决定哪些字段应为空）

| 任务来源 | 创建接口 | 预期有值 | 预期为空 |
|---|---|---|---|
| 本地文件上传（前端把 File 传给后端） | `POST /api/storage/upload-async` | `source_file_path`（相对路径） | `source_url` |
| URL 上传（后端从 URL 下载再上传） | `POST /api/storage/upload-from-url` | `source_url` | `source_file_path` |

因此：**如果你走的是 `upload-from-url`，看到 `source_file_path = NULL` 是正常的，不是写入不完整。**

### 1.2 任务阶段（决定 target_url / completed_at 是否应为空）

| status | 说明 | 预期字段情况 |
|---|---|---|
| `pending` | 已创建任务，尚未上传完成 | `target_url`、`completed_at` 可能为空（正常） |
| `uploading` | Worker 正在上传 | `target_url`、`completed_at` 可能为空（正常） |
| `completed` | 上传成功 | `target_url`、`completed_at` 应该有值 |
| `failed` | 最终失败 | `error_message` 应该有值，`completed_at` 通常有值 |

### 1.3 “不应该为空”的字段（若为空基本就是异常）

无论任务来源/阶段，这些字段理论上都不应为 NULL：
- `id`
- `filename`
- `status`
- `created_at`
- `priority`（应为 `high/normal/low`）
- `retry_count`（应为整数，默认 0）

如果你看到 `priority/retry_count` 仍为 NULL，几乎可以断定是：
- 命中了旧后端版本（旧逻辑没显式赋值），或
- 读写到了“另一个数据库”（例如脚本读 sqlite，服务写 postgres，或反过来），或
- 有非预期代码路径/脚本在直接插入表（绕过了应用逻辑）。

## 2. 已知强信号：前端日志出现 `/upload-logs` 404

你提供的前端日志里出现了：

- `GET /api/storage/upload-logs/{task_id} 404 (Not Found)`

这件事非常关键：**404 不是 Redis 错/DB 错，而是“路由不存在”**，通常意味着：
- 命中的是旧后端（还没包含 `upload-logs` 路由），或
- Vite 代理没打到后端（请求没被 proxy 转发），或
- 你实际上连到了另一个端口/另一台机器上的后端实例。

## 2.1 为什么“看起来要重启服务，数据库才刷新”

在 PostgreSQL/SQLite 里，**只要事务 commit 了，任何新的查询都应该立刻看到更新**。因此“必须重启服务才看到更新”一般不是数据库机制，而是以下几类“读到的不是最新/不是同一个地方”的问题：

1) **前端读的是缓存/本地存储，而不是后端数据库的最新值**
   - `CachedDB` 会对 `sessions` 做缓存（默认 TTL 12 小时），不会因为后端 Worker 写库就自动失效。
   - 如果你依赖“后端 Worker 更新 session.messages”，前端不主动刷新会话列表/当前会话，就会一直看到旧数据；你重启（前端/服务）后重新加载会话，看起来就像“数据库刷新了”。
   - 自检：看缓存指示器是否“来自缓存”；手动点刷新（强制 `refreshSessions`）即可验证。

2) **HybridDB 在启动时判定后端不可用后会锁定为 LocalStorage 模式**
   - `frontend/services/db.ts` 的 `HybridDB` 只在首次调用时检测 `/health`，一旦检测失败就会一直用 LocalStorage，直到你刷新页面/重启前端。
   - 这种情况下：后端 Worker 可能已经把 `upload_tasks/chat_sessions` 更新好了，但前端仍在 LocalStorage 里读写，自然“看不到数据库变化”。
   - 自检：浏览器控制台是否出现 `?? 后端 API 不可用 - 使用 LocalStorage`。

3) **你查的不是同一个数据库/同一个后端实例**
   - 典型表现：一会儿看到 Postgres 数据，一会儿看到 `sqlite:///./test.db`；或者命中旧后端导致路由 404。
   - 自检：访问 `GET /api/storage/debug` 看 `database_url/cwd/module_file` 是否符合预期。

4) **查询工具/连接处在长事务快照里（少见，但确实会发生）**
   - 某些 GUI 工具可能开启了手动事务/快照视图，你不提交/不刷新就一直看到旧快照。
   - 自检：关闭该连接/重新打开，或确认 “Auto-commit” 开启。

## 2.2 后端侧最强自证（不用重启就能验证是否真的写库成功）

如果你坚持“不是前端缓存/不是客户端快照”，可以用后端接口在**同一次运行**里直接证明：

1) 先对同一个 `task_id` 调用（直接读库、带 pid/cwd）：
   - `GET /api/storage/upload-task-db/{task_id}`
   - 代码位置：`backend/app/routers/storage.py:753`

2) 再对同一个 `task_id` 调用（ORM 读库、对外格式一致）：
   - `GET /api/storage/upload-status/{task_id}`

3) 如果两者都显示 `status=completed` 但你“外部”看不到更新：
   - 结论几乎只能是：你外部查的不是同一套 DB/同一实例，或你的查询连接处在快照里。

4) 如果两者都显示 `status=pending/uploading`：
   - 结论：Worker 侧确实没把状态写进 DB（需要看 Worker 日志/任务日志）。

## 2.2.1 一键看 Worker/Redis 是否“真的在跑”

新增诊断接口：
- `GET /api/storage/worker-status`

你可以在“不重启”的情况下直接判断：
- `worker_pool.running=false`：WorkerPool 根本没在运行（通常是启动时 Redis 连接失败导致 start() 失败）
- `workers_alive=0`：Worker 线程已全部退出（运行中断）
- `redis.connected=false` 或 `redis.error` 非空：Redis 不可用/连不上，队列无法消费

当出现你描述的“排队后不处理，重启后突然全部完成”，最常见链路是：
1) 请求创建任务成功（DB 有 pending）
2) 但 WorkerPool 当时没跑 / 或 Redis 不可用 → 任务不会被消费
3) 你重启后，WorkerPool 启动成功并执行启动补偿 → pending 任务被入队并完成

## 2.3 Worker 提交后 DB 回读日志（定位“写库 vs 看库”分歧）

Worker 在每次 `db.commit()` 后会用**新的 DB session 回读同一行**并写入任务日志，形如：

- `db verify (after_success_commit): status=completed, target_url=yes, ...`

用于排查：Worker 进程眼里是否真的已经把状态写进数据库。
代码位置：`backend/app/services/upload_worker_pool.py:552`

## 2.4 为什么“必须重启才会开始上传”（后端视角）

这个现象几乎不可能是“数据库提交延迟”，更常见是 **消费侧没在工作**：

1) **WorkerPool 启动时 Redis 连接失败**（应用继续启动，但 async uploads 实际不可用）
2) **Redis 运行中断线**（消费者反复报错不再有效消费）
3) **任务创建后没有成功入队 Redis**（只写入 DB；重启时启动补偿把 pending 任务补回队列）

为避免只能靠重启触发恢复：
- 后端已增加 WorkerPool 后台守护（启动失败会自动重试启动）。
- WorkerPool 增加周期性“pending 补偿入队”，无需重启也会把 DB 中未入队任务补回队列。

## 3. 一次性把“命中哪个后端/哪个数据库”说清楚

### 3.1 用后端自检接口确认版本与运行环境

后端已新增：
- `GET /api/storage/debug`（用于确认是否命中新代码、当前工作目录、TEMP_DIR、DB/Redis URL 等）
  - 代码位置：`backend/app/routers/storage.py:63`

你应该在浏览器里直接访问：
- `http://<backend-host>:8000/api/storage/debug`

预期：
- 返回 JSON（若 404：说明你根本没命中新后端）
- `features.upload_logs` 为 `true`
- `database_url` 显示的是 Postgres（而不是 `sqlite:///./test.db`）

### 3.2 为什么“错数据库”会造成你看到的所有现象

项目里 `.env` 放在 `backend/.env`。如果服务/脚本启动目录不一致，旧实现可能读不到 `.env`，会回退使用：
- `sqlite:///./test.db`

结果就是：
- 你在 Postgres 里看到了旧数据（字段 NULL/绝对路径）
- 但后端其实写到了 SQLite（或反过来）
- 于是你会觉得“我明明重启/改了代码，怎么还没好”

本次已修复为：优先加载 `backend/.env`，不再依赖启动目录：
- `backend/app/core/database.py:8`
- `backend/app/core/config.py:9`

## 4. 最小复现 + 证据采集（强烈建议照这个做）

请按以下流程“造一条全新的任务”，用它作为证据（不要用历史记录推断）：

1) 重启后端（确保只剩一个后端实例在 8000 上）
2) 前端触发一次新的 `upload-async` 或 `upload-from-url`
3) 记录返回的 `task_id`
4) 对这个 `task_id` 做如下采集（四件事缺一不可）：

### 4.1 采集 A：路由是否存在

- `GET /openapi.json` 搜索 `upload-logs`
- `GET /api/storage/debug` 是否 200

### 4.2 采集 B：DB 行内容（按 task_id 精确查询）

在 Postgres 执行：

```sql
SELECT
  id,
  status,
  filename,
  priority,
  retry_count,
  source_url,
  source_file_path,
  target_url,
  error_message,
  created_at,
  completed_at
FROM upload_tasks
WHERE id = '<task_id>';
```

把结果完整贴出来（尤其是 `priority/retry_count/source_*`）。

### 4.3 采集 C：后端任务日志（若 404 则直接判定命中旧后端）

```http
GET /api/storage/upload-logs/<task_id>?tail=200
```

- 200：把 logs 返回贴出来（至少看得到 `db_path`、入队、worker、状态流转）
- 404：不用再看 DB 字段了，先修“命中旧后端/代理未生效”
- 503：后端连不上 Redis（但 DB 写入仍可能成功）

### 4.4 采集 D：该任务是走的哪个创建接口

- `upload-async`：应该有 `source_file_path`（相对路径 `backend/temp/...`）
  - 写入逻辑位置：`backend/app/routers/storage.py:566`、`backend/app/routers/storage.py:588`
- `upload-from-url`：应该有 `source_url`
  - 写入逻辑位置：`backend/app/routers/storage.py:644`

## 5. 根因枚举（按概率排序）与判断方式

### 根因 1：命中旧后端/路由没更新（高概率）

**特征**
- `/api/storage/upload-logs/...` 404
- 新写入仍出现 `priority/retry_count` NULL
- `source_file_path` 仍写绝对路径（旧逻辑写的）

**判断**
- `GET /api/storage/debug` 是否 200

**处置**
- 确保你只启动了一个后端实例，且前端 proxy 指向它。

### 根因 2：前端 Vite proxy 指向了错误的后端（高概率）

`vite.config.ts` 写死了：
- `/api` -> `http://localhost:8000`

如果你用其它机器访问 Vite（例如 `http://192.168.x.x:5173`），proxy 的 `localhost:8000` 是 **Vite 那台机器的 localhost**，不一定是你想要的后端。

**判断**
- 在 Vite 运行的那台机器上访问 `http://localhost:8000/api/storage/debug` 是否存在

**处置**
- 把 `vite.config.ts` 的 proxy target 改为后端实际地址（例如 `http://192.168.50.22:8000`），或确保后端与 Vite 在同一台机器。

### 根因 3：读写到不同数据库（高概率）

**特征**
- 你“看见”写入不完整，但这些行的 `created_at` 很早/来自旧版本
- 或脚本查出来与后端 API 查出来不一致

**判断**
- `GET /api/storage/debug` 看 `database_url` 是否为 Postgres
- 查 `engine.url` 输出是否为 Postgres

**处置**
- 已在代码层稳定加载 `backend/.env`；重启后端/重跑脚本后再看。

### 根因 4：你认为“不完整”的字段本来就应为空（中概率）

例如：
- `upload-from-url`：`source_file_path` 为空是正常的
- `pending/uploading`：`target_url/completed_at` 为空是正常的

**判断**
- 对照本文第 1 节的“任务来源/阶段”规则。

### 根因 5：历史脏数据仍在（中概率）

即使新任务已经修复，旧任务仍可能：
- `priority/retry_count` NULL
- `source_file_path` 绝对路径

**处置**
- 用脚本回填与归一化（谨慎执行）：
  - `python backend/fix_upload_tasks_data.py`（dry-run）
  - `python backend/fix_upload_tasks_data.py --apply`
  - 脚本位置：`backend/fix_upload_tasks_data.py:58`

## 6. 建议的“最终修复”（把正确性下沉到数据库层）

如果你想彻底杜绝未来再出现 NULL 字段（哪怕有人写错代码），建议在 Postgres 做约束：

1) 让 DB 层提供 DEFAULT + NOT NULL：

```sql
ALTER TABLE upload_tasks ALTER COLUMN priority SET DEFAULT 'normal';
UPDATE upload_tasks SET priority = 'normal' WHERE priority IS NULL;
ALTER TABLE upload_tasks ALTER COLUMN priority SET NOT NULL;

ALTER TABLE upload_tasks ALTER COLUMN retry_count SET DEFAULT 0;
UPDATE upload_tasks SET retry_count = 0 WHERE retry_count IS NULL;
ALTER TABLE upload_tasks ALTER COLUMN retry_count SET NOT NULL;
```

2) 强制至少有一个来源：

```sql
ALTER TABLE upload_tasks
ADD CONSTRAINT upload_tasks_source_check
CHECK (source_file_path IS NOT NULL OR source_url IS NOT NULL);
```

> 注意：加 CHECK 前先清理历史“两个都为空”的记录（目前 worker 启动补偿逻辑会把这类任务标记 failed，但 DB 里旧行仍可能存在）。

## 7. 你需要提供给我/团队的最小信息（用于继续定位）

请贴一条“刚刚新创建”的任务证据，包含：
- `task_id`
- `GET /api/storage/debug` 返回（脱敏即可）
- 上面 SQL 的查询结果（按 task_id）
- `GET /api/storage/upload-logs/<task_id>?tail=200` 的返回（或 404/503）

有了这四样，基本可以 1 轮把根因锁死。
