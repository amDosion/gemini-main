# Google 提供商 Edit 模式流程分析

**日期**: 2026-01-XX  
**版本**: v1.0  
**范围**: Google 提供商在 edit 模式下的完整端到端流程

---

## 一、前端流程

### 1. 用户操作触发
- **位置**: `frontend/components/views/ImageEditView.tsx`
- **入口**: `handleSend` 函数（第352行）
- **触发**: 用户在编辑界面输入提示词并点击发送

### 2. 附件处理
- **位置**: `frontend/components/views/ImageEditView.tsx:380`
- **函数**: `processUserAttachments()` 
- **功能**: 
  - 处理用户上传的附件
  - 将画布上的图片转换为附件格式
  - 准备 `referenceImages` 对象（包含 `raw`、`mask` 等）

### 3. 调用 onSend
- **位置**: `frontend/components/views/ImageEditView.tsx:390`
- **参数**: `onSend(text, options, finalAttachments, mode)`
- **mode**: `'image-edit'`

### 4. Handler 路由
- **位置**: `frontend/App.tsx` (模式路由逻辑)
- **Handler**: `ImageEditHandler` 被选中
- **位置**: `frontend/hooks/handlers/ImageEditHandlerClass.ts`

### 5. Handler 执行
- **位置**: `frontend/hooks/handlers/ImageEditHandlerClass.ts:11`
- **调用**: `llmService.editImage(context.text, context.attachments)`
- **参数**:
  - `context.text`: 用户输入的编辑提示词
  - `context.attachments`: 处理后的附件数组

### 6. LLMService 处理
- **位置**: `frontend/services/llmService.ts:191`
- **函数**: `editImage(prompt, referenceImages)`
- **验证**:
  - 检查 Provider 是否配置
  - 检查模型是否选择
  - 验证 prompt 和 referenceImages
- **调用**: `this.currentProvider.editImage(...)`
- **Provider**: 通过 `LLMFactory.getProvider()` 获取，对于 Google 是 `UnifiedProviderClient`

### 7. UnifiedProviderClient 调用
- **位置**: `frontend/services/providers/UnifiedProviderClient.ts:393`
- **函数**: `editImage(modelId, prompt, referenceImages, options, baseUrl)`
- **请求构建**:
  - URL: `/api/generate/${this.id}/image/edit` (this.id = 'google')
  - Method: POST
  - Headers: Authorization Bearer token
  - Body: 
    ```json
    {
      "modelId": "...",
      "prompt": "...",
      "referenceImages": {
        "raw": "...",  // Base64 编码的图片
        "mask": "...", // 可选
        ...
      },
      "options": {
        "edit_mode": "...",
        "aspect_ratio": "...",
        "number_of_images": 1,
        ...
      }
    }
    ```

---

## 二、后端流程

### 1. API 路由接收
- **位置**: `backend/app/routers/generate.py:417`
- **端点**: `POST /api/generate/{provider}/image/edit`
- **函数**: `edit_image(provider, request_body, request, db)`
- **验证**:
  - 检查 provider 是否为 'google'
  - 用户认证（`require_user_id`）
  - 记录请求日志

### 2. 获取 API Key
- **位置**: `backend/app/routers/generate.py:478`
- **函数**: `get_api_key(provider, None, user_id, db)`
- **来源**: 从数据库 `config_profiles` 表读取用户配置的 API Key

### 3. 创建 Provider Service
- **位置**: `backend/app/routers/generate.py:490`
- **函数**: `ProviderFactory.create(provider='google', api_key, user_id, db)`
- **返回**: `GoogleService` 实例

### 4. GoogleService.edit_image
- **位置**: `backend/app/services/gemini/google_service.py:180`
- **函数**: `edit_image(prompt, model, reference_images, **kwargs)`
- **委托**: 调用 `self.image_edit_coordinator.get_editor()`

### 5. ImageEditCoordinator 协调
- **位置**: `backend/app/services/gemini/image_edit_coordinator.py:76`
- **函数**: `get_editor()`
- **配置加载**:
  - 优先从数据库 `imagen_configs` 表读取用户配置
  - 回退到环境变量
- **API 模式选择**:
  - `vertex_ai`: 使用 Vertex AI（支持完整编辑功能）
  - `gemini_api`: 使用 Gemini API（不支持编辑，会抛出 NotSupportedError）
- **创建编辑器**:
  - Vertex AI: `VertexAIImageEditor`
  - Gemini API: `GeminiAPIImageEditor`（仅用于错误提示）

### 6. VertexAIImageEditor 执行编辑
- **位置**: `backend/app/services/gemini/image_edit_vertex_ai.py:146`
- **函数**: `edit_image(prompt, reference_images, config)`
- **步骤**:
  1. **模型映射** (第178行):
     - `nano-banana-pro-preview` → `imagen-3.0-capability-001`
     - `gemini-3-pro-image-preview` → `imagen-3.0-capability-001`
     - `gemini-2.5-flash-image` → `imagen-3.0-capability-001`
     - 其他模型映射到 `imagen-3.0-capability-001`
  
  2. **参数验证**:
     - `validate_edit_mode()`: 验证编辑模式
     - `validate_reference_images()`: 验证参考图片
     - `validate_aspect_ratio()`: 验证宽高比
     - 其他参数验证
  
  3. **构建配置** (第169行):
     - `edit_mode`: 'inpaint' | 'outpaint' | 'product' | 'remove-background'
     - `number_of_images`: 生成图片数量
     - `aspect_ratio`: 宽高比
     - `guidance_scale`: 引导强度
     - `output_mime_type`: 输出格式
     - `safety_filter_level`: 安全过滤级别
     - `person_generation`: 人物生成设置
  
  4. **构建参考图片** (第172行):
     - 解码 Base64 图片
     - 转换为 Vertex AI SDK 格式
     - 支持 6 种参考图片类型:
       - `raw`: 基础图片（必需）
       - `mask`: 遮罩图片（可选）
       - `control`: 控制图片（可选）
       - `style`: 风格参考（可选）
       - `subject`: 主体参考（可选）
       - `content`: 内容参考（可选）
  
  5. **调用 Vertex AI API** (第188行):
     ```python
     response = self._client.models.edit_image(
         model=vertex_model,  # 'imagen-3.0-capability-001'
         prompt=prompt,
         reference_images=ref_images,
         config=edit_config
     )
     ```
  
  6. **处理响应** (第199行):
     - 提取生成的图片
     - 编码为 Base64
     - 返回图片列表

### 7. 返回结果
- **位置**: `backend/app/routers/generate.py:516`
- **响应格式**:
  ```json
  {
    "images": [
      {
        "url": "data:image/png;base64,...",
        "base64": "...",
        "metadata": {...}
      }
    ],
    "metadata": {
      "model": "...",
      "prompt": "...",
      "timestamp": "...",
      "api_mode": "vertex_ai",
      "reference_image_types": ["raw", "mask"]
    }
  }
  ```

---

## 三、前端接收结果

### 1. UnifiedProviderClient 接收响应
- **位置**: `frontend/services/providers/UnifiedProviderClient.ts:487`
- **处理**: 解析 JSON 响应，提取 `images` 数组

### 2. Handler 处理结果
- **位置**: `frontend/hooks/handlers/ImageEditHandlerClass.ts:14`
- **处理**: 
  - `processMediaResult()`: 处理媒体结果
  - 创建 `displayAttachments`
  - 准备上传任务

### 3. 更新 UI
- **位置**: `frontend/components/views/ImageEditView.tsx`
- **显示**: 
  - 在主画布显示编辑后的图片
  - 在侧边栏显示历史记录
  - 支持对比模式（原图 vs 编辑后）

---

## 四、关键配置

### 1. 编辑模式 (edit_mode)
- **inpaint**: 局部修复（需要 mask）
- **outpaint**: 扩展画布
- **product**: 产品编辑
- **remove-background**: 移除背景

### 2. 支持的模型
- `imagen-3.0-capability-001` (直接支持)
- `nano-banana-pro-preview` (映射到 imagen-3.0-capability-001)
- `gemini-3-pro-image-preview` (映射到 imagen-3.0-capability-001)
- `gemini-2.5-flash-image` (映射到 imagen-3.0-capability-001)

### 3. 宽高比选项
- **位置**: `frontend/controls/constants.ts`
- **Google Edit 模式**: `GOOGLE_EDIT_ASPECT_RATIOS`
- 支持: 1:1, 4:3, 3:4, 16:9, 9:16, 21:9, 9:21

### 4. 分辨率选项
- **1K**: Standard (1024x1024)
- **2K**: High (2048x2048)
- **4K**: Ultra (4096x4096) - 仅 Google 支持

---

## 五、错误处理

### 1. 前端错误
- Provider 未配置
- 模型未选择
- 缺少 raw 参考图片
- 网络请求失败

### 2. 后端错误
- Provider 不是 'google'
- API Key 未配置
- Vertex AI 配置不完整
- 内容策略违规 (422)
- 模型不支持 (400)

### 3. Vertex AI 错误
- 模型映射失败
- 参数验证失败
- API 调用失败
- 响应处理失败

---

## 六、数据流图

```
用户输入提示词 + 上传图片
    ↓
ImageEditView.handleSend()
    ↓
processUserAttachments() - 处理附件
    ↓
onSend() - 传递到 App.tsx
    ↓
ImageEditHandler.doExecute()
    ↓
llmService.editImage()
    ↓
UnifiedProviderClient.editImage()
    ↓
POST /api/generate/google/image/edit
    ↓
generate.py:edit_image()
    ↓
GoogleService.edit_image()
    ↓
ImageEditCoordinator.get_editor()
    ↓
VertexAIImageEditor.edit_image()
    ↓
Vertex AI API (edit_image)
    ↓
返回编辑后的图片
    ↓
前端显示结果
```

---

## 七、关键文件清单

### 前端
1. `frontend/components/views/ImageEditView.tsx` - 编辑视图
2. `frontend/hooks/handlers/ImageEditHandlerClass.ts` - 编辑处理器
3. `frontend/services/llmService.ts` - LLM 服务
4. `frontend/services/providers/UnifiedProviderClient.ts` - 统一提供商客户端
5. `frontend/controls/modes/ImageEditControls.tsx` - 编辑控件

### 后端
1. `backend/app/routers/generate.py` - 生成路由
2. `backend/app/services/gemini/google_service.py` - Google 服务
3. `backend/app/services/gemini/image_edit_coordinator.py` - 编辑协调器
4. `backend/app/services/gemini/image_edit_vertex_ai.py` - Vertex AI 编辑器
5. `backend/app/services/gemini/image_edit_base.py` - 编辑器基类

---

## 八、注意事项

1. **API 模式**: 只有 Vertex AI 模式支持编辑，Gemini API 模式会抛出错误
2. **模型映射**: 前端选择的模型会被映射到 Vertex AI 支持的模型
3. **参考图片**: `raw` 是必需的，其他类型可选
4. **认证**: 使用 JWT token + Cookie 双重认证
5. **API Key**: 从数据库读取，不在前端传递
6. **错误处理**: 完整的错误处理和日志记录
7. **性能**: 支持图片上传到 Google Files API 以减少数据传输

---

## 九、代码引用示例

### 前端关键代码

```393:497:frontend/services/providers/UnifiedProviderClient.ts
  async editImage(
    modelId: string,
    prompt: string,
    referenceImages: Record<string, any>,
    options: ChatOptions,
    baseUrl: string
  ): Promise<ImageGenerationResult[]> {
    try {
      // ✅ 输入验证
      if (!modelId || typeof modelId !== 'string') {
        throw new Error('Invalid modelId: must be a non-empty string');
      }
      if (!prompt || typeof prompt !== 'string') {
        throw new Error('Invalid prompt: must be a non-empty string');
      }
      if (!referenceImages || typeof referenceImages !== 'object') {
        throw new Error('Invalid referenceImages: must be an object');
      }
      if (!referenceImages.raw) {
        throw new Error('Invalid referenceImages: must include "raw" base image');
      }
      
      const requestBody = {
        modelId,
        prompt,
        referenceImages,
        options: {
          ...options,
          baseUrl: baseUrl || options.baseUrl
        }
        // ✅ API Key 由后端管理，不在前端传递（安全性）
      };
      
      // ✅ 构建请求头，添加 Authorization header
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };
      const token = getAccessToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      console.debug('[UnifiedProviderClient] Sending image edit request:', {
        url: `/api/generate/${this.id}/image/edit`,
        modelId,
        promptLength: prompt.length,
        referenceImageTypes: Object.keys(referenceImages)
      });
      
      const response = await fetch(`/api/generate/${this.id}/image/edit`, {
        method: 'POST',
        headers,
        credentials: 'include',  // 发送认证 Cookie（向后兼容）
        body: JSON.stringify(requestBody)
      });
      
      if (!response.ok) {
        // ✅ 详细的错误处理
        const contentType = response.headers.get('content-type');
        let errorMessage = `Image editing failed (${response.status})`;
        
        try {
          if (contentType?.includes('application/json')) {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.error || errorMessage;
          } else {
            errorMessage = await response.text() || errorMessage;
          }
        } catch (parseError) {
          console.error('[UnifiedProviderClient] Error parsing error response:', parseError);
        }
        
        // ✅ 根据 HTTP 状态码提供友好的错误信息
        switch (response.status) {
          case 400:
            throw new Error(`Invalid request: ${errorMessage}`);
          case 401:
            throw new Error('Authentication required. Please log in again.');
          case 404:
            throw new Error(`Provider "${this.id}" not found or does not support image editing.`);
          case 422:
            throw new Error(`Content policy violation: ${errorMessage}`);
          case 429:
            throw new Error('Rate limit exceeded. Please try again later.');
          case 500:
          case 502:
          case 503:
          case 504:
            throw new Error(`Server error: ${errorMessage}. Please try again later.`);
          default:
            throw new Error(errorMessage);
        }
      }
      
      const data = await response.json();
      console.debug('[UnifiedProviderClient] Image edit response received:', {
        imagesCount: data.images?.length || 0
      });
      
      return data.images || [];
    } catch (error) {
      console.error(`[UnifiedProviderClient] Image editing error for ${this.id}:`, error);
      throw error;
    }
  }
```

### 后端关键代码

```417:526:backend/app/routers/generate.py
@router.post("/{provider}/image/edit")
async def edit_image(
    provider: str,
    request_body: ImageEditRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Image editing API endpoint for Google Imagen.
    
    Currently only supports Google provider with Vertex AI configuration.
    Gemini API does not support image editing.
    
    Args:
        provider: Provider name (must be 'google')
        request_body: Image edit request with model, prompt, reference images, and options
        request: FastAPI request object for user authentication
        db: Database session for loading user configuration
    
    Returns:
        Dictionary with edited images and metadata
    
    Raises:
        HTTPException: If provider is not supported, editing fails, or content policy is violated
    """
    try:
        # Validate provider
        if provider != 'google':
            raise HTTPException(
                status_code=400,
                detail=f"Image editing is not supported for provider: {provider}. Only Google (Vertex AI) supports image editing."
            )
        
        # Authenticate user
        from ..core.user_context import require_user_id
        user_id = require_user_id(request)
        
        logger.info(
            f"[Generate] ==================== Image Editing Request ===================="
        )
        logger.info(
            f"[Generate] Provider: {provider}"
        )
        logger.info(
            f"[Generate] User ID: {user_id}"
        )
        logger.info(
            f"[Generate] Model: {request_body.modelId}"
        )
        logger.info(
            f"[Generate] Prompt: {request_body.prompt[:100]}{'...' if len(request_body.prompt) > 100 else ''}"
        )
        logger.info(
            f"[Generate] Reference Images: {list(request_body.referenceImages.keys())}"
        )
        if request_body.options:
            logger.info(
                f"[Generate] Options: {request_body.options}"
            )
        
        # Get API key with user-based credential retrieval
        api_key = await get_api_key(provider, None, user_id, db)
        
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="No API key configured. Please configure your API key in settings."
            )
        
        # Create provider service with user context
        from ..services.provider_factory import ProviderFactory
        
        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                timeout=120.0,
                user_id=user_id,
                db=db
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Call edit_image method
        result = await service.edit_image(
            prompt=request_body.prompt,
            model=request_body.modelId,
            reference_images=request_body.referenceImages,
            **(request_body.options or {})
        )
        
        # Get current API mode for metadata
        api_mode = service.image_edit_coordinator.get_current_api_mode()
        
        logger.info(
            f"[Generate] Image editing successful: provider={provider}, user={user_id}, "
            f"count={len(result)}, model={request_body.modelId}, api_mode={api_mode}"
        )
        
        return {
            "images": result,
            "metadata": {
                "model": request_body.modelId,
                "prompt": request_body.prompt,
                "timestamp": datetime.utcnow().isoformat(),
                "api_mode": api_mode,
                "reference_image_types": list(request_body.referenceImages.keys())
            }
        }
```

---

## 十、相关文档

- [Google Gemini 图片编辑流程（端到端）](./google-gemini-image-edit-flow.md)
- [Image Edit 404 错误完整修复总结](../../docs/reports/image-edit-404-fix-final.md)
- [Image Edit Mode 404 Error - Final Diagnosis](../../docs/reports/image-edit-404-final-diagnosis.md)
