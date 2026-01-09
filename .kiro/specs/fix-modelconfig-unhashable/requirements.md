# Requirements Document

## Introduction

修复 EditorTab 编辑现有配置时无法显示已保存模型列表的问题，并修复后端 `qwen_native.py` 中的 `ModelConfig` 不可哈希错误。

## Glossary

- **ConfigProfile**: 配置文件，包含 Provider 信息、API Key、模型列表等
- **ModelConfig**: 模型配置对象，包含 id、name、description、capabilities 等字段
- **savedModels**: 数据库中保存的完整 `ModelConfig[]` 数组
- **verifiedModels**: EditorTab 中显示的模型列表（用于 UI 渲染）
- **Provider Templates**: Provider 配置模板，用于前端初始化新配置
- **EditorTab**: 前端配置编辑器组件

## Requirements

### Requirement 1: 用户创建新配置流程

**User Story:** 作为用户，我想创建一个新的 AI Provider 配置，以便连接到不同的 AI 服务。

#### Acceptance Criteria

1. WHEN 用户点击 "New Config" THEN 系统应打开 EditorTab，显示空白表单
2. WHEN EditorTab 初始化 THEN 系统应从后端加载 Provider Templates
3. WHEN 用户选择 Provider Template THEN 系统应自动填充 baseUrl 和 protocol
4. WHEN 用户输入 API Key 并点击 "Verify Connection" THEN 系统应调用后端 API 获取模型列表
5. WHEN 后端返回模型列表 THEN 系统应将完整的 `ModelConfig` 对象数组存储到 `verifiedModels` 状态
6. WHEN 用户点击 "Save" THEN 系统应将完整的 `ConfigProfile`（包含 `savedModels` 数组）保存到后端数据库

### Requirement 2: 用户编辑现有配置流程（核心问题）

**User Story:** 作为用户，我想编辑已保存的配置，以便在原有基础上更新 API Key 或调整模型选择。

#### Acceptance Criteria

1. WHEN 用户点击配置的 "Edit" 按钮 THEN 系统应打开 EditorTab，显示现有配置数据
2. WHEN EditorTab 加载现有配置 THEN 系统应从 `initialData.savedModels` 加载已保存的模型列表到 `verifiedModels`
3. WHEN 模型列表加载完成 THEN 系统应显示所有已保存的模型，用户可以看到之前的选择
4. WHEN 用户修改配置（不点击 "Verify Connection"）并点击 "Save" THEN 系统应保留原有的 `savedModels`
5. WHEN 用户点击 "Verify Connection" THEN 系统应重新获取最新的模型列表，替换 `verifiedModels`
6. WHEN 用户点击 "Save" THEN 系统应更新后端数据库中的配置

### Requirement 3: 后端数据存储和检索

**User Story:** 作为系统，我需要正确存储和检索 `ModelConfig` 对象数组，以便用户下次编辑时能看到完整的模型信息。

#### Acceptance Criteria

1. WHEN 前端发送 `POST /api/profiles` 请求 THEN 后端应接收 `savedModels` 字段（`List[dict]` 类型）
2. WHEN 后端保存配置 THEN 系统应将 `savedModels` 存储为 JSON 数组到数据库
3. WHEN 前端请求 `GET /api/profiles` THEN 后端应返回完整的 `savedModels` 数组
4. WHEN 前端加载配置 THEN 系统应能正确解析 `savedModels` 为 `ModelConfig[]` 类型

### Requirement 4: 修复 ModelConfig 不可哈希错误

**User Story:** 作为开发者，我需要修复后端代码中将 `ModelConfig` 对象用作集合元素的错误。

#### Acceptance Criteria

1. WHEN 后端调用 `get_available_models()` THEN 系统应使用字符串 ID 进行去重，而不是对象
2. WHEN 去重完成 THEN 系统应构建 `ModelConfig` 对象列表并返回
3. WHEN 前端调用模型验证 API THEN 系统应成功返回模型列表，无类型错误
