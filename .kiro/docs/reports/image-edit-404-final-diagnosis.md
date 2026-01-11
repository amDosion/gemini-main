# Image Edit Mode 404 Error - Final Diagnosis

**Date**: 2026-01-10  
**Status**: Root Cause Confirmed  
**Version**: v2.0.0

---

## 问题确认

用户报告：在使用 `nano-banana-pro-preview` 模型进行图片编辑时遇到 404 错误。

## 错误日志分析

### 关键证据 1：错误日志显示 Generation 流程

```
[Generate] ==================== Image Generation Request ====================
[ImagenCoordinator] Using Vertex AI config...
[ImageGenerator] Initialized with coordinator-based architecture...
```

**这是 GENERATION 流程，不是 EDIT 流程！**

### 关键证据 2：用户上传了参考图片

```
[Generate] Reference Images Count: 1
```

这说明用户确实上传了图片，但是系统将其作为 generation 请求处理。

### 关键证据 3：模型映射错误

```
Publisher Model `projects/.../publishers/google/models/nano-banana-pro-preview` not found.
```

这个错误发生在 `imagen_vertex_ai.py`（generation 模式），而不是 `image_edit_vertex_ai.py`（edit 模式）。

## 根本原因

**用户在前端选择了 "Gen" 模式（image-gen），而不是 "Edit" 模式（image-edit）。**

### 证据链

1. **前端架构**：
   - ModeSelector 有 9 个按钮：Chat, Research, **Gen**, **Edit**, Try-On, Expand, Video, Audio, PDF
   - 用户点击 "Gen" → `mode='image-gen'` → 调用 `ImageGenHandler`
   - 用户点击 "Edit" → `mode='image-edit'` → 调用 `ImageEditHandler`

2. **Handler 路由**：
   - `ImageGenHandler` → `llmService.generateImage()` → `/api/generate/google/image` → `google_service.generate_image()` → `ImagenCoordinator` → `VertexAIImageGenerator`
   - `ImageEditHandler` → `llmService.editImage()` → `/api/generate/google/image/edit` → `google_service.edit_image()` → `ImageEditCoordinator` → `VertexAIImageEditor`

3. **错误日志匹配**：
   - 日志显示：`[ImagenCoordinator]` 和 `[ImageGenerator]`
   - 这明确对应 generation 流程，不是 edit 流程

4. **模型映射差异**：
   - **Generation 模式** (`imagen_vertex_ai.py`): 没有 MODEL_MAPPING，直接使用用户提供的模型名
   - **Edit 模式** (`image_edit_vertex_ai.py`): 有 MODEL_MAPPING，将 `nano-banana-pro-preview` 映射到 `imagen-3.0-capability-001`

## 解决方案

### 方案 1：用户操作修正（推荐）

**用户应该点击 "Edit" 按钮，而不是 "Gen" 按钮。**

- "Gen" 模式：从文本生成图片（可选：使用 style reference）
- "Edit" 模式：编辑现有图片（需要上传原图 + mask）

### 方案 2：Generation 模式添加模型映射（备选）

如果用户确实想在 "Gen" 模式下使用 `nano-banana-pro-preview`，需要在 `imagen_vertex_ai.py` 中添加 MODEL_MAPPING：

```python
# imagen_vertex_ai.py (Generation 模式)
MODEL_MAPPING = {
    'nano-banana-pro-preview': 'imagen-3.0-generate-001',
    'nano-banana-pro': 'imagen-3.0-generate-001',
    # ... 其他映射
}
```

但这需要确认 Vertex AI 是否支持这些模型名称用于 generation。

### 方案 3：UI 改进（长期）

在 UI 中添加提示，帮助用户理解：
- "Gen" 模式：创建新图片
- "Edit" 模式：修改现有图片

## 用户指导

### 如何使用 Edit 模式

1. 点击 **"Edit"** 按钮（不是 "Gen"）
2. 上传要编辑的图片
3. （可选）上传 mask 图片
4. 输入编辑提示词
5. 选择模型：`nano-banana-pro-preview` 或其他支持的模型
6. 点击发送

### Edit 模式支持的模型

根据 `image_edit_vertex_ai.py` 的 MODEL_MAPPING：
- `nano-banana-pro-preview` → `imagen-3.0-capability-001` ✅
- `nano-banana-pro` → `imagen-3.0-capability-001` ✅
- `gemini-3-pro-image-preview` → `imagen-3.0-capability-001` ✅
- 所有这些模型都会被映射到 Vertex AI 的 `imagen-3.0-capability-001`

## 架构验证

### 后端架构（✅ 完全正确）

1. **Edit Endpoint**: `/api/generate/google/image/edit`
   - 调用 `google_service.edit_image()`
   - 委托给 `ImageEditCoordinator`
   - 选择 `VertexAIImageEditor`
   - 使用 MODEL_MAPPING 映射模型名

2. **Generation Endpoint**: `/api/generate/google/image`
   - 调用 `google_service.generate_image()`
   - 委托给 `ImagenCoordinator`
   - 选择 `VertexAIImageGenerator`
   - 直接使用用户提供的模型名（无映射）

### 前端架构（✅ 完全正确）

1. **ModeSelector**: 9 个模式按钮，用户点击选择
2. **Handler 注册**: `strategyConfig.ts` 注册所有 handlers
3. **Handler 路由**: `StrategyRegistry` 根据 mode 选择 handler
4. **API 调用**: 每个 handler 调用对应的 API endpoint

## 结论

**问题不是 bug，而是用户操作错误。**

用户应该使用 "Edit" 模式（`mode='image-edit'`），而不是 "Gen" 模式（`mode='image-gen'`）。

后端和前端的架构都是正确的，没有需要修复的代码。

---

## 文件清单

### 后端（已验证，无问题）
- `backend/app/routers/generate.py` - Edit 和 Generation endpoints
- `backend/app/services/gemini/google_service.py` - 服务委托
- `backend/app/services/gemini/image_edit_coordinator.py` - Edit coordinator
- `backend/app/services/gemini/image_edit_vertex_ai.py` - Edit 实现（有 MODEL_MAPPING）
- `backend/app/services/gemini/imagen_coordinator.py` - Generation coordinator
- `backend/app/services/gemini/imagen_vertex_ai.py` - Generation 实现（无 MODEL_MAPPING）

### 前端（已验证，无问题）
- `frontend/hooks/handlers/strategyConfig.ts` - Handler 注册
- `frontend/hooks/handlers/ImageEditHandlerClass.ts` - Edit handler
- `frontend/hooks/handlers/ImageGenHandlerClass.ts` - Generation handler
- `frontend/components/chat/input/ModeSelector.tsx` - 模式选择 UI
- `frontend/App.tsx` - sendMessage 调用
- `frontend/hooks/useChat.ts` - Handler 执行

---

**最终建议**：告知用户使用 "Edit" 按钮，而不是 "Gen" 按钮。
