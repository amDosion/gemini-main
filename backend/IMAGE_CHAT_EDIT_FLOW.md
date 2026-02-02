# Image Chat Edit 完整端到端流程图

## 请求示例
- Provider: `google`
- Mode: `image-chat-edit`
- Model: `gemini-3-pro-image-preview`
- Prompt: `移除帽子`
- Attachments: 1个图片

---

## 流程图

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              前端 (Frontend)                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  1. 用户操作                                                                             │
│  ├─ 选择图片 → 设置 attachments                                                          │
│  ├─ 输入提示词 → "移除帽子"                                                               │
│  └─ 点击发送                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  2. ImageEditHandler.doExecute()                                                        │
│  frontend/hooks/handlers/ImageEditHandlerClass.ts                                       │
│                                                                                          │
│  ├─ 构建 referenceImages: { raw: Attachment }                                           │
│  ├─ 构建 editOptions: { frontendSessionId, sessionId, messageId, ... }                  │
│  └─ 调用 llmService.editImage(prompt, referenceImages, mode, options)                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  3. llmService.editImage()                                                              │
│  frontend/services/llmService.ts                                                        │
│                                                                                          │
│  └─ 调用 UnifiedProviderClient.editImage(modelId, prompt, referenceImages, options)     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  4. UnifiedProviderClient.editImage() → executeMode()                                   │
│  frontend/services/providers/UnifiedProviderClient.ts                                   │
│                                                                                          │
│  ├─ mode = 'image-chat-edit'                                                            │
│  ├─ 构建请求体 ModeRequest:                                                              │
│  │   {                                                                                   │
│  │     modelId: "gemini-3-pro-image-preview",                                           │
│  │     prompt: "移除帽子",                                                               │
│  │     attachments: [{ id, mimeType, url, ... }],                                       │
│  │     options: { frontendSessionId, messageId, ... }                                   │
│  │   }                                                                                   │
│  └─ POST /api/modes/google/image-chat-edit                                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ HTTP POST
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              后端 (Backend)                                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  5. CaseConversionMiddleware                                                            │
│  backend/app/middleware/case_conversion_middleware.py                                   │
│                                                                                          │
│  ├─ 将请求体 JSON 从 camelCase → snake_case                                              │
│  │   modelId → model_id                                                                  │
│  │   frontendSessionId → frontend_session_id                                            │
│  │   messageId → message_id                                                              │
│  └─ 将查询参数从 camelCase → snake_case                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  6. [步骤1] 获取提供商凭证 (3.87ms)                                                       │
│  backend/app/routers/core/modes.py → handle_mode()                                      │
│                                                                                          │
│  └─ get_provider_credentials(provider='google', ...)                                    │
│      └─ backend/app/core/credential_manager.py                                          │
│          └─ 从 active profile 'Google Gemini Config' 获取 API key                       │
│          └─ api_url: https://generativelanguage.googleapis.com/v1beta                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  7. [步骤2] 创建提供商服务 (0.20ms)                                                       │
│  backend/app/routers/core/modes.py                                                      │
│                                                                                          │
│  └─ ProviderFactory.create(provider='google', api_key, api_url, user_id, db)            │
│      └─ backend/app/services/common/provider_factory.py                                 │
│          └─ ✅ 使用缓存服务 → GoogleService 实例                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  8. [步骤3-4] 获取服务方法名 & 检查支持                                                   │
│  backend/app/routers/core/modes.py                                                      │
│                                                                                          │
│  ├─ get_service_method('image-chat-edit') → 'edit_image'                                │
│  │   └─ backend/app/core/mode_method_mapper.py                                          │
│  └─ hasattr(GoogleService, 'edit_image') → ✅ True                                      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  9. [步骤5] 准备调用参数 (2.25ms)                                                         │
│  backend/app/routers/core/modes.py                                                      │
│                                                                                          │
│  ├─ 基础参数:                                                                            │
│  │   model = "gemini-3-pro-image-preview"                                               │
│  │   prompt = "移除帽子"                                                                 │
│  │   mode = "image-chat-edit"                                                           │
│  │                                                                                       │
│  ├─ 从 options 添加参数 (14个):                                                          │
│  │   enable_search, enable_thinking, number_of_images,                                  │
│  │   image_aspect_ratio, image_resolution, frontend_session_id,                         │
│  │   session_id, message_id, output_mime_type, enhance_prompt, ...                      │
│  │                                                                                       │
│  ├─ 处理 attachments → reference_images:                                                │
│  │   ├─ 查询数据库获取附件信息 (MessageAttachment)                                       │
│  │   ├─ 如果 upload_status='completed' → 使用云存储 URL                                  │
│  │   └─ 否则使用 temp_url (Base64)                                                       │
│  │                                                                                       │
│  └─ 最终参数 (18个):                                                                     │
│      [model, prompt, base_url, enable_search, enable_thinking,                          │
│       number_of_images, image_aspect_ratio, image_resolution,                           │
│       frontend_session_id, session_id, message_id, output_mime_type,                    │
│       enhance_prompt, enhance_prompt_model, enable_code_execution,                      │
│       persona, mode, reference_images]                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  10. [步骤6] 调用服务方法                                                                 │
│  backend/app/routers/core/modes.py                                                      │
│                                                                                          │
│  └─ await GoogleService.edit_image(**params)                                            │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  11. GoogleService.edit_image()                                                         │
│  backend/app/services/gemini/google_service.py                                          │
│                                                                                          │
│  └─ 委托给 ImageEditCoordinator.edit_image(prompt, model, reference_images, mode, ...)  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  12. ImageEditCoordinator.edit_image() - 路由分发                                        │
│  backend/app/services/gemini/coordinators/image_edit_coordinator.py                     │
│                                                                                          │
│  路由逻辑:                                                                               │
│  ├─ mode='image-chat-edit' → ConversationalImageEditService ✅ (当前路径)               │
│  ├─ mode='image-mask-edit' → MaskEditService                                            │
│  ├─ mode='image-inpainting' → InpaintingService                                         │
│  ├─ mode='image-background-edit' → BackgroundEditService                                │
│  └─ mode='image-recontext' → RecontextService                                           │
│                                                                                          │
│  当前: mode='image-chat-edit'                                                           │
│  └─ 创建 ConversationalImageEditService 实例                                            │
│      └─ 调用 conversational_service.edit_image(prompt, model, reference_images, ...)    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  13. ConversationalImageEditService.edit_image()                                        │
│  backend/app/services/gemini/geminiapi/conversational_image_edit_service.py             │
│                                                                                          │
│  ├─ 13.1 检查/创建 Chat 会话                                                             │
│  │   ├─ 使用 frontend_session_id 查找现有会话                                            │
│  │   ├─ 如果存在 → 使用现有 chat session (d9d2bfd0-8054-45e9-ae51-bb80b873b36e)         │
│  │   └─ 如果不存在 → 创建新的 chat session                                               │
│  │                                                                                       │
│  ├─ 13.2 处理附件                                                                        │
│  │   └─ 转换 reference_images → 图片数据 (Base64/URL/HTTP下载)                          │
│  │                                                                                       │
│  ├─ 13.3 ⭐ AI 增强提示词 (如果 enhance_prompt=true)                                     │
│  │   ├─ 检查 config.enhance_prompt 是否为 true                                          │
│  │   ├─ 获取增强模型: config.enhance_prompt_model 或默认 'gemini-2.5-flash'             │
│  │   ├─ 调用 _enhance_prompt_two_stage(prompt, model_hint)                              │
│  │   │   ├─ 使用文本模型 (非图片模型) 进行提示词改写                                      │
│  │   │   ├─ System Prompt: "You are a professional edit prompt enhancer..."             │
│  │   │   ├─ User Prompt: "Rewrite the following image edit instruction..."              │
│  │   │   └─ 调用 client.models.generate_content() 获取增强后的提示词                     │
│  │   └─ 如果成功 → 用增强后的提示词替换原始 prompt                                        │
│  │       └─ enhanced_prompt_text 保存原始增强结果，用于返回给前端显示                     │
│  │                                                                                       │
│  ├─ 13.4 构建 chat_config                                                               │
│  │   ├─ response_modalities: [TEXT, IMAGE]                                              │
│  │   ├─ image_config: { aspect_ratio: '1:1', image_size: '1K' }                         │
│  │   ├─ ⭐ thinking_config: (根据 enable_thinking 和模型支持情况)                        │
│  │   │   ├─ 检查 _supports_thinking(model_name):                                        │
│  │   │   │   └─ 只有 gemini-3 系列模型支持 thinking                                      │
│  │   │   │       ├─ gemini-3-pro-image-preview: ✅ 支持                                  │
│  │   │   │       ├─ gemini-3-flash-preview: ✅ 支持 (但不能生成图片)                     │
│  │   │   │       ├─ gemini-2.5-flash-image: ❌ 不支持 (400 error)                        │
│  │   │   │       └─ gemini-2.0-flash-exp: ❌ 不支持                                      │
│  │   │   └─ 如果支持 → ThinkingConfig(include_thoughts=True)                            │
│  │   │       └─ 否则 → None (不启用思考过程)                                             │
│  │   ├─ safety_settings: 已禁用 (避免 IMAGE_RECITATION 错误)                             │
│  │   ├─ temperature: 1.0 (较高温度减少 RECITATION)                                       │
│  │   └─ automatic_function_calling: disabled (避免 MALFORMED_FUNCTION_CALL)             │
│  │                                                                                       │
│  ├─ 13.5 创建 Chat 对象 (无历史) ⭐ 关键设计                                              │
│  │   └─ client.aio.chats.create(model, config)                                          │
│  │       ├─ ✅ 简化设计：不加载历史记录                                                  │
│  │       ├─ 设计原则：前端传什么图片 → AI 就编辑什么图片                                 │
│  │       ├─ 图片来源由前端控制（用户上传 或 上一轮生成的图片）                           │
│  │       ├─ 优势：                                                                       │
│  │       │   ├─ 避免不必要的数据库查询                                                   │
│  │       │   ├─ 避免重复的图片数据传递给 API                                             │
│  │       │   └─ 减少 token 浪费和延迟                                                    │
│  │       └─ AFC is enabled with max remote calls: 10                                    │
│  │                                                                                       │
│  ├─ 13.6 构建消息内容 (message_parts)                                                    │
│  │   ├─ 图片 Part: genai_types.Part.from_bytes(image_bytes, mime_type)                  │
│  │   │   └─ 支持: Base64 Data URL / HTTP URL (自动下载) / Google File URI               │
│  │   └─ 文本 Part: prompt (可能是增强后的提示词)                                         │
│  │                                                                                       │
│  ├─ 13.7 发送消息到 Gemini API                                                           │
│  │   └─ response = await chat.send_message(message_to_send, config=send_config)         │
│  │       ├─ 调用 Google Gemini API                                                       │
│  │       └─ 等待响应 (可能需要几秒到几十秒)                                               │
│  │                                                                                       │
│  ├─ 13.8 解析响应                                                                        │
│  │   ├─ ⭐ 提取 thoughts (思考过程) - 如果启用了 thinking                                │
│  │   │   ├─ 遍历 response.parts                                                          │
│  │   │   ├─ 检查 part.thought == True                                                    │
│  │   │   ├─ 提取思考内容:                                                                │
│  │   │   │   ├─ 文本思考: part.text → { type: 'text', content: '...' }                  │
│  │   │   │   └─ 图片思考: part.inline_data → { type: 'image', content: 'data:...' }     │
│  │   │   └─ 收集到 thoughts 数组                                                         │
│  │   │                                                                                   │
│  │   ├─ 提取 text (文本响应)                                                             │
│  │   │   └─ 非 thought 的文本 part → text_responses                                      │
│  │   │                                                                                   │
│  │   └─ 提取 images (编辑后的图片)                                                       │
│  │       ├─ 优先使用 part.as_image() 方法                                                │
│  │       └─ 回退到 part.inline_data → Base64 图片                                        │
│  │                                                                                       │
│  └─ 13.9 返回结果                                                                        │
│      └─ List[Dict]: [{                                                                   │
│            url: "data:image/png;base64,...",                                             │
│            mime_type: "image/png",                                                       │
│            thoughts: [{ type, content }, ...],  // ⭐ 思考过程                            │
│            text: "...",                          // 文本响应                              │
│            enhanced_prompt: "..."                // ⭐ 增强后的提示词 (如果启用)          │
│          }]                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  14. [步骤7] 处理图片生成/编辑结果                                                        │
│  backend/app/routers/core/modes.py                                                      │
│                                                                                          │
│  ├─ 使用 AttachmentService 处理返回的图片                                                │
│  ├─ 创建附件记录 (MessageAttachment)                                                     │
│  ├─ 启动异步上传任务 (如果配置了云存储)                                                   │
│  └─ 返回处理后的结果:                                                                    │
│      {                                                                                   │
│        success: true,                                                                    │
│        data: [{                                                                          │
│          url: "data:image/png;base64,..." 或 "/api/temp-images/{id}",                   │
│          mimeType: "image/png",                                                          │
│          attachmentId: "xxx",                                                            │
│          uploadStatus: "pending" | "completed",                                          │
│          taskId: "xxx",                                                                  │
│          thoughts: [...],                                                                │
│          text: "...",                                                                    │
│          enhancedPrompt: "..."                                                           │
│        }],                                                                               │
│        provider: "google",                                                               │
│        mode: "image-chat-edit"                                                           │
│      }                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  15. CaseConversionMiddleware (响应)                                                    │
│  backend/app/middleware/case_conversion_middleware.py                                   │
│                                                                                          │
│  └─ 将响应体 JSON 从 snake_case → camelCase                                              │
│      attachment_id → attachmentId                                                        │
│      upload_status → uploadStatus                                                        │
│      mime_type → mimeType                                                                │
│      task_id → taskId                                                                    │
│      enhanced_prompt → enhancedPrompt                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          │ HTTP Response
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              前端 (Frontend) - 响应处理                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  16. UnifiedProviderClient.executeMode() - 响应处理                                      │
│  frontend/services/providers/UnifiedProviderClient.ts                                   │
│                                                                                          │
│  └─ 解析响应 JSON → ImageGenerationResult[]                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  17. ImageEditHandler.doExecute() - 结果处理                                             │
│  frontend/hooks/handlers/ImageEditHandlerClass.ts                                       │
│                                                                                          │
│  ├─ 提取 thoughts, textResponse, enhancedPrompt                                         │
│  ├─ 构建 displayAttachments (用于 UI 显示)                                              │
│  ├─ 启动 uploadTask (处理用户上传的附件)                                                 │
│  └─ 返回 HandlerResult:                                                                  │
│      {                                                                                   │
│        content: "移除帽子",                                                              │
│        attachments: displayAttachments,                                                  │
│        thoughts: [...],                                                                  │
│        textResponse: "...",                                                              │
│        enhancedPrompt: "..."                                                             │
│      }                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  18. UI 更新                                                                             │
│  frontend/components/views/ImageEditView.tsx (或 ChatView.tsx)                          │
│                                                                                          │
│  ├─ 显示编辑后的图片                                                                     │
│  ├─ 显示思考过程 (ThinkingBlock)                                                         │
│  ├─ 显示增强提示词 (如果有)                                                              │
│  └─ 更新会话消息列表                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 关键文件路径

### 前端
| 文件 | 职责 |
|------|------|
| `frontend/hooks/handlers/ImageEditHandlerClass.ts` | 图片编辑处理器，构建请求参数 |
| `frontend/services/llmService.ts` | LLM 服务入口 |
| `frontend/services/providers/UnifiedProviderClient.ts` | 统一 API 客户端，发送 HTTP 请求 |

### 后端
| 文件 | 职责 |
|------|------|
| `backend/app/middleware/case_conversion_middleware.py` | 大小写转换中间件 |
| `backend/app/routers/core/modes.py` | 统一模式路由，参数准备 |
| `backend/app/core/credential_manager.py` | 凭证管理 |
| `backend/app/services/common/provider_factory.py` | 提供商工厂 |
| `backend/app/core/mode_method_mapper.py` | 模式→方法映射 |
| `backend/app/services/gemini/google_service.py` | Google 服务主协调器 |
| `backend/app/services/gemini/coordinators/image_edit_coordinator.py` | 图片编辑协调器，路由分发 |
| `backend/app/services/gemini/geminiapi/conversational_image_edit_service.py` | 对话式图片编辑服务 |
| `backend/app/services/gemini/common/chat_session_manager.py` | Chat 会话管理 |

---

## 数据流转

```
前端 Attachment
    ↓
{ id, mimeType, url, ... }
    ↓ (camelCase)
POST /api/modes/google/image-chat-edit
    ↓
CaseConversionMiddleware (camelCase → snake_case)
    ↓
{ id, mime_type, url, ... }
    ↓
modes.py → convert_attachments_to_reference_images()
    ↓
reference_images = { 'raw': { 'url': '...', 'attachment_id': '...', 'mime_type': '...' } }
    ↓
GoogleService.edit_image()
    ↓
ImageEditCoordinator.edit_image()
    ↓
ConversationalImageEditService.edit_image()
    ↓
Google Gemini API (chat.send_message)
    ↓
响应: { parts: [image, text, thoughts] }
    ↓
解析 → List[Dict]
    ↓
modes.py → AttachmentService 处理
    ↓
CaseConversionMiddleware (snake_case → camelCase)
    ↓
前端接收 ImageGenerationResult[]
```


---

## ⭐ 高级功能详解

### 1. AI 增强提示词 (enhance_prompt)

**前端控件**: `frontend/controls/modes/google/ImageEditControls.tsx`
- 开关: `controls.enhancePrompt` (boolean)
- 模型选择: `controls.enhancePromptModel` (string, 可选)

**处理流程**:
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  AI 增强提示词流程 (两段式)                                                               │
│                                                                                          │
│  前端设置:                                                                               │
│  ├─ enhancePrompt: true                                                                  │
│  └─ enhancePromptModel: "gemini-2.5-flash" (可选，默认自动选择)                          │
│                                                                                          │
│  后端处理 (ConversationalImageEditService._enhance_prompt_two_stage):                   │
│  │                                                                                       │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  第一段：选择文本模型                                                            │ │
│  │  │  ├─ 如果 enhance_prompt_model 是图片模型 → 回退到 'gemini-2.5-flash'            │ │
│  │  │  └─ 否则使用指定模型或默认 'gemini-2.5-flash'                                   │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                              │                                                        │
│  │                              ▼                                                        │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  第二段：调用文本模型改写提示词                                                  │ │
│  │  │                                                                                  │ │
│  │  │  System Prompt:                                                                  │ │
│  │  │  "You are a professional edit prompt enhancer.                                   │ │
│  │  │   Return ONLY the enhanced prompt text, no explanations."                        │ │
│  │  │                                                                                  │ │
│  │  │  User Prompt:                                                                    │ │
│  │  │  "Rewrite the following image edit instruction to be more direct,                │ │
│  │  │   specific, and visually actionable while preserving the intent:                 │ │
│  │  │                                                                                  │ │
│  │  │   {原始提示词}"                                                                  │ │
│  │  │                                                                                  │ │
│  │  │  调用: client.models.generate_content(model, contents)                           │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                              │                                                        │
│  │                              ▼                                                        │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  结果处理                                                                        │ │
│  │  │  ├─ 成功 → 用增强后的提示词替换原始 prompt                                       │ │
│  │  │  │       → 保存 enhanced_prompt_text 用于返回给前端                              │ │
│  │  │  └─ 失败 → 使用原始 prompt，不影响后续流程                                       │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                                                                                       │
│  └─ 继续后续图片编辑流程 (使用增强后的 prompt)                                           │
│                                                                                          │
│  返回给前端:                                                                             │
│  └─ enhanced_prompt: "增强后的提示词" (用于在 UI 中显示)                                 │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**示例**:
```
原始提示词: "移除帽子"
增强后: "Remove the hat from the person's head completely, ensuring natural hair 
        appearance underneath and seamless blending with the background"
```

---

### 2. 思考过程 (enable_thinking)

**前端控件**: `frontend/controls/modes/google/ImageEditControls.tsx`
- 开关: `controls.enableThinking` (boolean)

**模型支持情况**:
| 模型 | 支持 Thinking | 支持图片输出 |
|------|--------------|-------------|
| gemini-3-pro-image-preview | ✅ | ✅ |
| gemini-3-flash-preview | ✅ | ❌ |
| gemini-2.5-flash-image | ❌ (400 error) | ✅ |
| gemini-2.0-flash-exp | ❌ | ✅ |

**处理流程**:
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  思考过程 (Thinking) 流程                                                                │
│                                                                                          │
│  前端设置:                                                                               │
│  └─ enableThinking: true                                                                 │
│                                                                                          │
│  后端处理:                                                                               │
│  │                                                                                       │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  1. 检查模型是否支持 Thinking                                                    │ │
│  │  │  _supports_thinking(model_name):                                                 │ │
│  │  │  └─ return 'gemini-3' in model_name.lower()                                      │ │
│  │  │                                                                                  │ │
│  │  │  只有 gemini-3 系列模型支持 thinking                                             │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                              │                                                        │
│  │                              ▼                                                        │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  2. 构建 ThinkingConfig                                                          │ │
│  │  │                                                                                  │ │
│  │  │  if _supports_thinking(model_name):                                              │ │
│  │  │      thinking_cfg = ThinkingConfig(include_thoughts=True)                        │ │
│  │  │  else:                                                                           │ │
│  │  │      thinking_cfg = None                                                         │ │
│  │  │                                                                                  │ │
│  │  │  send_config = GenerateContentConfig(                                            │ │
│  │  │      response_modalities=[TEXT, IMAGE],                                          │ │
│  │  │      thinking_config=thinking_cfg,  # ← 这里                                     │ │
│  │  │      ...                                                                         │ │
│  │  │  )                                                                               │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                              │                                                        │
│  │                              ▼                                                        │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  3. 发送请求到 Gemini API                                                        │ │
│  │  │  response = await chat.send_message(message, config=send_config)                 │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                              │                                                        │
│  │                              ▼                                                        │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │  │  4. 解析响应中的 thoughts                                                        │ │
│  │  │                                                                                  │ │
│  │  │  for part in response.parts:                                                     │ │
│  │  │      if part.thought == True:  # 这是一个思考 part                               │ │
│  │  │          if part.text:                                                           │ │
│  │  │              # 文本思考                                                          │ │
│  │  │              thoughts.append({                                                   │ │
│  │  │                  'type': 'text',                                                 │ │
│  │  │                  'content': part.text                                            │ │
│  │  │              })                                                                  │ │
│  │  │          elif part.inline_data:                                                  │ │
│  │  │              # 图片思考 (模型可能在思考过程中生成草图)                            │ │
│  │  │              thoughts.append({                                                   │ │
│  │  │                  'type': 'image',                                                │ │
│  │  │                  'content': f"data:{mime_type};base64,{base64_str}"              │ │
│  │  │              })                                                                  │ │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘ │
│  │                                                                                       │
│  └─ 返回结果包含 thoughts 数组                                                           │
│                                                                                          │
│  返回给前端:                                                                             │
│  └─ thoughts: [                                                                          │
│        { type: 'text', content: '分析图片中的帽子位置...' },                             │
│        { type: 'text', content: '确定需要修复的区域...' },                               │
│        { type: 'image', content: 'data:image/png;base64,...' },  // 草图                │
│        { type: 'text', content: '生成最终结果...' }                                      │
│      ]                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**前端显示**: `frontend/components/message/ThinkingBlock.tsx`
- 折叠/展开思考过程
- 支持文本和图片类型的思考内容

---

### 3. 两个功能的组合使用

当同时启用 `enhancePrompt` 和 `enableThinking` 时：

```
用户输入: "移除帽子"
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  1. AI 增强提示词 (先执行)                                                               │
│  └─ 增强后: "Remove the hat completely, restore natural hair, blend seamlessly"         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  2. 发送增强后的提示词到 Gemini API (带 ThinkingConfig)                                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  3. Gemini 返回:                                                                         │
│  ├─ thoughts: [思考过程...]                                                              │
│  ├─ images: [编辑后的图片]                                                               │
│  └─ text: [可能的文本说明]                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  4. 返回给前端:                                                                          │
│  {                                                                                       │
│    url: "data:image/png;base64,...",                                                     │
│    thoughts: [...],           // 思考过程                                                │
│    enhanced_prompt: "...",    // 增强后的提示词                                          │
│    text: "..."                // 文本响应                                                │
│  }                                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 前端高级参数传递路径

```
ImageEditControls.tsx
    │
    │  controls.enhancePrompt = true
    │  controls.enhancePromptModel = "gemini-2.5-flash"
    │  controls.enableThinking = true
    │
    ▼
useControlsState.ts (状态管理)
    │
    │  options: {
    │    enhancePrompt: true,
    │    enhancePromptModel: "gemini-2.5-flash",
    │    enableThinking: true,
    │    ...
    │  }
    │
    ▼
ImageEditHandlerClass.ts
    │
    │  editOptions = { ...context.options, ... }
    │
    ▼
llmService.editImage()
    │
    ▼
UnifiedProviderClient.executeMode()
    │
    │  POST /api/modes/google/image-chat-edit
    │  Body: {
    │    modelId: "gemini-3-pro-image-preview",
    │    prompt: "移除帽子",
    │    options: {
    │      enhancePrompt: true,           // camelCase
    │      enhancePromptModel: "...",     // camelCase
    │      enableThinking: true,          // camelCase
    │      ...
    │    }
    │  }
    │
    ▼
CaseConversionMiddleware (camelCase → snake_case)
    │
    │  options: {
    │    enhance_prompt: true,            // snake_case
    │    enhance_prompt_model: "...",     // snake_case
    │    enable_thinking: true,           // snake_case
    │    ...
    │  }
    │
    ▼
modes.py → params
    │
    ▼
ConversationalImageEditService.edit_image(config={...})
```
