# 官方 SDK 图片 API 示例与用法索引

> 基于 **python-genai-main** 与 **generative-ai-main** 官方 SDK 的示例、测试用例与用法整理  
> 创建日期: 2026-01-24  
> 对应 SDK 路径: `官方SDK/specs/参考/`

---

## 一、SDK 来源与路径

| SDK | 本地路径 | 说明 |
|-----|----------|------|
| **python-genai-main** | `官方SDK/specs/参考/python-genai-main (1)/python-genai-main` | Google 官方 Python SDK 源码、单元测试 |
| **generative-ai-main** | `官方SDK/specs/参考/generative-ai-main/generative-ai-main` | Vertex AI 示例 Notebook、Vision 教程 |

---

## 二、图片 API 与示例文件映射

| API | 功能 | python-genai 测试/源码 | generative-ai Notebook |
|-----|------|------------------------|------------------------|
| `recontext_image` | 虚拟试衣 / 产品重新语境化 | `google/genai/tests/models/test_recontext_image.py` | `vision/getting-started/virtual_try_on.ipynb`<br>`vision/use-cases/batch_virtual_try_on.ipynb`<br>`vision/getting-started/imagen_product_recontext.ipynb` |
| `generate_images` | 图片生成 | `google/genai/tests/models/test_generate_images.py` | `vision/getting-started/imagen4_image_generation.ipynb`<br>`vision/getting-started/imagen3_customization.ipynb`<br>`vision/getting-started/virtual_try_on.ipynb` |
| `edit_image` | 图片编辑 | `google/genai/tests/models/test_edit_image.py` | `vision/getting-started/imagen3_editing.ipynb`<br>`vision/getting-started/imagen3_customization.ipynb` |
| `upscale_image` | 图片放大 | `google/genai/tests/models/test_upscale_image.py` | `vision/getting-started/imagen4_upscale.ipynb` |
| `segment_image` | 图片分割 | `google/genai/tests/models/test_segment_image.py` | `vision/getting-started/image_segmentation.ipynb` |

---

## 三、recontext_image（虚拟试衣 + 产品重新语境化）

### 3.1 官方文件引用

**SDK-A (python-genai-main)**

| 文件路径 | 行号 | 用途 |
|----------|------|------|
| `google/genai/tests/models/test_recontext_image.py` | 24 | `PRODUCT_RECONTEXT_MODEL_LATEST = 'imagen-product-recontext-preview-06-30'` |
| `google/genai/tests/models/test_recontext_image.py` | 26 | `VIRTUAL_TRY_ON_IMAGE_MODEL_LATEST = 'virtual-try-on-001'` |
| `google/genai/tests/models/test_recontext_image.py` | 48–98 | 产品重新语境化用例（单/多产品图、config） |
| `google/genai/tests/models/test_recontext_image.py` | 99–141 | 虚拟试衣用例（基础 / all_config） |
| `google/genai/tests/models/test_recontext_image.py` | 151–188 | 异步 `recontext_image` 调用（产品 + 虚拟试衣） |
| `google/genai/models.py` | 4412–4463 | `recontext_image()` 方法定义与 docstring 示例 |

**SDK-B (generative-ai-main)**

| 文件路径 | 行号/位置 | 用途 |
|----------|------------|------|
| `vision/getting-started/virtual_try_on.ipynb` | Cell 16 | `virtual_try_on = "virtual-try-on-preview-08-04"` |
| `vision/getting-started/virtual_try_on.ipynb` | Cell 27, 29 | 本地文件 Virtual Try-On（`Image.from_file` + `RecontextImageConfig`） |
| `vision/getting-started/virtual_try_on.ipynb` | Cell 32 | Imagen 生成人物 + Try-On 前置 |
| `vision/getting-started/virtual_try_on.ipynb` | Cell 36 | GCS 服装图 + Try-On |
| `vision/use-cases/batch_virtual_try_on.ipynb` | 模型定义 | `virtual_try_on = "virtual-try-on-preview-08-04"` |
| `vision/use-cases/batch_virtual_try_on.ipynb` | recontext 调用 | 批量 Try-On（本地/URL 图 → `Image`/`image_bytes` → `recontext_image`） |
| `vision/getting-started/imagen_product_recontext.ipynb` | 多处 | 产品重新语境化（`RecontextImageSource` + `prompt` + `product_images`） |

### 3.2 最小示例（虚拟试衣）

**来源**: `test_recontext_image.py`（99–115）、`models.py`（4452–4462）、`virtual_try_on.ipynb` Cell 27

```python
from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# 虚拟试衣：人物图 + 单件服装
response = client.models.recontext_image(
    model="virtual-try-on-001",  # 或 "virtual-try-on-preview-08-04"
    source=types.RecontextImageSource(
        person_image=types.Image.from_file(location="person.jpg"),
        product_images=[
            types.ProductImage(product_image=types.Image.from_file(location="garment.jpg"))
        ],
    ),
    config=types.RecontextImageConfig(
        number_of_images=1,
        output_mime_type="image/jpeg",
    ),
)
image = response.generated_images[0].image
# image.image_bytes 或 image.save("try-on.jpeg")
```

### 3.3 最小示例（产品重新语境化）

**来源**: `test_recontext_image.py`（48–65）、`models.py`（4440–4449）

```python
response = client.models.recontext_image(
    model="imagen-product-recontext-preview-06-30",
    source=types.RecontextImageSource(
        prompt="On a school desk",
        product_images=[
            types.ProductImage(product_image=types.Image.from_file(location="product.png")),
            # 可选：同一产品多角度，最多 3 张
        ],
    ),
    config=types.RecontextImageConfig(
        number_of_images=1,
        output_mime_type="image/jpeg",
    ),
)
image = response.generated_images[0].image
```

### 3.4 用法要点

- **虚拟试衣**：`person_image` 必填，`prompt` 禁用；`product_images` 仅支持 **1 张**。
- **产品重新语境化**：`prompt` 可选，`person_image` 禁用；`product_images` 最多 **3 张**（同一产品多角度）。
- **仅 Vertex AI**：`recontext_image` 仅支持 `vertexai=True` 的客户端。
- **generative-ai Notebook**：可选 `safety_filter_level`、`number_of_images`、`add_watermark` 等；基础用法见上两节即可。

---

## 四、generate_images（图片生成）

### 4.1 官方文件引用

**SDK-A (python-genai-main)**

| 文件路径 | 行号 | 用途 |
|----------|------|------|
| `google/genai/tests/models/test_generate_images.py` | 25 | `IMAGEN_MODEL_LATEST = 'imagen-4.0-generate-001'` |
| `google/genai/tests/models/test_generate_images.py` | 27–64 | 简单 prompt、全 Vertex 配置、person_generation、safety_filter_level |

**SDK-B (generative-ai-main)**

| 文件路径 | 行号/位置 | 用途 |
|----------|------------|------|
| `vision/getting-started/imagen4_image_generation.ipynb` | 多处 | Imagen 4 / Fast / Ultra 生成 |
| `vision/getting-started/imagen3_customization.ipynb` | 多处 | 定制化生成、generate + edit 组合 |
| `vision/getting-started/virtual_try_on.ipynb` | Cell 32 | 用 Imagen 生成人物再 Try-On |

### 4.2 最小示例

**来源**: `test_generate_images.py`（27–36）、`imagen4_image_generation.ipynb`

```python
from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

response = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="Red skateboard",
    config=types.GenerateImagesConfig(
        number_of_images=1,
        output_mime_type="image/jpeg",
    ),
)
image = response.generated_images[0].image
```

### 4.3 可选配置（Vertex）

- `image_size`、`aspect_ratio`、`guidance_scale`、`negative_prompt`
- `safety_filter_level`、`person_generation`、`add_watermark`、`seed`
- `enhance_prompt`、`output_compression_quality`、`include_safety_attributes` 等  

参见 `test_generate_images.py` 39–63 行及 `imagen4_image_generation.ipynb`。

---

## 五、edit_image（图片编辑）

### 5.1 官方文件引用

**SDK-A (python-genai-main)**

| 文件路径 | 行号 | 用途 |
|----------|------|------|
| `google/genai/tests/models/test_edit_image.py` | 29 | `CAPABILITY_MODEL_NAME = 'imagen-3.0-capability-001'` |
| `google/genai/tests/models/test_edit_image.py` | 43–106 | `RawReferenceImage`、`MaskReferenceImage`、`EditMode`、mask/user-provided |
| `google/genai/tests/models/test_edit_image.py` | 108–265 | 掩码 inpaint、BGSWAP、style/subject/control 等用例 |

**SDK-B (generative-ai-main)**

| 文件路径 | 行号/位置 | 用途 |
|----------|------------|------|
| `vision/getting-started/imagen3_editing.ipynb` | 多处 | 掩码编辑、背景替换、移除物体、风格化等 |
| `vision/getting-started/imagen3_customization.ipynb` | 多处 | 风格/主体定制、Control 涂鸦 + `edit_image` |

### 5.2 最小示例（掩码 inpainting）

**来源**: `test_edit_image.py`（110–122）、`imagen3_editing.ipynb`

```python
from google.genai import types
from google.genai.types import RawReferenceImage, MaskReferenceImage, MaskReferenceConfig

raw_ref = RawReferenceImage(
    reference_id=1,
    reference_image=types.Image.from_file(location="input.png"),
)
mask_ref = MaskReferenceImage(
    reference_id=2,
    config=MaskReferenceConfig(
        mask_mode="MASK_MODE_BACKGROUND",
        mask_dilation=0.06,
    ),
)

response = client.models.edit_image(
    model="imagen-3.0-capability-001",
    prompt="Sunlight and clear weather",
    reference_images=[raw_ref, mask_ref],
    config=types.EditImageConfig(
        edit_mode=types.EditMode.EDIT_MODE_INPAINT_INSERTION,
        number_of_images=1,
    ),
)
image = response.generated_images[0].image
```

### 5.3 用法要点

- 仅 **Vertex AI**。支持多种 `edit_mode`（如 `EDIT_MODE_INPAINT_INSERTION`、`EDIT_MODE_BGSWAP` 等）。
- `MaskReferenceConfig`：`MASK_MODE_BACKGROUND` / `MASK_MODE_USER_PROVIDED` 等；可选 `reference_image` 提供用户掩码。
- 风格/主体/控制：见 `StyleReferenceImage`、`SubjectReferenceImage`、`ControlReferenceImage` 及 `imagen3_customization.ipynb`。

---

## 六、upscale_image（图片放大）

### 6.1 官方文件引用

**SDK-A (python-genai-main)**

| 文件路径 | 行号 | 用途 |
|----------|------|------|
| `google/genai/tests/models/test_upscale_image.py` | 28 | `IMAGEN_MODEL_LATEST = 'imagen-4.0-upscale-preview'` |
| `google/genai/tests/models/test_upscale_image.py` | 34–72 | 无 config、全 config、GCS 输出 |

**SDK-B (generative-ai-main)**

| 文件路径 | 行号/位置 | 用途 |
|----------|------------|------|
| `vision/getting-started/imagen4_upscale.ipynb` | 多处 | 先 `generate_images` 再 `upscale_image`，本地/GCS 输入 |

### 6.2 最小示例

**来源**: `test_upscale_image.py`（34–41）、`imagen4_upscale.ipynb`

```python
response = client.models.upscale_image(
    model="imagen-4.0-upscale-preview",
    image=types.Image.from_file(location="input.png"),
    upscale_factor="x2",
)
image = response.generated_images[0].image
```

### 6.3 用法要点

- 仅 **Vertex AI**。`upscale_factor`: `x2` / `x3` / `x4`。
- 可选 `UpscaleImageConfig`：`output_mime_type`、`output_compression_quality`、`output_gcs_uri`、`safety_filter_level` 等。

---

## 七、segment_image（图片分割）

### 7.1 官方文件引用

**SDK-A (python-genai-main)**

| 文件路径 | 行号 | 用途 |
|----------|------|------|
| `google/genai/tests/models/test_segment_image.py` | 26 | `SEGMENT_IMAGE_MODEL_LATEST = 'image-segmentation-001'` |
| `google/genai/tests/models/test_segment_image.py` | 47–149 | FOREGROUND、BACKGROUND、PROMPT、SEMANTIC、INTERACTIVE 等 |

**SDK-B (generative-ai-main)**

| 文件路径 | 行号/位置 | 用途 |
|----------|------------|------|
| `vision/getting-started/image_segmentation.ipynb` | 多处 | 各分割模式调用示例 |

### 7.2 最小示例（前景/背景）

**来源**: `test_segment_image.py`（47–63）、（66–76）、`image_segmentation.ipynb`

```python
# 前景
response = client.models.segment_image(
    model="image-segmentation-001",
    source=types.SegmentImageSource(image=types.Image.from_file(location="input.png")),
    config=types.SegmentImageConfig(
        mode=types.SegmentMode.FOREGROUND,
        max_predictions=1,
    ),
)

# 背景
response = client.models.segment_image(
    model="image-segmentation-001",
    source=types.SegmentImageSource(image=types.Image.from_file(location="input.png")),
    config=types.SegmentImageConfig(mode=types.SegmentMode.BACKGROUND),
)
# response.generated_masks
```

### 7.3 用法要点

- 仅 **Vertex AI**。`mode`: `FOREGROUND`、`BACKGROUND`、`PROMPT`、`SEMANTIC`、`INTERACTIVE` 等。
- 可选 `confidence_threshold`、`mask_dilation`、`binary_color_threshold` 等，见 `test_segment_image.py` 及 `image_segmentation.ipynb`。

---

## 八、Vision 目录与快速索引（generative-ai-main）

| Notebook | 路径 | 涉及 API |
|----------|------|----------|
| Virtual Try-On | `vision/getting-started/virtual_try_on.ipynb` | `recontext_image`、`generate_images` |
| Batch Virtual Try-On | `vision/use-cases/batch_virtual_try_on.ipynb` | `recontext_image` |
| Imagen Product Recontext | `vision/getting-started/imagen_product_recontext.ipynb` | `recontext_image` |
| Imagen 4 Image Generation | `vision/getting-started/imagen4_image_generation.ipynb` | `generate_images` |
| Imagen 4 Upscaling | `vision/getting-started/imagen4_upscale.ipynb` | `generate_images`、`upscale_image` |
| Imagen 3 Editing | `vision/getting-started/imagen3_editing.ipynb` | `generate_images`、`edit_image` |
| Imagen 3 Customization | `vision/getting-started/imagen3_customization.ipynb` | `edit_image`、`generate_images` |
| Image Segmentation | `vision/getting-started/image_segmentation.ipynb` | `segment_image` |

更全列表见 `vision/README.md`。

---

## 九、客户端与平台约定

- **Vertex AI**：`genai.Client(vertexai=True, project=..., location=...)`。编辑、放大、分割、虚拟试衣、产品重新语境化 **仅支持 Vertex**。
- **Gemini API**：`genai.Client(api_key=...)`。仅部分接口（如 `generate_images`、`generate_content`）可用。
- 异步：`client.aio.models.<api>(...)`，见 `test_recontext_image.py` 151–188、`test_generate_images` 等。

---

## 十、相关文档

- [OFFICIAL_SDK_IMAGE_API_REFERENCE.md](./OFFICIAL_SDK_IMAGE_API_REFERENCE.md)：模型列表、平台差异、类型定义、迁移说明。
- [IMAGE_SERVICE_RESTRUCTURE_DESIGN.md](./IMAGE_SERVICE_RESTRUCTURE_DESIGN.md)：本服务图像能力架构与重构设计。

---

*文档中的行号与 Cell 索引以当前检视的 SDK 版本为准，若官方库有更新请以仓库内实际内容为准。*
