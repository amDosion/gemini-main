# Gemini 后端服务增强设计文档（中文）

> 面向目录：
> - `backend/app/services/gemini/geminiapi`
> - `backend/app/services/gemini/vertexai`
>
> 目标：在不破坏现有结构的前提下，系统性增强“对话编辑图片”和“Vertex AI 编辑/生成能力”的一致性、可扩展性与可维护性。

---

## 1. 范围与约束

- **范围**：仅覆盖 `geminiapi` 与 `vertexai` 目录下的所有现有服务文件。
- **不改代码**：本设计为增强方案与路线图，未直接修改代码。
- **兼容优先**：现有模式与参数兼容必须保持，新增能力只允许“向后兼容”扩展。

---

## 2. 现有功能清单（逐文件）

### 2.1 geminiapi

#### `conversational_image_edit_service.py`
- **定位**：对话式图片编辑（chat 模式，Gemini 原生图像模型）。
- **核心能力**：
  - 创建/恢复 chat 会话（`create_chat_session`）
  - 多轮编辑消息（`send_edit_message`）
  - 处理 reference images（data URL / fileUri / googleFileUri）
  - 返回：`images + text + thoughts`（新格式）
- **特性**：
  - `response_modalities=[TEXT, IMAGE]`
  - 根据模型决定是否启用 `thinking_config`
  - 支持多个图片 part（自然多图，但无“数量参数”）
- **局限**：
  - 不支持 edit_image 的完整 Config（例如 number_of_images / edit_mode）
  - 输出图片数量不可保证

#### `image_edit_gemini_api.py`
- **定位**：明确不支持 Gemini API 的 edit_image，统一抛 NotSupported。
- **作用**：接口统一但实际不可用。

#### `imagen_gemini_api.py`
- **定位**：Gemini API 图像生成（非编辑）。
- **能力**：
  - `number_of_images`（1-4）
  - aspect_ratio / image_size / output_mime_type / output_compression_quality
- **限制**：
  - 未支持 edit_image
  - 参数依赖模型支持度（有过滤机制）

### 2.2 vertexai

#### `vertex_edit_base.py`
- **定位**：所有 Vertex 编辑服务共用基类。
- **核心能力**：
  - 统一 `edit_image` 管线（_build_config → _build_reference_images → edit_image → _process_response）
  - camelCase → snake_case 兼容
  - 统一错误分类与基础验证
- **支持的 Reference 类型**：raw / mask / control / style / subject / content
- **支持的 EditMode**：inpaint / outpaint / bgswap / style / controlled / product

#### `mask_edit_service.py`
- **定位**：掩码编辑（inpaint/outpaint/bgswap）
- **默认参数**：guidance_scale / output_mime_type / safety_filter_level 等
- **自动 mask**：无 mask 时启用 `MASK_MODE_FOREGROUND`

#### `inpainting_service.py`
- **定位**：修复/插入内容（edit_mode = inpainting）

#### `background_edit_service.py`
- **定位**：背景替换（edit_mode = bgswap）

#### `recontext_service.py`
- **定位**：重新上下文（默认 inpaint insertion）

#### `expand_service.py`
- **定位**：扩图（outpaint）
- **能力**：scale / offset / ratio 模式
- **特点**：不继承 VertexAIEditBase，参数校验为独立逻辑

#### `segmentation_service.py`
- **定位**：图像分割（segment_image）
- **模式**：foreground/background/prompt/semantic/interactive

#### `upscale_service.py`
- **定位**：图像放大（2x/4x）
- **含分辨率限制检查**

#### `tryon_service.py`
- **定位**：虚拟试穿（recontext_image）
- **参数**：number_of_images / base_steps / output_mime_type / seed

#### `imagen_vertex_ai.py`
- **定位**：Vertex 图像生成（Imagen + Gemini）
- **注意**：Gemini image 模型通过 generate_content，多图通过循环调用

---

## 3. 现有能力矩阵

| 类别 | GeminiAPI(Chat) | Vertex edit_image | Vertex 扩展/增强 |
|---|---|---|---|
| 对话式编辑 | ✅ | ❌ | ❌ |
| 显式 number_of_images | ❌（无显式） | ✅（EditImageConfig） | 部分支持（Expand 具备） |
| edit_mode | ❌ | ✅ | ✅ |
| mask 模式 | ✅（隐式） | ✅ | ✅ |
| bgswap | ✅（prompt） | ✅ | ✅ |
| outpaint | ✅（prompt） | ✅ | ✅（Expand） |
| segmentation | ❌ | ❌ | ✅ |
| upscale | ❌ | ❌ | ✅ |
| try-on | ❌ | ❌ | ✅ |

---

## 4. 核心问题与缺口

1. **参数体系不一致**：
   - Chat 编辑没有 EditImageConfig；Vertex edit_image 有。
2. **输出结构不一致**：
   - Chat 返回 `{images,text,thoughts}`，Vertex 仅返回 List[images]。
3. **多图策略不一致**：
   - Vertex edit_image 支持 `number_of_images`；Chat 编辑不保证数量。
4. **扩图逻辑独立**：
   - ExpandService 未复用 VertexAIEditBase，导致参数验证和输出不一致。
5. **能力声明不统一**：
   - get_capabilities 字段结构各自定义，无法统一前端或调度层。
6. **错误分类与日志不统一**：
   - 基类有分类，其他服务不一致。

---

## 5. 增强目标（保证兼容）

1. **统一输出结构**（最低风险，最高收益）
2. **统一能力描述与参数 schema**
3. **明确 Chat vs Vertex 适配策略**
4. **增强多图/批量策略**
5. **统一错误分类与安全提示**

---

## 6. 增强方案设计（详细）

### 6.1 输出结构统一

**目标**：所有编辑类返回结构统一：

```json
{
  "images": [ {"url": "...", "mimeType": "image/png", "index": 0, "size": 12345, "enhancedPrompt": "..."} ],
  "text": "...",
  "thoughts": [ {"type": "text", "content": "..."} ],
  "meta": { "provider": "vertex_ai|gemini_chat", "model": "...", "batch": 1 }
}
```

- **Chat 编辑**：已有 text/thoughts，补齐 meta。  
- **Vertex 编辑**：封装 list → {images, meta}。  
- **兼容策略**：对旧接口保留 list 输出，逐步迁移。

### 6.2 统一能力描述

新增统一结构（对每个服务返回）：

```json
{
  "api_type": "vertex_ai|gemini_chat",
  "supports_editing": true,
  "supports_batch": true|false,
  "max_images": 1-4,
  "edit_modes": [...],
  "mask_modes": [...],
  "requires_vertex": true|false,
  "supports_thinking": true|false
}
```

- geminiapi → 支持 thinking 与多 part，但 batch=False。
- vertexai → 支持 batch 与 edit_modes。

### 6.3 多图策略

- **Vertex edit_image**：使用 `number_of_images`。
- **Chat 编辑**：通过 prompt 说明“请生成 3 张不同版本”，并从 parts 中返回多张。
- **统一层**：对外暴露 `requested_images`，Chat 模式标记为“best effort”。

### 6.4 统一参数归一化

- 抽出 `normalize_config()`（camel/snake），复用于:
  - VertexAIEditBase
  - ExpandService
  - TryOn/Segmentation/Upscale

### 6.5 错误与安全提示统一

- 对所有编辑类增加统一错误映射：
  - SAFETY / QUOTA / PERMISSION / UNSUPPORTED
- 统一错误返回结构（带 `error_type` & `user_friendly_message`）

---

## 7. 具体增强建议（geminiapi）

1. **chat 编辑支持批量返回**：
   - 在 prompt 层引导数量，并明确返回数量属于 best effort。
   - 解析响应时聚合全部 images。  

2. **统一输出结构**：
   - send_edit_message 返回 {images,text,thoughts,meta}

3. **能力声明**：
   - get_capabilities 增加 `supports_batch=false`、`max_images=4 (best effort)`。

---

## 8. 具体增强建议（vertexai）

1. **统一输出结构**：
   - VertexAIEditBase 返回 {images, meta}
   - ExpandService、TryOn、Upscale、Segmentation 输出增加 meta

2. **统一参数规范**：
   - ExpandService/Segmentation/UpScale 引入 normalize_config
   - 避免不同服务对 `number_of_images`/`output_mime_type` 命名不一致

3. **扩图服务与 edit_image 接口对齐**：
   - ExpandService 可暴露 `edit_mode=OUTPAINT` 的配置路径

---

## 9. 迁移路径

1. **第一阶段**：输出结构统一（不改业务逻辑）
2. **第二阶段**：能力描述统一（元数据补齐）
3. **第三阶段**：参数归一化抽取
4. **第四阶段**：多图策略增强（Chat best effort）

---

## 10. 风险与回滚

- **Chat 模式数量不可保证** → 在 meta 中标注 best-effort。
- **输出结构变更** → 兼容旧模式 list 输出。
- **扩图/分割/放大与 edit_image 融合过度** → 保留独立服务，不强行合并。

---

## 11. 验证方案

- 对同一 prompt 测试 Chat 与 Vertex 输出一致性
- 验证多图场景：
  - Vertex: number_of_images=3
  - Chat: prompt 引导 + 解析 parts
- 回归：旧接口调用返回 list 时仍可工作

---

## 12. 结论

通过最小侵入式改造，统一输出结构 + 能力描述 + 参数归一化，可显著提升：
- 前后端兼容性
- 批量输出一致性
- 日志与错误可观测性

同时保持现有服务与调用路径不变，风险可控。

