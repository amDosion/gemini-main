# 图片编辑 API - Mask 相关说明

## 概述

`edit_image()` 方法支持使用 Mask 来指定图像编辑区域。可以使用自动生成的 mask 或用户提供的 mask 图像。

---

## 核心类型

### MaskReferenceConfig

配置 Mask 的生成和使用方式。

```python
class MaskReferenceConfig:
    mask_mode: Optional[MaskReferenceMode]
    """
    Mask 模式，指定如何生成或使用 mask。
    - MASK_MODE_DEFAULT: 默认模式
    - MASK_MODE_USER_PROVIDED: 使用用户提供的 mask 图像
    - MASK_MODE_BACKGROUND: 自动生成背景 mask
    - MASK_MODE_FOREGROUND: 自动生成前景 mask
    - MASK_MODE_SEMANTIC: 基于语义分割生成 mask
    """

    segmentation_classes: Optional[list[int]]
    """
    语义分割类别 ID 列表（最多 5 个）。
    仅在 MASK_MODE_SEMANTIC 模式下使用。
    自动基于特定对象类别创建 mask。
    """

    mask_dilation: Optional[float]
    """
    Mask 扩张比例，范围 0-1。
    - 0: 无扩张，保持原始边界
    - 0.06: 温和扩张（推荐值）
    - 1.0: 覆盖整个图像
    """
```

### MaskReferenceImage

Mask 参考图像，封装 mask 图像和配置。

```python
class MaskReferenceImage:
    reference_image: Optional[Image]
    """
    用户提供的 mask 图像。
    仅在 MASK_MODE_USER_PROVIDED 模式下需要。
    mask 必须与原始图像尺寸相同。
    非零像素值表示要编辑的区域。
    """

    reference_id: Optional[int]
    """
    引用 ID，用于在提示词中引用此 mask。
    格式：[reference_id]
    """

    config: Optional[MaskReferenceConfig]
    """
    Mask 配置。
    """
```

---

## Mask 模式详解

### MASK_MODE_BACKGROUND

自动生成背景 mask，编辑背景区域，保留前景。

**适用场景**：
- 替换背景
- 背景模糊
- 背景风格化

**示例**：
```python
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_BACKGROUND',
        mask_dilation=0.06,
    ),
)
```

### MASK_MODE_FOREGROUND

自动生成前景 mask，编辑前景区域，保留背景。

**适用场景**：
- 修改前景对象
- 对象风格化
- 对象替换

**示例**：
```python
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_FOREGROUND',
        mask_dilation=0.06,
    ),
)
```

### MASK_MODE_USER_PROVIDED

使用用户提供的 mask 图像。

**要求**：
- mask 图像尺寸必须与原始图像相同
- 非零像素值表示要编辑的区域
- 零值像素表示保留的区域

**示例**：
```python
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    reference_image=Image.from_file('my_mask.png'),
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_USER_PROVIDED',
        mask_dilation=0.06,
    ),
)
```

### MASK_MODE_SEMANTIC

基于语义分割自动生成 mask，针对特定对象类别。

**示例**：
```python
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_SEMANTIC',
        segmentation_classes=[1, 2, 3],  # 指定类别 ID
        mask_dilation=0.06,
    ),
)
```

---

## edit_image() 方法

### 方法签名

```python
def edit_image(
    self,
    *,
    model: str,
    prompt: str,
    reference_images: list[ReferenceImage],
    config: Optional[EditImageConfig] = None,
) -> EditImageResponse:
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | str | ✅ | 模型名称，如 `'imagen-3.0-capability-001'` |
| prompt | str | ✅ | 编辑描述，可使用 `[reference_id]` 引用图像 |
| reference_images | list | ✅ | 参考图像列表，包括原始图像和 mask |
| config | EditImageConfig | ❌ | 编辑配置 |

### EditImageConfig 配置

```python
class EditImageConfig:
    edit_mode: EditMode
    """
    编辑模式：
    - EDIT_MODE_INPAINT_INSERTION: 在 mask 区域插入内容
    - EDIT_MODE_INPAINT_REMOVAL: 移除 mask 区域的内容
    - EDIT_MODE_OUTPAINT: 扩展图像边界
    """

    number_of_images: int
    """生成的图像数量"""

    negative_prompt: Optional[str]
    """负面提示词，指定不希望出现的内容"""

    guidance_scale: Optional[float]
    """引导强度，通常 7-20"""

    safety_filter_level: Optional[SafetyFilterLevel]
    """安全过滤级别"""

    output_mime_type: Optional[str]
    """输出格式：'image/jpeg' 或 'image/png'"""

    output_compression_quality: Optional[int]
    """JPEG 压缩质量 (1-100)"""
```

---

## 完整示例

### 示例 1：自动背景替换

```python
from google.genai.types import (
    RawReferenceImage, MaskReferenceImage, MaskReferenceConfig,
    Image, EditImageConfig, EditMode
)

# 1. 准备原始图像
raw_ref_image = RawReferenceImage(
    reference_id=1,
    reference_image=Image.from_file('original.jpg'),
)

# 2. 配置背景 mask（自动生成）
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_BACKGROUND',
        mask_dilation=0.06,
    ),
)

# 3. 执行编辑
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Replace background with a sunset beach scene',
    reference_images=[raw_ref_image, mask_ref_image],
    config=EditImageConfig(
        edit_mode=EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
        negative_prompt='blurry, low quality',
        guidance_scale=15.0,
    ),
)

# 4. 获取结果
edited_image = response.generated_images[0].image
edited_image.show()
```

### 示例 2：使用用户 Mask 编辑

```python
# 1. 准备原始图像
raw_ref_image = RawReferenceImage(
    reference_id=1,
    reference_image=Image.from_file('original.jpg'),
)

# 2. 使用用户提供的 mask
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    reference_image=Image.from_file('my_mask.png'),  # 用户绘制的 mask
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_USER_PROVIDED',
        mask_dilation=0.06,
    ),
)

# 3. 执行编辑
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Add a beautiful flower in the masked area',
    reference_images=[raw_ref_image, mask_ref_image],
    config=EditImageConfig(
        edit_mode=EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)
```

### 示例 3：前景编辑

```python
# 配置前景 mask
mask_ref_image = MaskReferenceImage(
    reference_id=2,
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_FOREGROUND',
        mask_dilation=0.06,
    ),
)

response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Change the person to wear a red dress',
    reference_images=[raw_ref_image, mask_ref_image],
    config=EditImageConfig(
        edit_mode=EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)
```

---

## 注意事项

1. **API 限制**：`edit_image()` 仅支持 Vertex AI，不支持 Gemini API

2. **Mask 尺寸**：用户提供的 mask 必须与原始图像尺寸完全相同

3. **Mask 格式**：
   - 非零像素 = 编辑区域
   - 零像素 = 保留区域
   - 推荐使用 PNG 格式以保持精确度

4. **扩张参数**：`mask_dilation` 设置过大可能导致编辑区域超出预期

5. **引用 ID**：在 prompt 中使用 `[reference_id]` 引用特定图像
