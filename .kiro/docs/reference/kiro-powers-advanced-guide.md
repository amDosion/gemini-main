# Kiro Powers 高级用法完整指南

**文档版本**：v1.0.0
**最后更新**：2026-01-10
**基于**: [Kiro 官方文档](https://kiro.dev/docs/powers/)

---

## 📚 目录

1. [Power 基础结构](#power-基础结构)
2. [POWER.md 详细格式](#powermd-详细格式)
3. [Steering 目录高级用法](#steering-目录高级用法)
4. [MCP 集成](#mcp-集成)
5. [Hooks 集成](#hooks-集成)
6. [完整示例](#完整示例)
7. [最佳实践](#最佳实践)
8. [故障排除](#故障排除)

---

## Power 基础结构

### 标准目录结构

```
.kiro/powers/power-name/
├── POWER.md              # 必需：Power 主配置文件
├── mcp.json             # 可选：MCP 服务器配置
└── steering/            # 可选：多个 steering 文件
    ├── workflow-1.md
    ├── workflow-2.md
    └── reference.md
```

### 关键要点

1. **文件命名**：
   - 主文件必须命名为 `POWER.md`（不是 `power-name.md`）
   - Power 目录名应该是 `power-name` 格式（小写，连字符分隔）

2. **目录位置**：
   - 工作区 Power：`.kiro/powers/power-name/`
   - 全局 Power：`~/.kiro/powers/power-name/`

3. **激活机制**：
   - 基于 frontmatter 中的 `keywords` 字段
   - 当用户提到相关关键词时自动加载

---

## POWER.md 详细格式

### 完整结构

```markdown
---
name: "power-identifier"
displayName: "Human-readable Power Name"
description: "Brief description of what this power does (1-2 sentences)"
keywords: ["keyword1", "keyword2", "keyword3", "keyword4"]
mcpServers: ["server-name"]
---

# Power Display Name

Brief introduction to the power.

## Onboarding

### Step 1: Validate Dependencies

Check that required tools are installed:
- **Tool 1**: Verify with `tool --version`
- **Tool 2**: Run `tool check`
- **CRITICAL**: If not installed, provide installation instructions

### Step 2: Environment Setup

Environment variables needed:
```env
API_KEY=your_api_key
API_URL=https://api.example.com
```

### Step 3: Add Hooks (Optional)

Add to `.kiro/hooks/hook-name.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Hook Name",
  "description": "What this hook does",
  "when": {
    "type": "fileEdited",
    "patterns": ["**/*.ts"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Your agent instruction here"
  }
}
```

## When to Load Steering Files

Map steering files to specific scenarios:

### Scenario 1: Workflow Name
**Triggered by keywords**: keyword1, keyword2
**Load**: `.kiro/powers/power-name/steering/workflow-1.md`

Use when: Description of when this applies

### Scenario 2: Another Workflow
**Triggered by keywords**: keyword3, keyword4
**Load**: `.kiro/powers/power-name/steering/workflow-2.md`

Use when: Description of when this applies

## Best Practices

### Practice 1: Title

Description and code examples

### Practice 2: Title

Description and code examples

## Common Workflows

### Workflow 1: Task Name

Step-by-step guide with examples

### Workflow 2: Task Name

Step-by-step guide with examples

## Troubleshooting

### Problem 1

**Symptoms**: Description
**Solution**: Steps to fix

### Problem 2

**Symptoms**: Description
**Solution**: Steps to fix

## Resources

- [Official Documentation](https://example.com)
- [API Reference](https://example.com/api)
- [Community](https://example.com/community)
```

### Frontmatter 字段详解

#### 必需字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `name` | string | Power 唯一标识符（小写，连字符分隔） | `"gemini-fullstack"` |
| `displayName` | string | 人类可读的名称 | `"Gemini Full-Stack Development"` |
| `description` | string | 简短描述（1-2 句话） | `"Build AI apps with Gemini"` |
| `keywords` | array | 触发关键词（3-10 个） | `["gemini", "google", "ai"]` |

#### 可选字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `mcpServers` | array | 此 Power 使用的 MCP 服务器 | `["codex", "gemini"]` |

### Keywords 设计原则

**好的 keywords**：
```yaml
keywords: [
  "gemini",        # 主要技术
  "google",        # 厂商
  "fastapi",       # 后端框架
  "react",         # 前端框架
  "ai",            # 领域
  "fullstack"      # 类型
]
```

**不好的 keywords**：
```yaml
keywords: [
  "build",         # ❌ 太通用
  "create",        # ❌ 太通用
  "app",           # ❌ 太通用
  "code"           # ❌ 太通用
]
```

---

## Steering 目录高级用法

### Steering 文件格式

每个 steering 文件都是独立的 Markdown 文件，带有 frontmatter：

```markdown
---
inclusion: always|fileMatch|manual
fileMatchPattern: "pattern/**/*.ext"  # 仅 fileMatch 需要
---

# Steering File Title

Content here...
```

### Inclusion 类型详解

#### 1. Always（每次加载）

```yaml
---
inclusion: always
---
```

**使用场景**：
- 核心技术栈信息
- 基本编码约定
- 安全原则
- 必须始终遵循的规则

**注意**：
- ⚠️ 会占用每次对话的 token
- 应该尽可能简短（< 100 行）
- 只用于最核心的规则

**示例**：
```markdown
---
inclusion: always
---

# Core Principles

## Security
- Never hardcode API keys
- Always validate user input
- Use prepared statements for SQL

## Code Style
- TypeScript for frontend
- Python for backend
- Follow ESLint/Black rules
```

#### 2. FileMatch（文件匹配）

```yaml
---
inclusion: fileMatch
fileMatchPattern: "components/**/*.tsx"
---
```

**使用场景**：
- React 组件规范（仅编辑 `.tsx` 文件时加载）
- API 路由规范（仅编辑 `api/` 目录时加载）
- 测试规范（仅编辑 `.test.*` 文件时加载）

**匹配模式**：
```yaml
# 单个模式
fileMatchPattern: "**/*.tsx"

# 特定目录
fileMatchPattern: "backend/app/**/*.py"

# 测试文件
fileMatchPattern: "**/*.test.{ts,tsx,js,jsx}"

# API 路由
fileMatchPattern: "app/api/**/*"
```

**示例**：
```markdown
---
inclusion: fileMatch
fileMatchPattern: "components/**/*.tsx"
---

# React Component Guidelines

## Component Structure
```typescript
interface Props {
  // Props definition
}

export const ComponentName: React.FC<Props> = ({ prop1, prop2 }) => {
  // Component logic
  return (
    // JSX
  );
};
```

## Naming Conventions
- PascalCase for components
- camelCase for props
- Descriptive names
```

#### 3. Manual（手动引用）

```yaml
---
inclusion: manual
---
```

**使用场景**：
- 故障排除指南
- 迁移指南
- 特殊场景文档
- 不常用的参考资料

**如何使用**：
在对话中使用 `#filename` 引用：

```
User: 遇到了数据库迁移问题
User: #database-migration-guide
```

**示例**：
```markdown
---
inclusion: manual
---

# Database Migration Troubleshooting

## Problem: Migration Fails

**Symptoms**:
- Error: "column already exists"

**Solution**:
1. Check existing schema
2. Rollback migration
3. Fix migration file
4. Re-run migration
```

### 组织多个 Steering 文件

#### 按功能域分离

```
steering/
├── core-principles.md       # inclusion: always
├── frontend-patterns.md     # inclusion: fileMatch (*.tsx)
├── backend-patterns.md      # inclusion: fileMatch (*.py)
├── api-design.md           # inclusion: fileMatch (api/**)
├── testing-guide.md        # inclusion: fileMatch (*.test.*)
└── migration-guide.md      # inclusion: manual
```

#### 在 POWER.md 中映射

```markdown
## When to Load Steering Files

### Frontend Development
**Triggered by**: React, TypeScript, component, UI
**Auto-loads**: `frontend-patterns.md` (when editing `.tsx` files)

Use context-gatherer to load additional guidance:
```python
invokeSubAgent(
    name="context-gatherer",
    prompt="Read .kiro/powers/power-name/steering/frontend-patterns.md",
    explanation="Loading frontend patterns"
)
```

### Backend Development
**Triggered by**: FastAPI, Python, API, backend
**Auto-loads**: `backend-patterns.md` (when editing `.py` files)

### Troubleshooting
**Manual load**: `#migration-guide` in chat
```

### 文件引用

在 steering 文件中引用其他文件：

```markdown
# API Standards

Refer to OpenAPI spec:
#[[file:api/openapi.yaml]]

Refer to example:
#[[file:examples/api-example.py]]
```

---

## MCP 集成

### mcp.json 配置格式

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@org/mcp-server"],
      "env": {
        "API_KEY": "${API_KEY}",
        "API_URL": "${API_URL}"
      }
    },
    "another-server": {
      "command": "python",
      "args": ["-m", "mcp_server.main"],
      "env": {
        "CONFIG_PATH": "${WORKSPACE_ROOT}/config.json"
      }
    }
  }
}
```

### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `mcpServers` | MCP 服务器配置对象 | - |
| `server-name` | 服务器唯一标识符 | `"codex"`, `"gemini"` |
| `command` | 启动命令 | `"npx"`, `"python"`, `"node"` |
| `args` | 命令参数数组 | `["-y", "@org/mcp-server"]` |
| `env` | 环境变量对象 | `{"API_KEY": "${API_KEY}"}` |

### 环境变量

**使用占位符**：
```json
{
  "env": {
    "API_KEY": "${API_KEY}",
    "API_URL": "${API_URL}",
    "WORKSPACE_ROOT": "${WORKSPACE_ROOT}"
  }
}
```

**内置占位符**：
- `${WORKSPACE_ROOT}` - 工作区根目录
- `${API_KEY}` - 从用户环境读取
- `${HOME}` - 用户主目录

**安全注意事项**：
- ✅ 使用环境变量存储密钥
- ❌ 不要在 mcp.json 中硬编码密钥
- ✅ Kiro 会自动命名空间化服务器名称避免冲突

### 完整示例

```json
{
  "mcpServers": {
    "codex": {
      "command": "npx",
      "args": ["-y", "@codexio/mcp-server"],
      "env": {
        "CODEX_API_KEY": "${CODEX_API_KEY}",
        "SANDBOX_MODE": "read-only"
      }
    },
    "gemini": {
      "command": "npx",
      "args": ["-y", "@google/gemini-mcp"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@redwoodjs/sequential-thinking-mcp"],
      "env": {}
    },
    "custom-server": {
      "command": "python",
      "args": ["-m", "custom_mcp.server"],
      "env": {
        "CONFIG_PATH": "${WORKSPACE_ROOT}/.kiro/mcp-config.json",
        "LOG_LEVEL": "info"
      }
    }
  }
}
```

### 在 POWER.md 中声明

在 frontmatter 中列出使用的 MCP 服务器：

```yaml
---
name: "gemini-fullstack"
displayName: "Gemini Full-Stack Development"
description: "Build full-stack AI applications"
keywords: ["gemini", "google", "fastapi", "react"]
mcpServers: ["codex", "gemini", "sequential-thinking"]
---
```

---

## Hooks 集成

### Hook 文件格式

Hook 文件使用 `.kiro.hook` 扩展名：

```json
{
  "enabled": true,
  "name": "Hook Name",
  "description": "What this hook does",
  "when": {
    "type": "trigger-type",
    "patterns": ["glob-pattern"]
  },
  "then": {
    "type": "action-type",
    "prompt": "Agent instruction"
  }
}
```

### 触发器类型（when.type）

#### 1. 文件触发器

| 类型 | 说明 | 需要 patterns | 示例 |
|------|------|--------------|------|
| `fileEdited` | 文件保存时 | ✅ | 格式化、lint |
| `fileCreated` | 文件创建时 | ✅ | 添加模板 |
| `fileDeleted` | 文件删除时 | ✅ | 清理关联 |

**示例**：
```json
{
  "when": {
    "type": "fileEdited",
    "patterns": ["**/*.ts", "**/*.tsx"]
  }
}
```

#### 2. 上下文触发器

| 类型 | 说明 | 需要 patterns | 可用变量 |
|------|------|--------------|---------|
| `promptSubmit` | 用户提交提示时 | ❌ | `${USER_PROMPT}` |
| `agentStop` | Agent 完成时 | ❌ | - |

**示例**：
```json
{
  "when": {
    "type": "promptSubmit"
  }
}
```

#### 3. 手动触发器

| 类型 | 说明 | 需要 patterns | 如何触发 |
|------|------|--------------|---------|
| `userTriggered` | 手动触发 | ❌ | UI 按钮或斜杠命令 |

**示例**：
```json
{
  "when": {
    "type": "userTriggered"
  },
  "description": "Review code quality"
}
```

### 动作类型（then.type）

| 动作类型 | 说明 | 可用触发器 | 参数 |
|---------|------|-----------|------|
| `askAgent` | 让 Agent 执行任务 | 所有类型 | `prompt` |
| `runCommand` | 执行 shell 命令 | `promptSubmit`, `agentStop` | `command` |

#### askAgent 示例

```json
{
  "then": {
    "type": "askAgent",
    "prompt": "Review the changed files for security issues. Check for:\n1. API keys or credentials\n2. SQL injection vulnerabilities\n3. XSS risks\n4. Hardcoded secrets\n\nProvide specific recommendations."
  }
}
```

#### runCommand 示例

```json
{
  "then": {
    "type": "runCommand",
    "command": "npm run lint -- ${FILE}"
  }
}
```

**可用变量**：
- `${FILE}` - 当前文件路径
- `${WORKSPACE_ROOT}` - 工作区根目录
- `${USER_PROMPT}` - 用户提交的提示（仅 promptSubmit）

### 完整 Hook 示例

#### 1. 文件保存时格式化

`.kiro/hooks/format-typescript.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Format TypeScript",
  "description": "Auto-format TypeScript files on save",
  "when": {
    "type": "fileEdited",
    "patterns": ["**/*.ts", "**/*.tsx"]
  },
  "then": {
    "type": "runCommand",
    "command": "npx prettier --write ${FILE}"
  }
}
```

#### 2. 文件创建时添加模板

`.kiro/hooks/add-component-template.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Add React Component Template",
  "description": "Add boilerplate when creating new React components",
  "when": {
    "type": "fileCreated",
    "patterns": ["components/**/*.tsx"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Add React component boilerplate to the new file. Include:\n1. Props interface\n2. Functional component with TypeScript\n3. Export statement\n4. JSDoc comment\n\nUse the filename to derive the component name."
  }
}
```

#### 3. Agent 完成时运行测试

`.kiro/hooks/run-tests.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Run Tests",
  "description": "Run tests after agent completes changes",
  "when": {
    "type": "agentStop"
  },
  "then": {
    "type": "runCommand",
    "command": "npm test -- --run"
  }
}
```

#### 4. 手动代码审查

`.kiro/hooks/code-review.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Code Review",
  "description": "Perform comprehensive code review",
  "when": {
    "type": "userTriggered"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Perform a comprehensive code review of recent changes. Focus on:\n\n1. **Code Quality**\n   - Readability and maintainability\n   - Adherence to best practices\n   - Code duplication\n\n2. **Performance**\n   - Potential bottlenecks\n   - Optimization opportunities\n\n3. **Security**\n   - Input validation\n   - Authentication/authorization\n   - Sensitive data handling\n\n4. **Testing**\n   - Test coverage\n   - Edge cases\n\n5. **Documentation**\n   - Code comments\n   - API documentation\n\nProvide specific, actionable recommendations."
  }
}
```

### 在 POWER.md Onboarding 中添加 Hooks

```markdown
## Onboarding

### Step 3: Add Project Hooks

Add the following hooks to enhance your workflow:

#### 1. Code Quality Hook

Create `.kiro/hooks/check-quality.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Check Code Quality",
  "description": "Verify code quality on file save",
  "when": {
    "type": "fileEdited",
    "patterns": ["src/**/*.{ts,tsx,py}"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Review this file for code quality issues. Check for:\n1. Adherence to project patterns\n2. Potential bugs\n3. Performance issues\n\nProvide brief, actionable feedback."
  }
}
```

#### 2. Security Scan Hook

Create `.kiro/hooks/security-scan.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Security Scan",
  "description": "Scan for security issues before commits",
  "when": {
    "type": "agentStop"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Scan changed files for security vulnerabilities. Report any findings."
  }
}
```

These hooks will automatically activate when you save files or complete agent tasks.
```

---

## 完整示例

### 示例 1：Gemini Full-Stack Power

**目录结构**：
```
.kiro/powers/gemini-fullstack/
├── POWER.md
├── mcp.json
└── steering/
    ├── core-principles.md
    ├── frontend-development.md
    ├── backend-development.md
    ├── gemini-integration.md
    └── troubleshooting.md
```

**POWER.md**：
```markdown
---
name: "gemini-fullstack"
displayName: "Gemini Full-Stack Development"
description: "Build full-stack AI applications with Google Gemini API, FastAPI backend, and React/TypeScript frontend."
keywords: ["gemini", "google", "ai", "fastapi", "python", "react", "typescript", "fullstack"]
mcpServers: ["codex", "gemini", "sequential-thinking"]
---

# Gemini Full-Stack Development Power

Build production-ready AI applications using Google Gemini API with a modular architecture.

## Onboarding

### Step 1: Validate Dependencies

Verify required tools:
- **Python 3.9+**: `python --version`
- **Node.js 16+**: `node --version`
- **Docker**: `docker --version` (optional)

**CRITICAL**: Install missing dependencies before proceeding.

### Step 2: Environment Setup

Create `.env.local`:
```env
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your_secret_key
```

### Step 3: Add Hooks

Create `.kiro/hooks/modular-check.kiro.hook`:
```json
{
  "enabled": true,
  "name": "Check Modular Architecture",
  "description": "Ensure files follow modular principles",
  "when": {
    "type": "fileEdited",
    "patterns": ["backend/**/*.py", "frontend/**/*.tsx"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Check if this file follows modular architecture:\n- Backend files < 300 lines\n- Frontend files < 200 lines\n- Single responsibility\n\nIf violations found, suggest refactoring."
  }
}
```

## When to Load Steering Files

### Frontend Development
**Keywords**: React, TypeScript, component, UI
**Auto-loads**: `frontend-development.md` (when editing `.tsx` files)

### Backend Development
**Keywords**: FastAPI, Python, API, backend
**Auto-loads**: `backend-development.md` (when editing `.py` files)

### Gemini Integration
**Keywords**: Gemini, Google AI, model
**Auto-loads**: `gemini-integration.md`

### Troubleshooting
**Manual**: Use `#troubleshooting` in chat

## Best Practices

### 1. Modular Architecture

**Backend**:
```python
# ✅ Good: Modular structure
# services/gemini/chat_handler.py
class ChatHandler:
    def send_message(self): ...

# services/gemini/google_service.py (coordinator)
class GoogleService:
    def __init__(self):
        self.chat = ChatHandler()
```

**Frontend**:
```typescript
// ✅ Good: Component composition
// components/chat/MessageList.tsx
export const MessageList: React.FC = ({ messages }) => { ... };

// components/chat/ChatView.tsx (coordinator)
export const ChatView: React.FC = () => {
  return <><MessageList /><InputArea /></>;
};
```

### 2. API Integration

Follow Google GenAI SDK patterns:
```python
from google import genai

client = genai.Client(api_key=settings.GOOGLE_API_KEY)
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=messages
)
```

## Common Workflows

### Add New Feature

1. Create spec documents in `.kiro/specs/feature/`
2. Use context-gatherer to read specs
3. Use Codex/Gemini MCP to generate code
4. Review and test
5. Update documentation

### Refactor Large File

1. Identify files > 300 lines (backend) or > 200 lines (frontend)
2. Analyze functionality and responsibilities
3. Create modular structure
4. Split into separate files
5. Create coordinator file
6. Update imports and tests

## Troubleshooting

### MCP Server Timeout

**Symptoms**: `MCP error -32001: Request timed out`

**Solutions**:
1. Simplify the task
2. Break into smaller steps
3. Use SESSION_ID to continue previous session

### File Size Violations

**Symptoms**: Files exceed modular limits

**Solutions**:
1. Use refactoring workflow
2. Split by functionality
3. Create coordinator pattern

## Resources

- [Google GenAI SDK](https://ai.google.dev/gemini-api/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev/)
```

**mcp.json**：
```json
{
  "mcpServers": {
    "codex": {
      "command": "npx",
      "args": ["-y", "@codexio/mcp-server"],
      "env": {
        "CODEX_API_KEY": "${CODEX_API_KEY}",
        "SANDBOX_MODE": "read-only"
      }
    },
    "gemini": {
      "command": "npx",
      "args": ["-y", "@google/gemini-mcp"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@redwoodjs/sequential-thinking-mcp"],
      "env": {}
    }
  }
}
```

**steering/core-principles.md**：
```markdown
---
inclusion: always
---

# Core Development Principles

## Modular Architecture (First Principle)

- Backend files < 300 lines
- Frontend files < 200 lines
- Each module has single responsibility
- Coordinator pattern for composition

## Security

- Never hardcode API keys
- Validate all user input
- Use prepared statements
- Encrypt sensitive data

## Testing

- Unit tests for all modules
- Integration tests for workflows
- Backend coverage > 80%
- Frontend coverage > 70%
```

**steering/frontend-development.md**：
```markdown
---
inclusion: fileMatch
fileMatchPattern: "frontend/**/*.{ts,tsx}"
---

# Frontend Development Guidelines

## Component Structure

```typescript
interface Props {
  prop1: string;
  prop2: number;
}

/**
 * ComponentName - Brief description
 *
 * @param prop1 - Description
 * @param prop2 - Description
 */
export const ComponentName: React.FC<Props> = ({ prop1, prop2 }) => {
  // Hooks
  const [state, setState] = useState();

  // Effects
  useEffect(() => {}, []);

  // Handlers
  const handleClick = () => {};

  // Render
  return (
    <div>
      {/* JSX */}
    </div>
  );
};
```

## Naming Conventions

- Components: PascalCase
- Files: ComponentName.tsx
- Props: camelCase
- Handlers: handleEventName
- Custom hooks: useFeatureName

## State Management

- Local state: useState
- Shared state: Context API
- Server state: React Query
- Forms: React Hook Form
```

---

## 最佳实践

### 1. Power 设计原则

#### 专注单一领域

✅ **Good**:
- `power-react-patterns` - React 开发模式
- `power-supabase` - Supabase 集成
- `power-testing` - 测试策略

❌ **Bad**:
- `power-everything` - 包含所有技术
- `power-misc` - 杂项集合

#### 合理使用 Keywords

✅ **Good** - 具体且相关:
```yaml
keywords: ["react", "typescript", "components", "hooks", "frontend"]
```

❌ **Bad** - 太通用:
```yaml
keywords: ["code", "build", "create", "make", "write"]
```

#### Steering 文件分离

✅ **Good**:
```
steering/
├── core.md           # inclusion: always (< 100 lines)
├── frontend.md       # inclusion: fileMatch
├── backend.md        # inclusion: fileMatch
└── migration.md      # inclusion: manual
```

❌ **Bad**:
```
steering/
└── everything.md     # inclusion: always (500 lines)
```

### 2. Onboarding 清单

每个 POWER.md 应包含：

- [ ] **Step 1**: 依赖验证
  - [ ] 列出所有必需工具
  - [ ] 提供验证命令
  - [ ] 包含安装链接

- [ ] **Step 2**: 环境配置
  - [ ] 列出环境变量
  - [ ] 提供示例配置
  - [ ] 说明密钥获取方式

- [ ] **Step 3**: Hooks 设置（可选）
  - [ ] 提供完整 hook 配置
  - [ ] 说明每个 hook 的作用
  - [ ] 标注可选/必需

### 3. 内容组织

#### POWER.md 主文件

**应该包含**：
- ✅ Onboarding 步骤
- ✅ Steering 文件映射
- ✅ Best Practices 概述
- ✅ Common Workflows
- ✅ Troubleshooting

**不应该包含**：
- ❌ 详细的 API 参考（移到 steering/reference.md）
- ❌ 完整的代码示例（移到 steering/examples.md）
- ❌ 长篇故障排除（移到 steering/troubleshooting.md）

#### Steering 文件

**应该包含**：
- ✅ 详细的技术指南
- ✅ 代码示例
- ✅ 最佳实践
- ✅ 反模式警告

**不应该包含**：
- ❌ Onboarding 步骤（应在 POWER.md）
- ❌ MCP 配置（应在 mcp.json）
- ❌ Hook 配置（应在 .kiro/hooks/）

### 4. Token 优化

#### Inclusion 策略

| 文件大小 | Inclusion 类型 | 原因 |
|---------|---------------|------|
| < 100 行 | `always` | Token 成本可接受 |
| 100-300 行 | `fileMatch` | 仅需要时加载 |
| > 300 行 | `manual` | 拆分或按需引用 |

#### 示例

✅ **Good**:
```markdown
---
inclusion: always
---

# Core Principles (80 lines)

Brief, essential guidelines...
```

❌ **Bad**:
```markdown
---
inclusion: always
---

# Everything You Need to Know (500 lines)

Detailed explanations, examples, edge cases...
```

### 5. Hooks 设计

#### 合理的粒度

✅ **Good** - 单一职责:
```json
// format-typescript.kiro.hook
{
  "name": "Format TypeScript",
  "when": {"type": "fileEdited", "patterns": ["**/*.ts"]},
  "then": {"type": "runCommand", "command": "prettier --write ${FILE}"}
}
```

❌ **Bad** - 做太多事:
```json
// do-everything.kiro.hook
{
  "name": "Format, Lint, Test, Deploy",
  "then": {
    "type": "askAgent",
    "prompt": "Format, lint, test, and deploy this file"
  }
}
```

#### 性能考虑

✅ **Good** - 轻量级检查:
```json
{
  "when": {"type": "fileEdited"},
  "then": {"type": "runCommand", "command": "quick-lint ${FILE}"}
}
```

❌ **Bad** - 重量级操作:
```json
{
  "when": {"type": "fileEdited"},
  "then": {"type": "runCommand", "command": "run-full-test-suite"}
}
```

### 6. MCP 集成

#### 环境变量安全

✅ **Good**:
```json
{
  "env": {
    "API_KEY": "${API_KEY}",  // 从环境读取
    "API_URL": "${API_URL}"
  }
}
```

❌ **Bad**:
```json
{
  "env": {
    "API_KEY": "sk-1234567890",  // 硬编码密钥
  }
}
```

#### 服务器命名

✅ **Good** - 描述性名称:
```json
{
  "mcpServers": {
    "gemini-api": { ... },
    "code-generator": { ... }
  }
}
```

❌ **Bad** - 模糊名称:
```json
{
  "mcpServers": {
    "server1": { ... },
    "mcp2": { ... }
  }
}
```

---

## 故障排除

### Power 未激活

**症状**: 提到关键词但 Power 未加载

**解决方案**:
1. 检查 Power 位置：`.kiro/powers/power-name/POWER.md`
2. 验证 frontmatter 格式正确
3. 确认 `keywords` 字段包含相关词汇
4. 重启 Kiro IDE

### Steering 文件未加载

**症状**: Steering 规则未生效

**解决方案**:
1. 检查 frontmatter `inclusion` 字段
2. 对于 `fileMatch`，验证文件模式匹配
3. 对于 `manual`，确认使用 `#filename` 引用
4. 检查文件是否在正确目录

### MCP 服务器启动失败

**症状**: MCP 工具不可用

**解决方案**:
1. 检查 `mcp.json` 格式正确
2. 验证命令和参数
3. 确认环境变量已设置
4. 查看 Kiro 日志获取错误信息

### Hooks 未触发

**症状**: Hook 未执行

**解决方案**:
1. 检查 `enabled: true`
2. 验证文件扩展名是 `.kiro.hook`
3. 确认 `patterns` 匹配正确
4. 检查 Kiro 是否处于可信工作区

---

## 参考资源

### Kiro 官方文档

- [创建 Powers](https://kiro.dev/docs/powers/create/)
- [Steering 指南](https://kiro.dev/docs/steering/)
- [Hooks 文档](https://kiro.dev/docs/hooks/)
- [Hooks 类型](https://kiro.dev/docs/hooks/types)
- [Hooks 示例](https://kiro.dev/docs/hooks/examples)

### 社区资源

- [Kiro Powers 目录](https://kiro.dev/powers/)
- [引入 Powers 博客](https://kiro.dev/blog/introducing-powers/)

---

**文档版本**：v1.0.0
**最后更新**：2026-01-10
**维护者**：技术团队

---

## Sources

- [Create powers - IDE - Docs - Kiro](https://kiro.dev/docs/powers/create/)
- [Steering - IDE - Docs - Kiro](https://kiro.dev/docs/steering/)
- [Hooks - IDE - Docs - Kiro](https://kiro.dev/docs/hooks/)
- [Hook Types - IDE - Docs - Kiro](https://kiro.dev/docs/hooks/types)
- [Hook Examples - IDE - Docs - Kiro](https://kiro.dev/docs/hooks/examples)
- [Introducing Kiro powers](https://kiro.dev/blog/introducing-powers/)
- [Powers - Kiro](https://kiro.dev/powers/)
