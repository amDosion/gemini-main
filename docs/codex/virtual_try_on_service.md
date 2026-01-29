# Virtual Try-On 构建服务文档（基于官方 SDK）

## 1) 服务定位
Virtual Try-On 通过 Vertex AI 的 `recontext_image` 接口生成“人物穿着服饰”的结果图。该能力在官方 SDK 中与“Product Recontext”共享同一接口，但 Virtual Try-On 具有更严格的输入约束。

---

## 2) 依赖与前置条件
- **仅支持 Vertex AI Client**（非 Vertex AI 会报错：`only supported in the Vertex AI client`）。
- 需要可用的 GCP Project/Location。

---

## 3) 请求模型（建议服务入参）
> 服务侧建议将请求归一为以下结构，然后映射到 SDK。 

```json
{
  "model": "virtual-try-on-001",
  "source": {
    "person_image": { "gcs_uri": "gs://..." } | { "image_bytes": "..." },
    "product_images": [
      { "product_image": { "gcs_uri": "gs://..." } | { "image_bytes": "..." } }
    ]
  },
  "config": {
    "number_of_images": 1,
    "base_steps": 32,
    "seed": 1337,
    "safety_filter_level": "BLOCK_MEDIUM_AND_ABOVE",
    "person_generation": "ALLOW_ADULT",
    "add_watermark": false,
    "output_mime_type": "image/jpeg",
    "output_compression_quality": 75,
    "enhance_prompt": false,
    "output_gcs_uri": "gs://...",
    "labels": { "k": "v" }
  }
}
```

---

## 4) 入参约束（Virtual Try-On 专有）
- **person_image 必填**。
- **product_images 必填且只能 1 张**。
- **prompt 不支持**（仅适用于 Product Recontext）。
- 图片可来自：
  - 本地文件（SDK `Image.from_file`）
  - `gs://` 或 `https://storage.googleapis.com/...`
  - HTTP URL（先下载为 bytes，再传 `image_bytes`）

---

## 5) 配置项（可视作“按钮/开关”）
- **number_of_images**：生成图片数量（Notebook 提示 1–4）。
- **base_steps**：采样步数，质量/速度权衡。
- **seed**：随机种子。
- **safety_filter_level**：安全过滤强度（枚举）。
- **person_generation**：人物生成策略（枚举）。
- **add_watermark**：是否添加 SynthID 水印。
- **output_mime_type**：输出格式（如 `image/jpeg` / `image/png`）。
- **output_compression_quality**：JPEG 压缩质量（仅 JPEG 生效）。
- **enhance_prompt**：提示词增强（虽然 VTO 不支持 prompt，但该字段仍在 config 中）。
- **output_gcs_uri**：输出存储到 GCS。
- **labels**：计费/统计标签。
- **http_options**：HTTP 级别选项（SDK 允许）。

**SafetyFilterLevel 枚举值：**
- `BLOCK_LOW_AND_ABOVE`
- `BLOCK_MEDIUM_AND_ABOVE`
- `BLOCK_ONLY_HIGH`
- `BLOCK_NONE`

**PersonGeneration 枚举值：**
- `DONT_ALLOW`
- `ALLOW_ADULT`
- `ALLOW_ALL`

---

## 6) 返回结构
```json
{
  "generated_images": [
    {
      "image": { "image_bytes": "..." } | { "gcs_uri": "..." },
      "rai_filtered_reason": "...",
      "safety_attributes": { "categories": [...], "scores": [...] },
      "enhanced_prompt": "..."
    }
  ]
}
```

---

## 7) 功能说明（官方用例摘要）
- 输入人物图片 + 服饰图片，生成“试穿图”。
- 支持本地文件、GCS 文件、HTTP URL（需先下载）。
- 官方 Notebook 给出的服饰类别：
  - Tops: shirts, hoodies, sweaters, tank tops, blouses
  - Bottoms: pants, leggings, shorts, skirts
  - Footwear: sneakers, boots, sandals, flats, heels, formal shoes

---

## 8) 常见错误与处理建议
- **非 Vertex AI Client 调用** → 抛出 `ValueError`（SDK 侧限制）。
- **缺少 person_image 或 product_images** → 请求无效，应在服务层先校验。
- **product_images > 1** → 不符合 Virtual Try-On 约束，应直接拦截。
