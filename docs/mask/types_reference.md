# Mask 相关类型参考

> 基于 Google GenAI Python SDK `types.py` 源码

## 目录

1. [枚举类型](#枚举类型)
2. [配置类型](#配置类型)
3. [图像和 Mask 类型](#图像和-mask-类型)
4. [响应类型](#响应类型)

---

## 枚举类型

### MaskReferenceMode

图片编辑中的 Mask 模式。

```python
class MaskReferenceMode(Enum):
    MASK_MODE_DEFAULT = 'MASK_MODE_DEFAULT'
    MASK_MODE_USER_PROVIDED = 'MASK_MODE_USER_PROVIDED'
    MASK_MODE_BACKGROUND = 'MASK_MODE_BACKGROUND'
    MASK_MODE_FOREGROUND = 'MASK_MODE_FOREGROUND'
    MASK_MODE_SEMANTIC = 'MASK_MODE_SEMANTIC'
```

| 值 | 说明 | 需要提供 mask 图像 |
|----|------|-------------------|
| MASK_MODE_DEFAULT | 默认模式 | 否 |
| MASK_MODE_USER_PROVIDED | 使用用户提供的 mask | **是** |
| MASK_MODE_BACKGROUND | 自动生成背景 mask | 否 |
| MASK_MODE_FOREGROUND | 自动生成前景 mask | 否 |
| MASK_MODE_SEMANTIC | 基于语义分割生成 mask | 否 |

---

### SegmentMode

图片分割模式。

```python
class SegmentMode(Enum):
    FOREGROUND = 'FOREGROUND'
    BACKGROUND = 'BACKGROUND'
    PROMPT = 'PROMPT'
    SEMANTIC = 'SEMANTIC'
    INTERACTIVE = 'INTERACTIVE'
```

| 值 | 说明 | 额外输入 |
|----|------|----------|
| FOREGROUND | 分割前景对象 | 无 |
| BACKGROUND | 分割背景区域 | 无 |
| PROMPT | 基于文本描述分割 | prompt 字符串 |
| SEMANTIC | 语义分割 | 无 |
| INTERACTIVE | 交互式分割 | scribble_image |

---

### VideoGenerationMaskMode

视频生成中的 Mask 模式。

```python
class VideoGenerationMaskMode(Enum):
    INSERT = 'INSERT'
    REMOVE = 'REMOVE'
    REMOVE_STATIC = 'REMOVE_STATIC'
    OUTPAINT = 'OUTPAINT'
```

| 值 | 说明 | Mask 含义 |
|----|------|-----------|
| INSERT | 在视频中插入对象 | 白色区域 = 插入位置 |
| REMOVE | 移除跟踪对象 | 白色区域 = 要移除的对象 |
| REMOVE_STATIC | 移除静态区域内容 | 白色区域 = 要清除的固定区域 |
| OUTPAINT | 扩展视频画布 | 白色区域 = 原视频位置 |

---

### EditMode

图片编辑模式。

```python
class EditMode(Enum):
    EDIT_MODE_INPAINT_INSERTION = 'EDIT_MODE_INPAINT_INSERTION'
    EDIT_MODE_INPAINT_REMOVAL = 'EDIT_MODE_INPAINT_REMOVAL'
    EDIT_MODE_OUTPAINT = 'EDIT_MODE_OUTPAINT'
```

| 值 | 说明 |
|----|------|
| EDIT_MODE_INPAINT_INSERTION | 在 mask 区域插入新内容 |
| EDIT_MODE_INPAINT_REMOVAL | 移除 mask 区域的内容 |
| EDIT_MODE_OUTPAINT | 扩展图像边界 |

---

## 配置类型

### MaskReferenceConfig

Mask 参考配置。

```python
class MaskReferenceConfig:
    mask_mode: Optional[MaskReferenceMode] = None
    """Mask 模式"""

    segmentation_classes: Optional[list[int]] = None
    """
    语义分割类别 ID 列表（最多 5 个）。
    仅在 MASK_MODE_SEMANTIC 模式下使用。
    """

    mask_dilation: Optional[float] = None
    """
    Mask 扩张比例。
    范围：0.0 - 1.0
    - 0: 无扩张
    - 1: 覆盖整个图像
    """
```

---

### SegmentImageConfig

图片分割配置。

```python
class SegmentImageConfig:
    mode: Optional[SegmentMode] = None
    """分割模式"""

    max_predictions: Optional[int] = None
    """
    返回的预测数上限。
    按置信度排序，返回前 N 个结果。
    """

    confidence_threshold: Optional[float] = None
    """
    置信度阈值。
    范围：0.0 - 1.0
    仅返回置信度高于此值的结果。
    """

    mask_dilation: Optional[float] = None
    """
    Mask 扩张值。
    范围：0.0 - 1.0
    - 0: 无扩张
    - 1: 覆盖整个图像
    """

    binary_color_threshold: Optional[float] = None
    """
    二值化阈值。
    范围：0 - 255（非包含）
    设为 -1 禁用二值化。
    """

    labels: Optional[dict[str, str]] = None
    """用户标签，用于追踪计费"""
```

---

### EditImageConfig

图片编辑配置。

```python
class EditImageConfig:
    edit_mode: Optional[EditMode] = None
    """编辑模式"""

    number_of_images: Optional[int] = None
    """生成的图像数量"""

    negative_prompt: Optional[str] = None
    """负面提示词，指定不希望出现的内容"""

    guidance_scale: Optional[float] = None
    """
    引导强度。
    通常范围：7-20
    越高越遵循提示词，但可能降低图像质量。
    """

    safety_filter_level: Optional[SafetyFilterLevel] = None
    """安全过滤级别"""

    person_generation: Optional[PersonGeneration] = None
    """人物生成控制"""

    include_safety_attributes: Optional[bool] = None
    """是否包含安全属性"""

    include_rai_reason: Optional[bool] = None
    """是否包含 RAI 原因"""

    output_mime_type: Optional[str] = None
    """
    输出格式。
    可选：'image/jpeg', 'image/png'
    """

    output_compression_quality: Optional[int] = None
    """
    JPEG 压缩质量。
    范围：1-100
    仅在 output_mime_type='image/jpeg' 时有效。
    """

    base_steps: Optional[int] = None
    """生成步数"""

    add_watermark: Optional[bool] = None
    """是否添加水印"""

    labels: Optional[dict[str, str]] = None
    """用户标签"""
```

---

### GenerateVideosConfig

视频生成配置（Mask 相关部分）。

```python
class GenerateVideosConfig:
    output_gcs_uri: str
    """输出视频的 GCS URI"""

    aspect_ratio: Optional[str] = None
    """
    宽高比。
    可选：'16:9', '9:16'
    """

    mask: Optional[VideoGenerationMask] = None
    """视频编辑 Mask"""

    # ... 其他配置
```

---

## 图像和 Mask 类型

### Image

图像对象。

```python
class Image:
    image_bytes: Optional[bytes] = None
    """图像字节数据"""

    gcs_uri: Optional[str] = None
    """GCS URI"""

    mime_type: Optional[str] = None
    """MIME 类型：'image/jpeg', 'image/png'"""

    @classmethod
    def from_file(cls, location: str) -> 'Image':
        """从文件加载图像"""
        pass

    def show(self) -> None:
        """显示图像"""
        pass

    def save(self, path: str) -> None:
        """保存图像到文件"""
        pass
```

---

### MaskReferenceImage

Mask 参考图像。

```python
class MaskReferenceImage:
    reference_image: Optional[Image] = None
    """
    用户提供的 mask 图像。
    仅在 MASK_MODE_USER_PROVIDED 模式下需要。
    """

    reference_id: Optional[int] = None
    """
    引用 ID。
    用于在 prompt 中引用此 mask：[reference_id]
    """

    config: Optional[MaskReferenceConfig] = None
    """Mask 配置"""

    # 内部字段（自动设置）
    reference_type: str = 'REFERENCE_TYPE_MASK'
```

**使用说明**：
- 非零像素值表示要编辑的区域
- 用户提供的 mask 必须与原始图像尺寸相同

---

### RawReferenceImage

原始参考图像。

```python
class RawReferenceImage:
    reference_image: Image
    """原始图像"""

    reference_id: int
    """
    引用 ID。
    用于在 prompt 中引用此图像：[reference_id]
    """

    # 内部字段（自动设置）
    reference_type: str = 'REFERENCE_TYPE_RAW'
```

---

### VideoGenerationMask

视频生成 Mask。

```python
class VideoGenerationMask:
    image: Optional[Image] = None
    """Mask 图像"""

    mask_mode: Optional[VideoGenerationMaskMode] = None
    """Mask 使用方式"""
```

---

### ScribbleImage

涂鸦图像（用于交互式分割）。

```python
class ScribbleImage:
    image: Image
    """涂鸦图像"""
```

---

### SegmentImageSource

分割输入源。

```python
class SegmentImageSource:
    image: Image
    """要分割的图像"""

    prompt: Optional[str] = None
    """
    文本提示词。
    仅在 PROMPT 模式下使用。
    """

    scribble_image: Optional[ScribbleImage] = None
    """
    涂鸦图像。
    仅在 INTERACTIVE 模式下使用。
    """
```

---

## 响应类型

### EntityLabel

分割实体标签。

```python
class EntityLabel:
    label: Optional[str] = None
    """实体标签名称"""

    score: Optional[float] = None
    """置信度分数（0-1）"""
```

---

### GeneratedImageMask

生成的图像 Mask。

```python
class GeneratedImageMask:
    mask: Optional[Image] = None
    """生成的 mask 图像"""

    labels: Optional[list[EntityLabel]] = None
    """检测到的实体标签列表"""
```

---

### SegmentImageResponse

分割响应。

```python
class SegmentImageResponse:
    generated_masks: Optional[list[GeneratedImageMask]] = None
    """生成的 mask 列表"""
```

---

### GeneratedImage

生成的图像。

```python
class GeneratedImage:
    image: Optional[Image] = None
    """生成的图像"""

    rai_info: Optional[RAIInfo] = None
    """RAI 信息"""
```

---

### EditImageResponse

图片编辑响应。

```python
class EditImageResponse:
    generated_images: Optional[list[GeneratedImage]] = None
    """生成的图像列表"""
```

---

## 类型关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        edit_image()                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  RawReferenceImage ────┐                                     │
│    └── reference_id    │                                     │
│    └── reference_image │──► reference_images ──► API         │
│                        │                                     │
│  MaskReferenceImage ───┘                                     │
│    └── reference_id                                          │
│    └── reference_image (可选)                                │
│    └── config: MaskReferenceConfig                           │
│          └── mask_mode: MaskReferenceMode                    │
│          └── mask_dilation                                   │
│          └── segmentation_classes                            │
│                                                              │
│  EditImageConfig ──────────────────────────────► API         │
│    └── edit_mode: EditMode                                   │
│    └── number_of_images                                      │
│    └── negative_prompt                                       │
│    └── ...                                                   │
│                                                              │
│  API ──► EditImageResponse                                   │
│            └── generated_images: [GeneratedImage]            │
│                  └── image: Image                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      segment_image()                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  SegmentImageSource ───────────────────────────► API         │
│    └── image: Image                                          │
│    └── prompt (可选)                                         │
│    └── scribble_image (可选)                                 │
│                                                              │
│  SegmentImageConfig ───────────────────────────► API         │
│    └── mode: SegmentMode                                     │
│    └── max_predictions                                       │
│    └── confidence_threshold                                  │
│    └── mask_dilation                                         │
│    └── binary_color_threshold                                │
│                                                              │
│  API ──► SegmentImageResponse                                │
│            └── generated_masks: [GeneratedImageMask]         │
│                  └── mask: Image                             │
│                  └── labels: [EntityLabel]                   │
│                        └── label                             │
│                        └── score                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```
