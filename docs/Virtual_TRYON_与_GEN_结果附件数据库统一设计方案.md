# Virtual Try-On 与 GEN 模式结果 / 附件 / 数据库统一设计方案

> **版本**: v1.0  
> **创建日期**: 2026-01-24  
> **状态**: 设计阶段  
> **关联文档**: [GEN模式完整流程分析_前端与后端_2026-01-24.md](./GEN模式完整流程分析_前端与后端_2026-01-24.md)、[路由与逻辑分离架构设计文档](./路由与逻辑分离架构设计文档.md)、[UNIFIED_ATTACHMENT_PROCESSING_DESIGN](./UNIFIED_ATTACHMENT_PROCESSING_DESIGN.md)

---

## 一、背景与目标

### 1.1 问题描述

在 **GEN（图片生成）** 和 **Edit（图片编辑）** 模式下，后端对 AI 返回的图片会：

1. **写入数据库**：`AttachmentService.process_ai_result` 创建 `MessageAttachment` 记录；
2. **入队 Worker**：提交上传任务到 Redis，由 Worker 异步上传云存储；
3. **标准化响应**：返回 `images` 数组，每项含 `url`、`attachmentId`、`uploadStatus`、`taskId`、`mimeType`、`filename`；
4. **会话持久化**：前端通过 `sessionId`、`message_id` 关联附件，并将会话（含消息与附件）保存到 `/api/sessions`。

**Virtual Try-On（虚拟试衣）** 当前 **未** 走上述流程：试衣结果仅以 Base64 / Data URL 形式返回，不入库、不入队、不关联会话，前端只保存在内存（如 `tryOnHistory`），刷新即丢失。

### 1.2 设计目标

- **与 GEN/Edit 对齐**：试衣结果同样经 `AttachmentService` 落库、入队、返回标准化 `images`；
- **可持久化**：试衣结果可关联 `session_id`、`message_id`，随会话保存与恢复；
- **架构一致**：在不破坏「路由与逻辑分离」的前提下，尽量复用现有 modes 流程与 Attachment 设计。

---

## 二、GEN/Edit 模式现状（结果与附件流程）

以下为提炼要点，完整流程见 [GEN模式完整流程分析_前端与后端_2026-01-24](./GEN模式完整流程分析_前端与后端_2026-01-24.md)。

### 2.1 后端：modes 步骤 7 与 AttachmentService

| 项目 | 说明 |
|------|------|
| **触发条件** | `method_name in ["generate_image", "edit_image"]`（`modes.py` 步骤 7） |
| **依赖参数** | `request_body.options` 中的 `frontend_session_id` / `sessionId`、`message_id` |
| **服务返回格式** | `result` 为 `List[Dict]` 或 `dict` 且含 `images`；每项有 `url` / `image`、`mimeType` / `mime_type`，可选 `filename` |
| **处理逻辑** | 对每张图调用 `AttachmentService.process_ai_result(ai_url, mime_type, session_id, message_id, user_id, prefix)` |
| **process_ai_result** | 创建 `MessageAttachment`、提交 Redis 上传任务、返回 `{ attachment_id, display_url, status, task_id }` |
| **响应构建** | 将 `processed_images`（含 `url`、`attachmentId`、`uploadStatus`、`taskId`、`mimeType`、`filename`）写回 `result["images"]` 或 `result = processed_images` |

**代码位置**：

- `backend/app/routers/core/modes.py`：步骤 7，约 551–636 行；
- `backend/app/services/common/attachment_service.py`：`process_ai_result`，约 139–268 行。

### 2.2 前端：Handler、options 与会话保存

| 项目 | 说明 |
|------|------|
| **Strategy / Handler** | `ImageGenHandler`、`ImageEditHandler` 等；`doExecute` 内构造 `genOptions` / `editOptions`，包含 `frontend_session_id`、`sessionId`、`message_id`（`modelMessageId`） |
| **请求** | `executeMode('image-gen'|...)` 时，将上述 options 传入，后端从 `request_body.options` 取 `session_id`、`message_id` |
| **结果处理** | 后端返回 `data.images`；`UnifiedProviderClient.executeMode` 对 `image-gen` / `image-*` 且 `data.data.images` 存在时，映射为 `ImageGenerationResult[]`（`url`、`mimeType`、`attachmentId`、`uploadStatus`、`taskId` 等） |
| **会话与消息** | Handler 返回 `{ content, attachments, uploadTask }`；useChat 更新 model 消息、执行 `uploadTask`，再 `updateSessionMessages` → `saveSessionToDb`（POST /api/sessions），消息与附件一并持久化 |

因此，GEN/Edit 的 **结果**、**附件**、**数据库** 流程是统一的。

---

## 三、Virtual Try-On 模式现状与差异

### 3.1 后端

| 项目 | 当前实现 |
|------|----------|
| **路由** | `POST /api/modes/{provider}/virtual-try-on`，`get_service_method` → `virtual_tryon` |
| **步骤 7** | **不触发**：`virtual_tryon` 不在 `["generate_image", "edit_image"]` 中 |
| **服务返回** | `GoogleService.virtual_tryon` → `TryOnService`，返回 `{ image, mimeType }`（单图） |
| **AttachmentService** | **未调用** |
| **Worker / 入队** | **无** |
| **响应** | `data` 直接为 `{ image, mimeType }`，无 `images`、`attachmentId`、`taskId` 等 |

### 3.2 前端

| 项目 | 当前实现 |
|------|----------|
| **视图** | `VirtualTryOnView`，独立布局（人物图 / 服装图 / 试衣结果） |
| **发送流程** | 使用 **自定义 `handleSend`**，直接 `UnifiedProviderClient.executeMode('virtual-try-on', ...)`，**不经过** strategy / handler |
| **options** | **未传** `sessionId`、`message_id` |
| **结果消费** | `executeMode` 返回 `data.data` → `{ image, mimeType }`；用 `result.image` 作 `resultUrl`，仅更新本地 `tryOnHistory`、`activeResult` |
| **会话 / 消息** | **不写** messages，**不** `updateSessionMessages`，**不** POST /api/sessions；试衣历史仅在前端内存 |

### 3.3 差异小结

| 维度 | GEN / Edit | Virtual Try-On（当前） |
|------|------------|-------------------------|
| 步骤 7 / AttachmentService | ✅ 执行 | ❌ 不执行 |
| 数据库附件记录 | ✅ 有 | ❌ 无 |
| Worker 上传 | ✅ 入队、异步上传 | ❌ 无 |
| 响应格式 | `data.images` 标准化 | `data` 为 `{ image, mimeType }` |
| sessionId / message_id | ✅ 传递并使用 | ❌ 不传递 |
| 会话持久化 | ✅ 随 messages 保存 | ❌ 仅本地 state |

---

## 四、统一设计方案

### 4.1 原则

1. **复用既有能力**：尽量沿用 modes 步骤 7、`AttachmentService`、Worker 机制；
2. **契约统一**：试衣结果与 GEN/Edit 一样，以 `data.images` 返回，结构一致；
3. **可选持久化**：当请求带 `session_id`、`message_id` 时落库、入队；不带时仍可仅返回图片（兼容现有「仅展示」用法，若产品需要）。

### 4.2 方案 A：扩展 modes 步骤 7（推荐，若允许改 modes）

**思路**：将 `virtual_tryon` 纳入步骤 7 的“结果处理”分支，与 `generate_image`、`edit_image` 同等对待。

**后端**：

1. **modes.py**  
   - 步骤 7 条件改为：  
     `method_name in ["generate_image", "edit_image", "virtual_tryon"]`  
   - 其余逻辑不变：从 `options` 取 `session_id`、`message_id`，对 `result` 中的每张图调用 `process_ai_result`，写回 `result["images"]`。

2. **GoogleService.virtual_tryon**  
   - 返回格式改为与 GEN 对齐：  
     `{ "images": [ { "url": "<data_url 或 future 云 url>", "mimeType": "...", "filename": "tryon-<uuid>.png" } ] }`  
   - 即单张试衣图包成 `images` 数组，字段与 `generate_image` 的单项一致，便于步骤 7 统一处理。

3. **步骤 7 对 virtual_tryon**  
   - `prefix` 可用 `"tryon"`；  
   - 有 `session_id`、`message_id` 时：`process_ai_result` → 落库、入队，响应里带 `attachmentId`、`uploadStatus`、`taskId`；  
   - 缺其一则与当前 GEN/Edit 一样跳过附件处理（或按产品决定是否强制要求）。

**前端**：

1. **选项 1：完全走 Handler + 会话**  
   - Virtual Try-On 也经 `VirtualTryOnHandler` + useChat：创建 user/model 消息，传 `sessionId`、`message_id`，走 `executeMode`；  
   - 结果按 `data.images` 解析，得到 `ImageGenerationResult[]`，写回 model 消息、`updateSessionMessages`，与 GEN 一致。

2. **选项 2：保留自定义 UI，但对接统一契约**  
   - `VirtualTryOnView` 仍自定义 `handleSend`，但：  
     - 在调用 `executeMode` 前，像 GEN 一样创建 model 占位消息，拿到 `message_id`，并传入 `sessionId`、`message_id` 到 options；  
     - 请求体、attachments 等仍由视图组织；  
   - 后端返回 `data.images` 后，视图从 `images[0]` 取 `url` 等，更新本地 `tryOnHistory`；同时可把该条结果同步进 messages（若希望进会话历史）。

**优点**：与 GEN/Edit 共有一套步骤 7 逻辑，维护简单，行为一致。  
**缺点**：需修改 `modes.py`（若项目约束不允许改动，则采用方案 B）。

---

### 4.3 方案 B：服务层自处理附件（不修改 modes 步骤 7）

**思路**：modes 步骤 7 条件 **保持不变**；在 `GoogleService.virtual_tryon` 内部，当存在 `session_id`、`message_id` 时，自行调用 `AttachmentService.process_ai_result`，并返回与 GEN 相同的 `{ images: [...] }` 结构。

**后端**：

1. **GoogleService.virtual_tryon**  
   - 从 `kwargs`（即 modes 传入的 `params`）中读取 `session_id`、`message_id`（可与 GEN 一样从 `options` 映射：`frontend_session_id`/`sessionId` → `session_id`，`message_id` 即 `message_id`）。  
   - 调用 `TryOnService` 得到试衣图（Base64 / data URL）。  
   - **若** `session_id` 与 `message_id` 均有：  
     - 使用 `AttachmentService(db).process_ai_result(ai_url, mime_type, session_id, message_id, user_id, prefix="tryon")`；  
     - 将返回的 `display_url`、`attachment_id`、`status`、`task_id` 等组装成 `images` 一项；  
   - **否则**：  
     - 仅返回 `{ "images": [ { "url": data_url, "mimeType": "..." } ] }`，无 `attachmentId`、`taskId`（兼容不落库场景）。  
   - 统一返回 `{ "images": [ ... ] }`，以便前端按 `data.images` 处理。

2. **modes**  
   - 不再为 `virtual_tryon` 单独做步骤 7；`virtual_tryon` 返回的 `result` 已自带 `images`，modes 原样塞入 `ModeResponse.data` 即可。

**前端**：  
同方案 A 的两种选项（Handler + 会话 或 自定义 UI + 传 `sessionId`/`message_id` 并解析 `data.images`）。

**优点**：不修改 modes 步骤 7，仅改服务层。  
**缺点**：附件处理逻辑在服务里多一份分支，需注意与 `process_ai_result` 的约定一致（如 `prefix`、字段含义）。

---

### 4.4 方案对比与推荐

| 项目 | 方案 A（扩展 modes） | 方案 B（服务层自处理） |
|------|----------------------|---------------------------|
| 修改 modes | ✅ 是 | ❌ 否 |
| 修改 GoogleService | ✅ 返回 `images` | ✅ 调 AttachmentService + 返回 `images` |
| 流程一致性 | 高，与 GEN/Edit 完全同一路径 | 中，结果格式统一，处理位置不同 |
| 适用约束 | 允许改 modes | 禁止改 modes |

- **若允许修改 modes**：推荐 **方案 A**。  
- **若禁止修改 modes**：采用 **方案 B**，并在设计上明确：Virtual Try-On 的附件落地、入队完全在 `GoogleService.virtual_tryon` 内完成。

---

## 五、统一后的数据流（以方案 A 为例）

```
前端 Virtual Try-On
  → 传 sessionId、message_id（经 Handler 或自定义 handleSend）
  → executeMode('virtual-try-on', ..., options)
  → POST /api/modes/{provider}/virtual-try-on

modes
  → 认证、凭证、ProviderFactory、params（含 options）
  → service.virtual_tryon(**params)
  → 返回 { images: [ { url, mimeType, filename? } ] }

modes 步骤 7（virtual_tryon 已纳入）
  → session_id、message_id 从 options 取
  → 对 images 每项：AttachmentService.process_ai_result
  → 落库、入队、返回 attachmentId、uploadStatus、taskId
  → 写回 result["images"]

响应
  → data.images 标准化，与 GEN/Edit 一致

前端
  → 解析 data.images，更新 UI / messages
  → updateSessionMessages → POST /api/sessions（若走会话）
```

方案 B 的差别仅在于：步骤 7 不处理 `virtual_tryon`，`images` 的生成与 `process_ai_result` 调用在 `GoogleService.virtual_tryon` 内完成。

---

## 六、实施要点（清单）

### 6.1 后端

- [ ] **方案 A**：在 `modes.py` 步骤 7 中增加 `virtual_tryon`；**或**  
- [ ] **方案 B**：在 `GoogleService.virtual_tryon` 中根据 `session_id`、`message_id` 调用 `AttachmentService.process_ai_result`，并统一返回 `{ images }`。
- [ ] `GoogleService.virtual_tryon` 返回格式从 `{ image, mimeType }` 改为 `{ images: [ { url, mimeType, filename? } ] }`。
- [ ] 若采用方案 B，确保 `AttachmentService` 的调用约定（`user_id`、`db`、`prefix` 等）与 GEN/Edit 一致。

### 6.2 前端

- [ ] 调用 `executeMode('virtual-try-on', ...)` 时传入 `sessionId`、`message_id`（从当前会话与 model 占位消息取）。
- [ ] 按 `data.images` 解析结果；若 `UnifiedProviderClient` 对 `virtual-try-on` 未做特殊分支，可扩展为与 `image-gen` / `image-*` 一样映射 `data.data.images` → `ImageGenerationResult[]`。
- [ ] 若走 Handler：`VirtualTryOnHandler` 传入 `sessionId`、`message_id`，并像 `ImageGenHandler` 一样处理 `images`、`uploadTask`、会话更新。
- [ ] 若保留自定义 `VirtualTryOnView`：在 `handleSend` 里传入 `sessionId`、`message_id`，解析 `images`，并视需求同步到 messages / `updateSessionMessages`。

### 6.3 兼容与回归

- [ ] 不传 `session_id` / `message_id` 时，行为可保留为「仅返回图片、不入库」；具体以产品需求为准。
- [ ] 回归：GEN、Edit、Virtual Try-On 三种模式下，结果均具备 `images`、`attachmentId`、`uploadStatus`、`taskId`，且均可持久化到会话。

---

## 七、参考资料

- [GEN模式完整流程分析_前端与后端_2026-01-24](./GEN模式完整流程分析_前端与后端_2026-01-24.md)：GEN 前后端流程、步骤 7、AttachmentService、Worker。
- [路由与逻辑分离架构设计文档](./路由与逻辑分离架构设计文档.md)：modes、ProviderFactory、服务委托。
- [UNIFIED_ATTACHMENT_PROCESSING_DESIGN](./UNIFIED_ATTACHMENT_PROCESSING_DESIGN.md)：附件统一处理与后端化。
- `backend/app/routers/core/modes.py`：步骤 5–8、步骤 7 条件与 `process_ai_result` 调用。
- `backend/app/services/common/attachment_service.py`：`process_ai_result` 入参、出参、落库与入队。
