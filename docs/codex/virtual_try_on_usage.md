# Virtual Try-On 使用文档（Python SDK）

## 1) 前置条件（Vertex AI）
- 仅支持 Vertex AI Client。
- 示例初始化（来自官方 Notebook）：

```python
from google import genai
from google.genai import types

PROJECT_ID = "[your-project-id]"
LOCATION = "us-central1"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
```

---

## 2) 基础调用（本地文件）
```python
virtual_try_on = "virtual-try-on-preview-08-04"

response = client.models.recontext_image(
    model=virtual_try_on,
    source=types.RecontextImageSource(
        person_image=types.Image.from_file(location="person.jpg"),
        product_images=[
            types.ProductImage(product_image=types.Image.from_file(location="shirt.jpg"))
        ],
    ),
    config=types.RecontextImageConfig(
        output_mime_type="image/jpeg",
        number_of_images=1,
        safety_filter_level="BLOCK_LOW_AND_ABOVE",
    ),
)

response.generated_images[0].image.save("try-on.jpeg")
```

---

## 3) 使用 Cloud Storage 图片
```python
response = client.models.recontext_image(
    model=virtual_try_on,
    source=types.RecontextImageSource(
        person_image=types.Image.from_file(location="gs://bucket/person.jpg"),
        product_images=[
            types.ProductImage(product_image=types.Image.from_file(location="gs://bucket/dress.jpg"))
        ],
    ),
)
```

`Image.from_file(...)` 支持：
- 本地路径
- `gs://`
- `https://storage.googleapis.com/...`（会自动转换为 `gs://`）

---

## 4) 使用 HTTP URL（先下载为 bytes）
```python
import requests
from google.genai import types

person_bytes = requests.get(person_url).content
product_bytes = requests.get(product_url).content

response = client.models.recontext_image(
    model=virtual_try_on,
    source=types.RecontextImageSource(
        person_image=types.Image(image_bytes=person_bytes),
        product_images=[
            types.ProductImage(product_image=types.Image(image_bytes=product_bytes))
        ],
    ),
)
```

---

## 5) 批量调用（多人物 × 多商品）
官方批处理示例中使用双层循环与延迟以降低触发配额限制：
```python
for person_img in person_images:
    for product_img in product_images:
        try:
            person_image_obj = types.Image.from_file(location=person_img)
            product_image_obj = types.Image.from_file(location=product_img)

            generated = client.models.recontext_image(
                model=virtual_try_on,
                source=types.RecontextImageSource(
                    person_image=person_image_obj,
                    product_images=[types.ProductImage(product_image=product_image_obj)],
                ),
            )
        except Exception as e:
            print(f"skip: {e}")

        time.sleep(2)
```

---

## 6) 关键限制与建议
- **每次只能传 1 件商品**（product_images 只允许 1 张）。
- **person_image 必填**，`prompt` 不支持。
- Notebook 指出 **每次请求 1–4 张图**（`number_of_images`）。

### 官方示例中的支持服饰类别
- **Tops**: shirts, hoodies, sweaters, tank tops, blouses
- **Bottoms**: pants, leggings, shorts, skirts
- **Footwear**: sneakers, boots, sandals, flats, heels, formal shoes
