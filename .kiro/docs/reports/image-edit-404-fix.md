# Image Edit Mode 404 Error Fix

**日期**: 2026-01-10  
**问题**: 编辑模式下使用 `nano-banana-pro-preview` 模型返回 404 错误

## 问题分析

### 错误日志
```
2026-01-10 17:58:41 - [Generate] Reference Images Count: 1
2026-01-10 17:58:41 - [ImageGenerator] Initialized with coordinator-based architecture
2026-01-10 17:58:42 - [VertexAIImageGenerator] Generating image: model=nano-banana-pro-preview
404 NOT_FOUND: Publisher Model `nano-banana-pro-preview` not found
```

### 根本原因

**前端路由错误**：`ImageEditHandlerClass.ts` 调用了错误的方法

```typescript
// ❌ 错误代码（第 11 行）
const results = await llmService.generateImage(context.text, context.attachments);
```

**问题**：
1. 用户在前端选择了编辑模式（Edit Mode）
2. 上传了参考图片（Reference Images Count: 1）
3. 但 `ImageEditHandler` 调用的是 `generateImage()` 而不是 `editImage()`
4. 导致请求被发送到**生成端点** `/api/generate/google/image` 而不是**编辑端点** `/api/generate/google/image/edit`
5. 生成端点使用 `ImageGenerator` → `imagen_vertex_ai.py`
6. 编辑端点应该使用 `ImageEditCoordinator` → `image_edit_vertex_ai.py`

### 端点对比

| 模式 | 前端方法 | 后端端点 | 后端服务 | 模型映射 |
|------|---------|---------|---------|---------|
| 生成 | `generateImage()` | `/api/generate/{provider}/image` | `ImageGenerator` → `imagen_vertex_ai.py` | ❌ 无映射（直接使用用户提供的模型ID） |
| 编辑 | `editImage()` | `/api/generate/{provider}/image/edit` | `ImageEditCoordinator` → `image_edit_vertex_ai.py` | ✅ 有映射（nano-banana → imagen-3.0-capability-001） |

### 为什么会404？

**生成模式**（`imagen_vertex_ai.py`）：
- 直接使用用户提供的模型ID：`nano-banana-pro-preview`
- Vertex AI 不认识这个模型名称 → 404 NOT_FOUND

**编辑模式**（`image_edit_vertex_ai.py`）：
- 有 MODEL_MAPPING：`'nano-banana-pro-preview': 'imagen-3.0-capability-001'`
- 会自动映射到 Vertex AI 支持的模型 → 成功

## 修复方案

### 修复代码

**文件**: `frontend/hooks/handlers/ImageEditHandlerClass.ts`

```typescript
// ✅ 修复后
export class ImageEditHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const results = await llmService.editImage(context.text, context.attachments);
    
    // 使用统一的媒体处理函数
    return handleMediaResults(results, 'image');
  }
}
```

### 修复效果

修复后的请求流程：
```
用户编辑请求
  ↓
ImageEditHandler.doExecute()
  ↓
llmService.editImage()  ✅ 正确方法
  ↓
UnifiedProviderClient.editImage()
  ↓
POST /api/generate/google/image/edit  ✅ 正确端点
  ↓
google_service.edit_image()
  ↓
ImageEditCoordinator.get_editor()
  ↓
VertexAIImageEditor.edit_image()  ✅ 正确服务
  ↓
MODEL_MAPPING: nano-banana-pro-preview → imagen-3.0-capability-001  ✅ 正确映射
  ↓
Vertex AI API 调用成功
```

## 架构验证

### 后端协调逻辑（✅ 正确）

**生成模式**：
```
generate.py → google_service.generate_image() → ImageGenerator → ImagenCoordinator
  ├─ Vertex AI → VertexAIImageGenerator (imagen_vertex_ai.py)
  └─ Gemini API → GeminiAPIImageGenerator (imagen_gemini_api.py)
```

**编辑模式**：
```
generate.py → google_service.edit_image() → ImageEditCoordinator
  ├─ Vertex AI → VertexAIImageEditor (image_edit_vertex_ai.py)
  └─ Gemini API → GeminiAPIImageEditor (raises NotSupportedError)
```

### 前端路由逻辑（✅ 已修复）

**修复前**：
- `ImageGenHandler` → `llmService.generateImage()` ✅
- `ImageEditHandler` → `llmService.generateImage()` ❌ **错误**

**修复后**：
- `ImageGenHandler` → `llmService.generateImage()` ✅
- `ImageEditHandler` → `llmService.editImage()` ✅ **正确**

## 测试验证

### 测试步骤
1. 前端选择编辑模式（Edit Mode）
2. 上传参考图片
3. 选择模型：`nano-banana-pro-preview`
4. 输入提示词
5. 点击生成

### 预期结果
- ✅ 请求发送到 `/api/generate/google/image/edit`
- ✅ 后端使用 `ImageEditCoordinator`
- ✅ 模型自动映射：`nano-banana-pro-preview` → `imagen-3.0-capability-001`
- ✅ Vertex AI API 调用成功
- ✅ 返回编辑后的图片

## 相关文件

**修复文件**：
- `frontend/hooks/handlers/ImageEditHandlerClass.ts` - 修复方法调用

**验证文件**：
- `backend/app/services/gemini/image_edit_coordinator.py` - 编辑模式协调器
- `backend/app/services/gemini/image_edit_vertex_ai.py` - Vertex AI 编辑实现（含 MODEL_MAPPING）
- `backend/app/services/gemini/google_service.py` - 主服务协调器
- `backend/app/routers/generate.py` - API 路由

## 总结

**问题**：前端编辑模式调用了错误的方法（`generateImage` 而不是 `editImage`）

**影响**：
- 编辑请求被错误地路由到生成端点
- 生成端点没有模型映射，导致 404 错误
- 用户无法使用编辑功能

**修复**：
- 修改 `ImageEditHandlerClass.ts` 调用正确的 `editImage()` 方法
- 一行代码修复，影响范围小
- 后端协调逻辑无需修改（已经是正确的）

**验证**：
- 修复后编辑模式将正确路由到编辑端点
- 模型映射将自动生效
- Vertex AI API 调用将成功
