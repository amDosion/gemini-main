# 冲突修复总结报告 v2

**日期**：2026-01-10  
**修复范围**：`.kiro` 目录（排除 `specs`）

---

## 🔍 发现的冲突和重复

### 1. 文件操作方式冲突

**问题**：
- `mcp-collaboration.md` 中多处说使用 Desktop Commander MCP 写入文件
- `context-optimization-checklist.md` 中错误示例使用 Desktop Commander MCP
- `POWER.md` 中多处 Hook 提示使用 Desktop Commander MCP

**正确做法**：
- ✅ 文件写入/编辑必须通过 **general-purpose subagent** 使用 Kiro 原生工具

### 2. 文档读取方式冲突

**问题**：
- `context-optimization-checklist.md` 第 138 行错误地建议使用 Context7 MCP 读取项目 Spec

**正确做法**：
- ✅ 读取项目文档必须使用 **context-gatherer subagent**
- ✅ Context7 MCP 仅用于外部库文档

---

## ✅ 已修复的文件

### 1. `.kiro/powers/gemini-fullstack/steering/mcp-collaboration.md`

**修复内容**：
- ✅ 第 86 行：更新文件写入步骤说明
- ✅ 第 201 行：更新主 Agent 职责表
- ✅ 第 347-359 行：更新 Desktop Commander MCP 章节为文件操作章节
- ✅ 第 467-505 行：更新文件写入代码示例
- ✅ 第 599 行：更新应该做的事列表

### 2. `.kiro/docs/reference/context-optimization-checklist.md`

**修复内容**：
- ✅ 第 138-157 行：修复读取 Spec 文档的检查清单和示例
- ✅ 第 329-347 行：修复文件修改的示例代码
- ✅ 第 440-450 行：修复错误示例的修正代码

### 3. `.kiro/powers/gemini-fullstack/POWER.md`

**修复内容**：
- ✅ 第 168 行：更新创建测试文件的 Hook 提示
- ✅ 第 189 行：更新添加许可证标头的 Hook 提示
- ✅ 第 210 行：更新生成组件样板的 Hook 提示
- ✅ 第 295 行：更新提供上下文的 Hook 提示
- ✅ 第 379 行：更新生成 API 文档的 Hook 提示
- ✅ 第 549 行：更新 MCP 协作工作流说明

---

## 📋 统一后的规则

### 文档读取规则

| 文档类型 | 使用工具 | 调用方式 |
|---------|---------|---------|
| **项目文档**（Spec/Steering/代码） | context-gatherer subagent | `invokeSubAgent(name="context-gatherer", ...)` |
| **外部库文档**（FastAPI/React/Gemini SDK） | Context7 MCP | `mcp_context7_query_docs(...)` |

### 文件写入规则

| 操作类型 | 使用工具 | 调用方式 |
|---------|---------|---------|
| **新文件** | general-purpose subagent + Kiro 原生工具 | `invokeSubAgent(name="general-task-execution", prompt="Use fsWrite(...)", ...)` |
| **修改文件** | general-purpose subagent + Kiro 原生工具 | `invokeSubAgent(name="general-task-execution", prompt="Use strReplace(...)", ...)` |
| **追加内容** | general-purpose subagent + Kiro 原生工具 | `invokeSubAgent(name="general-task-execution", prompt="Use fsAppend(...)", ...)` |

---

## 🎯 核心原则（已统一）

1. **文档读取**：
   - ✅ 项目文档 → context-gatherer subagent
   - ✅ 外部库文档 → Context7 MCP（主 Agent 直接）
   - ❌ 禁止主 Agent 直接 readFile/readMultipleFiles
   - ❌ 禁止使用 Desktop Commander 读取文档
   - ❌ 禁止使用 Context7 MCP 读取项目 Spec

2. **文件写入**：
   - ✅ 通过 general-purpose subagent 使用 Kiro 原生工具（fsWrite/strReplace/fsAppend）
   - ❌ 禁止主 Agent 直接使用 Kiro 原生工具
   - ❌ 禁止使用 Desktop Commander MCP

3. **代码生成**：
   - ✅ 通过 general-purpose subagent 调用 Codex/Gemini
   - ❌ 禁止主 Agent 直接调用 MCP 工具

---

## ✅ 验证清单

- [x] KIRO-RULES.md 中的工具调用规则已统一
- [x] mcp-collaboration.md 中的所有示例已修正
- [x] context-optimization-checklist.md 中的所有示例已修正
- [x] POWER.md 中的所有 Hook 提示已更新
- [x] agents-collaboration.md 中的流程示例已更新
- [x] mcp-usage-guide.md 中的文件操作章节已更新
- [x] 所有文档中的禁止操作表已统一
- [x] 所有文档中的检查清单已更新
- [x] 快速参考部分已修正

---

## 📝 后续建议

1. **定期检查**：建议在每次更新文档时检查是否遵循统一规则
2. **自动化验证**：可以考虑添加 Hook 来自动检查文档中的工具使用方式
3. **文档同步**：确保所有相关文档（包括场景文档和 Hook 提示）都遵循这些规则

---

**修复完成时间**：2026-01-10  
**修复者**：AI Assistant  
**状态**：✅ 已完成
