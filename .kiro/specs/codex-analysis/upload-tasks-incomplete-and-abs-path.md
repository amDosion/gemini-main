# upload_tasks 字段不完整 / source_file_path 仍为绝对路径（排查与修复）

## 现象

- 前端持续请求 `GET /api/storage/upload-logs/{task_id}`，浏览器控制台显示 `404 (Not Found)`，导致日志轮询刷屏。
- 在 `upload_tasks` 表中观察到部分记录字段为 `NULL`（常见：`priority`、`retry_count`），以及 `source_file_path` 仍是绝对路径（例如 `C:\...` / `D:\...`）。

## 最常见根因（按出现概率排序）

### 1) 命中“旧后端实例”或代理未生效

`/api/storage/upload-logs/...` 返回 404 的含义非常明确：
- 要么后端未更新到包含该路由的版本；
- 要么前端并未真正代理到后端（请求被 Vite/静态站点自身 404 处理）。

**快速自检**：
- 访问 `GET /api/storage/debug`（本次已新增）。能返回 JSON 说明命中的是新后端代码。
- 访问 `GET /openapi.json` 搜索 `upload-logs`，确认路由是否存在。

### 2) 启动目录不同导致“读/写的是不同数据库”

项目里 `.env` 放在 `backend/.env`。如果运行脚本/服务时工作目录不是 `backend/`，旧实现可能读不到 `.env`，从而回退到 `sqlite:///./test.db`，造成：
- 后端服务写入的是 Postgres，但脚本在查 SQLite（或相反）；
- 你看到的“字段不完整/路径不一致”其实来自另一个数据库实例。

**修复**：
- `backend/app/core/database.py` 与 `backend/app/core/config.py` 已改为优先加载 `backend/.env`（与启动目录无关）。

### 3) 历史脏数据仍存在

在修复前创建的任务可能已经把 `priority/retry_count/source_file_path` 写成了 `NULL` 或绝对路径。
即使现在新任务已修复，旧记录仍会让你“看起来没修好”。

**修复**：
- 新增脚本 `backend/fix_upload_tasks_data.py`，用于回填缺失字段并把 `backend/temp` 下的绝对路径转成相对路径。

## 已落地修复（代码）

- 后端：
  - `backend/app/routers/storage.py`：`source_file_path` 统一写成 `backend/temp/...`（使用 `/`，跨平台更稳）。
  - `backend/app/routers/storage.py`：新增 `GET /api/storage/debug`，用于确认命中后端版本/环境。
  - `backend/app/core/database.py`、`backend/app/core/config.py`：稳定加载 `backend/.env`，避免误连 SQLite。
- 前端：
  - `frontend/services/storage/storageUpload.ts`：当 `/upload-logs` 首次返回 404 时停止继续拉取，避免轮询刷屏。
- 运维脚本：
  - `backend/fix_upload_tasks_data.py`：支持 dry-run，`--apply` 执行写入。

## 操作建议（你现在应该怎么做）

1. 重启后端后，先访问 `GET /api/storage/debug`，确认能返回 `features.upload_logs=true`。
2. 触发一次新的 `upload-async`，拿到 `task_id` 后访问：
   - `GET /api/storage/upload-status/{task_id}`（看 `sourceFilePath` 是否相对路径）
   - `GET /api/storage/upload-logs/{task_id}`（看是否仍 404）
3. 如果 DB 里还有历史记录不完整/绝对路径：运行
   - `python backend/fix_upload_tasks_data.py`（dry-run）
   - `python backend/fix_upload_tasks_data.py --apply`（执行写入）

