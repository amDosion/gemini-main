# Virtual Try-On SDK 使用文档（Python Gen AI SDK）

本文档说明如何使用 Google Gen AI Python SDK 调用 Virtual Try-On 模型。
内容基于 SDK 实现与官方示例笔记本。

## 官方来源位置（本地仓库路径）

以下为本项目内的官方来源文件，便于核对：

- SDK 方法与注释：`官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/models.py`
- 类型定义：`官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/types.py`
- SDK 测试用例：`官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/tests/models/test_recontext_image.py`
- 示例（入门）：`官方SDK/specs/参考/generative-ai-main/generative-ai-main/vision/getting-started/virtual_try_on.ipynb`
- 示例（批处理）：`官方SDK/specs/参考/generative-ai-main/generative-ai-main/vision/use-cases/batch_virtual_try_on.ipynb`

## 官方文档入口（在线）

以下链接来自官方示例笔记本的说明段落：

- Virtual Try-On 产品文档：`https://cloud.google.com/vertex-ai/generative-ai/docs/image/generate-virtual-try-on-images`
- Virtual Try-On 模型与配额说明：`https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/virtual-try-on-preview-08-04`
- Imagen 模型计费与价格：`https://cloud.google.com/vertex-ai/generative-ai/pricing#imagen-models`

## 范围

- SDK: `google-genai`（Python）
- API: `client.models.recontext_image`
- 场景: Virtual Try-On（VTO）

## 前置条件

- 必须使用 Vertex AI 客户端。SDK 会对 `recontext_image` 强制校验。
- 创建客户端时提供 `project` 与 `location`。
- 环境需完成认证（Colab 示例使用 `google.colab.auth.authenticate_user()`）。

## 模型名称

仓库中出现的 VTO 模型 ID：

- `virtual-try-on-001`（SDK 测试用）
- `virtual-try-on-preview-08-04`（示例笔记本）

请根据环境实际可用模型选择。

## API 形式

```
client.models.recontext_image(
    model=...,
    source=RecontextImageSource(...),
    config=RecontextImageConfig(...),
)
```

返回类型为 `RecontextImageResponse`，生成结果在 `generated_images`。

## 输入参数（RecontextImageSource）

Virtual Try-On 要求：

- `person_image` 必填。
- `product_images` 必填。
- VTO 仅支持 1 张产品图。
- `prompt` 在 VTO 中不支持。

图片支持的来源：

- `Image.from_file(location="path/to/image")`
- `Image(image_bytes=bytes)`
- `Image(gcs_uri="gs://bucket/path")`

产品图需包装为 `ProductImage(product_image=Image(...))`。

## 配置参数（RecontextImageConfig）

SDK 暴露的可配项如下：

- `number_of_images`（int）。示例中 VTO 为 1 到 4。
- `base_steps`（int）。数值越高质量越好、延迟越高。
- `seed`（int）。随机种子。
- `output_mime_type`（str）。例如 `image/jpeg`。
- `output_compression_quality`（int）。仅对 `image/jpeg` 生效。
- `enhance_prompt`（bool）。提示词重写（VTO 不支持 `prompt`）。
- `labels`（dict[str, str]）。计费标签。
- `http_options`（HttpOptions）。覆盖 HTTP 请求选项。

## 生产环境禁用参数

以下参数在生产环境中禁止使用（即使 SDK 支持也不要传入）：

- `output_gcs_uri`
- `safety_filter_level`
- `person_generation`
- `add_watermark`

说明：此限制不影响输入图片使用 `Image(gcs_uri=...)`。

## 质量优先的完整配置（生产可用）

```python
from google.genai.types import RecontextImageConfig, HttpOptions, HttpRetryOptions

config = RecontextImageConfig(
    number_of_images=1,
    base_steps=32,
    seed=123456,
    output_mime_type="image/jpeg",
    output_compression_quality=100,
    enhance_prompt=False,
    labels={"scene": "virtual_try_on", "env": "prod"},
    http_options=HttpOptions(
        timeout=120000,
        retry_options=HttpRetryOptions(
            attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            exp_base=2.0,
            jitter=1.0,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    ),
)
```

说明：

- `output_compression_quality=100` 为最高质量，但文件体积更大。
- `seed` 仅用于固定结果，可根据需求移除以增加随机性。

## 完整示例（本地文件）

```python
from google import genai
from google.genai.types import (
    Image,
    ProductImage,
    RecontextImageConfig,
    RecontextImageSource,
    HttpOptions,
    HttpRetryOptions,
)

client = genai.Client(vertexai=True, project="your-project-id", location="us-central1")

config = RecontextImageConfig(
    number_of_images=1,
    base_steps=32,
    seed=123456,
    output_mime_type="image/jpeg",
    output_compression_quality=100,
    enhance_prompt=False,
    labels={"scene": "virtual_try_on", "env": "prod"},
    http_options=HttpOptions(
        timeout=120000,
        retry_options=HttpRetryOptions(
            attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            exp_base=2.0,
            jitter=1.0,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    ),
)

response = client.models.recontext_image(
    model="virtual-try-on-preview-08-04",
    source=RecontextImageSource(
        person_image=Image.from_file(location="person.jpg"),
        product_images=[
            ProductImage(product_image=Image.from_file(location="pants.jpg"))
        ],
    ),
    config=config,
)
```

## GCS 或 URL 字节示例

以下示例继续复用上文的 `config`。

```python
import requests
from google.genai.types import Image, ProductImage, RecontextImageSource

# GCS 图片
person_image = Image(gcs_uri="gs://your-bucket/person.jpg")

# URL 图片字节
resp = requests.get("https://example.com/shirt.jpg")
resp.raise_for_status()
product_image = Image(image_bytes=resp.content)

response = client.models.recontext_image(
    model="virtual-try-on-preview-08-04",
    source=RecontextImageSource(
        person_image=person_image,
        product_images=[ProductImage(product_image=product_image)],
    ),
    config=config,
)
```

## 批处理模式

VTO 每次仅支持 1 件服饰，因此多件或多人需要多次请求。
以下示例继续复用上文的 `config`。

```python
results = []
for person_img in person_images:
    for product_img in product_images:
        response = client.models.recontext_image(
            model="virtual-try-on-preview-08-04",
            source=RecontextImageSource(
                person_image=person_img,
                product_images=[ProductImage(product_image=product_img)],
            ),
            config=config,
        )
        results.append(response.generated_images[0].image)
```

## 常见限制

- 仅支持 `vertexai=True` 的客户端。
- `prompt` 在 VTO 中不支持。
- 每次只允许 1 张产品图。
