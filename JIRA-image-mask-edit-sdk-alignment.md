# JIRA: Image Mask Edit 官方 SDK 对齐与链路修复

## 类型
Bug / Feature Hardening

## 状态
In Progress

## 背景
Mask 模式 UI 已提供矩形选区、画笔、橡皮擦、自动前景、自动背景、People/语义分割和导入 mask 的入口，但当前前后端链路没有严格按 Google GenAI SDK / Vertex AI Imagen mask edit 的官方结构执行，导致“UI 上有 mask，真实请求可能没有 mask”或“选了 Mask 模式但被路由到 Gemini chat edit”的脱节问题。

## 官方证据
- Google GenAI Python SDK `client.models.edit_image(...)` 要求 `reference_images` 是 `RawReferenceImage`、`MaskReferenceImage` 等对象列表。Mask 示例使用 `RawReferenceImage(reference_id=1, reference_image=...)` 加 `MaskReferenceImage(reference_id=2, config=MaskReferenceConfig(mask_mode='MASK_MODE_FOREGROUND', mask_dilation=0.06))`，模型为 `imagen-3.0-capability-001`。
- 官方自动前景/背景方式是不上传 mask 图片，传 `MaskReferenceImage(reference_image=None, config=MaskReferenceConfig(mask_mode='MASK_MODE_FOREGROUND' | 'MASK_MODE_BACKGROUND'))`。
- 官方手动 mask 方式是上传用户 mask 图片，并传 `MASK_MODE_USER_PROVIDED`；mask 图片必须与 raw 原图尺寸一致，非零像素代表要编辑的区域。
- 官方 People/语义分割是 `MASK_MODE_SEMANTIC`，并需要 mask classes / segmentation classes；person class id 为 `125`。
- 官方 `EDIT_IMAGE_COUNT / number_of_images` 支持 `1-4`。
- Google GenAI SDK 另有独立的 `client.models.segment_image(...)`，模型为 `image-segmentation-001`，用于返回 mask 图。它是 UI 预览/独立分割链路，不是 `edit_image` 自动 `MaskReferenceImage` 的必需步骤。
- 2026-03-24 Vertex AI 官方 release notes 将 `imagen-3.0-capability-001` 列入 Imagen generation GA endpoints deprecation，建议在 2026-06-30 前迁移到 `gemini-2.5-flash-image`。但截至 2026-05-08 官方 Gemini 编辑文档给出的替代方式是 `generate_content` 的自然语言 / mask-free editing，不提供等价的 `MaskReferenceImage` 精确 mask API；因此当前精确 Mask 模式仍按官方 SDK 的 Imagen mask edit 结构实现，并单独记录后续迁移风险。

Sources:
- https://googleapis.github.io/python-genai/genai.html
- https://cloud.google.com/vertex-ai/generative-ai/docs/image/edit-inpainting
- https://cloud.google.com/vertex-ai/generative-ai/docs/image/replace-image-background
- https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-customization
- https://cloud.google.com/vertex-ai/generative-ai/docs/release-notes
- https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-edit-images

## 本地证据链
- `frontend/components/views/ImageMaskEditView.tsx`
  - `maskPreviewUrl` 只用于 UI 预览，没有进入发送附件。
  - `handleImportMask` 是 TODO。
  - 历史列表仍是旧 bubble 结构，未复用 `ImageHistorySidebar`。
- `frontend/components/chat/ChatEditInputArea.tsx`
  - 发送时只处理用户附件/活跃画布图，没有 mask 专用附件入口。
- `frontend/hooks/handlers/ImageEditHandlerClass.ts`
  - `image-mask-edit` 假设第二个附件是 mask，但当前上游没有保证该附件存在或带 `role: "mask"`。
- `backend/app/routers/core/modes.py`
  - `convert_attachments_to_reference_images()` 只在 `attachment.role == "mask"` 时写入 `reference_images["mask"]`。
- `backend/app/services/gemini/coordinators/image_edit_coordinator.py`
  - Gemini image model 会优先走 conversational edit，Mask 模式如果暴露 Gemini image model 会绕开 Vertex Imagen mask edit。
- `backend/app/services/gemini/vertexai/vertex_edit_base.py`
  - 结构上已接近官方 SDK：`raw` 构造成 `RawReferenceImage`，`mask` 构造成 `MaskReferenceImage`，无 mask 时按 `mask_mode` 构造自动 mask。
- `backend/app/services/gemini/vertexai/segmentation_service.py`
  - `image-segmentation-001` 只服务 `/image-mask-preview` 预览反馈；权限不足时不应阻断正式 `image-mask-edit` 生成链路。

## 用户故事
1. 作为用户，我在 Mask 模式手动画选区/画笔后点击生成，系统应把我画出的 mask 作为 `MASK_MODE_USER_PROVIDED` 发送给 Vertex Imagen edit，而不是只在 UI 上显示。
2. 作为用户，我选择自动前景/背景后点击生成，系统应不上传 mask 图片，而是让后端构造自动 `MaskReferenceImage`。
3. 作为用户，我选择 People 后点击生成，系统应按官方 `MASK_MODE_SEMANTIC + segmentation_classes=[125]` 方式请求。
4. 作为用户，我在 Mask 模式选择模型时，只应看到真正支持 Vertex Imagen mask edit 的模型，避免误走 Gemini chat edit。

## 修复范围
- 前端类型补 `Attachment.role`。
- Mask 视图把手动/导入 mask 转为可发送的 Data URL，并作为 `role: "mask"` 附件追加。
- Mask 视图在手动 mask 模式下无 mask 时禁用生成。
- 自动前景/背景不发送 mask 图片，仅发送 `maskMode`。
- People/语义模式额外发送 `segmentationClasses: [125]`。
- Provider 转换链路保留 `role: "mask"`。
- 后端模型列表过滤：`image-mask-edit` 只暴露 Imagen edit 模型。
- 后端参数白名单和 SDK config 支持 `segmentation_classes`。
- 自动 mask 预览如果因为 `image-segmentation-001` 未开通而 404，只在 UI 上显示非阻塞提示；生成请求继续发送官方 `mask_mode`，由后端构造 `MaskReferenceImage`。

## 非目标
- 不重构整个 Mask 画布。
- 不在本次实现历史列表组件复用和 carousel，对比模式修复另列后续任务。
- 不改动视频、Recontext、Expand 既有行为。

## 验收标准
- 手动 mask 请求中后端收到 `reference_images.raw` 和 `reference_images.mask`。
- 自动前景/背景请求中后端收到 `reference_images.raw`，并由 config 的 `mask_mode` 构造自动 mask。
- People 请求中 config 包含 `mask_mode=MASK_MODE_SEMANTIC` 和 `segmentation_classes=[125]`。
- `image-mask-edit` 模型列表不再暴露 Gemini image 模型。
- 相关前端/后端测试通过。

## 测试计划
- Frontend:
  - `UnifiedProviderClient` 将 `referenceImages.mask` 转成 `role: "mask"` attachment。
  - `ImageMaskEditView` 在手动模式无 mask 时禁用生成。
  - `ImageMaskEditControls` 既有测试继续通过。
- Backend:
  - `convert_attachments_to_reference_images()` 识别 `role="mask"`。
  - 模型过滤对 `image-mask-edit` 只返回 `imagen-3.0-capability-001` 这类 Imagen edit 模型。
  - `VertexAIEditBase._build_reference_images()` 对 semantic mask 带 `segmentation_classes`。

## 风险
- 手动 mask 用 Data URL 会增加请求体体积，但 mask 与原图同尺寸且当前模式本来就是图像编辑请求，可接受。
- 真实 Vertex 调用仍可能受项目权限、区域、模型配额影响；本次先保证请求结构严格符合官方 SDK。
- `imagen-3.0-capability-001` 已进入官方 deprecation 窗口。后续需要单独评估 `gemini-2.5-flash-image` 的自然语言编辑是否能替代当前精确 mask / semantic mask 产品语义；不能把它当作同构接口直接替换。
