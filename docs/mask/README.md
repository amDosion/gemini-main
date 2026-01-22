# Google GenAI SDK Mask（遮罩）功能文档

> 基于 Python GenAI SDK 源码分析，版本：python-genai-main

## 目录

1. [概述](#概述)
2. [Mask 功能场景](#mask-功能场景)
3. [核心类型定义](#核心类型定义)
4. [API 方法说明](#api-方法说明)
5. [使用示例](#使用示例)
6. [限制与注意事项](#限制与注意事项)

---

## 概述

在 Google GenAI SDK 中，Mask（遮罩）是一种核心功能，用于指定图像/视频中需要处理的区域。Mask 本质上是一个图像，其**非零像素值**表示需要处理的区域。

### Mask 的核心作用

| 场景 | 作用 |
|------|------|
| 图片编辑 | 指定要编辑的区域（如替换背景、插入对象） |
| 图片分割 | 生成 mask 作为输出，标识分割的对象 |
| 视频生成 | 控制视频编辑操作的应用方式 |

---

## Mask 功能场景

### 1. 图片编辑（edit_image）

使用 `MaskReferenceImage` 指定编辑区域，支持：
- 自动生成 mask（背景/前景/语义分割）
- 用户提供 mask 图像

### 2. 图片分割（segment_image）

使用 `SegmentImageConfig` 配置分割参数，生成 mask 输出：
- 前景/背景分割
- 基于提示词分割
- 语义分割
- 交互式分割（涂鸦）

### 3. 视频生成（generate_videos）

使用 `VideoGenerationMask` 控制视频编辑：
- 插入对象
- 移除对象
- 扩展画布（Outpaint）

---

## 核心类型定义

### MaskReferenceMode（Mask 模式枚举）

```python
class MaskReferenceMode:
    MASK_MODE_DEFAULT = 'MASK_MODE_DEFAULT'           # 默认模式
    MASK_MODE_USER_PROVIDED = 'MASK_MODE_USER_PROVIDED'  # 用户提供 mask
    MASK_MODE_BACKGROUND = 'MASK_MODE_BACKGROUND'     # 自动生成背景 mask
    MASK_MODE_FOREGROUND = 'MASK_MODE_FOREGROUND'     # 自动生成前景 mask
    MASK_MODE_SEMANTIC = 'MASK_MODE_SEMANTIC'         # 语义分割 mask
```

### SegmentMode（分割模式枚举）

```python
class SegmentMode:
    FOREGROUND = 'FOREGROUND'      # 分割前景对象
    BACKGROUND = 'BACKGROUND'      # 分割背景
    PROMPT = 'PROMPT'              # 基于文本提示分割
    SEMANTIC = 'SEMANTIC'          # 语义分割（按对象类别）
    INTERACTIVE = 'INTERACTIVE'    # 交互式分割（使用涂鸦）
```

### VideoGenerationMaskMode（视频 Mask 模式）

```python
class VideoGenerationMaskMode:
    INSERT = 'INSERT'           # 在 mask 区域插入对象
    REMOVE = 'REMOVE'           # 移除 mask 指定的跟踪对象
    REMOVE_STATIC = 'REMOVE_STATIC'  # 移除 mask 区域的所有对象
    OUTPAINT = 'OUTPAINT'       # 在 mask 外的区域生成内容
```

---

## API 方法说明

详见：
- [图片编辑 API](./edit_image_api.md)
- [图片分割 API](./segment_image_api.md)
- [视频生成 Mask API](./video_mask_api.md)

---

## 使用示例

详见：
- [图片编辑示例](./examples/edit_image_examples.md)
- [图片分割示例](./examples/segment_image_examples.md)

---

## 限制与注意事项

### API 支持限制

| 方法 | Vertex AI | Gemini API |
|------|-----------|------------|
| `edit_image()` | ✅ 支持 | ❌ 不支持 |
| `segment_image()` | ✅ 支持 | ❌ 不支持 |
| `generate_videos()` + mask | ✅ 支持 | ❌ 不支持 |

### Mask 尺寸约束

- **用户提供的 mask**：必须与原始图像尺寸相同
- **视频 inpainting masks**：必须与输入视频的宽高比匹配
- **视频 outpainting masks**：必须是 9:16 或 16:9

### Mask 扩张限制

- `mask_dilation` 范围：0-1
  - 0：无扩张
  - 1：覆盖整个图像
- 图片编辑中使用 mask_dilation 时不支持 aspect ratio 设置
