# Kiro Hooks 配置指南

本目录包含 Kiro 项目的所有 Hook 配置文件。

## Hook 文件格式

Kiro 支持两种 Hook 配置格式：

### 1. JSON 格式（推荐）

用于 `.kiro.hook` 文件：

```json
{
  "enabled": true,
  "name": "hook-name",
  "description": "Hook description",
  "when": {
    "type": "promptSubmit"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Message to agent"
  }
}
```

### 2. YAML 格式（备选）

用于简单的 Hook 配置：

```yaml
when: <触发条件>
then: <执行动作>
```

## 触发条件（when）

### JSON 格式触发条件

| 触发类型 | when 配置 | 可用变量 | 说明 |
|---------|----------|---------|------|
| `promptSubmit` | `{"type": "promptSubmit"}` | `${MESSAGE}`, `${WORKSPACE}` | 用户提交消息时 |
| `fileEdited` | `{"type": "fileEdited"}` | `${FILE}`, `${WORKSPACE}` | 文件编辑时 |
| `fileCreated` | `{"type": "fileCreated"}` | `${FILE}`, `${WORKSPACE}` | 文件创建时 |
| `fileDeleted` | `{"type": "fileDeleted"}` | `${FILE}`, `${WORKSPACE}` | 文件删除时 |
| `agentStop` | `{"type": "agentStop"}` | `${WORKSPACE}` | Agent 执行完成时 |
| `userTriggered` | `{"type": "userTriggered"}` | `${WORKSPACE}` | 用户手动触发时 |

### YAML 格式触发条件（备选）

- `file-create:<pattern>` - 文件创建时触发
- `file-save:<pattern>` - 文件保存时触发
- `file-delete:<pattern>` - 文件删除时触发
- `message-send` - 发送消息时触发
- `agent-complete` - Agent 执行完成时触发
- `session-create` - 新会话创建时触发

### 执行动作（then）

#### askAgent 动作

```yaml
then:
  askAgent:
    message: "提示消息"
```

#### runCommand 动作

```yaml
then:
  runCommand:
    command: "shell 命令"
    args: ["参数1", "参数2"]
```

## Hook 类型

### 1. File Hooks（文件触发）

**触发时机**：文件创建、保存、删除时

**示例**：
- `sync-project-structure-on-create.kiro.hook` - 文件创建时自动更新 project-structure.md
- `sync-project-structure-on-delete.kiro.hook` - 文件删除时自动更新 project-structure.md
- `format-python-code.kiro.hook` - Python 文件保存时自动格式化
- `run-tests-on-save.kiro.hook` - 测试文件保存时自动运行测试
- `update-docs-on-api-change.kiro.hook` - API 文件修改时更新文档

### 2. Contextual Hooks（上下文触发）

**触发时机**：特定上下文事件发生时

**示例**：
- `remind-steering-rules.kiro.hook` - 发送消息时提醒 Steering 规则
- `check-test-coverage.kiro.hook` - Agent 完成时检查测试覆盖率
- `welcome-message.kiro.hook` - 新会话创建时显示欢迎消息

### 3. Manual Hooks（手动触发）

**触发时机**：用户手动点击触发

**示例**：
- `spell-check-readme.kiro.hook` - 手动检查 README 拼写
- `generate-api-docs.kiro.hook` - 手动生成 API 文档
- `optimize-imports.kiro.hook` - 手动优化导入语句

## 变量

Hook 中可以使用以下变量：

- `${file}` - 触发 Hook 的文件路径
- `${message}` - 用户发送的消息内容
- `${workspace}` - 工作区根目录路径

## 最佳实践

1. **命名规范**：使用描述性名称，格式为 `<动作>-<对象>.kiro.hook`
2. **文件模式**：使用精确的文件模式避免误触发
3. **命令安全**：避免在 Hook 中执行危险命令
4. **性能考虑**：避免在频繁触发的 Hook 中执行耗时操作
5. **错误处理**：确保 Hook 命令有适当的错误处理

## 示例

### 自动格式化 Python 代码

```yaml
when: file-save:backend/**/*.py
then:
  runCommand:
    command: "black"
    args: ["${file}"]
```

### 提醒 Steering 规则

```yaml
when: message-send
then:
  askAgent:
    message: "记得遵循 .kiro/steering/KIRO-RULES.md 中的规则"
```

### 运行测试

```yaml
when: file-save:backend/tests/**/*.py
then:
  runCommand:
    command: "pytest"
    args: ["${file}", "-v"]
```

## 管理 Hooks

### 启用/禁用 Hook

重命名文件：
- 启用：确保文件以 `.kiro.hook` 结尾
- 禁用：添加 `.disabled` 后缀（例如：`format-python-code.kiro.hook.disabled`）

### 调试 Hook

查看 Hook 执行日志：
1. 打开 Kiro 输出面板
2. 选择 "Hooks" 频道
3. 查看 Hook 触发和执行记录

---

**最后更新**：2026-01-10  
**版本**：v2.0.0
