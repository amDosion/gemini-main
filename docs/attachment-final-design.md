# 附件系统完整分析与设计文档

> 版本：1.0 | 日期：2026-04-12 | 状态：待评审
> 整合自 4 份分析文档，覆盖前端入口、后端路由、服务层、数据库、工具函数映射

---

## 一、背景与发现

### 1.1 `attachment_handler.py` 的历史

2026-03-21 的 `backup: stable state before architecture optimization` 提交中，同时创建了：

| 文件 | 位置 | 行数 | 当前状态 |
|------|------|:---:|---------|
| `attachmentUtils.ts` | `frontend/hooks/handlers/` | 1191 | **11 个文件导入，正常使用** |
| `attachment_handler.py` | `backend/app/utils/` | 791 | **0 个文件导入，完全死代码** |

两者是同一设计的前后端配对——前端被正确集成，后端写好了但**从未被接入**。后续开发继续在各处写内联实现，这个文件被遗忘。

### 1.2 项目中散落的等价内联实现

| attachment_handler.py 函数 | 内联实现数量 | 可安全替换 | 风险 |
|---|:---:|:---:|:---:|
| `is_base64_url()` | **39 处** | ~20 处 | 低 |
| `is_blob_url()` | **10 处** | ~7 处 | 低 |
| `is_http_url()` | **20+ 处** | ~5 处 | 低 |
| `get_url_type()` | **3 处** | 全部 | 低 |
| `parse_data_url()` | **15 处** | ~7 处 | 中 |
| `encode_to_data_url()` | **15 处** | ~12 处 | 低 |
| `base64_to_bytes/bytes_to_base64` | **83 处** | 少量 | 高 |
| `get_extension_from_mime()` | **6 处** | 全部 | 低 |
| `Attachment` dataclass | **0 处** | N/A | — |
| `AttachmentHandler` 类 | **0 处** | N/A | — |

---

## 二、附件系统全景

### 2.1 前端 Attachment 接口

**`frontend/types/types.ts:103`** — 唯一前端定义，27 字段超集：

```typescript
interface Attachment {
  id: string; mimeType: string; name: string;          // 核心标识
  url?: string; fileUri?: string; base64Data?: string;  // 数据源
  googleFileUri?: string; tempUrl?: string;              // 数据源（续）
  file?: File; kind?: string; language?: string;        // 本地引用
  uploadStatus?: 'pending'|'uploading'|'completed'|'failed'; // 状态机
  uploadTaskId?: string; uploadError?: string; cloudUrl?: string;
  size?: number; messageId?: string; sessionId?: string;
  userId?: string; createdAt?: number; googleFileExpiry?: number;
  enhancedPrompt?: string;
}
```

### 2.2 后端 3 处定义 + 1 数据库模型

| 字段 | chat.py Pydantic | modes.py Pydantic | handler.py dataclass | MessageAttachment DB |
|------|:---:|:---:|:---:|:---:|
| **id** | 必需 | 可选 | 必需 | PK `String(36)` |
| **mime_type** | 必需 | 可选 | 必需 | `String(100)` |
| **name** | 必需 | 可选 | 必需 | `String(255)` |
| **url** | 可选 | 可选 | 必需 | `Text` |
| **temp_url** | 可选 | 可选 | 可选 | `Text` |
| **file_uri** | 可选 | 可选 | — | `Text` |
| **base64_data** | 可选 | 可选 | — | — |
| **google_file_uri** | 可选 | **缺失 ⚠️** | — | `String(500)` |
| **role** | — | 可选 | — | — |
| **size** | — | — | 可选 | `BigInteger` |
| **upload_status** | — | — | 默认`pending` | `String(20)` |

**各定义的职责**：
- **chat.py Attachment** → `POST /{provider}/chat`，严格模型（id/mime_type/name 必需）
- **modes.py Attachment** → `POST /modes/{mode}`，宽松模型（全可选，支持只传 role+url）
- **handler.py Attachment** → 零引用，原设计为工具类数据结构但未集成
- **MessageAttachment** → 数据库 ORM，事实上的统一模型，包含所有字段超集

### 2.3 附件的 6 种入口

| # | 入口 | 触发 | 附件来源 |
|---|------|------|---------|
| 1 | 用户手动上传 | `ChatInputArea.handleFileSelect()` | File → Blob URL |
| 2 | 拖拽上传 | `useDragDrop.handleDrop()` → 复用上传 | File → Blob URL |
| 3 | 从画布编辑 | `useImageHandlers.handleEditImage()` | AI 生成图片 URL/Base64 |
| 4 | 从画布扩图 | `useImageHandlers.handleExpandImage()` | 同上 |
| 5 | AI 返回结果 | SSE stream → `AllHandlerClasses` | Base64/HTTP URL |
| 6 | 画布延续 | `active_image_url` → `resolve_continuity_attachment()` | 画布当前图片 |

### 2.4 两条独立的处理管道

```
管道 A: Chat 模式
  前端 Attachment → POST /api/{provider}/chat
    → chat.py Attachment（id/mime_type/name 必需）
    → MessageConverter._build_attachment_part()
    → Google Part: file_data / inline_data
  特点: 使用 google_file_uri，不用 role

管道 B: Modes 模式
  前端 Attachment → POST /api/modes/{mode}
    → modes.py Attachment（全可选）
    → convert_attachments_to_reference_images()
    → reference_images 字典 → 各 Coordinator
  特点: 使用 role 区分附件角色，google_file_uri 缺失但服务层在用
```

**数据源优先级不同**：
- Chat 管道: `fileUri → url/tempUrl(data:) → base64Data`
- Modes 管道: `url → tempUrl → fileUri → base64Data`
- Video 管道: `url → tempUrl → fileUri(非files//gs://) → base64Data(构造data:URL)`

### 2.5 6 种模式的附件处理差异

| 模式 | 管道 | 附件用途 | role | google_file_uri | 特有逻辑 |
|------|:---:|---------|:---:|:---:|---------|
| **chat** | A | 聊天附件 | ✗ | ✅ | fileUri 优先，内联到消息 |
| **image-gen** | B | 图生图参考图 | ✗ | ✗ | → reference_images['raw'] |
| **image-chat-edit** | B | 对话式编辑原图 | ✗ | ✅(隐式) | 多轮复用 google_file_uri |
| **image-mask-edit** | B | 原图 + 掩码 | ✅ mask | ✗ | 2 个附件按 role 分类 |
| **image-outpainting** | B | 扩图原图 | ✗ | ✗ | 同 image-gen + 扩图参数 |
| **video-gen** | B | 8 种角色附件 | ✅ 8种 | ✗ | video_mode_contract 分类 |

**Video-gen role 值映射**：
| role | 分类 |
|------|------|
| `mask` | mask_items |
| `last_frame`/`end_frame`/`target_frame` | last_frame_items |
| `source`/`source_image`/`start_frame`/`first_frame` | source_image_items |
| `reference`/`reference_image`/`style_reference` | reference_image_items |
| (mime=video/*) | video_items |
| (mime=image/*) | image_items |

### 2.6 跨模式附件传递流程

```
场景: 用户在 chat 收到 AI 图片 → 点击"编辑"

1. [后端] AI 返回 base64 → process_ai_result → 创建 MessageAttachment
   → 返回 display_url=/api/temp-images/{id}
2. [前端] 用户看到图片 → 点击"编辑"
3. [前端] useImageHandlers.handleEditImage(url, attachment)
   → 构造新 Attachment → setInitialAttachments → setAppMode('image-chat-edit')
4. [前端] 模式切换 → 新 ChatInputArea 收到 initialAttachments
5. [前端] 用户发送 → POST /api/modes/image-chat-edit
6. [后端] modes.py → convert_attachments_to_reference_images
   → 如果有 attachment_id → 查 DB 获取云 URL
```

### 2.7 附件状态机

```
pending → uploading → completed
                    → failed
```

- **前端创建**: `ChatInputArea` → `uploadStatus='pending'`
- **后端处理**: `AttachmentService.process_*` → 创建 DB 记录 → 提交 Worker Pool
- **Worker Pool**: 上传完成 → `upload_status='completed'`, `url=云URL`
- **前端轮询**: `PollingManager` → 更新 `cloudUrl`

### 2.8 完整存储链路

```
[用户选择文件] → File → Blob URL → Attachment{uploadStatus:'pending'}
  ↓ (上传)
[Handler] → storageUpload.uploadAttachment(file) → /api/storage/upload
  ↓ (轮询)
[PollingManager] → /api/storage/upload-status/{taskId} → cloudUrl
  ↓ (发送消息)
[Chat] POST /api/{provider}/chat → MessageConverter._build_attachment_part()
  → fileUri → file_data | data:URL → inline_data | base64Data → inline_data
[Modes] POST /api/modes/{mode} → convert_attachments_to_reference_images()
  → reference_images dict → Coordinator
  ↓ (Google API)
file_data: {file_uri, mime_type} | inline_data: {data, mime_type}
```

### 2.9 后端关键服务

| 服务 | 文件 | 核心方法 | 职责 |
|------|------|---------|------|
| **AttachmentService** | `services/common/attachment_service.py` | `process_user_upload()` | 用户上传 → DB + Worker Pool |
| | | `process_ai_result()` | AI 返回 → DB + 代理 URL + Worker Pool |
| | | `resolve_continuity_attachment()` | 画布延续 → 查消息 → 查 DB → 云 URL |
| **MessageConverter** | `services/gemini/common/message_converter.py:105` | `_build_attachment_part()` | 附件 → Google API Part |
| **VideoModeContract** | `services/common/video_mode_contract.py:75` | `merge_video_mode_attachment_params()` | 按 role 分类视频附件 |
| **UploadWorkerPool** | `services/common/upload_worker_pool.py` | 异步上传 | 后台上传到云存储 |

### 2.10 数据库 MessageAttachment

```
表名: message_attachments
复合主键: (id, message_id)

字段:
  id              String(36)   PK    附件 ID
  message_id      String(36)   PK    所属消息 ID
  user_id         String       NN    用户 ID
  session_id      String(36)   NN    会话 ID
  mime_type       String(100)        MIME 类型
  name            String(255)        文件名
  url             Text               云端永久 URL（权威来源）
  temp_url        Text               临时 URL
  file_uri        Text               通用文件 URI
  upload_status   String(20)  ='pending'
  upload_task_id  String(36)         关联上传任务
  upload_error    Text               失败原因
  google_file_uri String(500)        Google Files API URI（48h 有效）
  google_file_expiry BigInteger      过期时间(ms)
  size            BigInteger         文件大小
```

**CRUD 分布**：CREATE 5 处 | UPDATE 4 处 | SELECT 10+ 处 | DELETE 2 处

---

## 三、工具函数映射（精确到文件:行号）

### 3.1 `is_base64_url()` — 39 处 `startswith('data:')`

**可直接替换（简单独立判断）**：

| 文件 | 行号 | 函数/上下文 |
|------|------|------------|
| `routers/ai/multi_agent.py` | 747 | `_normalize_artifact_url` |
| `routers/ai/multi_agent.py` | 1238 | `_register_agent_or_build_card` |
| `routers/core/attachments.py` | 262, 345 | `_proxy_base64_attachment` / `_parse_data_url` |
| `routers/core/modes.py` | 1207, 1271, 1279, 1301, 1326 | continuity / DB 回查 / 数据提取 |
| `routers/user/sessions.py` | 456 | session 保存过滤 |
| `services/gemini/common/message_converter.py` | 135, 152 | `_build_attachment_part` |
| `services/gemini/common/chat_session_manager.py` | 234 | 会话管理 |
| `services/gemini/common/chat_handler.py` | 1128, 1144 | 附件处理 |
| `services/gemini/geminiapi/conv..._edit_service.py` | 195, 774 | 图片编辑 |
| `services/common/attachment_service.py` | 377, 390, 421, 426, 512, 750 | 附件服务多处 |
| `services/gemini/agent/workflow_template_sample.py` | 333, 416 | 模板处理 |

**不宜替换（含 MIME 子类型判断）**：

| 文件 | 行号 | 原因 |
|------|------|------|
| `routers/ai/workflows.py` | 1470-1476 | 分 `data:image/` `data:audio/` `data:video/` 三类 |
| `routers/ai/workflows.py` | 1706, 1942, 1965, 1999, 2027 | 动态 `f"data:{kind}/"` 前缀 |
| `routers/core/modes.py` | 1158, 1551 | 三元内联含 blob+http 联合 |

### 3.2 `is_blob_url()` — 10 处 `startswith('blob:')`

| 文件 | 行号 | 可替换 |
|------|------|:---:|
| `routers/ai/multi_agent.py` | 824 | ✅ |
| `routers/user/sessions.py` | 456 | ✅ |
| `services/common/attachment_service.py` | 377, 390, 512, 750 | ✅ |
| `services/gemini/agent/workflow_template_sample.py` | 502 | ✅ |
| `routers/ai/workflows.py` | 1561, 2144, 2419 | ⚠️ 混合判断 |
| `routers/core/modes.py` | 1158 | ❌ 三元内联 |

### 3.3 `parse_data_url()` — 15 处 data URL 解析

**完整解析（提取 mime + data）— 可替换**：

| 文件 | 行号 | 实现方式 |
|------|------|---------|
| `routers/core/attachments.py` | 349 | `split(',', 1)` + mime 提取 |
| `routers/ai/workflows.py` | 1943-1944, 1966-1967, 2000-2001 | `split(":",1)[1].split(";",1)[0]` |
| `services/gemini/agent/workflow_template_sample.py` | 417-418 | 同上 |
| `services/gemini/base/video_common.py` | 545-552 | `split(",",1)` + mime |

**仅提取 base64 部分（需新函数 `extract_base64_from_data_url`）**：

| 文件 | 行号 |
|------|------|
| `routers/core/modes.py` | 1302, 1327 |
| `services/gemini/vertexai/expand_service.py` | 1108, 1163, 1239 |
| `services/gemini/vertexai/tryon_service.py` | 53 |
| `services/gemini/vertexai/segmentation_service.py` | 220 |
| `services/gemini/vertexai/vertex_edit_base.py` | 323 |
| `services/gemini/geminiapi/conv..._edit_service.py` | 1059 |

### 3.4 `encode_to_data_url()` — 15 处 `f"data:{mime};base64,{data}"`

| 文件 | 行号 | 可替换 |
|------|------|:---:|
| `agent/tools/excel_tools.py` | 476 | ✅ |
| `agent/workflow_template_sample.py` | 316 | ✅ |
| `geminiapi/imagen_gemini_api.py` | 334, 445 | ✅ |
| `geminiapi/conv..._edit_service.py` | 1041, 1080, 1394, 1415, 1449 | ⚠️ 部分嵌入字典 |
| `vertexai/imagen_vertex_ai.py` | 350, 478 | ✅ |
| `vertexai/expand_service.py` | 511, 634, 772, 1066 | ✅ |

### 3.5 `get_extension_from_mime()` — 6 处

| 文件 | 行号 | 可替换 |
|------|------|:---:|
| `routers/storage/storage.py` | 2837 | ✅ |
| `services/gemini/base/video_common.py` | 577 | ✅ |
| `services/common/attachment_service.py` | 893 | ✅ |
| `services/agent/workflow_history_media.py` | 160 | ✅ |
| `services/agent/workflow_history_image.py` | 260 | ✅ |

### 3.6 `base64_to_bytes / bytes_to_base64` — 83 处（不建议批量替换）

20 个文件 `import base64`，大多嵌入业务逻辑（图片处理流水线、AI SDK 返回解析）。仅以下模式适合替换：
- `base64.b64decode(data_url.split(',',1)[1])` → `base64_to_bytes(data_url)`
- `base64.b64encode(bytes).decode('utf-8')` → `bytes_to_base64(bytes)`

---

## 四、设计方案

### 4.1 目标

1. 消除 40+ 处散落的 URL 类型检测重复
2. 消除 15+ 处散落的 data URL 解析重复
3. 不破坏任何现有功能（两条管道逻辑不变）
4. 不强制统一 Pydantic 模型（chat.py / modes.py 各保留）

### 4.2 保留并增强的工具函数

```python
# ✅ 已有，直接可用
is_base64_url(url) → bool
is_blob_url(url) → bool
is_http_url(url) → bool
get_url_type(url) → str          # 'base64'|'blob'|'http'|'empty'|'unknown'
parse_data_url(data_url) → (mime_type, binary_data)
encode_to_data_url(binary_data, mime_type) → str
base64_to_bytes(base64_str) → bytes
bytes_to_base64(binary_data) → str
get_extension_from_mime(mime_type) → str
get_mime_from_extension(filename) → str
```

### 4.3 新增函数

```python
# 细粒度解析（现有场景需要只取 base64 或只取 mime）
extract_base64_from_data_url(data_url: str) → str    # 只返回 base64 部分
extract_mime_from_data_url(data_url: str) → str       # 只返回 mime 部分

# 带 MIME 子类型的检测（workflows.py 的 data:image/ 等场景）
is_base64_image_url(url: str) → bool   # startswith('data:image/')
is_base64_audio_url(url: str) → bool   # startswith('data:audio/')
is_base64_video_url(url: str) → bool   # startswith('data:video/')
```

### 4.4 替换规则

| 当前内联代码 | 替换为 | 风险 |
|-------------|--------|:---:|
| `url.startswith('data:')` | `is_base64_url(url)` | 低 |
| `url.startswith('blob:')` | `is_blob_url(url)` | 低 |
| `url.startswith('http')` | `is_http_url(url)` | 低 |
| `'Base64' if x.startswith('data:') else ...` | `get_url_type(url)` | 低 |
| `url.split(',', 1)[1]` (提取 base64) | `extract_base64_from_data_url(url)` | 低 |
| `header.split(':',1)[1].split(';',1)[0]` (提取 mime) | `extract_mime_from_data_url(url)` | 低 |
| `re.match(r'^data:(.*?);base64,(.*)$', url)` | `parse_data_url(url)` | 中 |
| `f"data:{mime};base64,{b64}"` | `encode_to_data_url(bytes, mime)` | 低 |
| `url.startswith('data:image/')` | `is_base64_image_url(url)` | 低 |
| `mimetypes.guess_extension(mime)` | `get_extension_from_mime(mime)` | 低 |

### 4.5 不替换的场景

| 场景 | 原因 |
|------|------|
| `message_converter.py` 的 regex 解析 | 已封装良好，regex 一步完成 |
| `chat_handler.py` 的 regex 解析 | 同上 |
| Worker Pool 内部 base64 处理 | 内部实现，不暴露 |
| 业务逻辑中嵌入的 b64decode/encode | 上下文交织，机械替换风险高 |
| `workflows.py` 的动态 `f"data:{kind}/"` | 需要更通用的函数签名 |

### 4.6 modes.py 补充字段

`modes.py` 的 Attachment 模型缺少 `google_file_uri`，但 `ConversationalImageEditService` 已在使用：

```python
# modes.py Attachment 新增
google_file_uri: Optional[str] = None
```

### 4.7 清理 attachment_handler.py 死代码

| 内容 | 处理 |
|------|------|
| `Attachment` dataclass | 删除（与 Pydantic 模型冲突） |
| `AttachmentHandler` 类 | 删除（零使用，项目用 dict 传递附件） |
| `process_attachments()` | 删除（零使用） |
| `extract_base64_attachments()` | 删除（零使用） |
| `ProcessResult` dataclass | 删除（零使用） |
| 所有工具函数 | **保留并增强** |

---

## 五、实施计划（5 Phase）

### Phase 1: 增强 `attachment_handler.py`（低风险）

**文件**: `backend/app/utils/attachment_handler.py`

1. 新增 `extract_base64_from_data_url(data_url) → str`
2. 新增 `extract_mime_from_data_url(data_url) → str`
3. 新增 `is_base64_image_url(url) → bool`
4. 新增 `is_base64_audio_url(url) → bool`
5. 新增 `is_base64_video_url(url) → bool`
6. 删除 `Attachment` dataclass、`AttachmentHandler` 类、`ProcessResult`、批量处理函数
7. 更新 `__all__` 导出

**验证**: `from app.utils.attachment_handler import is_base64_url, parse_data_url, extract_base64_from_data_url; print('OK')`

### Phase 2: modes.py 补充字段（低风险）

**文件**: `backend/app/routers/core/modes.py`

在 Attachment 模型中添加 `google_file_uri: Optional[str] = None`

**验证**: `from app.routers.core.modes import Attachment; print(Attachment.model_fields.keys())`

### Phase 3: 替换核心服务层（中风险，逐文件验证）

| 顺序 | 文件 | 替换数 |
|:---:|------|:---:|
| 1 | `services/common/attachment_service.py` | ~12 |
| 2 | `routers/core/modes.py` | ~7 |
| 3 | `routers/core/attachments.py` | ~4 |
| 4 | `routers/user/sessions.py` | ~2 |
| 5 | `services/gemini/common/message_converter.py` | ~2 (仅 startswith) |
| 6 | `services/gemini/common/chat_handler.py` | ~2 (仅 startswith) |
| 7 | `services/common/video_mode_contract.py` | ~1 |

**验证（每文件）**: `from app.{module} import {main_export}; print('OK')`

### Phase 4: 替换工作流/Agent 层（低风险但量大）

| 顺序 | 文件 | 替换数 |
|:---:|------|:---:|
| 8 | `routers/ai/workflows.py` | ~18 |
| 9 | `routers/ai/multi_agent.py` | ~5 |
| 10 | `services/gemini/agent/workflow_template_sample_service.py` | ~4 |
| 11 | `services/gemini/vertexai/expand_service.py` | ~4 |
| 12 | 其他 VertexAI/GeminiAPI 服务 | ~8 |

### Phase 5: 全局验证

```bash
# 应用启动
cd backend && .venv/bin/python -c "from app.main import app; print('OK')"

# 单元测试
.venv/bin/python -m pytest tests/ -q
```

---

## 六、风险评估与回归测试

### 风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|:---:|---------|
| 替换后逻辑不一致 | 中 | 每文件独立替换+验证 |
| `startswith('data:image/')` 被错误替换为 `is_base64_url()` | 中 | 使用专用 `is_base64_image_url()` |
| `parse_data_url` 返回值与内联 split 不同 | 中 | 新增 `extract_base64_from_data_url` |
| 跨模式附件传递断裂 | 高 | 不改 Pydantic 模型、不改数据结构 |
| Worker Pool 上传中断 | 高 | 不动 Worker Pool 内部实现 |

### 回归测试清单

| 测试场景 | 覆盖入口 | 覆盖管道 |
|---------|---------|---------|
| Chat 模式发送带图片消息 | 入口 1 | 管道 A |
| Image-gen 模式图生图 | 入口 1 | 管道 B |
| 从 chat 结果点击"编辑"进入 image-chat-edit | 入口 3 | 跨模式 A→B |
| Image-mask-edit 原图+掩码 | 入口 1 | 管道 B (role) |
| Outpainting 扩图 | 入口 4 | 跨模式 |
| Video-gen 视频生成 | 入口 1 | 管道 B (8 role) |
| 上传状态轮询 pending→completed | 入口 1 | 状态机 |
| Session 保存/刷新后附件仍显示 | 入口 5 | DB 持久化 |
| AI 返回图片 → 临时代理 → 云 URL | 入口 5 | 服务层 |
| 画布延续（active_image_url） | 入口 6 | resolve_continuity |

---

*本文档整合自 4 份分析报告（~46KB），覆盖前端入口、后端路由、服务层、数据库模型、工具函数映射的完整附件链路。*
