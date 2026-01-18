# Edit 模式附件处理端到端分析文档

## 概述

本文档提供了 `attachmentUtils.ts` 在 edit 模式下的完整端到端分析，覆盖以下关键场景：
1. **Google 提供商 + Edit 模式 + 用户上传附件**
2. **无附件上传时从画布获取活跃图片**
3. **跨模式附件传递机制**

分析范围：从前端 UI 交互 → 附件处理 → API 调用 → 后端服务 → Google API 的完整数据流。

---

## 一、核心架构

### 1.1 attachmentUtils.ts 的角色定位

**位置**：`D:\gemini-main\gemini-main\frontend\hooks\handlers\attachmentUtils.ts`

**核心职责**：
- 统一的附件处理入口
- URL 类型检测和转换（HTTP/Base64/Blob）
- 跨模式附件复用（CONTINUITY LOGIC）
- 云存储上传管理
- 数据库序列化前的清理

**关键导出函数**（24 个主要函数）：

| 分类 | 函数 | 用途 |
|-----|------|------|
| **URL 类型检测** | `isHttpUrl`, `isBlobUrl`, `isBase64Url` | 识别 URL 类型 |
| **URL 转换** | `urlToBase64`, `fileToBase64`, `sourceToFile` | 格式转换（带降级策略） |
| **云存储上传** | `uploadToCloudStorageSync` | 同步上传到云存储 |
| **附件查询** | `findAttachmentByUrl`, `tryFetchCloudUrl` | 历史查找和后端查询 |
| **高层处理** | `prepareAttachmentForApi`, `processUserAttachments` | 编排复杂流程 |
| **媒体结果处理** | `processMediaResult` | AI 生成图片后处理 |
| **数据库清理** | `cleanAttachmentsForDb` | 序列化前清理 |

---

## 二、场景 1：Google 提供商 + Edit 模式 + 用户上传附件

### 2.1 完整数据流

```
用户选择文件
    ↓
InputArea.handleFileSelect()
    ├─ 创建 Blob URL: URL.createObjectURL(file)
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
ImageEditView.handleSend() 或 App.onSend()
    ↓
processUserAttachments(attachments, activeImageUrl, messages, sessionId)
    ├─ 步骤 1: 检查附件数量
    │   ├─ finalAttachments.length > 0 → 处理用户上传
    │   └─ finalAttachments.length === 0 && activeImageUrl → CONTINUITY LOGIC
    │
    ├─ 步骤 2: 处理每个附件
    │   ├─ uploadStatus === 'completed' && isHttpUrl(url) → 直接传递 HTTP URL
    │   ├─ att.file 存在 → 检查 URL 类型
    │   │   ├─ Blob URL → urlToBase64() + urlToFile()
    │   │   ├─ Base64 URL → base64ToFile()
    │   │   └─ 其他 → 直接使用
    │   └─ 无 file 对象 → 查询后端或直接传递
    │
    └─ 返回: Promise<Attachment[]>
    ↓
useChat.sendMessage(text, options, attachments, mode, currentModel, protocol)
    ├─ 创建 ExecutionContext
    ├─ preprocessorRegistry.process(context)
    │   └─ GoogleFileUploadPreprocessor (Google 文件上传)
    │       ├─ 检查: protocol === 'google' && mode === 'chat'
    │       └─ llmService.uploadFile(file) → fileUri
    │
    ├─ 创建 userMessage (包含处理后的附件)
    ├─ strategyRegistry.getHandler(mode) → ImageEditHandler
    └─ handler.execute(context)
    ↓
ImageEditHandler.doExecute()
    ├─ 转换 attachments → referenceImages { raw: attachment }
    ├─ 如果有 File 但无 HTTP URL → fileToBase64()
    └─ llmService.editImage(text, referenceImages, mode, editOptions)
    ↓
UnifiedProviderClient.editImage()
    ├─ 构建请求体
    │   ├─ modelId
    │   ├─ prompt
    │   ├─ attachments[] (Attachment 对象数组)
    │   └─ options (frontend_session_id, ...)
    │
    └─ POST /api/modes/google/{mode}
    ↓
后端 modes.py: handle_mode()
    ├─ 验证 ModeRequest
    ├─ convert_attachments_to_reference_images()
    │   └─ attachments[] → reference_images { 'raw': {...}, 'mask': {...} }
    │
    └─ provider.edit_image(prompt, model, reference_images, mode, **options)
    ↓
GoogleService.edit_image()
    └─ ImageEditCoordinator.edit_image(mode, ...)
        ├─ mode === 'image-chat-edit' → ConversationalImageEditService
        └─ 其他 → SimpleImageEditService
    ↓
ConversationalImageEditService.send_edit_message()
    ├─ 处理参考图片
    │   ├─ googleFileUri → genai_types.Part(file_data=FileData(...))
    │   ├─ Base64 URL → Part.from_bytes(image_bytes, mime_type)
    │   └─ HTTP URL → aiohttp 下载 → Part.from_bytes(...)
    │
    ├─ message_parts = [image_parts..., text_part]
    └─ chat.send_message(message_parts, config)
    ↓
Google Gemini API
    ↓
返回编辑后的图片
    ├─ response.candidates[0].content.parts
    ├─ 提取 thoughts (从 response.parts)
    └─ 提取最终图片 (part.as_image() 或 part.inline_data)
    ↓
processMediaResult(res, context, 'edited')
    ├─ displayAttachment: { url: Blob URL, tempUrl: HTTP URL, uploadStatus: 'pending' }
    ├─ dbAttachmentPromise:
    │   ├─ sourceToFile(res.url) → File
    │   ├─ storageUpload.uploadFileAsync(file, ...)
    │   └─ 返回 { url: HTTP, uploadTaskId: 'task-123' }
    └─ 返回 { displayAttachment, dbAttachmentPromise }
    ↓
setMessages(updatedMessages)
    ├─ 更新 UI（显示 Blob URL）
    └─ uploadTask 完成后 → updateSessionMessages() → 保存到数据库
```

### 2.2 关键代码路径

#### 前端附件预处理
**位置**：`attachmentUtils.ts:786-942`

```typescript
export const processUserAttachments = async (
  attachments: Attachment[],
  activeImageUrl: string | null,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas'
): Promise<Attachment[]> => {
  let finalAttachments = [...attachments];

  // 关键处理逻辑：
  // 1. uploadStatus === 'completed' && HTTP URL → 直接传递
  if (att.uploadStatus === 'completed' && isHttpUrl(att.url)) {
    return { ...att, url: att.url, uploadStatus: 'completed' };
  }

  // 2. Blob URL → Base64（避免被 InputArea cleanup 释放）
  if (att.file && isBlobUrl(att.url)) {
    const base64Data = await urlToBase64(att.url);
    const file = await urlToFile(att.url, att.name, att.mimeType);
    return { ...att, url: base64Data, file, base64Data };
  }

  // 3. Base64 URL → File 对象
  if (isBase64Url(att.url)) {
    const file = await base64ToFile(att.url, att.name);
    return { ...att, file };
  }

  // 4. HTTP URL → 直接传递
  if (isHttpUrl(att.url)) {
    return { ...att };
  }
};
```

#### 后端参考图片处理
**位置**：`conversational_image_edit_service.py:341-424`

```python
# 优先级 1: Google File URI
if ref_img.get('googleFileUri'):
    message_parts.append(genai_types.Part(file_data=genai_types.FileData(
        file_uri=ref_img['googleFileUri'],
        mime_type=ref_img.get('mimeType', 'image/png')
    )))

# 优先级 2: Base64 URL
elif ref_img.get('url', '').startswith('data:'):
    mime_type, base64_str = parse_data_url(ref_img['url'])
    image_bytes = base64.b64decode(base64_str)
    message_parts.append(genai_types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    ))

# 优先级 3: HTTP URL（下载）
elif ref_img.get('url', '').startswith('http'):
    async with aiohttp.ClientSession() as session:
        async with session.get(ref_img['url']) as response:
            image_bytes = await response.read()
    message_parts.append(genai_types.Part.from_bytes(
        data=image_bytes,
        mime_type=ref_img.get('mimeType', 'image/png')
    ))
```

### 2.3 附件格式转换表

| 阶段 | 输入格式 | 输出格式 | 处理函数 |
|-----|---------|---------|---------|
| **用户上传** | File 对象 | Blob URL | `URL.createObjectURL()` |
| **InputArea 发送** | Blob URL | Base64 URL | `fileToBase64()` |
| **processUserAttachments** | Base64 URL | File 对象 | `base64ToFile()` |
| **Google 上传 (可选)** | File 对象 | Google File URI | `llmService.uploadFile()` |
| **API 请求** | Attachment[] | JSON (序列化) | `JSON.stringify()` |
| **后端接收** | JSON | Dict[str, Any] | `convert_attachments_to_reference_images()` |
| **ConversationalEdit** | Dict | `genai_types.Part` | `Part.from_bytes()` |
| **Google API 返回** | 字节流 | Base64 URL | `base64.b64encode()` |
| **前端显示** | HTTP URL | Blob URL | `URL.createObjectURL(blob)` |

---

## 三、场景 2：无附件上传时从画布获取活跃图片

### 3.1 CONTINUITY LOGIC（连续性逻辑）

**核心机制**：当用户没有上传新附件时，自动从画布获取当前显示的图片作为附件。

**位置**：`attachmentUtils.ts:786-814`

```typescript
export const processUserAttachments = async (
  attachments: Attachment[],
  activeImageUrl: string | null,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas'
): Promise<Attachment[]> => {
  let finalAttachments = [...attachments];

  // ============================================================
  // CONTINUITY LOGIC - 无新上传时使用画布图片
  // ============================================================
  if (finalAttachments.length === 0 && activeImageUrl) {
    console.log(`[processUserAttachments] ✅ 触发 CONTINUITY LOGIC`);

    const skipBase64ForHttp = isHttpUrl(activeImageUrl);
    const prepared = await prepareAttachmentForApi(
      activeImageUrl,
      messages,
      sessionId,
      filePrefix,
      skipBase64ForHttp  // HTTP URL 让后端自己下载
    );

    if (prepared) {
      finalAttachments = [prepared];
    }
    return finalAttachments;
  }

  // 处理用户上传的附件...
};
```

### 3.2 画布图片来源

#### ImageEditView 的画布管理
**位置**：`ImageEditView.tsx:252-332`

```typescript
const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);

// 稳定的 Canvas URL（避免 InputArea 的 Blob URL 被释放）
const canvasObjectUrlRef = useRef<string | null>(null);
const canvasObjectUrlFileRef = useRef<File | null>(null);

const getStableCanvasUrlFromAttachment = useCallback((att: Attachment) => {
  if (att.file) {
    const file = att.file;
    // 创建独立的 Canvas Blob URL
    if (!canvasObjectUrlRef.current || canvasObjectUrlFileRef.current !== file) {
      if (canvasObjectUrlRef.current) {
        URL.revokeObjectURL(canvasObjectUrlRef.current);
      }
      canvasObjectUrlRef.current = URL.createObjectURL(file);
      canvasObjectUrlFileRef.current = file;
    }
    return canvasObjectUrlRef.current;
  }
  return att.url || att.tempUrl || null;
}, []);

// 清理 Canvas URL
useEffect(() => {
  return () => {
    if (canvasObjectUrlRef.current) {
      URL.revokeObjectURL(canvasObjectUrlRef.current);
    }
  };
}, []);
```

#### 画布图片的 3 种来源

**来源 1：用户上传的附件**
```typescript
useEffect(() => {
  if (activeAttachments.length > 0) {
    setActiveImageUrl(getStableCanvasUrlFromAttachment(activeAttachments[0]));
  }
}, [activeAttachments, getStableCanvasUrlFromAttachment]);
```

**来源 2：初始附件 (跨模式传递)**
```typescript
useEffect(() => {
  if (initialAttachments && initialAttachments.length > 0) {
    setActiveAttachments(initialAttachments);
    setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
  }
}, [initialAttachments, getStableCanvasUrlFromAttachment]);
```

**来源 3：AI 生成的最新结果**
```typescript
useEffect(() => {
  if (loadingState === 'idle' && messages.length > 0) {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.id !== lastProcessedMsgId) {
      if (lastMsg.role === Role.MODEL && lastMsg.attachments?.[0]?.url) {
        setActiveImageUrl(lastMsg.attachments[0].url);  // 自动切换到新图
        setLastProcessedMsgId(lastMsg.id);
      }
    }
  }
}, [messages, activeAttachments.length, loadingState, lastProcessedMsgId]);
```

### 3.3 prepareAttachmentForApi 详解

**位置**：`attachmentUtils.ts:653-758`

**核心流程**：
```typescript
export const prepareAttachmentForApi = async (
  imageUrl: string,
  messages: Message[],
  sessionId: string | null,
  filePrefix: string = 'canvas',
  skipBase64: boolean = true
): Promise<Attachment | null> => {
  // 步骤 1: 从历史消息中查找已有附件
  const found = findAttachmentByUrl(imageUrl, messages);

  if (found) {
    const { attachment: existingAttachment } = found;
    let finalUrl = existingAttachment.url;
    let finalUploadStatus = existingAttachment.uploadStatus || 'pending';

    // 步骤 2: 查询后端获取最新云 URL
    const cloudResult = await tryFetchCloudUrl(
      sessionId,
      existingAttachment.id,
      finalUrl,
      finalUploadStatus
    );

    if (cloudResult) {
      finalUrl = cloudResult.url;  // 使用权威的云 URL
      finalUploadStatus = 'completed';
    }

    // 步骤 3: 返回复用的附件
    return {
      id: uuidv4(),
      mimeType: existingAttachment.mimeType || 'image/png',
      name: existingAttachment.name || `${filePrefix}-${Date.now()}.png`,
      url: finalUrl,
      uploadStatus: finalUploadStatus
    };
  }

  // 步骤 4: 未找到历史附件，根据 URL 类型直接处理
  if (isBase64Url(imageUrl)) {
    return {
      id: uuidv4(),
      mimeType: imageUrl.match(/^data:([^;]+);/)?.[1] || 'image/png',
      name: `${filePrefix}-${Date.now()}.png`,
      url: '',
      uploadStatus: 'pending',
      base64Data: imageUrl
    };
  }

  if (isHttpUrl(imageUrl)) {
    return {
      id: uuidv4(),
      mimeType: 'image/png',
      name: `${filePrefix}-${Date.now()}.png`,
      url: imageUrl,
      uploadStatus: 'completed'
    };
  }
};
```

**关键优化**：
1. **避免重复上传**：从历史消息查找已有附件
2. **云 URL 查询**：调用 `tryFetchCloudUrl()` 获取最新的永久 URL
3. **HTTP URL 优化**：`skipBase64=true` 时，直接传递 URL，让后端自己下载

### 3.4 历史附件查找机制

**位置**：`attachmentUtils.ts:413-478`

```typescript
export const findAttachmentByUrl = (
  targetUrl: string,
  messages: Message[]
): { attachment: Attachment; messageId: string } | null => {
  // 按时间倒序遍历
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (!msg.attachments?.length) continue;

    for (const att of msg.attachments) {
      // 精确匹配 url 字段
      if (att.url === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }

      // 匹配 tempUrl 字段（Blob URL 或 DashScope 临时 URL）
      if (att.tempUrl === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }

      // 模糊匹配（提取查询参数前的路径）
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

**匹配策略**：
1. 精确匹配 `url` 字段
2. 精确匹配 `tempUrl` 字段（跨模式查找关键）
3. 模糊匹配（去除查询参数）

### 3.5 后端云 URL 查询

**位置**：`attachmentUtils.ts:378-411`

```typescript
export const tryFetchCloudUrl = async (
  sessionId: string | null,
  attachmentId: string,
  currentUrl: string,
  currentStatus: string
): Promise<{ url: string; uploadStatus: string } | null> => {
  // 已完成上传且是 HTTP URL → 直接使用
  if (currentStatus === 'completed' && isHttpUrl(currentUrl)) {
    return { url: currentUrl, uploadStatus: 'completed' };
  }

  // 查询后端获取最新状态
  if (sessionId && attachmentId) {
    const result = await fetchAttachmentStatus(sessionId, attachmentId);

    if (result && result.uploadStatus === 'completed' && isHttpUrl(result.url)) {
      return { url: result.url, uploadStatus: 'completed' };
    }
  }

  return null;
};
```

**API 调用**：
```typescript
const fetchAttachmentStatus = async (
  sessionId: string,
  attachmentId: string
): Promise<{ url: string; uploadStatus: string } | null> => {
  const response = await fetch(
    `/api/sessions/${sessionId}/attachments/${attachmentId}`,
    { credentials: 'include' }
  );
  return await response.json();
};
```

---

## 四、场景 3：跨模式附件传递机制

### 4.1 模式切换流程

**位置**：`useModeSwitch.ts:31-138`

```typescript
export const useModeSwitch = ({
  availableModels,
  hiddenModelIds,
  currentModelId,
  setCurrentModelId,
  setAppMode
}: UseModeSwitchProps): UseModeSwitchReturn => {
  const handleModeSwitch = useCallback((mode: AppMode) => {
    // 根据新模式过滤模型
    const modeFiltered = filterModelsByAppMode(availableModels, mode);
    const visible = modeFiltered.filter(m => !hiddenModelIds.includes(m.id));

    setAppMode(mode);  // 设置新模式

    // 自动选择合适的模型
    if (mode === 'image-gen') {
      const imageModel = visible.find(m => m.id.toLowerCase().includes('imagen'));
      if (imageModel) setCurrentModelId(imageModel.id);
    } else if (IMAGE_EDIT_MODES.includes(mode)) {
      const imageModel = visible.find(m =>
        m.capabilities.vision && !m.id.includes('imagen')
      );
      if (imageModel) setCurrentModelId(imageModel.id);
    }
  }, [availableModels, hiddenModelIds, setCurrentModelId, setAppMode]);
};
```

### 4.2 跨模式消息过滤

**位置**：`App.tsx:178-189`

```typescript
// 仅显示当前模式或通用的消息
const currentViewMessages = useViewMessages(messages, appMode);

// 图片导航：从当前视图的消息中提取所有图片
const {
  previewImage,
  setPreviewImage,
  allImages,
  handleNextImage,
  handlePrevImage,
  handleImageClick
} = useImageNavigation(currentViewMessages);
```

**useViewMessages 实现**：
```typescript
export const useViewMessages = (
  messages: Message[],
  appMode: AppMode
): Message[] => {
  return useMemo(() => {
    return messages.filter(msg => {
      // 保留当前模式的消息
      if (msg.mode === appMode) return true;

      // 保留通用消息（无 mode 字段且当前是 chat 模式）
      if (!msg.mode && appMode === 'chat') return true;

      return false;
    });
  }, [messages, appMode]);
};
```

### 4.3 跨模式附件传递示例

#### 场景：Chat → Image Edit

```typescript
// 步骤 1：在 Chat 模式上传图片
// Message: {
//   role: Role.USER,
//   content: "分析这张图片",
//   attachments: [{
//     id: "att-123",
//     url: "blob:xxx",
//     uploadStatus: "pending",
//     file: File { ... }
//   }],
//   mode: 'chat'
// }

// 步骤 2：用户切换到 Image Edit 模式
handleModeSwitch('image-chat-edit');

// 步骤 3：ImageEditView 接收 initialAttachments
<ImageEditView
  initialAttachments={messages.find(m => m.attachments?.length)?.attachments}
  ...
/>

// 步骤 4：自动同步到画布
useEffect(() => {
  if (initialAttachments && initialAttachments.length > 0) {
    setActiveAttachments(initialAttachments);
    setActiveImageUrl(getStableCanvasUrlFromAttachment(initialAttachments[0]));
  }
}, [initialAttachments]);

// 步骤 5：用户编辑并发送（无需重新上传）
handleSend(text, options, [], mode);
// → processUserAttachments([], activeImageUrl, messages, sessionId)
// → 触发 CONTINUITY LOGIC
// → prepareAttachmentForApi(activeImageUrl, ...)
// → findAttachmentByUrl() 找到原始附件
```

#### 场景：Image Edit 多轮编辑

```typescript
// 第 1 轮：用户上传图片并编辑
// Message 1: { role: USER, attachments: [{ url: "blob:xxx", file: File }], mode: 'image-chat-edit' }
// Message 2: { role: MODEL, attachments: [{ url: "http://temp-url", uploadStatus: 'pending' }], mode: 'image-chat-edit' }

// 第 2 轮：用户继续编辑（无需重新上传）
// activeImageUrl = Message 2.attachments[0].url
// processUserAttachments([], activeImageUrl, messages, sessionId)
// → findAttachmentByUrl(activeImageUrl) → 找到 Message 2 的附件
// → tryFetchCloudUrl() → 查询后端获取永久 URL
// → 返回 { url: "https://cloud-storage.com/...", uploadStatus: 'completed' }

// 第 3 轮：用户再次编辑
// activeImageUrl = 最新生成的图片 URL
// → 重复第 2 轮流程
```

### 4.4 Attachment 数据结构的跨模式字段

```typescript
interface Attachment {
  id: string;                          // 唯一标识

  // 显示相关
  url?: string;                        // 权威 URL（优先级：HTTP > Base64 > Blob）

  // 跨模式查找关键字段
  tempUrl?: string;                    // 临时 URL（用于 findAttachmentByUrl）
                                       // 存储原始 URL（Blob/HTTP 临时 URL）

  // 上传相关
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'failed';
  uploadTaskId?: string;               // 异步上传任务 ID

  // 文件相关
  file?: File;                         // 原始 File 对象
  mimeType: string;
  name: string;

  // 云存储 API 相关
  fileUri?: string;                    // Google Files API URI
  googleFileUri?: string;
  googleFileExpiry?: number;
}
```

**跨模式查找的关键**：
- `tempUrl` 字段保存原始 URL（Blob URL 或 HTTP 临时 URL）
- `findAttachmentByUrl()` 同时匹配 `url` 和 `tempUrl`
- 即使 `url` 被清理（如 Blob URL 失效），仍可通过 `tempUrl` 找到附件

### 4.5 数据库清理和序列化

**位置**：`attachmentUtils.ts:98-168`

```typescript
export const cleanAttachmentsForDb = (
  atts: Attachment[],
  verbose: boolean = false
): Attachment[] => {
  return atts.map(att => {
    const cleaned = { ...att };
    const url = cleaned.url || '';

    // Blob URL → 清空（临时，不可持久化）
    if (isBlobUrl(url)) {
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }

    // Base64 URL → 清空（太大，不可持久化）
    else if (isBase64Url(url)) {
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }

    // HTTP URL
    else if (isHttpUrl(url)) {
      if (cleaned.uploadStatus === 'completed') {
        // 永久云 URL → 保留
      } else if (url.includes('/temp/') || url.includes('expires=')) {
        // 临时 URL → 清空
        cleaned.url = '';
        cleaned.uploadStatus = 'pending';
      }
    }

    // 删除不可序列化字段
    delete cleaned.file;
    delete cleaned.base64Data;

    return cleaned;
  });
};
```

**处理规则**：

| URL 类型 | uploadStatus | 处理方式 | 理由 |
|---------|-------------|---------|------|
| Blob URL | * | **清空** | 页面关闭后失效 |
| Base64 URL | * | **清空** | 数据过大（>1MB） |
| HTTP URL | completed | **保留** | 云存储 URL，永久有效 |
| HTTP URL | pending + `/temp/` | **清空** | 临时 URL，会过期 |

---

## 五、关键优化实现

### 5.1 三层降级策略（sourceToFile）

**位置**：`attachmentUtils.ts:291-360`

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

  // HTTP URL → 三层降级策略
  const strategies = [
    {
      name: '后端代理',
      fetch: `/api/storage/download?url=${encodeURIComponent(url)}`
    },
    {
      name: '直接下载',
      fetch: url
    },
    {
      name: 'urlToFile',
      func: () => urlToFile(url, filename, mimeType)
    }
  ];

  for (const strategy of strategies) {
    try {
      if (strategy.fetch) {
        const response = await fetch(strategy.fetch);
        const blob = await response.blob();
        return new File([blob], filename, { type: mimeType || blob.type });
      } else if (strategy.func) {
        return await strategy.func();
      }
    } catch (e) {
      console.warn(`[sourceToFile] ${strategy.name} 失败:`, e);
      continue;
    }
  }

  throw new Error('所有下载策略均失败');
};
```

**优势**：
1. **解决 CORS 问题**：通过后端代理下载
2. **性能优化**：优先直接下载（无代理开销）
3. **兜底保障**：urlToFile 作为最后备选

### 5.2 Blob URL 生命周期管理

**创建**：
```typescript
const blobUrl = URL.createObjectURL(file);
```

**使用**：
```typescript
<img src={blobUrl} alt="preview" />
```

**转换**（发送前）：
```typescript
const base64Url = await fileToBase64(file);  // 永久有效
```

**清理**：
```typescript
URL.revokeObjectURL(blobUrl);  // 释放内存
```

**独立性**（ImageEditView）：
```typescript
// ImageEditView 维护自己的 Canvas Blob URL
const canvasObjectUrlRef = useRef<string | null>(null);

// 不依赖 InputArea 的 Blob URL（避免被 cleanup 释放）
const getStableCanvasUrlFromAttachment = (att) => {
  if (att.file) {
    if (!canvasObjectUrlRef.current || canvasObjectUrlFileRef.current !== att.file) {
      if (canvasObjectUrlRef.current) {
        URL.revokeObjectURL(canvasObjectUrlRef.current);
      }
      canvasObjectUrlRef.current = URL.createObjectURL(att.file);
    }
    return canvasObjectUrlRef.current;
  }
  return att.url || att.tempUrl;
};
```

### 5.3 Google Files API 优化

**位置**：`simple_image_edit_service.py:236-478`

```python
async def _process_reference_image(
    self,
    reference_image: Dict[str, Any],
    use_google_files_api: bool = True
) -> Dict[str, Any]:
    """
    优先级处理流程
    """

    # 优先级 1: Google File URI（已上传，未过期）
    if reference_image.get('googleFileUri'):
        if not expired(reference_image.get('googleFileExpiry')):
            return {
                'type': 'fileData',
                'data': {
                    'fileUri': reference_image['googleFileUri'],
                    'mimeType': reference_image.get('mimeType', 'image/png')
                }
            }

    # 优先级 2: Base64 数据
    base64_data = reference_image.get('base64Data') or reference_image.get('url')
    if base64_data and base64_data.startswith('data:'):
        mime_type, base64_str = parse_data_url(base64_data)
        image_bytes = base64.b64decode(base64_str)

        # 如果启用 Google Files API，尝试上传
        if use_google_files_api:
            file_uri = await self._upload_bytes_to_google_files(
                image_bytes,
                mime_type
            )
            return {
                'type': 'fileData',
                'data': {'fileUri': file_uri, 'mimeType': mime_type}
            }
        else:
            # 回退到 inlineData
            return {
                'type': 'inlineData',
                'data': {'data': base64_str, 'mimeType': mime_type}
            }

    # 优先级 3: HTTP URL（下载后上传）
    if reference_image.get('url', '').startswith('http'):
        async with aiohttp.ClientSession() as session:
            async with session.get(reference_image['url']) as response:
                image_bytes = await response.read()

        if use_google_files_api:
            file_uri = await self._upload_bytes_to_google_files(
                image_bytes,
                mime_type
            )
            return {
                'type': 'fileData',
                'data': {'fileUri': file_uri, 'mimeType': mime_type}
            }
```

**优势**：
- 减少请求体大小（File URI 代替 Base64）
- 提高传输效率
- 48 小时缓存有效期

---

## 六、调试和监控

### 6.1 前端日志点

**attachmentUtils.ts**：
```typescript
[processUserAttachments] ✅ 触发 CONTINUITY LOGIC
[prepareAttachmentForApi] 在历史中找到附件
[tryFetchCloudUrl] 后端返回云 URL
[sourceToFile] 后端代理下载失败，尝试直接下载
```

**ImageEditView.tsx**：
```typescript
[ImageEditView] handleSend 处理附件失败
```

**ImageEditHandler.ts**：
```typescript
[ImageEditHandler] 已将 File 对象转换为 Base64 Data URL
```

### 6.2 后端日志点

**modes.py**：
```python
[Modes] Request: provider=google, mode=image-chat-edit
```

**google_service.py**：
```python
[Google Service] Delegating image editing to ImageEditCoordinator
```

**conversational_image_edit_service.py**：
```python
[ConversationalImageEdit] HTTP URL 下载成功
[ConversationalImageEdit] 提取编辑后的图片
```

**simple_image_edit_service.py**：
```python
[SimpleImageEdit] Google Files API upload failed, using Base64
```

### 6.3 关键 API 端点

| 端点 | 方法 | 用途 |
|-----|------|------|
| `/api/modes/google/{mode}` | POST | 统一模式路由 |
| `/api/sessions/{sessionId}/attachments/{attachmentId}` | GET | 查询附件状态 |
| `/api/storage/download?url=...` | GET | 代理下载（解决 CORS） |

---

## 七、总结

### 7.1 数据流关键点

1. **始发点**：`InputArea.handleFileSelect()` 或 `Canvas activeImageUrl`
2. **处理核心**：`processUserAttachments()` + `prepareAttachmentForApi()`
3. **执行点**：`useChat.sendMessage()` → `handler.execute()`
4. **存储点**：`updateSessionMessages()` → 数据库

### 7.2 跨模式传递的保证

1. **消息级别隔离**：每条消息记录 `mode` 字段
2. **ViewMessages 过滤**：按模式过滤，但保留历史图片
3. **Attachment 查找**：通过 `url` 或 `tempUrl` 在历史中查找
4. **云 URL 查询**：后端查询 `upload_tasks` 表获取权威 URL

### 7.3 状态管理最佳实践

1. **url 字段**：始终存储最有效的 URL（HTTP > Base64 > Blob）
2. **tempUrl 字段**：存储原始 URL（用于跨模式查找）
3. **uploadStatus**：准确反映上传状态
4. **file 对象**：仅用于上传，不保存到数据库

### 7.4 核心设计模式

1. **CONTINUITY LOGIC**：无新上传时自动复用画布图片
2. **三层降级策略**：HTTP URL 下载的多重保障
3. **Blob URL 独立性**：各视图维护自己的 Canvas Blob URL
4. **优先级处理**：Google File URI > Base64 > HTTP URL

---

## 附录：关键文件索引

| 文件 | 行数 | 关键函数 |
|-----|------|---------|
| `attachmentUtils.ts` | 786-942 | `processUserAttachments` |
| `attachmentUtils.ts` | 653-758 | `prepareAttachmentForApi` |
| `attachmentUtils.ts` | 413-478 | `findAttachmentByUrl` |
| `attachmentUtils.ts` | 378-411 | `tryFetchCloudUrl` |
| `attachmentUtils.ts` | 291-360 | `sourceToFile` |
| `attachmentUtils.ts` | 98-168 | `cleanAttachmentsForDb` |
| `ImageEditView.tsx` | 252-332 | Canvas 状态管理 |
| `useChat.ts` | 44-241 | `sendMessage` |
| `ImageEditHandlerClass.ts` | 9-147 | `doExecute` |
| `modes.py` | 150-300 | `handle_mode` |
| `conversational_image_edit_service.py` | 341-424 | 参考图片处理 |
| `simple_image_edit_service.py` | 236-478 | Google Files API 优化 |
