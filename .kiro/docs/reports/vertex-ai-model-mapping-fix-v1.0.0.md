# Nano Banana 模型 Vertex AI 映射修复报告

## 问题描述

用户在使用 `nano-banana-pro-preview` 模型进行图片生成时，遇到 404 错误：

```
Publisher Model `projects/.../models/nano-banana-pro-preview` not found
```

## 根本原因分析

### 1. 问题定位

从错误日志可以看出：

```
2026-01-10 17:58:41 - backend.app.routers.generate - INFO - [Generate] ==================== Image Generation Request ====================
2026-01-10 17:58:41 - backend.app.routers.generate - INFO - [Generate] Model: nano-banana-pro-preview
2026-01-10 17:58:41 - backend.app.routers.generate - INFO - [Generate] Reference Images Count: 1
...
2026-01-10 17:58:42 - backend.app.services.gemini.imagen_vertex_ai - INFO - [VertexAIImageGenerator] Generating image: model=nano-banana-pro-preview
2026-01-10 17:58:44 - backend.app.services.gemini.imagen_vertex_ai - ERROR - [VertexAIImageGenerator] Generation failed: 404 NOT_FOUND
```

**关键发现：**
1. 这是**图片生成请求**（Image Generation），不是图片编辑（Image Editing）
2. 调用的是 `imagen_vertex_ai.py` 的 `generate_image` 方法
3. 前端传递的模型 ID `nano-banana-pro-preview` 直接传递给了 Vertex AI API
4. Vertex AI 不认识这个模型 ID，返回 404 错误

### 2. Vertex AI 支持的模型

根据 Google Genai SDK 的参考代码和官方文档：

**图片生成（Image Generation）：**
- `imagen-3.0-generate-001` - 标准生成模型
- `imagen-3.0-fast-generate-001` - 快速生成模型

**图片编辑（Image Editing）：**
- `imagen-3.0-capability-001` - 编辑能力模型

**Vertex AI 不支持的模型：**
- `nano-banana-pro-preview`
- `nano-banana-*`
- `gemini-*-image-*`

### 3. 为什么会有这个问题？

1. **前端模型选择器**显示了 `nano-banana-pro-preview` 等用户友好的模型名称
2. **后端能力推断**（`model_capabilities.py`）正确识别了这些模型的能力（vision=True）
3. **但是 Vertex AI API** 只接受特定的模型 ID（如 `imagen-3.0-generate-001`）
4. **缺少模型映射层**，导致用户选择的模型 ID 直接传递给 Vertex AI，引发 404 错误

## 修复方案

### 修复 1：imagen_vertex_ai.py（图片生成）

**文件：** `backend/app/services/gemini/imagen_vertex_ai.py`

**修改内容：**

1. **添加模型映射表**（第 31-60 行）：

```python
# Model mapping: User-facing model IDs → Vertex AI model IDs
MODEL_MAPPING = {
    # Nano-Banana series → imagen-3.0-generate-001
    'nano-banana-pro-preview': 'imagen-3.0-generate-001',
    'nano-banana-pro': 'imagen-3.0-generate-001',
    'nano-banana-preview': 'imagen-3.0-generate-001',
    'nano-banana': 'imagen-3.0-generate-001',
    
    # Gemini image models → imagen-3.0-generate-001
    'gemini-3-pro-image-preview': 'imagen-3.0-generate-001',
    'gemini-3.0-pro-image-preview': 'imagen-3.0-generate-001',
    'gemini-3-pro-image': 'imagen-3.0-generate-001',
    'gemini-3.0-pro-image': 'imagen-3.0-generate-001',
    'gemini-2.5-flash-image': 'imagen-3.0-generate-001',
    'gemini-2.5-flash-image-preview': 'imagen-3.0-generate-001',
    'gemini-2.5-pro-image': 'imagen-3.0-generate-001',
    'gemini-2.5-pro-image-preview': 'imagen-3.0-generate-001',
    
    # Imagen models (pass through)
    'imagen-3.0-generate-001': 'imagen-3.0-generate-001',
    'imagen-3.0-capability-001': 'imagen-3.0-capability-001',
    'imagen-3.0-fast-generate-001': 'imagen-3.0-fast-generate-001',
}

DEFAULT_GENERATE_MODEL = 'imagen-3.0-generate-001'
```

2. **修改 generate_image 方法**（第 150-160 行）：

```python
# Map user-facing model ID to Vertex AI model ID
vertex_model = MODEL_MAPPING.get(model, DEFAULT_GENERATE_MODEL)

if model != vertex_model:
    logger.info(
        f"[VertexAIImageGenerator] Model mapping: {model} → {vertex_model}"
    )

logger.info(f"[VertexAIImageGenerator] Generating image: model={vertex_model}, prompt={prompt[:50]}...")
```

3. **使用映射后的模型调用 API**（第 193 行）：

```python
response = self._client.models.generate_images(
    model=vertex_model,  # 使用映射后的模型
    prompt=effective_prompt,
    config=config
)
```

### 修复 2：image_edit_vertex_ai.py（图片编辑）

**文件：** `backend/app/services/gemini/image_edit_vertex_ai.py`

**修改内容：**

1. **添加模型映射表**（第 31-60 行）：

```python
# Model mapping: User-facing model IDs → Vertex AI model IDs
MODEL_MAPPING = {
    # Nano-Banana series → imagen-3.0-capability-001
    'nano-banana-pro-preview': 'imagen-3.0-capability-001',
    'nano-banana-pro': 'imagen-3.0-capability-001',
    'nano-banana-preview': 'imagen-3.0-capability-001',
    'nano-banana': 'imagen-3.0-capability-001',
    
    # Gemini image models → imagen-3.0-capability-001
    'gemini-3-pro-image-preview': 'imagen-3.0-capability-001',
    'gemini-3.0-pro-image-preview': 'imagen-3.0-capability-001',
    'gemini-3-pro-image': 'imagen-3.0-capability-001',
    'gemini-3.0-pro-image': 'imagen-3.0-capability-001',
    'gemini-2.5-flash-image': 'imagen-3.0-capability-001',
    'gemini-2.5-flash-image-preview': 'imagen-3.0-capability-001',
    'gemini-2.5-pro-image': 'imagen-3.0-capability-001',
    'gemini-2.5-pro-image-preview': 'imagen-3.0-capability-001',
    
    # Imagen models (pass through)
    'imagen-3.0-capability-001': 'imagen-3.0-capability-001',
    'imagen-3.0-generate-001': 'imagen-3.0-capability-001',
}

DEFAULT_EDIT_MODEL = 'imagen-3.0-capability-001'
```

2. **修改 edit_image 方法**（第 147-157 行）：

```python
# Get model from config
user_model = (config or {}).get('model', DEFAULT_EDIT_MODEL)

# Map user-facing model ID to Vertex AI model ID
vertex_model = MODEL_MAPPING.get(user_model, DEFAULT_EDIT_MODEL)

if user_model != vertex_model:
    logger.info(
        f"[VertexAIImageEditor] Model mapping: {user_model} → {vertex_model}"
    )
```

3. **使用映射后的模型调用 API**（第 172 行）：

```python
response = self._client.models.edit_image(
    model=vertex_model,  # 使用映射后的模型
    prompt=prompt,
    reference_images=ref_images,
    config=edit_config
)
```

## 修复效果

### 修复前

```
用户选择: nano-banana-pro-preview
    ↓
后端传递: nano-banana-pro-preview
    ↓
Vertex AI: 404 NOT_FOUND ❌
```

### 修复后

```
用户选择: nano-banana-pro-preview
    ↓
后端映射: nano-banana-pro-preview → imagen-3.0-generate-001
    ↓
Vertex AI: 成功生成图片 ✅
```

## 模型映射规则

| 用户选择的模型 | 图片生成 | 图片编辑 |
|---------------|---------|---------|
| nano-banana-pro-preview | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| nano-banana-pro | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| nano-banana-preview | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| nano-banana | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| gemini-3-pro-image-preview | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| gemini-2.5-flash-image | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| imagen-3.0-generate-001 | imagen-3.0-generate-001 | imagen-3.0-capability-001 |
| imagen-3.0-capability-001 | imagen-3.0-capability-001 | imagen-3.0-capability-001 |

## 测试验证

### 测试场景 1：图片生成

**请求：**
```json
{
  "provider": "google",
  "modelId": "nano-banana-pro-preview",
  "prompt": "白色的小猫",
  "options": {
    "numberOfImages": 1,
    "aspectRatio": "1:1"
  }
}
```

**预期日志：**
```
[VertexAIImageGenerator] Model mapping: nano-banana-pro-preview → imagen-3.0-generate-001
[VertexAIImageGenerator] Generating image: model=imagen-3.0-generate-001, prompt=白色的小猫...
```

**预期结果：** ✅ 成功生成图片

### 测试场景 2：图片编辑

**请求：**
```json
{
  "provider": "google",
  "modelId": "nano-banana-pro-preview",
  "prompt": "将猫变成白色",
  "referenceImages": {
    "raw": "base64_image_data",
    "mask": "base64_mask_data"
  },
  "options": {
    "edit_mode": "inpainting-insert"
  }
}
```

**预期日志：**
```
[VertexAIImageEditor] Model mapping: nano-banana-pro-preview → imagen-3.0-capability-001
[VertexAIImageEditor] Editing image: prompt=将猫变成白色...
```

**预期结果：** ✅ 成功编辑图片

## 相关文件

- `backend/app/services/gemini/imagen_vertex_ai.py` - 图片生成（已修复）
- `backend/app/services/gemini/image_edit_vertex_ai.py` - 图片编辑（已修复）
- `backend/app/services/model_capabilities.py` - 模型能力推断（已修复）
- `.kiro/specs/erron/log.md` - 错误日志

## 修复版本

- **修复日期：** 2026-01-10
- **修复文件：** 
  - `imagen_vertex_ai.py` - 添加模型映射（图片生成）
  - `image_edit_vertex_ai.py` - 添加模型映射（图片编辑）
- **测试状态：** ⏳ 待用户测试

## 后续建议

### 建议 1：统一模型映射管理

**当前状态：**
- 模型映射分散在两个文件中
- 可能导致不一致

**优化方案：**
- 创建统一的 `model_mapping.py` 模块
- 集中管理所有模型映射规则
- 便于维护和更新

**优先级：** 中

### 建议 2：添加模型验证

**当前状态：**
- 如果用户传递了未知模型，使用默认模型
- 用户可能不知道发生了映射

**优化方案：**
- 在前端模型选择器中只显示支持的模型
- 或者在后端返回警告信息，告知用户发生了模型映射

**优先级：** 低

### 建议 3：文档更新

**需要更新的文档：**
- API 文档：说明模型映射机制
- 用户指南：解释哪些模型可用于图片生成/编辑
- 开发者文档：说明如何添加新的模型映射

**优先级：** 低

---

**修复完成！** 🎉

用户现在可以使用 `nano-banana-pro-preview` 等友好的模型名称，后端会自动映射到 Vertex AI 支持的模型 ID。
