# 视频生成 Mask API 说明

## 概述

`generate_videos()` 方法支持使用 Mask 来控制视频编辑操作，包括插入对象、移除对象和扩展画布。

---

## 核心类型

### VideoGenerationMaskMode（视频 Mask 模式）

```python
class VideoGenerationMaskMode:
    INSERT = 'INSERT'
    """
    插入模式。
    mask 包含一个遮罩矩形区域，应用于视频第一帧。
    prompt 描述的对象将被插入到这个区域，并出现在后续帧中。
    """

    REMOVE = 'REMOVE'
    """
    移除模式。
    mask 用于确定视频第一帧中要跟踪的对象。
    该对象将从整个视频中被移除。
    """

    REMOVE_STATIC = 'REMOVE_STATIC'
    """
    静态区域移除模式。
    mask 用于确定视频中的一个区域。
    该区域内的所有对象将被移除。
    """

    OUTPAINT = 'OUTPAINT'
    """
    扩展模式（Outpaint）。
    mask 包含一个遮罩矩形区域，原视频将放置在这个区域内。
    其余区域将被生成。
    不支持视频 mask，只支持图像 mask。
    """
```

### VideoGenerationMask

```python
class VideoGenerationMask:
    image: Image
    """
    用于视频生成的 mask 图像。
    白色区域表示 mask 区域。
    """

    mask_mode: VideoGenerationMaskMode
    """
    Mask 的使用方式。
    """
```

---

## Mask 模式详解

### INSERT 模式

在视频中插入新对象。

**工作原理**：
1. mask 定义视频第一帧中的插入区域
2. AI 在该区域生成 prompt 描述的对象
3. 对象在后续帧中持续出现并自然融合

**约束**：
- mask 必须与视频宽高比匹配
- 适合插入静态或移动的对象

**示例**：
```python
mask = VideoGenerationMask(
    image=Image.from_file('insert_mask.png'),
    mask_mode=VideoGenerationMaskMode.INSERT,
)

operation = client.models.generate_videos(
    model='veo-3.1-generate-preview',
    source=GenerateVideosSource(
        prompt='A flying bird',
        video=Video(uri='gs://bucket/input.mp4'),
    ),
    config=GenerateVideosConfig(
        output_gcs_uri='gs://bucket/output/',
        mask=mask,
    ),
)
```

### REMOVE 模式

从视频中移除跟踪对象。

**工作原理**：
1. mask 标记第一帧中要移除的对象
2. AI 自动跟踪该对象在后续帧中的位置
3. 对象被从所有帧中移除，背景自动填充

**约束**：
- mask 必须准确覆盖目标对象
- 适合移除移动的对象

**示例**：
```python
mask = VideoGenerationMask(
    image=Image.from_file('remove_mask.png'),
    mask_mode=VideoGenerationMaskMode.REMOVE,
)
```

### REMOVE_STATIC 模式

移除静态区域中的所有内容。

**工作原理**：
1. mask 定义视频中的固定区域
2. 该区域内的所有内容（无论移动与否）都被移除
3. 区域被背景填充

**约束**：
- 区域在整个视频中保持固定
- 适合移除水印、Logo 等固定元素

**示例**：
```python
mask = VideoGenerationMask(
    image=Image.from_file('watermark_mask.png'),
    mask_mode=VideoGenerationMaskMode.REMOVE_STATIC,
)
```

### OUTPAINT 模式

扩展视频画布。

**工作原理**：
1. mask 中的白色区域放置原视频
2. mask 外的区域由 AI 生成
3. 生成内容与原视频风格一致

**约束**：
- mask 必须是 9:16 或 16:9 宽高比
- 仅支持图像 mask，不支持视频 mask
- 原视频区域必须是矩形

**示例**：
```python
mask = VideoGenerationMask(
    image=Image.from_file('outpaint_mask.png'),  # 16:9 mask
    mask_mode=VideoGenerationMaskMode.OUTPAINT,
)

operation = client.models.generate_videos(
    model='veo-3.1-generate-preview',
    source=GenerateVideosSource(
        prompt='Extend the landscape to show more mountains',
        video=Video(uri='gs://bucket/input.mp4'),
    ),
    config=GenerateVideosConfig(
        output_gcs_uri='gs://bucket/output/',
        aspect_ratio='16:9',
        mask=mask,
    ),
)
```

---

## generate_videos() 方法（Mask 相关）

### 方法签名

```python
def generate_videos(
    self,
    *,
    model: str,
    prompt: Optional[str] = None,
    image: Optional[Image] = None,
    video: Optional[Video] = None,
    source: Optional[GenerateVideosSource] = None,
    config: Optional[GenerateVideosConfig] = None,
) -> GenerateVideosOperation:
```

### GenerateVideosConfig 配置

```python
class GenerateVideosConfig:
    output_gcs_uri: str
    """输出视频的 GCS URI"""

    aspect_ratio: Optional[str]
    """宽高比：'16:9' 或 '9:16'"""

    mask: Optional[VideoGenerationMask]
    """视频编辑 mask"""

    # 其他配置...
```

---

## 完整示例

### 示例 1：在视频中插入对象

```python
from google.genai.types import (
    GenerateVideosSource, GenerateVideosConfig,
    VideoGenerationMask, VideoGenerationMaskMode,
    Video, Image
)

# 创建插入 mask（白色区域为插入位置）
insert_mask = VideoGenerationMask(
    image=Image(
        gcs_uri='gs://bucket/masks/insert_region.png',
        mime_type='image/png',
    ),
    mask_mode=VideoGenerationMaskMode.INSERT,
)

# 生成视频
operation = client.models.generate_videos(
    model='veo-3.1-generate-preview',
    source=GenerateVideosSource(
        prompt='A cute cat walking',
        video=Video(
            uri='gs://bucket/input/background.mp4',
            mime_type='video/mp4',
        ),
    ),
    config=GenerateVideosConfig(
        output_gcs_uri='gs://bucket/output/',
        aspect_ratio='16:9',
        mask=insert_mask,
    ),
)

# 等待完成
while not operation.done:
    operation = client.operations.get(operation=operation)
    print(f"Status: {operation.metadata}")

# 获取结果
video_uri = operation.result.generated_videos[0].video.uri
print(f"Generated video: {video_uri}")
```

### 示例 2：移除视频中的对象

```python
# 创建移除 mask（标记要移除的对象）
remove_mask = VideoGenerationMask(
    image=Image.from_file('person_to_remove.png'),
    mask_mode=VideoGenerationMaskMode.REMOVE,
)

operation = client.models.generate_videos(
    model='veo-3.1-generate-preview',
    source=GenerateVideosSource(
        video=Video(
            uri='gs://bucket/input/crowd_scene.mp4',
            mime_type='video/mp4',
        ),
    ),
    config=GenerateVideosConfig(
        output_gcs_uri='gs://bucket/output/',
        mask=remove_mask,
    ),
)
```

### 示例 3：移除水印

```python
# 创建水印区域 mask
watermark_mask = VideoGenerationMask(
    image=Image.from_file('watermark_region.png'),
    mask_mode=VideoGenerationMaskMode.REMOVE_STATIC,
)

operation = client.models.generate_videos(
    model='veo-3.1-generate-preview',
    source=GenerateVideosSource(
        video=Video(
            uri='gs://bucket/input/video_with_watermark.mp4',
            mime_type='video/mp4',
        ),
    ),
    config=GenerateVideosConfig(
        output_gcs_uri='gs://bucket/output/',
        mask=watermark_mask,
    ),
)
```

### 示例 4：扩展视频画布

```python
# 创建 outpaint mask
# 白色矩形区域为原视频位置，其余区域将被生成
outpaint_mask = VideoGenerationMask(
    image=Image(
        gcs_uri='gs://bucket/masks/outpaint_16x9.png',
        mime_type='image/png',
    ),
    mask_mode=VideoGenerationMaskMode.OUTPAINT,
)

operation = client.models.generate_videos(
    model='veo-3.1-generate-preview',
    source=GenerateVideosSource(
        prompt='Extend the scene to show more of the beautiful landscape',
        video=Video(
            uri='gs://bucket/input/landscape.mp4',
            mime_type='video/mp4',
        ),
    ),
    config=GenerateVideosConfig(
        output_gcs_uri='gs://bucket/output/',
        aspect_ratio='16:9',
        mask=outpaint_mask,
    ),
)
```

---

## Mask 制作指南

### INSERT Mask

```
┌─────────────────────────────┐
│                             │
│      ┌──────────┐           │
│      │ 白色区域 │ ← 插入位置 │
│      │  (255)   │           │
│      └──────────┘           │
│                             │
│   黑色背景 (0)              │
└─────────────────────────────┘
```

### REMOVE Mask

```
┌─────────────────────────────┐
│                             │
│   ╭─────╮                   │
│   │白色 │ ← 要移除的对象轮廓│
│   │区域 │                   │
│   ╰─────╯                   │
│                             │
│   黑色背景                  │
└─────────────────────────────┘
```

### OUTPAINT Mask

```
┌─────────────────────────────────┐  16:9
│   生成区域    ┌─────────┐  生成  │
│   (黑色)      │原视频   │  区域  │
│               │(白色)   │        │
│               └─────────┘        │
│   生成区域                       │
└─────────────────────────────────┘
```

---

## 注意事项

1. **API 限制**：视频 mask 功能仅支持 Vertex AI

2. **宽高比约束**：
   - INSERT/REMOVE/REMOVE_STATIC：mask 必须与输入视频宽高比匹配
   - OUTPAINT：mask 必须是 9:16 或 16:9

3. **异步操作**：`generate_videos()` 返回 Operation 对象，需要轮询等待完成

4. **存储要求**：输入视频和输出都需要使用 GCS（Google Cloud Storage）

5. **Mask 格式**：
   - 推荐使用 PNG 格式
   - 白色 (255) 表示 mask 区域
   - 黑色 (0) 表示非 mask 区域
