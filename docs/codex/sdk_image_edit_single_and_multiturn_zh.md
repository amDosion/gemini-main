# 官方 SDK 图片编辑能力调研：单次编辑 vs 对话式多轮编辑

## 结论速览
- 官方 SDK **有单次编辑**：`client.models.edit_image(...)`（Imagen Edit，Vertex AI 专用）。
- 官方 SDK **有对话式编辑**：使用原生图像输出模型（如 `gemini-2.5-flash-image`）配合 `client.chats.create(...).send_message([prompt, image])`，支持多轮继续编辑。
- 对话式编辑示例明确指出：**推荐使用 chat 模式编辑**，且 **配置项基本不支持（除模态）**。

---

## 一、单次编辑（Imagen edit_image API）

### 入口与签名（同步/异步）
- 同步：`client.models.edit_image(model, prompt, reference_images, config=None)`
- 异步：`await client.aio.models.edit_image(model, prompt, reference_images, config=None)`

这些签名在 SDK 源码里都有完整说明：
- `官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/models.py`

### 官方示例要点
- 模型：示例使用 `imagen-3.0-capability-001`。
- 输入：`prompt` + `reference_images`。
- `reference_images` 支持：
  - `RawReferenceImage`
  - `MaskReferenceImage`
  - `ControlReferenceImage`
  - `StyleReferenceImage`
  - `SubjectReferenceImage`
- 配置：`EditImageConfig`（示例包含 `edit_mode` / `number_of_images` / `include_rai_reason`）。

### 典型用途
- 单次“有明确规则”的编辑（修复/抠图/替换等）。
- 希望通过 `reference_images` + `EditImageConfig` 精细控制编辑行为。

---

## 二、对话式编辑（Chat + 原生图像输出模型）

### 官方推荐方式
SDK `codegen_instructions.md` 明确给出“编辑图片”的 chat 示例，并说明：
- **建议使用 chat 模式编辑**。
- **配置项不支持**（除模态）。

路径：
- `官方SDK/specs/参考/python-genai-main (1)/python-genai-main/codegen_instructions.md`

### 关键流程（单次 + 多轮）
1) 建立 chat：`chat = client.chats.create(model='gemini-2.5-flash-image')`
2) 发送“图片 + 指令”：`response = chat.send_message([prompt, image])`
3) 解析返回部件 `response.candidates[0].content.parts`，可同时得到文本 + 图像。
4) 继续多轮：`chat.send_message('Can you make it a bananas foster?')`

### 多图输出能力
官方示例中明确提到：响应里 **可能包含多张图片**（遍历 `parts` 保存多张）。
这意味着“对话式编辑”模式支持一次产生多张结果。

### 典型用途
- 需要多轮迭代的编辑（逐步修改、补充细节）。
- 不追求复杂 EditImageConfig 细粒度配置，偏交互式创作。

---

## 三、两类方式的对比

| 维度 | 单次编辑（edit_image） | 对话式编辑（chat + image model） |
|---|---|---|
| 输入结构 | `prompt` + `reference_images` + `EditImageConfig` | `send_message([prompt, image])` |
| 多轮能力 | 无（每次独立调用） | 有（同一 chat 可持续编辑） |
| 配置能力 | 强（edit_mode / mask / number_of_images 等） | 弱（示例说明 configs 基本不支持） |
| 输出多图 | 支持（`number_of_images`） | 支持（返回 parts 可包含多图） |
| 推荐场景 | 规则明确、自动化、批量 | 创作式、交互式、多轮迭代 |

---

## 四、如何在你们系统里落地（不改代码的建议）

- 如果需求是“精细控制 + mask/参考图组合”：优先走 `edit_image`（Imagen Edit）。
- 如果需求是“聊天式逐步修改”：对接 chat 模式图像模型（`gemini-2.5-flash-image` / `gemini-3-pro-image-preview`）。
- 如果要统一调度，可考虑在服务层加一个“策略路由”：
  - 有 mask / 强配置 → edit_image
  - 无 mask / 多轮交互 → chat image model

---

## 五、来源清单（本地 SDK 文件）
- `官方SDK/specs/参考/python-genai-main (1)/python-genai-main/google/genai/models.py`
- `官方SDK/specs/参考/python-genai-main (1)/python-genai-main/README.md`
- `官方SDK/specs/参考/python-genai-main (1)/python-genai-main/codegen_instructions.md`
