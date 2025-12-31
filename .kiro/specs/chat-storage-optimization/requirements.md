# Requirements Document

## Introduction

本需求文档定义了聊天会话存储结构的优化方案。当前系统将所有消息以 JSON 数组形式存储在 `chat_sessions` 表的 `messages` 字段中，随着对话增长会导致 JSON 无限膨胀，影响性能。

本次优化采用以下核心策略：
1. **纯文本字段** - 消息内容使用独立字段存储，避免 JSON 解析开销
2. **链式关联** - 通过 `parent_id` 建立消息间的父子关系，支持对话分支
3. **按月分表** - 消息和附件按月份存储在不同表中，历史数据自动隔离
4. **前端零改动** - 后端 API 返回格式保持不变

## Glossary

- **ChatSession**: 聊天会话主表，存储会话元数据（标题、创建时间等）
- **ChatMessage**: 消息表，按月分表存储（如 `chat_messages_202501`）
- **MessageAttachment**: 附件表，按月分表存储（如 `message_attachments_202501`）
- **parent_id**: 消息的父消息 ID，用于建立链式关联和对话分支
- **分表策略**: 根据消息创建时间戳，将数据存储到对应月份的表中
- **对话分支**: 从某条历史消息创建新的对话路径，形成对话树结构

## Requirements

### Requirement 1: 前端 API 接口兼容性

**User Story:** As a 前端开发者, I want 后端 API 返回格式保持不变, so that 前端代码无需任何修改。

#### Acceptance Criteria

1. WHEN 前端调用 `GET /api/sessions` THEN THE System SHALL 返回与当前完全相同的 JSON 结构
2. WHEN 前端调用 `POST /api/sessions` THEN THE System SHALL 接受与当前完全相同的请求体格式
3. WHEN 前端调用 `DELETE /api/sessions/{id}` THEN THE System SHALL 正常删除会话及关联数据
4. WHEN 前端调用 `GET /api/sessions/{id}/attachments/{att_id}` THEN THE System SHALL 返回与当前完全相同的附件信息
5. THE System SHALL 保持 `ChatSession.to_dict()` 返回格式不变，包含完整的 `messages` 数组

### Requirement 2: 消息链式关联设计

**User Story:** As a 系统架构师, I want 消息通过 parent_id 建立链式关联, so that 可以追溯对话历史并支持对话分支。

#### Acceptance Criteria

1. THE ChatMessage 表 SHALL 包含 `parent_id` 字段，指向上一条消息的 ID
2. WHEN 用户发送第一条消息 THEN THE System SHALL 设置 `parent_id` 为 NULL
3. WHEN AI 回复用户消息 THEN THE System SHALL 设置 `parent_id` 为用户消息的 ID
4. WHEN 用户基于 AI 回复继续对话 THEN THE System SHALL 设置 `parent_id` 为 AI 回复的 ID
5. WHEN 用户从历史消息创建分支 THEN THE System SHALL 设置 `parent_id` 为该历史消息的 ID
6. THE System SHALL 支持通过 `parent_id` 向上追溯完整对话链
7. THE System SHALL 支持查询某消息的所有子消息（分支）

### Requirement 3: 消息表纯文本字段设计

**User Story:** As a 数据库管理员, I want 消息使用纯文本字段存储, so that 避免 JSON 解析开销，提升查询性能。

#### Acceptance Criteria

1. THE ChatMessage 表 SHALL 使用 `TEXT` 类型存储消息内容，不使用 JSON
2. THE ChatMessage 表 SHALL 包含以下字段：`id`、`session_id`、`parent_id`、`role`、`content`、`timestamp`、`mode`、`is_error`、`has_attachments`、`metadata`
3. THE System SHALL 在 `session_id`、`parent_id` 和 `mode` 字段上创建索引
4. THE System SHALL 使用布尔字段 `has_attachments` 标记是否有附件，避免不必要的 JOIN
5. THE `mode` 字段 SHALL 记录每条消息所属的模式（chat、image-gen、video-gen 等）
6. THE `metadata` 字段 SHALL 使用 JSON 存储模式特定的配置和扩展数据（如 groundingMetadata、toolCalls 等）

### Requirement 4: 消息表按月分表

**User Story:** As a 数据库管理员, I want 消息数据按月存储在不同表中, so that 历史数据自动隔离，查询性能优化。

#### Acceptance Criteria

1. THE System SHALL 根据消息时间戳自动选择对应月份的表（如 `chat_messages_202501`）
2. WHEN 插入新消息 THEN THE System SHALL 自动创建目标月份的表（如果不存在）
3. WHEN 查询消息 THEN THE System SHALL 支持跨月份查询并正确合并结果
4. THE System SHALL 提供表名生成函数：`get_message_table_name(timestamp) -> "chat_messages_YYYYMM"`

### Requirement 5: 附件表独立存储

**User Story:** As a 系统架构师, I want 附件数据与消息分离存储, so that 消息表保持轻量，附件可独立管理。

#### Acceptance Criteria

1. THE System SHALL 将附件数据存储在独立的 `message_attachments_YYYYMM` 表中
2. THE MessageAttachment 表 SHALL 包含以下纯文本字段：`id`、`message_id`、`type`、`url`、`filename`、`mime_type`、`size`、`upload_status`
3. WHEN 消息包含附件 THEN THE System SHALL 设置消息的 `has_attachments` 为 True
4. WHEN 查询消息附件 THEN THE System SHALL 从对应月份的附件表中获取
5. THE System SHALL 在 `message_id` 字段上创建索引

### Requirement 6: 数据迁移

**User Story:** As a 系统管理员, I want 现有数据平滑迁移到新结构, so that 用户历史对话不丢失。

#### Acceptance Criteria

1. THE System SHALL 提供数据迁移脚本，将现有 `chat_sessions.messages` JSON 拆分到新表
2. WHEN 迁移消息 THEN THE System SHALL 根据消息顺序自动建立 `parent_id` 链式关联
3. WHEN 迁移完成 THEN THE System SHALL 验证数据完整性（消息数量、附件数量一致）
4. THE 迁移脚本 SHALL 支持增量迁移，可多次执行不重复迁移
5. IF 迁移过程中发生错误 THEN THE System SHALL 回滚当前会话的迁移并记录错误日志

### Requirement 7: 对话链查询

**User Story:** As a 用户, I want 快速加载对话历史, so that 我可以查看完整的对话上下文。

#### Acceptance Criteria

1. WHEN 加载会话 THEN THE System SHALL 通过 `parent_id` 链式追溯获取主线对话
2. WHEN 会话存在分支 THEN THE System SHALL 默认返回最新分支的对话链
3. THE System SHALL 支持获取某消息的所有子消息（用于展示分支选项）
4. THE System SHALL 支持构建完整的对话树结构（用于高级分支管理）
5. WHEN 查询跨月对话 THEN THE System SHALL 自动合并多个月份表的数据

### Requirement 8: 数据一致性

**User Story:** As a 系统架构师, I want 多表数据保持一致, so that 不会出现孤立数据或数据丢失。

#### Acceptance Criteria

1. WHEN 删除会话 THEN THE System SHALL 级联删除所有关联的消息和附件
2. WHEN 删除消息 THEN THE System SHALL 级联删除关联的附件
3. WHEN 删除消息 THEN THE System SHALL 处理子消息的 `parent_id`（设为 NULL 或级联删除）
4. THE System SHALL 使用数据库事务确保多表操作的原子性
5. IF 写入消息失败 THEN THE System SHALL 回滚整个操作，不留下部分数据

### Requirement 9: 对话分支支持（预留）

**User Story:** As a 用户, I want 从历史消息创建对话分支, so that 我可以探索不同的对话方向。

#### Acceptance Criteria

1. THE System SHALL 支持从任意历史消息创建新的对话分支
2. WHEN 创建分支 THEN THE System SHALL 设置新消息的 `parent_id` 为分支起点消息的 ID
3. THE System SHALL 支持查询会话的所有分支点（有多个子消息的消息）
4. THE System SHALL 支持切换当前活动分支
5. THE System SHALL 在 ChatSession 表中记录当前活动分支的最新消息 ID（可选）

### Requirement 10: 多模式消息隔离

**User Story:** As a 用户, I want 同一会话中不同模式的消息相互独立, so that 每个模式有自己独立的对话上下文。

#### Acceptance Criteria

1. THE ChatMessage 表 SHALL 为每条消息独立记录 `mode` 字段
2. WHEN 用户在某模式下发送第一条消息 THEN THE System SHALL 设置 `parent_id` 为 NULL（该模式的根消息）
3. WHEN 用户在某模式下继续对话 THEN THE System SHALL 设置 `parent_id` 为该模式下的上一条消息 ID
4. THE System SHALL 支持以下模式：`chat`、`image-gen`、`image-edit`、`video-gen`、`audio-gen`、`image-outpainting`、`pdf-extract`、`virtual-try-on`、`deep-research`
5. WHEN 加载会话历史 THEN THE System SHALL 按模式分组返回消息，每个模式有独立的对话链
6. THE `metadata` 字段 SHALL 存储模式特定的配置参数（如图片生成的尺寸、风格等）
7. WHEN 前端请求某模式的历史 THEN THE System SHALL 只返回该模式的消息链
8. THE System SHALL 为每个模式维护独立的 `latest_message_id`（可选，用于快速定位）
