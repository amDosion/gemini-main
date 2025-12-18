# Requirements Document

## Introduction

本功能旨在优化图片生成模式（`image-gen`、`image-edit`、`image-outpainting`）的用户体验。当前实现中，生成的图片必须等待云存储上传完成后才能显示给用户，导致 UI 阻塞 5-15 秒。本需求将实现"先显示、后上传"的非阻塞架构，让用户在 API 返回结果后立即看到生成的图片。

## Glossary

- **Gen 模式**：图片生成相关的应用模式，包括 `image-gen`（文生图）、`image-edit`（图片编辑）、`image-outpainting`（图片扩展）
- **云存储上传**：将生成的图片上传到云端存储服务（如 S3、OSS），获取持久化 URL
- **本地 URL**：浏览器端的临时 URL，包括 Base64 Data URL 和 Blob URL
- **云存储 URL**：以 `http://` 或 `https://` 开头的持久化 URL
- **displayAttachments**：用于前端 UI 显示的附件数组，使用本地 URL
- **dbAttachments**：用于数据库持久化的附件数组，使用云存储 URL
- **uploadToCloudStorageSync**：当前的同步上传函数，会阻塞调用方
- **uploadToCloudStorageAsync**：异步上传函数，不阻塞调用方

## Requirements

### Requirement 1

**User Story:** As a user, I want to see generated images immediately after the AI API returns, so that I don't have to wait for cloud upload to complete.

#### Acceptance Criteria

1. WHEN the AI API returns generated image results THEN the System SHALL display the images to the user within 500ms using local URLs
2. WHEN displaying generated images THEN the System SHALL use Base64 Data URL or Blob URL for immediate rendering
3. WHILE images are being uploaded to cloud storage THEN the System SHALL continue displaying the local URL version without interruption
4. WHEN cloud upload completes THEN the System SHALL update the database record with the cloud storage URL without affecting the displayed image

### Requirement 2

**User Story:** As a user, I want the loading state to end when images are ready to display, so that I know the generation is complete.

#### Acceptance Criteria

1. WHEN the AI API returns image results THEN the System SHALL set `loadingState` to `'idle'` immediately
2. WHEN the AI API returns image results THEN the System SHALL update the model message with displayable attachments immediately
3. IF cloud upload fails THEN the System SHALL log the error and mark the attachment with `uploadStatus: 'failed'`

### Requirement 3

**User Story:** As a developer, I want the upload process to run in the background, so that it doesn't block the main UI thread.

#### Acceptance Criteria

1. WHEN processing generated images THEN the System SHALL separate display logic from upload logic
2. WHEN initiating cloud upload THEN the System SHALL use fire-and-forget pattern without awaiting the result
3. WHEN multiple images are generated THEN the System SHALL upload all images concurrently in the background
4. WHEN the upload task is submitted THEN the System SHALL return control to the main flow immediately

### Requirement 4

**User Story:** As a user, I want my generated images to be persisted correctly, so that I can access them after refreshing the page.

#### Acceptance Criteria

1. WHEN cloud upload completes successfully THEN the System SHALL update the session messages in the database with cloud URLs
2. WHEN the page is refreshed THEN the System SHALL load images from cloud storage URLs
3. IF an image has `uploadStatus: 'pending'` and empty URL THEN the System SHALL filter it out from display
4. WHEN saving to database THEN the System SHALL use cloud storage URLs instead of local URLs

### Requirement 5

**User Story:** As a developer, I want a clean separation between display attachments and database attachments, so that the code is maintainable.

#### Acceptance Criteria

1. WHEN processing image generation results THEN the System SHALL create separate `displayAttachments` and `dbAttachments` arrays
2. WHEN updating UI state THEN the System SHALL use `displayAttachments` with local URLs
3. WHEN saving to database THEN the System SHALL use `dbAttachments` with cloud URLs
4. WHEN cloud upload completes THEN the System SHALL update only the database record without modifying UI state
