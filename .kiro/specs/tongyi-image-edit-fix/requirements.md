# Requirements Document

## Introduction

本需求文档旨在解决通义（Tongyi）提供商在图像编辑（Image Edit）模式下，处理远程 HTTP/HTTPS 图片 URL 时出现的下载超时问题。

## Glossary

- **DashScope**: 阿里云百炼平台的 API 服务
- **Image_Edit**: 图像编辑功能，基于现有图片进行修改
- **OSS**: 对象存储服务（Object Storage Service）
- **CONTINUITY_LOGIC**: 前端附件复用逻辑，用于在多轮对话中复用历史附件
- **X_DashScope_OssResourceResolve**: DashScope API 请求头，用于启用外部 URL 访问
- **System**: 整个图像编辑系统，包括前端和后端

## Requirements

### Requirement 1: 修复远程 URL 下载超时问题

**User Story:** 作为用户，当我使用通义提供商的图像编辑功能时，我希望系统能够正确处理远程图片 URL，而不会因为下载超时而失败。

#### Acceptance Criteria

1. WHEN 用户使用远程 HTTP/HTTPS 图片 URL 进行图像编辑 THEN THE System SHALL 优先尝试直接使用该 URL 调用 DashScope API
2. WHEN DashScope API 返回下载超时错误 THEN THE System SHALL 自动切换到备用方案（下载并上传到 OSS）
3. WHEN 备用方案执行时 THEN THE System SHALL 通过后端代理下载图片以避免 CORS 问题
4. WHEN 备用方案成功 THEN THE System SHALL 使用 OSS URL 重新调用 DashScope API
5. WHEN 备用方案失败 THEN THE System SHALL 返回清晰的错误信息给用户

### Requirement 2: 优化图片 URL 处理策略

**User Story:** 作为开发者，我希望系统能够智能地选择最优的图片 URL 处理策略，以提高成功率和性能。

#### Acceptance Criteria

1. WHEN 图片 URL 是 oss:// 格式 THEN THE System SHALL 直接使用该 URL 并启用 X_DashScope_OssResourceResolve
2. WHEN 图片 URL 是 HTTP/HTTPS 格式 THEN THE System SHALL 先尝试直接使用，失败后再下载上传
3. WHEN 图片是 blob: 或 data: URI THEN THE System SHALL 直接上传到 OSS
4. WHEN 图片已经在 DashScope OSS 中 THEN THE System SHALL 复用该 OSS URL
5. WHEN 处理策略切换时 THEN THE System SHALL 记录详细日志以便调试

### Requirement 3: 改进错误处理和用户反馈

**User Story:** 作为用户，当图像编辑失败时，我希望能够看到清晰的错误信息，了解失败原因和可能的解决方案。

#### Acceptance Criteria

1. WHEN 下载超时错误发生 THEN THE System SHALL 识别该错误类型并触发备用方案
2. WHEN 备用方案执行 THEN THE System SHALL 向用户显示"正在重试..."的提示
3. WHEN 所有方案都失败 THEN THE System SHALL 返回包含具体原因和建议的错误信息
4. WHEN 错误是网络问题 THEN THE System SHALL 建议用户检查网络连接
5. WHEN 错误是权限问题 THEN THE System SHALL 建议用户检查 API Key 权限

### Requirement 4: 后端支持图片下载代理

**User Story:** 作为系统，我需要后端提供图片下载代理服务，以避免浏览器的 CORS 限制。

#### Acceptance Criteria

1. WHEN 前端请求下载远程图片 THEN THE Backend SHALL 提供 /api/storage/download 端点
2. WHEN 后端接收下载请求 THEN THE Backend SHALL 验证 URL 的合法性
3. WHEN 后端下载图片 THEN THE Backend SHALL 设置合理的超时时间（30秒）
4. WHEN 下载成功 THEN THE Backend SHALL 返回图片的二进制数据和正确的 Content_Type
5. WHEN 下载失败 THEN THE Backend SHALL 返回清晰的错误信息和 HTTP 状态码
