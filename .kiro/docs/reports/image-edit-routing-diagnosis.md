# Image Edit Mode 404 Error - Routing Diagnosis

**Date**: 2026-01-10  
**Status**: Root Cause Identified  
**Version**: v1.0.0

---

## 问题描述

用户在使用 `nano-banana-pro-preview` 模型进行图片编辑时遇到 404 错误：
```
Publisher Model `projects/.../publishers/google/models/nano-banana-pro-preview` not found.
```

## 错误日志分析

### 关键证据

错误日志显示（`.kiro/specs/erron/log.md`）：

```
[Generate] ==================== Image Generation Request ====================
[ImagenCoordinator] Using Vertex AI config...
[ImageGenerator] Initialized with coordinator-based architecture...
```

**这是 GENERATION 流程，不是 EDIT 流程！**

如果是正确的 edit 流程，应该看到：
```
[Generate] ==================== Image Editing Request ====================
[ImageEditCoordinator] Using Vertex AI config...
```

## 架构验证

### 后端架构（✅ 完全正确）

1. **Edit Endpoint**: `/api/generate/google/image/edit` (generate.py:417)
   - 调用 `google_service.edit_image()`
   - 委托给 `ImageEditCoordinator`
   - 选择 `VertexAIImageEditor` 或 `GeminiAPIImageEditor`

2. **Generation Endpoint**: `/api/generate/google/image` (generate.py:XXX)
   - 调用 `google_service.generate_image()`
   - 委托给 `ImagenCoordinator`
   - 选择 `VertexAIImageGenerator` 或 `GeminiAPIImageGenerator`

### 前端架构（需要验证）

1. **Handler**: `ImageEditHandler` (ImageEditHandlerClass.ts:11)
   - 调用 `llmService.editImage()`

2. **Service**: `llmService.editImage()` (llmService.ts:191)
   - 调用 `currentProvider.editImage()`

3. **Provider**: `UnifiedProviderClient.editImage()` (UnifiedProviderClient.ts:444)
   - 发送请求到 `/api/generate/${this.id}/image/edit`
   - 其中 `this.id` 应该是 "google"

## 根本原因假设

**前端在 edit 模式下，实际调用的是 generation endpoint，而不是 edit endpoint。**

可能的原因：
1. `ImageEditHandler` 没有被正确触发
2. `llmService.editImage()` 内部逻辑错误
3. `UnifiedProviderClient.editImage()` 的 URL 构建错误
4. 前端路由配置错误

## 下一步行动

需要验证前端的实际请求：
1. 检查浏览器 Network 面板，确认实际发送的 URL
2. 检查 `ImageEditHandler` 是否被正确注册和触发
3. 检查前端的 handler 路由逻辑

## 文件清单

### 后端（已验证，无问题）
- `backend/app/routers/generate.py` - Edit endpoint 定义
- `backend/app/services/gemini/google_service.py` - Edit 方法委托
- `backend/app/services/gemini/image_edit_coordinator.py` - Editor 工厂
- `backend/app/services/gemini/image_edit_vertex_ai.py` - Vertex AI 实现

### 前端（需要验证）
- `frontend/hooks/handlers/ImageEditHandlerClass.ts` - Edit handler
- `frontend/services/llmService.ts` - Edit service 方法
- `frontend/services/providers/UnifiedProviderClient.ts` - Provider edit 方法
- `frontend/hooks/useHandlers.ts` - Handler 注册逻辑（需要检查）

---

**结论**：后端架构完全正确，问题出在前端路由或 handler 触发逻辑。
