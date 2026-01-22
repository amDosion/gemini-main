# 图片编辑 Mask 示例代码

## 示例概览

| 示例 | 描述 | Mask 模式 |
|------|------|-----------|
| [示例 1](#示例-1自动背景替换) | 自动背景替换 | MASK_MODE_BACKGROUND |
| [示例 2](#示例-2自动前景编辑) | 自动前景编辑 | MASK_MODE_FOREGROUND |
| [示例 3](#示例-3用户提供-mask) | 用户提供 Mask | MASK_MODE_USER_PROVIDED |
| [示例 4](#示例-4语义分割-mask) | 语义分割 Mask | MASK_MODE_SEMANTIC |
| [示例 5](#示例-5组合使用分割和编辑) | 组合使用分割和编辑 | 分割 + 编辑 |

---

## 示例 1：自动背景替换

将图像背景替换为日落海滩场景。

```python
from google import genai
from google.genai import types

# 初始化客户端
client = genai.Client(vertexai=True, project='your-project', location='us-central1')

# 加载原始图像
original_image = types.Image.from_file('portrait.jpg')

# 创建原始图像引用
raw_ref_image = types.RawReferenceImage(
    reference_id=1,
    reference_image=original_image,
)

# 创建背景 mask 引用（自动生成）
mask_ref_image = types.MaskReferenceImage(
    reference_id=2,
    config=types.MaskReferenceConfig(
        mask_mode='MASK_MODE_BACKGROUND',
        mask_dilation=0.06,  # 轻微扩张，避免边缘伪影
    ),
)

# 执行编辑
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Replace the background with a beautiful sunset beach scene',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
        negative_prompt='blurry, distorted, low quality',
        guidance_scale=15.0,
        output_mime_type='image/jpeg',
        output_compression_quality=90,
    ),
)

# 保存结果
if response.generated_images:
    result_image = response.generated_images[0].image
    with open('result_sunset_background.jpg', 'wb') as f:
        f.write(result_image.image_bytes)
    print("背景替换完成！")
```

---

## 示例 2：自动前景编辑

修改图像中的前景对象（如更换衣服颜色）。

```python
# 加载原始图像
original_image = types.Image.from_file('person.jpg')

# 创建原始图像引用
raw_ref_image = types.RawReferenceImage(
    reference_id=1,
    reference_image=original_image,
)

# 创建前景 mask 引用（自动生成）
mask_ref_image = types.MaskReferenceImage(
    reference_id=2,
    config=types.MaskReferenceConfig(
        mask_mode='MASK_MODE_FOREGROUND',
        mask_dilation=0.03,
    ),
)

# 执行编辑 - 更换衣服颜色
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Change the person clothing to a elegant red dress',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=2,  # 生成2个变体
    ),
)

# 保存所有结果
for i, gen_image in enumerate(response.generated_images):
    with open(f'result_red_dress_{i+1}.jpg', 'wb') as f:
        f.write(gen_image.image.image_bytes)
```

---

## 示例 3：用户提供 Mask

使用用户绘制的 mask 进行精确编辑。

```python
# 加载原始图像和用户 mask
original_image = types.Image.from_file('room.jpg')
user_mask = types.Image.from_file('wall_mask.png')  # 用户绘制的墙壁区域

# 创建原始图像引用
raw_ref_image = types.RawReferenceImage(
    reference_id=1,
    reference_image=original_image,
)

# 创建用户提供的 mask 引用
mask_ref_image = types.MaskReferenceImage(
    reference_id=2,
    reference_image=user_mask,  # 用户提供的 mask
    config=types.MaskReferenceConfig(
        mask_mode='MASK_MODE_USER_PROVIDED',
        mask_dilation=0.02,
    ),
)

# 执行编辑 - 更换墙壁颜色
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Paint the masked wall area with a warm coral color',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)

# 保存结果
if response.generated_images:
    result = response.generated_images[0].image
    with open('result_coral_wall.jpg', 'wb') as f:
        f.write(result.image_bytes)
```

### 创建用户 Mask 的方法

```python
from PIL import Image, ImageDraw

# 创建与原图相同尺寸的黑色 mask
original = Image.open('room.jpg')
mask = Image.new('L', original.size, 0)  # 'L' 模式，灰度图

# 绘制白色区域（要编辑的区域）
draw = ImageDraw.Draw(mask)
# 例如：绘制矩形区域
draw.rectangle([100, 50, 400, 300], fill=255)
# 或绘制多边形
draw.polygon([(100, 100), (200, 50), (300, 100), (250, 200), (150, 200)], fill=255)

# 保存 mask
mask.save('wall_mask.png')
```

---

## 示例 4：语义分割 Mask

基于对象类别自动创建 mask。

```python
# 加载原始图像
original_image = types.Image.from_file('street_scene.jpg')

# 创建原始图像引用
raw_ref_image = types.RawReferenceImage(
    reference_id=1,
    reference_image=original_image,
)

# 创建语义分割 mask 引用
# 使用 segmentation_classes 指定要编辑的对象类别
mask_ref_image = types.MaskReferenceImage(
    reference_id=2,
    config=types.MaskReferenceConfig(
        mask_mode='MASK_MODE_SEMANTIC',
        segmentation_classes=[1, 2],  # 假设 1=车辆, 2=人
        mask_dilation=0.05,
    ),
)

# 执行编辑
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Transform all vehicles into futuristic flying cars',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)
```

---

## 示例 5：组合使用分割和编辑

先使用 `segment_image()` 获取精确 mask，再用于编辑。

```python
# 步骤 1：使用分割 API 获取精确的前景 mask
segment_response = client.models.segment_image(
    model='image-segmentation-001',
    source=types.SegmentImageSource(
        image=types.Image.from_file('photo.jpg'),
        prompt='the cat',  # 分割特定对象
    ),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.PROMPT,
        confidence_threshold=0.5,
        mask_dilation=0.02,
        binary_color_threshold=128,
    ),
)

# 获取分割生成的 mask
cat_mask = segment_response.generated_masks[0].mask

# 步骤 2：使用分割结果进行编辑
raw_ref_image = types.RawReferenceImage(
    reference_id=1,
    reference_image=types.Image.from_file('photo.jpg'),
)

mask_ref_image = types.MaskReferenceImage(
    reference_id=2,
    reference_image=cat_mask,  # 使用分割生成的 mask
    config=types.MaskReferenceConfig(
        mask_mode='MASK_MODE_USER_PROVIDED',
    ),
)

# 执行编辑 - 将猫变成老虎
edit_response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Transform the cat into a baby tiger, keeping the same pose',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)

# 保存结果
if edit_response.generated_images:
    result = edit_response.generated_images[0].image
    with open('cat_to_tiger.jpg', 'wb') as f:
        f.write(result.image_bytes)
```

---

## 常见编辑场景

### 场景 1：移除对象

```python
# 使用 INPAINT_REMOVAL 模式移除 mask 区域的内容
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Remove the object and fill with natural background',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_REMOVAL,
        number_of_images=1,
    ),
)
```

### 场景 2：图像扩展（Outpaint）

```python
# 扩展图像边界
response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Extend the image to show more of the landscape',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_OUTPAINT,
        number_of_images=1,
    ),
)
```

### 场景 3：添加新对象

```python
# 在 mask 区域添加新对象
mask_ref_image = types.MaskReferenceImage(
    reference_id=2,
    reference_image=empty_area_mask,  # 标记空白区域
    config=types.MaskReferenceConfig(
        mask_mode='MASK_MODE_USER_PROVIDED',
    ),
)

response = client.models.edit_image(
    model='imagen-3.0-capability-001',
    prompt='Add a beautiful flower vase in the masked area',
    reference_images=[raw_ref_image, mask_ref_image],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)
```

---

## 错误处理

```python
try:
    response = client.models.edit_image(
        model='imagen-3.0-capability-001',
        prompt='Edit the image',
        reference_images=[raw_ref_image, mask_ref_image],
    )

    if response.generated_images:
        # 处理成功结果
        for gen_image in response.generated_images:
            if gen_image.rai_info:
                print(f"RAI Info: {gen_image.rai_info}")
            # 保存图像...
    else:
        print("未生成任何图像")

except Exception as e:
    print(f"编辑失败: {e}")
```

---

## 最佳实践

1. **Mask 扩张**：使用 0.03-0.06 的 mask_dilation 值，避免边缘伪影

2. **负面提示词**：使用 negative_prompt 排除不想要的元素

3. **多次生成**：设置 number_of_images > 1，选择最佳结果

4. **高质量输出**：使用 output_compression_quality=90 以上获得高质量 JPEG

5. **安全过滤**：根据需要设置 safety_filter_level
