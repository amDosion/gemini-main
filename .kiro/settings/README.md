# Gemini Full-Stack Development Power
<!-- Version: v5.1.0 -->

## 概述

这是一个为 Kiro AI 设计的 Power，提供了使用 Google Gemini API 构建全栈 AI 应用的完整工作流程和最佳实践。

## 特性

- ✅ **指哪打哪**：精准的场景路由和工具调用
- ✅ **不爆 token**：Subagent 独立上下文，主 Agent 只接收摘要
- ✅ **完整流程**：固定的并行执行流程（上下文 → 执行 → 写入）
- ✅ **模块化架构**：遵循第一原则，每个功能独立文件
- ✅ **MCP 协作**：与 Codex、Gemini 等子 Agent 高效协作
- ✅ **场景驱动**：根据任务类型自动加载对应规则
- ✅ **测试策略**：单元测试 + 属性测试双重保障
- ✅ **安全优先**：API 密钥加密、输入验证、错误处理

## 技术栈

### 后端
- Python 3.9+
- FastAPI
- SQLAlchemy
- Google GenAI SDK
- Redis（可选）

### 前端
- TypeScript
- React
- Vite
- Tailwind CSS

## 文档结构

### 核心文档
- **唯一 Steering 文件**：`.kiro/steering/KIRO-RULES.md`
- **Power 说明**：`.kiro/powers/gemini-fullstack/POWER.md`

### 场景文档（通过 context-gatherer 按需获取）
- 前端开发：`.kiro/powers/gemini-fullstack/steering/frontend-development.md`
- 后端开发：`.kiro/powers/gemini-fullstack/steering/backend-development.md`
- Gemini 集成：`.kiro/powers/gemini-fullstack/steering/gemini-integration.md`
- 代码重构：`.kiro/powers/gemini-fullstack/steering/refactoring.md`
- MCP 协作：`.kiro/powers/gemini-fullstack/steering/mcp-collaboration.md`
- 新功能开发：`.kiro/powers/gemini-fullstack/steering/new-feature.md`

### 参考文档（通过 context-gatherer 按需获取）
- Agent 协作：`.kiro/docs/core/agents-collaboration.md`
- 项目结构：`.kiro/docs/architecture/project-structure.md`
- 开发服务器：`.kiro/docs/reference/dev-servers-management.md`
- 上下文优化：`.kiro/docs/reference/context-optimization-checklist.md`
- MCP 使用：`.kiro/docs/collaboration/mcp-usage-guide.md`

## 快速开始

### 1. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填写：

```bash
# Google Gemini API
GOOGLE_API_KEY=your_api_key_here

# 其他配置...
```

### 3. 启动开发服务器

```bash
# 后端
cd backend
uvicorn app.main:app --reload

# 前端
cd frontend
npm run dev
```

## 使用指南

### 场景识别

Kiro AI 会根据关键词自动识别场景：

| 关键词 | 场景 |
|--------|------|
| React, TypeScript, 组件, UI, 前端 | 前端开发 |
| FastAPI, Python, API, 路由, 后端 | 后端开发 |
| Gemini, Google, AI, 模型, SDK | Gemini 集成 |
| 重构, 优化, 拆分, 模块化 | 代码重构 |
| Codex, MCP, 协作, 子 Agent | MCP 协作 |
| 新功能, 需求, 设计, Spec | 新功能开发 |

### 工具使用流程

```
1. 主 Agent 识别场景
2. context-gatherer 并行读取（场景文档 + Spec + 代码）
3. general-purpose 并行执行（Codex + Sequential Thinking + Claude Code）
4. 主 Agent 写入文件（Desktop Commander）
```

## 常见问题

### Q: 如何获取场景文档？
A: 主 Agent 会自动调用 context-gatherer 获取，你不需要手动操作。

### Q: 如何获取详细参考文档？
A: 场景文档会引用详细参考文档，主 Agent 会在需要时自动获取。

### Q: 为什么不直接加载所有文档？
A: 为了避免上下文爆炸。只加载需要的文档，保持主 Agent 上下文在 10K tokens 以内。

## 贡献指南

请参考 `.kiro/docs/collaboration/mcp-usage-guide.md` 了解如何与 MCP 工具协作开发。

## 许可证

MIT License

---

**文件路径**：`.kiro/settings/README.md`  
**版本**：v5.1.0  
**状态**：✅ 路径修复，版本同步
