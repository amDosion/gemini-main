# ImageExpandView 完整流程分析：从用户点击发送到UI显示图片

## 问题描述
分析 `image-outpainting` 模式下，用户点击发送按钮后，参数和附件如何传递到后端，以及后端返回的图片如何在前端UI中显示。

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

#### 步骤 1.2: ImageExpandView.handleSend 被调用
**位置**: `frontend/components/views/ImageExpandView.tsx` line 328-350

**关键代码**:
```typescript
const handleSend = async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
  try {
    console.log('========== [ImageExpandView] handleSend 开始 ==========');
    console.log('[handleSend] 用户上传的附件数量:', attachments.length);

    // ✅ 使用统一的附件处理函数（CONTINUITY LOGIC）
    const finalAttachments = await processUserAttachments(
      attachments,        // 用户上传的附件（可能为空）
      activeImageUrl,    // 当前画布上的图片 URL
      messages,          // 消息历史
      currentSessionId,  // 会话 ID
      'expand'           // 文件前缀
    );

    console.log('[handleSend] 最终附件数量:', finalAttachments.length);
    console.log('========== [ImageExpandView] handleSend 结束 ==========');
    onSend(text, options, finalAttachments, mode);  // ✅ mode = 'image-outpainting'
  } catch (error) {
    console.error('[ImageExpandView] handleSend 处理附件失败:', error);
    showError('处理附件失败，请重试');
    return;
  }
};
```

**关键逻辑**:
- **CONTINUITY LOGIC**: 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），`processUserAttachments` 会自动使用画布上的图片
- **扩图模式**: 使用 `mode = 'image-outpainting'`，此模式不需要文本提示词（`text` 可以为空）

#### 步骤 1.3: processUserAttachments 处理附件（CONTINUITY LOGIC）
**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 786-942

**处理流程**（与 ImageBackgroundEditView 相同）:
1. **如果用户没有上传新附件，但画布上有图片**:
   - 调用 `prepareAttachmentForApi(activeImageUrl, messages, sessionId, 'expand')`
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
  mode: AppMode,  // ✅ 'image-outpainting'
  currentModel: ModelConfig,
  protocol: 'google' | 'openai'
) => {
  // ...
  const enhancedOptions = options.enableResearch
    ? { ...options, enableSearch: true }
    : options;
  llmService.startNewChat(contextHistory, currentModel, enhancedOptions);
  // ...
  const handler = strategyRegistry.getHandler(mode);  // ✅ 返回 ImageOutpaintingHandler
  const result = await handler.execute(context);
  // ...
};
```

**确认**: 
- `mode` 传递给 `strategyRegistry.getHandler(mode)`，返回 `ImageOutpaintingHandler`
- `attachments` 传递给 `handler.execute(context)`

#### 步骤 2.3: ImageOutpaintingHandler.doExecute 处理附件
**位置**: `frontend/hooks/handlers/AllHandlerClasses.ts` line 8-33

```typescript
export class ImageOutpaintingHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    if (!context.attachments || context.attachments.length === 0) {
      throw new Error('ImageOutpaintingHandler requires an attachment.');
    }
    
    // ✅ 调用 llmService.outPaintImage，只传递第一个附件
    const result = await llmService.outPaintImage(context.attachments[0]);
    const results = [result];

    // ✅ 使用统一的媒体处理函数
    const processed = await Promise.all(
      results.map(res => processMediaResult(res, context, 'outpainted'))
    );
    
    const displayAttachments = processed.map(p => p.displayAttachment);
    const uploadTask = async () => ({
      dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise)),
      dbUserAttachments: context.attachments
    });

    return {
      content: 'Image expanded.',
      attachments: displayAttachments,
      uploadTask: uploadTask(),
    };
  }
}
```

**关键处理**:
- 只需要第一个附件（`context.attachments[0]`）
- 调用 `llmService.outPaintImage(referenceImage)`，不传递 `prompt` 和 `options`
- 使用 `processMediaResult` 处理结果，文件前缀为 `'outpainted'`

#### 步骤 2.4: llmService.outPaintImage 路由到 provider
**位置**: `frontend/services/llmService.ts` line 340-382

```typescript
public async outPaintImage(referenceImage: Attachment): Promise<ImageGenerationResult> {
  // ✅ 检查配置
  if (!this.isConfigured()) {
    throw new Error('Provider not configured. Please configure a provider in Settings → Profiles.');
  }

  if (!this._cachedModelConfig) {
    throw new Error('No model selected');
  }

  // ✅ 验证输入
  if (!referenceImage) {
    throw new Error('Reference image is required for outpainting');
  }

  // ✅ 尝试使用当前 provider 的 outPaintImage 方法
  if (this.currentProvider && 'outPaintImage' in this.currentProvider) {
    return this.currentProvider.outPaintImage(referenceImage, this._cachedOptions, this.apiKey, this.baseUrl);
  }
  
  // ✅ 回退：使用 UnifiedProviderClient('tongyi')，通过 executeMode('image-outpainting', ...) 统一处理
  const dashscopeKey = await configService.getDashScopeKey();
  if (dashscopeKey) {
    const tongyiProvider = LLMFactory.getProvider('openai', 'tongyi');
    if (tongyiProvider.outPaintImage) {
      return tongyiProvider.outPaintImage(referenceImage, this._cachedOptions, dashscopeKey, dsUrl);
    }
  }
  
  throw new Error("Out-Painting not supported by current provider.");
}
```

**确认**: 
- 调用 `provider.outPaintImage(referenceImage, options, apiKey, baseUrl)`
- 如果当前 provider 不支持，回退到 `UnifiedProviderClient('tongyi')`

#### 步骤 2.5: UnifiedProviderClient.outPaintImage 转换为请求格式
**位置**: `frontend/services/providers/UnifiedProviderClient.ts`

**实现**（如果存在）:
```typescript
async outPaintImage(
  referenceImage: Attachment,
  options: ChatOptions,
  apiKey: string,
  baseUrl: string
): Promise<ImageGenerationResult> {
  // ✅ 调用 executeMode
  const data = await this.executeMode(
    'image-outpainting',
    this._cachedModelConfig.id,
    '',  // ✅ prompt 为空（扩图不需要提示词）
    [referenceImage],  // ✅ 附件数组
    { ...options, baseUrl: baseUrl || options.baseUrl }
  );
  
  return Array.isArray(data) ? data[0] : data;
}
```

**确认**: 
- 调用 `executeMode('image-outpainting', modelId, '', [referenceImage], options)`
- `prompt` 为空字符串（扩图不需要提示词）

#### 步骤 2.6: UnifiedProviderClient.executeMode 构建请求体
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 378-443

```typescript
async executeMode(
  mode: string,  // ✅ 'image-outpainting'
  modelId: string,
  prompt: string,  // ✅ 空字符串
  attachments: Attachment[] = [],  // ✅ 包含一个附件
  options: Partial<ChatOptions> = {},
  extra: Record<string, any> = {}
): Promise<any> {
  const requestBody = {
    modelId,
    prompt,  // ✅ 空字符串
    attachments,  // ✅ 包含一个附件
    options: {
      ...options
    },
    extra
  };
  
  const response = await fetch(`/api/modes/${this.id}/${mode}`, {  // ✅ '/api/modes/tongyi/image-outpainting'
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
- 请求发送到 `/api/modes/tongyi/image-outpainting`（通常使用 Tongyi 提供商的扩图功能）
- `attachments` 包含一个附件（要扩展的图片）
- `prompt` 为空字符串

### 阶段 3: 后端处理 → 生成图片

#### 步骤 3.1: 后端路由接收请求
**位置**: `backend/app/routers/core/modes.py` line 150-305

```python
@router.post("/{provider}/{mode}")  # ✅ '/api/modes/tongyi/image-outpainting'
async def handle_mode(
    provider: str,  # ✅ 'tongyi'
    mode: str,      # ✅ 'image-outpainting'
    request_body: ModeRequest,
    ...
):
    # ✅ 1. 获取凭证
    api_key, api_url = await get_provider_credentials(...)
    
    # ✅ 2. 创建提供商服务
    service = ProviderFactory.create(provider=provider, ...)
    
    # ✅ 3. 根据 mode 获取服务方法名
    method_name = get_service_method(mode)  # ✅ 'image-outpainting' -> 'expand_image'
    
    # ✅ 4. 准备参数
    params = {
        "model": request_body.modelId,
        "prompt": request_body.prompt,  # ✅ 空字符串
    }
    
    # ✅ 5. 添加 options 中的参数
    if request_body.options:
        options_dict = request_body.options.dict(exclude_none=True)
        params.update(options_dict)
    
    # ✅ 6. 转换 attachments 为 reference_images
    if request_body.attachments:
        reference_images = convert_attachments_to_reference_images(request_body.attachments)
        # ✅ reference_images = { 'raw': base64_image }
        if reference_images:
            params["reference_images"] = reference_images
    
    # ✅ 7. 调用服务方法
    result = await method(**params)  # ✅ service.expand_image(**params)
    
    # ✅ 8. 返回响应
    return ModeResponse(success=True, data=result, ...)
```

**关键处理**:
- `convert_attachments_to_reference_images` 将 `attachments` 数组转换为 `reference_images` 字典
- 根据 `attachment.role` 设置键名（'raw'）
- 调用 `service.expand_image(**params)`

#### 步骤 3.2: TongyiService.expand_image 处理扩图
**位置**: `backend/app/services/tongyi/tongyi_service.py`

**实现**:
```python
async def expand_image(
    self,
    prompt: str,  # ✅ 空字符串
    model: str,
    reference_images: Dict[str, Any],  # ✅ { 'raw': base64_image }
    **kwargs
) -> Dict[str, Any]:
    # ✅ 委托给 ExpandService
    return await self.expand_service.expand_image(
        prompt=prompt,
        model=model,
        reference_images=reference_images,
        **kwargs
    )
```

**确认**: 委托给 `ExpandService.expand_image`。

#### 步骤 3.3: ExpandService.expand_image 调用扩图 API
**位置**: `backend/app/services/gemini/expand_service.py`

**实现**:
- 调用 DashScope API 的扩图功能
- 支持多个扩图方向（上、下、左、右、四方向）

#### 步骤 3.4: 后端返回图片数据
**位置**: `backend/app/services/gemini/expand_service.py`

**返回格式**: `Dict[str, Any]`，包含:
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

return data.data;  // ✅ 返回 data.data（即 Dict）
```

**确认**: 返回 `data.data`，即后端返回的结果字典。

#### 步骤 4.2: llmService.outPaintImage 返回结果
**位置**: `frontend/services/llmService.ts` line 360-378

```typescript
return this.currentProvider.outPaintImage(referenceImage, this._cachedOptions, this.apiKey, this.baseUrl);
// ✅ 返回 ImageGenerationResult
```

**返回类型**: `ImageGenerationResult`，包含:
- `url`: string (Base64 Data URL)
- `mimeType`: string

#### 步骤 4.3: ImageOutpaintingHandler.doExecute 处理结果
**位置**: `frontend/hooks/handlers/AllHandlerClasses.ts` line 8-33

```typescript
const result = await llmService.outPaintImage(context.attachments[0]);
const results = [result];  // ✅ 转换为数组

// ✅ 使用统一的媒体处理函数
const processed = await Promise.all(
  results.map(res => processMediaResult(res, context, 'outpainted'))
);
// ✅ processed: [{ displayAttachment: Attachment, dbAttachmentPromise: Promise<Attachment> }]

const displayAttachments = processed.map(p => p.displayAttachment);
// ✅ displayAttachments: Attachment[]，用于立即显示

const uploadTask = async () => ({
  dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise)),
  dbUserAttachments: context.attachments
});

return {
  content: 'Image expanded.',
  attachments: displayAttachments,  // ✅ 用于立即显示
  uploadTask: uploadTask()  // ✅ 异步上传任务
};
```

**处理逻辑**:
1. **processMediaResult**: 处理图片结果，创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
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

#### 步骤 5.2: ImageExpandView 从 messages 提取图片
**位置**: `frontend/components/views/ImageExpandView.tsx` line 303-326

```typescript
// ✅ Auto-select latest result logic
useEffect(() => {
  // 1. Initial Load: If no active image, pick latest from history
  if (activeAttachments.length === 0 && !activeImageUrl) {
    const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
    if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
      setActiveImageUrl(lastModelMsg.attachments[0].url);
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

#### 步骤 5.3: ImageExpandView 渲染图片
**位置**: `frontend/components/views/ImageExpandView.tsx` line 153-165

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

#### 步骤 5.4: Sidebar 历史显示
**位置**: `frontend/components/views/ImageExpandView.tsx` line 356-415

```typescript
const sidebarContent = useMemo(() => (
  <div className="flex-1 p-4 space-y-6">
    {messages.map((msg) => {
      // ✅ 过滤空占位符
      const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
      if (isPlaceholder) return null;

      return (
        <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
          {/* 消息内容 */}
          <div className={`p-3 rounded-2xl ...`}>
            {msg.content && <p className="mb-2">{msg.content}</p>}
            {msg.attachments?.map((att, idx) => {
              // ✅ 优先使用 url（永久 URL），如果没有则使用 tempUrl（临时 URL）
              const displayUrl = att.url || att.tempUrl || '';
              if (!displayUrl) return null;
              return (
                <div
                  key={idx}
                  onClick={() => setActiveImageUrl(displayUrl || null)}  // ✅ 点击缩略图切换主画布图片
                  className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === displayUrl ? 'ring-2 ring-orange-500 border-transparent' : 'border-slate-700 hover:border-slate-500'}`}
                >
                  <img src={displayUrl} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                </div>
              );
            })}
          </div>
        </div>
      );
    })}
  </div>
), [messages, loadingState, activeImageUrl, activeAttachments]);
```

**确认**: 
- Sidebar 显示所有消息的缩略图
- 点击缩略图可以切换主画布显示的图片
- 优先使用 `url`，如果没有则使用 `tempUrl`

## 关键发现

### 1. 扩图模式特性（关键特性）

**位置**: `backend/app/services/gemini/expand_service.py`

**逻辑**:
- 扩图模式不需要文本提示词（`prompt` 为空字符串）
- 只需要一张图片作为输入
- 支持多个扩图方向（上、下、左、右、四方向）
- 通常使用 Tongyi（DashScope）提供商的扩图功能

**优势**:
- 简单易用，用户只需上传图片即可
- 支持智能扩图，自动填充扩展区域

### 2. 附件传递链路（完整）

**前端附件处理**:
1. ✅ `ImageExpandView.handleSend` 调用 `processUserAttachments`
2. ✅ `processUserAttachments` 实现 CONTINUITY LOGIC（无新上传时使用画布图片）
3. ✅ `ImageOutpaintingHandler.doExecute` 只使用第一个附件
4. ✅ `llmService.outPaintImage` 传递 `referenceImage`（单个附件）
5. ✅ `UnifiedProviderClient.outPaintImage` 调用 `executeMode('image-outpainting', ...)`
6. ✅ `UnifiedProviderClient.executeMode` 将 `attachments` 发送到后端

**后端附件处理**:
1. ✅ 后端路由 `/api/modes/tongyi/image-outpainting` 接收 `requestBody.attachments`
2. ✅ `convert_attachments_to_reference_images` 将 `attachments` 转换为 `reference_images` 字典
3. ✅ 根据 `attachment.role` 设置键名（'raw'）
4. ✅ 调用 `service.expand_image(**params)`
5. ✅ `TongyiService.expand_image` 委托给 `ExpandService.expand_image`
6. ✅ `ExpandService` 调用 DashScope API 的扩图功能

### 3. 图片显示链路（完整）

**后端返回**:
1. ✅ `ExpandService` 返回 `Dict[str, Any]`，格式: `{"url": "data:image/png;base64,...", "mimeType": "image/png"}`
2. ✅ 后端路由返回 `ModeResponse(success=True, data=result)`

**前端处理**:
1. ✅ `UnifiedProviderClient.executeMode` 解析响应，返回 `data.data`（即结果字典）
2. ✅ `llmService.outPaintImage` 返回 `ImageGenerationResult`
3. ✅ `ImageOutpaintingHandler.doExecute` 调用 `processMediaResult` 处理结果
4. ✅ `processMediaResult` 创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
5. ✅ `ImageOutpaintingHandler` 返回 `HandlerResult`，包含 `attachments`
6. ✅ `useChat.sendMessage` 更新 `messages` 状态，将 `displayAttachments` 添加到 `modelMessage`
7. ✅ `ImageExpandView` 从 `messages` 中提取 MODEL 消息的 `attachments`
8. ✅ `ImageExpandView` 自动切换到最新结果，渲染 `<img src={activeImageUrl}>`，立即显示图片
9. ✅ 异步上传任务在后台执行，完成后更新数据库

### 4. CONTINUITY LOGIC（关键特性）

**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 786-942

**逻辑**（与 ImageBackgroundEditView 相同）:
- 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），`processUserAttachments` 会自动使用画布上的图片
- 尝试从历史消息中查找匹配的附件（通过 URL 匹配）
- 如果找到，复用附件的 ID 和其他信息，查询后端获取云存储 URL
- 如果未找到，根据 URL 类型（Base64/Blob/HTTP）创建新附件

**优势**:
- 用户可以在画布上查看结果，然后直接发送新的扩图指令，无需重新上传图片
- 支持连续扩图工作流

## 问题定位

### 可能的问题

1. **附件未正确传递**:
   - **位置**: `processUserAttachments` 或 `ImageOutpaintingHandler.doExecute`
   - **验证**: 检查 `finalAttachments` 和 `referenceImage` 的值

2. **Provider 不支持扩图**:
   - **位置**: `llmService.outPaintImage` 的 provider 检查
   - **验证**: 检查当前 provider 是否支持 `outPaintImage` 方法

3. **扩图方向未传递**:
   - **位置**: `options` 中的扩图方向参数
   - **验证**: 检查扩图方向是否正确传递到后端

## 需要检查的关键代码位置

### 前端
1. **ImageExpandView.tsx line 328-350**: `handleSend` 中调用 `processUserAttachments`
2. **AllHandlerClasses.ts line 8-33**: `ImageOutpaintingHandler.doExecute` 中调用 `llmService.outPaintImage`
3. **llmService.ts line 340-382**: `outPaintImage` 中路由到 provider
4. **UnifiedProviderClient.ts**: `outPaintImage` 实现（如果存在）

### 后端
1. **backend/app/routers/core/modes.py line 150-305**: 路由接收请求和处理
2. **backend/app/services/tongyi/tongyi_service.py**: `expand_image` 实现
3. **backend/app/services/gemini/expand_service.py**: 扩图服务实现

## 调试步骤

1. **在 ImageExpandView.handleSend 中添加日志**:
```typescript
console.log('[ImageExpandView.handleSend] activeImageUrl:', activeImageUrl);
console.log('[ImageExpandView.handleSend] attachments:', attachments);
console.log('[ImageExpandView.handleSend] finalAttachments:', finalAttachments);
```

2. **在 ImageOutpaintingHandler.doExecute 中添加日志**:
```typescript
console.log('[ImageOutpaintingHandler.doExecute] context.attachments:', context.attachments);
console.log('[ImageOutpaintingHandler.doExecute] referenceImage:', context.attachments[0]);
```

3. **在 llmService.outPaintImage 中添加日志**:
```typescript
console.log('[llmService.outPaintImage] referenceImage:', referenceImage);
console.log('[llmService.outPaintImage] provider:', this.currentProvider);
```

## 结论

**前端附件传递链路完整**，所有附件都应该被传递到后端。**图片显示链路也完整**，图片应该能够立即显示。

**关键特性**:
1. ✅ **扩图模式**: 不需要文本提示词，只需要图片
2. ✅ **CONTINUITY LOGIC**: 支持连续扩图工作流，无需重复上传图片
3. ✅ **自动切换结果**: 新结果生成后自动切换到主画布显示

**建议**:
- 在前端和后端关键位置添加日志，确认附件在每个步骤的值
- 检查 provider 是否支持扩图功能
- 检查扩图方向参数是否正确传递
