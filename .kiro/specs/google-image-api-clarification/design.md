# Design Document: Google Image API 方式梳理与实现

## Overview

本设计文档旨在梳理 Google 提供的三种图片 API 方式，并设计如何在现有代码库中正确实现 `edit_image()` 方法以支持图片编辑功能。

### 核心问题

当前代码库 (`backend/app/services/gemini/imagen_vertex_ai.py`) 只实现了两种方式：
1. `generate_images()` - 用于 Imagen 模型
2. `generate_content()` - 用于 Gemini Image 模型

缺少第三种方式：
3. `edit_image()` - 用于 Capability 模型的图片编辑

### 设计目标

1. 明确三种 API 方式的区别和适用场景
2. 在现有代码中添加 `edit_image()` 支持
3. 保持向后兼容性
4. 提供清晰的 API 选择逻辑

## Architecture

### 三种 API 方式对比

| 特性 | generate_images() | generate_content() | edit_image() |
|------|-------------------|-------------------|--------------|
| **SDK** | google-genai | google-genai | google-genai |
| **方法** | `client.models.generate_images()` | `client.models.generate_content()` | `client.models.edit_image()` |
| **模型** | Imagen-3.0, Imagen-4.0 | Gemini-2.5/3.0-pro-image, Veo-3.1 | imagen-3.0-capability-001 |
| **输入** | 文本提示词 | 文本 + 可选图片 | 文本 + Reference Images |
| **输出** | GenerateImagesResponse | GenerateContentResponse | EditImageResponse |
| **配置** | GenerateImagesConfig | GenerateContentConfig | EditImageConfig |
| **用途** | 纯图片生成 | 多模态交互 | 图片编辑 |
| **编辑能力** | ❌ | ❌ | ✅ (Inpaint, Style, Subject) |

### 模型路由策略

```python
def _determine_api_method(model_name: str) -> str:
    """
    根据模型名称决定使用哪个 API 方法
    
    Returns:
        "generate_images" | "generate_content" | "edit_image"
    """
    short_name = model_name.split('/')[-1]
    
    # Capability 模型 -> edit_image
    if "capability" in short_name:
        return "edit_image"
    
    # Gemini/Veo 模型 -> generate_content
    if any(x in short_name for x in ["gemini", "veo"]):
        return "generate_content"
    
    # Imagen 模型 -> generate_images
    return "generate_images"
```

### 架构层次

```
VertexAIImageGenerator
├── generate() [公共接口]
│   ├── _determine_api_method() [路由逻辑]
│   ├── _generate_with_imagen() [方式 1]
│   ├── _generate_with_gemini() [方式 2]
│   └── _edit_with_capability() [方式 3 - 新增]
│
├── edit() [新增公共接口]
│   └── _edit_with_capability()
│
└── _process_response() [统一响应处理]
```

## Components and Interfaces

### 1. Reference Image 类型系统

```python
from google.genai import types

# 基础图片
RawReferenceImage(
    reference_id: int,
    reference_image: types.Image
)

# Mask 图片
MaskReferenceImage(
    reference_id: int,
    reference_image: types.Image,  # 可选，如果不提供则自动生成
    config: types.MaskReferenceConfig(
        mask_mode: "MASK_MODE_FOREGROUND" | "MASK_MODE_BACKGROUND" | "MASK_MODE_USER_PROVIDED",
        mask_dilation: float  # 0.0 - 1.0
    )
)

# 控制图片
ControlReferenceImage(
    reference_id: int,
    reference_image: types.Image,
    config: types.ControlReferenceConfig(
        control_type: "CONTROL_TYPE_SCRIBBLE" | "CONTROL_TYPE_EDGE" | "CONTROL_TYPE_DEPTH",
        enable_control_image_computation: bool
    )
)

# 风格参考
StyleReferenceImage(
    reference_id: int,
    reference_image: types.Image,
    config: types.StyleReferenceConfig(
        style_description: str
    )
)

# 主体参考
SubjectReferenceImage(
    reference_id: int,
    reference_image: types.Image,
    config: types.SubjectReferenceConfig(
        subject_type: "SUBJECT_TYPE_PRODUCT" | "SUBJECT_TYPE_PERSON",
        subject_description: str
    )
)

# 内容参考
ContentReferenceImage(
    reference_id: int,
    reference_image: types.Image  # 支持 GCS URI
)
```

### 2. EditImageConfig 配置

```python
types.EditImageConfig(
    # 编辑模式
    edit_mode: str = "EDIT_MODE_INPAINT_INSERTION",
    # EDIT_MODE_INPAINT_INSERTION - 插入新内容
    # EDIT_MODE_INPAINT_REMOVAL - 移除内容
    # EDIT_MODE_OUTPAINT - 扩展图片
    
    # 生成参数
    number_of_images: int = 1,
    guidance_scale: float = 7.5,
    negative_prompt: str = "",
    base_steps: int = 50,
    
    # 输出参数
    aspect_ratio: str = "1:1",
    output_mime_type: str = "image/png",
    output_compression_quality: int = 95,
    
    # 安全参数
    safety_filter_level: str = "block_some",
    person_generation: str = "allow_adult",
    include_rai_reason: bool = True,
    
    # 水印
    add_watermark: bool = False
)
```

### 3. 新增方法签名

```python
class VertexAIImageGenerator:
    async def edit(
        self,
        model: str,
        prompt: str,
        base_image: bytes,
        mask_image: Optional[bytes] = None,
        mask_mode: str = "MASK_MODE_FOREGROUND",
        edit_mode: str = "EDIT_MODE_INPAINT_INSERTION",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        编辑图片
        
        Args:
            model: 模型名称（必须是 capability 模型）
            prompt: 编辑提示词
            base_image: 基础图片字节
            mask_image: Mask 图片字节（可选）
            mask_mode: Mask 模式
            edit_mode: 编辑模式
            **kwargs: 其他配置参数
            
        Returns:
            生成的图片列表
        """
```

## Data Models

### 输入数据模型

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class EditImageRequest(BaseModel):
    """图片编辑请求"""
    model: str = Field(..., description="模型名称")
    prompt: str = Field(..., description="编辑提示词")
    base_image: bytes = Field(..., description="基础图片")
    mask_image: Optional[bytes] = Field(None, description="Mask 图片")
    
    # Mask 配置
    mask_mode: Literal[
        "MASK_MODE_FOREGROUND",
        "MASK_MODE_BACKGROUND", 
        "MASK_MODE_USER_PROVIDED"
    ] = "MASK_MODE_FOREGROUND"
    mask_dilation: float = Field(0.0, ge=0.0, le=1.0)
    
    # 编辑配置
    edit_mode: Literal[
        "EDIT_MODE_INPAINT_INSERTION",
        "EDIT_MODE_INPAINT_REMOVAL",
        "EDIT_MODE_OUTPAINT"
    ] = "EDIT_MODE_INPAINT_INSERTION"
    
    # 生成参数
    number_of_images: int = Field(1, ge=1, le=8)
    guidance_scale: float = Field(7.5, ge=0.0, le=20.0)
    negative_prompt: Optional[str] = None
    
    # 输出参数
    aspect_ratio: str = "1:1"
    output_mime_type: str = "image/png"

class ReferenceImageInput(BaseModel):
    """Reference Image 输入"""
    type: Literal["raw", "mask", "control", "style", "subject", "content"]
    image_bytes: Optional[bytes] = None
    gcs_uri: Optional[str] = None
    config: Optional[dict] = None
```

### 输出数据模型

```python
class EditImageResponse(BaseModel):
    """图片编辑响应"""
    generated_images: List[GeneratedImage]
    
class GeneratedImage(BaseModel):
    """生成的图片"""
    url: str  # Data URL
    mime_type: str
    index: int
    size: int
    rai_filtered: bool = False
    rai_reason: Optional[str] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Model Routing Correctness

*For any* model name, the routing logic should correctly identify whether to use `generate_images()`, `generate_content()`, or `edit_image()` based on the model type.

**Validates: Requirements 8.1**

### Property 2: Edit Mode Support

*For any* valid edit mode (INPAINT_INSERTION, INPAINT_REMOVAL, OUTPAINT), the system should correctly configure and execute the edit operation.

**Validates: Requirements 8.2**

### Property 3: Reference Image Combination

*For any* valid combination of Reference Image types, the system should correctly construct the reference_images list and pass it to the API.

**Validates: Requirements 8.3**

### Property 4: Mask Processing

*For any* mask image and mask configuration, the system should correctly create a MaskReferenceImage with the specified mode and dilation.

**Validates: Requirements 8.4**

### Property 5: Backward Compatibility

*For any* existing call to `generate()` with Imagen or Gemini models, the behavior should remain unchanged after adding `edit_image()` support.

**Validates: Requirements 8.5**

## Error Handling

### 错误类型

1. **模型不支持错误**
   - 场景：使用非 capability 模型调用 `edit_image()`
   - 处理：抛出 `ValueError` 并提示正确的模型

2. **Reference Image 错误**
   - 场景：缺少必需的 Reference Image（如基础图片）
   - 处理：抛出 `ValueError` 并说明缺少哪个 Reference Image

3. **Mask 配置错误**
   - 场景：mask_mode 为 USER_PROVIDED 但未提供 mask_image
   - 处理：抛出 `ValueError` 并提示需要提供 mask 图片

4. **API 调用错误**
   - 场景：Vertex AI API 返回错误
   - 处理：包装为 `APIError` 并保留原始错误信息

5. **响应解析错误**
   - 场景：API 响应格式不符合预期
   - 处理：记录详细日志并抛出 `APIError`

### 错误处理流程

```python
try:
    # 1. 验证输入
    validate_edit_request(model, base_image, mask_image, mask_mode)
    
    # 2. 构建 Reference Images
    reference_images = build_reference_images(...)
    
    # 3. 调用 API
    response = client.models.edit_image(...)
    
    # 4. 处理响应
    return process_edit_response(response)
    
except ValueError as e:
    logger.error(f"Invalid input: {e}")
    raise
    
except Exception as e:
    logger.error(f"Edit failed: {e}")
    raise APIError(f"Image edit failed: {e}", original_error=e)
```

## Testing Strategy

### 单元测试

1. **路由逻辑测试**
   - 测试不同模型名称的路由结果
   - 测试边界情况（空字符串、特殊字符）

2. **Reference Image 构建测试**
   - 测试每种 Reference Image 类型的构建
   - 测试组合场景

3. **配置构建测试**
   - 测试 EditImageConfig 的各种参数组合
   - 测试默认值和边界值

4. **错误处理测试**
   - 测试各种错误场景
   - 验证错误消息的准确性

### 属性测试

使用 Hypothesis 进行属性测试：

1. **Property 1: Model Routing Correctness**
   ```python
   @given(model_name=st.text())
   def test_model_routing(model_name):
       method = _determine_api_method(model_name)
       assert method in ["generate_images", "generate_content", "edit_image"]
       
       if "capability" in model_name:
           assert method == "edit_image"
   ```

2. **Property 2: Edit Mode Support**
   ```python
   @given(
       edit_mode=st.sampled_from([
           "EDIT_MODE_INPAINT_INSERTION",
           "EDIT_MODE_INPAINT_REMOVAL",
           "EDIT_MODE_OUTPAINT"
       ])
   )
   def test_edit_mode_support(edit_mode):
       config = build_edit_config(edit_mode=edit_mode)
       assert config.edit_mode == edit_mode
   ```

3. **Property 3: Reference Image Combination**
   ```python
   @given(
       has_raw=st.booleans(),
       has_mask=st.booleans(),
       has_style=st.booleans()
   )
   def test_reference_image_combination(has_raw, has_mask, has_style):
       images = build_reference_images(
           raw=has_raw,
           mask=has_mask,
           style=has_style
       )
       assert len(images) == sum([has_raw, has_mask, has_style])
   ```

4. **Property 4: Mask Processing**
   ```python
   @given(
       mask_mode=st.sampled_from([
           "MASK_MODE_FOREGROUND",
           "MASK_MODE_BACKGROUND",
           "MASK_MODE_USER_PROVIDED"
       ]),
       mask_dilation=st.floats(min_value=0.0, max_value=1.0)
   )
   def test_mask_processing(mask_mode, mask_dilation):
       mask_ref = build_mask_reference(
           mode=mask_mode,
           dilation=mask_dilation
       )
       assert mask_ref.config.mask_mode == mask_mode
       assert mask_ref.config.mask_dilation == mask_dilation
   ```

5. **Property 5: Backward Compatibility**
   ```python
   @given(
       model=st.sampled_from(["imagen-3.0-generate-001", "gemini-2.5-flash-image"]),
       prompt=st.text(min_size=1)
   )
   def test_backward_compatibility(model, prompt):
       # 确保旧的调用方式仍然有效
       result = generator.generate(model=model, prompt=prompt)
       assert len(result) > 0
   ```

### 集成测试

1. **端到端编辑测试**
   - 使用真实的 Vertex AI API
   - 测试完整的编辑流程
   - 验证生成的图片质量

2. **多种编辑模式测试**
   - 测试 INPAINT_INSERTION
   - 测试 INPAINT_REMOVAL
   - 测试 OUTPAINT

3. **Reference Image 组合测试**
   - 测试不同的 Reference Image 组合
   - 验证 API 响应

### 测试配置

- 属性测试最少运行 100 次迭代
- 每个属性测试标注对应的设计文档属性编号
- 标签格式：`# Feature: google-image-api-clarification, Property {N}: {property_text}`
