# 虚拟试衣独立服务设计方案

> 前端 `virtual-try-on` 为独立模式，后端虚拟试衣为独立服务（TryOnService + recontext_image API）。  
> 本文档约定前后端契约、数据流与重构方案。  
> 创建日期: 2026-01-24

---

## 一、目标与原则

### 1.1 目标

1. **后端**：虚拟试衣作为**独立服务**，仅依赖 `TryOnService.virtual_tryon(person_image, clothing_image)` 与 `recontext_image` API，不依赖 prompt、掩码或通用 chat 流程。
2. **前端**：`VirtualTryOnView` 作为**独立模式**，直接适配该服务，采用「人物图 + 服装图」双槽位，调用专用 API，而非通过通用 modes 的 prompt + 多用途 attachments 流转。
3. **契约清晰**：请求/响应格式明确，便于前后端独立演进与联调。

### 1.2 原则

- **单一职责**：虚拟试衣 = 人物图 + 服装图 → 试衣结果图。
- **显式输入**：人物、服装分别占位，避免单图 + prompt 的歧义。
- **最小依赖**：不依赖 mask 预览、tryOnTarget（upper/lower）等与 recontext API 无关的复杂能力；可选能力（如 number_of_images、upscale）单独约定。

---

## 二、后端现状与能力

### 2.1 TryOnService（`vertexai/tryon_service.py`）

- **核心 API**：`virtual_tryon(person_image_base64, clothing_image_base64, number_of_images=1, output_mime_type="image/jpeg", model="virtual-try-on-001")`
- **能力**：调用 `client.models.recontext_image(...)`，Vertex AI only；仅支持 **1 张服装图**。
- **结论**：以 `virtual_tryon(person, clothing)` 为唯一主路径（`legacy_virtual_tryon` 方法不存在）。

### 2.2 通用 Modes 流程（`routers/core/modes.py`）

- **路由**：`POST /api/modes/{provider}/virtual-try-on`
- **入参**：`ModeRequest`：`modelId`、`prompt`、`attachments`、`options`、`extra`。
- **附件转换**：`convert_attachments_to_reference_images` → 非 mask 图依次填入 `raw`，第二张起变成 `raw: [img1, img2]`；**无** `person` / `clothing` 区分。
- **服务调用**：`GoogleService.virtual_tryon(prompt, model, reference_images, **options)`。  
  - 当前实现调用 `tryon_service.virtual_tryon(prompt=..., reference_images=...)`，与 `TryOnService.virtual_tryon(person, clothing)` 签名不符；应改为直接调用 `virtual_tryon`，且 `reference_images` 需提供 `raw` + `clothing`。

### 2.3 小结：后端需统一的部分

1. **Virtual Try-On 专用契约**：明确 `raw` = 人物图，`clothing` = 服装图；`convert_attachments_to_reference_images` 在 `virtual-try-on` 模式下按 **顺序** 或 **role** 映射为 `raw` / `clothing`。
2. **GoogleService**：`virtual_tryon` 应委托 `TryOnService.virtual_tryon`，并只使用 `raw` + `clothing` 路径（即 recontext）；若缺 `clothing`，直接报错，不走 mask 回退（或单独配置）。
3. 虚拟试衣通过统一 modes 路由 `POST /api/modes/google/virtual-try-on` 调用，无独立 tryon 路由。

---

## 三、前端现状与问题

### 3.1 VirtualTryOnView（`components/views/VirtualTryOnView.tsx`）

- **输入**：`onSend(text, options, attachments, mode)`；`text` 为 prompt（服装描述），`attachments` 多来自 **单图** continuity（`activeImageUrl` → 复用为 1 个 attachment）。
- **Controls**：`VirtualTryOnControls` 提供 `tryOnTarget`（upper/lower）；`enableUpscale`、`upscaleFactor`、`addWatermark` 等。
- **Handler**：`VirtualTryOnHandler` 要求 **2 个 attachments**（person + garment），调 `llmService.virtualTryOn(prompt, attachments)` → `UnifiedProviderClient.executeMode('virtual-try-on', ...)` → `POST /api/modes/google/virtual-try-on`。
- **问题**：  
  1. 实际常只传 **1 张图**（continuity 复用），与 「person + garment」 不符。  
  2. **Prompt** 在 recontext 中不使用，易造成误解。  
  3. 人物/服装**未显式区分**，依赖顺序或隐式约定，易错。  
  4. 掩码预览、tryOnTarget 等与 recontext 无关，增加复杂度。

### 3.2 数据流简述

```
VirtualTryOnView (handleSend)
  → onSend(text, options, attachments, 'virtual-try-on')
  → useChat / StrategyRegistry → VirtualTryOnHandler
  → llmService.virtualTryOn(text, attachments)
  → UnifiedProviderClient.executeMode('virtual-try-on', modelId, prompt, attachments, options, {})
  → POST /api/modes/google/virtual-try-on
  → modes 路由 → convert_attachments_to_reference_images → reference_images (raw / raw[])
  → GoogleService.virtual_tryon(prompt, model, reference_images, **options)
  → TryOnService（当前签名不匹配）
```

---

## 四、目标架构与契约

### 4.1 后端：虚拟试衣专用 API（推荐）

**路由**：`POST /api/modes/google/virtual-try-on`（通过统一 modes 路由）。

**请求体**（JSON）：

```json
{
  "personImage": "data:image/jpeg;base64,...",
  "clothingImage": "data:image/jpeg;base64,...",
  "numberOfImages": 1,
  "outputMimeType": "image/jpeg",
  "model": "virtual-try-on-001"
}
```

- `personImage`、`clothingImage`：必填；Base64 Data URL 或纯 Base64 字符串均可，后端统一 strip `data:*;base64,` 后使用。
- `numberOfImages`：可选，默认 1；1–4。
- `outputMimeType`：可选，默认 `image/jpeg`。
- `model`：可选，默认 `virtual-try-on-001`。

**响应体**（JSON）：

```json
{
  "success": true,
  "data": {
    "image": "data:image/jpeg;base64,...",
    "mimeType": "image/jpeg"
  }
}
```

或失败：

```json
{
  "success": false,
  "error": "错误信息"
}
```

- 后端直接调 `TryOnService.virtual_tryon(person_image_base64, clothing_image_base64, number_of_images, output_mime_type, model)`，返回 `TryOnResult` 对应字段。

### 4.2 替代方案：沿用 Modes 路由

若暂不新增 `/api/tryon/virtual`，则继续使用 `POST /api/modes/google/virtual-try-on`，但契约收紧：

- **Attachments**：**仅 2 个**；顺序约定 `[0]` = 人物，`[1]` = 服装。  
  - 前端上传时需明确 **person** / **garment** 角色（例如 `attachment.role` 或固定顺序）。
- **convert_attachments_to_reference_images**：在 `virtual-try-on` 模式下，  
  - `attachments[0]` → `raw`，  
  - `attachments[1]` → `clothing`；  
  不再使用 `raw: [img1, img2]`。
- **Prompt**：**不参与** recontext 调用；可保留键名用于审计，但不传 `TryOnService`。
- **GoogleService.virtual_tryon**：  
  - 从 `reference_images` 取 `raw`、`clothing`；  
  - 调用 `TryOnService.virtual_tryon(person, clothing)`；
  - 缺 `clothing` 时直接 400。

### 4.3 前端：独立双槽位 UI

**布局**：

- **人物图槽位**：占位图 + 上传/粘贴/拖拽；支持预览、清除、替换。
- **服装图槽位**：同上。
- **操作**：「开始试衣」主按钮；可选「生成数量」等（若后端支持）。

**交互**：

1. 用户分别在两槽位上传 **人物图**、**服装图**。
2. 二者齐备后「开始试衣」可点；否则禁用并提示。
3. 点击后：
   - 使用 **Modes**：
     `POST /api/modes/google/virtual-try-on`，`attachments`: `[personAttachment, garmentAttachment]`，顺序固定；可不传或传空 `prompt`。
4. 成功后展示结果图；可保留历史列表、对比、下载等（与现有 View 能力兼容）。

**移除或弱化**：

- **掩码预览**：与 recontext 无关，移除或仅作占位。
- **tryOnTarget（upper/lower）**：不作为 API 参数；若保留仅作前端标签/说明。
- **Prompt 输入**：不作为试衣 API 入参；可保留为可选「备注」仅存于前端或会话。

**可选**：

- **Upscale**：若后端支持试衣后 upscale，可单独增加「放大」步骤（先试衣，再调 upscale API），与试衣主流程解耦。

---

## 五、实施步骤

### 5.1 后端

1. **Modes 路径调整**
   - `convert_attachments_to_reference_images`：在 `mode === 'virtual-try-on'` 时，按顺序映射 `attachments[0]` → `raw`，`attachments[1]` → `clothing`。  
   - `GoogleService.virtual_tryon`：仅使用 `raw` + `clothing`，调用 `TryOnService.virtual_tryon`，并统一返回格式。
3. **文档**：在 `docs` 或 API 说明中写明虚拟试衣的请求/响应契约及错误码。

### 5.2 前端

1. **VirtualTryOnView 重构**  
   - 改为 **双槽位**：人物图、服装图独立 state，独立上传/清除。  
   - 移除对单图 continuity 复用为「试衣输入」的逻辑；history 仅用于展示历史结果。  
   - 「开始试衣」仅在两张图皆备时可用；点击后根据配置调用 **专用 API** 或 **Modes**。
2. **调用层**  
   - 若使用专用 API：新增 `tryonApi.virtualTryOn({ personImage, clothingImage, ... })`，直接 `fetch('/api/tryon/virtual', ...)`。  
   - 若使用 Modes：保持 `executeMode('virtual-try-on', ...)`，但保证 `attachments` 严格为 `[person, garment]`，且不再依赖 `prompt` 参与后端试衣逻辑。
3. **Handler**  
   - `VirtualTryOnHandler` 仅处理「双附件 + 调用试衣 API」；不再处理单图 + prompt 的旧形态。  
   - 若改用专用 API，可考虑让 View 直接调 API，Handler 只负责结果展示与上传（或逐步淡出 Handler 对试衣的参与）。
4. **Controls**  
   - 移除或淡化与 recontext 无关的项（如掩码、tryOnTarget）；保留与后端实际支持的选项（如 `numberOfImages`）。

### 5.3 联调与验收

- 用例：**人物图 A + 服装图 B** → 仅调用试衣 API → 返回结果图。  
- 校验：**缺少人物图 / 服装图** → 400 或前端禁用；**无效 Base64 / 格式错误** → 明确错误提示。  
- 回归：其他模式（如图片编辑、生成）不受影响。

---

## 六、接口速查

| 项目       | 说明                                                                 |
|------------|----------------------------------------------------------------------|
| **后端核心** | `TryOnService.virtual_tryon(person_image_base64, clothing_image_base64, ...)` |
| **Modes API** | `POST /api/modes/google/virtual-try-on`，`attachments[0]`=人物，`attachments[1]`=服装 |
| **Modes 备选** | `POST /api/modes/google/virtual-try-on`，`attachments[0]`=人物，`attachments[1]`=服装 |
| **前端 UI** | 双槽位（人物 / 服装），「开始试衣」→ 调用上述之一                   |
| **移除**   | 试衣流程中的 prompt、掩码预览、tryOnTarget 作为 API 参数             |

---

## 七、相关文档

- [OFFICIAL_SDK_IMAGE_EXAMPLES_AND_USAGE.md](./OFFICIAL_SDK_IMAGE_EXAMPLES_AND_USAGE.md)：`recontext_image` 官方示例与用法。  
- [README.md](./README.md)：Gemini 服务与 TryOnService 总览。

---

## 八、实现状态（2026-01-24）

| 项目 | 状态 | 说明 |
|------|------|------|
| **后端** 虚拟试衣 API | ✅ 已实现 | 通过统一 modes 路由 `POST /api/modes/google/virtual-try-on` 调用 `TryOnService.virtual_tryon`（无独立 `routers/tryon.py`） |
| **前端** `VirtualTryOnView` 重构 | ✅ 已实现 | 双槽位（人物 / 服装）、`开始试衣`、试衣历史、直接调 `/api/tryon/virtual` |
| **掩码预览 / tryOnTarget** | 已移除 | 与 recontext API 无关，不再作为试衣流程的一部分 |
| **Modes 路径** `virtual-try-on` | 未改动 | 仍可用；前端独立模式已切到专用 API |

---

*文档版本: 1.0 | 最后更新: 2026-01-24*
