# 图片分割 Mask 示例代码

## 示例概览

| 示例 | 描述 | 分割模式 |
|------|------|----------|
| [示例 1](#示例-1前景分割) | 前景分割 | FOREGROUND |
| [示例 2](#示例-2背景分割) | 背景分割 | BACKGROUND |
| [示例 3](#示例-3提示词分割) | 基于提示词分割 | PROMPT |
| [示例 4](#示例-4语义分割) | 语义分割 | SEMANTIC |
| [示例 5](#示例-5交互式分割) | 交互式分割（涂鸦） | INTERACTIVE |

---

## 示例 1：前景分割

自动分割图像中的前景主体。

```python
from google import genai
from google.genai import types

# 初始化客户端
client = genai.Client(vertexai=True, project='your-project', location='us-central1')

# 加载图像
source_image = types.Image.from_file('portrait.jpg')

# 执行前景分割
response = client.models.segment_image(
    model='image-segmentation-001',
    source=types.SegmentImageSource(
        image=source_image,
    ),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.FOREGROUND,
        max_predictions=1,  # 只返回最佳结果
        confidence_threshold=0.5,
        mask_dilation=0.02,
        binary_color_threshold=128,  # 二值化
    ),
)

# 处理结果
if response.generated_masks:
    mask_result = response.generated_masks[0]

    # 获取 mask 图像
    mask_image = mask_result.mask

    # 查看检测标签
    for label in mask_result.labels:
        print(f"检测到: {label.label}, 置信度: {label.score:.2f}")

    # 保存 mask
    with open('foreground_mask.png', 'wb') as f:
        f.write(mask_image.image_bytes)

    print("前景分割完成！")
```

---

## 示例 2：背景分割

分割图像背景区域。

```python
# 加载图像
source_image = types.Image.from_file('scene.jpg')

# 执行背景分割
response = client.models.segment_image(
    model='image-segmentation-001',
    source=types.SegmentImageSource(
        image=source_image,
    ),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.BACKGROUND,
        mask_dilation=0.03,
    ),
)

# 保存背景 mask
if response.generated_masks:
    background_mask = response.generated_masks[0].mask
    with open('background_mask.png', 'wb') as f:
        f.write(background_mask.image_bytes)
```

---

## 示例 3：提示词分割

基于文本描述分割特定对象。

```python
# 加载包含多个对象的图像
source_image = types.Image.from_file('living_room.jpg')

# 使用提示词分割特定对象
response = client.models.segment_image(
    model='image-segmentation-001',
    source=types.SegmentImageSource(
        image=source_image,
        prompt='the red sofa',  # 描述要分割的对象
    ),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.PROMPT,
        confidence_threshold=0.4,
        mask_dilation=0.02,
    ),
)

# 保存沙发 mask
if response.generated_masks:
    sofa_mask = response.generated_masks[0].mask

    # 查看检测结果
    for label in response.generated_masks[0].labels:
        print(f"分割对象: {label.label}, 置信度: {label.score:.2f}")

    with open('sofa_mask.png', 'wb') as f:
        f.write(sofa_mask.image_bytes)
```

### 更多提示词示例

```python
# 分割特定颜色的对象
prompt='the blue car'

# 分割特定位置的对象
prompt='the person on the left'

# 分割特定类型的对象
prompt='all the flowers in the image'

# 分割特定品牌
prompt='the Apple logo'
```

---

## 示例 4：语义分割

按对象类别进行语义分割，返回多个分割结果。

```python
# 加载街景图像
source_image = types.Image.from_file('street.jpg')

# 执行语义分割
response = client.models.segment_image(
    model='image-segmentation-001',
    source=types.SegmentImageSource(
        image=source_image,
    ),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.SEMANTIC,
        max_predictions=10,  # 返回多个类别
        confidence_threshold=0.3,
    ),
)

# 处理多个分割结果
print(f"检测到 {len(response.generated_masks)} 个对象类别")

for i, mask_result in enumerate(response.generated_masks):
    # 获取类别标签
    labels = mask_result.labels
    if labels:
        category = labels[0].label
        confidence = labels[0].score
        print(f"\n类别 {i+1}: {category} (置信度: {confidence:.2f})")

    # 保存每个类别的 mask
    mask = mask_result.mask
    with open(f'semantic_mask_{i}_{category}.png', 'wb') as f:
        f.write(mask.image_bytes)
```

---

## 示例 5：交互式分割

使用用户涂鸦进行交互式分割。

```python
# 加载原图和用户涂鸦图像
source_image = types.Image.from_file('complex_scene.jpg')
scribble_image = types.Image.from_file('user_scribble.png')

# 执行交互式分割
response = client.models.segment_image(
    model='image-segmentation-001',
    source=types.SegmentImageSource(
        image=source_image,
        scribble_image=types.ScribbleImage(
            image=scribble_image,
        ),
    ),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.INTERACTIVE,
        mask_dilation=0.02,
    ),
)

# 保存分割结果
if response.generated_masks:
    interactive_mask = response.generated_masks[0].mask
    with open('interactive_mask.png', 'wb') as f:
        f.write(interactive_mask.image_bytes)
```

### 创建涂鸦图像

```python
from PIL import Image, ImageDraw

# 加载原图获取尺寸
original = Image.open('complex_scene.jpg')
width, height = original.size

# 创建涂鸦图像（黑色背景）
scribble = Image.new('RGB', (width, height), (0, 0, 0))
draw = ImageDraw.Draw(scribble)

# 绿色涂鸦表示前景（要分割的对象）
# 红色涂鸦表示背景（不要分割的区域）

# 在要分割的对象上画绿色线条
draw.line([(100, 100), (200, 150), (150, 200)], fill=(0, 255, 0), width=5)

# 在背景上画红色线条
draw.line([(300, 50), (350, 100)], fill=(255, 0, 0), width=5)

# 保存涂鸦图像
scribble.save('user_scribble.png')
```

---

## 批量分割处理

```python
import os
from pathlib import Path

def batch_segment_images(image_folder, output_folder, mode=types.SegmentMode.FOREGROUND):
    """批量分割图像"""

    Path(output_folder).mkdir(parents=True, exist_ok=True)

    for filename in os.listdir(image_folder):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(image_folder, filename)

            try:
                # 加载图像
                source_image = types.Image.from_file(image_path)

                # 执行分割
                response = client.models.segment_image(
                    model='image-segmentation-001',
                    source=types.SegmentImageSource(image=source_image),
                    config=types.SegmentImageConfig(
                        mode=mode,
                        max_predictions=1,
                        confidence_threshold=0.5,
                    ),
                )

                # 保存 mask
                if response.generated_masks:
                    mask = response.generated_masks[0].mask
                    output_path = os.path.join(output_folder, f'mask_{filename}')
                    with open(output_path, 'wb') as f:
                        f.write(mask.image_bytes)
                    print(f"✓ 处理完成: {filename}")
                else:
                    print(f"✗ 无法分割: {filename}")

            except Exception as e:
                print(f"✗ 处理失败 {filename}: {e}")

# 使用示例
batch_segment_images(
    image_folder='./input_images',
    output_folder='./output_masks',
    mode=types.SegmentMode.FOREGROUND
)
```

---

## 分割结果可视化

```python
from PIL import Image
import numpy as np

def visualize_segmentation(original_path, mask_path, output_path, alpha=0.5):
    """将分割 mask 叠加到原图上进行可视化"""

    # 加载原图和 mask
    original = Image.open(original_path).convert('RGBA')
    mask = Image.open(mask_path).convert('L')

    # 确保尺寸一致
    mask = mask.resize(original.size)

    # 创建彩色叠加层（红色表示分割区域）
    overlay = Image.new('RGBA', original.size, (255, 0, 0, 0))
    mask_np = np.array(mask)
    overlay_np = np.array(overlay)

    # 在 mask 区域添加红色叠加
    overlay_np[mask_np > 128] = [255, 0, 0, int(255 * alpha)]
    overlay = Image.fromarray(overlay_np, 'RGBA')

    # 合成图像
    result = Image.alpha_composite(original, overlay)
    result.save(output_path)

    print(f"可视化结果已保存: {output_path}")

# 使用示例
visualize_segmentation(
    original_path='portrait.jpg',
    mask_path='foreground_mask.png',
    output_path='segmentation_visualization.png',
    alpha=0.4
)
```

---

## 使用分割结果进行抠图

```python
from PIL import Image
import numpy as np

def extract_foreground(original_path, mask_path, output_path):
    """使用 mask 提取前景（透明背景）"""

    # 加载原图和 mask
    original = Image.open(original_path).convert('RGBA')
    mask = Image.open(mask_path).convert('L')

    # 确保尺寸一致
    mask = mask.resize(original.size)

    # 将 mask 应用为 alpha 通道
    original_np = np.array(original)
    mask_np = np.array(mask)

    # 设置透明度
    original_np[:, :, 3] = mask_np

    # 保存结果（PNG 格式保留透明度）
    result = Image.fromarray(original_np, 'RGBA')
    result.save(output_path, 'PNG')

    print(f"抠图结果已保存: {output_path}")

# 使用示例
extract_foreground(
    original_path='portrait.jpg',
    mask_path='foreground_mask.png',
    output_path='extracted_foreground.png'
)
```

---

## 配置参数调优指南

### confidence_threshold

```python
# 低阈值：返回更多结果，可能包含误检
config = types.SegmentImageConfig(
    confidence_threshold=0.2,
)

# 中等阈值：平衡精度和召回率
config = types.SegmentImageConfig(
    confidence_threshold=0.5,
)

# 高阈值：只返回高置信度结果
config = types.SegmentImageConfig(
    confidence_threshold=0.8,
)
```

### mask_dilation

```python
# 无扩张：精确边界
config = types.SegmentImageConfig(
    mask_dilation=0,
)

# 轻微扩张：避免边缘伪影（推荐）
config = types.SegmentImageConfig(
    mask_dilation=0.02,
)

# 中度扩张：更宽松的边界
config = types.SegmentImageConfig(
    mask_dilation=0.1,
)
```

### binary_color_threshold

```python
# 禁用二值化：保留灰度值
config = types.SegmentImageConfig(
    binary_color_threshold=-1,
)

# 中等阈值：平衡
config = types.SegmentImageConfig(
    binary_color_threshold=128,
)

# 高阈值：更严格的边界
config = types.SegmentImageConfig(
    binary_color_threshold=200,
)
```

---

## 错误处理

```python
try:
    response = client.models.segment_image(
        model='image-segmentation-001',
        source=types.SegmentImageSource(
            image=source_image,
        ),
        config=types.SegmentImageConfig(
            mode=types.SegmentMode.FOREGROUND,
        ),
    )

    if response.generated_masks:
        # 处理成功结果
        pass
    else:
        print("未检测到任何对象，尝试降低 confidence_threshold")

except Exception as e:
    if "RESOURCE_EXHAUSTED" in str(e):
        print("配额耗尽，请稍后重试")
    elif "INVALID_ARGUMENT" in str(e):
        print("参数错误，请检查图像格式和配置")
    else:
        print(f"分割失败: {e}")
```
