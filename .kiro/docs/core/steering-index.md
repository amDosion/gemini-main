# Steering 规则文档索引
<!-- Version: v5.1.0 -->

本目录包含 Kiro AI 的 Steering 规则文件，用于指导 AI 理解项目规范和最佳实践。

## 📚 架构说明

**核心理念**：指哪打哪 + 不爆 token + 完整流程

- **主 Agent** 只加载 `KIRO-RULES.md`（唯一的 steering 文件）
- **场景规则** 通过 `context-gatherer` 子 Agent 按需获取
- **详细文档** 在需要时通过子 Agent 获取

---

## 🎯 文档层级结构

```
Level 1: KIRO-RULES.md (.kiro/steering/)
         ↓ 自动加载到主 Agent（唯一的 steering 文件）
         
Level 2: Scenario Documents (.kiro/powers/gemini-fullstack/steering/)
         ↓ 通过 context-gatherer 按需获取
         
Level 3: Reference Documents (.kiro/docs/)
         ↓ 通过 context-gatherer 按需获取（当 Level 2 不够详细时）
```

---

## 📋 当前 Steering 文件

### 核心文件（1个）

| 文件 | 说明 | 包含模式 |
|------|------|---------|
| `.kiro/steering/KIRO-RULES.md` | **唯一的 Steering 文件**（路由表 + 工具策略 + 流程骨架） | `always` |

**说明**：所有详细的场景规则和参考文档已移至 `.kiro/powers/gemini-fullstack/steering/` 和 `.kiro/docs/` 目录，通过 context-gatherer 按需获取。

---

## 🗂️ 场景文档（Level 2）

位于 `.kiro/powers/gemini-fullstack/steering/`，通过 `context-gatherer` 按需获取：

| 场景 | 文档 | 何时使用 | Inclusion |
|------|------|---------|-----------|
| **前端开发** | `frontend-development.md` | 开发 React/TypeScript 组件、UI 功能 | `fileMatch: frontend/**/*.{ts,tsx,js,jsx}` |
| **后端开发** | `backend-development.md` | 开发 FastAPI 服务、API 端点 | `fileMatch: backend/**/*.py` |
| **Gemini 集成** | `gemini-integration.md` | 集成 Google Gemini API 功能 | `manual` |
| **代码重构** | `refactoring.md` | 重构现有代码、优化架构 | `manual` |
| **MCP 协作** | `mcp-collaboration.md` | 使用 MCP 工具进行协作开发 | `manual` |
| **新功能开发** | `new-feature.md` | 从零开始开发新功能 | `manual` |

---

## 📖 参考文档（Level 3）

位于 `.kiro/docs/`，在需要详细信息时通过 `context-gatherer` 获取：

### 核心文档

| 文档 | 说明 | Inclusion |
|------|------|-----------|
| `.kiro/docs/core/agents-collaboration.md` | Kiro 主 Agent 与 Subagents 协作规则 | `manual` |
| `.kiro/docs/core/steering-index.md` | 本文档（Steering 文档索引） | `manual` |

### 架构文档

| 文档 | 说明 | Inclusion |
|------|------|-----------|
| `.kiro/docs/architecture/project-structure.md` | 项目结构和目录说明 | `manual` |
| `.kiro/docs/architecture/modular-architecture-guide.md` | 模块化架构原则 | `manual` |

### 参考文档

| 文档 | 说明 | Inclusion |
|------|------|-----------|
| `.kiro/docs/reference/dev-servers-management.md` | 开发服务器管理规范 | `manual` |
| `.kiro/docs/reference/context-optimization-checklist.md` | 上下文优化检查清单 | `manual` |

### 协作文档

| 文档 | 说明 | Inclusion |
|------|------|-----------|
| `.kiro/docs/collaboration/mcp-usage-guide.md` | MCP 工具使用指南 | `manual` |

---

## 🔄 固定执行流程

```
1. 主 Agent 识别场景（根据关键词）
2. context-gatherer 并行读取（场景文档 + Spec + 代码）
3. general-purpose 并行执行（Codex + Sequential Thinking + Claude Code）
4. 主 Agent 写入文件（Desktop Commander）
```

---

## 📝 如何获取文档

### 获取场景文档
```python
invokeSubAgent(
    name="context-gatherer",
    prompt="Read .kiro/powers/gemini-fullstack/steering/{scenario}.md",
    explanation="Getting scenario rules"
)
```

### 获取参考文档
```python
invokeSubAgent(
    name="context-gatherer",
    prompt="Read .kiro/docs/{category}/{document}.md",
    explanation="Getting detailed reference"
)
```

---

**文件路径**：`.kiro/docs/core/steering-index.md`  
**版本**：v5.1.0  
**状态**：✅ 路径统一，版本同步
