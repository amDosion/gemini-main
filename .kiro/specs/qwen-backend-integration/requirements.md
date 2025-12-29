# Requirements Document

## Introduction

本需求文档定义了通义千问后端集成功能，目标是将前端的 DashScope API 调用迁移到后端。

**当前状态分析**：

前端直接调用 DashScope API：
- ✅ 聊天功能 (`streamNativeDashScope`) - 前端直接调用
- ✅ 模型列表获取 (`getTongYiModels`) - 前端直接调用
- ✅ 图像生成 (`generateDashScopeImage`) - 前端直接调用
- ✅ 图像编辑 - 已通过后端 `/api/image-edit/edit`
- ✅ 图像扩展 - 已通过后端 `/api/image/out-painting`

**存在的问题**：
- 前端直接调用 DashScope API 遇到 **CORS 限制**
- API Key 暴露在前端，存在安全风险
- 无法统一管理和监控 API 调用
- 无法实现后端缓存和优化

**目标架构**：
- 后端使用 `qwen_native.py` 调用 DashScope API
- 前端调用后端 API（而不是直接调用 DashScope）
- 逐步迁移，优先实现核心功能（聊天、模型列表）
- 保持前端代码改动最小化

**迁移策略**：
1. **阶段一**：实现后端聊天 API（使用 `qwen_native.py`）
2. **阶段二**：实现后端模型列表 API
3. **阶段三**：前端切换到后端 API
4. **阶段四**：移除前端的 DashScope 直接调用代码

## Glossary

- **DashScope**: 阿里云通义千问的 API 服务平台
- **qwen_native.py**: 后端通义千问原生 SDK 实现
- **NativeSDKBase**: 后端原生 SDK 基类
- **StreamUpdate**: 流式响应更新对象
- **ChatOptions**: 聊天选项配置

## Requirements

### Requirement 1: 后端聊天 API

**User Story:** 作为前端开发者，我希望后端提供聊天 API，以便通过后端调用 DashScope 聊天功能。

#### Acceptance Criteria

1. THE System SHALL 提供 `/api/chat/tongyi` 端点接收聊天请求
2. WHEN 前端发送聊天请求时，THE System SHALL 使用 `qwen_native.py` 调用 DashScope API
3. THE System SHALL 支持流式响应（SSE）
4. THE System SHALL 支持网页搜索功能（`enable_search`）
5. THE System SHALL 支持思考模式（`enable_thinking`）
6. THE System SHALL 支持插件功能（`code_interpreter`、`pdf_extracter`）
7. THE System SHALL 返回与前端 `StreamUpdate` 格式兼容的响应

### Requirement 2: 后端模型列表 API

**User Story:** 作为前端开发者，我希望后端提供模型列表 API，以便获取可用的通义千问模型。

#### Acceptance Criteria

1. THE System SHALL 提供 `/api/models/tongyi` 端点返回模型列表
2. THE System SHALL 使用 `qwen_native.py` 的 `get_available_models()` 方法
3. THE System SHALL 返回包含文本模型和图像模型的完整列表
4. THE System SHALL 返回与前端 `ModelConfig` 格式兼容的响应
5. THE System SHALL 支持缓存（TTL: 1 小时）

### Requirement 3: 请求参数映射

**User Story:** 作为开发者，我希望后端能够正确映射前端请求参数到 `qwen_native.py` 参数。

#### Acceptance Criteria

1. WHEN 前端发送 `messages` 参数时，THE System SHALL 映射到 `qwen_native.py` 的 `messages` 参数
2. WHEN 前端发送 `modelId` 参数时，THE System SHALL 映射到 `qwen_native.py` 的 `model` 参数
3. WHEN 前端发送 `options.enableSearch` 参数时，THE System SHALL 映射到 `qwen_native.py` 的 `enable_search` 参数
4. WHEN 前端发送 `options.enableThinking` 参数时，THE System SHALL 映射到 `qwen_native.py` 的 `enable_thinking` 参数
5. WHEN 前端发送 `options.temperature` 参数时，THE System SHALL 映射到 `qwen_native.py` 的 `temperature` 参数

### Requirement 4: 响应格式转换

**User Story:** 作为前端开发者，我希望后端返回的响应格式与前端期望的格式一致。

#### Acceptance Criteria

1. THE System SHALL 将 `qwen_native.py` 的响应转换为前端 `StreamUpdate` 格式
2. WHEN 流式响应包含 `reasoning_content` 时，THE System SHALL 设置 `chunk_type: "reasoning"`
3. WHEN 流式响应包含 `content` 时，THE System SHALL 设置 `chunk_type: "content"`
4. WHEN 流式响应结束时，THE System SHALL 设置 `chunk_type: "done"` 并包含 `usage` 信息
5. WHEN 响应包含搜索结果时，THE System SHALL 转换为 `groundingMetadata` 格式

### Requirement 5: 错误处理

**User Story:** 作为前端开发者，我希望后端能够正确处理错误并返回友好的错误信息。

#### Acceptance Criteria

1. WHEN DashScope API 返回错误时，THE System SHALL 捕获并转换为 HTTP 错误
2. WHEN API Key 无效时，THE System SHALL 返回 401 错误
3. WHEN 模型不存在时，THE System SHALL 返回 404 错误
4. WHEN 请求限流时，THE System SHALL 返回 429 错误
5. WHEN 网络错误时，THE System SHALL 返回 502 错误

### Requirement 6: API Key 管理

**User Story:** 作为系统管理员，我希望 API Key 在后端管理，以便提高安全性。

#### Acceptance Criteria

1. THE System SHALL 从数据库读取用户的 DashScope API Key
2. THE System SHALL 不在日志中记录 API Key
3. THE System SHALL 不在错误响应中暴露 API Key
4. THE System SHALL 支持多用户多 API Key 管理
5. THE System SHALL 验证 API Key 的有效性

### Requirement 7: 性能优化

**User Story:** 作为用户，我希望后端响应速度快，以便获得流畅体验。

#### Acceptance Criteria

1. THE System SHALL 使用异步 I/O 处理请求
2. THE System SHALL 使用连接池管理 DashScope 连接
3. THE System SHALL 缓存模型列表（TTL: 1 小时）
4. THE System SHALL 支持并发请求（最大 100 并发）
5. THE System SHALL 记录请求执行时间

### Requirement 8: 日志和监控

**User Story:** 作为系统管理员，我希望能够监控 DashScope API 调用，以便调试和分析。

#### Acceptance Criteria

1. THE System SHALL 记录每个请求的模型名称
2. THE System SHALL 记录请求方法（chat、models）
3. THE System SHALL 记录响应状态码
4. THE System SHALL 记录执行时间
5. THE System SHALL 记录 token 使用量（prompt_tokens、completion_tokens）

### Requirement 9: 前端兼容性

**User Story:** 作为前端开发者，我希望后端 API 与前端现有代码兼容，以便最小化前端改动。

#### Acceptance Criteria

1. THE System SHALL 提供与前端 `DashScopeProvider` 兼容的 API 接口
2. THE System SHALL 支持前端现有的所有参数（messages、options、attachments）
3. THE System SHALL 返回与前端 `StreamUpdate` 格式一致的响应
4. THE System SHALL 支持前端现有的错误处理逻辑
5. THE System SHALL 提供迁移指南文档

### Requirement 10: 渐进式迁移

**User Story:** 作为开发者，我希望能够渐进式迁移，以便降低风险。

#### Acceptance Criteria

1. THE System SHALL 支持前端同时使用后端 API 和直接调用 DashScope
2. THE System SHALL 提供功能开关（Feature Flag）控制迁移进度
3. THE System SHALL 提供回滚机制（如果后端 API 失败，回退到前端直接调用）
4. THE System SHALL 提供 A/B 测试支持（部分用户使用后端 API）
5. THE System SHALL 提供迁移进度监控（后端 API 使用率）
