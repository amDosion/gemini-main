---
inclusion: always
---

# AI MCP 服务 API 参考

本文档定义三个 AI MCP 服务的调用方法和参数规范。

**工作流程请参考**：`claude-mcp-collaboration.md`

---

## 概述

| MCP 服务 | 工具名称 | 职责 | 适用场景 |
|---------|---------|------|---------|
| **Codex** | `mcp_codex_codex` | 后端开发 | Python、FastAPI、数据库、API |
| **Gemini** | `mcp_gemini_gemini` | 前端开发 | TypeScript、Vue、React、CSS |
| **Claude Code** | `mcp_claude_code_mcp_*` | 代码分析 | 搜索、读取、审查、思考 |

---

## 一、Codex MCP

### 1.1 工具信息

- **工具名称**：`mcp_codex_codex`
- **用途**：后端代码生成（Python、FastAPI、SQLAlchemy）

### 1.2 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `PROMPT` | string | ✅ | - | 任务描述 |
| `cd` | path | ✅ | - | 工作目录**绝对路径** |
| `sandbox` | enum | ❌ | `"read-only"` | 沙箱策略 |
| `SESSION_ID` | string | ❌ | `""` | 会话 ID，用于续问 |
| `model` | string | ❌ | `""` | 模型名称 |
| `skip_git_repo_check` | boolean | ❌ | `true` | 跳过 Git 检查 |
| `return_all_messages` | boolean | ❌ | `false` | 返回完整消息链 |

### 1.3 Sandbox 权限

| sandbox 值 | 权限 | 使用场景 |
|-----------|------|---------|
| `read-only` | 只读 | 代码分析、方案设计 |
| `workspace-write` | 工作区写入 | 代码生成（需要直接写文件时） |

### 1.4 调用示例

```python
mcp_codex_codex(
    PROMPT="分析当前项目的认证逻辑，给出改进建议。",
    cd="D:\\gemini-main\\gemini-main\\backend",
    sandbox="read-only"
)
```

### 1.5 返回结构

```json
{
  "success": true,
  "SESSION_ID": "019b3152-04ac-78d1-95dd-3920b2a12c84",
  "agent_messages": "生成的代码内容..."
}
```

---

## 二、Gemini MCP

### 2.1 工具信息

- **工具名称**：`mcp_gemini_gemini`
- **用途**：前端代码生成（TypeScript、Vue、React）

### 2.2 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `PROMPT` | string | ✅ | - | 任务描述 |
| `cd` | path | ✅ | - | 工作目录**绝对路径** |
| `sandbox` | boolean | ❌ | `false` | **必须设置为 `false`** |
| `SESSION_ID` | string | ❌ | `""` | 会话 ID |
| `model` | string | ❌ | `""` | 模型名称 |
| `return_all_messages` | boolean | ❌ | `false` | 返回完整消息链 |

### 2.3 调用示例

```python
mcp_gemini_gemini(
    PROMPT="创建 Vue 3 缓存状态组件 CacheStatus.vue",
    cd="D:\\gemini-main\\gemini-main\\frontend",
    sandbox=false
)
```

### 2.4 返回结构

```json
{
  "success": true,
  "SESSION_ID": "xyz789",
  "agent_messages": "生成的 Vue 组件代码..."
}
```

---

## 三、Claude Code MCP

### 3.1 工具列表

| 工具名称 | 用途 | 必填参数 |
|---------|------|---------|
| `mcp_claude_code_mcp_bash` | 执行 Shell 命令 | `command` |
| `mcp_claude_code_mcp_readFile` | 读取文件 | `file_path` |
| `mcp_claude_code_mcp_listFiles` | 列出目录 | `path` |
| `mcp_claude_code_mcp_searchGlob` | 文件名搜索 | `pattern` |
| `mcp_claude_code_mcp_grep` | 内容搜索 | `pattern` |
| `mcp_claude_code_mcp_think` | 深度思考 | `thought` |
| `mcp_claude_code_mcp_codeReview` | 代码审查 | `code` |
| `mcp_claude_code_mcp_editFile` | 编辑文件 | `file_path`, `content` |

### 3.2 调用示例

```python
# 读取文件
mcp_claude_code_mcp_readFile(
    file_path="D:\\gemini-main\\gemini-main\\backend\\app\\main.py"
)

# 搜索代码
mcp_claude_code_mcp_grep(
    pattern="cache|缓存",
    path="D:\\gemini-main\\gemini-main",
    include="*.ts"
)

# 代码审查
mcp_claude_code_mcp_codeReview(
    code="def get_user(id): return db.query(User).filter(User.id == id).first()"
)
```

---

## 四、MCP 配置

### 4.1 配置位置

- **Kiro 工作区**：`.kiro/settings/mcp.json`
- **Codex CLI**：`~/.codex/config.toml`

### 4.2 推荐配置

```json
{
  "mcpServers": {
    "codex": {
      "command": "python",
      "args": ["-m", "codexmcp.cli"]
    },
    "gemini": {
      "command": "python",
      "args": ["-m", "geminimcp.cli"]
    },
    "claude-code-mcp": {
      "command": "node",
      "args": ["C:\\Users\\12180\\tools\\claude-code-mcp\\dist\\index.js"]
    }
  }
}
```

### 4.3 安装依赖

```bash
# Codex MCP
pip install git+https://github.com/GuDaStudio/codexmcp.git

# Gemini MCP
pip install git+https://github.com/GuDaStudio/geminimcp.git

# Codex CLI
npm install -g @openai/codex
```

---

## 五、已知问题与解决方案

### 5.1 Codex 超时

**症状**：`MCP error -32001: Request timed out`

**原因**：Codex CLI 启动时加载 `~/.codex/config.toml` 中的 MCP 服务器

**验证**：
```bash
npx @openai/codex exec --sandbox read-only --cd D:\your\project --json -- "请回复 Hello"
```

### 5.2 Gemini 需要 Docker

**症状**：`Error: Sandbox mode requires Docker`

**解决**：设置 `sandbox=false`

### 5.3 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `Request timed out` | Codex 启动慢 | 简化 PROMPT |
| `Sandbox mode requires Docker` | sandbox=true | 设置 `sandbox=false` |
| `shutil.which('codex') returns None` | PATH 问题 | 确保 npm bin 在 PATH |

---

## 六、验证 CLI

```bash
# Codex
npx @openai/codex --version
npx @openai/codex login status

# Python 模块
python -c "import codexmcp; print('codexmcp OK')"
python -c "import geminimcp; print('geminimcp OK')"
```
