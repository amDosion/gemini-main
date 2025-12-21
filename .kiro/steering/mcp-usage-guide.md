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
| `PROMPT` | string | ✅ | - | 任务描述（使用英文） |
| `cd` | path | ✅ | - | 工作目录**绝对路径** |
| `sandbox` | enum | ❌ | `"read-only"` | 沙箱策略 |
| `SESSION_ID` | string | ❌ | `""` | 会话 ID，用于续问 |
| `model` | string | ❌ | `""` | 模型名称 |
| `skip_git_repo_check` | boolean | ❌ | `true` | 跳过 Git 检查 |
| `return_all_messages` | boolean | ❌ | `false` | 返回完整消息链 |

### 1.3 Sandbox 权限

| sandbox 值 | 权限 | 使用场景 |
|-----------|------|---------|
| `read-only` | 只读 | **唯一允许的模式** - 代码分析、方案设计、生成代码片段 |

**重要约束**:
- Codex **禁止**直接写入文件
- 所有文件操作必须由 `Desktop Commander MCP` 完成
- Codex 只负责生成代码内容,返回给 Kiro 后由 Kiro 写入文件

### 1.4 Kiro 调用格式（已验证 2025-12-19）

```
mcp_codex_codex(
    PROMPT="Reply with Hello from Codex to confirm the connection is working.",
    sandbox="read-only",
    cd="D:\\vue-admin\\backend"
)
```

### 1.5 返回结构（实际验证）

```json
{
  "success": true,
  "SESSION_ID": "019b3738-5472-7190-9d7d-42e3f1fb73da",
  "agent_messages": "Hello from Codex!"
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
| `PROMPT` | string | ✅ | - | 任务描述（使用英文） |
| `cd` | path | ✅ | - | 工作目录**绝对路径** |
| `sandbox` | boolean | ❌ | `false` | **必须设置为 `false`** |
| `SESSION_ID` | string | ❌ | `""` | 会话 ID |
| `model` | string | ❌ | `""` | 模型名称 |
| `return_all_messages` | boolean | ❌ | `false` | 返回完整消息链 |

### 2.3 Kiro 调用格式（已验证 2025-12-19）

```
mcp_gemini_gemini(
    PROMPT="Reply with Hello from Gemini to confirm the connection is working.",
    sandbox=false,
    cd="D:\\vue-admin\\frontend"
)
```

### 2.4 返回结构（实际验证）

```json
{
  "success": true,
  "SESSION_ID": "f0930c95-8a83-436e-af2f-82cc0dc2c1a3",
  "agent_messages": "Hello from Gemini!"
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

### 3.2 Kiro 调用格式（已验证 2025-12-19）

```
mcp_claude_code_mcp_think(
    thought="Testing Claude Code MCP connection. This is a simple test to verify the MCP service is responding correctly."
)
```

### 3.3 返回结构（实际验证）

```
Thought process: Testing Claude Code MCP connection. This is a simple test to verify the MCP service is responding correctly.
```

### 3.4 其他工具调用示例

```
# 读取文件
mcp_claude_code_mcp_readFile(
    file_path="D:\\vue-admin\\backend\\app\\main.py"
)

# 搜索代码
mcp_claude_code_mcp_grep(
    pattern="cache|缓存",
    path="D:\\vue-admin",
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

### 4.2 推荐配置（含 autoApprove）

```json
{
  "mcpServers": {
    "codex": {
      "command": "python",
      "args": ["-m", "codexmcp.cli"],
      "autoApprove": ["codex", "mcp_codex_codex"]
    },
    "gemini": {
      "command": "python",
      "args": ["-m", "geminimcp.cli"],
      "autoApprove": ["gemini", "mcp_gemini_gemini"]
    },
    "claude-code-mcp": {
      "command": "node",
      "args": ["C:\\Users\\12180\\tools\\claude-code-mcp\\dist\\index.js"],
      "autoApprove": ["bash", "readFile", "listFiles", "searchGlob", "grep", "think", "codeReview", "editFile"]
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

---

## 七、验证记录

**测试时间**：2025-12-19

| MCP 服务 | 状态 | SESSION_ID |
|---------|------|------------|
| **Gemini** | ✅ 正常 | `f0930c95-8a83-436e-af2f-82cc0dc2c1a3` |
| **Claude Code** | ✅ 正常 | - |
| **Codex** | ✅ 正常 | `019b3738-5472-7190-9d7d-42e3f1fb73da` |


---

## 八、Codex 超时问题分析

**测试时间**：2025-12-19

### 8.1 超时原因

1. **CLI 启动开销** - Codex CLI 每次调用需要初始化，加载 `~/.codex/config.toml`
2. **任务复杂度** - 文件写入任务比简单测试复杂
3. **sandbox 限制** - `read-only` 无法写文件，`workspace-write` 需要额外验证

### 8.2 正确使用方式

根据协作规则,Codex 的职责边界:

**Codex 应该做**:
- ✅ 代码分析和方案设计
- ✅ 生成代码片段(返回文本)
- ✅ 提供技术建议和最佳实践
- ✅ 多轮对话优化代码逻辑

**Codex 不应该做**:
- ❌ 直接写入文件
- ❌ 使用 `workspace-write` 模式
- ❌ 执行文件系统操作

**标准工作流**:
```
1. mcp_codex_codex(sandbox="read-only", PROMPT="生成 XXX 功能代码")
   → 返回: { "agent_messages": "生成的代码内容..." }

2. Kiro 审查代码质量

3. mcp_claude_code_mcp_codeReview(code="...")
   → 代码审查

4. mcp_desktop_commander_mcp_write_file(path="...", content="...")
   → 写入文件
```

### 8.3 超时解决方案

| 方案 | 说明 |
|------|------|
| 简化 PROMPT | 减少任务复杂度 |
| 分步执行 | 先分析，再写入 |
| 使用 Desktop Commander | 文件操作交给专门工具 |
