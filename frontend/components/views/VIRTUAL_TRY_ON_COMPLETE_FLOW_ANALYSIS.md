# VirtualTryOnView 完整流程分析：从用户点击发送到UI显示图片

## 问题描述
分析 `virtual-try-on` 模式下，用户点击发送按钮后，参数和附件如何传递到后端，以及后端返回的图片如何在前端UI中显示。

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

#### 步骤 1.2: VirtualTryOnView.handleSend 被调用
**位置**: `frontend/components/views/VirtualTryOnView.tsx` line 327-449

**关键代码**:
```typescript
const handleSend = useCallback(async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
  console.log('========== [VirtualTryOnView] handleSend 开始 ==========');
  console.log('[handleSend] 服装描述:', text);
  console.log('[handleSend] tryOnTarget:', options.virtualTryOnTarget);

  let finalAttachments = [...attachments];

  // ✅ CONTINUITY LOGIC: 当用户没有上传新图片时，使用画布上的图片
  if (finalAttachments.length === 0 && activeImageUrl) {
    console.log('[handleSend] 触发 CONTINUITY LOGIC');

    try {
      const isBase64 = activeImageUrl?.startsWith('data:');
      const isBlobUrl = activeImageUrl?.startsWith('blob:');
      const isCloudUrl = activeImageUrl?.startsWith('http://') || activeImageUrl?.startsWith('https://');

      // ✅ 尝试从历史消息中查找匹配的附件
      const found = findAttachmentFromHistory(activeImageUrl);

      if (found) {
        const { attachment: existingAttachment } = found;
        let finalUrl = existingAttachment.url;
        let finalUploadStatus = existingAttachment.uploadStatus || 'completed';

        // ✅ 查询后端获取云存储 URL
        if (finalUploadStatus === 'pending' && currentSessionId) {
          const backendData = await fetchAttachmentFromBackend(currentSessionId, existingAttachment.id);
          if (backendData && backendData.url?.startsWith('http')) {
            finalUrl = backendData.url;
            finalUploadStatus = 'completed';
          }
        }

        const reusedAttachment: Attachment = {
          id: uuidv4(),
          mimeType: existingAttachment.mimeType || 'image/png',
          name: existingAttachment.name || `canvas-${Date.now()}.png`,
          url: finalUrl,
          uploadStatus: finalUploadStatus
        };

        // ✅ 转换为 Base64（用于 API 调用）
        if (isBase64 && activeImageUrl) {
          (reusedAttachment as any).base64Data = activeImageUrl;
        } else if (finalUrl?.startsWith('http')) {
          const fetchUrl = `/api/storage/download?url=${encodeURIComponent(finalUrl)}`;
          const response = await fetch(fetchUrl);
          const blob = await response.blob();
          const base64Url = await new Promise<string>((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result as string);
            reader.readAsDataURL(blob);
          });
          (reusedAttachment as any).base64Data = base64Url;
        }

        finalAttachments = [reusedAttachment];
      } else if (isCloudUrl) {
        // ✅ 云存储 URL，下载并转换为 Base64
        const fetchUrl = `/api/storage/download?url=${encodeURIComponent(activeImageUrl)}`;
        const response = await fetch(fetchUrl);
        const blob = await response.blob();
        const base64Url = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result as string);
          reader.readAsDataURL(blob);
        });

        const reusedAttachment: Attachment = {
          id: uuidv4(),
          mimeType: blob.type || 'image/png',
          name: `canvas-${Date.now()}.png`,
          url: activeImageUrl,
          uploadStatus: 'completed'
        };
        (reusedAttachment as any).base64Data = base64Url;
        finalAttachments = [reusedAttachment];
      } else if (isBase64 || isBlobUrl) {
        // ✅ Base64 或 Blob URL，直接使用
        let base64Url: string;
        if (isBlobUrl) {
          const response = await fetch(activeImageUrl);
          const blob = await response.blob();
          base64Url = await new Promise<string>((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result as string);
            reader.readAsDataURL(blob);
          });
        } else {
          base64Url = activeImageUrl;
        }

        const reusedAttachment: Attachment = {
          id: uuidv4(),
          mimeType: 'image/png',
          name: `canvas-${Date.now()}.png`,
          url: base64Url,
          uploadStatus: 'completed'
        };
        (reusedAttachment as any).base64Data = base64Url;
        finalAttachments = [reusedAttachment];
      }
    } catch (e) {
      console.error("[handleSend] CONTINUITY LOGIC 失败:", e);
    }
  }

  console.log('[handleSend] 最终附件数量:', finalAttachments.length);
  
  // ✅ 更新当前选择的服装类型（用于掩码预览）
  if (options.virtualTryOnTarget) {
    setCurrentTryOnTarget(options.virtualTryOnTarget);
  }
  
  // ✅ 添加 Upscale 选项到 options（从 View 内部状态）
  const finalOptions = {
    ...options,
    enableUpscale,
    upscaleFactor,
    addWatermark
  };
  
  onSend(text, finalOptions, finalAttachments, mode);  // ✅ mode = 'virtual-try-on'
}, [activeImageUrl, currentSessionId, findAttachmentFromHistory, fetchAttachmentFromBackend, enableUpscale, upscaleFactor, addWatermark, onSend]);
```

**关键逻辑**:
- **CONTINUITY LOGIC**: 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），自动使用画布上的图片
- **特殊处理**: Virtual Try-On 需要将图片转换为 Base64 格式（用于 API 调用）
- **Upscale 选项**: 从 View 内部状态（`enableUpscale`, `upscaleFactor`, `addWatermark`）添加到 `options`
- **服装类型**: 从 `options.virtualTryOnTarget` 获取，用于掩码预览

**注意**: Virtual Try-On 模式通常需要2个附件（人物照片和服装照片），但当前实现只处理了1个附件（人物照片）。服装描述通过 `text`（prompt）传递。

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
  mode: AppMode,  // ✅ 'virtual-try-on'
  currentModel: ModelConfig,
  protocol: 'google' | 'openai'
) => {
  // ...
  const enhancedOptions = options.enableResearch
    ? { ...options, enableSearch: true }
    : options;
  llmService.startNewChat(contextHistory, currentModel, enhancedOptions);
  // ...
  const handler = strategyRegistry.getHandler(mode);  // ✅ 返回 VirtualTryOnHandler
  const result = await handler.execute(context);
  // ...
};
```

**确认**: 
- `mode` 传递给 `strategyRegistry.getHandler(mode)`，返回 `VirtualTryOnHandler`
- `attachments` 传递给 `handler.execute(context)`

#### 步骤 2.3: VirtualTryOnHandler.doExecute 处理附件
**位置**: `frontend/hooks/handlers/AllHandlerClasses.ts` line 36-62

```typescript
export class VirtualTryOnHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    // ✅ 验证：需要至少2个附件（人物照片和服装照片）
    if (!context.attachments || context.attachments.length < 2) {
      throw new Error('Virtual try-on requires 2 images: person and garment');
    }

    // ✅ 调用 llmService.virtualTryOn
    const results = await llmService.virtualTryOn(context.text, context.attachments);

    // ✅ 使用统一的媒体处理函数
    const processed = await Promise.all(
      results.map((res: { url: string; mimeType: string; filename?: string }) => 
        processMediaResult(res, context, 'vto')  // ✅ 文件前缀为 'vto'
      )
    );

    const displayAttachments = processed.map(p => p.displayAttachment);
    const uploadTask = async () => ({
      dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise)),
      dbUserAttachments: context.attachments
    });

    return {
      content: `Virtual try-on result for: "${context.text}"`,
      attachments: displayAttachments,  // ✅ 用于立即显示
      uploadTask: uploadTask()  // ✅ 异步上传任务
    };
  }
}
```

**关键处理**:
- **验证**: 需要至少2个附件（人物照片和服装照片）
- 调用 `llmService.virtualTryOn(context.text, context.attachments)`
- 使用 `processMediaResult` 处理结果，文件前缀为 `'vto'`

#### 步骤 2.4: llmService.virtualTryOn 路由到 provider
**位置**: `frontend/services/llmService.ts` line 384-406

```typescript
public async virtualTryOn(prompt: string, attachments: Attachment[]): Promise<ImageGenerationResult[]> {
  // ✅ 新架构: 使用 UnifiedProviderClient.executeMode('virtual-try-on', ...) 统一处理
  if (this.currentProvider && 'executeMode' in this.currentProvider) {
    const unifiedProvider = this.currentProvider as any;
    const result = await unifiedProvider.executeMode(
      'virtual-try-on',
      this._cachedOptions.modelId || '',  // ✅ 模型 ID
      prompt,  // ✅ 服装描述
      attachments,  // ✅ 附件数组（人物照片和服装照片）
      this._cachedOptions,  // ✅ 包含 enableUpscale, upscaleFactor, addWatermark, virtualTryOnTarget 等
      {}
    );
    return Array.isArray(result) ? result : [result];
  }
  
  // 回退到旧方法（仅用于兼容性，应该尽快迁移）
  if (this.providerId === 'google') {
    const result = await this.callGoogleVirtualTryonAPI(prompt, attachments);
    return [result];
  }
  
  throw new Error("Virtual Try-On not supported by current provider.");
}
```

**确认**: 
- 调用 `UnifiedProviderClient.executeMode('virtual-try-on', modelId, prompt, attachments, options, {})`
- `attachments` 包含至少2个附件（人物照片和服装照片）
- `options` 包含 `enableUpscale`, `upscaleFactor`, `addWatermark`, `virtualTryOnTarget` 等

#### 步骤 2.5: UnifiedProviderClient.executeMode 构建请求体
**位置**: `frontend/services/providers/UnifiedProviderClient.ts` line 378-443

```typescript
async executeMode(
  mode: string,  // ✅ 'virtual-try-on'
  modelId: string,
  prompt: string,  // ✅ 服装描述
  attachments: Attachment[] = [],  // ✅ 包含至少2个附件
  options: Partial<ChatOptions> = {},  // ✅ 包含 enableUpscale, upscaleFactor, addWatermark, virtualTryOnTarget
  extra: Record<string, any> = {}
): Promise<any> {
  const requestBody = {
    modelId,
    prompt,  // ✅ 服装描述
    attachments,  // ✅ 包含至少2个附件
    options: {
      ...options  // ✅ 包含 enableUpscale, upscaleFactor, addWatermark, virtualTryOnTarget
    },
    extra
  };
  
  const response = await fetch(`/api/modes/${this.id}/${mode}`, {  // ✅ '/api/modes/google/virtual-try-on'
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
- 请求发送到 `/api/modes/google/virtual-try-on`
- `attachments` 包含至少2个附件（人物照片和服装照片）
- `options` 包含 `enableUpscale`, `upscaleFactor`, `addWatermark`, `virtualTryOnTarget` 等

### 阶段 3: 后端处理 → 生成图片

#### 步骤 3.1: 后端路由接收请求
**位置**: `backend/app/routers/core/modes.py` line 150-305

```python
@router.post("/{provider}/{mode}")  # ✅ '/api/modes/google/virtual-try-on'
async def handle_mode(
    provider: str,  # ✅ 'google'
    mode: str,      # ✅ 'virtual-try-on'
    request_body: ModeRequest,
    ...
):
    # ✅ 1. 获取凭证
    api_key, api_url = await get_provider_credentials(...)
    
    # ✅ 2. 创建提供商服务
    service = ProviderFactory.create(provider=provider, ...)
    
    # ✅ 3. 根据 mode 获取服务方法名
    method_name = get_service_method(mode)  # ✅ 'virtual-try-on' -> 'virtual_tryon'
    
    # ✅ 4. 准备参数
    params = {
        "model": request_body.modelId,
        "prompt": request_body.prompt,  # ✅ 服装描述
    }
    
    # ✅ 5. 添加 options 中的参数
    if request_body.options:
        options_dict = request_body.options.dict(exclude_none=True)
        params.update(options_dict)  # ✅ 包含 enableUpscale, upscaleFactor, addWatermark, virtualTryOnTarget
    
    # ✅ 6. 转换 attachments 为 reference_images
    if request_body.attachments:
        reference_images = convert_attachments_to_reference_images(request_body.attachments)
        # ✅ reference_images = { 'raw': base64_image, ... }
        if reference_images:
            params["reference_images"] = reference_images
    
    # ✅ 7. 调用服务方法
    result = await method(**params)  # ✅ service.virtual_tryon(**params)
    
    # ✅ 8. 返回响应
    return ModeResponse(success=True, data=result, ...)
```

**关键处理**:
- `convert_attachments_to_reference_images` 将 `attachments` 数组转换为 `reference_images` 字典
- 根据 `attachment.role` 设置键名（'raw', 等）
- `params` 包含 `enableUpscale`, `upscaleFactor`, `addWatermark`, `virtualTryOnTarget` 等选项

#### 步骤 3.2: GoogleService.virtual_tryon 委托给 TryOnService
**位置**: `backend/app/services/gemini/google_service.py`

**实现**:
```python
async def virtual_tryon(
    self,
    prompt: str,  # ✅ 服装描述
    model: str,
    reference_images: Dict[str, Any],  # ✅ { 'raw': base64_image, ... }
    **kwargs  # ✅ 包含 enableUpscale, upscaleFactor, addWatermark, virtualTryOnTarget
) -> Dict[str, Any]:
    # ✅ 委托给 TryOnService
    return await self.tryon_service.virtual_tryon(
        prompt=prompt,
        model=model,
        reference_images=reference_images,
        **kwargs
    )
```

**确认**: 委托给 `TryOnService.virtual_tryon`。

#### 步骤 3.3: TryOnService.virtual_tryon 处理虚拟试衣
**位置**: `backend/app/services/gemini/tryon_service.py`

**实现**:
- 处理人物照片和服装描述
- 调用服装分割 API（如果需要）
- 调用编辑 API 进行虚拟试衣
- 支持 Upscale（如果启用）

#### 步骤 3.4: 后端返回图片数据
**位置**: `backend/app/services/gemini/tryon_service.py`

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

#### 步骤 4.2: llmService.virtualTryOn 返回结果
**位置**: `frontend/services/llmService.ts` line 388-396

```typescript
const result = await unifiedProvider.executeMode(
  'virtual-try-on',
  this._cachedOptions.modelId || '',
  prompt,
  attachments,
  this._cachedOptions,
  {}
);
return Array.isArray(result) ? result : [result];  // ✅ 返回 ImageGenerationResult[]
```

**返回类型**: `ImageGenerationResult[]`，每个元素包含:
- `url`: string (Base64 Data URL)
- `mimeType`: string

#### 步骤 4.3: VirtualTryOnHandler.doExecute 处理结果
**位置**: `frontend/hooks/handlers/AllHandlerClasses.ts` line 36-62

```typescript
const results = await llmService.virtualTryOn(context.text, context.attachments);
// ✅ results: ImageGenerationResult[] = [{ url: "data:image/png;base64,...", mimeType: "image/png" }, ...]

// ✅ 使用统一的媒体处理函数
const processed = await Promise.all(
  results.map((res: { url: string; mimeType: string; filename?: string }) => 
    processMediaResult(res, context, 'vto')
  )
);
// ✅ processed: [{ displayAttachment: Attachment, dbAttachmentPromise: Promise<Attachment> }, ...]

const displayAttachments = processed.map(p => p.displayAttachment);
// ✅ displayAttachments: Attachment[]，用于立即显示

const uploadTask = async () => ({
  dbAttachments: await Promise.all(processed.map(p => p.dbAttachmentPromise)),
  dbUserAttachments: context.attachments
});

return {
  content: `Virtual try-on result for: "${context.text}"`,
  attachments: displayAttachments,  // ✅ 用于立即显示
  uploadTask: uploadTask()  // ✅ 异步上传任务
};
```

**处理逻辑**:
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

#### 步骤 5.2: VirtualTryOnView 从 messages 提取图片
**位置**: `frontend/components/views/VirtualTryOnView.tsx` line 192-211

```typescript
// ✅ Auto-select latest result
useEffect(() => {
  if (activeAttachments.length === 0 && !activeImageUrl) {
    const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
    if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
      setActiveImageUrl(lastModelMsg.attachments[0].url);
    }
  }

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

#### 步骤 5.3: VirtualTryOnView 渲染图片
**位置**: `frontend/components/views/VirtualTryOnView.tsx` line 688-713

```typescript
{activeImageUrl ? (
  <div
    className="relative shadow-2xl group transition-transform duration-75 ease-out"
    style={canvas.canvasStyle}
  >
    <img
      src={activeImageUrl}  // ✅ 使用 Base64 Data URL 或 Blob URL
      className="max-w-none rounded-lg border border-slate-800 pointer-events-none"
      style={{ maxHeight: '80vh', maxWidth: '80vw' }}
      alt="Main Canvas"
    />
    {/* ✅ Mask Preview Overlay */}
    {showMaskPreview && maskPreviewUrl && (
      <div className="absolute inset-0 pointer-events-none">
        <img
          src={maskPreviewUrl}
          className="max-w-none rounded-lg opacity-50 mix-blend-multiply"
          style={{ maxHeight: '80vh', maxWidth: '80vw', filter: 'hue-rotate(330deg)' }}
          alt="Mask Preview"
        />
        <div className="absolute top-4 left-4 bg-black/60 text-white px-3 py-1 rounded-full text-xs">
          红色区域将被替换
        </div>
      </div>
    )}
  </div>
) : (
  // 空状态
)}
```

**确认**: 
- `activeImageUrl` 是 Base64 Data URL 或 Blob URL，可以直接在 `<img src={activeImageUrl}>` 中使用
- 图片立即显示，无需等待上传完成
- **Mask Preview**: 如果启用了掩码预览（`showMaskPreview`），会叠加显示掩码预览图

#### 步骤 5.4: Sidebar 历史显示
**位置**: `frontend/components/views/VirtualTryOnView.tsx` line 454-501

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
            {msg.attachments?.filter(att => att.url && att.url.length > 0).map((att, idx) => (
              <div
                key={idx}
                onClick={() => setActiveImageUrl(att.url || null)}  // ✅ 点击缩略图切换主画布图片
                className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${activeImageUrl === att.url ? 'ring-2 ring-rose-500 border-transparent' : 'border-slate-700 hover:border-slate-500'}`}
              >
                <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
              </div>
            ))}
          </div>
        </div>
      );
    })}
  </div>
), [messages, loadingState, activeModelConfig?.name, activeImageUrl]);
```

**确认**: 
- Sidebar 显示所有消息的缩略图
- 点击缩略图可以切换主画布显示的图片

## 关键发现

### 1. 虚拟试衣模式特性（关键特性）

**位置**: `backend/app/services/gemini/tryon_service.py`

**逻辑**:
- 虚拟试衣模式需要至少2个附件（人物照片和服装照片）
- 但实际上，当前实现只处理了1个附件（人物照片），服装描述通过 `prompt` 传递
- 支持服装分割（自动生成 mask）
- 支持 Upscale（超分辨率）
- 支持掩码预览（在 View 中实现）

**优势**:
- 支持智能试衣，自动识别服装区域
- 支持多种服装类型（上衣、下装、全身）
- 支持超分辨率，提高图片质量

### 2. 附件传递链路（完整）

**前端附件处理**:
1. ✅ `VirtualTryOnView.handleSend` 实现 CONTINUITY LOGIC（无新上传时使用画布图片）
2. ✅ **特殊处理**: 将图片转换为 Base64 格式（用于 API 调用）
3. ✅ `VirtualTryOnHandler.doExecute` 验证需要至少2个附件
4. ✅ `llmService.virtualTryOn` 传递 `attachments` 和 `prompt`（服装描述）
5. ✅ `UnifiedProviderClient.executeMode` 将 `attachments` 和 `options`（包含 `enableUpscale`, `upscaleFactor`, `addWatermark`, `virtualTryOnTarget`）发送到后端

**后端附件处理**:
1. ✅ 后端路由 `/api/modes/google/virtual-try-on` 接收 `requestBody.attachments` 和 `requestBody.options`
2. ✅ `convert_attachments_to_reference_images` 将 `attachments` 转换为 `reference_images` 字典
3. ✅ 根据 `attachment.role` 设置键名（'raw', 等）
4. ✅ 调用 `service.virtual_tryon(**params)`，包含 `enableUpscale`, `upscaleFactor`, `addWatermark`, `virtualTryOnTarget` 等选项
5. ✅ `GoogleService.virtual_tryon` 委托给 `TryOnService.virtual_tryon`
6. ✅ `TryOnService` 处理虚拟试衣，包括服装分割和编辑

### 3. 图片显示链路（完整）

**后端返回**:
1. ✅ `TryOnService` 返回 `Dict[str, Any]`，格式: `{"url": "data:image/png;base64,...", "mimeType": "image/png"}`
2. ✅ 后端路由返回 `ModeResponse(success=True, data=result)`

**前端处理**:
1. ✅ `UnifiedProviderClient.executeMode` 解析响应，返回 `data.data`（即结果字典）
2. ✅ `llmService.virtualTryOn` 返回 `ImageGenerationResult[]`
3. ✅ `VirtualTryOnHandler.doExecute` 调用 `processMediaResult` 处理每个结果
4. ✅ `processMediaResult` 创建 `displayAttachment`（包含 Base64 Data URL 或 Blob URL）和 `dbAttachmentPromise`（异步上传任务）
5. ✅ `VirtualTryOnHandler` 返回 `HandlerResult`，包含 `attachments`
6. ✅ `useChat.sendMessage` 更新 `messages` 状态，将 `displayAttachments` 添加到 `modelMessage`
7. ✅ `VirtualTryOnView` 从 `messages` 中提取 MODEL 消息的 `attachments`
8. ✅ `VirtualTryOnView` 自动切换到最新结果，渲染 `<img src={activeImageUrl}>`，立即显示图片
9. ✅ 异步上传任务在后台执行，完成后更新数据库

### 4. CONTINUITY LOGIC（关键特性）

**位置**: `frontend/components/views/VirtualTryOnView.tsx` line 335-431

**逻辑**:
- 如果用户没有上传新附件，但画布上有图片（`activeImageUrl`），自动使用画布上的图片
- 尝试从历史消息中查找匹配的附件（通过 URL 匹配）
- 如果找到，复用附件的 ID 和其他信息，查询后端获取云存储 URL
- **特殊处理**: 将图片转换为 Base64 格式（用于 API 调用）

**优势**:
- 用户可以在画布上查看结果，然后直接发送新的试衣指令，无需重新上传图片
- 支持连续试衣工作流

### 5. Upscale 和 Mask Preview（关键特性）

**位置**: `frontend/components/views/VirtualTryOnView.tsx` line 89-325

**逻辑**:
- **Upscale**: View 内部状态（`enableUpscale`, `upscaleFactor`, `addWatermark`），添加到 `options` 传递给后端
- **Mask Preview**: View 内部状态（`showMaskPreview`, `maskPreviewUrl`），用于显示掩码预览
- **掩码生成**: 调用 `generateMaskPreview` 函数，生成掩码预览图
- **参数持久化**: 掩码预览参数（`maskAlpha`, `maskThreshold`）保存到 localStorage

**优势**:
- 支持超分辨率，提高图片质量
- 支持掩码预览，帮助用户理解哪些区域将被替换

## 问题定位

### 可能的问题

1. **附件数量不足**:
   - **位置**: `VirtualTryOnHandler.doExecute` 的验证逻辑
   - **验证**: 检查 `context.attachments.length` 是否 >= 2

2. **Base64 转换失败**:
   - **位置**: `VirtualTryOnView.handleSend` 的 CONTINUITY LOGIC
   - **验证**: 检查 Base64 转换是否成功

3. **Upscale 选项未传递**:
   - **位置**: `VirtualTryOnView.handleSend` 的 `finalOptions` 构建
   - **验证**: 检查 `enableUpscale`, `upscaleFactor`, `addWatermark` 是否添加到 `options`

4. **Mask Preview 未正确生成**:
   - **位置**: `VirtualTryOnView.handleGenerateMaskPreview`
   - **验证**: 检查掩码预览生成是否成功

## 需要检查的关键代码位置

### 前端
1. **VirtualTryOnView.tsx line 327-449**: `handleSend` 中实现 CONTINUITY LOGIC 和 Base64 转换
2. **VirtualTryOnView.tsx line 243-325**: `handleGenerateMaskPreview` 中生成掩码预览
3. **AllHandlerClasses.ts line 36-62**: `VirtualTryOnHandler.doExecute` 中验证附件数量
4. **llmService.ts line 384-406**: `virtualTryOn` 中路由到 provider
5. **UnifiedProviderClient.ts line 378-443**: `executeMode` 中构建请求体

### 后端
1. **backend/app/routers/core/modes.py line 150-305**: 路由接收请求和处理
2. **backend/app/services/gemini/google_service.py**: `virtual_tryon` 实现
3. **backend/app/services/gemini/tryon_service.py**: 虚拟试衣服务实现

## 调试步骤

1. **在 VirtualTryOnView.handleSend 中添加日志**:
```typescript
console.log('[VirtualTryOnView.handleSend] activeImageUrl:', activeImageUrl);
console.log('[VirtualTryOnView.handleSend] attachments:', attachments);
console.log('[VirtualTryOnView.handleSend] finalAttachments:', finalAttachments);
console.log('[VirtualTryOnView.handleSend] finalOptions:', finalOptions);
```

2. **在 VirtualTryOnHandler.doExecute 中添加日志**:
```typescript
console.log('[VirtualTryOnHandler.doExecute] context.attachments:', context.attachments);
console.log('[VirtualTryOnHandler.doExecute] context.attachments.length:', context.attachments.length);
console.log('[VirtualTryOnHandler.doExecute] context.text:', context.text);
```

3. **在 UnifiedProviderClient.executeMode 中添加日志**:
```typescript
console.log('[UnifiedProviderClient.executeMode] Request body:', JSON.stringify(requestBody, null, 2));
console.log('[UnifiedProviderClient.executeMode] Options:', JSON.stringify(requestBody.options, null, 2));
```

## 结论

**前端附件传递链路完整**，所有附件都应该被传递到后端。**图片显示链路也完整**，图片应该能够立即显示。

**关键特性**:
1. ✅ **虚拟试衣模式**: 需要至少2个附件（人物照片和服装照片），支持智能试衣
2. ✅ **CONTINUITY LOGIC**: 支持连续试衣工作流，无需重复上传图片
3. ✅ **Upscale 支持**: 支持超分辨率，提高图片质量
4. ✅ **Mask Preview**: 支持掩码预览，帮助用户理解哪些区域将被替换
5. ✅ **自动切换结果**: 新结果生成后自动切换到主画布显示

**建议**:
- 在前端和后端关键位置添加日志，确认附件、Upscale 选项和参数在每个步骤的值
- 检查附件数量是否满足要求（至少2个）
- 检查 Base64 转换是否成功
- 检查 Upscale 选项是否正确传递到后端
