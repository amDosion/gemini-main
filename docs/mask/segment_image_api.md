# 图片分割 API - Mask 生成说明

## 概述

`segment_image()` 方法用于从图像中分割出特定区域，**生成 mask 作为输出**。支持多种分割模式，可用于后续的图片编辑操作。

---

## 核心类型

### SegmentMode（分割模式）

```python
class SegmentMode:
    FOREGROUND = 'FOREGROUND'
    """分割前景对象，适用于主体提取"""

    BACKGROUND = 'BACKGROUND'
    """分割背景区域"""

    PROMPT = 'PROMPT'
    """基于文本提示分割特定对象"""

    SEMANTIC = 'SEMANTIC'
    """语义分割，按对象类别分割"""

    INTERACTIVE = 'INTERACTIVE'
    """交互式分割，使用涂鸦指定区域"""
```

### SegmentImageConfig

```python
class SegmentImageConfig:
    mode: Optional[SegmentMode]
    """分割模式"""

    max_predictions: Optional[int]
    """
    返回的预测数上限，按置信度排序。
    例如：设为 1 只返回最高置信度的结果。
    """

    confidence_threshold: Optional[float]
    """
    置信度阈值（0-1）。
    仅返回置信度高于此值的预测结果。
    """

    mask_dilation: Optional[float]
    """
    Mask 扩张值（0-1）。
    - 0: 无扩张
    - 1.0: 覆盖整个图像
    """

    binary_color_threshold: Optional[float]
    """
    二值化阈值（0-255 非包含）。
    将 mask 转换为黑白二值图像。
    设为 -1 禁用二值化。
    """

    labels: Optional[dict[str, str]]
    """用户标签，用于追踪计费"""
```

### SegmentImageSource

```python
class SegmentImageSource:
    image: Image
    """要分割的图像"""

    prompt: Optional[str]
    """
    文本提示词（PROMPT 模式使用）。
    描述要分割的对象，如 "a cat"、"the red car"。
    """

    scribble_image: Optional[ScribbleImage]
    """
    涂鸦图像（INTERACTIVE 模式使用）。
    用户绘制的涂鸦指示要分割的区域。
    """
```

### GeneratedImageMask（输出）

```python
class GeneratedImageMask:
    mask: Image
    """生成的 mask 图像"""

    labels: list[EntityLabel]
    """检测到的实体标签列表"""


class EntityLabel:
    label: str
    """实体标签，如 "cat"、"foreground""""

    score: float
    """置信度分数（0-1）"""
```

---

## 分割模式详解

### FOREGROUND 模式

分割图像中的前景对象（主体）。

**特点**：
- 自动检测主要前景对象
- 无需提供额外输入
- 适用于简单场景的主体提取

**示例**：
```python
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('photo.jpg'),
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.FOREGROUND,
        max_predictions=1,
        confidence_threshold=0.5,
    ),
)
```

### BACKGROUND 模式

分割图像背景区域。

**示例**：
```python
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('photo.jpg'),
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.BACKGROUND,
    ),
)
```

### PROMPT 模式

基于文本描述分割特定对象。

**特点**：
- 支持自然语言描述
- 可精确指定要分割的对象
- 适用于复杂场景

**示例**：
```python
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('photo.jpg'),
        prompt='the red car on the left',  # 文本描述
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.PROMPT,
    ),
)
```

### SEMANTIC 模式

语义分割，按对象类别分割。

**特点**：
- 可识别多种对象类别
- 返回带标签的分割结果
- 适用于场景理解

**示例**：
```python
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('street.jpg'),
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.SEMANTIC,
        max_predictions=5,
    ),
)

# 处理多个分割结果
for mask_result in response.generated_masks:
    for label in mask_result.labels:
        print(f"Object: {label.label}, Confidence: {label.score}")
```

### INTERACTIVE 模式

交互式分割，使用用户涂鸦指定区域。

**特点**：
- 用户通过涂鸦指示区域
- 适用于精确分割
- 需要提供 scribble_image

**示例**：
```python
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('photo.jpg'),
        scribble_image=ScribbleImage(
            image=Image.from_file('scribble.png'),
        ),
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.INTERACTIVE,
    ),
)
```

---

## segment_image() 方法

### 方法签名

```python
def segment_image(
    self,
    *,
    model: str,
    source: SegmentImageSource,
    config: Optional[SegmentImageConfig] = None,
) -> SegmentImageResponse:
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | str | ✅ | 模型名称，如 `'image-segmentation-001'` |
| source | SegmentImageSource | ✅ | 输入源，包含图像、提示词或涂鸦 |
| config | SegmentImageConfig | ❌ | 分割配置 |

### 返回值

```python
class SegmentImageResponse:
    generated_masks: list[GeneratedImageMask]
    """生成的 mask 列表"""
```

---

## 完整示例

### 示例 1：前景分割

```python
from google.genai.types import (
    SegmentImageSource, SegmentImageConfig, SegmentMode, Image
)

# 执行前景分割
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('portrait.jpg'),
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.FOREGROUND,
        max_predictions=1,
        confidence_threshold=0.5,
        mask_dilation=0.02,
        binary_color_threshold=128,  # 二值化
    ),
)

# 获取 mask
mask_image = response.generated_masks[0].mask

# 显示 mask
mask_image.show()

# 保存 mask
with open('foreground_mask.png', 'wb') as f:
    f.write(mask_image.image_bytes)

# 查看检测标签
for label in response.generated_masks[0].labels:
    print(f"Label: {label.label}, Score: {label.score:.2f}")
```

### 示例 2：基于提示词分割

```python
# 分割特定对象
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('scene.jpg'),
        prompt='the golden retriever dog',
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.PROMPT,
        mask_dilation=0.03,
    ),
)

# 获取分割结果
if response.generated_masks:
    dog_mask = response.generated_masks[0].mask
    dog_mask.save('dog_mask.png')
```

### 示例 3：交互式分割

```python
# 使用涂鸦进行交互式分割
response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=Image.from_file('complex_scene.jpg'),
        scribble_image=ScribbleImage(
            image=Image.from_file('user_scribble.png'),
        ),
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.INTERACTIVE,
    ),
)
```

### 示例 4：分割后用于编辑

```python
# 步骤 1：分割前景
segment_response = client.models.segment_image(
    model='image-segmentation-001',
    source=SegmentImageSource(
        image=original_image,
    ),
    config=SegmentImageConfig(
        mode=SegmentMode.FOREGROUND,
    ),
)

foreground_mask = segment_response.generated_masks[0].mask

# 步骤 2：使用分割结果进行编辑
from google.genai.types import RawReferenceImage, MaskReferenceImage, MaskReferenceConfig

raw_ref = RawReferenceImage(
    reference_id=1,
    reference_image=original_image,
)

mask_ref = MaskReferenceImage(
    reference_id=2,
    reference_image=foreground_mask,  # 使用分割生成的 mask
    config=MaskReferenceConfig(
        mask_mode='MASK_MODE_USER_PROVIDED',
    ),
)

edit_response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Change the foreground object to a robot',
    reference_images=[raw_ref, mask_ref],
)
```

---

## 配置参数调优

### mask_dilation（扩张）

| 值 | 效果 | 适用场景 |
|------|------|----------|
| 0 | 无扩张，精确边界 | 精细编辑 |
| 0.01-0.03 | 轻微扩张 | 避免边缘伪影 |
| 0.05-0.1 | 中度扩张 | 背景替换 |
| 0.2+ | 大幅扩张 | 特殊效果 |

### confidence_threshold（置信度阈值）

| 值 | 效果 |
|------|------|
| 0.1-0.3 | 宽松，返回更多结果 |
| 0.5 | 平衡 |
| 0.7-0.9 | 严格，仅返回高置信度结果 |

### binary_color_threshold（二值化阈值）

| 值 | 效果 |
|------|------|
| -1 | 禁用，保留灰度 |
| 64 | 低阈值，更多区域为白色 |
| 128 | 中间值 |
| 192 | 高阈值，更多区域为黑色 |

---

## 注意事项

1. **API 限制**：`segment_image()` 仅支持 Vertex AI，不支持 Gemini API

2. **模型选择**：使用专门的分割模型 `'image-segmentation-001'`

3. **输出格式**：
   - `mask.image_bytes`：获取原始字节数据
   - `mask.show()`：显示图像
   - mask 中白色区域表示分割对象

4. **性能考虑**：
   - `max_predictions` 设置较小值可加快响应
   - 高分辨率图像处理时间较长

5. **涂鸦要求**（INTERACTIVE 模式）：
   - 涂鸦图像应与原图尺寸相同
   - 使用不同颜色标记前景/背景区域
