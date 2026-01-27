# Virtual Try-On SDK Usage (Python Gen AI SDK)

This document explains how to call the Virtual Try-On model using the
Google Gen AI Python SDK. It is based on the SDK implementation and the
official sample notebooks in this repo.

## Scope

- SDK: `google-genai` (Python)
- API: `client.models.recontext_image`
- Use case: Virtual Try-On (VTO)

## Requirements

- Use the Vertex AI client. The SDK enforces this for `recontext_image`.
- Provide `project` and `location` when creating the client.
- Ensure your environment is authenticated (Colab uses
  `google.colab.auth.authenticate_user()` in the samples).

## Model Names

The repo shows two model IDs for VTO:

- `virtual-try-on-001` (SDK tests)
- `virtual-try-on-preview-08-04` (sample notebooks)

Pick the model that is available in your environment.

## API Shape

```
client.models.recontext_image(
    model=...,
    source=RecontextImageSource(...),
    config=RecontextImageConfig(...),
)
```

The response is `RecontextImageResponse` with `generated_images`.

## Source Parameters (RecontextImageSource)

For Virtual Try-On:

- `person_image` is required.
- `product_images` is required.
- Only one product image is supported for VTO.
- `prompt` is not supported for VTO.

Images can be provided as:

- `Image.from_file(location="path/to/image")`
- `Image(image_bytes=bytes)`
- `Image(gcs_uri="gs://bucket/path")`

Product images must be wrapped as `ProductImage(product_image=Image(...))`.

## Config Parameters (RecontextImageConfig)

These settings are available in the SDK:

- `number_of_images` (int). Samples mention 1 to 4 for VTO.
- `base_steps` (int). Higher = better quality, lower = faster.
- `seed` (int). Random seed.
- `output_gcs_uri` (str). Save output images to GCS.
- `safety_filter_level` (enum).
  - `BLOCK_LOW_AND_ABOVE`
  - `BLOCK_MEDIUM_AND_ABOVE`
  - `BLOCK_ONLY_HIGH`
  - `BLOCK_NONE`
- `person_generation` (enum).
  - `DONT_ALLOW`
  - `ALLOW_ADULT`
  - `ALLOW_ALL`
- `add_watermark` (bool). Adds SynthID watermark.
- `output_mime_type` (str). Example: `image/jpeg`.
- `output_compression_quality` (int). For `image/jpeg` only.
- `enhance_prompt` (bool). Prompt rewriting. VTO does not accept `prompt`.
- `labels` (dict[str, str]). Billing labels.
- `http_options` (HttpOptions). Override HTTP request options.

## Minimal Example (Local Files)

```python
from google import genai
from google.genai.types import Image, ProductImage, RecontextImageSource

PROJECT_ID = "your-project-id"
LOCATION = "us-central1"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

response = client.models.recontext_image(
    model="virtual-try-on-preview-08-04",
    source=RecontextImageSource(
        person_image=Image.from_file(location="person.jpg"),
        product_images=[
            ProductImage(product_image=Image.from_file(location="shirt.jpg"))
        ],
    ),
)

response.generated_images[0].image.save("try-on.jpg")
```

## Example With Config

```python
from google import genai
from google.genai.types import (
    Image,
    ProductImage,
    RecontextImageConfig,
    RecontextImageSource,
)

client = genai.Client(vertexai=True, project="your-project-id", location="us-central1")

response = client.models.recontext_image(
    model="virtual-try-on-preview-08-04",
    source=RecontextImageSource(
        person_image=Image.from_file(location="person.jpg"),
        product_images=[
            ProductImage(product_image=Image.from_file(location="pants.jpg"))
        ],
    ),
    config=RecontextImageConfig(
        output_mime_type="image/jpeg",
        number_of_images=1,
        safety_filter_level="BLOCK_LOW_AND_ABOVE",
    ),
)
```

## Example With GCS or URL Bytes

```python
import requests
from google.genai.types import Image, ProductImage, RecontextImageSource

# GCS image
person_image = Image(gcs_uri="gs://your-bucket/person.jpg")

# URL image bytes
resp = requests.get("https://example.com/shirt.jpg")
resp.raise_for_status()
product_image = Image(image_bytes=resp.content)

response = client.models.recontext_image(
    model="virtual-try-on-preview-08-04",
    source=RecontextImageSource(
        person_image=person_image,
        product_images=[ProductImage(product_image=product_image)],
    ),
)
```

## Batch Processing Pattern

Virtual Try-On only supports one clothing item per request. For multiple
items or multiple people, run multiple requests.

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
        )
        results.append(response.generated_images[0].image)
```

## Common Constraints

- VTO is only supported with `vertexai=True`.
- `prompt` is not supported for VTO.
- Only one product image per call.
