# ImageMaskEditView 完整流程分析：从用户点击发送到UI显示图片

## 问题描述
分析 `image-mask-edit` 模式下，用户点击发送按钮后，参数和附件如何传递到后端，以及后端返回的图片如何在前端UI中显示。

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

#### 步骤 1.2: ImageMaskEditView.handleSend 被调用
**位置**: `frontend/components/views/ImageMaskEditView.tsx` line 383-398

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
    // ✅ 固定使用 image-mask-edit 模式
    onSend(text, options, finalAttachments, editMode);  // editMode = 'image-mask-edit'
  } catch (error) {
    console.error('[ImageMaskEditView] handleSend 处理附件失败:', error);
    showError('处理附件失败，请重试');
    return;
  }
}, [activeImageUrl, messages, currentSessionId, onSend, editMode, showError]);
```

**关键逻辑**:
- **CONTINUITY LOGIC**: 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），`processUserAttachments` 会自动使用画布上的图片
- **固定模式**: 始终使用 `editMode = 'image-mask-edit'`，忽略传入的 `mode` 参数
- **Mask 编辑模式**: 此模式需要两个附件：第一个是原图（raw），第二个是遮罩（mask）

#### 步骤 1.3: processUserAttachments 处理附件（CONTINUITY LOGIC）
**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 786-942

**处理流程**（与 ImageBackgroundEditView 相同）:
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
  mode: AppMode,  // ✅ 'image-mask-edit'
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
  
  // ✅ 关键：检查是否有 mask（第二个附件作为 mask）
  if (context.attachments.length > 1) {
    // ✅ 简单判断：如果模式是 image-mask-edit，第二个附件作为 mask
    if (context.mode === 'image-mask-edit') {
      referenceImages.mask = context.attachments[1];  // ✅ 第二个附件作为 mask
    }
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
    referenceImages,  // ✅ { raw: Attachment, mask: Attachment }
    context.mode,  // ✅ 'image-mask-edit'
    editOptions
  );
  // ...
}
```

**关键处理**:
- 将 `attachments` 数组转换为 `referenceImages` 字典格式: `{ raw: Attachment, mask?: Attachment }`
- **关键**: 对于 `image-mask-edit` 模式，第二个附件（`context.attachments[1]`）作为 `mask`
- 如果有 HTTP URL，直接传递 URL；否则转换为 Base64

#### 步骤 2.4: llmService.editImage 路由到 provider
**位置**: `frontend/services/llmService.ts` line 240-329

```typescript
public async editImage(
  prompt: string, 
  referenceImages: Record<string, Attachment>,
  mode?: AppMode,  // ✅ 'image-mask-edit'
  options?: ChatOptions
): Promise<ImageGenerationResult[]> {
  // ✅ 验证输入
  if (!referenceImages.raw) {
    throw new Error('Raw reference image is required for image editing');
  }
  
  // ✅ 路由 2: Mask 编辑模式（image-mask-edit）- 必须有 mask
  if (mode === 'image-mask-edit') {
    if (!referenceImages.mask) {
      throw new Error('image-mask-edit mode requires a mask in referenceImages');
    }
    if (this.providerId === 'google') {
      const result = await this.callGoogleInpaintAPI(prompt, referenceImages);
      return [result];
    }
  }
  
  // ✅ 合并 options
  const finalOptions = options ? { ...this._cachedOptions, ...options } : this._cachedOptions;
  
  // ✅ 调用 UnifiedProviderClient.editImage
  if ('id' in provider && typeof (provider as any).id === 'string') {
    return (provider as UnifiedProviderClient).editImage(
      this._cachedModelConfig.id,
      prompt,
      referenceImages,  // ✅ { raw: Attachment, mask: Attachment }
      finalOptions,
      this.baseUrl,
      mode  // ✅ 'image-mask-edit'
    );
  }
  // ...
}
```

**确认**: 
- `mode = 'image-mask-edit'` 传递给 `UnifiedProviderClient.editImage`
- `referenceImages = { raw: Attachment, mask: Attachment }` 传递给 provider
- 如果 provider 是 'google'，可能使用 `callGoogleInpaintAPI`（旧方法）

#### 步骤 2.5: UnifiedProviderClient.editImage 转换为请求格式
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 488-551

```typescript
async editImage(
  modelId: string,
  prompt: string,
  referenceImages: Record<string, any>,  // ✅ { raw: Attachment, mask: Attachment }
  options: ChatOptions,
  baseUrl: string,
  mode?: string  // ✅ 'image-mask-edit'
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
    mode || 'image-edit',  // ✅ 'image-mask-edit'
    modelId,
    prompt,
    attachments,  // ✅ 包含 role='raw' 和 role='mask' 的附件
    { ...options, baseUrl: baseUrl || options.baseUrl }
  );
  
  return Array.isArray(data) ? data : [];
}
```

**确认**: 
- `referenceImages` 转换为 `attachments` 数组，每个附件包含 `role` 字段（'raw' 或 'mask'）
- 调用 `executeMode('image-mask-edit', ...)`

#### 步骤 2.6: UnifiedProviderClient.executeMode 构建请求体
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 378-443

```typescript
async executeMode(
  mode: string,  // ✅ 'image-mask-edit'
  modelId: string,
  prompt: string,
  attachments: Attachment[] = [],  // ✅ 包含 role='raw' 和 role='mask' 的附件
  options: Partial<ChatOptions> = {},
  extra: Record<string, any> = {}
): Promise<any> {
  const requestBody = {
    modelId,
    prompt,
    attachments,  // ✅ 包含 role='raw' 和 role='mask' 的附件
    options: {
      ...options
    },
    extra
  };
  
  const response = await fetch(`/api/modes/${this.id}/${mode}`, {  // ✅ '/api/modes/google/image-mask-edit'
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
- 请求发送到 `/api/modes/google/image-mask-edit`
- `attachments` 包含 `role='raw'` 和 `role='mask'` 的附件

### 阶段 3: 后端处理 → 生成图片

#### 步骤 3.1: 后端路由接收请求
**位置**: `backend/app/routers/core/modes.py` line 150-305

```python
@router.post("/{provider}/{mode}")  # ✅ '/api/modes/google/image-mask-edit'
async def handle_mode(
    provider: str,  # ✅ 'google'
    mode: str,      # ✅ 'image-mask-edit'
    request_body: ModeRequest,
    ...
):
    # ✅ 1. 获取凭证
    api_key, api_url = await get_provider_credentials(...)
    
    # ✅ 2. 创建提供商服务
    service = ProviderFactory.create(provider=provider, ...)
    
    # ✅ 3. 根据 mode 获取服务方法名
    method_name = get_service_method(mode)  # ✅ 'image-mask-edit' -> 'edit_image'
    
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
        # ✅ reference_images = { 'raw': base64_image, 'mask': base64_mask }
        if reference_images:
            params["reference_images"] = reference_images
    
    # ✅ 7. 对于 edit_image 方法，传递 mode 参数
    if method_name == "edit_image":
        params["mode"] = mode  # ✅ 'image-mask-edit'
    
    # ✅ 8. 调用服务方法
    result = await method(**params)  # ✅ service.edit_image(**params)
    
    # ✅ 9. 返回响应
    return ModeResponse(success=True, data=result, ...)
```

**关键处理**:
- `convert_attachments_to_reference_images` 将 `attachments` 数组转换为 `reference_images` 字典
- 根据 `attachment.role` 设置键名（'raw', 'mask'）
- `params["mode"] = 'image-mask-edit'` 传递给 `edit_image` 方法

#### 步骤 3.2: GoogleService.edit_image 委托给 ImageEditCoordinator
**位置**: `backend/app/services/gemini/google_service.py` line 407-443

```python
async def edit_image(
    self,
    prompt: str,
    model: str,
    reference_images: Dict[str, Any],  # ✅ { 'raw': base64_image, 'mask': base64_mask }
    mode: Optional[str] = None,  # ✅ 'image-mask-edit'
    **kwargs
) -> List[Dict[str, Any]]:
    # ✅ 委托给 ImageEditCoordinator
    return await self.image_edit_coordinator.edit_image(
        prompt=prompt,
        model=model,
        reference_images=reference_images,
        mode=mode,  # ✅ 'image-mask-edit'
        sdk_initializer=self.sdk_initializer,
        chat_session_manager=self.chat_session_manager,
        **kwargs
    )
```

**确认**: 
- `mode='image-mask-edit'` 传递给 `ImageEditCoordinator.edit_image`
- `reference_images` 包含 'raw' 和 'mask'

#### 步骤 3.3: ImageEditCoordinator.edit_image 根据 mode 路由
**位置**: `backend/app/services/gemini/image_edit_coordinator.py`

**路由逻辑**:
- `mode='image-mask-edit'` → 路由到 `ImageEditCoordinator` 的 Vertex AI Imagen 实现
- 调用 Vertex AI Imagen 的 `edit_image` API，使用 `edit_mode='mask'`
- 使用提供的 mask 进行编辑

#### 步骤 3.4: 后端返回图片数据
**位置**: `backend/app/services/gemini/image_edit_vertex_ai.py`

**返回格式**: `List[Dict[str, Any]]`，每个元素包含:
- `url`: Base64 Data URL (例如: `"data:image/png;base64,..."`)
- `mimeType`: MIME 类型 (例如: `"image/png"`)

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

#### 步骤 4.3: ImageEditHandler.doExecute 处理结果
**位置**: `frontend/hooks/handlers/ImageEditHandlerClass.ts` line 70-145

```typescript
// ✅ 使用统一的媒体处理函数
const processed = await Promise.all(
  results.map(res => processMediaResult(res, context, 'edited'))
);
// ✅ processed: [{ displayAttachment: Attachment, dbAttachmentPromise: Promise<Attachment> }, ...]

const displayAttachments: Attachment[] = processed.map(p => p.displayAttachment);
// ✅ displayAttachments: Attachment[]，用于立即显示

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
  content: `Edited images for: "${context.text}"`,
  attachments: displayAttachments,  // ✅ 用于立即显示
  uploadTask: uploadTask()  // ✅ 异步上传任务
};
```

**处理逻辑**（与 ImageBackgroundEditView 相同）:
1. **processMediaResult**: 处理每个图片结果，创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
2. **uploadTask**: 异步上传任务，处理 AI 生成的图片和用户上传的附件

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
//   uploadTask: Promise
// }

// 9. Update UI with result
const displayModelMessage: Message = {
  ...initialModelMessage,
  content: result.content,
  attachments: result.attachments as Attachment[],  // ✅ 使用 displayAttachments
};

setMessages(prev => prev.map(msg => msg.id === modelMessageId ? displayModelMessage : msg));
// ✅ 更新 messages 状态，立即显示图片
```

**确认**: 
- `result.attachments` 是 `displayAttachments`，包含 Base64 Data URL 或 Blob URL
- `setMessages` 立即更新状态，触发 UI 重新渲染

#### 步骤 5.2: ImageMaskEditView 从 messages 提取图片
**位置**: `frontend/components/views/ImageMaskEditView.tsx` line 357-381

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

#### 步骤 5.3: ImageMaskEditView 渲染图片
**位置**: `frontend/components/views/ImageMaskEditView.tsx` line 158-169

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

#### 步骤 5.4: ImageMaskEditView 显示思考过程
**位置**: `frontend/components/views/ImageMaskEditView.tsx` line 308-355

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

## 关键发现

### 1. Mask 编辑模式特性（关键特性）

**位置**: `backend/app/services/gemini/image_edit_vertex_ai.py`

**逻辑**:
- Mask 编辑模式需要两个附件：原图（raw）和遮罩（mask）
- 遮罩用于指定要编辑的区域（白色区域将被编辑，黑色区域保持不变）
- 使用 Vertex AI Imagen 的 `edit_image` API，`edit_mode='mask'`
- 支持精确控制编辑区域

**优势**:
- 支持精确控制编辑区域
- 支持复杂编辑任务（例如：替换特定区域的内容）

### 2. 附件传递链路（完整）

**前端附件处理**:
1. ✅ `ImageMaskEditView.handleSend` 调用 `processUserAttachments`
2. ✅ `processUserAttachments` 实现 CONTINUITY LOGIC（无新上传时使用画布图片）
3. ✅ `ImageEditHandler.doExecute` 将 `attachments` 转换为 `referenceImages` 字典
4. ✅ **关键**: 对于 `image-mask-edit` 模式，第二个附件（`context.attachments[1]`）作为 `mask`
5. ✅ `llmService.editImage` 传递 `referenceImages = { raw: Attachment, mask: Attachment }` 和 `mode='image-mask-edit'`
6. ✅ `UnifiedProviderClient.editImage` 将 `referenceImages` 转换为 `attachments` 数组（包含 `role='raw'` 和 `role='mask'`）
7. ✅ `UnifiedProviderClient.executeMode` 将 `attachments` 发送到后端

**后端附件处理**:
1. ✅ 后端路由 `/api/modes/google/image-mask-edit` 接收 `requestBody.attachments`
2. ✅ `convert_attachments_to_reference_images` 将 `attachments` 转换为 `reference_images` 字典
3. ✅ 根据 `attachment.role` 设置键名（'raw', 'mask'）
4. ✅ 调用 `service.edit_image(**params)`，包含 `mode='image-mask-edit'`
5. ✅ `GoogleService.edit_image` 委托给 `ImageEditCoordinator.edit_image`
6. ✅ `ImageEditCoordinator` 根据 `mode` 路由到 Vertex AI Imagen 实现

### 3. 图片显示链路（完整）

**后端返回**:
1. ✅ Vertex AI Imagen 返回 `List[Dict[str, Any]]`，格式: `[{"url": "data:image/png;base64,...", "mimeType": "image/png"}]`
2. ✅ 后端路由返回 `ModeResponse(success=True, data=results)`

**前端处理**:
1. ✅ `UnifiedProviderClient.executeMode` 解析响应，返回 `data.data`（即 results 列表）
2. ✅ `llmService.editImage` 返回 `ImageGenerationResult[]`
3. ✅ `ImageEditHandler.doExecute` 调用 `processMediaResult` 处理每个结果
4. ✅ `processMediaResult` 创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
5. ✅ `ImageEditHandler` 返回 `HandlerResult`，包含 `attachments`
6. ✅ `useChat.sendMessage` 更新 `messages` 状态，将 `displayAttachments` 添加到 `modelMessage`
7. ✅ `ImageMaskEditView` 从 `messages` 中提取 MODEL 消息的 `attachments`
8. ✅ `ImageMaskEditView` 自动切换到最新结果，渲染 `<img src={activeImageUrl}>`，立即显示图片
9. ✅ 异步上传任务在后台执行，完成后更新数据库

### 4. CONTINUITY LOGIC（关键特性）

**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 786-942

**逻辑**（与 ImageBackgroundEditView 相同）:
- 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），`processUserAttachments` 会自动使用画布上的图片
- 尝试从历史消息中查找匹配的附件（通过 URL 匹配）
- 如果找到，复用附件的 ID 和其他信息，查询后端获取云存储 URL
- 如果未找到，根据 URL 类型（Base64/Blob/HTTP）创建新附件

**优势**:
- 用户可以在画布上查看结果，然后直接发送新的编辑指令，无需重新上传图片
- 支持连续编辑工作流

## 问题定位

### 可能的问题

1. **Mask 附件未正确传递**:
   - **位置**: `ImageEditHandler.doExecute` 中的 mask 处理逻辑
   - **验证**: 检查 `context.attachments.length` 和 `referenceImages.mask` 的值

2. **附件顺序错误**:
   - **位置**: `ImageMaskEditView` 的附件上传逻辑
   - **验证**: 检查第一个附件是否是原图（raw），第二个附件是否是遮罩（mask）

3. **模式参数未传递**:
   - **位置**: `UnifiedProviderClient.editImage` 或后端路由
   - **验证**: 检查 `mode` 参数是否传递到后端

## 需要检查的关键代码位置

### 前端
1. **ImageMaskEditView.tsx line 383-398**: `handleSend` 中调用 `processUserAttachments`
2. **ImageEditHandlerClass.ts line 10-68**: `doExecute` 中处理附件和调用 `llmService.editImage`（特别是 mask 的处理）
3. **llmService.ts line 240-329**: `editImage` 中路由到 provider
4. **UnifiedProviderClient.ts line 488-551**: `editImage` 中转换为请求格式
5. **UnifiedProviderClient.ts line 378-443**: `executeMode` 中构建请求体

### 后端
1. **backend/app/routers/core/modes.py line 150-305**: 路由接收请求和处理
2. **backend/app/services/gemini/google_service.py line 407-443**: `edit_image` 委托给 coordinator
3. **backend/app/services/gemini/image_edit_coordinator.py**: 根据 `mode` 路由到对应服务
4. **backend/app/services/gemini/image_edit_vertex_ai.py**: Vertex AI Imagen 实现

## 调试步骤

1. **在 ImageMaskEditView.handleSend 中添加日志**:
```typescript
console.log('[ImageMaskEditView.handleSend] activeImageUrl:', activeImageUrl);
console.log('[ImageMaskEditView.handleSend] attachments:', attachments);
console.log('[ImageMaskEditView.handleSend] finalAttachments:', finalAttachments);
console.log('[ImageMaskEditView.handleSend] finalAttachments.length:', finalAttachments.length);
```

2. **在 ImageEditHandler.doExecute 中添加日志**:
```typescript
console.log('[ImageEditHandler.doExecute] context.attachments:', context.attachments);
console.log('[ImageEditHandler.doExecute] context.attachments.length:', context.attachments.length);
console.log('[ImageEditHandler.doExecute] context.mode:', context.mode);
console.log('[ImageEditHandler.doExecute] referenceImages:', referenceImages);
console.log('[ImageEditHandler.doExecute] referenceImages.mask:', referenceImages.mask);
```

3. **在 UnifiedProviderClient.executeMode 中添加日志**:
```typescript
console.log('[UnifiedProviderClient.executeMode] Request body:', JSON.stringify(requestBody, null, 2));
console.log('[UnifiedProviderClient.executeMode] Attachments with roles:', requestBody.attachments.map(a => ({ role: a.role, id: a.id })));
```

## 结论

**前端附件传递链路完整**，所有附件（包括 mask）都应该被传递到后端。**图片显示链路也完整**，图片应该能够立即显示。

**关键特性**:
1. ✅ **Mask 编辑模式**: 需要两个附件（原图和遮罩），支持精确控制编辑区域
2. ✅ **CONTINUITY LOGIC**: 支持连续编辑工作流，无需重复上传图片
3. ✅ **思考过程显示**: 显示 AI 的思考过程（如果后端返回）
4. ✅ **自动切换结果**: 新结果生成后自动切换到主画布显示

**建议**:
- 在前端和后端关键位置添加日志，确认附件（特别是 mask）在每个步骤的值
- 检查附件顺序是否正确（第一个是 raw，第二个是 mask）
- 检查 mask 是否正确传递到后端
