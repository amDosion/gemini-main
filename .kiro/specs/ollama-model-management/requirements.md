# Requirements Document

## Introduction

本需求文档定义了 Ollama 模型管理功能的需求规格。当用户在设置界面选择 Ollama 作为 Provider Template 时，系统应支持远程下载模型、查看本地模型列表、删除模型等管理功能。

## Glossary

- **Ollama**: 本地运行的大语言模型服务
- **Model_Manager**: 模型管理组件，负责模型的下载、删除、列表展示
- **Pull_Progress**: 模型下载进度信息
- **EditorTab**: 配置编辑器标签页组件
- **Native_API**: Ollama 原生 API（`/api/*` 端点）

## Requirements

### Requirement 1: 模型列表展示

**User Story:** As a user, I want to see all locally available Ollama models, so that I can know which models are ready to use.

#### Acceptance Criteria

1. WHEN the user selects Ollama as Provider Template, THE Model_Manager SHALL display a list of locally available models
2. WHEN the model list is loading, THE Model_Manager SHALL show a loading indicator
3. WHEN no models are available locally, THE Model_Manager SHALL display an empty state message with guidance
4. THE Model_Manager SHALL display model name, size, and modification time for each model

### Requirement 2: 模型下载功能

**User Story:** As a user, I want to download new models from Ollama registry, so that I can use different models for my tasks.

#### Acceptance Criteria

1. WHEN the user enters a model name and clicks download, THE Model_Manager SHALL initiate a pull request to Ollama API
2. WHILE a model is downloading, THE Model_Manager SHALL display real-time download progress (percentage, downloaded size, total size)
3. WHEN the download completes successfully, THE Model_Manager SHALL refresh the model list and show success notification
4. IF the download fails, THEN THE Model_Manager SHALL display an error message with the failure reason
5. WHEN a download is in progress, THE Model_Manager SHALL allow the user to cancel the download

### Requirement 3: 模型删除功能

**User Story:** As a user, I want to delete models I no longer need, so that I can free up disk space.

#### Acceptance Criteria

1. WHEN the user clicks delete on a model, THE Model_Manager SHALL show a confirmation dialog
2. WHEN the user confirms deletion, THE Model_Manager SHALL send a delete request to Ollama API
3. WHEN deletion succeeds, THE Model_Manager SHALL remove the model from the list and show success notification
4. IF deletion fails, THEN THE Model_Manager SHALL display an error message

### Requirement 4: 模型详情查看

**User Story:** As a user, I want to view detailed information about a model, so that I can understand its capabilities and configuration.

#### Acceptance Criteria

1. WHEN the user clicks on a model, THE Model_Manager SHALL display model details (family, parameter count, quantization level, capabilities)
2. THE Model_Manager SHALL show whether the model supports vision, tools, or thinking capabilities

### Requirement 5: UI 集成

**User Story:** As a user, I want the model management UI to be integrated into the settings panel, so that I can manage models without leaving the configuration interface.

#### Acceptance Criteria

1. WHEN Provider Template is Ollama, THE EditorTab SHALL display a "Model Management" section
2. WHEN Provider Template is not Ollama, THE EditorTab SHALL NOT display the model management section
3. THE Model_Manager SHALL be visually consistent with the existing EditorTab design

### Requirement 6: 后端 API 支持

**User Story:** As a frontend developer, I want backend API endpoints for model management, so that the frontend can communicate with Ollama service.

#### Acceptance Criteria

1. THE Backend SHALL expose an endpoint to list local Ollama models
2. THE Backend SHALL expose an endpoint to pull/download a model with streaming progress
3. THE Backend SHALL expose an endpoint to delete a model
4. THE Backend SHALL expose an endpoint to get model details
5. WHEN Ollama service is not available, THE Backend SHALL return appropriate error responses
