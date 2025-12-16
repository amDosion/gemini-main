# Requirements Document

## Introduction

本文档定义了聊天数据库存储结构的规范化重构需求。当前系统将会话中的所有消息以 JSON 数组形式存储在 `chat_sessions` 表的单个字段中，导致数据无限膨胀、查询效率低下、存储配额溢出等问题。本次重构旨在将消息和附件拆分为独立的关系型表，实现数据规范化存储。

## Glossary

- **User（用户）**: 系统的注册用户，拥有独立的数据空间
- **ChatSession（聊天会话）**: 用户与 AI 的一次完整对话上下文，包含标题、模式、角色等元数据
- **Message（消息）**: 会话中的单条对话记录，包含角色、内容、时间戳等
- **Attachment（附件）**: 消息中关联的文件，如图片、PDF 等
- **JSON 字段**: 数据库中以 JSON 格式存储的非结构化数据列
- **规范化（Normalization）**: 将嵌套的 JSON 数据拆分为独立的关系型表
- **外键（Foreign Key）**: 表之间的关联字段，用于建立一对多关系
- **user_id**: 用户唯一标识符，用于数据隔离和多用户支持

## Requirements

### Requirement 1

**User Story:** 作为开发者，我希望消息数据存储在独立的表中，以便系统能够高效地增删改查单条消息而无需加载整个会话。

#### Acceptance Criteria

1. WHEN 系统存储新消息 THEN Message_Table SHALL 创建一条独立记录并通过 `session_id` 外键关联到对应会话
2. WHEN 系统查询会话消息 THEN Message_Table SHALL 支持按 `session_id` 和 `timestamp` 进行索引查询
3. WHEN 系统删除单条消息 THEN Message_Table SHALL 仅删除该条记录而不影响同会话的其他消息
4. WHEN 系统更新消息内容 THEN Message_Table SHALL 仅更新该条记录而无需重写整个会话数据

### Requirement 2

**User Story:** 作为开发者，我希望附件数据存储在独立的表中，以便大型文件元数据不会嵌入消息 JSON 导致数据膨胀。

#### Acceptance Criteria

1. WHEN 系统存储新附件 THEN Attachment_Table SHALL 创建一条独立记录并通过 `message_id` 外键关联到对应消息
2. WHEN 系统查询消息附件 THEN Attachment_Table SHALL 支持按 `message_id` 进行索引查询
3. WHEN 系统删除消息 THEN Attachment_Table SHALL 级联删除该消息关联的所有附件记录
4. WHEN 系统更新附件状态 THEN Attachment_Table SHALL 仅更新该条附件记录

### Requirement 3

**User Story:** 作为开发者，我希望会话表仅存储元数据，以便会话列表加载速度不受消息数量影响。

#### Acceptance Criteria

1. WHEN 系统查询会话列表 THEN ChatSession_Table SHALL 仅返回会话元数据（id、title、mode、createdAt）而不包含消息内容
2. WHEN 系统创建新会话 THEN ChatSession_Table SHALL 不包含 `messages` JSON 字段
3. WHEN 系统删除会话 THEN ChatSession_Table SHALL 级联删除该会话关联的所有消息和附件

### Requirement 4

**User Story:** 作为开发者，我希望数据库支持分页加载消息，以便长对话不会一次性加载全部历史记录。

#### Acceptance Criteria

1. WHEN 系统请求会话消息 THEN Message_Table SHALL 支持 `LIMIT` 和 `OFFSET` 分页参数
2. WHEN 系统请求最新消息 THEN Message_Table SHALL 支持按 `timestamp` 降序排列并限制返回数量
3. WHEN 系统请求消息总数 THEN Message_Table SHALL 支持按 `session_id` 统计消息数量

### Requirement 5

**User Story:** 作为开发者，我希望前端 API 接口保持向后兼容，以便现有前端代码无需大规模修改。

#### Acceptance Criteria

1. WHEN 前端调用 `GET /api/sessions` THEN API SHALL 返回与当前格式兼容的会话列表（包含聚合的消息数据）
2. WHEN 前端调用 `POST /api/sessions` THEN API SHALL 接受当前格式的会话数据并拆分存储到规范化表中
3. WHEN 前端调用 `GET /api/sessions/{id}` THEN API SHALL 返回完整会话数据（包含从 Message_Table 聚合的消息列表）

### Requirement 6

**User Story:** 作为开发者，我希望系统提供数据迁移工具，以便将现有 JSON 格式数据迁移到规范化表结构。

#### Acceptance Criteria

1. WHEN 管理员执行迁移脚本 THEN Migration_Tool SHALL 读取现有 `chat_sessions.messages` JSON 数据并拆分插入到 Message_Table
2. WHEN 迁移过程中发生错误 THEN Migration_Tool SHALL 回滚事务并报告失败的会话 ID
3. WHEN 迁移完成 THEN Migration_Tool SHALL 输出迁移统计（会话数、消息数、附件数）

### Requirement 7

**User Story:** 作为开发者，我希望 LocalStorage 模式也采用类似的数据结构，以便前端在离线模式下保持一致的数据访问模式。

#### Acceptance Criteria

1. WHEN 前端使用 LocalStorage 模式 THEN LocalStorageDB SHALL 将消息存储在独立的 `flux_messages` 键中
2. WHEN 前端查询会话消息 THEN LocalStorageDB SHALL 按 `sessionId` 过滤消息列表
3. WHEN 前端保存新消息 THEN LocalStorageDB SHALL 仅追加新消息而非重写整个会话

### Requirement 8

**User Story:** 作为开发者，我希望外键关系得到正确管理，以便数据完整性在增删改操作中得到保障。

#### Acceptance Criteria

1. WHEN 系统创建消息记录 THEN Message_Table SHALL 验证 `session_id` 对应的会话存在
2. WHEN 系统创建附件记录 THEN Attachment_Table SHALL 验证 `message_id` 对应的消息存在
3. WHEN 系统删除会话 THEN Database SHALL 通过级联删除（CASCADE）自动删除关联的消息和附件
4. WHEN 系统删除消息 THEN Database SHALL 通过级联删除（CASCADE）自动删除关联的附件
5. IF 外键约束验证失败 THEN Database SHALL 拒绝该操作并返回明确的错误信息

### Requirement 9

**User Story:** 作为用户，我希望加载历史消息时保持完整的对话上下文，以便 AI 能够理解之前的对话内容并给出连贯的回复。

#### Acceptance Criteria

1. WHEN 系统加载会话历史 THEN Message_Table SHALL 按 `timestamp` 升序返回消息以保持对话顺序
2. WHEN 系统加载消息 THEN Message_Table SHALL 同时加载每条消息关联的所有附件数据
3. WHEN 系统发送 AI 请求 THEN API SHALL 将历史消息按正确顺序组装为上下文数组
4. WHEN 系统分页加载消息 THEN API SHALL 支持指定起始时间戳以加载特定范围的历史消息
5. WHEN 系统加载最近 N 条消息 THEN API SHALL 返回按时间排序的完整消息（包含附件）以供 AI 上下文使用

### Requirement 10

**User Story:** 作为系统管理员，我希望所有数据表都包含 `user_id` 字段，以便支持多用户数据隔离和未来的用户认证系统。

#### Acceptance Criteria

1. WHEN 系统创建用户表 THEN User_Table SHALL 包含 `id`（自增主键）、`user_id`（UUID 业务标识）、`email`、`name`、`password_hash`、`created_at` 字段
2. WHEN 系统创建会话记录 THEN ChatSession_Table SHALL 包含 `user_id` 字段并建立外键关联到 User_Table 的 `user_id` 字段
3. WHEN 系统查询会话列表 THEN API SHALL 按当前登录用户的 `user_id` 过滤返回结果
4. WHEN 系统创建消息记录 THEN Message_Table SHALL 通过会话的 `user_id` 间接关联到用户
5. WHEN 用户未登录 THEN System SHALL 使用默认用户 ID（如 `default`）以保持向后兼容
6. WHEN 系统生成新用户 THEN User_Table SHALL 自动生成唯一的 `user_id`（UUID 格式）作为业务标识

### Requirement 11

**User Story:** 作为开发者，我希望用户认证系统支持基本的登录功能，以便替换当前的模拟登录逻辑。

#### Acceptance Criteria

1. WHEN 用户提交登录表单 THEN Auth_API SHALL 验证邮箱和密码并返回用户信息
2. WHEN 登录验证成功 THEN Auth_API SHALL 返回用户 ID 和基本信息供前端存储
3. WHEN 登录验证失败 THEN Auth_API SHALL 返回明确的错误信息（无效凭证）
4. WHEN 系统初始化 THEN Migration_Tool SHALL 创建默认管理员用户以支持首次登录

