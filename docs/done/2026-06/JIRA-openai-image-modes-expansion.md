# JIRA: OpenAI GPT Image Modes Expansion

## 背景

当前项目已经支持 OpenAI `image-gen` 与 `image-chat-edit`，但部分图片模式仍复用 Google/Vertex 专用控件或缺少 OpenAI 服务方法，导致切换到 OpenAI provider 后出现模型不可选、参数面板不匹配、统一 `/api/modes/{provider}/{mode}` 路由无法落到服务层的问题。

官方依据：

- OpenAI Image Generation Guide: https://developers.openai.com/api/docs/guides/image-generation?api=image
- OpenAI multi-turn image guide: https://developers.openai.com/api/docs/guides/image-generation?api=image&multi-turn=responseid
- OpenAI Images and Vision Guide: https://developers.openai.com/api/docs/guides/images-vision?format=file
- OpenAI ImageGen demo: https://github.com/openai/openai-imagegen-demo

## 官方能力归纳

- `images.generate` 适合文生图，对应本项目 `image-gen`。
- `images.edit` 支持参考图、多参考图、mask、输出数量、尺寸、质量、背景、格式等参数，对应 `image-chat-edit` 以及可被提示词表达的图片编辑派生模式。
- `gpt-image-2` 在当前项目中采用官方最新 GPT Image 面：默认高质量、`auto/1K/2K/max` 分辨率层级、`1:1/4:3/3:4/16:9/9:16` 比例。
- Responses API 的 `previous_response_id`、`input_image`、`input_file`、`image_generation` 工具适合多轮图片上下文和文件输入场景；本项目现在作为 OpenAI 图片高级路径接入，默认仍保持 Image API。
- 官方 demo 使用 `/images/edits`、GPT Image 2 和 streaming partial images，可继续作为流式局部预览的实现参考。

## 模式矩阵

| 模式 | OpenAI 路线 | 当前落地 |
| --- | --- | --- |
| `image-gen` | `images.generate` | 已有并保留 |
| `image-chat-edit` | `images.edit` | 已有并保留 |
| `image-mask-edit` | `images.edit` + mask attachment | 统一到 GPT Image 编辑面 |
| `image-inpainting` | `images.edit` | 统一到 GPT Image 编辑面 |
| `image-background-edit` | `images.edit` + prompt | 统一到 GPT Image 编辑面 |
| `image-recontext` | `images.edit` + prompt/reference | 统一到 GPT Image 编辑面 |
| `image-outpainting` | `images.edit` + extension prompt | 新增 `OpenAIService.expand_image` |
| `virtual-try-on` | `images.edit` + person/garment references | 新增 `OpenAIService.virtual_tryon` |
| `pdf-extract` | Responses API `input_file` | 新增 OpenAI PDF file input 提取 |

## 本次修改

- 前端 OpenAI provider override 新增：
  - `ImageMaskEditControls`
  - `ImageOutpaintControls`
  - `VirtualTryOnControls`
- 这三个控件都复用 `OpenAIImageControls`，避免继续展示 Google/Vertex 专用字段。
- `ModeControlsCoordinator` 给 mask/outpaint/try-on 传入 `mode/currentModel/availableModels/maxImageCount`，让 OpenAI schema 能按模型变体解析。
- 后端 `mode_controls_catalog` 为 OpenAI provider 增加派生模式别名，将 `image-mask-edit/image-outpainting/virtual-try-on` 等归一到 `image-edit` schema。
- 后端模型过滤允许 `gpt-image-*` 出现在 OpenAI 的 mask/background/recontext/outpainting/try-on 模式中。
- `OpenAIService` 新增：
  - `expand_image()`：统一 modes 路由可调用，内部转到 `ImageEditor.edit_image(mode="image-outpainting")`
  - `virtual_tryon()`：使用两张参考图的 GPT Image edit 实现试衣
- 统一 modes 路由将 `virtual_tryon` 纳入图片结果持久化路径，试衣结果会像 Gen/Edit/Expand 一样落模型消息、附件和上传任务。

## 高级能力落地

- 新增 `ResponsesImageService`，OpenAI 图片模式可通过共享参数 `openaiImageApi=responses` 切换到 Responses API。
- `ResponsesImageService` 支持：
  - 文生图：`image_generation` tool action=`generate`
  - 图生图/派生编辑：`input_image` + action=`edit/auto`
  - 多轮上下文：透传 `openaiPreviousResponseId` 到 `previous_response_id`
  - 多张图片：按现有并发策略拆成多个 Responses API 调用，避免依赖单接口是否支持 `n`
- 前端 `OpenAIImageControls` 新增共享“OpenAI 图片接口”选项；选择 Responses API 时复用 OpenAI 文本模型候选选择器，不为每个模式单独做控件。
- 图片结果会保留 `openai_response_id/openaiResponseId`，供后续多轮编辑继续传 `previous_response_id`。
- 新增 `OpenAIPDFExtractor`，`pdf-extract` 在 OpenAI provider 下使用 Responses API `input_file`，避免“模型可选但服务不支持”的断层。

## 后续高级能力

- 为 GPT Image streaming partial images 增加 SSE 结果流，前端可先显示局部预览，再替换为最终附件。
- 将 OpenAI `openaiResponseId` 与活跃画布/历史图片选择继续打通，实现无需用户手动带参的多轮 Responses 图片续编。
