# KIRO-RULES 冲突修复报告

**日期**：2026-01-10  
**修复范围**：`.kiro` 目录（排除 `specs`）

---

## 🔍 发现的冲突

### 1. 文档读取方式冲突

**问题**：
- `context-optimization-checklist.md` 第 52-58 行错误地建议使用 Context7 MCP 读取项目 Spec 文档
- 但第 37 行和第 61 行明确禁止使用 Context7 读取项目 Spec

**正确做法**：
- ✅ 读取项目文档（Spec/Steering/代码）必须使用 **context-gatherer subagent**
- ✅ Context7 MCP 仅用于读取外部库文档（FastAPI/React/Gemini SDK）

### 2. 文件写入方式冲突

**问题**：
- `KIRO-RULES.md` 第 38、48、86 行说使用 Kiro 原生工具（fsWrite/strReplace/fsAppend）
- 但 `agents-collaboration.md` 和 `context-optimization-checklist.md` 多处说使用 Desktop Commander MCP

**正确做法**：
- ✅ 文件写入/编辑必须使用 **Kiro 原生工具**（fsWrite/strReplace/fsAppend）
- ❌ 禁止使用 Desktop Commander MCP 写入文件

---

## ✅ 已修复的文件

### 1. `.kiro/steering/KIRO-RULES.md`

**修复内容**：
- ✅ 第 48 行：将 "Desktop Commander" 改为 "Kiro 原生工具"
- ✅ 添加重要说明，明确文档读取和文件写入的正确方式

**修复后的工具调用规则**：
```
| **Kiro 原生工具** | Main Agent 直接 | 文件操作（fsWrite/strReplace/fsAppend） |
```

**新增说明**：
- ✅ 读取项目文档必须使用 context-gatherer subagent
- ✅ 文件写入/编辑必须使用 Kiro 原生工具
- ❌ 禁止使用 Desktop Commander MCP 读取或写入文件

### 2. `.kiro/docs/reference/context-optimization-checklist.md`

**修复内容**：
- ✅ 第 23 行：优先级表中的工具名称
- ✅ 第 36 行：禁止操作表中的正确做法
- ✅ 第 52-58 行：读取文档流程示例（改为使用 context-gatherer）
- ✅ 第 110-116 行：文件写入流程示例（改为使用 Kiro 原生工具）
- ✅ 第 287-293 行：场景 5 检查清单
- ✅ 第 480-499 行：错误示例修正
- ✅ 第 552-555 行：读取文档检查清单
- ✅ 第 577-582 行：写入文件检查清单
- ✅ 第 649-665 行：故障排除部分
- ✅ 第 673-678 行：总结部分
- ✅ 第 690-708 行：快速参考部分

### 3. `.kiro/docs/core/agents-collaboration.md`

**修复内容**：
- ✅ 第 41 行：优先级表中的工具名称
- ✅ 第 65 行：主 Agent 工具集说明
- ✅ 第 192-193 行：文件写入步骤示例
- ✅ 第 324 行：主 Agent 应该做的列表
- ✅ 第 334 行：主 Agent 不应该做的列表
- ✅ 第 343 行：主 Agent 必须做的列表

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
| **新文件** | Kiro 原生工具 | `fsWrite(path="...", text="...")` |
| **修改文件** | Kiro 原生工具 | `strReplace(file="...", old="...", new="...")` |
| **追加内容** | Kiro 原生工具 | `fsAppend(file="...", text="...")` |

---

## 🎯 核心原则（已统一）

1. **文档读取**：
   - ✅ 项目文档 → context-gatherer subagent
   - ✅ 外部库文档 → Context7 MCP
   - ❌ 禁止主 Agent 直接 readFile/readMultipleFiles
   - ❌ 禁止使用 Desktop Commander 读取文档

2. **文件写入**：
   - ✅ 使用 Kiro 原生工具（fsWrite/strReplace/fsAppend）
   - ❌ 禁止使用 Desktop Commander MCP

3. **代码生成**：
   - ✅ 通过 general-purpose subagent 调用 Codex/Gemini
   - ❌ 禁止主 Agent 直接调用 MCP 工具

---

## ✅ 验证清单

- [x] KIRO-RULES.md 中的工具调用规则已统一
- [x] context-optimization-checklist.md 中的所有示例已修正
- [x] agents-collaboration.md 中的流程示例已更新
- [x] 所有文档中的禁止操作表已统一
- [x] 所有文档中的检查清单已更新
- [x] 快速参考部分已修正

---

## 📝 后续建议

1. **定期检查**：建议在每次更新文档时检查是否遵循统一规则
2. **自动化验证**：可以考虑添加 Hook 来自动检查文档中的工具使用方式
3. **文档同步**：确保所有相关文档（包括场景文档）都遵循这些规则

---

**修复完成时间**：2026-01-10  
**修复者**：AI Assistant  
**状态**：✅ 已完成
