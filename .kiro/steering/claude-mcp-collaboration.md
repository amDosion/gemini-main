---
inclusion: always
---

# 多 MCP 协作开发规则

## 概述

本规则定义了 Kiro 与三个 AI MCP 服务（Codex、Gemini、Claude Code）的协作流程。

**文档分工**：
- 本文档：工作流程、核心理念、协作规则
- `mcp-usage-guide.md`：MCP 工具 API 参数规范

---

## 0. 全局协议 (Global Protocols)

所有操作必须严格遵循以下系统约束：

| 约束 | 说明 |
|------|------|
| **交互语言** | 与工具/模型交互使用 **English**；用户输出使用 **中文** |
| **多轮对话** | 若返回 `SESSION_ID`，必须记录并判断是否续问 |
| **沙箱安全** | 严禁 Codex/Gemini 写文件；代码生成必须要求返回 `Unified Diff Patch` |
| **代码主权** | 外部模型输出仅作逻辑参考；最终代码必须自主重写到企业级质量 |
| **风格定义** | 精简高效、无冗余；注释遵循"非必要不形成" |
| **最小变更** | 仅对需求做针对性改动，严禁影响现有功能 |
| **并行执行** | 可并行任务尽量并行；长耗时任务用 `run in background` 挂起 |
| **强制流程** | 必须完整执行所有阶段，严禁跳步 |

---

## 1. 核心理念与硬约束 (Core Philosophy & Constraints)

### 1.1 核心理念

- **协作而非依赖**：Codex/Gemini 是协作者而非裁决者；最终决策与质量由你负责
- **思辨与质疑**：必须批判性审查模型输出，必要时多轮追问与修正
- **质量为先**：目标是企业生产级可读、可维护、健壮的交付

### 1.2 关键约束（违反=任务失败）

- 必须先获取并理解上下文，禁止基于假设回答
- 禁止生成任何恶意或有害代码
- 禁止直接使用外部模型生成代码，必须自主重写
- 注释只写"必要"的，保持语言与现有注释一致
- 必须遵循工作流与代码质量标准

### 1.3 代码质量原则

| 类别 | 要求 |
|------|------|
| **架构** | 优先复用官方 SDK、成熟社区方案；严格遵循 SOLID、DRY |
| **风格** | 遵循项目既有风格；避免冗余与隐式耦合 |
| **性能** | 主动评估复杂度、内存占用；必要时落地优化 |

---

## 2. 第一阶段：Kiro 设计 Spec 文档

在任何代码实现之前，Kiro 必须先完成以下三个文档：

### 2.1 需求文档 `requirements.md`

**职责**：用户故事、验收标准、EARS 模式需求、术语表

```markdown
# Requirements Document
## Introduction
## Glossary
## Requirements
### Requirement 1
**User Story:** As a [role], I want [feature], so that [benefit]
#### Acceptance Criteria
1. WHEN [event], THE [System] SHALL [response]
```

### 2.2 设计文档 `design.md`

**职责**：系统架构、组件接口、数据模型、正确性属性、测试策略

```markdown
# Design Document
## Overview
## Architecture
## Components and Interfaces
## Data Models
## Correctness Properties
## Error Handling
## Testing Strategy
```

### 2.3 任务文档 `tasks.md`

**职责**：可执行编码任务、依赖关系、任务类型标注

```markdown
# Implementation Plan
- [ ] 1. 任务组名称
  - [ ] 1.1 后端任务：实现 XXX API
    - 类型：backend
    - Requirements: 1.1, 1.2
```

**完成标志**：Spec 文档创建完成后自动批准,直接进入任务执行阶段

---

## 3. 第二阶段：MCP 协作实现

### 3.1 MCP 角色分工

| MCP 服务 | 角色 | 职责范围 | 调用工具 |
|---------|------|---------|---------|
| **Codex** | 后端开发者 | Python、FastAPI、SQLAlchemy、Redis | `mcp_codex_codex` |
| **Gemini** | 前端开发者 | TypeScript、Vue、React、CSS | `mcp_gemini_gemini` |
| **Claude Code** | 代码分析师 | 搜索、读取、分析、审查 | `mcp_claude_code_mcp_*` |
| **Desktop Commander** | 文件操作 | 读写文件、搜索代码 | `mcp_desktop_commander_mcp_*` |

### 3.2 任务类型判断

| 类型 | 关键词 | 分配 |
|------|--------|------|
| **后端** | backend, api, endpoint, database, model, Python, FastAPI | Codex |
| **前端** | frontend, component, view, TypeScript, Vue, React | Gemini |
| **全栈** | fullstack, end-to-end, 同时涉及 API 和组件 | Codex + Gemini |

### 3.3 资源矩阵 (Resource Matrix)

| Phase | 功能 | 工具/模型 | 输入策略 | 输出约束 | 关键行为 |
|-------|------|----------|----------|----------|----------|
| **Phase 1** | 上下文检索 | Desktop Commander | 自然语言 (English) | 完整代码/定义 | 递归检索直到完整 |
| **Phase 2** | 分析规划 | Codex + Gemini | 原始需求 (English) | Step-by-step 计划 | 交叉验证消除逻辑漏洞 |
| **Phase 3A** | 前端原型 | Gemini | English, < 32k | Unified Diff Patch | 仅作视觉基准 |
| **Phase 3B** | 后端原型 | Codex | English | Unified Diff Patch | 禁止写文件 |
| **Phase 4** | 编码实施 | Claude (Self) | 内部处理 | 生产级代码 | 精简高效无冗余 |
| **Phase 5** | 审计交付 | Codex + Gemini | Diff + 目标文件 | Review 意见 | 变更后立即审计 |

---

## 4. 完整实现流程

### 4.1 阶段一：Kiro 创建 Spec 文档

```
┌─────────────────────────────────────────────────────────────┐
│  Kiro 独立完成三个文档                                       │
│  ├─ requirements.md (需求文档)                              │
│  ├─ design.md (设计文档)                                    │
│  └─ tasks.md (任务文档)                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    自动批准所有文档
                              │
                              ▼
                    进入阶段二：任务执行
```

**注意**: 在 MCP 协作模式下,Spec 文档创建完成后自动批准,无需用户手动确认。

### 4.2 阶段二：任务执行流程

#### 后端任务流程

```
┌─────────────────────────────────────────────────────────────┐
│  步骤 1：Kiro 读取 Spec 文档                                 │
│  └─ mcp_desktop_commander_mcp_read_multiple_files(...)      │
│     (requirements.md, design.md, tasks.md)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 2：Kiro 判断任务类型 → 后端任务                        │
│  关键词：backend, api, Python, FastAPI, database            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 3：Codex MCP 生成代码内容                              │
│  └─ mcp_codex_codex(                                        │
│       PROMPT="Generate XXX code...",                        │
│       sandbox="read-only",                                  │
│       cd="D:\\project\\backend"                             │
│     )                                                       │
│  ⚠️  注意：Codex 只返回代码文本，不写入文件                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 4：Sequential Thinking MCP 深度思考                    │
│  └─ 先分析调用链路深度，计算 totalThoughts                   │
│     totalThoughts = 链路深度 × 5 (每节点5个维度)            │
│                                                              │
│  └─ mcp_sequential_thinking_sequentialthinking(             │
│       thought="[节点名] 维度名 - 分析内容",                 │
│       thoughtNumber=1,                                      │
│       totalThoughts=N,  # 基于链路计算                      │
│       nextThoughtNeeded=True                                │
│     )                                                       │
│                                                              │
│  按链路顺序思考每个节点的5个维度：                            │
│  1. 输入验证 (参数类型、边界、空值)                          │
│  2. 业务逻辑 (核心逻辑、算法)                                │
│  3. 输出处理 (返回值、数据结构)                              │
│  4. 错误处理 (异常、回滚)                                    │
│  5. 性能考虑 (复杂度、内存)                                  │
│                                                              │
│  ⚠️  注意：必须完成所有思考轮次，直到 nextThoughtNeeded=False │
│  ⚠️  注意：必须按调用链路顺序，逐节点分析所有维度             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 5：验证思考结果                                        │
│  判断：是否发现问题？                                        │
│  ├─ 是 → 返回步骤 3 (重新生成代码)                          │
│  │   └─ mcp_codex_codex(                                    │
│  │        PROMPT="根据以下问题修正代码: [问题列表]",        │
│  │        SESSION_ID="<上次会话ID>",                        │
│  │        sandbox="read-only"                               │
│  │      )                                                   │
│  │   └─ 重复步骤 4-5，直到所有验证通过                      │
│  └─ 否 → 继续步骤 6                                          │
│                                                              │
│  验证通过标准：                                              │
│  ✅ 调用链路完整且正确                                       │
│  ✅ 无逻辑错误和边界问题                                     │
│  ✅ 无明显性能瓶颈                                           │
│  ✅ 无安全漏洞                                               │
│  ✅ 符合设计文档要求                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 6：Claude Code MCP 最终审查                            │
│  └─ mcp_claude_code_mcp_codeReview(                         │
│       code="<优化后的最终代码>"                             │
│     )                                                       │
│  最终检查：代码规范、注释完整性、可维护性                     │
│  ⚠️  注意：此步骤只在迭代优化完成后执行                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 7：Desktop Commander MCP 写入文件                      │
│  ├─ 新文件 → mcp_desktop_commander_mcp_write_file(...)      │
│  └─ 修改文件 → mcp_desktop_commander_mcp_edit_block(...)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 8：Kiro 标记任务完成                                   │
│  └─ taskStatus(task="1.1 实现 XXX", status="completed")     │
└─────────────────────────────────────────────────────────────┘
```

#### 前端任务流程

```
┌─────────────────────────────────────────────────────────────┐
│  步骤 1：Kiro 读取 Spec 文档                                 │
│  └─ mcp_desktop_commander_mcp_read_multiple_files(...)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 2：Kiro 判断任务类型 → 前端任务                        │
│  关键词：frontend, component, TypeScript, Vue, React        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 3：Gemini MCP 生成代码内容                             │
│  └─ mcp_gemini_gemini(                                      │
│       PROMPT="Generate XXX component...",                   │
│       sandbox=false,                                        │
│       cd="D:\\project\\frontend"                            │
│     )                                                       │
│  ⚠️  注意：Gemini 只返回代码文本，不写入文件                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 4：Sequential Thinking MCP 深度思考                    │
│  └─ 先分析组件依赖链深度，计算 totalThoughts                 │
│     totalThoughts = 链路深度 × 5 (每节点5个维度)            │
│                                                              │
│  └─ mcp_sequential_thinking_sequentialthinking(             │
│       thought="[组件名] 维度名 - 分析内容",                 │
│       thoughtNumber=1,                                      │
│       totalThoughts=N,  # 基于链路计算                      │
│       nextThoughtNeeded=True                                │
│     )                                                       │
│                                                              │
│  按依赖链顺序思考每个组件的5个维度：                          │
│  1. Props验证 (类型、必填、默认值)                           │
│  2. 状态管理 (响应式、更新逻辑)                              │
│  3. 事件处理 (emit、回调)                                    │
│  4. 生命周期 (挂载、卸载、清理)                              │
│  5. 性能优化 (渲染、内存)                                    │
│                                                              │
│  ⚠️  注意：必须完成所有思考轮次，直到 nextThoughtNeeded=False │
│  ⚠️  注意：必须按组件依赖链顺序，逐节点分析所有维度           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 5：验证思考结果                                        │
│  判断：是否发现问题？                                        │
│  ├─ 是 → 返回步骤 3 (重新生成代码)                          │
│  │   └─ mcp_gemini_gemini(                                  │
│  │        PROMPT="根据以下问题修正代码: [问题列表]",        │
│  │        SESSION_ID="<上次会话ID>",                        │
│  │        sandbox=false                                     │
│  │      )                                                   │
│  │   └─ 重复步骤 4-5，直到所有验证通过                      │
│  └─ 否 → 继续步骤 6                                          │
│                                                              │
│  验证通过标准：                                              │
│  ✅ 组件依赖链完整且正确                                     │
│  ✅ 状态管理无逻辑错误                                       │
│  ✅ 无性能问题 (渲染优化、内存泄漏)                          │
│  ✅ 用户交互流畅                                             │
│  ✅ 符合设计文档要求                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 6：Claude Code MCP 最终审查                            │
│  └─ mcp_claude_code_mcp_codeReview(                         │
│       code="<优化后的最终代码>"                             │
│     )                                                       │
│  最终检查：代码规范、注释完整性、可维护性                     │
│  ⚠️  注意：此步骤只在迭代优化完成后执行                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 7：Desktop Commander MCP 写入文件                      │
│  ├─ 新文件 → mcp_desktop_commander_mcp_write_file(...)      │
│  └─ 修改文件 → mcp_desktop_commander_mcp_edit_block(...)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 8：Kiro 标记任务完成                                   │
│  └─ taskStatus(task="2.1 实现 XXX", status="completed")     │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 关键原则

| 原则 | 说明 |
|------|------|
| **职责分离** | Codex/Gemini 只生成代码，Desktop Commander 负责文件操作 |
| **迭代优化** | Sequential Thinking 发现问题后，必须反馈给 Codex/Gemini 重新生成 |
| **质量保证** | 必须通过所有验证标准后，才进入 Claude Code 最终审查 |
| **会话延续** | 使用 `SESSION_ID` 保持上下文，避免重复说明 |
| **任务追踪** | Kiro 负责标记任务状态 |
| **沙箱安全** | Codex 使用 `read-only`，Gemini 使用 `sandbox=false` |

---

## 5. 高级工具规则

### 5.0 迭代优化循环机制

**核心理念**：代码质量通过"生成-思考-验证-修正"的迭代循环来保证。

**执行流程**：

```
┌─────────────────────────────────────────────────────────────┐
│  循环开始                                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Codex/Gemini 生成代码                                    │
│     └─ 返回：代码文本 + SESSION_ID                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Sequential Thinking 深度思考                             │
│     └─ 输出：问题列表 (如果有)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  是否发现问题？  │
                    └─────────────────┘
                       │           │
                      是           否
                       │           │
                       ▼           ▼
        ┌──────────────────┐   ┌──────────────────┐
        │  反馈给 Codex/   │   │  验证通过        │
        │  Gemini 修正     │   │  进入最终审查    │
        │  (使用SESSION_ID)│   └──────────────────┘
        └──────────────────┘
                │
                └──────► 返回步骤 1 (循环)
```

**问题反馈格式**：

```python
# 示例：反馈给 Codex 修正
mcp_codex_codex(
    PROMPT="""
    根据链路驱动的深度思考分析，发现以下问题需要修正：
    
    调用链路：login_handler → validate_user → query_database → hash_password
    
    问题列表：
    
    [login_handler 节点]
    1. 输入验证：缺少对空字符串的检查
    2. 错误处理：未捕获 validate_user 可能抛出的异常
    
    [validate_user 节点]
    3. 业务逻辑：用户验证规则不完整，未检查账户状态
    4. 输出处理：返回值类型不明确
    
    [query_database 节点]
    5. 输入验证：SQL参数未正确转义，存在注入风险
    6. 性能考虑：存在 N+1 查询问题
    
    [hash_password 节点]
    7. 业务逻辑：哈希算法强度不足
    8. 错误处理：哈希失败时未回滚
    
    请按照上述问题修正代码，并返回完整的修正后代码。
    """,
    SESSION_ID="<上次会话ID>",
    sandbox="read-only",
    cd="D:\\project\\backend"
)
```

**迭代终止条件**：

| 条件 | 说明 |
|------|------|
| ✅ 链路完整 | 所有调用节点已按顺序分析完成 |
| ✅ 维度覆盖 | 每个节点的5个维度都已检查 |
| ✅ 逻辑正确 | 无逻辑错误，边界条件已处理 |
| ✅ 性能合格 | 无明显性能瓶颈 |
| ✅ 安全无虞 | 无安全漏洞 |
| ✅ 符合设计 | 符合设计文档要求 |

**最大迭代次数**：建议不超过 3 次，如超过则需要：
1. 重新审视设计文档
2. 简化任务范围
3. 寻求用户指导

---

## 5. 高级工具规则

### 5.1 文件操作 - Desktop Commander MCP

**所有文件操作必须使用 Desktop Commander MCP**：

| 操作 | 工具 | 说明 |
|------|------|------|
| 读取文件 | `mcp_desktop_commander_mcp_read_file` | 必须使用绝对路径 |
| 批量读取 | `mcp_desktop_commander_mcp_read_multiple_files` | 一次读取多个文件 |
| 写入文件 | `mcp_desktop_commander_mcp_write_file` | mode: rewrite/append |
| 精确替换 | `mcp_desktop_commander_mcp_edit_block` | 修改现有文件 |
| 搜索代码 | `mcp_desktop_commander_mcp_start_search` | searchType: files/content |

### 5.2 深度思考 - Sequential Thinking MCP

**所有代码生成后必须使用**：

```python
mcp_sequential_thinking_sequentialthinking(
    thought="当前思考内容...",
    thoughtNumber=1,
    totalThoughts=N,  # N = 调用链路深度 × 每节点思考维度数
    nextThoughtNeeded=True
)
```

**强制使用场景**：
- ✅ **代码生成后分析** (必须) - 在 Codex/Gemini 生成代码后,Claude Code 审查前
- ✅ 架构设计
- ✅ Bug 排查
- ✅ 性能优化
- ✅ 代码重构
- ✅ 方案分析

**链路驱动思考策略**：

Sequential Thinking 的轮次必须基于实际调用链路计算，而不是预估：

**步骤 1：分析调用链路**
```
示例链路：A → B → C → D → 返回A
链路深度：4 个节点
```

**步骤 2：计算思考轮次**
```
每个节点需要分析的维度：
1. 输入参数验证
2. 业务逻辑正确性
3. 输出结果处理
4. 错误处理
5. 性能考虑

totalThoughts = 链路深度 × 5 = 4 × 5 = 20
```

**步骤 3：按链路顺序思考**

| 思考轮次 | 节点 | 维度 | 内容 |
|---------|------|------|------|
| 1-5 | A (入口) | 5个维度 | 分析函数A的输入、逻辑、输出、错误、性能 |
| 6-10 | B (A调用B) | 5个维度 | 分析A→B的参数传递、B的处理、返回给A |
| 11-15 | C (B调用C) | 5个维度 | 分析B→C的数据转换、C的逻辑、返回给B |
| 16-20 | D (C调用D) | 5个维度 | 分析C→D的调用、D的处理、返回链路 |

**思考维度（固定顺序）**：

对于每个调用节点，必须按以下顺序思考：

1. **输入验证** - 参数类型、边界条件、空值处理
2. **业务逻辑** - 核心逻辑正确性、算法合理性
3. **输出处理** - 返回值类型、数据结构、状态更新
4. **错误处理** - 异常捕获、错误传播、回滚机制
5. **性能考虑** - 时间复杂度、内存占用、优化空间

**执行要求**：
- 必须自动执行,无需用户干预
- 必须完成所有思考轮次 (直到 `nextThoughtNeeded=False`)
- 每轮思考必须有明确的结论
- **禁止跳过节点**：必须按调用链路顺序逐个分析
- **禁止合并维度**：每个维度必须独立思考

**思考完整性标准**：
- ✅ 所有调用节点已按顺序分析
- ✅ 每个节点的 5 个维度都已覆盖
- ✅ 所有数据流向已追踪完整
- ✅ 所有错误路径已考虑
- ✅ 整体性能已评估

**示例：完整调用链分析**

```
代码：用户登录功能
调用链路：login_handler → validate_user → query_database → hash_password → 返回token

totalThoughts = 4 × 5 = 20

Thought 1: [login_handler] 输入验证 - 检查username和password是否为空
Thought 2: [login_handler] 业务逻辑 - 调用validate_user的时机和参数
Thought 3: [login_handler] 输出处理 - token生成和响应封装
Thought 4: [login_handler] 错误处理 - 登录失败时的错误码
Thought 5: [login_handler] 性能考虑 - 是否需要限流

Thought 6: [validate_user] 输入验证 - 接收的参数类型是否正确
Thought 7: [validate_user] 业务逻辑 - 用户验证规则是否完整
Thought 8: [validate_user] 输出处理 - 返回用户对象还是布尔值
Thought 9: [validate_user] 错误处理 - 用户不存在时的处理
Thought 10: [validate_user] 性能考虑 - 是否需要缓存用户信息

Thought 11: [query_database] 输入验证 - SQL参数是否正确转义
Thought 12: [query_database] 业务逻辑 - 查询语句是否高效
Thought 13: [query_database] 输出处理 - 查询结果的数据结构
Thought 14: [query_database] 错误处理 - 数据库连接失败的处理
Thought 15: [query_database] 性能考虑 - 是否存在N+1查询

Thought 16: [hash_password] 输入验证 - 密码字符串是否有效
Thought 17: [hash_password] 业务逻辑 - 哈希算法是否安全
Thought 18: [hash_password] 输出处理 - 哈希值的存储格式
Thought 19: [hash_password] 错误处理 - 哈希失败时的处理
Thought 20: [hash_password] 性能考虑 - 哈希计算的时间成本
```

### 5.3 上下文持久化 - Redis MCP

**Key 命名规范**：

| Key 模式 | 用途 |
|---------|------|
| `spec:{name}:context` | 任务进度、已完成任务、关键文件 |
| `spec:{name}:decisions` | 设计决策记录 |
| `api:contract:{endpoint}` | API 契约定义 |

### 5.4 后端 API 分析 - FastAPI MCP

```python
mcp_fastapi_mcp_server_analyze_fastapi_structure()
mcp_fastapi_mcp_server_get_api_endpoints()
mcp_fastapi_mcp_server_get_data_models()
```

---

## 6. 代码审查标准

| 类别 | 检查项 |
|-----|-------|
| **错误** | 逻辑错误、边界条件、空值处理、异常处理 |
| **安全** | SQL 注入、XSS、CSRF、敏感数据暴露、认证授权 |
| **性能** | N+1 查询、内存泄漏、不必要的计算、缓存策略 |
| **规范** | 命名规范、代码风格、注释完整性、类型注解 |
| **测试** | 可测试性、边界用例覆盖 |

---

## 7. 工具选择速查表

| 需求 | 工具 |
|------|------|
| 读取/写入文件 | `mcp_desktop_commander_mcp_*` |
| 搜索代码 | `mcp_desktop_commander_mcp_start_search` |
| 深度思考 | `mcp_sequential_thinking_sequentialthinking` |
| 代码审查 | `mcp_claude_code_mcp_codeReview` |
| 后端开发 | `mcp_codex_codex` |
| 前端开发 | `mcp_gemini_gemini` |
| API 分析 | `mcp_fastapi_mcp_server_*` |
| 上下文存储 | `mcp_redis_*` |
| Lint 检查 | `mcp_eslint_mcp_lint_files` |

---

## 8. 执行检查清单

### 8.1 阶段一：Spec 文档创建

- [ ] Kiro 创建 `requirements.md`
- [ ] Kiro 创建 `design.md`
- [ ] Kiro 创建 `tasks.md`
- [ ] 自动批准所有文档 (无需用户确认)

### 8.2 阶段二：后端任务执行

- [ ] 读取 Spec 文档 (Desktop Commander)
- [ ] 判断任务类型为后端
- [ ] Codex 生成代码内容 (`sandbox="read-only"`)
- [ ] Sequential Thinking 链路驱动深度思考
  - [ ] 分析调用链路深度 (例如：A→B→C→D = 4个节点)
  - [ ] 计算 totalThoughts = 链路深度 × 5
  - [ ] 按链路顺序，逐节点分析5个维度
  - [ ] 确认 `nextThoughtNeeded=False`
- [ ] 验证思考结果
  - [ ] 如发现问题 → 反馈给 Codex 重新生成 (使用 `SESSION_ID`)
  - [ ] 重复"生成-思考-验证"循环，直到所有验证通过
- [ ] Claude Code 最终审查 (仅在验证通过后执行)
- [ ] Desktop Commander 写入文件
- [ ] Kiro 标记任务完成

### 8.3 阶段二：前端任务执行

- [ ] 读取 Spec 文档 (Desktop Commander)
- [ ] 判断任务类型为前端
- [ ] Gemini 生成代码内容 (`sandbox=false`)
- [ ] Sequential Thinking 链路驱动深度思考
  - [ ] 分析组件依赖链深度 (例如：父组件→子组件→服务→API = 4个节点)
  - [ ] 计算 totalThoughts = 链路深度 × 5
  - [ ] 按依赖链顺序，逐节点分析5个维度
  - [ ] 确认 `nextThoughtNeeded=False`
- [ ] 验证思考结果
  - [ ] 如发现问题 → 反馈给 Gemini 重新生成 (使用 `SESSION_ID`)
  - [ ] 重复"生成-思考-验证"循环，直到所有验证通过
- [ ] Claude Code 最终审查 (仅在验证通过后执行)
- [ ] Desktop Commander 写入文件
- [ ] Kiro 标记任务完成

### 8.4 关键约束

1. **禁止跳步**：必须按顺序执行所有步骤
2. **禁止直接写文件**：Codex/Gemini 不得使用文件写入功能
3. **必须链路驱动思考**：代码生成后必须先分析调用链路，计算 totalThoughts = 链路深度 × 5
4. **必须按序分析**：必须按调用链路顺序，逐节点分析5个维度，禁止跳过或合并
5. **必须迭代优化**：发现问题必须反馈给 Codex/Gemini 重新生成，不得跳过
6. **必须验证通过**：只有所有验证标准通过后，才能进入 Claude Code 最终审查
7. **必须最终审查**：所有代码必须经过 Claude Code 最终审查
8. **必须标记**：每个任务完成后必须调用 `taskStatus`
