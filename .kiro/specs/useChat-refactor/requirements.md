# Requirements Document

## Introduction

本需求文档定义了 `useChat.ts` 的重构目标。当前实现中，`sendMessage` 函数包含一个巨大的 `if-else` 链来处理不同的应用模式（chat、image-gen、image-edit 等），导致代码难以维护和扩展。我们需要将 `useChat` 重构为一个真正的协调者（Coordinator），通过策略模式（Strategy Pattern）来处理不同模式的执行逻辑。

## Glossary

- **useChat Hook**: React Hook，负责管理聊天消息状态和协调消息发送流程
- **Handler**: 处理特定应用模式（如 chat、image-gen）的业务逻辑模块
- **Strategy Pattern**: 设计模式，定义一系列算法，把它们一个个封装起来，并且使它们可以相互替换
- **Coordinator**: 协调者，负责调度和协调不同组件的交互，但不包含具体业务逻辑
- **AppMode**: 应用模式枚举，包括 chat、image-gen、image-edit、image-outpainting、virtual-try-on、video-gen、audio-gen、pdf-extract
- **HandlerContext**: 传递给 Handler 的上下文对象，包含 sessionId、messageId、apiKey 等信息
- **Message**: 消息对象，包含 id、role、content、attachments 等字段
- **Attachment**: 附件对象，包含 id、type、url、file 等字段

## Requirements

### Requirement 1

**User Story:** 作为开发者，我希望 `useChat` 是一个纯粹的协调者，这样我可以轻松添加新的应用模式而不修改核心逻辑。

#### Acceptance Criteria

1. WHEN 添加新的应用模式 THEN `useChat` 的核心逻辑 SHALL 保持不变
2. WHEN 执行消息发送 THEN `useChat` SHALL 通过策略模式委托给对应的 Handler
3. WHEN 处理不同模式 THEN 每个模式的业务逻辑 SHALL 完全封装在独立的 Handler 中
4. WHEN 初始化 Handler THEN 系统 SHALL 自动注册所有可用的 Handler
5. WHEN 选择 Handler THEN 系统 SHALL 根据 AppMode 动态选择对应的策略

### Requirement 2

**User Story:** 作为开发者，我希望消除巨大的 `if-else` 链，这样代码更易读和维护。

#### Acceptance Criteria

1. WHEN 查看 `sendMessage` 函数 THEN 函数体 SHALL 不包含任何模式判断的 `if-else` 语句
2. WHEN 处理模式分发 THEN 系统 SHALL 使用策略映射表（Strategy Map）进行查找
3. WHEN 执行 Handler THEN 所有 Handler SHALL 实现统一的接口
4. WHEN 处理错误 THEN 错误处理逻辑 SHALL 在协调者层统一处理
5. WHEN 更新状态 THEN 状态更新逻辑 SHALL 在协调者层统一管理

### Requirement 3

**User Story:** 作为开发者，我希望每个 Handler 有清晰的职责边界，这样可以独立测试和维护。

#### Acceptance Criteria

1. WHEN 定义 Handler 接口 THEN 接口 SHALL 包含 `execute` 方法和可选的生命周期钩子
2. WHEN Handler 执行 THEN Handler SHALL 只负责特定模式的业务逻辑
3. WHEN Handler 需要更新 UI THEN Handler SHALL 通过回调函数通知协调者
4. WHEN Handler 处理上传 THEN Handler SHALL 返回标准化的结果对象
5. WHEN Handler 失败 THEN Handler SHALL 抛出标准化的错误对象

### Requirement 4

**User Story:** 作为开发者，我希望保持向后兼容，这样现有功能不会受到影响。

#### Acceptance Criteria

1. WHEN 重构完成 THEN 所有现有功能 SHALL 保持原有行为
2. WHEN 调用 `sendMessage` THEN API 签名 SHALL 保持不变
3. WHEN 处理消息 THEN 消息格式 SHALL 保持不变
4. WHEN 更新状态 THEN 状态更新时机 SHALL 保持不变
5. WHEN 处理附件 THEN 附件处理逻辑 SHALL 保持不变

### Requirement 5

**User Story:** 作为开发者，我希望代码结构清晰，这样新成员可以快速理解架构。

#### Acceptance Criteria

1. WHEN 查看项目结构 THEN Handler 注册逻辑 SHALL 集中在一个配置文件中
2. WHEN 阅读代码 THEN 每个 Handler SHALL 有清晰的文档注释
3. WHEN 理解流程 THEN 协调者的执行流程 SHALL 通过注释清晰标注
4. WHEN 查看类型定义 THEN 所有接口和类型 SHALL 有完整的 TypeScript 类型注解
5. WHEN 追踪数据流 THEN 数据流向 SHALL 通过类型系统清晰表达

### Requirement 6

**User Story:** 作为开发者，我希望 Handler 可以共享通用逻辑，这样避免代码重复。

#### Acceptance Criteria

1. WHEN 多个 Handler 需要相同功能 THEN 系统 SHALL 提供抽象基类或工具函数
2. WHEN 处理上传 THEN 上传逻辑 SHALL 在基类或工具模块中实现
3. WHEN 处理轮询 THEN 轮询逻辑 SHALL 在基类或工具模块中实现
4. WHEN 更新消息 THEN 消息更新逻辑 SHALL 通过统一的回调接口
5. WHEN 处理错误 THEN 错误转换逻辑 SHALL 在基类或工具模块中实现

### Requirement 7

**User Story:** 作为开发者，我希望支持 Handler 的生命周期管理，这样可以处理复杂的异步场景。

#### Acceptance Criteria

1. WHEN Handler 开始执行 THEN 系统 SHALL 调用 `onStart` 钩子（如果定义）
2. WHEN Handler 执行完成 THEN 系统 SHALL 调用 `onComplete` 钩子（如果定义）
3. WHEN Handler 执行失败 THEN 系统 SHALL 调用 `onError` 钩子（如果定义）
4. WHEN Handler 被取消 THEN 系统 SHALL 调用 `onCancel` 钩子（如果定义）
5. WHEN Handler 需要清理资源 THEN 系统 SHALL 在适当时机调用清理钩子

### Requirement 8

**User Story:** 作为开发者，我希望支持 Handler 的组合和链式调用，这样可以构建复杂的工作流。

#### Acceptance Criteria

1. WHEN 需要多步骤处理 THEN Handler SHALL 支持返回中间结果供下一步使用
2. WHEN 需要条件分支 THEN Handler SHALL 支持根据结果选择下一个 Handler
3. WHEN 需要并行处理 THEN 系统 SHALL 支持同时执行多个 Handler
4. WHEN 需要串行处理 THEN 系统 SHALL 支持按顺序执行多个 Handler
5. WHEN 需要回滚 THEN Handler SHALL 支持撤销操作（可选）
