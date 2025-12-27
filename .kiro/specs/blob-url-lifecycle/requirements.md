# Requirements Document

## Introduction

本文档定义了聊天附件上传功能中 Blob URL 生命周期管理的需求。当前系统存在 Blob URL 过早释放的问题，导致图片在消息历史中显示为 `ERR_FILE_NOT_FOUND`。

## Glossary

- **Blob URL**: 通过 `URL.createObjectURL()` 创建的临时对象 URL，格式为 `blob:http://...`
- **Attachment**: 附件对象，包含文件、URL、上传状态等信息
- **InputArea**: 输入区域组件，负责附件的添加和预览
- **AttachmentGrid**: 附件网格组件，负责在消息中显示附件
- **useChat**: 聊天钩子，负责消息的发送和状态管理

## Requirements

### Requirement 1: Blob URL 生命周期管理

**User Story:** 作为用户，我希望在消息发送后仍能看到附件图片，以便回顾聊天历史。

#### Acceptance Criteria

1. WHEN 用户上传附件时，THE System SHALL 创建 Blob URL 并存储在 `tempUrl` 字段
2. WHEN 用户发送消息时，THE System SHALL 保留 Blob URL 直到文件上传完成
3. WHEN 文件上传完成后，THE System SHALL 用云存储 URL 替换 Blob URL
4. WHEN 组件卸载时，THE System SHALL 释放所有未使用的 Blob URL
5. WHEN 附件被移除时，THE System SHALL 立即释放对应的 Blob URL

### Requirement 2: 附件状态追踪

**User Story:** 作为开发者，我需要清晰的附件状态追踪，以便正确管理 Blob URL 生命周期。

#### Acceptance Criteria

1. THE Attachment SHALL 包含 `uploadStatus` 字段，值为 `pending | uploading | uploaded | failed`
2. WHEN 附件创建时，THE System SHALL 设置状态为 `pending`
3. WHEN 开始上传时，THE System SHALL 更新状态为 `uploading`
4. WHEN 上传成功时，THE System SHALL 更新状态为 `uploaded` 并设置云存储 URL
5. WHEN 上传失败时，THE System SHALL 更新状态为 `failed` 并保留 Blob URL

### Requirement 3: 消息附件 URL 更新

**User Story:** 作为用户，我希望消息中的附件能自动从临时 URL 切换到永久 URL，无需刷新页面。

#### Acceptance Criteria

1. WHEN 文件上传完成时，THE System SHALL 更新消息中的附件 URL
2. WHEN 更新 URL 时，THE System SHALL 释放旧的 Blob URL
3. WHEN 显示消息时，THE System SHALL 优先使用云存储 URL，其次使用 Blob URL
4. WHEN Blob URL 已失效时，THE System SHALL 显示占位符或错误提示

### Requirement 4: 错误处理

**User Story:** 作为用户，我希望在上传失败时能看到清晰的错误提示，并能重试上传。

#### Acceptance Criteria

1. WHEN 上传失败时，THE System SHALL 显示错误消息
2. WHEN 上传失败时，THE System SHALL 保留 Blob URL 以便用户查看原图
3. IF 上传超时，THEN THE System SHALL 标记为失败并允许重试
4. WHEN 网络错误时，THE System SHALL 提供重试选项

### Requirement 5: 内存泄漏防护

**User Story:** 作为系统管理员，我需要确保 Blob URL 不会导致内存泄漏。

#### Acceptance Criteria

1. THE System SHALL 在组件卸载时释放所有 Blob URL
2. THE System SHALL 在附件移除时立即释放 Blob URL
3. THE System SHALL 在 URL 替换时释放旧的 Blob URL
4. THE System SHALL 使用 WeakMap 或引用计数追踪 Blob URL 使用情况
5. WHEN 会话切换时，THE System SHALL 清理未使用的 Blob URL
