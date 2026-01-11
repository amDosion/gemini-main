---
name: "gemini-fullstack"
displayName: "Gemini Full-Stack Development"
description: "Build full-stack AI applications with Google Gemini API, FastAPI backend, and React/TypeScript frontend. Includes modular architecture patterns, MCP collaboration workflows, and comprehensive testing strategies."
keywords: ["gemini", "google", "ai", "fastapi", "python", "react", "typescript", "fullstack", "mcp", "modular-architecture", "api", "backend", "frontend"]
mcpServers: ["codex-mcp-toolkit", "gemini", "sequential-thinking", "desktop-commander", "context7", "fastapi-mcp-server", "vue-analyzer"]
---

# Gemini Full-Stack Development Power

## 概述

这个 Power 提供了使用 Google Gemini API 构建全栈 AI 应用的完整工作流程和最佳实践。项目采用模块化架构，支持多 AI 提供商集成，并通过 MCP 协作实现高效开发。

**技术栈**：
- **后端**：Python, FastAPI, SQLAlchemy, Google GenAI SDK
- **前端**：TypeScript, React, Vite, Tailwind CSS
- **AI 集成**：Google Gemini, OpenAI, 通义千问
- **协作工具**：MCP (Codex, Gemini, Sequential Thinking)

---

## Onboarding

### Step 1: 验证开发环境

在开始使用此 Power 之前，请确保以下工具已安装并正常运行：

**必需工具**：
- **Python 3.9+**: 后端开发
  - 验证：`python --version`
  - **CRITICAL**: 如果 Python 未安装，请先安装后再继续
- **Node.js 16+**: 前端开发
  - 验证：`node --version`
  - **CRITICAL**: 如果 Node.js 未安装，请先安装后再继续
- **Git**: 版本控制
  - 验证：`git --version`

**推荐工具**：
- **Docker Desktop**: 用于容器化部署（可选）
  - 验证：`docker --version`
- **VS Code / Kiro IDE**: 代码编辑器

**关键检查**：
- ✅ 确保 Git 已配置用户信息（`git config user.name` 和 `git config user.email`）
- ✅ 验证 Python 和 Node.js 版本符合要求

### Step 2: 添加 Hooks

为了自动化工作流程，建议添加以下 Hooks。Hooks 分为三类：

- **File Hooks**: 在文件操作时触发（`fileEdited`, `fileCreated`, `fileDeleted`）
- **Contextual Hooks**: 在特定上下文事件时触发（`promptSubmit`, `agentStop`）
- **Manual Hooks**: 用户手动触发（`userTriggered`）

每个 Hook 可以执行两种 action：
- **askAgent**: 向 Agent 发送消息
- **runCommand**: 执行 shell 命令

---

#### 1. File Edited Hooks（文件保存时触发）

##### 1.1 代码格式化和 Lint

添加 Hook 到 `.kiro/hooks/on-file-save/format-and-lint.kiro.hook`

```json
{
  "enabled": true,
  "name": "Format and Lint Code",
  "description": "保存文件时自动运行代码格式化和 Lint 检查",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "pattern": "{backend/**/*.py,frontend/**/*.{ts,tsx,js,jsx}}"
  },
  "then": {
    "type": "runCommand",
    "command": "if ($env:FILE -like '*backend\\*\\*.py') { cd backend; ruff format $env:FILE; ruff check $env:FILE } elseif ($env:FILE -like '*frontend\\*\\*.ts*') { cd frontend; npm run lint -- $env:FILE }"
  }
}
```

##### 1.2 运行相关测试

添加 Hook 到 `.kiro/hooks/on-file-save/run-related-tests.kiro.hook`

```json
{
  "enabled": false,
  "name": "Run Related Tests",
  "description": "保存文件时自动运行相关的测试文件",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "pattern": "{backend/**/*.py,frontend/**/*.{ts,tsx}}"
  },
  "then": {
    "type": "runCommand",
    "command": "if ($env:FILE -like '*backend\\*\\*.py') { cd backend; $testFile = $env:FILE -replace '\\.py$','_test.py'; pytest $testFile -v } elseif ($env:FILE -like '*frontend\\*\\*.ts*') { cd frontend; $testFile = $env:FILE -replace '\\.tsx?$','.test.tsx'; npm test -- $testFile }"
  }
}
```

##### 1.3 更新文档

添加 Hook 到 `.kiro/hooks/on-file-save/update-documentation.kiro.hook`

```json
{
  "enabled": false,
  "name": "Update Documentation",
  "description": "保存文件时提醒更新相关文档",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "pattern": "{backend/app/routers/**/*.py,frontend/services/**/*.ts}"
  },
  "then": {
    "type": "askAgent",
    "prompt": "文件 ${FILE} 已更新。请检查是否需要更新以下文档：\n1. API 文档（如果是路由文件）\n2. README.md（如果是核心服务）\n3. 类型定义文档（如果是 TypeScript 服务）"
  }
}
```

##### 1.4 文件大小检查

添加 Hook 到 `.kiro/hooks/on-file-save/check-file-size.kiro.hook`

```json
{
  "enabled": true,
  "name": "Check File Size",
  "description": "检查文件是否符合模块化原则（后端 < 300 行，前端 < 200 行）",
  "version": "1",
  "when": {
    "type": "fileEdited",
    "pattern": "{backend/**/*.py,frontend/**/*.{ts,tsx}}"
  },
  "then": {
    "type": "askAgent",
    "prompt": "检查文件 ${FILE} 的行数。如果后端文件超过 300 行或前端文件超过 200 行，建议拆分为多个模块。"
  }
}
```

---

#### 2. File Created Hooks（文件创建时触发）

##### 2.1 生成测试文件样板

添加 Hook 到 `.kiro/hooks/on-file-create/create-test-file.kiro.hook`

```json
{
  "enabled": true,
  "name": "Create Test File",
  "description": "创建新文件时自动生成对应的测试文件样板",
  "version": "1",
  "when": {
    "type": "fileCreated",
    "pattern": "{backend/**/*.py,frontend/**/*.{ts,tsx}}"
  },
  "then": {
    "type": "askAgent",
    "prompt": "为新文件 ${FILE} 创建对应的测试文件样板。\n\n要求：\n1. 后端：使用 pytest，包含基本的单元测试结构\n2. 前端：使用 Vitest + React Testing Library\n3. 包含至少 3 个测试用例：正常情况、边界条件、错误处理\n4. 使用 Desktop Commander MCP 写入文件"
  }
}
```

##### 2.2 添加许可证标头

添加 Hook 到 `.kiro/hooks/on-file-create/add-license-header.kiro.hook`

```json
{
  "enabled": false,
  "name": "Add License Header",
  "description": "为新文件添加许可证标头和文件元信息",
  "version": "1",
  "when": {
    "type": "fileCreated",
    "pattern": "{backend/**/*.py,frontend/**/*.{ts,tsx}}"
  },
  "then": {
    "type": "askAgent",
    "prompt": "为新文件 ${FILE} 添加许可证标头。\n\n包含：\n1. MIT License 声明\n2. 文件描述\n3. 创建日期\n4. 作者信息\n\n使用 Desktop Commander MCP 的 edit_block 工具在文件开头插入。"
  }
}
```

##### 2.3 生成组件样板代码

添加 Hook 到 `.kiro/hooks/on-file-create/generate-component-boilerplate.kiro.hook`

```json
{
  "enabled": true,
  "name": "Generate Component Boilerplate",
  "description": "创建新组件时自动生成样板代码",
  "version": "1",
  "when": {
    "type": "fileCreated",
    "pattern": "frontend/components/**/*.tsx"
  },
  "then": {
    "type": "askAgent",
    "prompt": "为新组件 ${FILE} 生成样板代码。\n\n包含：\n1. React 函数组件结构\n2. TypeScript 类型定义（Props interface）\n3. 基本的 JSX 结构\n4. 导出语句\n5. 简单的注释说明\n\n使用 Desktop Commander MCP 写入文件。"
  }
}
```

##### 2.4 验证模块化结构

添加 Hook 到 `.kiro/hooks/on-file-create/validate-modular-structure.kiro.hook`

```json
{
  "enabled": true,
  "name": "Validate Modular Structure",
  "description": "验证文件是否遵循模块化目录结构",
  "version": "1",
  "when": {
    "type": "fileCreated",
    "pattern": "{backend/app/services/**/*.py,frontend/components/**/*.tsx}"
  },
  "then": {
    "type": "askAgent",
    "prompt": "验证新文件 ${FILE} 是否遵循模块化架构原则：\n1. 后端服务是否在正确的子目录中\n2. 前端组件是否按功能分组\n3. 文件命名是否符合规范\n4. 是否需要创建 __init__.py 或 index.ts"
  }
}
```

---

#### 3. Contextual Hooks（上下文事件触发）

##### 3.1 Agent 完成后运行测试套件

添加 Hook 到 `.kiro/hooks/on-agent-stop/run-test-suite.kiro.hook`

```json
{
  "enabled": false,
  "name": "Run Test Suite After Agent",
  "description": "Agent 完成任务后自动运行完整的测试套件",
  "version": "1",
  "when": {
    "type": "agentStop"
  },
  "then": {
    "type": "runCommand",
    "command": "cd backend && pytest tests/ -v --cov=app --cov-report=term-missing && cd ../frontend && npm test -- --run"
  }
}
```

##### 3.2 Agent 完成后格式化代码

添加 Hook 到 `.kiro/hooks/on-agent-stop/format-all-code.kiro.hook`

```json
{
  "enabled": false,
  "name": "Format All Code After Agent",
  "description": "Agent 完成任务后格式化所有修改的代码",
  "version": "1",
  "when": {
    "type": "agentStop"
  },
  "then": {
    "type": "runCommand",
    "command": "cd backend && ruff format . && cd ../frontend && npm run format"
  }
}
```

##### 3.3 提交消息时提供额外上下文

添加 Hook 到 `.kiro/hooks/on-prompt-submit/provide-context.kiro.hook`

```json
{
  "enabled": false,
  "name": "Provide Additional Context",
  "description": "用户提交消息时自动提供项目上下文信息",
  "version": "1",
  "when": {
    "type": "promptSubmit"
  },
  "then": {
    "type": "askAgent",
    "prompt": "用户提交了新消息。请记住以下项目上下文：\n1. 模块化原则：后端 < 300 行，前端 < 200 行\n2. 使用 Desktop Commander MCP 写入文件\n3. 使用 context-gatherer subagent 读取文档\n4. 遵循 .kiro/steering/KIRO-RULES.md 中的规则"
  }
}
```

---

#### 4. Manual Hooks（用户手动触发）

##### 4.1 代码审查

添加 Hook 到 `.kiro/hooks/manual/code-review.kiro.hook`

```json
{
  "enabled": true,
  "name": "Code Review",
  "description": "手动触发完整的代码审查",
  "version": "1",
  "when": {
    "type": "userTriggered"
  },
  "then": {
    "type": "askAgent",
    "prompt": "执行完整的代码审查。\n\n检查项：\n1. 代码质量：是否遵循最佳实践\n2. 模块化：文件大小是否合理\n3. 测试覆盖：是否有足够的测试\n4. 安全性：是否有安全漏洞\n5. 性能：是否有性能问题\n6. 文档：是否有足够的注释和文档\n\n使用 general-purpose subagent 调用 Claude Code MCP 进行深度审查。"
  }
}
```

##### 4.2 安全扫描

添加 Hook 到 `.kiro/hooks/manual/security-scan.kiro.hook`

```json
{
  "enabled": true,
  "name": "Security Scan",
  "description": "手动触发安全漏洞扫描",
  "version": "1",
  "when": {
    "type": "userTriggered"
  },
  "then": {
    "type": "askAgent",
    "prompt": "执行安全漏洞扫描。\n\n检查项：\n1. SQL 注入风险\n2. XSS 攻击风险\n3. CSRF 防护\n4. API 密钥泄露\n5. 敏感数据加密\n6. 依赖包漏洞\n\n使用 general-purpose subagent 调用 Sequential Thinking MCP 进行深度分析。"
  }
}
```

##### 4.3 性能优化建议

添加 Hook 到 `.kiro/hooks/manual/performance-optimization.kiro.hook`

```json
{
  "enabled": true,
  "name": "Performance Optimization",
  "description": "手动触发性能优化建议",
  "version": "1",
  "when": {
    "type": "userTriggered"
  },
  "then": {
    "type": "askAgent",
    "prompt": "分析项目性能并提供优化建议。\n\n分析项：\n1. 后端：数据库查询优化、异步处理、缓存策略\n2. 前端：组件渲染优化、代码分割、懒加载\n3. API：响应时间、并发处理、流式传输\n4. 资源：内存使用、CPU 占用、网络带宽\n\n使用 general-purpose subagent 调用 Sequential Thinking MCP 进行深度分析。"
  }
}
```

##### 4.4 生成 API 文档

添加 Hook 到 `.kiro/hooks/manual/generate-api-docs.kiro.hook`

```json
{
  "enabled": true,
  "name": "Generate API Documentation",
  "description": "手动触发 API 文档生成",
  "version": "1",
  "when": {
    "type": "userTriggered"
  },
  "then": {
    "type": "askAgent",
    "prompt": "生成完整的 API 文档。\n\n包含：\n1. 所有 API 端点列表\n2. 请求/响应格式\n3. 参数说明\n4. 错误代码\n5. 使用示例\n\n使用 context-gatherer subagent 读取所有路由文件，然后生成 Markdown 文档。使用 Desktop Commander MCP 写入文件到 docs/api.md。"
  }
}
```

##### 4.5 依赖更新检查

添加 Hook 到 `.kiro/hooks/manual/check-dependencies.kiro.hook`

```json
{
  "enabled": true,
  "name": "Check Dependencies",
  "description": "手动触发依赖包更新检查",
  "version": "1",
  "when": {
    "type": "userTriggered"
  },
  "then": {
    "type": "runCommand",
    "command": "cd backend && pip list --outdated && cd ../frontend && npm outdated"
  }
}
```

---

#### Hook 使用指南

**如何启用/禁用 Hooks**：
- 编辑 Hook 文件中的 `"enabled"` 字段
- `true`: 启用，`false`: 禁用

**如何触发 Manual Hooks**：
1. 打开 Kiro 命令面板（Ctrl+Shift+P / Cmd+Shift+P）
2. 搜索 "Kiro: Run Hook"
3. 选择要运行的 Hook

**Hook 变量**：
- `${FILE}`: 当前文件路径
- `${WORKSPACE}`: 工作区根目录
- `${MESSAGE}`: 用户消息内容（仅 promptSubmit）

**最佳实践**：
1. 开发阶段启用 `format-and-lint` 和 `check-file-size`
2. 生产部署前运行 `security-scan` 和 `run-test-suite`
3. 定期运行 `check-dependencies` 保持依赖更新
4. 使用 `code-review` 进行代码质量检查

### Step 3: 配置 API 密钥

**后端配置**（`.env.local`）：
```env
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key

# OpenAI API（可选）
OPENAI_API_KEY=your_openai_api_key

# 数据库
DATABASE_URL=sqlite:///./gemini.db

# JWT 密钥
SECRET_KEY=your_secret_key
ENCRYPTION_KEY=your_encryption_key
```

**前端配置**：
- API 端点配置在 `frontend/services/apiClient.ts`
- 默认连接到 `http://localhost:8000`

---

## When to Load Steering Files

根据你当前的开发任务，Kiro 会自动加载对应的 steering 文件：

### 前端开发
**触发关键词**：React, TypeScript, 组件, UI, 前端

**加载文件**：`steering/frontend-development.md`

**包含内容**：
- React 组件开发规范
- TypeScript 类型定义最佳实践
- Custom Hooks 使用指南
- 状态管理模式
- 性能优化建议

### 后端开发
**触发关键词**：FastAPI, Python, API, 路由, 后端

**加载文件**：`steering/backend-development.md`

**包含内容**：
- FastAPI 路由设计规范
- Pydantic 模型验证
- 异步编程最佳实践
- 数据库操作规范
- 错误处理模式

### Gemini 集成
**触发关键词**：Gemini, Google, AI, 模型, SDK

**加载文件**：`steering/gemini-integration.md`

**包含内容**：
- 文档优先原则（必须先阅读官方 SDK 文档）
- 继承 BaseProviderService 的规范
- 模块化实现要求
- 错误处理和重试机制
- 流式响应处理

### 代码重构
**触发关键词**：重构, 优化, 拆分, 模块化

**加载文件**：`steering/refactoring.md`

**包含内容**：
- 识别需要重构的代码
- 模块化拆分步骤
- 重构检查清单
- 测试覆盖验证

### MCP 协作
**触发关键词**：Codex, MCP, 协作, 子 Agent

**加载文件**：`steering/mcp-collaboration.md`

**包含内容**：
- Kiro 主 Agent 与子 Agent 的协作流程
- "生成-思考-验证-修正"迭代循环
- 深度思考分析方法
- 会话上下文管理

### 新功能开发
**触发关键词**：新功能, 需求, 设计, Spec

**加载文件**：`steering/new-feature.md`

**包含内容**：
- Spec 驱动开发流程
- Requirements → Design → Tasks 工作流
- 验收标准定义
- 测试策略规划

---

## Best Practices

### 1. 模块化架构（核心原则）

**服务层模块化**：
- 每个功能单独文件，主文件协调
- 单个文件不超过 300 行（后端）
- 例如：`chat_handler.py`, `image_generator.py`, `google_service.py`（协调器）

**UI 层模块化**：
- 每个组件单独文件，协调组件组装
- 单个文件不超过 200 行（前端）
- 例如：`MessageList.tsx`, `InputArea.tsx`, `ChatView.tsx`（协调器）

### 2. MCP 协作工作流

**标准流程**：
1. Kiro 读取 Spec 文档（使用 context-gatherer subagent）
2. Kiro 调用子 Agent 生成代码（Codex 或 Gemini）
3. Kiro 进行深度思考分析（Sequential Thinking MCP）
4. Kiro 验证思考结果
5. Kiro 进行最终代码审查（Claude Code MCP）
6. Kiro 写入文件（Desktop Commander MCP）
7. Kiro 标记任务完成

### 3. Gemini API 集成

**文档优先原则**：
1. 阅读官方文档（`.kiro/specs/参考/python-genai-main/google-genai-models-usage.md`）
2. 查看原始代码（`.kiro/specs/参考/python-genai-main/google/genai/`）
3. 实现功能

### 4. 测试策略

**双重测试方法**：
- **单元测试**：具体示例和边界条件
- **属性测试**：通用属性跨所有输入

### 5. 安全最佳实践

- API 密钥管理：使用环境变量
- 输入验证：使用 Pydantic
- JWT 令牌 + API 密钥加密

---

## Common Workflows

### 工作流 1：添加新的 AI 提供商

1. 创建提供商服务目录：`backend/app/services/{provider_name}/`
2. 实现 `BaseProviderService` 接口
3. 创建功能模块（chat, image, etc.）
4. 在 `provider_factory.py` 中注册
5. 添加路由和测试

**参考 steering 文件**：`steering/gemini-integration.md`

### 工作流 2：开发新的前端组件

1. 在 `frontend/components/` 创建组件目录
2. 拆分为子组件（每个 < 200 行）
3. 创建协调组件组装子组件
4. 编写 Custom Hooks 管理状态
5. 添加 TypeScript 类型定义
6. 编写单元测试

**参考 steering 文件**：`steering/frontend-development.md`

### 工作流 3：重构大文件

1. 识别文件大小 > 500 行的文件
2. 分析功能模块和职责
3. 创建独立的模块文件
4. 创建主协调器文件
5. 更新导入和测试
6. 验证功能正常

**参考 steering 文件**：`steering/refactoring.md`

---

## Troubleshooting

### 问题 1：MCP 子 Agent 超时

**症状**：`MCP error -32001: Request timed out`

**解决方案**：
1. 简化 PROMPT，减少任务复杂度
2. 分步执行，先分析再生成
3. 检查网络连接
4. 使用 SESSION_ID 续问而不是重新开始

### 问题 2：文件大小超限

**症状**：文件超过 300 行（后端）或 200 行（前端）

**解决方案**：
1. 使用 Hooks 自动检查（已配置）
2. 按功能拆分为多个模块
3. 创建主协调器组装模块
4. 参考 `steering/refactoring.md`

### 问题 3：Gemini API 错误

**症状**：API 调用失败或返回错误

**解决方案**：
1. 检查 API 密钥是否正确配置
2. 验证请求格式是否符合官方文档
3. 查看错误日志获取详细信息
4. 参考 `.kiro/specs/参考/python-genai-main/` 中的示例

### 问题 4：上下文超载

**症状**：Kiro 响应缓慢或无法加载所有规则

**解决方案**：
1. 使用 `context-gatherer` 子 Agent 按需获取文档
2. 不要直接读取所有 steering 文件
3. 遵循单一路由文件架构
4. 使用 Redis MCP 缓存文档摘要

---

## Resources

### 官方文档
- [Google GenAI SDK 文档](https://ai.google.dev/gemini-api/docs)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [React 文档](https://react.dev/)

### 项目文档
- [项目结构](.kiro/docs/architecture/project-structure.md)
- [主 Agent 协作规则](.kiro/docs/core/agents-collaboration.md)
- [Steering 规则路由](.kiro/steering/KIRO-RULES.md)
- [Hooks 指南](.kiro/docs/collaboration/hooks-integration-guide.md)

### 参考代码
- [Google GenAI SDK 原始代码](.kiro/specs/参考/python-genai-main/google/genai/)
- [API 使用示例](.kiro/specs/参考/python-genai-main/google-genai-models-usage.md)

---

## Version

**Power Version**: v2.1.0  
**Last Updated**: 2026-01-10  
**Maintainer**: Development Team  
**Changes**: 添加完整的 Hooks 配置（15 个 Hooks），包含 File Hooks、Contextual Hooks 和 Manual Hooks
