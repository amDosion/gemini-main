# Requirements Document

## Introduction

本文档定义了附件 URL 处理系统的需求，明确区分 `url` 和 `tempUrl` 字段的用途，以及不同来源附件的处理策略。系统需要正确处理三种 URL 类型（Base64、Blob、云 URL）和两种附件来源（手动上传、跨模式传递）。

## Glossary

- **url 字段**: 用于 UI 显示的 URL，可以是：
  - Base64 URL（用户上传后立即显示）
  - Blob URL（用户上传后立即显示）
  - 云 URL（当 `uploadStatus === 'completed'` 时，从后端 `upload_tasks.target_url` 获取）
- **tempUrl 字段**: 临时性的原始 URL，来源包括：
  - AI 返回的临时图片链接（如 DashScope 返回的临时 URL，会过期）
  - 跨模式传递时保存的原始 URL（用于 `findAttachmentByUrl` 查找匹配）
- **target_url (后端)**: 数据库 `upload_tasks` 表中的字段，存储上传到云存储后的永久 URL
- **Base64 URL**: 内嵌数据 URL，格式为 `data:image/png;base64,xxx`，可直接用于 UI 显示
- **Blob URL**: 浏览器本地 URL，格式为 `blob:xxx`，页面关闭后失效，仅用于 UI 显示
- **云 URL (Cloud URL)**: 上传到云存储后返回的永久 HTTP/HTTPS URL
- **手动上传附件 (Manual Upload)**: 用户通过文件选择器上传的附件，初始 `url` 为 Blob URL，`uploadStatus` 为 pending
- **跨模式附件 (Cross-Mode Transfer)**: 从其他模式（如 GEN）传递到当前模式（如 EDIT）的附件，保留原始 ID 和状态
- **CONTINUITY LOGIC**: 当用户没有上传新附件时，自动使用画布上的图片作为输入（这里可能是Blob URL，base64，也可能是云 URL）
- **uploadStatus**: 附件上传状态，可选值：pending（待上传）、uploading（上传中）、completed（已完成）、failed（失败）

## Requirements

### Requirement 1: URL 字段职责分离

**User Story:** As a developer, I want clear separation between url and tempUrl fields, so that I can correctly handle different URL types in different scenarios.

#### Acceptance Criteria

1. WHEN an attachment is created from user upload THEN the system SHALL store Blob URL in url field for immediate UI display
2. WHEN AI returns a generated image with temp URL THEN the system SHALL store AI temp URL in tempUrl field and create Blob URL for url field for display
3. WHEN rendering an image in UI THEN the system SHALL use url field for img src attribute
4. WHEN uploadStatus becomes completed THEN the system SHALL update url field with cloud URL from backend target_url
5. WHEN attachment is transferred cross-mode THEN the system SHALL preserve original url in tempUrl for findAttachmentByUrl matching
6. WHEN persisting to database THEN the system SHALL clear url if it is Blob or Base64 because they are ephemeral or too large


### Requirement 2: 附件来源识别与处理

**User Story:** As a developer, I want to identify the source of an attachment, so that I can apply the correct processing strategy.

#### Acceptance Criteria

1. WHEN a user uploads a file via file picker THEN the system SHALL create an attachment with url as Blob URL and uploadStatus as pending and file as File object
2. WHEN an attachment is transferred from another mode THEN the system SHALL preserve the original id and uploadStatus and tempUrl if available
3. WHEN processing attachments THEN the system SHALL log the source type with format 来源手动上传 or 来源跨模式传递
4. WHEN a cross-mode attachment has uploadStatus pending THEN the system SHALL query backend for cloud URL using attachment ID

### Requirement 3: URL 类型检测与转换

**User Story:** As a developer, I want to detect and convert URL types accurately, so that I can apply the correct processing strategy.

#### Acceptance Criteria

1. WHEN checking URL type THEN the system SHALL correctly identify Base64 URLs starting with data colon
2. WHEN checking URL type THEN the system SHALL correctly identify Blob URLs starting with blob colon
3. WHEN checking URL type THEN the system SHALL correctly identify HTTP URLs starting with http or https
4. WHEN converting Base64 URL to File THEN the system SHALL use fetch and blob methods
5. WHEN converting Blob URL to File THEN the system SHALL use fetch and blob methods
6. WHEN converting HTTP URL to File THEN the system SHALL use backend proxy api storage download to avoid CORS
7. WHEN logging URL information THEN the system SHALL include the URL type in format urlType Base64 or Blob or HTTP or Other

### Requirement 4: 跨模式传递处理流程

**User Story:** As a user, I want to edit an image generated in GEN mode, so that I can refine the result without re-uploading.

#### Acceptance Criteria

1. WHEN user clicks Edit on a generated image THEN the system SHALL create new attachment with same id as original and copy original url to tempUrl for matching lookup
2. WHEN the original attachment has uploadStatus completed THEN the system SHALL use the cloud URL from url field directly
3. WHEN the original attachment has uploadStatus pending THEN the system SHALL query backend API sessions attachments endpoint to get target_url and update url field with cloud URL
4. WHEN processing the attachment for API call THEN the system SHALL check uploadStatus first and if completed use url field cloud URL and if pending query backend for target_url


### Requirement 5: API 调用准备

**User Story:** As a developer, I want to prepare attachments correctly for API calls, so that the API receives the correct data format.

#### Acceptance Criteria

1. WHEN preparing attachment for Google API THEN the system SHALL convert to base64Data format and include MIME type in the data
2. WHEN preparing attachment for Tongyi API THEN the system SHALL use cloud URL directly from url field if uploadStatus is completed
3. WHEN uploadStatus is completed and url is HTTP URL THEN the system SHALL use url to obtain base64Data via backend proxy
4. WHEN uploadStatus is pending THEN the system SHALL query backend using attachment ID to get target_url first
5. WHEN backend query fails THEN the system SHALL fall back to using tempUrl or convert local Blob or Base64 to base64Data
6. WHEN all methods fail THEN the system SHALL throw error with descriptive message

### Requirement 6: 数据库持久化规则

**User Story:** As a developer, I want to persist attachments correctly, so that data integrity is maintained across sessions.

#### Acceptance Criteria

1. WHEN saving attachment to database THEN the system SHALL keep url if it is HTTP URL and clear url if it is Blob URL and clear url if it is Base64 URL
2. WHEN saving attachment to database THEN the system SHALL keep tempUrl if it is HTTP URL for cross-mode lookup and clear tempUrl if it is Base64 or Blob URL
3. WHEN saving attachment to database THEN the system SHALL remove file property because it cannot serialize and remove base64Data property because it is only for API calls
4. WHEN attachment has uploadStatus completed and HTTP url THEN the system SHALL preserve both fields

### Requirement 7: 日志记录规范

**User Story:** As a developer, I want detailed logs for debugging, so that I can trace the attachment processing flow.

#### Acceptance Criteria

1. WHEN processing an attachment THEN the system SHALL log attachment source and URL types and upload status
2. WHEN querying backend for cloud URL THEN the system SHALL log query reason and query result
3. WHEN preparing attachment for API THEN the system SHALL log processing strategy chosen and whether base64Data was obtained successfully
4. WHEN an error occurs THEN the system SHALL log error message with context and attachment ID and session ID truncated for privacy

### Requirement 8: CONTINUITY LOGIC 处理

**User Story:** As a user, I want to continue editing without re-uploading, so that my workflow is seamless.

#### Acceptance Criteria

1. WHEN user sends message without new attachments AND canvas has active image THEN the system SHALL use activeImageUrl as input source and search message history for matching attachment and prepare attachment using prepareAttachmentForApi function
2. WHEN searching for matching attachment THEN the system SHALL match by url field exact match and match by tempUrl field exact match and fall back to most recent image attachment if Blob URL does not match
3. WHEN matching attachment is found THEN the system SHALL reuse original attachment ID for backend lookup and query backend for cloud URL if uploadStatus is pending
4. WHEN no matching attachment is found THEN the system SHALL create new attachment from activeImageUrl and convert to base64Data for API call
