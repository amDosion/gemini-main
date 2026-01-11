# Gemini 图片生成模型测试报告

**测试日期**: 2026-01-10  
**测试目的**: 验证 Gemini 图片模型使用 `generate_content()` 方法而非 `generate_images()` 方法

## 测试结果总结

### ✅ 成功的模型
| 模型 ID | 完整路径 | 方法 | 状态 |
|---------|---------|------|------|
| gemini-2.5-flash-image | publishers/google/models/gemini-2.5-flash-image | `generate_content()` | ✅ 成功生成图片 |

### ❌ 失败的模型
| 模型 ID | 完整路径 | 错误 | 原因 |
|---------|---------|------|------|
| gemini-3-pro-image-preview | publishers/google/models/gemini-3-pro-image-preview | 404 NOT_FOUND | 所有区域均不可用 |
| gemini-2.5-flash-image-preview | publishers/google/models/gemini-2.5-flash-image-preview | 404 NOT_FOUND | 预览版本不可用 |
| nano-banana-pro-preview | N/A | 404 NOT_FOUND | 模型不存在 |

## 关键发现

### 1. Gemini 图片模型使用不同的 API 方法

**Imagen 模型** (imagen-3.0-*, imagen-4.0-*):
```python
response = client.models.generate_images(
    model='publishers/google/models/imagen-3.0-generate-002',
    prompt="A white cat",
    config=GenerateImagesConfig(...)
)
```

**Gemini 图片模型** (gemini-*-image):
```python
response = client.models.generate_content(
    model='publishers/google/models/gemini-2.5-flash-image',
    contents=[Content(role="user", parts=[Part.from_text("Generate a white cat")])],
    config=GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],  # 关键配置
        image_config=ImageConfig(...)
    )
)
```

### 2. 配置差异

| 配置项 | Imagen (generate_images) | Gemini (generate_content) |
|--------|--------------------------|---------------------------|
| 输入格式 | `prompt: str` | `contents: List[Content]` |
| 配置类型 | `GenerateImagesConfig` | `GenerateContentConfig` |
| 关键参数 | `number_of_images`, `aspect_ratio` | `response_modalities=["TEXT", "IMAGE"]` |
| 输出格式 | `GeneratedImage` 对象 | `Candidate.content.parts` (inline_data) |

### 3. 模型路径格式

所有 Vertex AI 模型必须使用完整路径：
- ✅ 正确: `publishers/google/models/gemini-2.5-flash-image`
- ❌ 错误: `gemini-2.5-flash-image`

## 当前实现问题

### 问题 1: 错误的 MODEL_MAPPING
**文件**: `backend/app/services/gemini/imagen_vertex_ai.py`

```python
# ❌ 当前实现（错误）
MODEL_MAPPING = {
    'gemini-3-pro-image-preview': 'imagen-3.0-generate-001',  # 错误映射
    'gemini-2.5-flash-image': 'imagen-3.0-generate-001',      # 错误映射
}

# 然后使用 generate_images() 方法
response = self._client.models.generate_images(
    model=vertex_model,  # imagen-3.0-generate-001
    prompt=effective_prompt,
    config=config
)
```

**问题**: 
- Gemini 图片模型被错误地映射到 Imagen 模型
- 使用了错误的 API 方法 (`generate_images` 而非 `generate_content`)
- 导致功能无法正常工作

### 问题 2: 缺少 Gemini 图片生成服务
当前只有 `imagen_vertex_ai.py`，没有专门处理 Gemini 图片模型的服务。

## 解决方案

### 方案 1: 双路径架构（推荐）

创建两个独立的服务类：

1. **imagen_vertex_ai.py** - 处理 Imagen 模型
   - 使用 `generate_images()` 方法
   - 支持: imagen-3.0-*, imagen-4.0-*

2. **gemini_image_vertex_ai.py** - 处理 Gemini 图片模型
   - 使用 `generate_content()` 方法
   - 支持: gemini-*-image

3. **路由逻辑** - 在 `image_coordinator.py` 中
   ```python
   if model.startswith('gemini-') and '-image' in model:
       # 使用 GeminiImageVertexAIGenerator
   elif model.startswith('imagen-'):
       # 使用 VertexAIImageGenerator
   ```

### 方案 2: 统一服务（不推荐）

在 `imagen_vertex_ai.py` 中添加条件判断：
```python
if model.startswith('gemini-') and '-image' in model:
    # 使用 generate_content()
else:
    # 使用 generate_images()
```

**缺点**: 代码复杂度高，难以维护

## 下一步行动

1. ✅ **移除错误的 MODEL_MAPPING**
   - 从 `imagen_vertex_ai.py` 中移除 Gemini 模型映射
   - 从 `image_edit_vertex_ai.py` 中移除 Gemini 模型映射

2. ✅ **创建 `gemini_image_vertex_ai.py`**
   - 实现 `generate_content()` 方法
   - 支持 `gemini-2.5-flash-image`
   - 处理 `response_modalities=["TEXT", "IMAGE"]`

3. ✅ **更新路由逻辑**
   - 在 `image_coordinator.py` 中添加模型类型检测
   - 根据模型类型选择正确的生成器

4. ✅ **更新模型能力检测**
   - 确保 `model_capabilities.py` 正确识别 Gemini 图片模型

5. ✅ **端到端测试**
   - 测试 Imagen 模型（generate_images）
   - 测试 Gemini 图片模型（generate_content）
   - 测试前端集成

## 测试脚本

已创建的测试脚本：
- `backend/test_gemini_3_pro_image.py` - 测试 Gemini 图片模型
- `backend/test_list_vertex_models.py` - 列出所有可用模型
- `backend/test_gemini_3_regions.py` - 测试区域可用性
- `backend/test_model_details.py` - 获取模型详细信息

## 参考文档

- Google Cloud Console 示例: 显示 `gemini-3-pro-image-preview` 使用 `generate_content()`
- Vertex AI 文档: https://cloud.google.com/vertex-ai/generative-ai/docs/image/generate-images
- Google GenAI SDK: `.kiro/specs/参考/python-genai-main/google/genai/`
