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

**完成标志**：用户明确批准所有三个文档

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

## 4. 实现流程

```
┌─────────────────────────────────────────────────────────────┐
│  步骤 0：恢复上下文                                          │
│  └─ mcp_redis_get("spec:{name}:context")                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 1：读取 Spec 文档（Desktop Commander）                 │
│  └─ mcp_desktop_commander_mcp_read_multiple_files(...)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 2：深度思考分析（Sequential Thinking）                 │
│  └─ mcp_sequential_thinking_sequentialthinking(...)         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 3：搜索相关代码（Desktop Commander）                   │
│  └─ mcp_desktop_commander_mcp_start_search(...)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 4：生成代码                                            │
│  ├─ 后端 → mcp_codex_codex(sandbox="read-only")             │
│  └─ 前端 → mcp_gemini_gemini(sandbox=false)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 5：写入文件（Desktop Commander）                       │
│  ├─ 新文件 → mcp_desktop_commander_mcp_write_file           │
│  └─ 修改 → mcp_desktop_commander_mcp_edit_block             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 6：代码审查（Claude Code + Sequential Thinking）       │
│  ├─ mcp_claude_code_mcp_codeReview(code)                    │
│  └─ mcp_sequential_thinking_sequentialthinking(自问自答)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 7：保存上下文（Redis）                                 │
│  └─ mcp_redis_set("spec:{name}:context", ...)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 8：标记任务完成                                        │
│  └─ taskStatus(task, "completed")                           │
└─────────────────────────────────────────────────────────────┘
```

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

**复杂任务必须使用**：

```python
mcp_sequential_thinking_sequentialthinking(
    thought="当前思考内容...",
    thoughtNumber=1,
    totalThoughts=5,
    nextThoughtNeeded=True
)
```

**必须使用场景**：架构设计、Bug 排查、性能优化、代码重构、方案分析

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

## 8. 注意事项

1. **前提条件**：必须先有 Kiro 设计的三个 Spec 文档
2. **顺序执行**：先读文档，再逐个执行任务
3. **正确分配**：后端用 Codex，前端用 Gemini
4. **必须审查**：每次代码修改后必须审查
5. **Codex 配置**：`sandbox="read-only"`（生成代码由 Desktop Commander 写入）
6. **Gemini 配置**：`sandbox=false`
