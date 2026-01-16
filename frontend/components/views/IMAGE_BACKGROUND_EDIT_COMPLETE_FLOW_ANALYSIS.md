# ImageBackgroundEditView 完整流程分析：从用户点击发送到UI显示图片

## 问题描述
分析 `image-background-edit` 模式下，用户点击发送按钮后，参数和附件如何传递到后端，以及后端返回的图片如何在前端UI中显示。

## 完整数据流追踪

### 阶段 1: 用户交互 → 附件和参数收集

#### 步骤 1.1: 用户点击发送按钮
**位置**: `frontend/components/chat/input/PromptInput.tsx` line 257-267

```typescript
<button 
  onClick={handleSend}  // handleSend 来自 InputArea
  disabled={isSendDisabled}
>
  <Send size={20} />
</button>
```

#### 步骤 1.2: ImageBackgroundEditView.handleSend 被调用
**位置**: `frontend/components/views/ImageBackgroundEditView.tsx` line 383-398

**关键代码**:
```typescript
const handleSend = useCallback(async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
  try {
    // ✅ 使用统一的附件处理函数（CONTINUITY LOGIC）
    const finalAttachments = await processUserAttachments(
      attachments,        // 用户上传的附件（可能为空）
      activeImageUrl,    // 当前画布上的图片 URL
      messages,          // 消息历史
      currentSessionId,  // 会话 ID
      'canvas'           // 文件前缀
    );
    // ✅ 固定使用 image-background-edit 模式
    onSend(text, options, finalAttachments, editMode);  // editMode = 'image-background-edit'
  } catch (error) {
    console.error('[ImageBackgroundEditView] handleSend 处理附件失败:', error);
    showError('处理附件失败，请重试');
    return;
  }
}, [activeImageUrl, messages, currentSessionId, onSend, editMode, showError]);
```

**关键逻辑**:
- **CONTINUITY LOGIC**: 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），`processUserAttachments` 会自动使用画布上的图片
- **固定模式**: 始终使用 `editMode = 'image-background-edit'`，忽略传入的 `mode` 参数

#### 步骤 1.3: processUserAttachments 处理附件（CONTINUITY LOGIC）
**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 786-942

**处理流程**:
1. **如果用户没有上传新附件，但画布上有图片**:
   - 调用 `prepareAttachmentForApi(activeImageUrl, messages, sessionId, 'canvas')`
   - `prepareAttachmentForApi` 会尝试从历史消息中查找匹配的附件（通过 URL 匹配）
   - 如果找到，复用附件的 ID 和其他信息，查询后端获取云存储 URL
   - 如果未找到，根据 URL 类型（Base64/Blob/HTTP）创建新附件

2. **如果用户上传了附件**:
   - 处理每个附件：
     - HTTP URL（已上传）: 直接传递 URL，后端会自己下载
     - File 对象: 转换为 Base64 Data URL（用于 UI 显示）和 File 对象（用于上传）
     - Blob URL: 转换为 Base64 Data URL（永久有效）
     - Base64 URL: 直接使用

**返回**: 处理后的 `Attachment[]`，包含 `url`（用于显示）和 `base64Data`/`file`（用于 API 调用）

### 阶段 2: 参数传递 → 后端请求

#### 步骤 2.1: App.tsx.onSend 接收参数
**位置**: `frontend/App.tsx` line 254-285

```typescript
const onSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
  // ...
  const optionsWithPersona = { ...options, persona: activePersona };
  // ...
  sendMessage(text, optionsWithPersona, attachments, mode, modelForSend, config.protocol);
}, [...]);
```

**确认**: `text`, `options`, `attachments`, `mode` 完整传递给 `sendMessage`。

#### 步骤 2.2: useChat.sendMessage 接收参数
**位置**: `frontend/hooks/useChat.ts` line 44-64

```typescript
const sendMessage = async (
  text: string,
  options: ChatOptions,
  attachments: Attachment[],
  mode: AppMode,  // ✅ 'image-background-edit'
  currentModel: ModelConfig,
  protocol: 'google' | 'openai'
) => {
  // ...
  const enhancedOptions = options.enableResearch
    ? { ...options, enableSearch: true }
    : options;
  llmService.startNewChat(contextHistory, currentModel, enhancedOptions);
  // ...
  const handler = strategyRegistry.getHandler(mode);  // ✅ 返回 ImageEditHandler
  const result = await handler.execute(context);
  // ...
};
```

**确认**: 
- `mode` 传递给 `strategyRegistry.getHandler(mode)`，返回 `ImageEditHandler`
- `attachments` 传递给 `handler.execute(context)`

#### 步骤 2.3: ImageEditHandler.doExecute 处理附件
**位置**: `frontend/hooks/handlers/ImageEditHandlerClass.ts` line 10-68

```typescript
protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
  const referenceImages: Record<string, Attachment> = {};
  
  // ✅ 处理第一个附件作为 raw（基础图片）
  if (context.attachments.length > 0) {
    let rawAttachment = context.attachments[0];
    
    // ✅ 如果有 File 对象但没有 HTTP URL，转换为 Base64
    if (rawAttachment.file && !isHttpUrl(rawAttachment.url)) {
      if (!(rawAttachment as any).base64Data) {
        const base64Data = await fileToBase64(rawAttachment.file);
        rawAttachment = { ...rawAttachment, url: base64Data, base64Data };
      }
    } else if (isHttpUrl(rawAttachment.url)) {
      // ✅ 有 HTTP URL，直接传递 URL（后端会自己下载）
      console.log('[ImageEditHandler] ✅ 使用 HTTP URL，后端将自行下载');
    }
    
    referenceImages.raw = rawAttachment;
  }
  
  // ✅ 检查是否有 mask（第二个附件可能是 mask）
  if (context.attachments.length > 1 && context.mode === 'image-mask-edit') {
    referenceImages.mask = context.attachments[1];
  }
  
  // ✅ 传递模式参数和 sessionId
  const editOptions = {
    ...context.options,
    frontend_session_id: context.sessionId,
    sessionId: context.sessionId
  };
  
  // ✅ 调用 llmService.editImage
  const results = await llmService.editImage(
    context.text, 
    referenceImages,
    context.mode,  // ✅ 'image-background-edit'
    editOptions
  );
  // ...
}
```

**关键处理**:
- 将 `attachments` 数组转换为 `referenceImages` 字典格式: `{ raw: Attachment, mask?: Attachment }`
- 对于 `image-background-edit` 模式，只需要 `raw` 附件（基础图片）
- 如果有 HTTP URL，直接传递 URL；否则转换为 Base64

#### 步骤 2.4: llmService.editImage 路由到 provider
**位置**: `frontend/services/llmService.ts` line 240-329

```typescript
public async editImage(
  prompt: string, 
  referenceImages: Record<string, Attachment>,
  mode?: AppMode,  // ✅ 'image-background-edit'
  options?: ChatOptions
): Promise<ImageGenerationResult[]> {
  // ✅ 验证输入
  if (!referenceImages.raw) {
    throw new Error('Raw reference image is required for image editing');
  }
  
  // ✅ 合并 options
  const finalOptions = options ? { ...this._cachedOptions, ...options } : this._cachedOptions;
  
  // ✅ 调用 UnifiedProviderClient.editImage
  if ('id' in provider && typeof (provider as any).id === 'string') {
    return (provider as UnifiedProviderClient).editImage(
      this._cachedModelConfig.id,
      prompt,
      referenceImages,
      finalOptions,
      this.baseUrl,
      mode  // ✅ 传递模式参数
    );
  }
  // ...
}
```

**确认**: 
- `mode = 'image-background-edit'` 传递给 `UnifiedProviderClient.editImage`
- `referenceImages = { raw: Attachment }` 传递给 provider

#### 步骤 2.5: UnifiedProviderClient.editImage 转换为请求格式
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 488-551

```typescript
async editImage(
  modelId: string,
  prompt: string,
  referenceImages: Record<string, any>,  // ✅ { raw: Attachment }
  options: ChatOptions,
  baseUrl: string,
  mode?: string  // ✅ 'image-background-edit'
): Promise<ImageGenerationResult[]> {
  // ✅ 将 referenceImages 对象转换为 attachments 数组
  const attachments: Attachment[] = [];
  for (const [key, value] of Object.entries(referenceImages)) {
    if (value) {
      attachments.push({
        ...value,
        role: key  // ✅ 'raw' 或 'mask'
      } as Attachment);
    }
  }
  
  // ✅ 调用 executeMode
  const data = await this.executeMode(
    mode || 'image-edit',  // ✅ 'image-background-edit'
    modelId,
    prompt,
    attachments,  // ✅ 包含 role='raw' 的附件
    { ...options, baseUrl: baseUrl || options.baseUrl }
  );
  
  return Array.isArray(data) ? data : [];
}
```

**确认**: 
- `referenceImages` 转换为 `attachments` 数组，每个附件包含 `role` 字段（'raw' 或 'mask'）
- 调用 `executeMode('image-background-edit', ...)`

#### 步骤 2.6: UnifiedProviderClient.executeMode 构建请求体
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 378-443

```typescript
async executeMode(
  mode: string,  // ✅ 'image-background-edit'
  modelId: string,
  prompt: string,
  attachments: Attachment[] = [],  // ✅ 包含 role='raw' 的附件
  options: Partial<ChatOptions> = {},
  extra: Record<string, any> = {}
): Promise<any> {
  const requestBody = {
    modelId,
    prompt,
    attachments,  // ✅ 包含 role='raw' 的附件
    options: {
      ...options  // ✅ 包含 frontend_session_id, sessionId 等
    },
    extra
  };
  
  const response = await fetch(`/api/modes/${this.id}/${mode}`, {  // ✅ '/api/modes/google/image-background-edit'
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(requestBody)
  });
  
  const data = await response.json();
  return data.data;  // ✅ 返回 { success: true, data: {...} } 中的 data
}
```

**确认**: 
- 请求发送到 `/api/modes/google/image-background-edit`
- `attachments` 包含 `role='raw'` 的附件
- `options` 包含 `frontend_session_id` 和 `sessionId`（用于对话式编辑）

### 阶段 3: 后端处理 → 生成图片

#### 步骤 3.1: 后端路由接收请求
**位置**: `backend/app/routers/core/modes.py` line 150-305

```python
@router.post("/{provider}/{mode}")  # ✅ '/api/modes/google/image-background-edit'
async def handle_mode(
    provider: str,  # ✅ 'google'
    mode: str,      # ✅ 'image-background-edit'
    request_body: ModeRequest,
    ...
):
    # ✅ 1. 获取凭证
    api_key, api_url = await get_provider_credentials(...)
    
    # ✅ 2. 创建提供商服务
    service = ProviderFactory.create(provider=provider, ...)
    
    # ✅ 3. 根据 mode 获取服务方法名
    method_name = get_service_method(mode)  # ✅ 'image-background-edit' -> 'edit_image'
    
    # ✅ 4. 准备参数
    params = {
        "model": request_body.modelId,
        "prompt": request_body.prompt,
    }
    
    # ✅ 5. 添加 options 中的参数
    if request_body.options:
        options_dict = request_body.options.dict(exclude_none=True)
        params.update(options_dict)
    
    # ✅ 6. 转换 attachments 为 reference_images
    if request_body.attachments:
        reference_images = convert_attachments_to_reference_images(request_body.attachments)
        # ✅ reference_images = { 'raw': base64_image, 'mask': base64_mask, ... }
        if reference_images:
            params["reference_images"] = reference_images
    
    # ✅ 7. 对于 edit_image 方法，传递 mode 参数
    if method_name == "edit_image":
        params["mode"] = mode  # ✅ 'image-background-edit'
    
    # ✅ 8. 调用服务方法
    result = await method(**params)  # ✅ service.edit_image(**params)
    
    # ✅ 9. 返回响应
    return ModeResponse(success=True, data=result, ...)
```

**关键处理**:
- `convert_attachments_to_reference_images` 将 `attachments` 数组转换为 `reference_images` 字典
- 根据 `attachment.role` 设置键名（'raw', 'mask', 等）
- `params["mode"] = 'image-background-edit'` 传递给 `edit_image` 方法

#### 步骤 3.2: GoogleService.edit_image 委托给 ImageEditCoordinator
**位置**: `backend/app/services/gemini/google_service.py` line 407-443

```python
async def edit_image(
    self,
    prompt: str,
    model: str,
    reference_images: Dict[str, Any],  # ✅ { 'raw': base64_image }
    mode: Optional[str] = None,  # ✅ 'image-background-edit'
    **kwargs
) -> List[Dict[str, Any]]:
    # ✅ 委托给 ImageEditCoordinator
    return await self.image_edit_coordinator.edit_image(
        prompt=prompt,
        model=model,
        reference_images=reference_images,
        mode=mode,  # ✅ 'image-background-edit'
        sdk_initializer=self.sdk_initializer,
        chat_session_manager=self.chat_session_manager,
        **kwargs
    )
```

**确认**: `mode='image-background-edit'` 传递给 `ImageEditCoordinator.edit_image`。

#### 步骤 3.3: ImageEditCoordinator.edit_image 根据 mode 路由
**位置**: `backend/app/services/gemini/image_edit_coordinator.py`

**路由逻辑**:
- `mode='image-background-edit'` → 路由到 `ImageEditCoordinator` 的 Vertex AI Imagen 实现
- 调用 Vertex AI Imagen 的 `edit_image` API，使用 `edit_mode='background'`

#### 步骤 3.4: 后端返回图片数据
**位置**: `backend/app/services/gemini/image_edit_vertex_ai.py`

**返回格式**: `List[Dict[str, Any]]`，每个元素包含:
- `url`: Base64 Data URL (例如: `"data:image/png;base64,..."`)
- `mimeType`: MIME 类型 (例如: `"image/png"`)
- `thoughts`: 思考过程（可选）
- `text`: 文本响应（可选）

### 阶段 4: 后端响应 → 前端处理

#### 步骤 4.1: UnifiedProviderClient.executeMode 解析响应
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 432-438

```typescript
const data = await response.json();
// ✅ 新架构统一响应格式: { success: true, data: {...} }
if (!data.success || data.data === undefined) {
    throw new Error(`Invalid response format: ${JSON.stringify(data)}`);
}

return data.data;  // ✅ 返回 data.data（即 List[Dict]）
```

**确认**: 返回 `data.data`，即后端返回的 `results` 列表。

#### 步骤 4.2: llmService.editImage 返回结果
**位置**: `frontend/services/llmService.ts` line 311-318

```typescript
return (provider as UnifiedProviderClient).editImage(
    this._cachedModelConfig.id,
    prompt,
    referenceImages,
    finalOptions,
    this.baseUrl,
    mode
);  // ✅ 返回 ImageGenerationResult[]
```

**返回类型**: `ImageGenerationResult[]`，每个元素包含:
- `url`: string (Base64 Data URL)
- `mimeType`: string
- `thoughts`: Array<{ type: 'text' | 'image'; content: string }> (可选)
- `text`: string (可选)

#### 步骤 4.3: ImageEditHandler.doExecute 处理结果
**位置**: `frontend/hooks/handlers/ImageEditHandlerClass.ts` line 70-145

```typescript
// ✅ 提取 thoughts 和 text（从第一个结果中）
const firstResult = results[0];
const thoughts = firstResult?.thoughts || [];
const textResponse = firstResult?.text;

// ✅ 使用统一的媒体处理函数
const processed = await Promise.all(
  results.map(res => processMediaResult(res, context, 'edited'))
);
// ✅ processed: [{ displayAttachment: Attachment, dbAttachmentPromise: Promise<Attachment> }, ...]

const displayAttachments: Attachment[] = processed.map(p => p.displayAttachment);
// ✅ displayAttachments: Attachment[]，用于立即显示

// ✅ 构建内容：包含 thoughts 和 text（如果有）
let content = `Edited images for: "${context.text}"`;
if (thoughts.length > 0 || textResponse) {
  const thoughtTexts = thoughts
    .filter(t => t.type === 'text')
    .map(t => t.content)
    .join('\n\n');
  if (thoughtTexts) {
    content += `\n\n**思考过程：**\n${thoughtTexts}`;
  }
  if (textResponse) {
    content += `\n\n**AI 响应：**\n${textResponse}`;
  }
}

const uploadTask = async () => {
  const dbAttachments = await Promise.all(processed.map(p => p.dbAttachmentPromise));
  const dbUserAttachments = await Promise.all(
    context.attachments.map(async (att) => {
      // ✅ 处理用户上传的附件（上传到云存储）
      if (att.file) {
        const result = await storageUpload.uploadFileAsync(att.file, {...});
        return { ...att, uploadStatus: result.taskId ? 'pending' : 'failed' };
      }
      return att;
    })
  );
  return { dbAttachments, dbUserAttachments };
};

return {
  content: content,
  attachments: displayAttachments,  // ✅ 用于立即显示
  uploadTask: uploadTask(),  // ✅ 异步上传任务
  thoughts: thoughts,  // ✅ 用于前端显示思考过程
  textResponse: textResponse  // ✅ 用于前端显示文本响应
};
```

**处理逻辑**:
1. **提取 thoughts 和 textResponse**: 从第一个结果中提取（所有图片共享相同的思考过程）
2. **processMediaResult**: 处理每个图片结果，创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
3. **构建 content**: 包含思考过程和文本响应（如果有）
4. **uploadTask**: 异步上传任务，处理 AI 生成的图片和用户上传的附件

#### 步骤 4.4: processMediaResult 处理单个图片结果
**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 960-1016

```typescript
export const processMediaResult = async (
  res: { url: string; mimeType: string; filename?: string },  // ✅ 后端返回的格式
  context: { sessionId: string; modelMessageId: string; storageId?: string },
  filePrefix: string  // ✅ 'edited'
): Promise<{ 
  displayAttachment: Attachment; 
  dbAttachmentPromise: Promise<Attachment>; 
}> => {
  const attachmentId = uuidv4();
  const filename = res.filename || `${filePrefix}-${Date.now()}.png`;
  let displayUrl = res.url;  // ✅ 后端返回的 Base64 Data URL
  const originalUrl = res.url;

  // ✅ 根据 URL 类型处理显示 URL
  if (isHttpUrl(res.url)) {
    // HTTP URL（临时 URL）- 下载后创建 Blob URL 用于显示
    const response = await fetch(res.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob);  // ✅ 创建 Blob URL
  }
  // ✅ 对于 Base64 URL，直接使用

  // ✅ 创建用于 UI 显示的附件
  const displayAttachment: Attachment = {
    id: attachmentId,
    mimeType: res.mimeType,
    name: filename,
    url: displayUrl,  // ✅ Base64 Data URL 或 Blob URL
    tempUrl: originalUrl,  // ✅ 保存原始 URL
    uploadStatus: 'pending' as const,
  };

  // ✅ 创建异步上传任务
  const dbAttachmentPromise = (async (): Promise<Attachment> => {
    const file = await sourceToFile(res.url, filename, res.mimeType);
    
    const result = await storageUpload.uploadFileAsync(file, {
      sessionId: context.sessionId,
      messageId: context.modelMessageId,
      attachmentId: attachmentId,
      storageId: context.storageId,
    });

    return {
      id: attachmentId,
      mimeType: res.mimeType,
      name: filename,
      url: isHttpUrl(originalUrl) ? originalUrl : '',  // ✅ 临时 URL 或空（等待上传完成）
      tempUrl: isHttpUrl(originalUrl) ? originalUrl : undefined,
      uploadStatus: result.taskId ? 'pending' : 'failed',
      uploadTaskId: result.taskId || undefined,
    };
  })();

  return { displayAttachment, dbAttachmentPromise };
};
```

**处理逻辑**:
1. **displayAttachment**: 用于立即显示，`url` 字段是 Base64 Data URL 或 Blob URL
2. **dbAttachmentPromise**: 异步上传任务，完成后返回包含云存储 URL 的 Attachment

### 阶段 5: 前端UI更新 → 显示图片

#### 步骤 5.1: useChat.sendMessage 更新 messages 状态
**位置**: `frontend/hooks/useChat.ts` line 138-155

```typescript
// 8. Execute Handler (策略模式)
const handler = strategyRegistry.getHandler(mode);
const result = await handler.execute(context);
// ✅ result: HandlerResult = { 
//   content: string, 
//   attachments: Attachment[], 
//   uploadTask: Promise,
//   thoughts: Array,
//   textResponse: string
// }

// 9. Update UI with result
const displayModelMessage: Message = {
  ...initialModelMessage,
  content: result.content,
  attachments: result.attachments as Attachment[],  // ✅ 使用 displayAttachments
  // ✅ 存储 thoughts 和 textResponse（用于前端显示）
  ...(result.thoughts && { thoughts: result.thoughts }),
  ...(result.textResponse && { textResponse: result.textResponse })
};

setMessages(prev => prev.map(msg => msg.id === modelMessageId ? displayModelMessage : msg));
// ✅ 更新 messages 状态，立即显示图片和思考过程
```

**确认**: 
- `result.attachments` 是 `displayAttachments`，包含 Base64 Data URL 或 Blob URL
- `result.thoughts` 和 `result.textResponse` 存储在 `Message` 对象中
- `setMessages` 立即更新状态，触发 UI 重新渲染

#### 步骤 5.2: ImageBackgroundEditView 从 messages 提取图片
**位置**: `frontend/components/views/ImageBackgroundEditView.tsx` line 370-381

```typescript
// ✅ Auto-select latest result logic
useEffect(() => {
  // 1. Initial Load: If no active image, pick latest from history
  if (activeAttachments.length === 0 && !activeImageUrl) {
    const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments?.length);
    if (lastUserMsg && lastUserMsg.attachments?.[0]?.url) {
      setActiveImageUrl(lastUserMsg.attachments[0].url);
    } else {
      const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
      if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
        setActiveImageUrl(lastModelMsg.attachments[0].url);
      }
    }
  }

  // 2. New Generation Complete: Auto-switch to result
  if (loadingState === 'idle' && messages.length > 0) {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.id !== lastProcessedMsgId) {
      if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
        setActiveImageUrl(lastMsg.attachments[0].url);  // ✅ 自动切换到最新结果
        setLastProcessedMsgId(lastMsg.id);
      }
    }
  }
}, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);
```

**确认**: 
- 当新的 MODEL 消息到达时，自动将 `activeImageUrl` 设置为最新结果的 URL
- 触发主画布重新渲染，显示新图片

#### 步骤 5.3: ImageBackgroundEditView 渲染图片
**位置**: `frontend/components/views/ImageBackgroundEditView.tsx` line 158-169

```typescript
{activeImageUrl ? (
  <div
    className="relative shadow-2xl group transition-transform duration-75 ease-out"
    style={canvasStyle}
  >
    <img
      src={activeImageUrl}  // ✅ 使用 Base64 Data URL 或 Blob URL
      className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
      style={{ maxHeight: '80vh', maxWidth: '80vw' }}
      alt="Main Canvas"
    />
  </div>
) : (
  // 空状态
)}
```

**确认**: 
- `activeImageUrl` 是 Base64 Data URL 或 Blob URL，可以直接在 `<img src={activeImageUrl}>` 中使用
- 图片立即显示，无需等待上传完成

#### 步骤 5.4: ImageBackgroundEditView 显示思考过程
**位置**: `frontend/components/views/ImageBackgroundEditView.tsx` line 308-355

```typescript
// ✅ 流式输出思考过程（打字效果）
useEffect(() => {
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  if (!lastMessage) {
    setDisplayedThinkingContent('');
    return;
  }
  
  // ✅ 合并 thoughts 和 textResponse 的内容
  const thoughts = lastMessage?.thoughts || [];
  const textResponse = lastMessage?.textResponse;
  const thinkingParts: string[] = [];
  thoughts.forEach((thought) => {
    if (thought.type === 'text') {
      thinkingParts.push(thought.content);
    } else {
      thinkingParts.push('[图片思考过程]');
    }
  });
  if (textResponse) {
    thinkingParts.push(`\n\n💬 AI 响应：\n${textResponse}`);
  }
  const fullContent = thinkingParts.join('\n\n');
  
  // ✅ 流式输出：逐步显示思考内容（打字效果）
  if (loadingState === 'idle') {
    setDisplayedThinkingContent(fullContent);
  } else {
    // 逐步显示内容
    const chunkSize = 5;
    const nextLength = Math.min(currentLength + chunkSize, targetLength);
    setTimeout(() => {
      setDisplayedThinkingContent(fullContent.substring(0, nextLength));
    }, 30);
  }
}, [messages, loadingState]);
```

**确认**: 
- `thoughts` 和 `textResponse` 从 `Message` 对象中提取
- 使用 `ThinkingBlock` 组件显示思考过程（打字效果）
- 在 sidebar 中显示，用户可以展开/折叠

#### 步骤 5.5: Sidebar 历史显示
**位置**: `frontend/components/views/ImageBackgroundEditView.tsx` line 402-495

```typescript
const sidebarContent = useMemo(() => (
  <div ref={scrollRef} className="flex-1 p-4 space-y-6 overflow-y-auto custom-scrollbar">
    {messages.map((msg) => {
      // ✅ 过滤空占位符
      const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
      if (isPlaceholder) return null;

      return (
        <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
          {/* 消息内容 */}
          <div className={`p-3 rounded-2xl ...`}>
            {msg.content && <p className="mb-2">{msg.content}</p>}
            {msg.attachments?.filter(att => att.url && att.url.length > 0).map((att, idx) => (
              <div
                key={idx}
                onClick={() => setActiveImageUrl(att.url || null)}  // ✅ 点击缩略图切换主画布图片
                className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === att.url ? 'ring-2 ring-indigo-500 border-transparent' : 'border-slate-700 hover:border-slate-500'}`}
              >
                <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
              </div>
            ))}
          </div>
        </div>
      );
    })}
    
    {/* ✅ 显示思考过程 */}
    {loadingState !== 'idle' && displayedThinkingContent && (
      <div className="mt-2">
        <ThinkingBlock
          content={displayedThinkingContent}
          isOpen={isThinkingOpen}
          onToggle={() => setIsThinkingOpen(!isThinkingOpen)}
          isComplete={isThinkingComplete}
        />
      </div>
    )}
  </div>
), [messages, loadingState, activeModelConfig?.name, activeImageUrl, activeAttachments, displayedThinkingContent, isThinkingOpen]);
```

**确认**: 
- Sidebar 显示所有消息的缩略图
- 点击缩略图可以切换主画布显示的图片
- 显示思考过程（通过 `ThinkingBlock` 组件）

#### 步骤 5.6: 异步上传完成后更新数据库
**位置**: `frontend/hooks/useChat.ts` line 157-179

```typescript
// 10. Handle upload task (if any)
if (result.uploadTask) {
    result.uploadTask.then(({ dbAttachments, dbUserAttachments }) => {
        // ✅ 上传完成后，dbAttachments 包含云存储 URL
        const dbModelMessage: Message = {
            ...initialModelMessage,
            content: result.content,
            attachments: dbAttachments as Attachment[]  // ✅ 使用云存储 URL
        };

        const dbMessages = [...];
        updateSessionMessages(currentSessionId, dbMessages);  // ✅ 保存到数据库
    });
}
```

**确认**: 
- 上传任务在后台异步执行
- 完成后更新数据库，使用云存储 URL 替换临时 URL

## 关键发现

### 1. 附件传递链路（完整）

**前端附件处理**:
1. ✅ `ImageBackgroundEditView.handleSend` 调用 `processUserAttachments`
2. ✅ `processUserAttachments` 实现 CONTINUITY LOGIC（无新上传时使用画布图片）
3. ✅ `ImageEditHandler.doExecute` 将 `attachments` 转换为 `referenceImages` 字典
4. ✅ `llmService.editImage` 传递 `referenceImages` 和 `mode='image-background-edit'`
5. ✅ `UnifiedProviderClient.editImage` 将 `referenceImages` 转换为 `attachments` 数组（包含 `role` 字段）
6. ✅ `UnifiedProviderClient.executeMode` 将 `attachments` 发送到后端

**后端附件处理**:
1. ✅ 后端路由 `/api/modes/google/image-background-edit` 接收 `requestBody.attachments`
2. ✅ `convert_attachments_to_reference_images` 将 `attachments` 转换为 `reference_images` 字典
3. ✅ 根据 `attachment.role` 设置键名（'raw', 'mask', 等）
4. ✅ 调用 `service.edit_image(**params)`，包含 `mode='image-background-edit'`
5. ✅ `GoogleService.edit_image` 委托给 `ImageEditCoordinator.edit_image`
6. ✅ `ImageEditCoordinator` 根据 `mode` 路由到对应的编辑服务

### 2. 图片显示链路（完整）

**后端返回**:
1. ✅ 编辑服务返回 `List[Dict[str, Any]]`，格式: `[{"url": "data:image/png;base64,...", "mimeType": "image/png", "thoughts": [...], "text": "..."}]`
2. ✅ 后端路由返回 `ModeResponse(success=True, data=results)`

**前端处理**:
1. ✅ `UnifiedProviderClient.executeMode` 解析响应，返回 `data.data`（即 results 列表）
2. ✅ `llmService.editImage` 返回 `ImageGenerationResult[]`
3. ✅ `ImageEditHandler.doExecute` 提取 `thoughts` 和 `textResponse`，调用 `processMediaResult` 处理每个结果
4. ✅ `processMediaResult` 创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
5. ✅ `ImageEditHandler` 返回 `HandlerResult`，包含 `attachments`, `thoughts`, `textResponse`
6. ✅ `useChat.sendMessage` 更新 `messages` 状态，将 `displayAttachments`, `thoughts`, `textResponse` 添加到 `modelMessage`
7. ✅ `ImageBackgroundEditView` 从 `messages` 中提取 MODEL 消息的 `attachments`
8. ✅ `ImageBackgroundEditView` 自动切换到最新结果，渲染 `<img src={activeImageUrl}>`，立即显示图片
9. ✅ `ImageBackgroundEditView` 显示思考过程（通过 `ThinkingBlock` 组件）
10. ✅ 异步上传任务在后台执行，完成后更新数据库

### 3. CONTINUITY LOGIC（关键特性）

**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 786-942

**逻辑**:
- 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），`processUserAttachments` 会自动使用画布上的图片
- 尝试从历史消息中查找匹配的附件（通过 URL 匹配）
- 如果找到，复用附件的 ID 和其他信息，查询后端获取云存储 URL
- 如果未找到，根据 URL 类型（Base64/Blob/HTTP）创建新附件

**优势**:
- 用户可以在画布上查看结果，然后直接发送新的编辑指令，无需重新上传图片
- 支持连续编辑工作流

### 4. 思考过程显示（关键特性）

**位置**: `frontend/components/views/ImageBackgroundEditView.tsx` line 308-355

**逻辑**:
- `ImageEditHandler` 从后端返回的 `results` 中提取 `thoughts` 和 `textResponse`
- 存储在 `HandlerResult` 中，传递给 `useChat.sendMessage`
- `useChat.sendMessage` 将 `thoughts` 和 `textResponse` 存储在 `Message` 对象中
- `ImageBackgroundEditView` 从 `Message` 对象中提取，使用 `ThinkingBlock` 组件显示
- 支持流式输出（打字效果）

## 问题定位

### 可能的问题

1. **附件未正确传递**:
   - **位置**: `processUserAttachments` 或 `ImageEditHandler.doExecute`
   - **验证**: 检查 `finalAttachments` 和 `referenceImages` 的值

2. **模式参数未传递**:
   - **位置**: `UnifiedProviderClient.editImage` 或后端路由
   - **验证**: 检查 `mode` 参数是否传递到后端

3. **思考过程未显示**:
   - **位置**: `ImageEditHandler.doExecute` 或 `ImageBackgroundEditView` 的思考过程显示逻辑
   - **验证**: 检查 `thoughts` 和 `textResponse` 是否从后端返回并正确存储

## 需要检查的关键代码位置

### 前端
1. **ImageBackgroundEditView.tsx line 383-398**: `handleSend` 中调用 `processUserAttachments`
2. **ImageEditHandlerClass.ts line 10-68**: `doExecute` 中处理附件和调用 `llmService.editImage`
3. **llmService.ts line 240-329**: `editImage` 中路由到 provider
4. **UnifiedProviderClient.ts line 488-551**: `editImage` 中转换为请求格式
5. **UnifiedProviderClient.ts line 378-443**: `executeMode` 中构建请求体

### 后端
1. **backend/app/routers/core/modes.py line 150-305**: 路由接收请求和处理
2. **backend/app/services/gemini/google_service.py line 407-443**: `edit_image` 委托给 coordinator
3. **backend/app/services/gemini/image_edit_coordinator.py**: 根据 `mode` 路由到对应服务

## 调试步骤

1. **在 ImageBackgroundEditView.handleSend 中添加日志**:
```typescript
console.log('[ImageBackgroundEditView.handleSend] activeImageUrl:', activeImageUrl);
console.log('[ImageBackgroundEditView.handleSend] attachments:', attachments);
console.log('[ImageBackgroundEditView.handleSend] finalAttachments:', finalAttachments);
```

2. **在 ImageEditHandler.doExecute 中添加日志**:
```typescript
console.log('[ImageEditHandler.doExecute] context.attachments:', context.attachments);
console.log('[ImageEditHandler.doExecute] referenceImages:', referenceImages);
console.log('[ImageEditHandler.doExecute] mode:', context.mode);
```

3. **在 UnifiedProviderClient.executeMode 中添加日志**:
```typescript
console.log('[UnifiedProviderClient.executeMode] Request body:', JSON.stringify(requestBody, null, 2));
```

4. **在后端路由中添加日志**:
```python
logger.info(f"[Modes] Request: provider={provider}, mode={mode}, attachments={len(request_body.attachments)}")
logger.info(f"[Modes] Reference images: {list(reference_images.keys())}")
```

## 结论

**前端附件传递链路完整**，所有附件都应该被传递到后端。**图片显示链路也完整**，图片应该能够立即显示。**思考过程显示链路完整**，思考过程和文本响应应该能够正确显示。

**关键特性**:
1. ✅ **CONTINUITY LOGIC**: 支持连续编辑工作流，无需重复上传图片
2. ✅ **思考过程显示**: 显示 AI 的思考过程和文本响应
3. ✅ **自动切换结果**: 新结果生成后自动切换到主画布显示

**建议**:
- 在前端和后端关键位置添加日志，确认附件和参数在每个步骤的值
- 检查思考过程是否正确从后端返回并显示
