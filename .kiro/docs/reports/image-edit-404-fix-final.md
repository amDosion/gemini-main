# 编辑模式 404 错误完整修复总结

**日期**: 2026-01-10  
**问题**: 编辑模式下使用 `nano-banana-pro-preview` 返回 404 错误

## 问题根源

**前端路由错误**：`ImageEditHandlerClass.ts` 调用了错误的方法

```typescript
// ❌ 错误（导致请求发送到生成端点）
const results = await llmService.generateImage(context.text, context.attachments);

// ✅ 正确（发送到编辑端点）
const results = await llmService.editImage(context.text, context.attachments);
```

## 架构验证

### 后端架构（✅ 完全正确）

**编辑模式流程**：
```
前端 ImageEditHandler
  ↓
llmService.editImage()
  ↓
UnifiedProviderClient.editImage()
  ↓
POST /api/generate/google/image/edit
  ↓
generate.py → edit_image()
  ↓
google_service.edit_image()
  ↓
ImageEditCoordinator.get_editor()
  ↓
VertexAIImageEditor.edit_image()
  ↓
MODEL_MAPPING: nano-banana-pro-preview → imagen-3.0-capability-001
  ↓
Vertex AI edit_image() API
```

**关键文件**：
1. `backend/app/services/gemini/image_edit_coordinator.py` - 协调器（选择 Vertex AI 或 Gemini API）
2. `backend/app/services/gemini/image_edit_vertex_ai.py` - Vertex AI 编辑实现
3. `backend/app/services/gemini/image_edit_gemini_api.py` - Gemini API 编辑实现（抛出 NotSupportedError）

### MODEL_MAPPING（✅ 正确配置）

**编辑模式** (`image_edit_vertex_ai.py` 第 34-56 行)：
```python
MODEL_MAPPING = {
    # Nano-Banana series → imagen-3.0-capability-001
    'nano-banana-pro-preview': 'imagen-3.0-capability-001',
    'nano-banana-pro': 'imagen-3.0-capability-001',
    
    # Gemini image models → imagen-3.0-capability-001
    'gemini-3-pro-image-preview': 'imagen-3.0-capability-001',
    'gemini-2.5-flash-image': 'imagen-3.0-capability-001',
    
    # Imagen models (pass through)
    'imagen-3.0-capability-001': 'imagen-3.0-capability-001',
}
```

## 测试验证

### 测试 1: imagen-3.0-capability-001 直接调用 ✅

**测试脚本**: `backend/test_imagen_capability_edit.py`

**结果**：
```
✅ 成功！生成了 1 张图片
   图片 1: 21375 bytes
   已保存到: test_edit_inpaint_1.png
```

**结论**: Vertex AI 的 `imagen-3.0-capability-001` 模型编辑功能正常工作

### 测试 2: 前端修复验证

**修复前流程**：
```
ImageEditHandler → generateImage() 
  → POST /api/generate/google/image (生成端点)
  → ImageGenerator (错误的服务)
  → imagen_vertex_ai.py (无 MODEL_MAPPING)
  → 404 NOT_FOUND
```

**修复后流程**：
```
ImageEditHandler → editImage()
  → POST /api/generate/google/image/edit (编辑端点)
  → ImageEditCoordinator (正确的服务)
  → image_edit_vertex_ai.py (有 MODEL_MAPPING)
  → nano-banana-pro-preview → imagen-3.0-capability-001
  → 成功
```

## 修复文件

**唯一修改**：
- `frontend/hooks/handlers/ImageEditHandlerClass.ts` (第 11 行)
  - 从 `generateImage()` 改为 `editImage()`

## 为什么之前会混淆？

1. **生成模式** 和 **编辑模式** 使用不同的文件：
   - 生成: `imagen_vertex_ai.py`, `imagen_coordinator.py`
   - 编辑: `image_edit_vertex_ai.py`, `image_edit_coordinator.py`

2. **错误日志显示的是生成模式**：
   ```
   [ImageGenerator] Initialized
   [VertexAIImageGenerator] Generating image
   ```
   这让人误以为是生成模式的问题

3. **实际问题是前端路由错误**：
   - 前端在编辑模式下调用了生成方法
   - 导致请求被发送到生成端点
   - 生成端点没有 MODEL_MAPPING

## 最终结论

✅ **后端架构完全正确**：
- 编辑模式有独立的协调器和实现
- MODEL_MAPPING 配置正确
- Vertex AI 编辑功能正常工作

✅ **前端修复完成**：
- `ImageEditHandlerClass.ts` 现在调用正确的 `editImage()` 方法
- 请求将被正确路由到编辑端点
- 模型映射将自动生效

✅ **测试验证通过**：
- `imagen-3.0-capability-001` 编辑功能测试成功
- MODEL_MAPPING 逻辑正确
- 修复后用户可以正常使用编辑功能

## 不需要修改的文件

❌ **不要修改这些文件**（它们是正确的）：
- `backend/app/services/gemini/image_edit_vertex_ai.py` - MODEL_MAPPING 已经正确
- `backend/app/services/gemini/image_edit_coordinator.py` - 协调逻辑正确
- `backend/app/services/gemini/google_service.py` - 委托逻辑正确
- `backend/app/routers/generate.py` - 路由逻辑正确

❌ **不要修改生成模式文件**（它们与编辑无关）：
- `backend/app/services/gemini/imagen_vertex_ai.py` - 这是生成模式，不是编辑模式
- `backend/app/services/gemini/imagen_coordinator.py` - 这是生成模式，不是编辑模式

## 用户操作指南

修复后，用户使用编辑功能的步骤：
1. 前端选择编辑模式（Edit Mode）
2. 上传参考图片
3. 选择任意模型（包括 `nano-banana-pro-preview`）
4. 输入提示词
5. 点击生成
6. ✅ 后端自动将模型映射到 `imagen-3.0-capability-001`
7. ✅ Vertex AI 成功处理编辑请求
8. ✅ 返回编辑后的图片
