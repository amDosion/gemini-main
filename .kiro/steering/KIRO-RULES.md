---
inclusion: always
---

# Kiro AI 开发规则（唯一 Steering 文件）
<!-- Version: v5.1.1 -->

## ⚠️ 核心原则

**指哪打哪 + 不爆 token + 完整流程**

---

## 📋 快速路由表

| 关键词 | 场景文档 | 加载方式 |
|--------|---------|---------|
| React, TypeScript, 组件, UI, 前端 | `frontend-development.md` | fileMatch 自动 |
| FastAPI, Python, API, 路由, 后端 | `backend-development.md` | fileMatch 自动 |
| Gemini, Google, AI, 模型, SDK | `gemini-integration.md` | manual 点名 |
| 重构, 优化, 拆分, 模块化 | `refactoring.md` | manual 点名 |
| Codex, MCP, 协作, 子 Agent | `mcp-collaboration.md` | manual 点名 |
| 新功能, 需求, 设计, Spec | `new-feature.md` | manual 点名 |

**场景文档路径**：`.kiro/powers/gemini-fullstack/steering/{scenario}.md`

---

## 🔧 工具使用策略

### 主 Agent 职责（仅路由和协调）

```
1. 识别场景（根据关键词）
2. 调用 context-gatherer 读取场景文档
3. 调用 context-gatherer 读取项目文档/代码
4. 调用 general-purpose 执行生成/分析
5. 使用 Desktop Commander 写入文件
```

### 工具调用规则（简化版）

| 工具 | 调用者 | 用途 |
|------|--------|------|
| **Context7 MCP** | Main Agent 直接 | 外部库文档（FastAPI/React/Gemini SDK） |
| **context-gatherer** | Main Agent 调用 | 项目文档/代码（Spec/Steering/代码文件） |
| **general-purpose** | Main Agent 调用 | 代码生成/分析（Codex/Gemini/Sequential Thinking） |
| **Desktop Commander** | Main Agent 直接 | 文件操作（写入/编辑，不读取） |
| **Redis MCP** | Main Agent 直接 | 缓存摘要 |

**详细的 Token 节省数据和使用示例**：见 `.kiro/docs/core/agents-collaboration.md`

### 禁止操作

| ❌ 禁止 | ✅ 正确 |
|---------|---------|
| 主 Agent 直接 readFile | context-gatherer + readFile |
| 主 Agent 直接 readMultipleFiles | context-gatherer + readMultipleFiles |
| 主 Agent 直接调用 Codex/Gemini | general-purpose + Codex/Gemini |
| 主 Agent 直接调用 Sequential Thinking | general-purpose + Sequential Thinking |
| 使用 fsWrite/fsAppend/strReplace | Desktop Commander MCP |
| Context7 读取项目 Spec | context-gatherer + readFile |
| Desktop Commander 读取文档 | context-gatherer + readFile |

---

## 🔄 固定执行流程（高层视图）

```
用户请求
  ↓
主 Agent 识别场景
  ↓
并行阶段 1：上下文获取
  ├─ context-gatherer 读取场景文档
  ├─ context-gatherer 读取 Spec 文档
  └─ context-gatherer 读取代码文件
  ↓
主 Agent 接收摘要（2-5K tokens）
  ↓
并行阶段 2：执行
  ├─ general-purpose + Codex 生成代码
  ├─ general-purpose + Sequential Thinking 分析
  └─ general-purpose + Claude Code 审查
  ↓
主 Agent 接收结果（3K tokens）
  ↓
主 Agent 写入文件（Desktop Commander）
  ↓
完成
```

**详细的 Mermaid 流程图和并行策略**：见 `.kiro/docs/core/agents-collaboration.md`

---

## 📚 详细文档获取方式

当场景文档不够详细时，使用 context-gatherer 获取参考文档：

| 文档类型 | 路径 | 何时使用 |
|---------|------|---------|
| **Agent 协作详解** | `.kiro/docs/core/agents-collaboration.md` | 需要详细的 Agent 协作流程、角色定义、工作流程示例、Token 节省数据 |
| 项目结构 | `.kiro/docs/architecture/project-structure.md` | 需要了解项目目录结构 |
| 开发服务器 | `.kiro/docs/reference/dev-servers-management.md` | 需要管理开发服务器 |
| 上下文优化 | `.kiro/docs/reference/context-optimization-checklist.md` | 需要详细的工具使用检查清单 |
| MCP 使用 | `.kiro/docs/collaboration/mcp-usage-guide.md` | 需要详细的 MCP 工具使用指南 |

**获取方式**：
```python
invokeSubAgent(
    name="context-gatherer",
    prompt="Read {document_path} and provide summary",
    explanation="Getting detailed reference"
)
```

---

## 🎯 核心开发原则

1. **模块化架构**：后端 < 300 行，前端 < 200 行
2. **安全优先**：JWT + API 密钥加密 + 输入验证
3. **测试覆盖**：单元测试 + 属性测试
4. **文档同步**：代码注释包含参考文档链接

---

## 🆘 故障排除

### 不确定使用哪个场景？
1. 查看"快速路由表"
2. 如仍不确定，调用 context-gatherer 获取多个场景文档摘要对比

### 场景规则不够详细？
1. 场景文档会引用详细参考文档
2. 调用 context-gatherer 获取引用的详细文档
3. 优先查看 `agents-collaboration.md` 了解 Agent 协作机制

### 多个场景同时适用？
按优先级：新功能 > 具体技术 > 协作方式

### 不确定工具调用方式？
查看 `agents-collaboration.md` 的详细工具使用优先级表和代码示例

---

**文件路径**：`.kiro/steering/KIRO-RULES.md`  
**版本**：v5.1.1  
**这是唯一的 Steering 文件**：所有其他文档都通过 context-gatherer 按需获取
