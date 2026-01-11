---
inclusion: manual
---

# Kiro 主 Agent 与 Subagents 协作规则

> 📌 **快速导航**：本文档是 `.kiro/steering/KIRO-RULES.md` 的详细参考。
> 
> - 如需快速查询场景路由，请查看 **KIRO-RULES.md** 的快速路由表
> - 如需快速查询禁止操作，请查看 **KIRO-RULES.md** 的禁止操作表
> - 本文档提供详细的 Agent 协作流程、角色定义、工作流程示例、Token 节省数据

---

## ⚠️ 核心架构原则

**Kiro 使用两种专用 subagents**：
1. **context-gatherer subagent**: 探索项目和收集相关上下文（读取文档/代码）
2. **general-purpose subagent**: 并行执行所有其他任务（代码生成/分析/文件操作）

**关键特性**：
- ✅ Subagents 有**独立的上下文空间**，不占用主 Agent token
- ✅ Subagents 可以**并行执行**多个任务
- ✅ 主 Agent 只接收**摘要结果**，不是完整内容
- ✅ 经过测试验证：可以读取 28K+ tokens 而不影响主 Agent

---

## 📋 快速参考

> 💡 **提示**：这些表格也在 KIRO-RULES.md 中以简化版本列出。本文档提供详细的 Token 节省数据和使用示例。

### 工具使用优先级

| 优先级 | 工具 | 用途 | Token 节省 | 何时使用 |
|-------|------|------|-----------|---------|
| 🥇 **最高** | **context-gatherer subagent** | 读取项目文档/代码 | 100% (主 Agent 0 token) | 读取 Spec、代码、项目文档 |
| 🥈 **最高** | **Context7 MCP** | 读取外部文档 | 90% (20K → 2K) | 读取外部库文档、API 文档 |
| 🥉 **高** | **general-purpose subagent** | 代码生成/审查/文件操作 | 90% (30K → 3K) | 调用 Codex/Gemini/Claude Code，使用 Kiro 原生工具写入文件 |
| 4️⃣ **中** | **Redis MCP** | 缓存摘要 | 避免重复 | 缓存文档摘要 |

### 禁止操作

> 💡 **完整的禁止操作列表请查看 `.kiro/steering/KIRO-RULES.md` 的"禁止操作"表格**

---

## 1. 角色定义

### 1.1 Kiro 主 Agent（你自己）

**职责**：
- 任务分解与编排
- 启动和协调 subagents
- 接收和整合 subagent 结果
- 最终决策和质量把控
- 任务状态追踪与更新

**工具集**：
- `invokeSubAgent`: 启动 context-gatherer 或 general-purpose subagent
- `Context7 MCP`: 读取外部库文档（FastAPI、React 等）
- `Redis MCP`: 缓存文档摘要
- `taskStatus`: 更新任务状态

**禁止使用**：
- ❌ `readFile` / `readMultipleFiles`（使用 context-gatherer 代替）
- ❌ 直接调用 Codex/Gemini/Claude Code MCP（使用 general-purpose subagent 代替）
- ❌ 直接使用 Kiro 原生工具写入文件（使用 general-purpose subagent 代替）

### 1.2 context-gatherer subagent

**用途**：探索项目和收集相关上下文

**何时使用**：
- 读取项目内部文档（Spec、Steering、README）
- 探索现有代码模式
- 查找相关文件
- 理解项目结构

**关键特性**：
- ✅ 有独立的上下文空间
- ✅ 可以使用 readFile 和 readMultipleFiles
- ✅ 返回摘要给主 Agent
- ✅ 不占用主 Agent token

**调用示例**：
```python
invokeSubAgent(
    name="context-gatherer",
    prompt="""使用 readFile 读取 .kiro/specs/feature/requirements.md
    
    请提供：
    1. 主要需求摘要
    2. 关键的 acceptance criteria
    3. 技术约束""",
    explanation="Reading requirements document"
)
```

### 1.3 general-purpose subagent

**用途**：并行执行任务（代码生成、审查、文件操作等）

**何时使用**：
- 调用 Codex MCP 生成后端代码
- 调用 Gemini MCP 生成前端代码
- 调用 Sequential Thinking MCP 进行深度分析
- 调用 Claude Code MCP 进行代码审查
- 使用 Kiro 原生工具写入/编辑文件（fsWrite/strReplace/fsAppend）
- 并行执行多个任务

**关键特性**：
- ✅ 有独立的上下文空间
- ✅ 可以并行运行多个实例
- ✅ 自动返回结果给主 Agent
- ✅ 不占用主 Agent token

**调用示例**：
```python
invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Codex MCP to generate authentication API code.
    
    Requirements:
    1. FastAPI router with JWT authentication
    2. Password hashing with bcrypt
    3. Input validation with Pydantic
    
    Use sandbox="read-only" mode.
    Working directory: D:\\project\\backend""",
    explanation="Parallel code generation with Codex"
)
```

---

## 2. 标准协作流程

### 2.1 后端任务流程（完整示例）

```
步骤 1：Kiro 主 Agent 读取 Spec 文档
└─ 使用 Context7 MCP 读取外部库文档（如需要）
└─ 或使用 context-gatherer 读取项目 Spec：
   invokeSubAgent(
     name="context-gatherer",
     prompt="Read .kiro/specs/feature/requirements.md and design.md",
     explanation="Reading Spec documents"
   )

步骤 2：Kiro 主 Agent 探索现有代码
└─ 启动 context-gatherer subagent：
   invokeSubAgent(
     name="context-gatherer",
     prompt="Read backend authentication files and analyze patterns",
     explanation="Gathering code context"
   )

步骤 3：Kiro 主 Agent 启动并行代码生成
└─ 启动 general-purpose subagent（Codex）：
   invokeSubAgent(
     name="general-task-execution",
     prompt="Use Codex MCP to generate authentication code",
     explanation="Parallel code generation"
   )
└─ 返回：生成的代码 + SESSION_ID

步骤 4：Kiro 主 Agent 启动并行深度分析
└─ 启动 general-purpose subagent（Sequential Thinking）：
   invokeSubAgent(
     name="general-task-execution",
     prompt="Use Sequential Thinking MCP to analyze generated code",
     explanation="Parallel code analysis"
   )

步骤 5：Kiro 主 Agent 验证分析结果
├─ 发现问题 → 启动新的 general-purpose subagent 修正
│   └─ 返回步骤 3，重复"生成-分析-修正"循环
└─ 验证通过 → 继续步骤 6

步骤 6：Kiro 主 Agent 启动并行代码审查
└─ 启动 general-purpose subagent（Claude Code）：
   invokeSubAgent(
     name="general-task-execution",
     prompt="Use Claude Code MCP to review final code",
     explanation="Parallel code review"
   )

步骤 7：Kiro 主 Agent 启动文件写入
└─ 启动 general-purpose subagent（文件操作）：
   invokeSubAgent(
     name="general-task-execution",
     prompt="Use Kiro native tools to write files:\n- fsWrite(path='...', text='...') for new files\n- strReplace(file='...', old='...', new='...') for modifications\n- fsAppend(file='...', text='...') for appending",
     explanation="File operations through subagent"
   )

步骤 8：Kiro 主 Agent 标记任务完成
└─ taskStatus(task="1.1 实现 XXX", status="completed")
```

### 2.2 前端任务流程（完整示例）

```
步骤 1：Kiro 主 Agent 读取 Spec 文档
└─ 使用 context-gatherer 读取项目 Spec

步骤 2：Kiro 主 Agent 探索现有代码
└─ 启动 context-gatherer subagent

步骤 3：Kiro 主 Agent 启动并行代码生成
└─ 启动 general-purpose subagent（Gemini）：
   invokeSubAgent(
     name="general-task-execution",
     prompt="Use Gemini MCP to generate React component",
     explanation="Parallel code generation"
   )

步骤 4-8：与后端流程相同
```

---

## 3. 并行执行模式

### 3.1 最大化并行执行

**核心原则**：Subagents 可以并行运行，主 Agent 等待所有 subagents 完成后继续。

**示例：并行生成和分析**

```python
# 同时启动多个 subagents
subagent1 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Codex to generate backend code",
    explanation="Backend code generation"
)

subagent2 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Gemini to generate frontend code",
    explanation="Frontend code generation"
)

subagent3 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Sequential Thinking to analyze architecture",
    explanation="Architecture analysis"
)

# 主 Agent 自动等待所有 subagents 完成
# 然后整合结果并继续
```

### 3.2 并行审查模式

```python
# 同时启动多个审查 subagents
review1 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Sequential Thinking to analyze security",
    explanation="Security analysis"
)

review2 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Claude Code to review code quality",
    explanation="Code quality review"
)

# 主 Agent 整合所有审查结果
```

---

## 4. 迭代优化机制

### 4.1 核心理念

代码质量通过"生成-分析-验证-修正"的迭代循环来保证。

### 4.2 迭代流程

```
┌─────────────────────────────────────┐
│  1. general-purpose subagent        │
│     生成代码（Codex/Gemini）        │
│     返回: 代码文本 + SESSION_ID     │
└─────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│  2. general-purpose subagent        │
│     深度分析（Sequential Thinking） │
│     输出: 问题列表 (如果有)         │
└─────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ 是否发现问题？ │
        └───────────────┘
           │         │
          是         否
           │         │
           ▼         ▼
    ┌──────────┐  ┌──────────┐
    │ 反馈修正 │  │ 验证通过 │
    │ (续问)   │  │ 进入审查 │
    └──────────┘  └──────────┘
           │
           └──► 返回步骤 1 (循环)
```

---

## 5. 主 Agent 职责边界

### 5.1 主 Agent 应该做的

**Kiro 主 Agent 应该**：
- ✅ 使用 Context7 MCP 读取外部库文档
- ✅ 使用 context-gatherer subagent 读取项目文档和代码
- ✅ 使用 general-purpose subagent 调用所有 MCP 工具和执行文件操作
- ✅ 最大化并行执行（多个 subagents）
- ✅ 整合 subagent 结果并做出决策
- ✅ 使用 Redis MCP 缓存文档摘要

### 5.2 主 Agent 不应该做的

**Kiro 主 Agent 不应该**：
- ❌ 直接使用 readFile 或 readMultipleFiles
- ❌ 直接调用 Codex/Gemini MCP
- ❌ 直接调用 Sequential Thinking MCP
- ❌ 直接调用 Claude Code MCP
- ❌ 直接使用 Kiro 原生工具写入文件（fsWrite/strReplace/fsAppend）
- ❌ 使用 Desktop Commander MCP 读取或写入文件
- ❌ 在验证失败时继续执行

### 5.3 必须事项

**Kiro 主 Agent 必须**：
- ✅ 所有文件读取通过 context-gatherer subagent
- ✅ 所有 MCP 工具调用通过 general-purpose subagent
- ✅ 所有文件写入操作通过 general-purpose subagent（使用 Kiro 原生工具）
- ✅ 最大化利用并行执行能力

---

## 6. 会话上下文管理

### 6.1 SESSION_ID 使用

**何时使用 SESSION_ID**：
- 需要续问或修正代码时
- 保持对话上下文连续性
- 避免重复传递大量上下文

**示例**：
```python
# 第一次调用
result1 = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Codex to generate initial code",
    explanation="Initial generation"
)
# 返回：code + SESSION_ID

# 续问修正
result2 = invokeSubAgent(
    name="general-task-execution",
    prompt=f"Use Codex with SESSION_ID={result1.SESSION_ID} to fix issue X",
    explanation="Code correction"
)
```

---

## 7. 最佳实践总结

### 7.1 核心原则

1. **永远不要直接读取文件** - 使用 context-gatherer subagent
2. **永远不要直接调用 MCP 工具** - 使用 general-purpose subagent
3. **最大化并行执行** - 同时启动多个 subagents
4. **使用 SESSION_ID 续问** - 保持上下文连续性
5. **缓存文档摘要** - 使用 Redis MCP 避免重复读取

### 7.2 性能优化

- ✅ Subagents 有独立上下文空间（主 Agent 0 token）
- ✅ 并行执行多个任务（提升效率）
- ✅ 缓存文档摘要（避免重复读取）
- ✅ 使用 Context7 MCP 读取外部文档（90% token 节省）

### 7.3 质量保证

- ✅ "生成-分析-验证-修正"迭代循环
- ✅ 并行审查（Sequential Thinking + Claude Code）
- ✅ 主 Agent 最终决策和质量把控

