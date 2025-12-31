# design_v3.md 可行性评审（结合当前代实现）

## 结论（TL;DR）

`design_v3.md` 的总体方向是合理的，并且与当前实现的主要痛点高度对齐：
- 用 `message_attachments` 把“附件 URL 更新”从“重写整段 JSON”降为 O(1) UPDATE
- 用 `message_index + seq` 解决“同毫秒 timestamp 顺序不稳定 / parent_id 断链”
- 用“收敛删除（existing_ids - posted_ids）”适配前端“全量快照写回”语义，避免消息复活
- 用 `messages_generic` 兜底覆盖当前前端已存在的多模式

但当前 `design_v3.md` 仍存在若干与代码现状不一致/实现会直接踩坑的点：
- **附件表缺少 `fileUri` 的持久化**（会破坏“前端零改动”的 API 兼容）
- **模式表字段与 upsert 示例不一致**（示例对所有模式表写 `metadata_json`，但 image/video 专表 DDL 未包含该列）
- **消息组装必须补回 `Message.mode`**（否则前端模式过滤会异常）
- **收敛删除示例里取消 UploadTask 的顺序有 bug**（先删附件再查 deleted_attachment_ids 会查不到）
- **SQLite 默认数据库下 DROP COLUMN 有兼容性风险**（需要在方案中写清楚替代路径）
- **“前端级联删除后续消息”与当前前端行为不符**（当前是“成对删除”，不删后续）

建议将上述点修订进 `design_v3.md` 或以 v3.1 补丁说明后，再按 `tasks.md` 落地。

---

## 现状快照（当前代实现关键点）

### 后端存储/接口现状
- `chat_sessions.messages` 以 JSON 数组存储全部消息：`backend/app/models/db_models.py`（`ChatSession.messages`）
- `POST /api/sessions` 每次覆盖 `messages`，并做“保留已上传云 URL”的合并逻辑：`backend/app/routers/sessions.py`
- `GET /api/sessions/{session_id}/attachments/{attachment_id}` 目前通过扫描 `session.messages` JSON 找附件，再结合 `UploadTask` 返回：`backend/app/routers/sessions.py`
- 上传 Worker/上传任务完成后更新附件 URL 的方式是：深拷贝 JSON → 遍历 → commit，且带重试：
  - `backend/app/services/upload_worker_pool.py`（`_update_session_attachment`）
  - `backend/app/routers/storage.py`（`update_session_attachment_url`）

### 前端数据/行为现状
- `Role` 是 `'user' | 'model' | 'system'`（不是 `'assistant'`）：`frontend/types/types.ts`
- 已存在的 `AppMode` 至少包含：`chat | image-gen | image-edit | video-gen | audio-gen | image-outpainting | pdf-extract | virtual-try-on | deep-research`：`frontend/types/types.ts`
- 删除消息行为：**成对删除**（删除 MODEL 会连同前一条同 mode 的 USER 一起删），不会级联删除后续消息：`frontend/App.tsx`（`handleDeleteMessage`）
- 保存会话时，前端在某些 image-* 模式会清理 Blob/Base64 URL（写入 DB 时置空等待后端上传完成再补回）：
  - `frontend/hooks/useSessions.ts`（`cleanAttachmentsForDb` 调用）
  - `frontend/hooks/handlers/attachmentUtils.ts`（`cleanAttachmentsForDb`）

---

## v3 方案与现状的匹配点（为什么“整体合理”）

1) **`seq` 是必要的**
- 当前消息 `timestamp` 来源于前端 `Date.now()`，同毫秒重复很现实；按 `timestamp` 计算 parent/顺序会不稳定。
- v3 使用 `seq = messages[] 数组下标`，并且查询按 `seq` 排序，能稳定复现前端顺序。

2) **`message_attachments` 能直接解决当前最大复杂点（附件 URL 更新）**
- 当前 Worker/上传完成回写需要修改整段 JSON，且要处理竞态、重试、JSON 变更检测。
- v3 把附件独立为表后，Worker 只需 UPDATE 单行，竞态面明显收缩。

3) **“收敛删除”是与当前前端“快照写回”语义一致的**
- 当前前端保存是发送完整 `ChatSession` 快照；删除消息后再保存，如果后端只做增量 upsert，会导致删除无法落库、甚至“消息复活”。
- v3 的 `existing_ids - posted_ids` 是正确方向。

4) **`messages_generic` 兜底是必须的**
- 现有模式不止 chat/image-gen/video-gen；兜底表可以避免“新增模式就得立即做专表”的落地阻力。

---

## 必须修订/补充项（否则会破坏兼容或实现会报错）

### 1) `message_attachments` 需要持久化 `Attachment.fileUri`（强制）

**原因**：当前前端和后端都在使用 `fileUri`：
- 前端 `AttachmentGrid` 展示 URL 采用 `url || tempUrl || fileUri`
- Google Files API / 多媒体能力会依赖 `fileUri`
- 通义等后端路由也把 `fileUri` 作为 URL 解析优先级的一部分

**修订建议**：
- 在 `message_attachments` 增加 `file_uri TEXT`（或 `file_uri VARCHAR(...)`）
- `to_dict()` 必须输出 `fileUri`
- 迁移脚本需把旧 JSON 里的 `attachments[].fileUri` 迁移到该列

### 2) 专表（image/video）DDL 与 upsert 示例不一致（强制）

`design_v3.md` 的保存示例对模式表写入 `metadata_json=json.dumps(extract_metadata(msg))`，
但 `messages_image_gen` / `messages_video_gen` 的 DDL 未包含 `metadata_json` 列；同时专用字段（image_size 等）在示例里也没有填充来源。

**两条可选修订路径（二选一即可）**：
- 路径 A（推荐，最小歧义）：所有 `messages_*` 表统一包含 `metadata_json TEXT`；专用字段后续再补齐。
- 路径 B（更简单）：上线 MVP 阶段仅落地 `messages_chat + messages_generic`，所有非 chat 的消息先落到 `messages_generic`，等字段来源清晰后再拆专表。

### 3) 组装消息时必须补回 `Message.mode`（强制）

v3 的模式表里没有 `mode` 列，但前端会用 `msg.mode` 做过滤/分视图展示。

**修订建议**：
- 组装 `messages[]` 时，从 `message_index.mode` 写入 `msg_dict['mode'] = idx.mode`
- 或者在模式表冗余 `mode` 列（不推荐，重复存储且易不一致）

### 4) 收敛删除里“取消 UploadTask”示例顺序有 bug（强制）

v3 示例先 `DELETE message_attachments WHERE message_id IN deleted_ids`，
再去查询 `deleted_attachment_ids = SELECT ... FROM message_attachments WHERE message_id=...`，这会查不到，导致无法取消上传任务。

**修订建议**：
- 先查询并缓存 `deleted_attachment_ids`（或直接从 `UploadTask` 侧按 message_id / attachment_id 做更新），再执行删除。
- 且该过程应在同一事务中执行，避免半删状态。

### 5) SQLite 下 `ALTER TABLE DROP COLUMN` 需要方案兜底（强制）

当前默认数据库是 SQLite：`backend/app/core/database.py`（`DATABASE_URL` 默认 `sqlite:///./test.db`）。

`ALTER TABLE ... DROP COLUMN` 在 SQLite 的可用性与版本强相关；即便成功，文件空间也不一定释放，通常还需要 `VACUUM`。

**修订建议**：在迁移章节写清楚两种路径：
- 路径 A：支持 DROP COLUMN 的 SQLite/Postgres：按文档执行
- 路径 B：不支持 DROP COLUMN 的 SQLite：创建新表→拷贝→重命名（或先将 `messages` 置 NULL + VACUUM，保留列但不再使用）

### 6) “前端级联删除后续消息”与当前前端行为不符（建议修订为描述性而非强制）

当前前端删除是“成对删除”，不删后续。后端应当能正确收敛任意子集删除，并重建 `seq/parent_id`。

**修订建议**：
- 文档中不要把“级联删除后续”作为前端硬要求
- 把语义描述改为：后端以快照为准，删除缺失消息，并对剩余消息按新顺序重建同 mode 链

---

## 建议的落地顺序（在 tasks.md 基础上做最小调整）

1) **先修订设计文档的 6 个点**（本评审文档已列出）
2) MVP 建议优先落地：`message_index + messages_chat + messages_generic + message_attachments`
   - image/video 专表先不强依赖（避免字段来源不清导致返工）
3) 改造后端：
   - `GET /api/sessions`：按 `seq` 批量组装 + 补回 `mode` + 批量附加 attachments
   - `POST /api/sessions`：收敛删除 + 事务化 upsert + 云 URL 保护逻辑
   - `GET /api/sessions/{id}/attachments/{att_id}`：直接查新表 + 结合 UploadTask
   - Worker：直接 UPDATE `message_attachments`
4) 迁移：补充“SQLite 兼容路径”与验证脚本；并考虑停机窗口期间 HybridDB 降级到 LocalStorage 的行为（是否需要维护提示/禁止写入）

---

## 可行性结论

在补齐/修订上述关键点后，`design_v3.md` 作为“当前代实现的下一代存储方案”是**可行且收益明确**的。
若不修订，至少会在“附件 fileUri 丢失”“模式表字段不一致导致写入报错”“mode 丢失导致前端过滤异常”等处直接破坏兼容性。
