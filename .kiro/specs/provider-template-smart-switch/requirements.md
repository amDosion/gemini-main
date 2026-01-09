# Requirements Document: Provider Template Smart Switch

## Introduction

实现智能 Provider Template 切换功能，允许用户在编辑配置时切换 Provider Template，系统自动加载该 Provider 对应的已有配置数据（API Key、模型列表、Connection Details 等），提升配置管理效率。

## Glossary

- **Provider Template**: AI 服务提供商模板，包含 providerId、name、baseUrl、protocol 等默认配置
- **ConfigProfile**: 用户保存的完整配置，包含 id、name、providerId、apiKey、baseUrl、savedModels、hiddenModels 等
- **EditorTab**: 配置编辑界面组件
- **SettingsModal**: 设置模态框，包含配置列表和编辑界面
- **Smart Switch**: 智能切换，指根据 Provider 自动加载已有配置数据的行为

## Requirements

### Requirement 1: 传递配置列表到编辑器

**User Story:** 作为开发者，我希望 EditorTab 能够访问所有已有的配置数据，以便在切换 Provider 时查找对应的配置。

#### Acceptance Criteria

1. WHEN SettingsModal 渲染 EditorTab 时，THE System SHALL 将完整的 profiles 数组传递给 EditorTab
2. WHEN EditorTab 接收 profiles 数据时，THE System SHALL 存储在组件状态中供后续使用
3. THE EditorTab SHALL 保持 existingProfiles 参数的接口定义

### Requirement 2: 查找 Provider 对应的配置

**User Story:** 作为用户，当我切换 Provider Template 时，系统应该自动查找该 Provider 的已有配置。

#### Acceptance Criteria

1. WHEN 用户点击 Provider Template 按钮时，THE System SHALL 根据 providerId 在 profiles 中查找匹配的配置
2. WHEN 存在多个相同 Provider 的配置时，THE System SHALL 选择最近更新的配置（updatedAt 最大）
3. WHEN 不存在该 Provider 的配置时，THE System SHALL 返回 null 表示未找到

### Requirement 3: 编辑模式的智能切换

**User Story:** 作为用户，当我在编辑模式下切换 Provider Template 时，系统应该完全切换到该 Provider 的已有配置进行编辑。

#### Acceptance Criteria

1. WHEN 用户在编辑模式下切换 Provider Template 且找到已有配置时，THE System SHALL 加载该配置的所有字段（id、name、apiKey、baseUrl、savedModels、hiddenModels、cachedModelCount、customHeaders）
2. WHEN 加载已有配置时，THE System SHALL 同时更新 verifiedModels 状态为该配置的 savedModels
3. WHEN 用户在编辑模式下切换 Provider Template 但未找到已有配置时，THE System SHALL 应用模板默认值（baseUrl、protocol）并清空用户数据字段（apiKey、savedModels 等）
4. WHEN 切换完成后保存时，THE System SHALL 更新对应配置的数据

### Requirement 4: 创建模式的智能切换

**User Story:** 作为用户，当我在创建模式下切换 Provider Template 时，系统应该基于已有配置提供模板数据，但保持新配置的独立性。

#### Acceptance Criteria

1. WHEN 用户在创建模式下切换 Provider Template 且找到已有配置时，THE System SHALL 复制该配置的数据字段（apiKey、baseUrl、savedModels、hiddenModels、cachedModelCount、customHeaders）
2. WHEN 复制配置数据时，THE System SHALL 保持当前的 id（新生成的 UUID）不变
3. WHEN 复制配置数据时，THE System SHALL 更新 name 为新的模板名称（例如 "OpenAI Config"）
4. WHEN 用户在创建模式下切换 Provider Template 但未找到已有配置时，THE System SHALL 应用模板默认值
5. WHEN 切换完成后保存时，THE System SHALL 创建新的配置记录

### Requirement 5: 用户界面反馈

**User Story:** 作为用户，我希望在切换 Provider Template 时能够清楚地看到数据的变化。

#### Acceptance Criteria

1. WHEN Provider Template 切换完成时，THE System SHALL 立即更新所有表单字段的显示值
2. WHEN 加载已有配置的模型列表时，THE System SHALL 在模型列表区域显示加载的模型
3. WHEN 切换到没有已有配置的 Provider 时，THE System SHALL 清空模型列表显示
4. THE System SHALL 保持 Provider Template 按钮的高亮状态与当前 providerId 一致

### Requirement 6: 数据完整性保证

**User Story:** 作为系统，我需要确保切换过程中数据的完整性和一致性。

#### Acceptance Criteria

1. WHEN 加载已有配置时，THE System SHALL 验证配置对象包含所有必需字段
2. WHEN savedModels 字段存在时，THE System SHALL 验证其为有效的 ModelConfig 数组
3. WHEN 切换过程中发生错误时，THE System SHALL 保持当前表单数据不变
4. THE System SHALL 在控制台输出切换操作的日志，包括找到的配置信息

### Requirement 7: 性能优化

**User Story:** 作为用户，我希望 Provider Template 切换操作响应迅速，不影响编辑体验。

#### Acceptance Criteria

1. WHEN 查找配置时，THE System SHALL 使用高效的数组查找算法（时间复杂度 O(n)）
2. WHEN 更新状态时，THE System SHALL 使用 React 的批量更新机制避免多次重渲染
3. WHEN 配置列表很大时（>100 个配置），THE System SHALL 仍能在 100ms 内完成切换操作

### Requirement 8: 向后兼容性

**User Story:** 作为开发者，我需要确保新功能不破坏现有的配置编辑流程。

#### Acceptance Criteria

1. WHEN existingProfiles 参数未提供时，THE System SHALL 降级到原有的模板应用行为
2. WHEN 用户手动修改表单字段后切换 Provider 时，THE System SHALL 正确覆盖手动修改的值
3. THE System SHALL 保持与现有保存、验证、关闭等功能的兼容性
