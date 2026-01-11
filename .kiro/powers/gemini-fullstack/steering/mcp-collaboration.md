---
inclusion: manual
---

# MCP 协作与 Subagent 并行执行指南

## 核心原则

### 1. Subagent 并行执行原则（第一原则）⭐

**Kiro 主 Agent 应该充分利用 Subagents 的并行执行能力和独立上下文空间**

#### Subagent 关键特性

| 特性 | 说明 | 优势 |
|------|------|------|
| **并行执行** | 多个 subagents 同时运行 | 大幅提升执行速度 |
| **独立上下文** | 每个 subagent 有自己的上下文窗口 | 主 Agent 上下文不被污染 |
| **自动返回结果** | Subagent 完成后自动返回结果给主 Agent | 无需手动管理 |
| **等待完成** | 主 Agent 等待所有 subagents 完成后继续 | 确保结果完整 |

#### Kiro 内置 Subagents

| Subagent | 用途 | 何时使用 |
|----------|------|---------|
| **context-gatherer** | 探索项目、收集上下文 | 读取文档、分析代码结构 |
| **general-purpose** | 并行执行所有其他任务 | 代码生成、代码审查、测试 |

---

## 标准协作流程（优化版）

### 后端开发任务流程

```
1. 主 Agent：识别任务需求
   └─ 分析用户请求，确定需要哪些信息和操作

2. 主 Agent：并行启动多个 Subagents
   ├─ Subagent 1 (context-gatherer)：读取 Spec 文档
   │  └─ 使用 readFile 读取 requirements.md, design.md, tasks.md
   │  └─ 返回：需求摘要、设计要点、任务列表
   │
   ├─ Subagent 2 (context-gatherer)：探索现有代码
   │  └─ 使用 readMultipleFiles 读取相关代码文件
   │  └─ 返回：现有模式、代码结构、最佳实践
   │
   └─ Subagent 3 (general-purpose)：查询外部文档
      └─ 使用 Context7 MCP 查询 FastAPI 文档
      └─ 返回：API 设计模式、最佳实践

3. 主 Agent：等待所有 Subagents 完成
   └─ 接收所有 Subagent 的返回结果
   └─ 主 Agent 上下文保持清洁（0 token 占用）

4. 主 Agent：综合分析结果
   └─ 整合所有 Subagent 返回的信息
   └─ 制定实施计划

5. 主 Agent：并行启动代码生成 Subagents
   ├─ Subagent 4 (general-purpose)：生成后端代码
   │  └─ 使用 Codex MCP 生成 FastAPI 路由
   │  └─ 返回：生成的代码 + SESSION_ID
   │
   └─ Subagent 5 (general-purpose)：生成测试代码
      └─ 使用 Codex MCP 生成单元测试
      └─ 返回：生成的测试代码

6. 主 Agent：等待代码生成完成
   └─ 接收所有生成的代码

7. 主 Agent：并行启动审查 Subagents
   ├─ Subagent 6 (general-purpose)：深度思考分析
   │  └─ 使用 Sequential Thinking MCP 分析代码逻辑
   │  └─ 返回：安全性分析、正确性验证
   │
   └─ Subagent 7 (general-purpose)：代码审查
      └─ 使用 Claude Code MCP 审查代码质量
      └─ 返回：代码审查报告、改进建议

8. 主 Agent：等待审查完成
   └─ 接收审查结果
   └─ 验证代码质量和正确性

9. 主 Agent：写入文件
   └─ 使用 Desktop Commander MCP 写入所有文件
   └─ 标记任务完成
```

**关键优势**：
- ✅ **并行执行**：步骤 2 的 3 个 subagents 同时运行（节省 ~70% 时间）
- ✅ **并行审查**：步骤 7 的 2 个 subagents 同时审查（节省 ~50% 时间）
- ✅ **独立上下文**：主 Agent 上下文保持清洁（0 token 占用）
- ✅ **自动返回**：所有结果自动返回给主 Agent

---

## Subagent 使用模式

### 模式 1：并行读取多个文档

**场景**：需要同时读取 Spec 文档、现有代码、外部文档

**实现**：
```python
# ✅ 正确做法：并行启动多个 subagents
# 主 Agent 发起并行任务
"Run subagents to:
1. Read requirements.md, design.md, tasks.md from .kiro/specs/feature/
2. Explore existing code in backend/app/services/
3. Query FastAPI documentation for authentication patterns"

# Kiro 自动并行启动 3 个 subagents：
# - Subagent 1: context-gatherer (读取 Spec)
# - Subagent 2: context-gatherer (探索代码)
# - Subagent 3: general-purpose (查询文档)

# 主 Agent 等待所有 subagents 完成
# 接收所有结果，上下文保持清洁
```

**时间对比**：
- ❌ 串行执行：30s + 25s + 20s = 75s
- ✅ 并行执行：max(30s, 25s, 20s) = 30s（节省 60%）

### 模式 2：并行生成前后端代码

**场景**：同时生成前端和后端代码

**实现**：
```python
# ✅ 正确做法：并行生成
"Run subagents to:
1. Use Codex MCP to generate FastAPI backend code
2. Use Gemini MCP to generate React frontend code"

# Kiro 自动并行启动 2 个 subagents：
# - Subagent 1: general-purpose (Codex 生成后端)
# - Subagent 2: general-purpose (Gemini 生成前端)

# 主 Agent 等待完成，接收两份代码
```

**时间对比**：
- ❌ 串行执行：40s + 35s = 75s
- ✅ 并行执行：max(40s, 35s) = 40s（节省 47%）

### 模式 3：并行代码生成和审查

**场景**：生成代码的同时进行代码审查

**实现**：
```python
# ✅ 正确做法：并行执行
"Run subagents to:
1. Use Codex MCP to generate new feature code
2. Use Claude Code MCP to review existing code for similar patterns"

# Kiro 自动并行启动 2 个 subagents：
# - Subagent 1: general-purpose (生成新代码)
# - Subagent 2: general-purpose (审查现有代码)

# 主 Agent 综合两者结果，确保一致性
```

### 模式 4：并行多任务执行

**场景**：同时执行多个独立任务

**实现**：
```python
# ✅ 正确做法：并行执行多个任务
"Run subagents to:
1. Generate backend API code
2. Generate frontend components
3. Generate unit tests
4. Generate integration tests
5. Update documentation"

# Kiro 自动并行启动 5 个 subagents
# 所有任务同时执行，大幅提升效率
```

**时间对比**：
- ❌ 串行执行：30s + 25s + 20s + 20s + 15s = 110s
- ✅ 并行执行：max(30s, 25s, 20s, 20s, 15s) = 30s（节省 73%）

---

## 主 Agent 职责

### 主 Agent 应该做的事

| 职责 | 说明 | 示例 |
|------|------|------|
| **任务分解** | 将复杂任务分解为可并行的子任务 | 识别需要读取的文档、生成的代码、审查步骤 |
| **Subagent 编排** | 决定启动哪些 subagents 以及并行策略 | 同时启动 3 个 context-gatherer + 2 个 general-purpose |
| **结果整合** | 综合所有 subagent 返回的结果 | 整合 Spec、代码、文档、审查结果 |
| **质量把控** | 验证生成的代码质量和正确性 | 整合 Sequential Thinking 和 Claude Code 的审查结果 |
| **最终决策** | 决定是否接受生成的代码 | 审查后决定写入文件 |
| **文件写入** | 使用 Desktop Commander MCP 写入文件 | 写入所有生成的代码 |

### 主 Agent 不应该做的事

| 禁止操作 | 原因 | 正确做法 |
|---------|------|---------|
| ❌ 直接读取大文件 | 占用主 Agent 上下文 | 使用 context-gatherer subagent |
| ❌ 直接调用 Codex/Gemini MCP | 占用主 Agent 上下文 | 使用 general-purpose subagent |
| ❌ 直接调用 Sequential Thinking/Claude Code | 占用主 Agent 上下文 | 使用 general-purpose subagent（并行审查） |
| ❌ 串行执行独立任务 | 浪费时间 | 并行启动多个 subagents |
| ❌ 重复读取相同文档 | 浪费 token | 使用 Redis MCP 缓存 |

---

## MCP 工具使用规则

### Context7 MCP（外部文档查询）

**用途**：查询外部库文档、API 文档

**使用方式**：
```python
# ✅ 在 general-purpose subagent 中使用
invokeSubAgent(
    name="general-purpose",
    prompt="""Use Context7 MCP to query FastAPI documentation:
    
    mcp_context7_query_docs(
        libraryId="/fastapi/fastapi",
        query="How to implement JWT authentication with dependencies"
    )
    
    Return the authentication patterns and best practices.""",
    explanation="Querying FastAPI authentication docs"
)
```

### Codex MCP（代码生成）

**用途**：生成后端代码（Python, FastAPI）

**使用方式**：
```python
# ✅ 在 general-purpose subagent 中使用
invokeSubAgent(
    name="general-purpose",
    prompt="""Use Codex MCP to generate FastAPI authentication code:
    
    Requirements:
    1. JWT token generation and validation
    2. Password hashing with bcrypt
    3. Pydantic models for request/response
    4. Error handling for all edge cases
    
    Use sandbox="read-only" mode.
    Working directory: D:\\gemini-main\\gemini-main\\backend
    
    Return the generated code.""",
    explanation="Generating authentication code with Codex"
)
```

### Gemini MCP（前端代码生成）

**用途**：生成前端代码（React, TypeScript）

**使用方式**：
```python
# ✅ 在 general-purpose subagent 中使用
invokeSubAgent(
    name="general-purpose",
    prompt="""Use Gemini MCP to generate React authentication components:
    
    Requirements:
    1. Login form with validation
    2. TypeScript interfaces
    3. Custom hooks for auth state
    4. Error handling UI
    
    Return the generated components.""",
    explanation="Generating auth components with Gemini"
)
```

### Sequential Thinking MCP（深度分析）

**用途**：进行深度思考分析

**使用方式**：
```python
# ✅ 在 general-purpose subagent 中使用（并行审查）
invokeSubAgent(
    name="general-purpose",
    prompt="""Use Sequential Thinking MCP to analyze the generated authentication code:
    
    mcp_sequential_thinking_sequentialthinking(
        thought="Analyze the generated auth code for security issues and logical correctness",
        totalThoughts=15,
        nextThoughtNeeded=True
    )
    
    Focus on:
    1. Security vulnerabilities
    2. Logic correctness
    3. Edge case handling
    4. Performance considerations
    
    Return the analysis results.""",
    explanation="Deep thinking analysis of auth code"
)

# ⚠️ 也可以主 Agent 直接使用（但会占用上下文）
# 仅在需要主 Agent 直接思考时使用
mcp_sequential_thinking_sequentialthinking(
    thought="Analyze task requirements and plan implementation",
    totalThoughts=10,
    nextThoughtNeeded=True
)
```

### Claude Code MCP（代码审查）

**用途**：审查代码质量和最佳实践

**使用方式**：
```python
# ✅ 在 general-purpose subagent 中使用（并行审查）
invokeSubAgent(
    name="general-purpose",
    prompt="""Use Claude Code MCP to review the generated authentication code:
    
    mcp_claude_code_mcp_codeReview(
        code=generated_auth_code
    )
    
    Focus on:
    1. Code quality and readability
    2. Best practices adherence
    3. Potential bugs
    4. Improvement suggestions
    
    Return the review report.""",
    explanation="Code quality review with Claude"
)
```

### Desktop Commander MCP（文件操作）

**用途**：写入文件、编辑文件

**使用方式**：
```python
# ✅ 主 Agent 直接使用（写入文件）
mcp_desktop_commander_mcp_write_file(
    path="D:\\gemini-main\\gemini-main\\backend\\app\\routers\\auth.py",
    content=generated_code,
    mode="rewrite"
)
```

### Redis MCP（缓存）

**用途**：缓存文档摘要，避免重复读取

**使用方式**：
```python
# ✅ 主 Agent 直接使用（缓存摘要）
# 1. 检查缓存
cached = mcp_redis_get(key="doc_summary:fastapi_auth")

if not cached:
    # 2. 读取文档（使用 subagent）
    result = invokeSubAgent(
        name="context-gatherer",
        prompt="Read FastAPI authentication docs",
        explanation="Reading docs"
    )
    
    # 3. 缓存摘要
    mcp_redis_set(
        key="doc_summary:fastapi_auth",
        value=result,
        expireSeconds=86400  # 24 hours
    )
```

---

## 完整示例：开发认证功能

### 任务：实现 JWT 认证功能

**步骤 1：主 Agent 分解任务**
```
任务分解：
1. 读取 Spec 文档（requirements.md, design.md）
2. 探索现有认证代码
3. 查询 FastAPI JWT 文档
4. 生成后端认证代码
5. 生成前端登录组件
6. 生成单元测试
7. 审查代码质量
8. 写入所有文件
```

**步骤 2：并行启动 Subagents（第一批）**
```python
# 主 Agent 发起并行任务
"Run subagents to:
1. Read .kiro/specs/auth-feature/requirements.md and design.md
2. Explore existing auth code in backend/app/services/
3. Query FastAPI documentation for JWT authentication patterns"

# Kiro 自动并行启动 3 个 subagents
# 时间：max(20s, 25s, 15s) = 25s（vs 串行 60s）
```

**步骤 3：主 Agent 整合结果**
```python
# 主 Agent 接收所有结果
# - Spec 要求：JWT token, refresh token, password hashing
# - 现有模式：BaseProviderService 继承模式
# - FastAPI 模式：Depends() 依赖注入，HTTPBearer 认证

# 主 Agent 制定实施计划
```

**步骤 4：并行启动 Subagents（第二批）**
```python
# 主 Agent 发起并行代码生成
"Run subagents to:
1. Use Codex MCP to generate FastAPI JWT authentication code
2. Use Gemini MCP to generate React login components
3. Use Codex MCP to generate unit tests for auth service"

# Kiro 自动并行启动 3 个 subagents
# 时间：max(40s, 35s, 30s) = 40s（vs 串行 105s）
```

**步骤 5：并行启动审查 Subagents（第三批）**
```python
# 主 Agent 发起并行审查
"Run subagents to:
1. Use Sequential Thinking MCP to analyze code logic and security
2. Use Claude Code MCP to review code quality and best practices"

# Kiro 自动并行启动 2 个 subagents
# 时间：max(15s, 20s) = 20s（vs 串行 35s）
```

**步骤 6：主 Agent 整合审查结果**
```python
# 主 Agent 接收审查结果
# - Sequential Thinking：安全性分析、逻辑正确性验证
# - Claude Code：代码质量报告、改进建议

# 验证：
# - JWT token 生成正确
# - 密码哈希使用 bcrypt
# - 错误处理完整
# - 测试覆盖充分
# - 代码质量符合标准
```

**步骤 7：主 Agent 写入文件**
```python
# 主 Agent 使用 Desktop Commander 写入所有文件
mcp_desktop_commander_mcp_write_file(
    path="D:\\gemini-main\\gemini-main\\backend\\app\\routers\\auth.py",
    content=backend_code,
    mode="rewrite"
)

mcp_desktop_commander_mcp_write_file(
    path="D:\\gemini-main\\gemini-main\\frontend\\components\\auth\\LoginForm.tsx",
    content=frontend_code,
    mode="rewrite"
)

mcp_desktop_commander_mcp_write_file(
    path="D:\\gemini-main\\gemini-main\\backend\\tests\\test_auth.py",
    content=test_code,
    mode="rewrite"
)
```

**总时间对比**：
- ❌ 串行执行：60s + 105s + 35s + 10s = 210s
- ✅ 并行执行：25s + 40s + 20s + 10s = 95s（节省 55%）

---

## 性能优化建议

### 1. 最大化并行度

**原则**：识别所有可以并行执行的任务

**示例**：
```python
# ❌ 错误：串行执行
"First read requirements.md, then read design.md, then read existing code"
# 时间：20s + 20s + 25s = 65s

# ✅ 正确：并行执行
"Run subagents to read requirements.md, design.md, and existing code in parallel"
# 时间：max(20s, 20s, 25s) = 25s
```

### 2. 使用缓存避免重复

**原则**：缓存文档摘要，避免重复读取

**示例**：
```python
# 检查缓存
cached = mcp_redis_get(key="doc_summary:feature_requirements")

if cached:
    # 使用缓存（0s）
    use_cached_summary(cached)
else:
    # 读取并缓存（20s）
    result = invokeSubAgent(...)
    mcp_redis_set(key="doc_summary:feature_requirements", value=result)
```

### 3. 合理分配任务

**原则**：将大任务分解为多个小任务并行执行

**示例**：
```python
# ❌ 错误：单个大任务
"Generate all authentication code including backend, frontend, and tests"
# 时间：120s

# ✅ 正确：分解为多个小任务
"Run subagents to:
1. Generate backend auth code
2. Generate frontend auth components
3. Generate unit tests
4. Generate integration tests"
# 时间：max(40s, 35s, 25s, 20s) = 40s
```

### 4. 独立上下文优势

**原则**：利用 subagent 独立上下文，主 Agent 保持清洁

**优势**：
- ✅ 主 Agent 上下文：0 token（所有文档读取在 subagent 中）
- ✅ 主 Agent 只接收摘要：~2-5K tokens
- ✅ 可以处理更复杂的任务

---

## 故障排除

### 问题 1：Subagent 超时

**症状**：`Subagent timeout after 300s`

**解决方案**：
1. 简化 subagent 任务
2. 分解为更小的子任务
3. 检查 MCP 服务器状态

### 问题 2：并行任务冲突

**症状**：多个 subagents 尝试写入同一文件

**解决方案**：
1. 只在主 Agent 中写入文件
2. Subagents 只负责生成代码
3. 主 Agent 整合后统一写入

### 问题 3：上下文污染

**症状**：主 Agent 上下文被大量文档占用

**解决方案**：
1. 检查是否直接使用 readFile（应该使用 subagent）
2. 检查是否直接调用 Codex/Gemini MCP（应该使用 subagent）
3. 使用 Redis 缓存避免重复读取

---

## 最佳实践总结

### ✅ 应该做的事

1. **并行启动多个 subagents**（最大化效率）
2. **使用 context-gatherer 读取文档**（独立上下文）
3. **使用 general-purpose 生成代码**（并行执行）
4. **使用 general-purpose 审查代码**（并行审查：Sequential Thinking + Claude Code）
5. **主 Agent 负责整合和决策**（质量把控）
6. **使用 Redis 缓存文档摘要**（避免重复）
7. **主 Agent 负责文件写入**（避免冲突）

### ❌ 不应该做的事

1. **主 Agent 直接读取大文件**（上下文爆炸）
2. **主 Agent 直接调用 Codex/Gemini**（占用上下文）
3. **主 Agent 直接调用 Sequential Thinking/Claude Code**（占用上下文，应并行审查）
4. **串行执行独立任务**（浪费时间）
5. **重复读取相同文档**（浪费 token）
6. **Subagents 直接写入文件**（可能冲突）

---

## 参考资源

- [Kiro Subagents 官方文档](https://kiro.dev/docs/subagents/)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [上下文优化检查清单](.kiro/docs/reference/context-optimization-checklist.md)
- [主 Agent 协作规则](.kiro/docs/core/agents-collaboration.md)

---

**版本**：v2.1.0  
**最后更新**：2026-01-10  
**重大变更**：
- 强调 Subagent 并行执行和独立上下文空间
- 明确 Sequential Thinking 和 Claude Code 应通过 general-purpose subagent 使用
- 添加并行审查模式（Sequential Thinking + Claude Code 同时运行）
