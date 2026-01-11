---
inclusion: manual
---

# MCP 工具使用指南

## ⚠️ 关键架构原则

**MCP 工具使用规则**：

### 必须通过 subagent 使用的 MCP 工具

| MCP 工具 | 使用方式 | 禁止操作 |
|---------|---------|---------|
| Codex MCP | 通过 general-purpose subagent | ❌ 主 Agent 直接调用 |
| Gemini MCP | 通过 general-purpose subagent | ❌ 主 Agent 直接调用 |
| Sequential Thinking MCP | 通过 general-purpose subagent | ❌ 主 Agent 直接调用 |
| Claude Code MCP | 通过 general-purpose subagent | ❌ 主 Agent 直接调用 |

### 主 Agent 可以直接使用的 MCP 工具

| MCP 工具 | 使用方式 | 允许操作 |
|---------|---------|---------|
| Context7 MCP | 主 Agent 可以直接使用 | ✅ 读取外部库文档 |
| Redis MCP | 主 Agent 可以直接使用 | ✅ 缓存摘要 |

**重要说明**：
- ❌ **Desktop Commander MCP 不应用于文件操作**
- ✅ 文件写入/编辑应使用 **Kiro 原生工具**（fsWrite/strReplace/fsAppend）

---

## 概述

本文档提供 MCP 工具的 API 参考和使用示例。

**重要提醒**：
- ✅ 使用 general-purpose subagent 调用 Codex/Gemini/Sequential Thinking/Claude Code
- ✅ 使用 context-gatherer subagent 读取项目文档和代码
- ❌ 主 Agent 不要直接调用这些 MCP 工具

---

## 一、Codex MCP（后端代码生成）

### 1.1 工具信息

- **工具名称**：`mcp_codex_codex`
- **用途**：后端代码生成（Python、FastAPI、SQLAlchemy）
- **使用方式**：**必须通过 general-purpose subagent**

### 1.2 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `PROMPT` | string | ✅ | - | 任务描述（使用英文） |
| `cd` | path | ✅ | - | 工作目录**绝对路径** |
| `sandbox` | enum | ❌ | `"read-only"` | 沙箱策略 |
| `SESSION_ID` | string | ❌ | `""` | 会话 ID，用于续问 |
| `model` | string | ❌ | `""` | 模型名称 |
| `return_all_messages` | boolean | ❌ | `false` | 返回完整消息链 |

### 1.3 Sandbox 权限

| sandbox 值 | 权限 | 使用场景 |
|-----------|------|---------|
| `read-only` | 只读 | **唯一允许的模式** - 代码分析、方案设计、生成代码片段 |

**重要约束**:
- Codex **禁止**直接写入文件
- 所有文件操作必须通过 general-purpose subagent 使用 Kiro 原生工具完成

### 1.4 正确使用方式（通过 subagent）

```python
# ✅ 正确做法：通过 general-purpose subagent
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Codex MCP to generate authentication API code.
    
    Call mcp_codex_codex with:
    - PROMPT: "Generate FastAPI authentication router with JWT..."
    - cd: "D:\\project\\backend"
    - sandbox: "read-only"
    
    Return the generated code.""",
    explanation="Parallel code generation with Codex"
)

# ❌ 错误做法：主 Agent 直接调用
# result = mcp_codex_codex(PROMPT="...", cd="...", sandbox="read-only")
# 问题：占用主 Agent 上下文，违反架构原则
```

### 1.5 续问模式（使用 SESSION_ID）

```python
# 第一次调用
result1 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Codex to generate initial authentication code",
    explanation="Initial generation"
)
# 返回：code + SESSION_ID

# 续问修正
result2 = invokeSubAgent(
    name="general-task-execution",
    prompt=f"""Use Codex with SESSION_ID={result1.SESSION_ID} to:
    1. Add password hashing
    2. Improve error handling
    3. Add input validation""",
    explanation="Code refinement"
)
```

---

## 二、Gemini MCP（前端代码生成）

### 2.1 工具信息

- **工具名称**：`mcp_gemini_gemini`
- **用途**：前端代码生成（TypeScript、React、Vue）
- **使用方式**：**必须通过 general-purpose subagent**

### 2.2 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `PROMPT` | string | ✅ | - | 任务描述（使用英文） |
| `cd` | path | ✅ | - | 工作目录**绝对路径** |
| `sandbox` | boolean | ❌ | `false` | 沙箱模式 |
| `SESSION_ID` | string | ❌ | `""` | 会话 ID，用于续问 |
| `model` | string | ❌ | `""` | 模型名称 |
| `return_all_messages` | boolean | ❌ | `false` | 返回完整消息链 |

### 2.3 正确使用方式（通过 subagent）

```python
# ✅ 正确做法：通过 general-purpose subagent
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Gemini MCP to generate React authentication component.
    
    Call mcp_gemini_gemini with:
    - PROMPT: "Generate React component for login form with TypeScript..."
    - cd: "D:\\project\\frontend"
    - sandbox: false
    
    Return the generated component code.""",
    explanation="Parallel component generation with Gemini"
)

# ❌ 错误做法：主 Agent 直接调用
# result = mcp_gemini_gemini(PROMPT="...", cd="...", sandbox=False)
# 问题：占用主 Agent 上下文，违反架构原则
```

---

## 三、Sequential Thinking MCP（深度分析）

### 3.1 工具信息

- **工具名称**：`mcp_sequential_thinking_sequentialthinking`
- **用途**：深度思考和分析
- **使用方式**：**必须通过 general-purpose subagent**

### 3.2 参数定义

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `thought` | string | ✅ | 当前思考步骤 |
| `thoughtNumber` | integer | ✅ | 当前思考编号 |
| `totalThoughts` | integer | ✅ | 总思考步骤数 |
| `nextThoughtNeeded` | boolean | ✅ | 是否需要下一步 |

### 3.3 正确使用方式（通过 subagent）

```python
# ✅ 正确做法：通过 general-purpose subagent
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Sequential Thinking MCP to analyze the generated authentication code.
    
    Analyze these aspects:
    1. Security vulnerabilities
    2. Error handling completeness
    3. Input validation coverage
    4. Code structure and modularity
    5. Performance considerations
    
    Use totalThoughts=5 for comprehensive analysis.""",
    explanation="Parallel code analysis with Sequential Thinking"
)

# ❌ 错误做法：主 Agent 直接调用
# result = mcp_sequential_thinking_sequentialthinking(
#     thought="...", thoughtNumber=1, totalThoughts=5, nextThoughtNeeded=True
# )
# 问题：占用主 Agent 上下文，违反架构原则
```

---

## 四、Claude Code MCP（代码审查）

### 4.1 工具列表

| 工具名称 | 用途 | 使用方式 |
|---------|------|---------|
| `mcp_claude_code_mcp_think` | 深度思考 | 通过 general-purpose subagent |
| `mcp_claude_code_mcp_codeReview` | 代码审查 | 通过 general-purpose subagent |
| `mcp_claude_code_mcp_readFile` | 读取文件 | 通过 general-purpose subagent |
| `mcp_claude_code_mcp_grep` | 内容搜索 | 通过 general-purpose subagent |

### 4.2 正确使用方式（通过 subagent）

```python
# ✅ 正确做法：通过 general-purpose subagent
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Claude Code MCP to review the authentication code.
    
    Call mcp_claude_code_mcp_codeReview with the generated code.
    
    Focus on:
    1. Code quality and best practices
    2. Security issues
    3. Performance problems
    4. Maintainability concerns""",
    explanation="Parallel code review with Claude Code"
)

# ❌ 错误做法：主 Agent 直接调用
# result = mcp_claude_code_mcp_codeReview(code="...")
# 问题：占用主 Agent 上下文，违反架构原则
```

---

## 五、Context7 MCP（外部文档）

### 5.1 工具信息

- **工具名称**：`mcp_context7_query_docs`
- **用途**：读取外部库文档（FastAPI、React 等）
- **使用方式**：**主 Agent 可以直接使用**

### 5.2 参数定义

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `libraryId` | string | ✅ | 库 ID（如 `/fastapi/fastapi`） |
| `query` | string | ✅ | 查询问题 |

### 5.3 使用方式

```python
# ✅ 主 Agent 可以直接使用
result = mcp_context7_query_docs(
    libraryId="/fastapi/fastapi",
    query="How to implement JWT authentication in FastAPI"
)
# 返回：结构化文档摘要（~2K tokens）
```

---

## 六、文件操作（通过 general-purpose subagent）

### 6.1 工具信息

- **用途**：文件写入和编辑
- **使用方式**：**通过 general-purpose subagent 使用 Kiro 原生工具**
- **禁止用途**：❌ 主 Agent 不要直接使用 Kiro 原生工具或 Desktop Commander MCP

### 6.2 主要工具

| 工具名称 | 用途 | 何时使用 |
|---------|------|---------|
| `fsWrite` | 写入新文件 | 创建新文件（通过 subagent） |
| `strReplace` | 编辑文件 | 修改现有文件（通过 subagent） |
| `fsAppend` | 追加内容 | 在文件末尾追加内容（通过 subagent） |

### 6.3 使用方式

```python
# ✅ 正确做法：通过 general-purpose subagent
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Kiro native tools to write files:

1. Write new file:
fsWrite(
    path="backend/app/routers/auth.py",
    text="\"\"\"from fastapi import APIRouter
# ... code ...
\"\"\"
)

2. Modify existing file:
strReplace(
    file="backend/app/main.py",
    old="# TODO: Add auth router",
    new="from app.routers import auth\\napp.include_router(auth.router)"
)

3. Append content:
fsAppend(
    file="backend/app/main.py",
    text="\\n# Additional configuration"
)""",
    explanation="File operations through subagent"
)

# ❌ 错误做法 1：主 Agent 直接使用 Kiro 原生工具
# fsWrite(path="...", text="...")
# 问题：不符合架构规范

# ❌ 错误做法 2：使用 Desktop Commander MCP
# mcp_desktop_commander_mcp_write_file(...)
# 问题：不符合架构规范
```

---

## 七、Redis MCP（缓存）

### 7.1 工具信息

- **用途**：缓存文档摘要
- **使用方式**：**主 Agent 可以直接使用**

### 7.2 主要工具

| 工具名称 | 用途 |
|---------|------|
| `mcp_redis_set` | 存储缓存 |
| `mcp_redis_get` | 获取缓存 |

### 7.3 使用方式

```python
# 存储文档摘要
mcp_redis_set(
    key="spec:feature:requirements",
    value=requirements_summary,
    expireSeconds=3600
)

# 获取缓存
cached = mcp_redis_get(key="spec:feature:requirements")
if cached:
    # 使用缓存的摘要
    pass
else:
    # 调用 context-gatherer 重新读取
    pass
```

---

## 八、完整工作流程示例

### 8.1 后端开发流程

```python
# 步骤 1：读取 Spec（使用 context-gatherer）
spec = invokeSubAgent(
    name="context-gatherer",
    prompt="Read requirements.md and design.md for authentication feature",
    explanation="Reading Spec documents"
)

# 步骤 2：探索现有代码（使用 context-gatherer）
code_context = invokeSubAgent(
    name="context-gatherer",
    prompt="Read existing authentication code and analyze patterns",
    explanation="Gathering code context"
)

# 步骤 3：生成代码（使用 general-purpose + Codex）
generated_code = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Codex MCP to generate authentication API based on Spec",
    explanation="Code generation"
)

# 步骤 4：深度分析（使用 general-purpose + Sequential Thinking）
analysis = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Sequential Thinking MCP to analyze generated code",
    explanation="Code analysis"
)

# 步骤 5：代码审查（使用 general-purpose + Claude Code）
review = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Claude Code MCP to review code quality",
    explanation="Code review"
)

# 步骤 6：写入文件（通过 general-purpose subagent）
file_result = invokeSubAgent(
    name="general-task-execution",
    prompt=f"Use Kiro native tools to write the generated code to file:\nfsWrite(path='backend/app/routers/auth.py', text='''{generated_code}''')",
    explanation="File operations through subagent"
)
```

---

## 九、最佳实践总结

### 9.1 工具使用规则

| 工具类型 | 使用方式 | 原因 |
|---------|---------|------|
| Codex/Gemini/Sequential Thinking/Claude Code | 通过 general-purpose subagent | 避免占用主 Agent 上下文 |
| 项目文档/代码读取 | 通过 context-gatherer subagent | 独立上下文空间，返回摘要 |
| 外部库文档 | Context7 MCP（主 Agent 直接使用） | 已优化为摘要格式 |
| 文件写入 | 通过 general-purpose subagent + Kiro 原生工具 | 符合架构规范，主 Agent 0 token |
| 缓存 | Redis MCP（主 Agent 直接使用） | 避免重复读取 |

### 9.2 性能优化

- ✅ 使用 subagents 避免上下文爆炸（主 Agent 0 token）
- ✅ 并行执行多个 subagents 提升效率
- ✅ 使用 Redis 缓存避免重复读取
- ✅ 使用 SESSION_ID 续问保持上下文

### 9.3 质量保证

- ✅ "生成-分析-审查-修正"迭代循环
- ✅ 并行审查（Sequential Thinking + Claude Code）
- ✅ 主 Agent 最终决策和质量把控

