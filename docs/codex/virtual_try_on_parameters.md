# Virtual Try-On 参数文档（基于官方 SDK 示例与类型定义）

## 范围与来源
- Python SDK 类型与接口定义：`官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/types.py`
- Python SDK 方法文档：`官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/models.py`、`docs/genai.html`
- 示例 Notebook：`官方SDK/specs/参考/generative-ai-main/generative-ai-main/vision/getting-started/virtual_try_on.ipynb`
- 测试用例：`官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/tests/models/test_recontext_image.py`

> Virtual Try-On 通过 `client.models.recontext_image(...)` 调用，仅支持 Vertex AI Client。

---

## 1) 入口方法（Vertex AI）
```
client.models.recontext_image(
    model: str,
    source: RecontextImageSource,
    config: RecontextImageConfig | None = None,
) -> RecontextImageResponse
```
- **model**：模型 ID（见下文）。
- **source**：输入源（人员图 + 商品图）。
- **config**：可选配置（数量、安全、种子等）。

### 常见模型 ID（来自官方示例/测试）
- `virtual-try-on-001`（测试/文档使用的最新 ID）
- `virtual-try-on-preview-08-04`（官方 Notebook 示例）

---

## 2) source：RecontextImageSource
**字段**（来自 `types.py` / `models.py`）：
- **prompt**: `str | None`
  - 产品重上下文可用；**Virtual Try-On 不支持**。
- **person_image**: `Image | None`
  - **Virtual Try-On 必填**。
- **product_images**: `list[ProductImage] | None`
  - **Virtual Try-On 必填**。
  - Virtual Try-On **只支持 1 张商品图**。

### ProductImage
- **product_image**: `Image`
  - 商品图片（衣物/鞋类等）。

### Image
- **gcs_uri**: `gs://...` 或 `https://storage.googleapis.com/...`
- **image_bytes**: `bytes`
- **mime_type**: 可选
- `Image.from_file(location=...)`：支持本地路径或 GCS 路径；`https://storage.googleapis.com/...` 会自动转换为 `gs://...`。
- `gcs_uri` 和 `image_bytes` 二选一。

---

## 3) config：RecontextImageConfig
> 以下字段在 Virtual Try-On 中可用（来自类型定义与测试用例）。

- **http_options**: `HttpOptions | None`
  - 覆盖 HTTP 请求选项。
- **number_of_images**: `int | None`
  - 生成图片数量（Notebook 提示 1–4）。
- **base_steps**: `int | None`
  - 采样步数（高质量 vs 低延迟权衡）。
- **output_gcs_uri**: `str | None`
  - 输出图片存储到 GCS 的路径。
- **seed**: `int | None`
  - 随机种子。
- **safety_filter_level**: `SafetyFilterLevel | str | None`
  - 安全过滤等级。
- **person_generation**: `PersonGeneration | str | None`
  - 是否允许生成包含人物的图像。
- **add_watermark**: `bool | None`
  - 是否添加 SynthID 水印。
- **output_mime_type**: `str | None`
  - 输出格式（如 `image/jpeg`、`image/png`）。
- **output_compression_quality**: `int | None`
  - 仅当 `output_mime_type = image/jpeg` 时有效。
- **enhance_prompt**: `bool | None`
  - 是否启用提示词增强。
- **labels**: `dict[str, str] | None`
  - 计费/跟踪标签。

### SafetyFilterLevel 枚举值
- `BLOCK_LOW_AND_ABOVE`
- `BLOCK_MEDIUM_AND_ABOVE`
- `BLOCK_ONLY_HIGH`
- `BLOCK_NONE`

### PersonGeneration 枚举值
- `DONT_ALLOW`
- `ALLOW_ADULT`
- `ALLOW_ALL`

---

## 4) 响应结构（RecontextImageResponse）
- **generated_images**: `list[GeneratedImage]`

### GeneratedImage
- **image**: `Image`（输出图片）
- **rai_filtered_reason**: `str | None`
- **safety_attributes**: `SafetyAttributes | None`
- **enhanced_prompt**: `str | None`

---

## 5) Virtual Try-On 关键约束（官方说明）
- **必须提供** `person_image` + `product_images`。
- **不支持** `prompt`。
- **仅支持 1 张**商品图（product_images 只允许 1 项）。
- 仅支持 Vertex AI Client（非 Vertex AI 会报错）。
