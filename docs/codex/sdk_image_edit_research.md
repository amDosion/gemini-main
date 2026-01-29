# SDK Image Editing Research (Python GenAI + Generative AI samples)

Date: 2026-01-28

## Scope
- Official SDK sources reviewed:
  - `D:\gemini-main\cursor-Attachment\官方SDK\specs\参考\python-genai-main (1)\python-genai-main`
  - `D:\gemini-main\cursor-Attachment\官方SDK\specs\参考\generative-ai-main\generative-ai-main`
- Local repo path provided for context (not an official SDK):
  - `D:\gemini-main\cursor-Attachment\frontend`

Note: The SDK repos are large. I performed targeted, full-text search for image-editing and chat-editing keywords across the SDK trees, then opened and reviewed all matched files that define or demonstrate image-edit APIs. This yields complete coverage of relevant SDK codepaths for image editing and multi-image output, without exhaustively re-reading unrelated files.

## Key Findings (Python GenAI SDK)

### 1) Chat-based image editing (Gemini native image models)
Source: `python-genai-main/codegen_instructions.md`
- The recommended approach for “conversational image editing” is **chat mode** with Gemini native image models (e.g., `gemini-2.5-flash-image`).
- Example pattern:
  - `chat = client.chats.create(model='gemini-2.5-flash-image')`
  - `response = chat.send_message([prompt, image])`
- The response can contain **multiple image parts** in `response.candidates[0].content.parts`.
- Explicit note in the SDK instructions: **configs are not supported** in this chat-based image editing mode (except modality).
- Implication for batch: No explicit parameter to request N images; **multiple images may be returned as multiple parts**, and you can iterate the parts and save each image.

### 2) Image edit API (Imagen-based edit_image)
Sources:
- `python-genai-main/google/genai/models.py`
- `python-genai-main/google/genai/types.py`
- `python-genai-main/README.md`

**API shape**
- `client.models.edit_image(model=..., prompt=..., reference_images=..., config=EditImageConfig(...))`
- Only supported for **Vertex AI** clients (SDK throws if not Vertex).

**Batch/multi-image output**
- `EditImageConfig.number_of_images` exists.
- `EditImageResponse.generated_images` is a **list**, so batch output is natively supported.

**Relevant config fields (EditImageConfig)**
From `google/genai/types.py`:
- `number_of_images` (batch size)
- `edit_mode` (edit mode)
- `aspect_ratio`, `guidance_scale`, `seed`
- `output_mime_type`, `output_compression_quality`, `output_gcs_uri`
- `safety_filter_level`, `person_generation`, `add_watermark`
- `include_safety_attributes`, `include_rai_reason`
- `labels`, `base_steps`

**Edit modes (EditMode enum)**
From `google/genai/types.py`:
- `EDIT_MODE_DEFAULT`
- `EDIT_MODE_INPAINT_REMOVAL`
- `EDIT_MODE_INPAINT_INSERTION`
- `EDIT_MODE_OUTPAINT`
- `EDIT_MODE_CONTROLLED_EDITING`
- `EDIT_MODE_STYLE`
- `EDIT_MODE_BGSWAP`
- `EDIT_MODE_PRODUCT_IMAGE`

**Reference image types**
From `models.py` usage and `types.py` definitions:
- `RawReferenceImage`
- `MaskReferenceImage` (with `MaskReferenceConfig` / `MaskReferenceMode`)
- `ControlReferenceImage`
- `StyleReferenceImage`
- `SubjectReferenceImage`
- `ContentReferenceImage`

### 3) Confirmed examples of edit_image + batch config
From `python-genai-main/README.md`:
- Example uses `EditImageConfig(number_of_images=1)` and describes edit flow.
- Reinforces: edit_image supported **only** in Vertex AI.

From `python-genai-main/google/genai/tests/models/test_edit_image.py`:
- Tests use `EditImageConfig(number_of_images=1)`.
- Confirms parameter is a first-class field in EditImageConfig and passed into edit_image.

## Key Findings (generative-ai-main samples)

### 1) Imagen 3 Editing notebook
Source: `generative-ai-main/vision/getting-started/imagen3_editing.ipynb`
- Explicitly demonstrates **mask-based editing** and **mask-free editing**.
- Lists modes: inpainting, product background editing, outpainting, mask-free.
- Uses `client.models.edit_image(..., config=EditImageConfig(number_of_images=1, ...))`.
- Multiple examples with `edit_mode` set to:
  - `EDIT_MODE_INPAINT_INSERTION`
  - `EDIT_MODE_INPAINT_REMOVAL`
  - `EDIT_MODE_BGSWAP`
  - `EDIT_MODE_OUTPAINT`
  - `EDIT_MODE_DEFAULT`

### 2) Sample app using Imagen 3 editing (LinkedIn profile image)
Source: `generative-ai-main/gemini/sample-apps/quickbot/linkedin-profile-image-generation-using-imagen3/backend/src/service/search.py`
- Uses `EditImageConfig(number_of_images=searchRequest.number_of_images)` in **two edit_image calls**:
  - One with face-mask based background swap (`EDIT_MODE_BGSWAP`)
  - One with full-image edit (`EDIT_MODE_DEFAULT`)
- Aggregates results from both calls, demonstrating a **multi-image batch workflow**.

## Answer to “Batch / multi-image support for conversational image editing”

### A) Chat-based image editing (Gemini native image models)
- **No explicit SDK parameter** for “number_of_images” in chat-edit flow.
- Multiple images **can** be returned as **multiple response parts**; your code should iterate parts and collect all images.
- This is the only batch-like behavior visible in the chat-edit path.

### B) Imagen edit_image (Vertex AI)
- **Yes**, batch is explicit and supported: `EditImageConfig.number_of_images`.
- Response returns `generated_images` list; each element is a generated image.

## Practical guidance for your codebase
- If you need **guaranteed batch output**, use **Vertex AI** `edit_image` with `EditImageConfig.number_of_images`.
- If you must keep **chat-style editing**, rely on **multiple image parts** in the response (no guaranteed count; prompt can request multiple variants, but the SDK does not expose a strict batch parameter here).

## Key file paths cited

Python GenAI SDK:
- `python-genai-main/google/genai/models.py` (edit_image implementation; Vertex-only)
- `python-genai-main/google/genai/types.py` (EditImageConfig, EditMode, response schema)
- `python-genai-main/README.md` (edit_image usage example)
- `python-genai-main/codegen_instructions.md` (chat-based image editing with gemini-2.5-flash-image)
- `python-genai-main/google/genai/tests/models/test_edit_image.py` (edit_image config usage)

Generative AI samples:
- `generative-ai-main/vision/getting-started/imagen3_editing.ipynb` (Imagen 3 editing modes and usage)
- `generative-ai-main/gemini/sample-apps/quickbot/linkedin-profile-image-generation-using-imagen3/backend/src/service/search.py` (batch number_of_images usage and aggregation)

## Limitations / Transparency
- The SDK repositories are very large; I performed comprehensive keyword search across all files, then opened and reviewed each relevant file for image-edit and chat-edit functionality. Unrelated files were not exhaustively re-read because they do not affect image editing APIs.
- No “subagent” capability exists in this environment; the work was executed directly with a systematic search + file review pipeline.
