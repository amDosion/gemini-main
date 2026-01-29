# TryOnService 改造方案（仅基于当前代码与 SDK 类型定义）

## 1) 现状定位
文件：`backend/app/services/gemini/vertexai/tryon_service.py`
- 目标：调用 Vertex AI `recontext_image` 完成 Virtual Try‑On。
- 当前接口：`virtual_tryon(person_image_base64, clothing_image_base64, ...) -> TryOnResult`
- 当前实现特点：
  - 运行时创建 Client（可传入解密凭证，或从 env / client_pool 回退）。
  - 输入仅支持 Base64（`_base64_to_bytes`）。
  - 只返回**第一张**结果图（不支持多图返回）。
  - `config` 覆盖面有限，且未明确哪些参数允许/禁止，易引发稳定性问题。

## 2) 主要问题与风险
1. **输入格式不一致**
   - `GoogleService.virtual_tryon()` 从 `reference_images` 取 `url` 字段，可能是 **HTTP URL / GCS URL / Base64**。当前 `TryOnService` 会强制 Base64 解码，遇到 URL 将直接报错。

2. **返回结构不统一**
   - Vertex AI 其他服务返回 `List[Dict]`（统一格式），TryOnService 返回 `TryOnResult` + 仅一张图。

3. **参数策略不清晰**
   - SDK `RecontextImageConfig` 可选项很多，但当前服务未明确“允许/禁止”的参数集合，容易出现不稳定或不可控的行为。

4. **Vertex AI 客户端创建方式不一致**
   - Vertex AI 其他服务（如 `mask_edit_service`）都使用显式凭证构造的**有状态服务**。
   - TryOnService 在 VertexAI 模块内仍依赖 env/client_pool 回退，行为不可预期。

5. **与现有 Handler/路由存在断层**
   - `handlers/virtual_tryon_handler.py` 仍在调用旧的 `tryon_service.edit_with_mask(...)`（已不存在）。
   - 这会导致模式处理路径和服务接口不一致（潜在运行时错误）。

---

## 3) 改造目标
- **输入适配**：支持 Base64、HTTP URL、GCS URL、文件路径（与 SDK `Image.from_file` 能力一致）。
- **接口统一**：返回与其他 Vertex AI 服务一致的 `List[Dict[str, Any]]` 或统一 `Result` 列表结构。
- **参数收敛（稳定性优先）**：仅允许核心参数；**不透传** `safety_filter_level`、`person_generation`、`add_watermark`。
- **服务一致性**：改造为**有状态服务**（`__init__(project_id, location, credentials_json)` + `_ensure_initialized()`），与 `VertexAIEditBase` 体系一致。
- **校验与约束**：服务内强制校验 Virtual Try‑On 约束（person_image 必填、product_images 仅 1 张、prompt 不允许）。

---

## 4) 推荐改造方案（分阶段）

### 阶段 A：保持调用不变的“兼容增强”
**目标**：不破坏现有调用方，先增强输入/参数处理。
- **输入兼容层**：新增 `_parse_image_input(...)`
  - 支持 `data:image/...`、纯 Base64、HTTP URL、`gs://`、`https://storage.googleapis.com/...`。
  - URL -> 下载为 bytes，再构建 `types.Image(image_bytes=...)`。
  - `gs://` / storage.googleapis.com -> 使用 `Image.from_file`。
- **参数收敛**：明确允许的参数范围，并**忽略**高风险参数
  - **允许**：`number_of_images`、`output_mime_type`、`output_compression_quality`、`base_steps`、`seed`（可选：`output_gcs_uri`、`labels`）  
  - **禁止/忽略**：`safety_filter_level`、`person_generation`、`add_watermark`（必要时记录日志）  
  - 允许 `camelCase` 入参（`numberOfImages`、`outputMimeType` 等）。
- **多图返回**：支持 `number_of_images > 1` 时返回多张结果。
- **错误处理**：保留 TryOnResult 结构，但增加 error code/类型字段（便于调用方判断）。

### 阶段 B：结构统一（推荐）
**目标**：与 Vertex AI 服务体系一致。
- 让 `TryOnService` 接收**显式凭证**：
  - `__init__(project_id, location, credentials_json)`
  - 去除 env/client_pool 回退（或改为显式 `allow_env_fallback=False`）
- 统一返回格式为 List[Dict]：
  - `[{"url": "data:image/...", "mimeType": "image/jpeg", "index": 0, ...}]`
- 统一参数入口为 `edit_image(prompt, reference_images, config)` 的子类模式，或新增 `recontext_tryon(...)` 但输出结构保持一致。
- 将 `virtual_tryon` 视为“只支持 `raw`(person) + `clothing`(product)` 的专用路径”。

---

## 5) 建议的目标接口（示例）
```python
class TryOnService:
    def __init__(self, project_id: str, location: str, credentials_json: str): ...

    def recontext_tryon(
        self,
        person_image: ImageInput,
        product_image: ImageInput,
        config: Optional[Dict[str, Any]] = None,
        model: str = "virtual-try-on-001",
    ) -> List[Dict[str, Any]]:
        ...
```

**ImageInput 支持：**
- `data:image/...;base64,...`
- Base64 字符串
- `gs://` / `https://storage.googleapis.com/...`
- HTTP URL（通过下载转 bytes）
- 文件路径（本地）

---

## 6) 参数映射规范（建议）
| 输入参数 | SDK 字段 | 说明 |
| --- | --- | --- |
| numberOfImages / number_of_images | number_of_images | 1–4 |
| outputMimeType / output_mime_type | output_mime_type | image/jpeg/png |
| outputCompressionQuality / output_compression_quality | output_compression_quality | JPEG 有效 |
| baseSteps / base_steps | base_steps | 采样步数 |
| seed | seed | 随机种子 |
| outputGcsUri / output_gcs_uri | output_gcs_uri | gs://（可选） |
| labels | labels | dict（可选） |

**明确不透传的参数（稳定性原因）：**
- `safety_filter_level`
- `person_generation`
- `add_watermark`

---

## 7) 与现有调用点的对齐建议
### GoogleService.virtual_tryon
- 现有实现从 `reference_images` 解析 `person_url`/`clothing_url`。
- 改造后 TryOnService 可直接接受 URL，避免 Base64 解码失败。
- 建议在 GoogleService 层保持 `{images:[...]}` 返回结构，无需变动 modes.py。

### VirtualTryonHandler（若仍被调用）
- 当前仍在调用 `tryon_service.edit_with_mask(...)`（已失效）。
- 建议更新为调用 `TryOnService.recontext_tryon(...)` 或直接弃用。

---

## 8) 验收清单
- ✅ 兼容 Base64 / HTTP URL / GCS URL / 本地路径输入。
- ✅ `number_of_images` > 1 时可返回多图。
- ✅ **不透传** `safety_filter_level / person_generation / add_watermark`。
- ✅ 当 `output_gcs_uri` 设置时，输出可返回 GCS URL 或 bytes（若启用）。
- ✅ Vertex AI 凭证缺失时给出明确错误提示。

---

## 9) 迁移步骤建议
1. 新增图像输入解析函数（不破坏旧 Base64 入口）。
2. 明确参数允许/禁止列表，过滤高风险参数。
3. 增强返回结构（支持多图 + index + mimeType）。
4. 引入显式凭证构造（按需保留 env fallback）。
5. 更新调用方（GoogleService / Handler）到新接口。

---

## 10) 变更影响范围（仅文档）
- `backend/app/services/gemini/vertexai/tryon_service.py`
- `backend/app/services/gemini/google_service.py`（参数与返回对齐）
- `backend/app/services/gemini/handlers/virtual_tryon_handler.py`（如仍使用）

> 本文档仅为改造方案说明，未修改代码。
