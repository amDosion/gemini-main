# Implementation Plan: Chat Storage Optimization v3

## Overview

本实施计划基于 `design_v3.md` 设计文档，采用**按模式分表 + 消息索引表**架构，实现聊天存储优化。采用**直接迁移**方案（无双写期），分为准备、停机迁移、上线三个阶段。

## Tasks

- [ ] 1. 数据库模型层实现
  - [ ] 1.1 创建 `MessageIndex` 模型类
    - 定义 `message_index` 表的 SQLAlchemy 模型
    - 字段：`id`, `session_id`, `mode`, `table_name`, `seq`, `timestamp`, `parent_id`
    - 添加 `to_dict()` 方法
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 1.2 创建 `MessagesChat` 模型类
    - 定义 `messages_chat` 表的 SQLAlchemy 模型
    - 字段：`id`, `session_id`, `role`, `content`, `timestamp`, `is_error`, `metadata_json`
    - 添加 `to_dict()` 方法，兼容前端 `Message` 结构
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 1.3 创建 `MessagesImageGen` 模型类
    - 定义 `messages_image_gen` 表的 SQLAlchemy 模型
    - 包含图像生成特定字段：`image_size`, `image_style`, `image_quality`, `image_count`, `model_name`
    - ⚠️ **注意**：必须包含 `metadata_json TEXT` 字段，用于存储扩展元数据
    - _Requirements: 3.1, 10.1, 10.6_

  - [ ] 1.4 创建 `MessagesVideoGen` 模型类
    - 定义 `messages_video_gen` 表的 SQLAlchemy 模型
    - 包含视频生成特定字段：`video_duration`, `video_resolution`, `video_fps`, `model_name`
    - ⚠️ **注意**：必须包含 `metadata_json TEXT` 字段，用于存储扩展元数据
    - _Requirements: 3.1, 10.1, 10.6_

  - [ ] 1.5 创建 `MessagesGeneric` 模型类
    - 定义 `messages_generic` 兜底表的 SQLAlchemy 模型
    - 使用 `metadata_json` 存储模式特定数据
    - _Requirements: 3.1, 3.6, 10.4_

  - [ ] 1.6 创建 `MessageAttachment` 模型类
    - 定义 `message_attachments` 表的 SQLAlchemy 模型
    - 字段：`id`, `session_id`, `message_id`, `mime_type`, `name`, `url`, `temp_url`, `upload_status`, `upload_task_id`, `upload_error`, `google_file_uri`, `google_file_expiry`, `size`, **`file_uri`**
    - 添加 `to_dict()` 方法
    - ⚠️ **注意**：`file_uri` 字段用于存储通用文件 URI（如 Google File API 返回的 URI），与 `google_file_uri` 区分
    - _Requirements: 5.1, 5.2, 5.5_

  - [ ] 1.7 修改 `ChatSession` 模型
    - 移除 `messages` JSON 字段
    - 保留 `id`, `title`, `persona_id`, `mode`, `created_at` 字段
    - _Requirements: 1.5_

- [ ] 2. 核心工具函数实现
  - [ ] 2.1 实现模式映射函数 `get_table_name_for_mode()`
    - 映射 `chat` → `messages_chat`
    - 映射 `image-gen` → `messages_image_gen`
    - 映射 `video-gen` → `messages_video_gen`
    - 其他模式 → `messages_generic`（兜底）
    - _Requirements: 10.4_

  - [ ] 2.2 实现表类获取函数 `get_message_table_class_by_name()`
    - 根据 `table_name` 返回对应的 SQLAlchemy 模型类
    - _Requirements: 10.4_

  - [ ] 2.3 实现元数据提取函数 `extract_metadata()`
    - 从前端消息对象提取 `groundingMetadata`, `urlContextMetadata`, `toolCalls`, `toolResults` 等
    - 返回 JSON 字符串
    - _Requirements: 3.6_

- [ ] 3. Checkpoint - 模型层验证
  - 确保所有模型类可正常导入
  - 确保表结构与设计文档一致
  - 如有问题请询问用户

- [ ] 4. API 路由层重写
  - [ ] 4.1 重写 `GET /api/sessions` 查询逻辑
    - 从 `message_index` 查询会话消息索引，按 `seq ASC` 排序
    - 按 `table_name` 分组批量查询各模式表（避免 N+1）
    - 批量查询 `message_attachments`（避免 N+1）
    - 按 `seq` 顺序组装 `messages` 数组
    - ⚠️ **注意**：组装消息时必须从 `message_index` 获取 `mode` 字段并赋值到 `msg_dict['mode']`
    - 返回与当前完全相同的 JSON 结构
    - _Requirements: 1.1, 1.5, 7.1, 7.5_

  - [ ] 4.2 重写 `POST /api/sessions` 保存逻辑
    - 实现收敛删除机制：计算 `existing_ids - posted_ids`
    - ⚠️ **注意**：收敛删除时必须**先查询**关联的 `UploadTask`，**再删除**消息/附件/索引，否则无法取消孤儿任务
    - 批量删除前端已移除的消息（含附件、索引）
    - 取消关联的 `UploadTask`（避免孤儿记录）
    - 使用内存字典 `mode_last_msg` 构建 `parent_id`（关键修正）
    - 增量 upsert 消息到对应模式表
    - 增量 upsert 附件到 `message_attachments`
    - 实现云 URL 保护逻辑（优先级：UploadTask > 旧附件 > 前端）
    - _Requirements: 1.2, 2.2, 2.3, 2.4, 8.4, 8.5_

  - [ ] 4.3 重写 `DELETE /api/sessions/{id}` 删除逻辑
    - 级联删除会话关联的所有消息索引
    - 级联删除各模式表中的消息
    - 级联删除附件
    - _Requirements: 1.3, 8.1, 8.2_

  - [ ] 4.4 重写 `GET /api/sessions/{id}/attachments/{att_id}` 查询逻辑
    - 直接从 `message_attachments` 表查询
    - 联查 `UploadTask` 获取最新云 URL
    - _Requirements: 1.4_

- [ ] 5. Checkpoint - API 层验证
  - 确保 API 返回格式与当前完全一致
  - 确保收敛删除机制正常工作
  - 如有问题请询问用户

- [ ] 6. Worker 层简化
  - [ ] 6.1 简化 `upload_worker_pool.py` 附件 URL 更新逻辑
    - 移除旧的 JSON 深拷贝 + 遍历逻辑
    - 直接更新 `message_attachments` 表
    - 代码行数从 50+ 行简化到 5 行
    - _Requirements: 5.4_

- [ ] 7. 数据迁移脚本
  - [ ] 7.1 创建迁移脚本 `run_chat_storage_migration_v3.py`
    - 遍历所有 `chat_sessions`
    - 解析旧 `messages` JSON 字段
    - 使用内存字典 `mode_last_msg` 构建 `parent_id` 链
    - 按模式分发消息到对应表
    - 迁移附件到 `message_attachments`
    - 支持断点续传（记录已迁移会话 ID）
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ] 7.2 创建数据验证脚本 `verify_migration_v3.py`
    - 对比迁移前后消息数量
    - 对比迁移前后附件数量
    - 验证 `parent_id` 链式完整性
    - 输出验证报告
    - _Requirements: 6.3_

- [ ] 8. Checkpoint - 迁移脚本验证
  - 在测试环境执行迁移脚本
  - 执行验证脚本确认数据完整性
  - 如有问题请询问用户

- [ ] 9. DDL 迁移文件
  - [ ] 9.1 创建 SQL 迁移文件 `migrations/xxx_v3_tables.sql`
    - 创建 `message_index` 表及索引
    - 创建 `messages_chat` 表及索引
    - 创建 `messages_image_gen` 表及索引
    - 创建 `messages_video_gen` 表及索引
    - 创建 `messages_generic` 表及索引
    - 创建 `message_attachments` 表及索引
    - _Requirements: 3.3, 5.5_

  - [ ] 9.2 创建清理 SQL `migrations/xxx_drop_messages_column.sql`
    - 删除 `chat_sessions.messages` 字段
    - ⚠️ **SQLite 兼容性**：`DROP COLUMN` 仅 SQLite 3.35.0+ 支持
    - 若 SQLite 版本 < 3.35.0，需使用"创建新表 → 复制数据 → 删除旧表 → 重命名"的替代方案
    - 迁移脚本应自动检测 SQLite 版本并选择合适策略
    - _Requirements: 6.1_

- [ ] 10. Final Checkpoint - 全流程验证
  - 确保所有测试通过
  - 确保 API 兼容性
  - 确保迁移脚本可正常执行
  - 如有问题请询问用户

## Notes

- 任务按依赖顺序排列，建议按顺序执行
- 每个 Checkpoint 是验证点，确保前序任务正确后再继续
- 本方案采用**直接迁移**，无双写期，需要短暂停机
- 迁移前必须完整备份数据库
- `parent_id` 必须在内存中构建，禁止在 upsert 循环中查询数据库

## 关键修正记录（来自 design_v3_review.md）

| 序号 | 问题 | 修正 | 影响任务 |
|------|------|------|----------|
| 1 | `message_attachments` 缺少 `file_uri` 字段 | 已添加 `file_uri TEXT` | 1.6, 9.1 |
| 2 | 专表缺少 `metadata_json` 列 | `messages_image_gen`/`messages_video_gen` 已添加 | 1.3, 1.4, 9.1 |
| 3 | 消息组装时缺少 `mode` 字段 | 从 `message_index.mode` 获取并赋值 | 4.1 |
| 4 | 收敛删除取消 UploadTask 顺序 bug | 先查询 UploadTask，再删除消息 | 4.2 |
| 5 | SQLite `DROP COLUMN` 兼容性 | 添加版本检测和替代方案 | 9.2 |
| 6 | "前端级联删除"描述不准确 | 改为"成对删除"机制 | 4.2 |
