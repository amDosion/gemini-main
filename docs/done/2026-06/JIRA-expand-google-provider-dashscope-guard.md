# JIRA: Expand 模式误要求 DashScope Key 导致 Google/Gemini 路由被拦截

## 背景

Expand/Image Outpainting 当前有四个子模式：

- `ratio`: 按目标比例扩图。
- `scale`: 按水平/垂直缩放因子扩图。
- `offset`: 按四边像素偏移扩图。
- `upscale`: 按 `x2`/`x3`/`x4` 放大。

项目内证据：

- `frontend/controls/modes/google/ImageOutpaintControls.tsx` 的 `MODE_META` 和 `isOutpaintMode()` 明确包含 `ratio`、`scale`、`offset`、`upscale` 四种。
- `backend/app/config/mode_controls_catalog.json` 的 Google `image-outpainting` catalog 暴露同样四种 `outpaint_modes`。
- `backend/app/routers/core/modes.py` 会把前端 `outpaint_mode` 映射成 `ExpandService.expand_image()` 需要的 `mode`。
- `backend/app/services/gemini/vertexai/expand_service.py` 在 `mode` 为 `scale`、`offset`、`ratio` 时走 Vertex `edit_image` outpaint；`upscale` 时走 Vertex `upscale_image`。
- `frontend/services/llmService.ts` 的 `outPaintImage()` 已通过当前 provider 的 `executeMode('image-outpainting', ...)` 进入 `/api/modes/{provider}/image-outpainting`。

官方 SDK/文档证据：

- Google Cloud Vertex AI Outpaint 文档使用 `client.models.edit_image(...)`、`RawReferenceImage`、`MaskReferenceImage`、`MaskReferenceConfig(mask_mode="MASK_MODE_USER_PROVIDED")`、`EditImageConfig(edit_mode="EDIT_MODE_OUTPAINT")`，模型为 `imagen-3.0-capability-001`。参考：https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/edit-outpainting
- Google GenAI Python SDK README 明确 `edit_image` 和 `upscale_image` 仅支持 Vertex AI；`upscale_image` 示例模型为 `imagen-4.0-upscale-preview`。参考：https://github.com/googleapis/python-genai/blob/main/README.md
- Google Cloud Vertex AI Upscale 文档说明 `imagen-4.0-upscale-preview` 支持 `x2`、`x3`、`x4` 放大，并走 Vertex predict/upscale 语义。参考：https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/upscale-image
- Google GenAI JS SDK API 文档中 `models.editImage()` 接收 `EditImageParameters`，`models.upscaleImage()` 接收 `UpscaleImageParameters`；Vertex/Enterprise 路径需要 project/location，而不是 DashScope Key。参考：https://googleapis.github.io/js-genai/release_docs/classes/models.Models.html

## 问题

当当前激活 profile 是 Google/Gemini provider 且没有配置 DashScope Key 时，前端发送 `image-outpainting` 会被 `frontend/App.tsx` 的发送前预检拦截：

```ts
if (
  mode === 'image-outpainting' &&
  !config.dashscopeApiKey &&
  config.providerId !== 'tongyi'
) {
  showWarning("DashScope API Key is required for 'Expand Image'. Please configure it in Settings.");
  setIsSettingsOpen(true);
  return;
}
```

这段逻辑发生在 provider 路由之前，所以 Google/Gemini 的合法 Vertex Expand 请求无法进入 `llmService.outPaintImage()` 和后端 `ExpandService`。

## 根因

旧的 App 层 guard 把 Expand 模式历史上的 DashScope fallback 当成了全局前置条件。现在 Expand 已经 provider 化：

- Google/Gemini Expand 应该走 Google provider 的 `executeMode('image-outpainting')`。
- Tongyi/DashScope Expand 应该由 Tongyi provider 和它自己的 profile/API key 处理。
- 不支持 Expand 的 provider 应该由 provider 能力/后端路由返回真实错误，而不是在 App 层统一报 DashScope Key。

因此这个 guard 是错误的全局耦合。

## 修复计划

1. 增加 App 层回归测试：
   - 当前 provider 为 `google`。
   - `config.apiKey` 有值。
   - `config.dashscopeApiKey` 为空。
   - 发送 `image-outpainting`。
   - 期望不触发 DashScope warning、不打开 Settings，并调用 `sendMessage()`。

2. 精准修改 `frontend/App.tsx`：
   - 移除 `image-outpainting` 对 `config.dashscopeApiKey` 的 App 层前置依赖。
   - 保留现有主 provider API key 检查：非 Ollama provider 仍然需要 `config.apiKey`。
   - 保留现有模型选择、session 创建、protocol 检查、`sendMessage()` 流程。

3. 保持现有 `llmService.outPaintImage()` 路由不变：
   - 继续优先走当前 provider `executeMode('image-outpainting')`。
   - DashScope fallback 只作为旧 provider 兼容路径存在，不作为 Google/Gemini 的前端 blocker。

4. 验证：
   - 先运行新增测试，确认修改前 RED。
   - 修复后运行同一测试和 `llmService.outpainting` 路由测试。
   - 运行 `npx tsc --noEmit`。
   - 运行 `git diff --check` 检查空白问题。

## 验收标准

- Google/Gemini active profile 下，未配置 DashScope Key 也可以发送 Expand 请求。
- 上述请求不会出现 “DashScope API Key is required for 'Expand Image'”。
- Tongyi provider 不受影响，仍按自己的 active profile/API key 配置发送。
- `ratio`、`scale`、`offset`、`upscale` 四种子模式仍通过 `outpaintMode/outpaint_mode -> mode` 到达后端。
- 新增/相关测试通过。

## 非本次范围

- 不在本票修改 Vertex Expand 算法、padding/mask 生成逻辑。
- 不在本票修改 Google ratio 可选比例与后端 `_validate_ratio_parameters` 的差异；该问题应单独开票，因为它不导致本次 DashScope Key 误拦截。
