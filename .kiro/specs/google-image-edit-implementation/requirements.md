# Requirements Document: Google Image Editing Implementation

## Introduction

本文档定义 Google Gemini 图像编辑功能的需求，包括后端 API 实现和前端集成。该功能将支持 Vertex AI 和 Gemini API 双模式，类似于现有的图像生成流程。

**核心目标**：
- 提供安全的图像编辑 API（API Key 不暴露在前端）
- 支持 Vertex AI 配置（优先）和 Gemini API（回退）
- 支持多种编辑模式（inpaint, outpaint, style transfer 等）
- 与现有架构保持一致（参考 `imagen_coordinator.py`）

## Glossary

- **System**: Google 图像编辑系统
- **Vertex_AI**: Google Cloud Vertex AI 图像编辑服务
- **Gemini_API**: Google Gemini API 图像编辑服务
- **ImageEditCoordinator**: 协调 Vertex AI 和 Gemini API 的协调器
- **Backend_API**: 后端 FastAPI 路由端点
- **Frontend_Client**: 前端 UnifiedProviderClient
- **Reference_Image**: 参考图像（原始图像、掩码、样式等）
- **Edit_Config**: 图像编辑配置对象
- **User_Context**: 用户上下文（user_id, db session）

## Requirements

### Requirement 1: 后端图像编辑 API

**User Story**: 作为前端开发者，我希望调用后端 API 进行图像编辑，这样 API Key 不会暴露在前端。

#### Acceptance Criteria

1. WHEN 前端发送图像编辑请求到 `/api/generate/google/image/edit`，THEN THE System SHALL 接收请求并验证参数
2. WHEN 请求包含 prompt 和 reference_images，THEN THE System SHALL 将它们传递给 ImageEditCoordinator
3. WHEN 请求包含 edit_config，THEN THE System SHALL 验证配置参数的有效性
4. WHEN 图像编辑成功，THEN THE System SHALL 返回生成的图像列表（Base64 格式）
5. WHEN 图像编辑失败，THEN THE System SHALL 返回详细的错误信息和 HTTP 状态码

### Requirement 2: Vertex AI 优先策略

**User Story**: 作为系统管理员，我希望系统优先使用 Vertex AI 进行图像编辑，这样可以利用企业级配置和更好的性能。

#### Acceptance Criteria

1. WHEN 用户配置了 Vertex AI（project, location, credentials），THEN THE ImageEditCoordinator SHALL 使用 Vertex AI 进行图像编辑
2. WHEN 用户未配置 Vertex AI，THEN THE ImageEditCoordinator SHALL 回退到 Gemini API
3. WHEN Vertex AI 配置不完整（缺少 project 或 location），THEN THE ImageEditCoordinator SHALL 回退到 Gemini API
4. WHEN 从数据库加载 Vertex AI 配置，THEN THE System SHALL 记录配置来源（数据库或环境变量）
5. WHEN Vertex AI 调用失败，THEN THE System SHALL 记录错误并尝试回退到 Gemini API

### Requirement 3: Gemini API 回退支持

**User Story**: 作为开发者，我希望在 Vertex AI 不可用时能回退到 Gemini API，这样系统具有更好的容错性。

#### Acceptance Criteria

1. WHEN Vertex AI 不可用或未配置，THEN THE System SHALL 使用 Gemini API 进行图像编辑
2. WHEN Gemini API 不支持图像编辑功能，THEN THE System SHALL 返回明确的错误信息
3. WHEN 使用 Gemini API，THEN THE System SHALL 从环境变量或数据库获取 API Key
4. WHEN Gemini API 调用失败，THEN THE System SHALL 返回详细的错误信息
5. WHEN 回退发生，THEN THE System SHALL 记录回退事件用于监控

### Requirement 4: 参考图像处理

**User Story**: 作为用户，我希望能上传多种类型的参考图像（原始图像、掩码、样式等），这样可以实现复杂的编辑效果。

#### Acceptance Criteria

1. WHEN 前端发送 RawReferenceImage，THEN THE System SHALL 将其转换为 SDK 格式
2. WHEN 前端发送 MaskReferenceImage，THEN THE System SHALL 验证掩码模式和配置
3. WHEN 前端发送 StyleReferenceImage，THEN THE System SHALL 验证样式描述
4. WHEN 前端发送 SubjectReferenceImage，THEN THE System SHALL 验证主体类型和描述
5. WHEN 前端发送 ControlReferenceImage，THEN THE System SHALL 验证控制类型
6. WHEN 前端发送 ContentReferenceImage，THEN THE System SHALL 支持 GCS URI 和 Base64
7. WHEN 参考图像格式无效，THEN THE System SHALL 返回验证错误

### Requirement 5: 编辑配置验证

**User Story**: 作为系统，我需要验证编辑配置参数，这样可以避免无效的 API 调用。

#### Acceptance Criteria

1. WHEN edit_mode 为 INPAINT_INSERTION，THEN THE System SHALL 验证必须提供掩码参考图像
2. WHEN edit_mode 为 INPAINT_INSERTION，THEN THE System SHALL 拒绝 aspect_ratio 参数（不支持）
3. WHEN number_of_images 超出范围（1-8），THEN THE System SHALL 返回验证错误
4. WHEN aspect_ratio 不在有效列表中，THEN THE System SHALL 返回验证错误
5. WHEN guidance_scale 超出范围（0-100），THEN THE System SHALL 返回验证错误
6. WHEN output_compression_quality 超出范围（1-100），THEN THE System SHALL 返回验证错误
7. WHEN add_watermark=True 且提供了 seed，THEN THE System SHALL 返回冲突错误

### Requirement 6: 用户上下文传递

**User Story**: 作为系统架构师，我希望用户上下文正确传递到所有层级，这样可以加载用户特定的配置。

#### Acceptance Criteria

1. WHEN 路由接收到请求，THEN THE System SHALL 从认证中间件获取 user_id
2. WHEN 调用 ProviderFactory，THEN THE System SHALL 传递 user_id 和 db session
3. WHEN 创建 GoogleService，THEN THE System SHALL 传递 user_id 和 db session
4. WHEN 创建 ImageEditCoordinator，THEN THE System SHALL 传递 user_id 和 db session
5. WHEN 加载 Vertex AI 配置，THEN THE System SHALL 使用 user_id 查询数据库

### Requirement 7: 前端集成

**User Story**: 作为前端开发者，我希望通过 UnifiedProviderClient 调用图像编辑 API，这样保持接口一致性。

#### Acceptance Criteria

1. WHEN 调用 UnifiedProviderClient.editImage()，THEN THE System SHALL 发送请求到后端 API
2. WHEN 发送请求，THEN THE System SHALL 不包含 apiKey 参数（安全性）
3. WHEN 发送请求，THEN THE System SHALL 包含 credentials: 'include'（发送 session cookie）
4. WHEN 发送请求，THEN THE System SHALL 包含 Authorization header（JWT token）
5. WHEN 接收响应，THEN THE System SHALL 解析图像列表并返回
6. WHEN 接收错误响应，THEN THE System SHALL 根据 HTTP 状态码提供友好的错误信息

### Requirement 8: 错误处理和日志

**User Story**: 作为运维人员，我希望系统提供详细的错误信息和日志，这样可以快速定位问题。

#### Acceptance Criteria

1. WHEN 任何层级发生错误，THEN THE System SHALL 记录详细的错误日志
2. WHEN Vertex AI 调用失败，THEN THE System SHALL 记录失败原因和回退决策
3. WHEN 参数验证失败，THEN THE System SHALL 返回 400 错误和具体的验证信息
4. WHEN 认证失败，THEN THE System SHALL 返回 401 错误
5. WHEN API 调用超时，THEN THE System SHALL 返回 504 错误
6. WHEN 内容被安全过滤器阻止，THEN THE System SHALL 返回 422 错误和 RAI 原因
7. WHEN 服务不可用，THEN THE System SHALL 返回 503 错误

### Requirement 9: 监控和统计

**User Story**: 作为产品经理，我希望追踪图像编辑的使用情况，这样可以了解功能使用率和成本。

#### Acceptance Criteria

1. WHEN 使用 Vertex AI 编辑图像，THEN THE System SHALL 增加 vertex_ai_edit_count 计数器
2. WHEN 使用 Gemini API 编辑图像，THEN THE System SHALL 增加 gemini_api_edit_count 计数器
3. WHEN 发生回退，THEN THE System SHALL 增加 edit_fallback_count 计数器
4. WHEN 调用监控端点 `/api/generate/monitoring/stats`，THEN THE System SHALL 返回编辑统计数据
5. WHEN 重置统计数据，THEN THE System SHALL 提供 reset 功能（仅测试环境）

### Requirement 10: 向后兼容性

**User Story**: 作为系统维护者，我希望新功能不影响现有的图像生成功能，这样保证系统稳定性。

#### Acceptance Criteria

1. WHEN 添加图像编辑功能，THEN THE System SHALL 不修改现有的图像生成代码
2. WHEN 使用 GoogleService，THEN THE System SHALL 同时支持 generate_image() 和 edit_image() 方法
3. WHEN 使用 ProviderFactory，THEN THE System SHALL 保持现有的接口签名
4. WHEN 使用 UnifiedProviderClient，THEN THE System SHALL 保持现有的 generateImage() 方法不变
5. WHEN 运行现有测试，THEN THE System SHALL 所有测试通过（无回归）

---

**文档版本**: v1.0.0  
**创建日期**: 2026-01-09  
**作者**: Development Team
