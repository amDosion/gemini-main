# CLAUDE.md

## AI 协作开发指南

本项目使用多 MCP 协作开发模式。详细规则请参考：

| 文档 | 路径 | 内容 |
|------|------|------|
| **协作流程** | `.kiro/steering/claude-mcp-collaboration.md` | 工作流程、核心理念、协作规则、工具选择 |
| **API 参考** | `.kiro/steering/mcp-usage-guide.md` | MCP 工具参数规范、配置、故障排除 |

---

## 快速参考

### 核心约束

- **交互语言**：工具交互用 English，用户输出用中文
- **沙箱安全**：Codex/Gemini 禁止写文件，必须返回 `Unified Diff Patch`
- **代码主权**：外部模型输出仅作参考，最终代码必须自主重写

### MCP 分工

| MCP | 职责 | 配置 |
|-----|------|------|
| Codex | 后端开发 | `sandbox="read-only"` |
| Gemini | 前端开发 | `sandbox=false` |
| Desktop Commander | 文件读写 | 绝对路径 |
| Claude Code | 代码审查 | - |

### 工作流程

1. **读取 Spec** → Desktop Commander
2. **深度分析** → Sequential Thinking
3. **生成代码** → Codex (后端) / Gemini (前端)
4. **写入文件** → Desktop Commander
5. **代码审查** → Claude Code
6. **保存上下文** → Redis
