# Requirements Document - Google Provider Image Generation Flow Analysis

## Introduction

分析 Google 提供商在图片生成模式下的调用流程，确定前端是否直接调用 Google SDK，还是通过后端服务。同时分析 Vertex AI 配置对调用流程的影响。

## Glossary

- **Google Provider**: Google 提供商，包括 Gemini API 和 Vertex AI
- **Gemini API**: Google 的 API Key 认证方式，使用 `@google/genai` SDK
- **Vertex AI**: Google Cloud 的服务账号认证方式，需要项目 ID 和凭证
- **Gen Mode**: Gemini 生成模式，使用 `generateContent` API
- **Imagen Mode**: Imagen 图片生成模式，使用 `generateImages` API
- **Frontend SDK**: 前端直接调用的 `@google/genai` SDK
- **Backend SDK**: 后端调用的 Google SDK
- **UnifiedProviderClient**: 前端统一提供商客户端，用于调用后端 API

## Requirements

### Requirement 1: 分析当前图片生成调用流程

**User Story:** 作为开发者，我想了解当前 Google 提供商图片生成的调用流程，以便确定是否需要优化架构。

#### Acceptance Criteria

1. WHEN 用户使用 Google 提供商生成图片 THEN 系统应该明确显示调用路径（前端 SDK vs 后端 API）
2. WHEN 分析代码 THEN 应该识别出所有图片生成的入口点
3. WHEN 分析代码 THEN 应该识别出 Vertex AI 配置的影响范围
4. WHEN 分析代码 THEN 应该识别出提示词（prompt）的传递路径

### Requirement 2: 识别架构问题

**User Story:** 作为开发者，我想识别当前架构中的问题，以便制定改进方案。

#### Acceptance Criteria

1. WHEN 前端直接调用 Google SDK THEN 应该识别出这种模式的问题
2. WHEN 后端没有接收到提示词 THEN 应该识别出数据流问题
3. WHEN Vertex AI 配置影响调用路径 THEN 应该识别出配置逻辑问题
4. WHEN 存在重复代码 THEN 应该识别出代码重复问题

### Requirement 3: 提供改进建议

**User Story:** 作为开发者，我想获得架构改进建议，以便统一调用流程。

#### Acceptance Criteria

1. WHEN 识别出架构问题 THEN 应该提供统一调用流程的建议
2. WHEN 提供建议 THEN 应该包含具体的实现方案
3. WHEN 提供建议 THEN 应该考虑向后兼容性
4. WHEN 提供建议 THEN 应该考虑 Vertex AI 和 Gemini API 的差异

## Current Analysis

### 发现 1: 图片生成主流程已走后端 /api/generate/google/image

**入口链路**:
- `frontend/hooks/handlers/ImageGenHandlerClass.ts` -> `llmService.generateImage`
- `frontend/services/llmService.ts` -> `LLMFactory.getProvider(...)`
- `frontend/services/LLMFactory.ts` -> `UnifiedProviderClient('google')`
- `frontend/services/providers/UnifiedProviderClient.ts` -> `POST /api/generate/google/image`
- `backend/app/routers/generate.py` -> `ProviderFactory` -> `GoogleService` -> `ImageGenerator`

**结论**:
1. ✅ 图片生成主流程不是前端直调 SDK，而是统一走后端 API
2. ✅ prompt 通过 request body 传给后端并被使用
3. ✅ 该路径与聊天、视频、语音的调用方式一致

### 发现 2: 前端 Google SDK 仍存在于特定功能或遗留模块

**文件**:
- `frontend/services/providers/google/media/image-gen.ts`（前端直调 SDK 的实现，当前不在主图片生成链路）
- `frontend/services/providers/google/media/virtual-tryon.ts`（Virtual Try-On 分割/掩码场景）
- `frontend/services/providers/google/fileService.ts`（Google Files API 上传）

**结论**:
1. ⚠️ 主图片生成流程已走后端，但前端仍保留 SDK 直调的模块
2. ⚠️ 这些模块属于特定功能或历史遗留，不代表主流程

### 发现 3: 聊天功能已统一使用后端

**文件**: `frontend/services/LLMFactory.ts`

**代码分析**:
```typescript
case 'google':
case 'google-custom':
    // ✅ Google 现在统一使用后端 SDK（UnifiedProviderClient）
    // 前端不再直接调用 Google SDK
    if (protocol === 'openai') provider = new OpenAIProvider();
    else provider = new UnifiedProviderClient('google');
    break;
```

**发现**:
1. ✅ 聊天功能已经统一使用 `UnifiedProviderClient`
2. ✅ 通过后端 API `/api/chat/google` 调用
3. ✅ 后端从数据库获取 API Key
4. ✅ 支持 Vertex AI 配置

### 发现 4: 后端有图片生成端点且已被主流程使用

**文件**: `frontend/services/providers/UnifiedProviderClient.ts`

**代码分析**:
```typescript
async generateImage(
    modelId: string,
    prompt: string,
    referenceImages: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl: string
): Promise<ImageGenerationResult[]> {
    const response = await fetch(`/api/generate/${this.id}/image`, {  // ✅ 后端端点存在
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify(requestBody)
    });
}
```

**发现**:
1. ✅ 后端有 `/api/generate/google/image` 端点
2. ✅ 支持传递 prompt、options、apiKey
3. ✅ 统一的错误处理
4. ✅ 主流程已经使用该端点

### 发现 5: 后端具备 ImagenCoordinator，但用户级 Vertex AI 配置未被使用

**文件**:
- `backend/app/routers/generate.py`
- `backend/app/services/gemini/google_service.py`
- `backend/app/services/gemini/image_generator.py`
- `backend/app/services/gemini/imagen_coordinator.py`

**事实**:
1. ✅ 后端生成图像时会进入 `ImageGenerator` -> `ImagenCoordinator`
2. ⚠️ `ImagenCoordinator` 只有在传入 `user_id + db` 时才会从数据库读取 Vertex AI 配置
3. ⚠️ 当前 `GoogleService` 初始化 `ImageGenerator` 仅传 `api_key`，未传 `user_id/db`，因此只会使用环境变量配置

## Architecture Issues

### Issue 1: 主流程已统一，但遗留前端 SDK 造成理解成本

| 功能 | 主流程调用方式 | 备注 |
|------|---------------|------|
| 聊天 | 后端 API (`/api/chat/google`) | ✅ 已统一 |
| 图片生成 | 后端 API (`/api/generate/google/image`) | ✅ 主流程已统一 |
| 视频生成 | 后端 API (`/api/generate/google/video`) | ✅ 已统一 |
| 语音生成 | 后端 API (`/api/generate/google/speech`) | ✅ 已统一 |

补充：前端仍保留 `frontend/services/providers/google/media/*` 的 SDK 实现（特定功能或遗留），容易被误读为主流程。

### Issue 2: API Key 仍暴露在前端并回传到后端

- ❌ 配置文件数据包含 API Key，会下发到前端
- ❌ `UnifiedProviderClient.generateImage` 仍在 request body 里传 `apiKey`
- ❌ 前端可读到密钥，风险仍在

### Issue 3: Vertex AI 配置未应用到图片生成

- ⚠️ `ImagenCoordinator` 需要 `user_id + db` 才能从数据库读取 Vertex AI 配置
- ⚠️ 当前 `GoogleService` 创建 `ImageGenerator` 未传入 `user_id/db`，导致只用环境变量配置

### Issue 4: 遗留代码与主流程重复

- ⚠️ 前端仍保留 Google SDK 的图片生成/编辑实现
- ⚠️ 参数处理与错误处理在前后端都有类似逻辑

## Proposed Solution

### Solution 1: 清理或隔离前端 SDK 遗留模块

**改动**:
1. 标注 `frontend/services/providers/google/media/*` 为特定功能或 legacy
2. 如果这些功能应统一走后端，则改为调用 `UnifiedProviderClient`
3. 移除未被主流程使用的直调代码，避免误解

**优点**:
- ✅ 文档与代码一致
- ✅ 减少维护成本与认知成本

### Solution 2: 后端按用户配置选择 Gemini API / Vertex AI

**改动**:
1. 在生成端点创建 `GoogleService` 时传入 `user_id/db`（或直接在端点调用 `ImagenCoordinator`）
2. 优先使用 Vertex AI（如果数据库中配置完整）
3. 回退到 Gemini API（如果没有 Vertex AI 配置）

**逻辑**:
```
IF user has Vertex AI config (project_id + credentials):
    USE Vertex AI SDK
ELSE IF user has Gemini API key:
    USE Gemini API SDK
ELSE:
    RETURN error: "No valid configuration"
```

### Solution 3: 维持并验证 prompt 传递（已具备）

**确保**:
1. ✅ 前端传递 `prompt` 到后端
2. ✅ 后端接收 `prompt` 并传递给 SDK
3. ✅ 后端正确调用 `generate_images(prompt=...)`

**官方 SDK 用法**:
```python
response = await client.aio.models.generate_images(
    model='imagen-3.0-generate-002',
    prompt='Man with a dog',  # ✅ 必须传递 prompt
    config=types.GenerateImagesConfig(
        number_of_images=1,
        include_rai_reason=True,
    )
)
```

## Next Steps

1. 创建 design.md 文档，详细设计统一调用流程
2. 创建 tasks.md 文档，列出具体实现任务
3. 清理/标注前端 Google SDK 遗留路径
4. 实现后端按用户配置切换 Vertex AI / Gemini API
5. 测试 Gemini API 和 Vertex AI 两种模式
