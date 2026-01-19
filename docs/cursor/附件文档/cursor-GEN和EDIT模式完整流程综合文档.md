# GEN和EDIT模式完整流程综合文档（含附件处理）

> **文档版本**: v3.0 (综合版)  
> **创建日期**: 2026-01-18  
> **整合来源**:
> - `docs/GEN和EDIT模式完整流程分析文档.md` (v1.0, 95.7%准确率验证)
> - `docs/附件文档/cursor-完整附件处理流程分析文档.md` (v2.0)
> 
> **验证状态**: ✅ 整合两文档优势，保留所有细节  
> **文档类型**: 完整流程分析 + 附件处理完整生命周期

---

## 📋 目录

1. [概述](#概述)
2. [附件处理核心概念](#附件处理核心概念)
3. [EDIT模式完整流程](#edit模式完整流程)
4. [GEN模式完整流程](#gen模式完整流程)
5. [附件处理完整生命周期](#附件处理完整生命周期)
6. [提供商差异分析](#提供商差异分析)
7. [函数调用链路详解](#函数调用链路详解)
8. [关键数据结构](#关键数据结构)
9. [数据库加载流程（含附件）](#数据库加载流程含附件)
10. [验证发现与修正](#验证发现与修正)
11. [完整流程图](#完整流程图)
12. [附录](#附录)

---

## 概述

### 1.1 文档目标

本文档提供**GEN模式**和**EDIT模式**的端到端完整流程分析，整合了两份文档的所有优势，覆盖：

- ✅ 用户从开始工作到完整显示的全流程
- ✅ 不同提供商 (Google Gemini vs Tongyi 通义) 的差异
- ✅ 页面重载加载历史的完整流程
- ✅ 函数调用链路的层级关系 (A→B→C→D)
- ✅ 数据格式在各阶段的转换
- ✅ **附件处理完整生命周期**（从上传到数据库持久化）
- ✅ **CONTINUITY LOGIC** 详细流程（跨模式传递）
- ✅ **异步上传机制**（Worker Pool + Redis 队列）

### 1.2 核心架构差异

| 特性 | EDIT模式 | GEN模式 |
|------|---------|---------|
| **CONTINUITY LOGIC** | ✅ 存在 (自动复用画布图片) | ❌ 不存在 |
| **主要用途** | 编辑现有图片 | 生成新图片 |
| **附件处理** | 支持用户上传 + 画布复用 | 仅支持用户上传 |
| **多轮对话** | 支持 (ConversationalEdit) | 不支持 |
| **批量生成** | 单张 | 支持多张 (1-4张) |
| **历史加载** | 加载所有编辑历史 | 加载所有生成结果 |
| **参数支持** | editMode, maskData | numberOfImages, aspectRatio, negativePrompt |

### 1.3 文档整合说明

本综合文档整合了以下内容：

**来自现有文档 (v1.0) 的优势**：
- ✅ 详细的代码位置标注（含行号）
- ✅ 4个EDIT场景的详细分析
- ✅ 提供商差异的深入分析（含代码、性能对比、优化建议）
- ✅ 完整的验证发现与修正
- ✅ 25层完整端到端调用链

**来自新文档 (v2.0) 的优势**：
- ✅ 附件处理核心概念的系统化说明
- ✅ 附件处理完整生命周期独立章节
- ✅ 数据库加载流程独立章节
- ✅ Mermaid 流程图（可视化）
- ✅ 按流程阶段组织的清晰结构

---

## 附件处理核心概念

### 2.1 URL 类型

| URL 类型 | 格式 | 生命周期 | 用途 | 保存到数据库 |
|---------|------|---------|------|------------|
| **Blob URL** | `blob:http://localhost:3000/xxx` | 页面关闭后失效 | 用户上传文件的临时预览 | ❌ 否（需清理） |
| **Base64 Data URL** | `data:image/png;base64,iVBORw0KGgo...` | 永久有效（内存中） | AI 生成图片（Google）、跨模式传递 | ❌ 否（太大） |
| **HTTP 临时 URL** | `https://dashscope.oss-cn-beijing.aliyuncs.com/...?Expires=xxx` | 会过期（通常24小时） | AI 生成图片（Tongyi） | ⚠️ 临时保存 |
| **HTTP 云存储 URL** | `https://storage.example.com/path/image.png` | 永久有效 | 上传到云存储后的永久 URL | ✅ 是（主要） |

**URL类型判断函数**：

**代码位置**: `frontend/hooks/handlers/attachmentUtils.ts`

```typescript
export const isBlobUrl = (url: string): boolean => {
  return url.startsWith('blob:');
};

export const isBase64Url = (url: string): boolean => {
  return url.startsWith('data:image/') || url.startsWith('data:application/');
};

export const isHttpUrl = (url: string): boolean => {
  return url.startsWith('http://') || url.startsWith('https://');
};
```

### 2.2 附件状态（uploadStatus）

| 状态 | 说明 | url 字段内容 | 触发时机 |
|------|------|------------|---------|
| `pending` | 待上传 | Base64/Blob URL 或空 | 附件创建时、上传任务提交前 |
| `uploading` | 上传中 | 临时 URL 或空 | Worker 开始处理任务时 |
| `completed` | 已上传 | 云存储 HTTP URL | 上传成功、Worker 更新数据库时 |
| `failed` | 上传失败 | 临时 URL 或空 | 上传失败、达到重试上限时 |

**状态流转图**：

```
pending (创建附件)
    ↓
pending (提交上传任务)
    ↓
uploading (Worker 开始处理)
    ↓
completed (上传成功)
    或
failed (上传失败)
    ↓
pending (重试，retry_count++)
```

### 2.3 附件字段说明

**Attachment 接口定义**：

**代码位置**: `frontend/types/types.ts`

```typescript
interface Attachment {
  // ========== 核心标识 ==========
  id: string;                          // 唯一标识 (UUID)

  // ========== 显示相关 ==========
  url?: string;                        // 权威 URL
                                       // 优先级: HTTP Cloud URL > Base64 > Blob URL

  tempUrl?: string;                    // 临时 URL (跨模式查找关键)
                                       // 保存原始URL (Blob/HTTP临时URL)

  // ========== 上传相关 ==========
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'failed';
  uploadTaskId?: string;               // 异步上传任务 ID

  // ========== 文件相关 ==========
  file?: File;                         // 原始 File 对象 (仅前端)
  mimeType: string;                    // MIME类型 (image/png, image/jpeg, ...)
  name: string;                        // 文件名

  // ========== 云存储 API 相关 ==========
  fileUri?: string;                    // 云存储 File URI (通用)
  googleFileUri?: string;              // Google Files API URI (48小时缓存)
  googleFileExpiry?: number;           // Google File URI 过期时间戳

  // ========== 数据清理字段 (不保存到数据库) ==========
  base64Data?: string;                 // Base64 数据 (临时, 过大不存储)
}
```

**字段用途说明**：

| 字段 | 用途 | 生命周期 | 是否保存到DB | 备注 |
|------|------|---------|------------|------|
| `id` | 唯一标识 | 永久 | ✅ 是 | UUID |
| `url` | 权威URL (优先HTTP Cloud URL) | 永久 | ✅ 是 | 主要显示字段 |
| `tempUrl` | 原始URL (Blob/临时HTTP) | 永久 | ✅ 是 | 跨模式查找关键 |
| `uploadStatus` | 上传状态 | 永久 | ✅ 是 | 4种状态 |
| `uploadTaskId` | 上传任务ID | 任务期间 | ❌ 否 | 临时字段 |
| `file` | 原始File对象 | 前端会话 | ❌ 否 | 不可序列化 |
| `base64Data` | Base64数据 | 前端会话 | ❌ 否 | 太大不存储 |
| `googleFileUri` | Google File URI | 48小时 | ✅ 是 | Google Files API |

---

## EDIT模式完整流程

EDIT模式支持4个核心场景，本部分详细分析每个场景的完整流程，包含代码位置标注。

### 3.1 场景1: 用户上传新附件并编辑

#### 3.1.1 完整流程图（含代码位置）

```
用户选择文件
    ↓
InputArea.handleFileSelect()  [InputArea.tsx:95]
    ├─ 创建 Blob URL: URL.createObjectURL(file)  [Line 108]
    ├─ 创建 Attachment { url: blobUrl, file: File, uploadStatus: 'pending' }
    └─ updateAttachments([...attachments, newAttachment])
    ↓
显示在输入区预览
    ↓
用户点击发送
    ↓
InputArea.handleSend()
    ├─ Blob URL → Base64 (fileToBase64)
    └─ onSend(text, options, processedAttachments, mode)
    ↓
ImageEditView.handleSend()  [ImageEditView.tsx:425]
    ↓
processUserAttachments(attachments, activeImageUrl, messages, sessionId)  [attachmentUtils.ts:786]
    ├─ 步骤1: 检查附件数量 (finalAttachments.length > 0)
    ├─ 步骤2: Blob URL → Base64 URL (urlToBase64)  [Line 835-848]
    ├─ 步骤3: Base64 URL → File 对象 (base64ToFile)  [Line 852-863]
    └─ 返回: Promise<Attachment[]>
    ↓
useChat.sendMessage(text, options, attachments, mode, currentModel, protocol)  [useChat.ts:43]
    ├─ 创建 ExecutionContext
    ├─ preprocessorRegistry.process(context)  [Line 110]
    │   └─ GoogleFileUploadPreprocessor (如果是Google + Chat模式)
    │       └─ llmService.uploadFile(file) → fileUri
    │
    ├─ 创建 userMessage (包含处理后的附件)  [Line 137-154]
    ├─ strategyRegistry.getHandler(mode)  [Line 161]
    │   └─ ImageEditHandler
    └─ handler.execute(context)  [Line 166]
    ↓
ImageEditHandler.doExecute()  [ImageEditHandlerClass.ts:10]
    ├─ 转换 attachments → referenceImages { raw: attachment }  [Line 14-41]
    ├─ 如果有 File 但无 HTTP URL → fileToBase64()  [Line 29-35]
    └─ llmService.editImage(text, referenceImages, mode, editOptions)  [Line 45]
    ↓
UnifiedProviderClient.editImage()  [llmService.ts:524]
    ├─ 构建请求体
    │   ├─ modelId
    │   ├─ prompt
    │   ├─ attachments[] (Attachment 对象数组)
    │   └─ options (frontend_session_id, ...)
    │
    └─ POST /api/modes/{provider}/{mode}  [Line 545]
    ↓
后端 modes.py: handle_mode()  [modes.py:151]
    ├─ 验证 ModeRequest
    ├─ convert_attachments_to_reference_images()  [Line 102]
    │   └─ attachments[] → reference_images { 'raw': {...}, 'mask': {...} }
    │
    └─ provider.edit_image(prompt, model, reference_images, mode, **options)  [Line 253]
    ↓
GoogleService.edit_image()  [google_service.py:407]
    └─ ImageEditCoordinator.edit_image(mode, ...)
        ├─ mode === 'image-chat-edit' → ConversationalImageEditService
        └─ 其他 → SimpleImageEditService
    ↓
ConversationalImageEditService.send_edit_message()  [conversational_image_edit_service.py:183]
    ├─ 处理参考图片  [Line 341-424]
    │   ├─ googleFileUri → genai_types.Part(file_data=FileData(...))
    │   ├─ Base64 URL → Part.from_bytes(image_bytes, mime_type)
    │   └─ HTTP URL → aiohttp 下载 → Part.from_bytes(...)
    │
    ├─ message_parts = [image_parts..., text_part]
    └─ chat.send_message(message_parts, config)  [Line 479]
    ↓
Google Gemini API
    ↓
返回编辑后的图片
    ├─ response.candidates[0].content.parts
    ├─ 提取 thoughts (从 response.parts)  [Line 502-604]
    └─ 提取最终图片 (part.inline_data)  [Line 615-642]
        └─ Base64 Data URL: data:image/png;base64,...
    ↓
前端接收响应
    ↓
processMediaResult(res, context, 'edited')  [attachmentUtils.ts:960]
    ├─ displayAttachment:  [Line 975-993]
    │   ├─ Google: displayUrl = res.url (Base64)
    │   └─ Tongyi: fetch(res.url) → Blob URL
    │
    └─ dbAttachmentPromise:  [Line 995-1013]
        ├─ sourceToFile(res.url) → File
        ├─ storageUpload.uploadFileAsync(file, ...)
        └─ 返回 { url: HTTP, uploadTaskId: 'task-123' }
    ↓
setMessages(updatedMessages)
    ├─ 更新 UI (显示 Blob URL 或 Base64)
    └─ uploadTask 完成后 → updateSessionMessages() → 保存到数据库
    ↓
[后台异步] Worker Pool 处理上传
    ├─ Redis BRPOP 获取任务  [upload_worker_pool.py:316]
    ├─ 状态: pending → uploading  [Line 407]
    ├─ 上传到云存储  [Line 444]
    ├─ 状态: uploading → completed  [Line 564]
    └─ 更新 UploadTask.target_url  [Line 565]
    ↓
[前端轮询] 查询上传状态
    └─ GET /api/sessions/{sessionId}/attachments/{attachmentId}
    ↓
获取到云URL后更新消息
    └─ updateSessionMessages() → 数据库保存云URL
```

#### 3.1.2 关键代码位置

| 步骤 | 文件 | 行号 | 函数 |
|-----|------|------|------|
| 用户上传 | `InputArea.tsx` | 95-115 | `handleFileSelect` |
| 附件处理 | `attachmentUtils.ts` | 786-942 | `processUserAttachments` |
| 消息发送 | `useChat.ts` | 43-231 | `sendMessage` |
| Edit Handler | `ImageEditHandlerClass.ts` | 10-147 | `doExecute` |
| API 调用 | `llmService.ts` | 524-556 | `editImage` |
| 后端路由 | `modes.py` | 151-315 | `handle_mode` |
| 附件转换 | `modes.py` | 102-145 | `convert_attachments_to_reference_images` |
| Google 服务 | `conversational_image_edit_service.py` | 183-673 | `send_edit_message` |
| 结果处理 | `attachmentUtils.ts` | 960-1016 | `processMediaResult` |
| 异步上传 | `upload_worker_pool.py` | 381-491 | `_process_task` |

### 3.2 场景2: 无新上传时使用画布图片 (CONTINUITY LOGIC)

#### 3.2.1 完整流程图（含代码位置）

```
用户在画布上看到图片
    ├─ 来源1: 上一轮AI生成的图片
    ├─ 来源2: 历史消息中的图片
    └─ 来源3: 跨模式传递的图片
    ↓
ImageEditView 维护 activeImageUrl 状态  [ImageEditView.tsx:252]
    ├─ 来自 activeAttachments[0]
    ├─ 来自 initialAttachments (跨模式)
    └─ 来自 messages 最新结果
    ↓
用户输入编辑提示词 (不上传新附件)
    ↓
用户点击发送
    ↓
ImageEditView.handleSend()  [Line 425]
    └─ onSend(text, options, [], mode)  // attachments = []
    ↓
processUserAttachments([], activeImageUrl, messages, sessionId)  [attachmentUtils.ts:786]
    ↓
触发 CONTINUITY LOGIC  [Line 798-814]
    ├─ 条件: finalAttachments.length === 0 && activeImageUrl
    ├─ console.log: "✅ 触发 CONTINUITY LOGIC（无新上传）"
    │
    └─ prepareAttachmentForApi(activeImageUrl, messages, sessionId, 'canvas', true)
        ↓
prepareAttachmentForApi()  [Line 653-758]
    ├─ 步骤1: 从历史消息查找附件
    │   └─ findAttachmentByUrl(imageUrl, messages)  [Line 664]
    │       ├─ 匹配 url 字段
    │       ├─ 匹配 tempUrl 字段
    │       └─ 模糊匹配 (去除查询参数)
    │
    ├─ 步骤2: 如果找到，查询云URL
    │   └─ tryFetchCloudUrl(sessionId, attachmentId, url, uploadStatus)  [Line 671]
    │       └─ GET /api/sessions/{sessionId}/attachments/{attachmentId}
    │           ↓
    │           后端查询：  [sessions.py:645-705]
    │           ├─ 查询 UploadTask（如果 upload_task_id 存在）
    │           ├─ 查询 MessageAttachment
    │           └─ 返回 { url, uploadStatus, taskId, taskStatus }
    │
    ├─ 步骤3: 返回复用的附件
    │   └─ { id: uuidv4(), url: cloudUrl, uploadStatus: 'completed' }
    │
    └─ 步骤4: 未找到历史附件时
        ├─ Base64 URL → 直接返回
        └─ HTTP URL → 直接返回 (skipBase64=true)
    ↓
继续常规流程
    └─ useChat.sendMessage → ImageEditHandler → API → Google → processMediaResult
```

#### 3.2.2 CONTINUITY LOGIC 关键代码

**位置**: `attachmentUtils.ts:798-814`

```typescript
// CONTINUITY LOGIC - 无新上传时复用画布图片
if (finalAttachments.length === 0 && activeImageUrl) {
  console.log(`[processUserAttachments] ✅ 触发 CONTINUITY LOGIC（无新上传）`);
  console.log(`[processUserAttachments] activeImageUrl=${activeImageUrl.slice(0, 60)}...`);

  // HTTP URL 跳过 Base64 转换，让后端自己下载
  const skipBase64ForHttp = isHttpUrl(activeImageUrl);

  const prepared = await prepareAttachmentForApi(
    activeImageUrl,
    messages,
    sessionId,
    filePrefix,
    skipBase64ForHttp
  );

  if (prepared) {
    finalAttachments = [prepared];
  }
  return finalAttachments;
}
```

**关键优化**: `skipBase64ForHttp = true`
- 避免前端重复下载HTTP URL
- 后端直接使用HTTP URL下载图片
- 减少前端网络开销

#### 3.2.3 历史附件查找机制

**位置**: `attachmentUtils.ts:524-584`

```typescript
export const findAttachmentByUrl = (
  targetUrl: string,
  messages: Message[]
): { attachment: Attachment; messageId: string } | null => {
  // 按时间倒序遍历 (优先查找最新)
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (!msg.attachments?.length) continue;

    for (const att of msg.attachments) {
      // 策略1: 精确匹配 url 字段
      if (att.url === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }

      // 策略2: 精确匹配 tempUrl 字段 (跨模式关键)
      if (att.tempUrl === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }

      // 策略3: 模糊匹配 (去除查询参数)
      const attUrlBase = att.url?.split('?')[0];
      const targetUrlBase = targetUrl.split('?')[0];
      if (attUrlBase && targetUrlBase && attUrlBase === targetUrlBase) {
        return { attachment: att, messageId: msg.id };
      }
    }
  }

  return null;
};
```

**匹配优先级**:
1. 精确匹配 `url` (权威URL)
2. 精确匹配 `tempUrl` (原始URL, 跨模式查找关键)
3. 模糊匹配 (路径相同, 参数不同)

#### 3.2.4 云URL查询

**位置**: `attachmentUtils.ts:378-411`

```typescript
export const tryFetchCloudUrl = async (
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string,
  currentStatus: string
): Promise<{ url: string; uploadStatus: string } | null> => {
  // 已完成上传且是HTTP URL → 直接使用
  if (currentStatus === 'completed' && isHttpUrl(currentUrl)) {
    return { url: currentUrl, uploadStatus: 'completed' };
  }

  // 查询后端获取最新状态
  if (sessionId && attachmentId) {
    const response = await fetch(
      `/api/sessions/${sessionId}/attachments/${attachmentId}`,
      { credentials: 'include' }
    );
    const result = await response.json();

    if (result && result.uploadStatus === 'completed' && isHttpUrl(result.url)) {
      return { url: result.url, uploadStatus: 'completed' };
    }
  }

  return null;
};
```

**后端查询API**:

**代码位置**: `backend/app/routers/user/sessions.py:645-705`

```python
@router.get("/sessions/{session_id}/attachments/{attachment_id}")
async def get_attachment(
    session_id: str,
    attachment_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    查询附件的最新信息 (v3 架构)
    
    从 message_attachments 表直接查询，联查 UploadTask 获取最新云 URL
    """
    # 1. 验证会话存在
    session = user_query.get(DBChatSession, session_id)
    
    # 2. 从 message_attachments 表查询附件
    attachment = db.query(MessageAttachment).filter(
        MessageAttachment.session_id == session_id,
        MessageAttachment.id == attachment_id,
        MessageAttachment.user_id == user_id
    ).first()
    
    # 3. 查询关联的上传任务
    task = db.query(UploadTask).filter(
        UploadTask.attachment_id == attachment_id
    ).first()
    
    # 4. 构建返回结果
    result = attachment.to_dict()
    
    # 如果任务已完成且有目标 URL，优先使用任务的 URL
    if task and task.status == 'completed' and task.target_url:
        result["url"] = task.target_url
        result["uploadStatus"] = 'completed'
    
    return result
```

**前端查询函数**:

**代码位置**: `attachmentUtils.ts:590-630`

```typescript
export const fetchAttachmentStatus = async (
  sessionId: string, 
  attachmentId: string
): Promise<{ url: string; uploadStatus: string; taskId?: string; taskStatus?: string } | null> => {
  try {
    const response = await fetch(`/api/sessions/${sessionId}/attachments/${attachmentId}`, {
      credentials: 'include'
    });
    
    if (!response.ok) {
      return null;
    }
    
    const data = await response.json();
    return data;
  } catch (e) {
    console.error('[fetchAttachmentStatus] 查询异常:', e);
    return null;
  }
};
```

---

### 3.3 场景3: AI返回编辑后的图片

#### 3.3.1 完整流程图（含代码位置）

```
Google Gemini API 返回响应
    └─ response.candidates[0].content.parts[]
    ↓
ConversationalImageEditService 提取图片  [conversational_image_edit_service.py:615-642]
    ├─ 提取 thoughts (文本部分)  [Line 502-604]
    │   └─ parts[*].text → thoughts
    │
    └─ 提取图片 (inline_data部分)  [Line 615-642]
        ├─ image_bytes = part.inline_data.data
        ├─ mime_type = part.inline_data.mime_type || 'image/png'
        ├─ base64_str = base64.b64encode(image_bytes).decode('utf-8')
        └─ url = f"data:{mime_type};base64,{base64_str}"
    ↓
返回 ImageEditResult
    └─ { success: True, url: "data:image/png;base64,...", thoughts: "..." }
    ↓
前端接收响应  [useChat.ts:166-190]
    ├─ HandlerResult { content, attachments, uploadTasks }
    └─ 调用 processMediaResult 处理每个附件
    ↓
processMediaResult(res, context, 'edited')  [attachmentUtils.ts:960]
    ├─ 创建 displayAttachment (立即显示)  [Line 975-993]
    │   ├─ Google: res.url 是 Base64
    │   │   └─ displayUrl = res.url (直接使用)
    │   │
    │   └─ Tongyi: res.url 是 HTTP 临时URL
    │       ├─ fetch(res.url) → blob
    │       └─ displayUrl = URL.createObjectURL(blob)
    │
    └─ 创建 dbAttachmentPromise (后台上传)  [Line 995-1013]
        ├─ sourceToFile(res.url, filename, mimeType) → File
        │   ├─ Google: Base64 → Blob → File
        │   └─ Tongyi: HTTP URL → 下载 → File
        │
        └─ storageUpload.uploadFileAsync(file, {
            sessionId, messageId, attachmentId
        })
            └─ POST /api/storage/upload-async
    ↓
返回双重URL结构
    ├─ displayAttachment: { url: displayUrl, uploadStatus: 'pending' }
    │   └─ 用于立即显示
    │
    └─ dbAttachmentPromise: Promise<{ url, uploadTaskId }>
        └─ 用于数据库保存
    ↓
useChat.sendMessage 继续处理  [Line 175-190]
    ├─ displayAttachments → 立即更新UI
    │   └─ setMessages([...messages, modelMessage])
    │
    └─ uploadTasks → 后台等待上传完成
        └─ await Promise.all(uploadTasks)
        └─ updateSessionMessages(sessionId, messages)
    ↓
Worker Pool 异步上传  [upload_worker_pool.py:381-491]
    ├─ Redis BRPOP 获取任务  [Line 349]
    ├─ 更新状态: pending → uploading  [Line 407]
    ├─ 读取文件内容  [Line 501-533]
    │   ├─ source_file_path → 读取本地文件
    │   └─ source_url → HTTP下载
    │
    ├─ 上传到云存储  [Line 444]
    │   └─ StorageService.upload_file(...)
    │
    └─ 处理成功  [Line 558-608]
        ├─ 更新状态: uploading → completed
        ├─ 设置 target_url (云存储URL)
        └─ 更新 Attachment.url
    ↓
前端轮询查询上传状态
    └─ 获取到云URL后更新消息
```

#### 3.3.2 双重URL机制

| URL类型 | 用途 | 来源 | 生命周期 |
|---------|------|------|---------|
| **displayUrl** | 立即显示 | Blob URL 或 Base64 | 页面会话期间 |
| **dbUrl** | 永久存储 | 云存储 HTTP URL | 永久有效 |

**代码位置**: `attachmentUtils.ts:975-1013`

```typescript
// 1. 创建 displayAttachment (立即显示)
let displayUrl: string;
if (isHttpUrl(res.url)) {
  // Tongyi: HTTP临时URL → 下载为Blob
  const response = await fetch(res.url);
  const blob = await response.blob();
  displayUrl = URL.createObjectURL(blob);
} else {
  // Google: Base64 → 直接使用
  displayUrl = res.url;
}

const displayAttachment: Attachment = {
  id: attachmentId,
  url: displayUrl,
  tempUrl: res.url,  // 保存原始URL
  uploadStatus: 'pending'
};

// 2. 创建 dbAttachmentPromise (后台上传)
const dbAttachmentPromise = (async () => {
  const file = await sourceToFile(res.url, filename, mimeType);
  const uploadResult = await storageUpload.uploadFileAsync(file, {
    sessionId: context.sessionId,
    messageId: context.messageId,
    attachmentId
  });
  return {
    url: uploadResult.url,  // 云存储URL (后端返回)
    uploadTaskId: uploadResult.taskId
  };
})();

return { displayAttachment, dbAttachmentPromise };
```

---

### 3.4 场景4: 页面刷新加载历史

#### 3.4.1 完整流程图（含代码位置）

```
用户刷新页面
    ↓
App.tsx 加载  [App.tsx:178]
    └─ useEffect(() => { loadSession() }, [])
    ↓
loadSession()
    ├─ GET /api/sessions/{sessionId}
    └─ 返回: { id, messages: [...] }
    ↓
setMessages(session.messages)
    ↓
ImageEditView 接收 messages  [ImageEditView.tsx:252-332]
    ├─ 过滤当前模式的消息
    │   └─ useViewMessages(messages, appMode)
    │
    └─ 提取最新结果作为 activeImageUrl
        └─ useEffect(() => {
            if (messages.length > 0) {
              const lastMsg = messages[messages.length - 1];
              if (lastMsg.role === MODEL && lastMsg.attachments?.[0]) {
                setActiveImageUrl(lastMsg.attachments[0].url);
              }
            }
        }, [messages])
    ↓
Canvas 显示图片
    └─ <Canvas imageUrl={activeImageUrl} />
    ↓
历史消息显示
    └─ messages.map(msg => <MessageItem message={msg} />)
        └─ 显示附件: msg.attachments.map(att => <img src={att.url} />)
```

#### 3.4.2 消息过滤机制

**位置**: `useViewMessages.ts:15-35`

```typescript
export const useViewMessages = (
  messages: Message[],
  appMode: AppMode
): Message[] => {
  return useMemo(() => {
    return messages.filter(msg => {
      // 保留当前模式的消息
      if (msg.mode === appMode) return true;

      // 保留通用消息 (无mode字段且当前是chat模式)
      if (!msg.mode && appMode === 'chat') return true;

      return false;
    });
  }, [messages, appMode]);
};
```

#### 3.4.3 附件URL优先级

**从数据库加载的附件URL优先级**:

1. **云存储URL** (uploadStatus === 'completed' && isHttpUrl(url))
   - 永久有效
   - 直接显示

2. **Base64 URL** (uploadStatus === 'pending' && isBase64Url(url))
   - 已清理 (数据库不存储Base64)
   - 需要重新查询或重新生成

3. **Blob URL** (已失效)
   - 页面刷新后 Blob URL 无效
   - 需要重新查询云URL

**代码位置**: `sessions.py:408-430` (云URL保护逻辑)

```python
# 优先级1: UploadTask.target_url (最权威)
task = completed_tasks.get(att_id)
if task and task.target_url:
    authoritative_url = task.target_url

# 优先级2: Database existing URL
if not authoritative_url:
    existing_att = existing_attachments.get(att_id)
    if existing_att and existing_att.url and existing_att.url.startswith('http'):
        authoritative_url = existing_att.url

# 优先级3: Frontend URL
frontend_url = att.get("url", "")
if not frontend_url or frontend_url.startswith("blob:") or frontend_url.startswith("data:"):
    final_url = authoritative_url or frontend_url
else:
    final_url = frontend_url
```

**保护效果**:

| 前端URL | 数据库URL | UploadTask URL | 最终URL | 说明 |
|---------|----------|---------------|---------|------|
| `blob:xxx` | `http://cloud/1.png` | - | `http://cloud/1.png` | ✅ 保护数据库URL |
| `data:xxx` | - | `http://cloud/2.png` | `http://cloud/2.png` | ✅ 使用最新上传URL |
| `http://new.png` | `http://old.png` | - | `http://new.png` | ✅ 前端HTTP URL优先 |
| `blob:xxx` | - | - | `blob:xxx` | ⚠️ 无云URL, 保留Blob (临时) |

## GEN模式完整流程

GEN模式（图片生成）的完整流程分析，包含用户操作、Handler处理、API请求、后端处理、附件处理、UI显示和异步上传等完整阶段。

### 4.1 场景: 用户输入提示词生成图片

#### 4.1.1 完整流程图（含代码位置）

```
用户输入生成提示词
    ↓
ImageGenView.tsx  [ImageGenView.tsx:52-68]
    ├─ 输入框: <InputArea onSend={handleSend} />
    └─ 配置参数:
        ├─ numberOfImages (生成数量: 1-4张)
        ├─ aspectRatio (宽高比: 1:1, 16:9, 9:16, 4:3, 3:4)
        └─ negativePrompt (负面提示词, 可选)
    ↓
用户点击发送
    ↓
ImageGenView.handleSend()  [Line 81-97]
    └─ onSend(text, {
        numberOfImages,
        aspectRatio,
        negativePrompt
    }, attachments, mode)
    ↓
useChat.sendMessage(text, options, attachments, mode)  [useChat.ts:43]
    ├─ 创建 ExecutionContext
    │   ├─ text: 用户提示词
    │   ├─ options: { numberOfImages, aspectRatio, negativePrompt }
    │   ├─ attachments: [] (Gen模式通常无附件)
    │   └─ mode: 'image-gen'
    │
    ├─ preprocessorRegistry.process(context)  [Line 110]
    │   └─ 无特殊预处理 (Gen模式不需要文件上传)
    │
    ├─ 创建 userMessage  [Line 137-154]
    ├─ strategyRegistry.getHandler('image-gen')  [Line 161]
    │   └─ ImageGenHandler
    └─ handler.execute(context)  [Line 166]
    ↓
ImageGenHandler.doExecute()  [ImageGenHandlerClass.ts:10]
    ├─ 提取参数
    │   ├─ numberOfImages = options.numberOfImages || 1
    │   ├─ aspectRatio = options.aspectRatio || '1:1'
    │   └─ negativePrompt = options.negativePrompt
    │
    └─ llmService.generateImage(
        text,
        attachments,
        numberOfImages,
        aspectRatio,
        negativePrompt
    )  [Line 25]
    ↓
UnifiedProviderClient.generateImage()  [llmService.ts:431]
    ├─ 构建请求体
    │   ├─ modelId
    │   ├─ prompt
    │   ├─ numberOfImages
    │   ├─ aspectRatio
    │   ├─ negativePrompt
    │   └─ options (frontend_session_id, ...)
    │
    └─ POST /api/modes/{provider}/image-gen  [Line 454]
    ↓
后端 modes.py: handle_mode()  [modes.py:151]
    ├─ provider = request.provider (google/tongyi)
    ├─ mode = 'image-gen'
    ├─ method_name = 'generate_image'  [Line 226]
    │
    ├─ 提取参数
    │   ├─ prompt = request_body.prompt
    │   ├─ numberOfImages = request_body.numberOfImages
    │   ├─ aspectRatio = request_body.aspectRatio
    │   └─ negativePrompt = request_body.negativePrompt
    │
    └─ provider.generate_image(
        prompt,
        model,
        numberOfImages,
        aspectRatio,
        negativePrompt,
        **options
    )  [Line 253]
    ↓
GoogleService.generate_image()  [google_service.py:542]
    └─ ImageGenerator.generate_image(...)
        ↓
ImageGenerator._generate_image_internal()  [image_generator.py:89]
    ├─ 构建 generation_config
    │   ├─ number_of_images = numberOfImages
    │   └─ aspect_ratio = aspectRatio
    │
    ├─ 构建提示词
    │   ├─ parts = [prompt]
    │   └─ 如果有 negativePrompt → parts.append(negative_prompt_part)
    │
    └─ model.generate_content(
        parts,
        generation_config=generation_config
    )  [Line 145]
    ↓
Google Imagen API
    └─ 返回 1-4 张生成的图片
    ↓
ImageGenerator 提取结果  [Line 154-188]
    ├─ 遍历 response.candidates
    │   └─ 每个 candidate.content.parts
    │       └─ part.inline_data
    │           ├─ image_bytes = part.inline_data.data
    │           ├─ mime_type = part.inline_data.mime_type || 'image/png'
    │           ├─ base64_str = base64.b64encode(image_bytes)
    │           └─ url = f"data:{mime_type};base64,{base64_str}"
    │
    └─ 返回: List[ImageGenerationResult]
        └─ [{ url: "data:image/png;base64,...", mimeType: "image/png" }, ...]
    ↓
前端接收响应  [useChat.ts:166-190]
    ├─ HandlerResult { content, attachments: [res1, res2, ...] }
    └─ 对每个附件调用 processMediaResult
    ↓
processMediaResult(res, context, 'generated')  [attachmentUtils.ts:960]
    ├─ 创建 displayAttachment
    │   └─ displayUrl = res.url (Base64)  [Google]
    │   或
    │   └─ fetch(res.url) → Blob URL  [Tongyi]
    │
    └─ 创建 dbAttachmentPromise
        ├─ sourceToFile(res.url) → File
        └─ storageUpload.uploadFileAsync(file, ...)
    ↓
批量显示生成结果
    └─ setMessages([...messages, modelMessage])
        └─ modelMessage.attachments = [
            { url: blobUrl1, uploadStatus: 'pending' },
            { url: blobUrl2, uploadStatus: 'pending' },
            ...
        ]
    ↓
[后台] Worker Pool 批量上传
    └─ 每张图片独立上传到云存储
    ↓
完成后更新消息
    └─ 所有附件的 url 更新为云存储URL
```

#### 4.1.2 关键代码位置

| 步骤 | 文件 | 行号 | 函数 |
|-----|------|------|------|
| 用户界面 | `ImageGenView.tsx` | 52-97 | `handleSend` |
| Handler处理 | `ImageGenHandlerClass.ts` | 8-48 | `doExecute` |
| API调用 | `llmService.ts` | 431-456 | `generateImage` |
| 后端路由 | `modes.py` | 151-315 | `handle_mode` |
| Google服务 | `image_generator.py` | 89-188 | `_generate_image_internal` |
| 结果处理 | `attachmentUtils.ts` | 960-1016 | `processMediaResult` |
| 异步上传 | `upload_worker_pool.py` | 381-491 | `_process_task` |

#### 4.1.3 关键差异点

**1. 无 CONTINUITY LOGIC**

Gen模式 **不支持** 自动复用画布图片:

**代码位置**: `ImageGenHandlerClass.ts:8-48`

```typescript
// ImageGenHandler.ts - 无 CONTINUITY LOGIC
protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
  // ❌ 不处理 activeImageUrl
  // ❌ 不调用 prepareAttachmentForApi
  // ❌ 每次生成都是独立的

  const results = await llmService.generateImage(
    context.text,
    context.attachments,  // 通常为空
    numberOfImages,
    aspectRatio,
    negativePrompt
  );
}
```

**2. 批量生成支持**

Gen模式支持一次生成多张图片:

**代码位置**: `ImageGenView.tsx:52-68`

```typescript
// 用户选择生成数量
const [numberOfImages, setNumberOfImages] = useState(1);  // 1-4

const handleSend = (text, options, attachments) => {
  onSend(text, {
    numberOfImages,  // 传递数量参数
    aspectRatio,
    negativePrompt
  }, attachments, mode);
};
```

**3. 宽高比参数**

Gen模式支持多种宽高比:

| 宽高比 | 用途 | 尺寸示例 |
|-------|------|---------|
| 1:1 | 正方形 | 1024x1024 |
| 16:9 | 宽屏横向 | 1920x1080 |
| 9:16 | 竖屏 | 1080x1920 |
| 4:3 | 传统横向 | 1024x768 |
| 3:4 | 传统竖向 | 768x1024 |

**4. 负面提示词**

Gen模式支持负面提示词 (避免生成特定内容):

**代码位置**: `image_generator.py:89-145`

```python
# 后端构建
if (negativePrompt) {
  parts.append({
    'text': f"Negative prompt: {negativePrompt}"
  });
}
```

#### 4.1.4 页面刷新加载历史

Gen模式加载历史的流程与Edit模式基本相同:

```
用户刷新页面
    ↓
loadSession()
    └─ GET /api/sessions/{sessionId}
    ↓
setMessages(session.messages)
    ↓
ImageGenView 过滤消息
    └─ useViewMessages(messages, 'image-gen')
        └─ 仅显示 mode === 'image-gen' 的消息
    ↓
显示生成的图片批次
    └─ messages.map(msg => {
        if (msg.attachments?.length > 1) {
          return <ImageBatch images={msg.attachments} />
        }
    })
```

**关键差异**: Gen模式可能有多张图片的批次:

**代码位置**: `ImageGenView.tsx:66-136`

```typescript
const filteredMessages = useViewMessages(messages, 'image-gen');

// 按批次分组显示
const imageBatches = filteredMessages
  .filter(msg => msg.role === Role.MODEL && msg.attachments?.length > 0)
  .map(msg => ({
    messageId: msg.id,
    images: msg.attachments  // 可能是1-4张图片
  }));
```

## 附件处理完整生命周期

附件从用户上传到数据库持久化的完整生命周期，包括URL转换链、Continuity Logic详细流程、异步上传机制等。

### 5.1 附件 URL 转换链

附件在不同阶段的URL类型转换完整链路：

```
[用户上传]
File 对象
    ↓
URL.createObjectURL(file) → Blob URL  [InputArea.tsx:108]
    ↓
[跨模式传递]
findAttachmentByUrl(blobUrl, messages)  [attachmentUtils.ts:524]
    ↓
找到历史附件 → 获取云存储 URL（如果已上传）
    ↓
[发送到后端]
prepareAttachmentForApi()  [attachmentUtils.ts:653]
    ├─ 如果是 HTTP URL → 直接传递（后端下载）
    ├─ 如果是 Blob URL → urlToBase64() → Base64 URL
    └─ 如果是 Base64 URL → 直接使用
    ↓
[后端处理]
convert_attachments_to_reference_images()  [modes.py:102]
    ├─ HTTP URL → 后端下载 → image_bytes
    ├─ Base64 URL → base64.b64decode() → image_bytes
    └─ 转换为 API 格式
    ↓
[AI 生成/编辑]
返回结果 URL（Base64 或 HTTP 临时 URL）
    ├─ Google: Base64 Data URL
    └─ Tongyi: HTTP 临时 URL
    ↓
[前端处理]
processMediaResult()  [attachmentUtils.ts:960]
    ├─ HTTP URL → fetch() → Blob → Blob URL（显示）
    └─ Base64 URL → 直接使用（显示）
    ↓
[异步上传]
sourceToFile()  [attachmentUtils.ts:291]
    ├─ Base64 URL → fetch() → blob → File
    ├─ Blob URL → fetch() → blob → File
    └─ HTTP URL → fetch(proxyUrl) → blob → File
    ↓
uploadFileAsync()  [storageUpload.ts:404]
    ↓
POST /api/storage/upload-async  [storage.py:576]
    ├─ 保存文件到临时目录  [Line 668]
    ├─ 创建 UploadTask 记录  [Line 638]
    └─ Redis LPUSH upload_tasks_queue task_id  [Line 755]
    ↓
[Worker 处理]
Worker._worker_loop()  [upload_worker_pool.py:316]
    ├─ Redis BRPOP upload_tasks_queue  [Line 349]
    └─ _process_task(task_id)  [Line 381]
        ├─ 更新状态: pending → uploading  [Line 407]
        ├─ _get_file_content(task)  [Line 419]
        │   ├─ source_file_path → 读取本地文件  [Line 501]
        │   └─ source_url → httpx.get() 下载  [Line 526]
        ├─ StorageService.upload_file()  [Line 444]
        └─ _handle_success()  [Line 466]
            ├─ 更新 UploadTask: status → 'completed', target_url  [Line 558]
            └─ update_session_attachment_url()  [storage.py:523]
                └─ 更新 MessageAttachment.url = 云存储 URL
    ↓
[页面重载]
从数据库加载 → 使用云存储 URL（永久有效）
```

**URL类型转换对照表**：

| 阶段 | 输入格式 | 输出格式 | 转换函数 | 代码位置 |
|-----|---------|---------|---------|---------|
| **用户上传** | File 对象 | Blob URL | `URL.createObjectURL` | `InputArea.tsx:108` |
| **InputArea发送** | Blob URL | Base64 URL | `fileToBase64` | `attachmentUtils.ts:196` |
| **processUserAttachments** | Base64 URL | File 对象 | `base64ToFile` | `attachmentUtils.ts:262` |
| **Google上传(可选)** | File 对象 | Google File URI | `llmService.uploadFile` | `llmService.ts` |
| **API请求** | Attachment[] | JSON | `JSON.stringify` | - |
| **后端接收** | JSON | Dict[str, Any] | `convert_attachments_to_reference_images` | `modes.py:102` |
| **Google API** | Dict | `genai_types.Part` | `Part.from_bytes` | `conversational_image_edit_service.py:471` |
| **Google返回** | 字节流 | Base64 URL | `base64.b64encode` | `conversational_image_edit_service.py:615` |
| **Tongyi返回** | - | HTTP URL | - | `tongyi/image_edit.py:308` |
| **前端显示(Google)** | Base64 URL | Base64 URL | 直接使用 | `attachmentUtils.ts:975` |
| **前端显示(Tongyi)** | HTTP URL | Blob URL | `fetch + URL.createObjectURL` | `attachmentUtils.ts:974` |
| **异步上传** | Base64/Blob/HTTP | File 对象 | `sourceToFile` | `attachmentUtils.ts:291` |
| **云存储** | File 对象 | HTTP Cloud URL | `StorageService.upload_file` | `upload_worker_pool.py:444` |

---

### 5.2 Continuity Logic 详细流程

Continuity Logic是Edit模式独有的核心功能，用于在无新上传时自动复用画布图片。

#### 5.2.1 完整流程图

```
[Edit 模式：无新上传，但有 activeImageUrl]
    ↓
processUserAttachments([], activeImageUrl, messages, sessionId)  [attachmentUtils.ts:786]
    ↓
触发 CONTINUITY LOGIC  [Line 798-814]
    ├─ 条件: finalAttachments.length === 0 && activeImageUrl
    └─ prepareAttachmentForApi(activeImageUrl, messages, sessionId, 'canvas', skipBase64ForHttp)
        ↓
步骤 1: findAttachmentByUrl(activeImageUrl, messages)  [Line 664]
    ├─ 策略 1: 精确匹配 url 或 tempUrl
    │   ├─ 遍历 messages（从新到旧）
    │   └─ 匹配 att.url === targetUrl || att.tempUrl === targetUrl
    │
    └─ 策略 2: Blob URL 兜底策略  [Line 566-582]
        ├─ 如果是 Blob URL 且未精确匹配
        └─ 查找最近的有效云端图片附件
            ├─ mimeType.startsWith('image/')
            ├─ uploadStatus === 'completed'
            └─ isHttpUrl(url)
    ↓
步骤 2: 如果找到历史附件
    ├─ tryFetchCloudUrl(sessionId, attachmentId, url, status)  [Line 671]
    │   ├─ 检查是否需要查询（pending 或非 HTTP URL）
    │   ├─ fetchAttachmentStatus(sessionId, attachmentId)  [Line 590]
    │   │   ↓
    │   │   GET /api/sessions/{sessionId}/attachments/{attachmentId}
    │   │   ↓
    │   │   后端查询：  [sessions.py:645-705]
    │   │   ├─ 查询 UploadTask（如果 upload_task_id 存在）
    │   │   ├─ 查询 MessageAttachment
    │   │   └─ 返回 { url, uploadStatus, taskId, taskStatus }
    │   │
    │   └─ 如果返回有效云 URL → 使用云 URL
    │
    └─ 创建 reusedAttachment  [Line 685-691]
        ├─ id: uuidv4()
        ├─ url: finalUrl（云存储 URL 或原始 URL）
        ├─ uploadStatus: finalUploadStatus
        └─ 如果是 HTTP URL → 直接传递（后端下载）
    ↓
步骤 3: 如果未找到历史附件
    ├─ 如果是 Base64/Blob URL  [Line 720-732]
    │   ↓
    │   创建新附件 {
    │     id: uuidv4(),
    │     url: '',  // 本地数据没有永久 URL
    │     uploadStatus: 'pending',
    │     base64Data: base64Data
    │   }
    │
    └─ 如果是 HTTP URL  [Line 735-748]
        ↓
        创建新附件 {
          id: uuidv4(),
          url: imageUrl,  // 直接传递 HTTP URL
          uploadStatus: 'completed'
        }
```

#### 5.2.2 关键优化：HTTP URL 跳过 Base64 转换

**代码位置**: `attachmentUtils.ts:802, 707, 747`

```typescript
// prepareAttachmentForApi 调用时
const skipBase64ForHttp = isHttpUrl(activeImageUrl);

const prepared = await prepareAttachmentForApi(
  activeImageUrl,
  messages,
  sessionId,
  filePrefix,
  skipBase64ForHttp  // ✅ HTTP URL跳过Base64转换
);

// prepareAttachmentForApi 内部
if (skipBase64 && isHttpUrl(imageUrl)) {
  // ✅ 直接返回 HTTP URL，让后端自己下载
  return {
    id: uuidv4(),
    url: imageUrl,
    uploadStatus: 'completed'
  };
}
```

**优化效果**:
- 避免前端下载 HTTP URL
- 避免 HTTP → Base64 → HTTP 的无意义转换
- 减少前端网络开销和内存占用

#### 5.2.3 Blob URL 兜底策略

**代码位置**: `attachmentUtils.ts:566-582`

```typescript
// 如果未找到精确匹配且是 Blob URL，查找最近的有效云端图片附件
if (isBlobUrl(targetUrl) && !found) {
  // 查找最近的有效云端图片附件（兜底策略）
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (!msg.attachments?.length) continue;

    for (const att of msg.attachments) {
      if (
        att.mimeType?.startsWith('image/') &&
        att.uploadStatus === 'completed' &&
        isHttpUrl(att.url)
      ) {
        // 找到最近的有效云端图片附件
        return { attachment: att, messageId: msg.id };
      }
    }
  }
}
```

---

### 5.3 sourceToFile 的3层降级策略

**代码位置**: `attachmentUtils.ts:291-360`

```typescript
export const sourceToFile = async (
  source: string | File,
  filename: string,
  mimeType?: string
): Promise<File> => {
  if (source instanceof File) {
    return source;
  }

  const url = source;

  // 非 HTTP URL → 直接转换
  if (!isHttpUrl(url)) {
    return await urlToFile(url, filename, mimeType);
  }

  // HTTP URL → 3层降级策略
  const strategies = [
    {
      name: '后端代理下载 (解决CORS)',
      fetch: `/api/storage/download?url=${encodeURIComponent(url)}`
    },
    {
      name: '直接下载 (性能优先)',
      fetch: url
    },
    {
      name: 'urlToFile降级 (兜底保障)',
      func: () => urlToFile(url, filename, mimeType)
    }
  ];

  for (const strategy of strategies) {
    try {
      if (strategy.fetch) {
        const response = await fetch(strategy.fetch);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const blob = await response.blob();
        return new File([blob], filename, {
          type: mimeType || blob.type
        });
      } else if (strategy.func) {
        return await strategy.func();
      }
    } catch (e) {
      console.warn(`[sourceToFile] ${strategy.name} 失败:`, e);
      continue;  // ✅ 自动尝试下一个策略
    }
  }

  throw new Error('所有下载策略均失败');
};
```

**策略优势**:
1. **后端代理**: 解决CORS问题
2. **直接下载**: 减少代理开销
3. **urlToFile**: 兜底保障

## 提供商差异分析

不同提供商（Google Gemini vs Tongyi 通义）在附件处理方面的详细差异，包含代码位置、性能对比和优化建议。

### 6.1 Google (Gemini) vs Tongyi (通义) 核心差异

#### 6.1.1 核心差异对比表

| 特性 | Google Gemini | Tongyi 通义 |
|-----|--------------|------------|
| **返回格式** | Base64 Data URL | HTTP 临时URL |
| **API字段** | `inline_data.data` | `result_url` |
| **下载次数** | 0次 (已在内存) | 2次 (显示+上传) |
| **临时性** | 永久 (Base64嵌入) | 有时限 (URL会过期) |
| **传输大小** | 大 (Base64编码+33%) | 小 (仅URL) |
| **前端处理** | 直接使用 | 需要下载 |
| **多轮对话** | 支持 (ConversationalEdit) | 不支持 |
| **文件上传API** | Google Files API | OSS Upload |
| **Gen模式批量** | 支持 (1-4张) | 支持 (1-4张) |

---

### 6.2 Google 提供商详细流程

#### 6.2.1 Edit模式返回格式

**代码位置**: `conversational_image_edit_service.py:615-642`

```python
def _extract_edited_image_from_response(self, response):
    results = []
    for part in response.parts:
        if hasattr(part, 'inline_data') and part.inline_data:
            # ✅ inline_data 字段 (包含图片字节)
            image_bytes = part.inline_data.data
            mime_type = getattr(part.inline_data, 'mime_type', None) or 'image/png'

            # ✅ Base64 编码
            base64_str = base64.b64encode(image_bytes).decode('utf-8')

            # ✅ 构建 Data URL
            url = f"data:{mime_type};base64,{base64_str}"

            results.append({
                'url': url,  # data:image/png;base64,iVBORw0KGgoAAAANS...
                'mimeType': mime_type
            })
    return results
```

#### 6.2.2 Gen模式返回格式

**代码位置**: `image_generator.py:154-188`

```python
def _extract_images_from_response(self, response):
    results = []
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = getattr(part.inline_data, 'mime_type', 'image/png')
                base64_str = base64.b64encode(image_bytes).decode('utf-8')

                results.append(ImageGenerationResult(
                    url=f"data:{mime_type};base64,{base64_str}",
                    mimeType=mime_type
                ))
    return results
```

#### 6.2.3 前端处理 (0次下载)

**代码位置**: `attachmentUtils.ts:975-993`

```typescript
// Google: Base64 Data URL
if (!isHttpUrl(res.url)) {
  // ✅ 直接使用 Base64
  displayUrl = res.url;  // data:image/png;base64,...
}

// ✅ 无需 fetch 下载
// ✅ 无需创建 Blob URL
```

#### 6.2.4 Google Files API (Chat模式优化)

**代码位置**: `conversational_image_edit_service.py:341-387`

```python
async def _upload_to_google_files_api(self, image_bytes: bytes, mime_type: str):
    """上传到 Google Files API (48小时缓存)"""

    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
        tmp_file.write(image_bytes)
        tmp_path = tmp_file.name

    try:
        # 上传到 Google Files API
        uploaded_file = genai.upload_file(
            path=tmp_path,
            mime_type=mime_type
        )

        # ✅ 返回 File URI (减少请求体大小)
        return uploaded_file.uri
    finally:
        os.unlink(tmp_path)

# 使用方式
if ref_img.get('googleFileUri'):
    # ✅ 使用 fileData (File URI)
    message_parts.append(genai_types.Part(file_data=genai_types.FileData(
        file_uri=ref_img['googleFileUri'],
        mime_type=ref_img.get('mimeType', 'image/png')
    )))
else:
    # ❌ 使用 inlineData (Base64, 请求体大)
    message_parts.append(genai_types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    ))
```

---

### 6.3 Tongyi 提供商详细流程

#### 6.3.1 Edit模式返回格式

**代码位置**: `tongyi/image_edit.py:308-312`

```python
def extract_image_url(self, result: dict, model: str) -> str:
    """从 Tongyi API 响应提取图片 URL"""

    if 'output' in result and 'results' in result['output']:
        results = result['output']['results']
        if results and len(results) > 0:
            # ✅ HTTP 临时 URL
            result_url = results[0].get('url', '')

            logger.info(f"[Image Edit] ✅ 图像编辑完成: {result_url[:60]}...")
            return result_url

    raise Exception("无法从响应中提取图片 URL")

# 返回结果
return ImageEditResult(
    success=True,
    url=result_url  # https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/...
)
```

#### 6.3.2 临时URL特征

Tongyi返回的URL特征:
- 域名: `dashscope-result-*.oss-*.aliyuncs.com`
- 包含查询参数: `?Expires=xxx&OSSAccessKeyId=xxx&Signature=xxx`
- 有效期: 通常24小时

示例:
```
https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/1d/c3/...
?Expires=1737273600
&OSSAccessKeyId=LTAI5t...
&Signature=xxx
```

#### 6.3.3 前端处理 (2次下载)

**代码位置**: `attachmentUtils.ts:975-1013`

```typescript
// Tongyi: HTTP 临时 URL
if (isHttpUrl(res.url)) {
  // ❌ 下载1: 用于显示
  const response = await fetch(res.url);
  const blob = await response.blob();
  displayUrl = URL.createObjectURL(blob);
}

// 创建上传任务
const dbAttachmentPromise = (async () => {
  // ❌ 下载2: 用于上传
  const file = await sourceToFile(res.url, filename, mimeType);
  // sourceToFile 内部会再次下载 HTTP URL

  const uploadResult = await storageUpload.uploadFileAsync(file, {
    sessionId, messageId, attachmentId
  });
  return { url: uploadResult.url, uploadTaskId: uploadResult.taskId };
})();
```

---

### 6.4 性能对比

#### 6.4.1 传输大小对比 (以1MB原始图片为例)

| 提供商 | 格式 | 大小 | API响应时间 | 前端下载时间 | 总时间 |
|-------|------|------|-----------|------------|--------|
| **Google** | Base64 | ~1.33MB | +200ms | 0ms | +200ms |
| **Tongyi** | HTTP URL | ~50B | +50ms | +300ms×2 | +650ms |

#### 6.4.2 内存占用对比

| 提供商 | 前端内存 | 后端内存 |
|-------|---------|---------|
| **Google** | Base64字符串 (~1.33MB) | 图片字节 (~1MB) |
| **Tongyi** | Blob URL引用 (~100B) | 无 (直接传URL) |

#### 6.4.3 网络请求对比

| 提供商 | 请求数 | 总流量 (1MB图片) |
|-------|-------|---------------|
| **Google** | 1次 (API) | ~1.33MB (上行) |
| **Tongyi** | 3次 (API + 2次下载) | ~50B (上行) + ~2MB (下载) |

---

### 6.5 优化建议

#### 6.5.1 针对 Tongyi 双重下载问题的优化方案

**当前流程** (2次下载):
```
Tongyi API 返回 HTTP URL
    ↓
前端下载1: 用于显示 (fetch → Blob URL)
    ↓
前端下载2: 用于上传 (sourceToFile → File)
    ↓
上传到云存储
```

**优化方案** (0次前端下载):

```typescript
// processMediaResult 检测 Tongyi HTTP URL
if (isHttpUrl(res.url) && res.url.includes('dashscope-result')) {
  // ✅ 直接传递 HTTP URL 给 Worker Pool
  const uploadResult = await storageUpload.uploadFileAsync(null, {
    sessionId,
    messageId,
    attachmentId,
    sourceUrl: res.url  // ✅ Worker Pool 直接下载
  });

  // ✅ 显示也使用原始 URL (或代理)
  displayUrl = `/api/storage/proxy?url=${encodeURIComponent(res.url)}`;
}
```

**Worker Pool 支持**:

**代码位置**: `upload_worker_pool.py:526-532`

```python
# upload_worker_pool.py:526-532
elif task.source_url:
    # ✅ Worker Pool 直接下载
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(task.source_url)
        response.raise_for_status()
        return response.content
```

**优化效果**:
- 前端下载次数: 2次 → 0次
- 总延迟: +650ms → +350ms (仅API响应 + Worker下载)
- 前端内存占用: 减少 ~1MB

---

**文档状态**: 📝 第五部分进行中（提供商差异分析已完成）  
**下一步**: 继续写入第六部分（函数调用链路详解）
