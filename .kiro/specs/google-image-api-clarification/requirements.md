# Requirements Document: Google Image API 方式梳理

## Introduction

本文档旨在梳理 Google 提供的三种不同的图片生成/编辑 API 方式，明确它们的区别、适用场景和正确使用方法。

## Glossary

- **Google GenAI SDK**: Google 官方的 Python SDK (`google-genai`)，统一封装了 Vertex AI 和 Gemini API
- **Vertex AI API**: Google Cloud 的企业级 AI 服务 API
- **Gemini API**: Google 的开发者 API（需要 API Key）
- **Imagen**: Google 的图片生成模型系列（Imagen-3.0, Imagen-4.0）
- **Gemini Image Models**: Gemini 多模态模型的图片生成能力（Gemini-2.5/3.0-pro-image, Veo-3.1）
- **Capability Model**: 专门用于图片编辑的模型（imagen-3.0-capability-001）
- **Reference Image**: 编辑操作中的参考图片（基础图、mask、风格参考等）

## Requirements

### Requirement 1: 理解三种 API 方式的区别

**User Story:** 作为开发者，我想理解 Google 提供的三种图片 API 方式的本质区别，以便选择正确的方法。

#### Acceptance Criteria

1. THE System SHALL 明确区分以下三种方式：
   - **方式 1**: `generate_images()` - Imagen 模型的图片生成
   - **方式 2**: `generate_content()` - Gemini 多模态模型的图片生成
   - **方式 3**: `edit_image()` - Capability 模型的图片编辑

2. WHEN 开发者查看文档 THEN THE System SHALL 说明每种方式的核心特征：
   - 使用的 API 方法名称
   - 支持的模型列表
   - 输入参数类型
   - 输出响应格式
   - 配置对象类型

3. THE System SHALL 说明这三种方式都使用同一个 SDK (`google-genai`)，只是调用不同的方法

### Requirement 2: 明确 generate_images() 的使用场景

**User Story:** 作为开发者，我想知道何时使用 `generate_images()` 方法。

#### Acceptance Criteria

1. THE System SHALL 说明 `generate_images()` 适用于以下场景：
   - 使用 Imagen-3.0 或 Imagen-4.0 模型
   - 纯文本到图片的生成（Text-to-Image）
   - 不需要编辑现有图片
   - 不需要多模态输入/输出

2. THE System SHALL 列出 `generate_images()` 的配置参数：
   - `number_of_images`: 生成图片数量
   - `aspect_ratio`: 宽高比
   - `output_mime_type`: 输出格式
   - `include_rai_reason`: 是否包含 RAI 过滤原因
   - `image_size`: 图片尺寸

3. THE System SHALL 说明响应格式为 `GenerateImagesResponse`，包含 `generated_images` 列表

### Requirement 3: 明确 generate_content() 的使用场景

**User Story:** 作为开发者，我想知道何时使用 `generate_content()` 方法生成图片。

#### Acceptance Criteria

1. THE System SHALL 说明 `generate_content()` 适用于以下场景：
   - 使用 Gemini-2.5/3.0-pro-image 或 Veo-3.1 模型
   - 需要多模态输入（文本 + 图片）
   - 需要多模态输出（文本 + 图片）
   - 需要对话式交互

2. THE System SHALL 列出 `generate_content()` 的图片相关配置：
   - `response_modalities`: 必须包含 `["TEXT", "IMAGE"]`
   - `ImageConfig`: 包含 `aspect_ratio`, `image_size`, `output_mime_type`
   - `SafetySetting`: 安全过滤设置

3. THE System SHALL 说明响应格式为 `GenerateContentResponse`，需要从 `candidates[].content.parts[]` 中提取 `inline_data`

4. THE System SHALL 说明此方法不支持一次生成多张图片，需要多次调用

### Requirement 4: 明确 edit_image() 的使用场景

**User Story:** 作为开发者，我想知道何时使用 `edit_image()` 方法。

#### Acceptance Criteria

1. THE System SHALL 说明 `edit_image()` 适用于以下场景：
   - 使用 imagen-3.0-capability-001 模型
   - 需要编辑现有图片（Inpainting）
   - 需要使用 mask 指定编辑区域
   - 需要风格迁移或主体定制

2. THE System SHALL 列出 `edit_image()` 支持的 Reference Image 类型：
   - `RawReferenceImage`: 基础图片
   - `MaskReferenceImage`: Mask 图片（FOREGROUND/BACKGROUND/USER_PROVIDED）
   - `ControlReferenceImage`: 控制图（Scribble）
   - `StyleReferenceImage`: 风格参考图
   - `SubjectReferenceImage`: 主体参考图
   - `ContentReferenceImage`: 内容参考图（GCS URI）

3. THE System SHALL 列出 `edit_image()` 的配置参数：
   - `edit_mode`: 编辑模式（INPAINT_INSERTION, INPAINT_REMOVAL 等）
   - `guidance_scale`: 引导强度
   - `negative_prompt`: 负面提示词
   - `base_steps`: 基础步数
   - `safety_filter_level`: 安全过滤级别
   - `person_generation`: 人物生成设置

4. THE System SHALL 说明响应格式为 `EditImageResponse`，包含 `generated_images` 列表

### Requirement 5: 提供 API 选择决策树

**User Story:** 作为开发者，我想要一个清晰的决策树来帮助我选择正确的 API 方法。

#### Acceptance Criteria

1. THE System SHALL 提供决策流程：
   ```
   需要编辑现有图片？
   ├─ 是 → 使用 edit_image() + imagen-3.0-capability-001
   └─ 否 → 需要多模态交互？
       ├─ 是 → 使用 generate_content() + Gemini Image Models
       └─ 否 → 使用 generate_images() + Imagen Models
   ```

2. THE System SHALL 说明每种方式的性能特点：
   - `generate_images()`: 最快，专注图片生成
   - `generate_content()`: 中等，支持多模态
   - `edit_image()`: 较慢，支持复杂编辑

3. THE System SHALL 说明每种方式的成本考虑（如果适用）

### Requirement 6: 提供代码示例对比

**User Story:** 作为开发者，我想看到三种方式的并排代码示例，以便理解它们的差异。

#### Acceptance Criteria

1. THE System SHALL 提供 `generate_images()` 的完整示例：
   - 初始化客户端
   - 构建配置
   - 调用 API
   - 处理响应

2. THE System SHALL 提供 `generate_content()` 的完整示例：
   - 初始化客户端
   - 构建 Content 和 Config
   - 调用 API
   - 提取图片数据

3. THE System SHALL 提供 `edit_image()` 的完整示例：
   - 初始化客户端
   - 创建 Reference Images
   - 构建 EditImageConfig
   - 调用 API
   - 处理响应

4. THE System SHALL 在每个示例中标注关键差异点

### Requirement 7: 说明 SDK 统一性

**User Story:** 作为开发者，我想理解这三种方式是否使用同一个 SDK，以及如何配置。

#### Acceptance Criteria

1. THE System SHALL 说明所有三种方式都使用 `google-genai` SDK

2. THE System SHALL 说明客户端初始化方式：
   - Vertex AI: 设置环境变量 `GOOGLE_GENAI_USE_VERTEXAI=true`
   - Gemini API: 使用 API Key

3. THE System SHALL 说明三种方式可以在同一个项目中混用

4. THE System SHALL 说明模型名称格式的差异：
   - Vertex AI: `publishers/google/models/imagen-3.0-generate-001`
   - Gemini API: `models/imagen-3.0-generate-001`

### Requirement 8: 更新现有代码库

**User Story:** 作为开发者，我想更新现有的 `imagen_vertex_ai.py` 以支持 `edit_image()` 方法。

#### Acceptance Criteria

1. WHEN 检测到 capability 模型 THEN THE System SHALL 使用 `edit_image()` 方法

2. THE System SHALL 支持以下编辑模式：
   - INPAINT_INSERTION: 插入新内容
   - INPAINT_REMOVAL: 移除内容
   - OUTPAINT: 扩展图片

3. THE System SHALL 支持多种 Reference Image 类型的组合

4. THE System SHALL 正确处理 mask 图片的上传和配置

5. THE System SHALL 保持与现有 `generate_images()` 和 `generate_content()` 方法的兼容性
