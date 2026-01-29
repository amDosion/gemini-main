# 对话式图片编辑：输出增强提示词与思考过程的修改方案（不改代码说明）

> 目标：结合前端参数面板（ImageEditView / ImageEditControls / ChatEditInputArea），让“增强提示词”和“思考过程”可控、可展示。
> 范围：仅给出改造方案与变更点，不直接改代码。

---

## 一、现状梳理（前后端已具备的能力）

### 前端
- 参数面板已有“AI 增强提示词”开关：
  - `frontend/controls/modes/google/ImageEditControls.tsx`
  - 使用 `controls.enhancePrompt` 作为状态
- 请求已携带 `enhancePrompt`：
  - `frontend/components/chat/ChatEditInputArea.tsx` 在 `options` 中传入 `enhancePrompt`
- 思考过程与文本响应展示已有UI：
  - `frontend/components/views/ImageEditView.tsx`
  - 通过 `ThinkingBlock` 展示 `lastMessage.thoughts + lastMessage.textResponse`

### 后端
- 对话式图片编辑服务已能采集 thoughts：
  - `backend/app/services/gemini/geminiapi/conversational_image_edit_service.py`
  - 开启 `thinking_config`（仅 gemini-3 系列）并从 `response.parts` 抽取 `thoughts`
- 但 **未使用 `enhancePrompt`**，因此没有“增强提示词”的输出

---

## 二、目标行为定义（产品层）

1) “增强提示词”开关开启时：
   - 在最终渲染区域/ThinkingBlock 能看到“增强提示词”文本
   - 不影响已有的图片输出结构

2) “思考过程”展示：
   - 仅在支持 thinking 的模型时启用（gemini-3 系列）
   - 可由前端开关显式控制

---

## 三、修改方案（不改代码说明）

### A. 增强提示词（最小改动方案）
**思路**：在后端组装 prompt 时，若 `enhancePrompt = true`，将“增强提示词输出要求”注入 prompt，让模型在文本响应中返回 `Enhanced Prompt`。

**改动点（后端）**
- 文件：`backend/app/services/gemini/geminiapi/conversational_image_edit_service.py`
- 位置：`send_edit_message(...)` 构建 message_parts 之前
- 逻辑：
  - 读取 `config` 中的 `enhancePrompt`
  - 若开启：对 `prompt` 包装，例如：
    - “请先给出增强后的提示词（Enhanced Prompt: ...），再生成图片。”
  - 该文本会进入 `text_responses`，前端 `ThinkingBlock` 会展示

**优点**
- 不需要新增字段，也不需要改前端结构
- `textResponse` 已有显示位

**注意**
- 使用 `gemini-2.5-flash-image` 也能输出文本，但不支持 thinking

---

### B. 增强提示词（稳定性更高方案）
**思路**：当 `enhancePrompt = true` 时，先调用文本模型生成增强提示词，再把增强后的提示词送进图像编辑模型。

**改动点（后端）**
- `conversational_image_edit_service.py`
  - 在 `send_edit_message(...)` 前新增一步：
    1. 调用文本模型（如 `gemini-2.5-flash`）生成增强提示词
    2. 将增强提示词替换为最终 prompt
    3. 将“增强提示词文本”塞入返回结果的 `text` 字段

**优点**
- 输出更稳定、结构更可控

**缺点**
- 需要增加一次模型调用（成本和时延增加）

---

### C. 思考过程的显式开关（前端可控）
**思路**：让用户在参数面板中决定是否启用 thinking。

**改动点（前端）**
- `frontend/controls/modes/google/ImageEditControls.tsx`
  - 增加一个开关，例如“显示思考过程”
  - 绑定 `controls.enableThinking`

**改动点（前端请求）**
- `frontend/components/chat/ChatEditInputArea.tsx`
  - `options.enableThinking = controls.enableThinking`

**改动点（后端）**
- `conversational_image_edit_service.py`
  - `_supports_thinking(model)` 判断通过后，再结合 `config.enableThinking` 决定是否传 `ThinkingConfig(include_thoughts=True)`

---

## 四、参数透传链路建议（字段名对齐）

| 目的 | 前端字段 | 后端读取 | 说明 |
|---|---|---|---|
| 增强提示词 | `options.enhancePrompt` | `config.enhancePrompt` | 已存在但后端未使用 |
| 思考过程开关 | `options.enableThinking` | `config.enableThinking` | 需新增透传 |

---

## 五、验证方案（不改代码情况下的验证建议）

1) 使用支持 thinking 的模型（gemini-3）
   - 检查 `lastMessage.thoughts` 是否非空
   - `ThinkingBlock` 是否展示

2) 打开“增强提示词”开关
   - 检查 `textResponse` 是否包含“Enhanced Prompt”
   - 看最终图片是否仍正常生成

---

## 六、输出结构建议（不改结构，但明确语义）

当前返回中每个 image 已附加：
- `text`（增强提示词建议放这里）
- `thoughts`（思考过程）

**建议约定**：
- `text` 字段优先用于“增强提示词”
- `thoughts` 字段用于模型思考过程

---

## 七、涉及文件清单

前端：
- `frontend/components/views/ImageEditView.tsx`
- `frontend/components/chat/ChatEditInputArea.tsx`
- `frontend/controls/modes/google/ImageEditControls.tsx`
- `frontend/hooks/useControlsState.ts`

后端：
- `backend/app/services/gemini/geminiapi/conversational_image_edit_service.py`

---

如果你确认要执行，我可以基于此方案落地：
1) 先做最小改动（方案A）
2) 再提供稳定方案B的可选实现
