# ImageGen 完整流程分析：从用户点击发送到UI显示图片

## 问题描述
分析 `image-gen` 模式下，用户点击发送按钮后，参数如何传递到后端，以及后端返回的图片如何在前端UI中显示。

## 完整数据流追踪

### 阶段 1: 用户交互 → 参数收集

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

#### 步骤 1.2: InputArea.handleSend 被调用
**位置**: `frontend/components/chat/InputArea.tsx` line 164-240

**关键代码**:
```typescript
const handleSend = async (...) => {
  // ...
  onSend(input, {
    imageAspectRatio: controls.aspectRatio,              // ✅ 从 useControlsState 读取
    imageResolution: controls.resolution,                // ✅ 从 useControlsState 读取
    numberOfImages: controls.numberOfImages,            // ✅ 从 useControlsState 读取
    imageStyle: controls.style,                          // ✅ 从 useControlsState 读取
    negativePrompt: controls.negativePrompt.trim(),     // ✅ 从 useControlsState 读取
    seed: controls.seed > -1 ? controls.seed : undefined, // ✅ 从 useControlsState 读取
    guidanceScale: controls.guidanceScale,               // ✅ 从 useControlsState 读取
    outputMimeType: controls.outputMimeType,            // ✅ 从 useControlsState 读取
    outputCompressionQuality: controls.outputCompressionQuality, // ✅ 从 useControlsState 读取
    enhancePrompt: controls.enhancePrompt,              // ✅ 从 useControlsState 读取
  }, processedAttachments, mode);
};
```

**参数来源**:
- `controls` 对象来自 `useControlsState(mode, currentModel)` (line 60)
- `ImageGenControls` 通过 props 接收这些参数和 setter，用户修改时更新状态

### 阶段 2: 参数传递 → 后端请求

#### 步骤 2.1: App.tsx.onSend 接收 options
**位置**: `frontend/App.tsx` line 254-285

```typescript
const onSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
  // ...
  const optionsWithPersona = { ...options, persona: activePersona };
  // ...
  sendMessage(text, optionsWithPersona, attachments, mode, modelForSend, config.protocol);
}, [...]);
```

**确认**: `options` 对象完整传递，只添加了 `persona` 字段。

#### 步骤 2.2: useChat.sendMessage 接收 options
**位置**: `frontend/hooks/useChat.ts` line 44-64

```typescript
const sendMessage = async (
  text: string,
  options: ChatOptions,  // ✅ 接收完整的 options
  attachments: Attachment[],
  mode: AppMode,
  currentModel: ModelConfig,
  protocol: 'google' | 'openai'
) => {
  // ...
  const enhancedOptions = options.enableResearch
    ? { ...options, enableSearch: true }
    : options;
  llmService.startNewChat(contextHistory, currentModel, enhancedOptions);
  // ...
};
```

**确认**: `options` 完整传递给 `llmService.startNewChat`，只可能添加 `enableSearch`。

#### 步骤 2.3: llmService.startNewChat 缓存 options
**位置**: `frontend/services/llmService.ts` line 143-149

```typescript
public startNewChat(history: Message[], modelConfig: ModelConfig, options?: ChatOptions) {
    this._cachedHistory = history;
    this._cachedModelConfig = modelConfig;
    if (options) {
        this._cachedOptions = options;  // ✅ 缓存到实例变量
    }
}
```

**确认**: `options` 被缓存到 `_cachedOptions` 实例变量。

#### 步骤 2.4: ImageGenHandler.doExecute 调用 generateImage
**位置**: `frontend/hooks/handlers/ImageGenHandlerClass.ts` line 8-10

```typescript
protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
  const results = await llmService.generateImage(context.text, context.attachments);
  // ...
}
```

**确认**: 调用 `llmService.generateImage`，**未传递 options**（使用缓存的 `_cachedOptions`）。

#### 步骤 2.5: llmService.generateImage 使用缓存的 options
**位置**: `frontend/services/llmService.ts` line 218-238

```typescript
public async generateImage(prompt: string, referenceImages: Attachment[] = []): Promise<ImageGenerationResult[]> {
  return this.currentProvider.generateImage(
      this._cachedModelConfig!.id,
      prompt,
      referenceImages,
      this._cachedOptions,  // ✅ 使用缓存的 options
      '', // API Key
      this.baseUrl
  );
}
```

**确认**: 将 `_cachedOptions` 传递给 provider 的 `generateImage` 方法。

#### 步骤 2.6: UnifiedProviderClient.generateImage 展开 options
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 450-467

```typescript
async generateImage(
  modelId: string,
  prompt: string,
  referenceImages: Attachment[],
  options: ChatOptions,  // ✅ 接收 options
  apiKey: string,
  baseUrl: string
): Promise<ImageGenerationResult[]> {
  const data = await this.executeMode(
    'image-gen',
    modelId,
    prompt,
    referenceImages,
    { ...options, baseUrl: baseUrl || options.baseUrl }  // ✅ 展开 options 并传递
  );
  return Array.isArray(data) ? data : [];
}
```

**确认**: `options` 被展开并传递给 `executeMode`。

#### 步骤 2.7: UnifiedProviderClient.executeMode 构建请求体
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 378-443

```typescript
async executeMode(
  mode: string,
  modelId: string,
  prompt: string,
  attachments: Attachment[] = [],
  options: Partial<ChatOptions> = {},  // ✅ 接收 options
  extra: Record<string, any> = {}
): Promise<any> {
  const requestBody = {
    modelId,
    prompt,
    attachments,
    options: {
      ...options  // ✅ 展开 options 到请求体
    },
    extra
  };
  
  const response = await fetch(`/api/modes/${this.id}/${mode}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(requestBody)  // ✅ 发送到后端
  });
  
  const data = await response.json();
  return data.data;  // ✅ 返回 data.data（后端返回 { success: true, data: {...} }）
}
```

**确认**: 
- `options` 被展开到 `requestBody.options` 并发送到 `/api/modes/{provider}/image-gen`
- 后端响应格式: `{ success: true, data: {...} }`
- 前端返回 `data.data`

### 阶段 3: 后端处理 → 生成图片

#### 步骤 3.1: 后端路由接收请求
**位置**: `backend/app/routers/core/modes.py` line 150-305

```python
@router.post("/{provider}/{mode}")
async def handle_mode(
    provider: str,
    mode: str,
    request_body: ModeRequest,  # 包含 modelId, prompt, attachments, options, extra
    ...
):
    # ✅ 1. 获取凭证
    api_key, api_url = await get_provider_credentials(...)
    
    # ✅ 2. 创建提供商服务
    service = ProviderFactory.create(provider=provider, ...)
    
    # ✅ 3. 根据 mode 获取服务方法名
    method_name = get_service_method(mode)  # 'image-gen' -> 'generate_image'
    
    # ✅ 4. 准备参数
    params = {
        "model": request_body.modelId,
        "prompt": request_body.prompt,
    }
    
    # ✅ 5. 添加 options 中的参数
    if request_body.options:
        options_dict = request_body.options.dict(exclude_none=True)
        params.update(options_dict)  # ✅ 展开 options 到 params
    
    # ✅ 6. 调用服务方法
    result = await method(**params)  # service.generate_image(**params)
    
    # ✅ 7. 返回响应
    return ModeResponse(success=True, data=result, ...)
```

**关键点**:
- `request_body.options` 被展开到 `params` 字典
- `params` 传递给 `service.generate_image(**params)`

#### 步骤 3.2: GoogleService.generate_image 委托给 ImageGenerator
**位置**: `backend/app/services/gemini/google_service.py` line 388-405

```python
async def generate_image(
    self,
    prompt: str,
    model: str,
    **kwargs  # ✅ 包含所有 options 中的参数
) -> List[Dict[str, Any]]:
    return await self.image_generator.generate_image(prompt, model, **kwargs)
```

**确认**: `**kwargs` 包含所有从 `options` 展开的参数。

#### 步骤 3.3: ImageGenerator.generate_image 委托给 ImagenCoordinator
**位置**: `backend/app/services/gemini/image_generator.py` line 55-95

```python
async def generate_image(
    self,
    prompt: str,
    model: str,
    **kwargs  # ✅ 包含所有参数
) -> List[Dict[str, Any]]:
    # 转换参数
    kwargs = self._convert_parameters_for_api(kwargs)
    
    # 获取生成器
    generator = self._coordinator.get_generator()
    
    # 委托给生成器
    return await generator.generate_image(prompt, model, **kwargs)
```

**确认**: `**kwargs` 包含所有参数，传递给具体的生成器（Gemini API 或 Vertex AI）。

#### 步骤 3.4: 具体生成器处理参数并生成图片
**位置**: `backend/app/services/gemini/imagen_gemini_api.py` line 82-227

```python
async def generate_image(
    self,
    prompt: str,
    model: str,
    **kwargs  # ✅ 包含: number_of_images, aspect_ratio, image_size, image_style, 
              #     output_mime_type, output_compression_quality, enhancePrompt, etc.
) -> List[Dict[str, Any]]:
    # 构建配置
    config = self._build_config(**kwargs)  # ✅ 使用 kwargs 中的参数
    
    # 应用 style 到 prompt
    image_style = kwargs.get('image_style')
    effective_prompt = prompt
    if image_style and image_style.lower() != "none":
        effective_prompt = f"{prompt}, style: {image_style}"
    
    # 调用 Gemini API
    response = self._client.models.generate_images(
        model=model,
        prompt=effective_prompt,
        config=config  # ✅ 包含所有参数
    )
    
    # 处理响应
    return self._process_response(response, **kwargs)
```

**关键参数映射**:
- `numberOfImages` → `config.number_of_images`
- `imageAspectRatio` → `config.aspect_ratio`
- `imageResolution` → `config.image_size`
- `imageStyle` → 应用到 prompt
- `outputMimeType` → `config.output_mime_type`
- `outputCompressionQuality` → `config.output_compression_quality`
- `enhancePrompt` → 在生成器中处理
- `guidanceScale` → 传递给 API（如果支持）
- `negativePrompt` → 传递给 API（如果支持）
- `seed` → 传递给 API（如果支持）

#### 步骤 3.5: 后端返回图片数据
**位置**: `backend/app/services/gemini/imagen_gemini_api.py` line 174-227

```python
def _process_response(self, response, **kwargs) -> List[Dict[str, Any]]:
    results = []
    for idx, generated_image in enumerate(response.generated_images):
        # 处理图片字节
        image_bytes = ...
        b64_data = encode_image_to_base64(image_bytes)
        
        result = {
            "url": f"data:{output_mime_type};base64,{b64_data}",  # ✅ Base64 Data URL
            "mimeType": output_mime_type,  # ✅ MIME 类型
            "index": idx,
            "size": len(image_bytes)
        }
        results.append(result)
    
    return results  # ✅ 返回 List[Dict[str, Any]]
```

**返回格式**: `List[Dict[str, Any]]`，每个元素包含:
- `url`: Base64 Data URL (例如: `"data:image/png;base64,..."`)
- `mimeType`: MIME 类型 (例如: `"image/png"`)
- `index`: 图片索引
- `size`: 图片大小（字节）

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

#### 步骤 4.2: llmService.generateImage 返回结果
**位置**: `frontend/services/llmService.ts` line 230-234

```typescript
return this.currentProvider.generateImage(
    this._cachedModelConfig!.id,
    prompt,
    referenceImages,
    this._cachedOptions,
    '',
    this.baseUrl
);  // ✅ 返回 ImageGenerationResult[]
```

**返回类型**: `ImageGenerationResult[]`，每个元素包含:
- `url`: string (Base64 Data URL)
- `mimeType`: string

#### 步骤 4.3: ImageGenHandler.doExecute 处理结果
**位置**: `frontend/hooks/handlers/ImageGenHandlerClass.ts` line 8-28

```typescript
protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
  try {
    const results = await llmService.generateImage(context.text, context.attachments);
    // ✅ results: ImageGenerationResult[] = [{ url: "data:image/png;base64,...", mimeType: "image/png" }, ...]

    // ✅ 使用统一的媒体处理函数
    const processed = await Promise.all(
      results.map(res => processMediaResult(res, context, 'generated'))
    );
    // ✅ processed: [{ displayAttachment: Attachment, dbAttachmentPromise: Promise<Attachment> }, ...]

    const displayAttachments: Attachment[] = processed.map(p => p.displayAttachment);
    // ✅ displayAttachments: Attachment[]，用于立即显示

    const uploadTask = async () => {
      const dbAttachments = await Promise.all(processed.map(p => p.dbAttachmentPromise));
      return { dbAttachments };
    };
    // ✅ uploadTask: 异步上传任务，完成后返回 dbAttachments（包含云存储 URL）

    return {
      content: `Generated images for: "${context.text}"`,
      attachments: displayAttachments,  // ✅ 用于立即显示
      uploadTask: uploadTask()  // ✅ 异步上传任务
    };
  } catch (error: any) {
    // 错误处理
  }
}
```

#### 步骤 4.4: processMediaResult 处理单个图片结果
**位置**: `frontend/hooks/handlers/attachmentUtils.ts` line 960-1016

```typescript
export const processMediaResult = async (
  res: { url: string; mimeType: string; filename?: string },  // ✅ 后端返回的格式
  context: { sessionId: string; modelMessageId: string; storageId?: string },
  filePrefix: string
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
// ✅ result: HandlerResult = { content: string, attachments: Attachment[], uploadTask: Promise }

// 9. Update UI with result
const displayModelMessage: Message = {
  ...initialModelMessage,
  content: result.content,
  attachments: result.attachments as Attachment[],  // ✅ 使用 displayAttachments
  // ...
};

setMessages(prev => prev.map(msg => msg.id === modelMessageId ? displayModelMessage : msg));
// ✅ 更新 messages 状态，立即显示图片
```

**确认**: 
- `result.attachments` 是 `displayAttachments`，包含 Base64 Data URL 或 Blob URL
- `setMessages` 立即更新状态，触发 UI 重新渲染

#### 步骤 5.2: ImageGenView 从 messages 提取图片
**位置**: `frontend/components/views/ImageGenView.tsx` line 51-67

```typescript
// 1. Group History by Message (Batch)
const historyBatches = useMemo(() => {
    return messages
        .filter(m => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError))
        .reverse();
}, [messages]);
// ✅ 过滤出 MODEL 角色的消息，且包含 attachments

// 2. Determine Active Batch to Display
const activeBatchMessage = useMemo(() => {
    if (selectedMsgId) {
        return historyBatches.find(m => m.id === selectedMsgId);
    }
    return historyBatches[0];  // ✅ 默认显示最新的批次
}, [selectedMsgId, historyBatches]);

const displayImages = (activeBatchMessage?.attachments || []).filter(att => att.url && att.url.length > 0);
// ✅ 提取附件中有效的 URL
```

**确认**: 
- `historyBatches` 包含所有有附件的 MODEL 消息
- `activeBatchMessage` 是当前要显示的消息
- `displayImages` 是当前消息的附件列表

#### 步骤 5.3: ImageGenView 渲染图片
**位置**: `frontend/components/views/ImageGenView.tsx` line 203-280

```typescript
{displayImages.length > 0 ? (
    <div className="...grid...">
        {displayImages.map((att, idx) => (
            <div key={idx} className="...">
                {att.url ? (
                    <img
                        src={att.url}  // ✅ 使用 Base64 Data URL 或 Blob URL
                        className="..."
                        onClick={() => onImageClick(att.url!)}
                        alt="Generated image"
                    />
                ) : (
                    <div>...</div>
                )}
            </div>
        ))}
    </div>
) : (
    <div>No images</div>
)}
```

**确认**: 
- `att.url` 是 Base64 Data URL 或 Blob URL，可以直接在 `<img src={att.url}>` 中使用
- 图片立即显示，无需等待上传完成

#### 步骤 5.4: 异步上传完成后更新数据库
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

### 阶段 6: Sidebar 历史显示

#### 步骤 6.1: ImageGenView 的 sidebarContent 显示历史
**位置**: `frontend/components/views/ImageGenView.tsx` line 80-136

```typescript
const sidebarContent = useMemo(() => (
    <div className="p-3 space-y-3">
        {historyBatches.map((msg, i) => {
            const firstImage = msg.attachments?.[0]?.url;  // ✅ 获取第一张图片的 URL
            const count = msg.attachments?.length || 0;
            const isSelected = activeBatchMessage?.id === msg.id;

            return (
                <div key={msg.id} onClick={() => setSelectedMsgId(msg.id)}>
                    <div className="aspect-square...">
                        {firstImage ? (
                            <img src={firstImage} className="..." alt="Generated image" />
                            // ✅ 使用附件中的 URL 显示缩略图
                        ) : (
                            <div>...</div>
                        )}
                    </div>
                </div>
            );
        })}
    </div>
), [historyBatches, activeBatchMessage?.id]);
```

**确认**: 
- `historyBatches` 包含所有有附件的 MODEL 消息
- 每个消息的 `attachments` 包含图片 URL
- Sidebar 显示每批生成的缩略图

## 关键发现

### 1. 参数传递链路（完整）

**前端参数传递**:
1. ✅ `useControlsState` 管理参数状态
2. ✅ `ImageGenControls` 通过 setter 更新状态
3. ✅ `InputArea.handleSend` 从 `controls` 读取参数并构建 `options` 对象
4. ✅ `App.tsx.onSend` 接收 `options` 并传递给 `sendMessage`
5. ✅ `useChat.sendMessage` 接收 `options` 并传递给 `llmService.startNewChat`
6. ✅ `llmService.startNewChat` 缓存 `options` 到 `_cachedOptions`
7. ✅ `ImageGenHandler` 调用 `llmService.generateImage`（使用缓存的 `_cachedOptions`）
8. ✅ `llmService.generateImage` 将 `_cachedOptions` 传递给 `UnifiedProviderClient.generateImage`
9. ✅ `UnifiedProviderClient.generateImage` 展开 `options` 并传递给 `executeMode`
10. ✅ `UnifiedProviderClient.executeMode` 将 `options` 展开到请求体并发送到后端

**后端参数处理**:
1. ✅ 后端路由 `/api/modes/{provider}/image-gen` 接收 `requestBody.options`
2. ✅ 将 `requestBody.options` 展开到 `params` 字典
3. ✅ 调用 `service.generate_image(**params)`
4. ✅ `GoogleService.generate_image` 委托给 `ImageGenerator.generate_image(**kwargs)`
5. ✅ `ImageGenerator.generate_image` 委托给 `ImagenCoordinator.get_generator().generate_image(**kwargs)`
6. ✅ 具体生成器（Gemini API 或 Vertex AI）使用参数生成图片

### 2. 图片显示链路（完整）

**后端返回**:
1. ✅ 生成器返回 `List[Dict[str, Any]]`，格式: `[{"url": "data:image/png;base64,...", "mimeType": "image/png", ...}]`
2. ✅ 后端路由返回 `ModeResponse(success=True, data=results)`

**前端处理**:
1. ✅ `UnifiedProviderClient.executeMode` 解析响应，返回 `data.data`（即 results 列表）
2. ✅ `llmService.generateImage` 返回 `ImageGenerationResult[]`
3. ✅ `ImageGenHandler.doExecute` 调用 `processMediaResult` 处理每个结果
4. ✅ `processMediaResult` 创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
5. ✅ `ImageGenHandler` 返回 `HandlerResult`，包含 `attachments: displayAttachments[]`
6. ✅ `useChat.sendMessage` 更新 `messages` 状态，将 `displayAttachments` 添加到 `modelMessage.attachments`
7. ✅ `ImageGenView` 从 `messages` 中提取 MODEL 消息的 `attachments`
8. ✅ `ImageGenView` 渲染 `<img src={att.url}>`，立即显示图片
9. ✅ 异步上传任务在后台执行，完成后更新数据库

### 3. 参数映射关系

**前端 ChatOptions → 后端参数**:
- `imageAspectRatio` → `aspect_ratio` (kwargs)
- `imageResolution` → `image_size` (kwargs)
- `numberOfImages` → `number_of_images` (kwargs)
- `imageStyle` → `image_style` (kwargs，应用到 prompt)
- `guidanceScale` → `guidance_scale` (kwargs，如果 API 支持)
- `outputMimeType` → `output_mime_type` (kwargs)
- `outputCompressionQuality` → `output_compression_quality` (kwargs)
- `enhancePrompt` → 在生成器中处理
- `negativePrompt` → `negative_prompt` (kwargs，如果 API 支持)
- `seed` → `seed` (kwargs，如果 API 支持)

## 问题定位

### 问题 1: ModeOptions 模型缺少字段（已确认）

**位置**: `backend/app/routers/core/modes.py` line 49-78

**问题分析**:
```python
class ModeOptions(BaseModel):
    # ... 其他字段 ...
    imageAspectRatio: Optional[str] = None      # ✅ 存在
    imageResolution: Optional[str] = None        # ✅ 存在
    numberOfImages: Optional[int] = None        # ✅ 存在
    imageStyle: Optional[str] = None            # ✅ 存在
    negativePrompt: Optional[str] = None        # ✅ 存在
    guidanceScale: Optional[float] = None       # ✅ 存在
    seed: Optional[int] = None                  # ✅ 存在
    # ❌ 缺少以下字段:
    # outputMimeType: Optional[str] = None
    # outputCompressionQuality: Optional[int] = None
    # enhancePrompt: Optional[bool] = None
    class Config:
        extra = "allow"  # ✅ 允许额外字段，但可能未被正确使用
```

**确认**: 
- `ModeOptions` 模型**缺少**以下字段:
  - `outputMimeType` (前端发送: `outputMimeType`)
  - `outputCompressionQuality` (前端发送: `outputCompressionQuality`)
  - `enhancePrompt` (前端发送: `enhancePrompt`)

**影响**:
- 虽然 `Config.extra = "allow"` 允许额外字段，但这些字段可能:
  1. 在 `options_dict = request_body.options.dict(exclude_none=True)` 时被正确处理（因为 extra="allow"）
  2. 但在后续处理中可能被忽略或未正确映射

### 问题 2: 参数名不匹配（已确认）

**位置**: `backend/app/routers/core/modes.py` line 227-231 + `backend/app/services/gemini/imagen_gemini_api.py` line 156

**问题分析**:
```python
# 后端路由 (modes.py)
options_dict = request_body.options.dict(exclude_none=True)  # ✅ 保持原始字段名（驼峰命名）
params.update(options_dict)  # ✅ params 包含: {"outputMimeType": "...", "outputCompressionQuality": 95, ...}

# 后端服务层 (imagen_gemini_api.py)
output_mime_type = kwargs.get('output_mime_type', 'image/jpeg')  # ❌ 期望下划线命名，但收到的是驼峰命名
```

**确认**: 
- 前端发送: `outputMimeType`, `outputCompressionQuality`, `enhancePrompt` (驼峰命名)
- 后端路由: `params` 包含驼峰命名的字段
- 后端服务层: 期望 `output_mime_type`, `output_compression_quality`, `enhance_prompt` (下划线命名)
- **问题**: 中间没有转换，导致参数名不匹配！

**影响**:
- `kwargs.get('output_mime_type')` 返回 `None`，使用默认值 `'image/jpeg'`
- `kwargs.get('output_compression_quality')` 返回 `None`，未使用
- `kwargs.get('enhance_prompt')` 返回 `None`，未使用

**验证方法**:
- 在后端路由中添加日志，打印 `options_dict` 和 `params`
- 在服务层添加日志，打印 `kwargs` 和 `kwargs.get('output_mime_type')`
- 检查参数名是否匹配

### 问题 2: 参数在服务层未正确传递

**位置**: `backend/app/services/gemini/image_generator.py` + `imagen_gemini_api.py`

**问题分析**:
- `ImageGenerator.generate_image` 接收 `**kwargs`
- `_convert_parameters_for_api` 可能过滤或转换某些参数
- 具体生成器的 `_build_config` 可能未使用某些参数

**验证方法**:
- 在 `ImageGenerator.generate_image` 中添加日志，打印 `kwargs`
- 在 `_convert_parameters_for_api` 中添加日志，打印转换后的参数
- 在 `_build_config` 中添加日志，打印构建的配置

### 问题 3: 参数在 API 调用时丢失

**位置**: `backend/app/services/gemini/imagen_gemini_api.py` line 149-172

**问题分析**:
- `_build_config` 只使用部分参数构建配置
- 某些参数（如 `guidanceScale`, `negativePrompt`, `seed`）可能未被使用

**验证方法**:
- 检查 `_build_config` 实现，确认所有参数都被使用
- 检查 Gemini API 是否支持这些参数
- 在 API 调用前后添加日志，确认参数传递

## 需要检查的关键代码位置

### 前端
1. **InputArea.tsx line 206-236**: `handleSend` 中构建的 `options` 对象
2. **UnifiedProviderClient.ts line 391-393**: `executeMode` 构建的 `requestBody.options`

### 后端
1. **backend/app/routers/core/modes.py line 49-86**: `ModeOptions` 模型定义
2. **backend/app/routers/core/modes.py line 225-231**: `options` 展开到 `params`
3. **backend/app/services/gemini/image_generator.py line 97-120**: `_convert_parameters_for_api` 参数转换
4. **backend/app/services/gemini/imagen_gemini_api.py line 149-172**: `_build_config` 配置构建

## 调试步骤

1. **在前端 UnifiedProviderClient.executeMode 中添加日志**:
```typescript
console.log('[UnifiedProviderClient.executeMode] Request body:', JSON.stringify(requestBody, null, 2));
```

2. **在后端 modes.py 中添加日志**:
```python
logger.info(f"[Modes] Request options: {request_body.options}")
logger.info(f"[Modes] Params after update: {params}")
```

3. **在 ImageGenerator.generate_image 中添加日志**:
```python
logger.info(f"[ImageGenerator] Received kwargs: {kwargs}")
```

4. **在 _build_config 中添加日志**:
```python
logger.info(f"[GeminiAPIImageGenerator] Config kwargs: {config_kwargs}")
```

5. **检查 ModeOptions 模型定义**: 确认包含所有必要字段

## 结论

**前端参数传递链路完整**，所有参数都应该被传递到后端。**图片显示链路也完整**，图片应该能够立即显示。

**已确认的问题**:
1. ✅ **ModeOptions 模型缺少字段**: `outputMimeType`, `outputCompressionQuality`, `enhancePrompt` 未在模型中定义（但有 `Config.extra = "allow"`，所以可以通过）
2. ✅ **参数名不匹配**: 前端发送驼峰命名（`outputMimeType`），后端服务层期望下划线命名（`output_mime_type`），中间没有转换

**解决方案**:
1. **在 ModeOptions 中添加缺失字段**（推荐）:
```python
class ModeOptions(BaseModel):
    # ... 现有字段 ...
    outputMimeType: Optional[str] = None
    outputCompressionQuality: Optional[int] = None
    enhancePrompt: Optional[bool] = None
```

2. **在后端路由中添加参数名转换**（推荐）:
```python
# 添加 options 中的参数
if request_body.options:
    options_dict = request_body.options.dict(exclude_none=True)
    
    # ✅ 转换驼峰命名为下划线命名
    converted_dict = {}
    for key, value in options_dict.items():
        # 转换驼峰命名为下划线命名
        snake_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
        converted_dict[snake_key] = value
    
    params.update(converted_dict)
```

3. **或者在服务层同时支持两种命名**（备选）:
```python
output_mime_type = kwargs.get('output_mime_type') or kwargs.get('outputMimeType', 'image/jpeg')
```

**建议**:
- 优先使用方案 1 + 方案 2，确保参数名一致
- 在前端和后端关键位置添加日志，确认参数在每个步骤的值
- 测试所有参数是否正确传递和使用
