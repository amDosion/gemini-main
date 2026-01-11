# Claude Agent Hooks 配置

本目录包含 Claude Code 的 Agent Hooks 配置和相关文档。

## 📁 目录结构

```
.claude/
├── hooks.json              # 主配置文件
├── HOOKS_GUIDE.md          # 详细使用指南
├── README.md               # 本文件
├── scripts/                # 辅助脚本
│   ├── setup_hooks.ps1     # Windows 环境设置脚本
│   ├── setup_hooks.sh      # Linux/macOS 环境设置脚本
│   └── verify_schema.py    # 数据库 Schema 验证脚本
├── logs/                   # 日志目录（自动创建）
└── backups/                # 备份目录（自动创建）
```

## 🚀 快速开始

### 1. 安装依赖

**Windows:**
```powershell
.\.claude\scripts\setup_hooks.ps1
```

**Linux/macOS:**
```bash
bash .claude/scripts/setup_hooks.sh
```

### 2. 配置 Hooks

编辑 `.claude/hooks.json`，设置需要的 hooks 为 `enabled: true`。

### 3. 开始使用

Claude Code 会自动在适当的时机触发配置的 hooks。

## 📚 文档

- **[完整使用指南](HOOKS_GUIDE.md)** - 详细的 Hooks 说明、配置、工作流、故障排除
- **[项目协作指南](../.kiro/steering/claude-mcp-collaboration.md)** - MCP 协作开发流程
- **[MCP 工具参考](../.kiro/steering/mcp-usage-guide.md)** - MCP 工具使用规范

## 🎯 核心功能

### 代码质量
- ✅ Python 自动格式化（Black）
- ✅ TypeScript 自动格式化（Prettier）
- ✅ 类型检查（mypy, tsc）
- ✅ Linting（Ruff, ESLint）

### 测试
- 🧪 提交前运行测试套件
- 🧪 集成测试
- 🧪 覆盖率报告

### 安全
- 🔒 依赖漏洞扫描（pip-audit, npm audit）
- 🔒 危险命令拦截
- 🔒 关键文件备份

### 工作流
- 🚀 完整测试套件
- 🚀 部署前检查
- 🚀 开发环境设置
- 🚀 新功能脚手架
- 🚀 数据库迁移

## ⚙️ 常用配置

### 最小化配置（推荐新手）

```json
{
  "format_python_code": { "enabled": true },
  "format_typescript_code": { "enabled": true },
  "prevent_dangerous_commands": { "enabled": true }
}
```

### 标准配置（推荐开发）

```json
{
  "format_python_code": { "enabled": true },
  "format_typescript_code": { "enabled": true },
  "python_type_check": { "enabled": true },
  "typescript_type_check": { "enabled": true },
  "prevent_dangerous_commands": { "enabled": true },
  "log_errors": { "enabled": true }
}
```

### 完整配置（推荐生产）

```json
{
  "before_file_write": "全部启用",
  "after_file_write": "全部启用",
  "before_commit": "全部启用",
  "on_tool_call.Bash.prevent_dangerous_commands": { "enabled": true },
  "on_tool_call.Edit.backup_before_edit": { "enabled": true },
  "on_session_start": "全部启用",
  "on_error": "全部启用"
}
```

## 🛠️ 自定义工作流命令

在 Claude Code 中执行：

```bash
# 运行完整测试
/workflow run_full_test_suite

# 部署前检查
/workflow deploy_check

# 设置开发环境
/workflow setup_dev_environment

# 添加新提供商
/workflow add_new_provider PROVIDER_NAME=azure

# 添加新模式
/workflow add_new_mode MODE_NAME=3d-model-gen

# 数据库迁移
/workflow database_migration MIGRATION_MESSAGE="add user roles"
```

## 📊 Hooks 概览

### 文件操作 Hooks

| Hook | 触发时机 | 阻塞 | 默认状态 |
|------|---------|------|---------|
| format_python_code | 写入 Python 文件前 | ✅ | 启用 |
| format_typescript_code | 写入 TS 文件前 | ✅ | 启用 |
| validate_json_syntax | 写入 JSON 文件前 | ✅ | 启用 |
| python_type_check | 写入 Python 文件后 | ❌ | 启用 |
| typescript_type_check | 写入 TS 文件后 | ❌ | 启用 |
| lint_python | 写入 Python 文件后 | ❌ | 启用 |
| lint_typescript | 写入 TS 文件后 | ❌ | 禁用 |

### Git Hooks

| Hook | 触发时机 | 阻塞 | 默认状态 |
|------|---------|------|---------|
| run_backend_tests | 提交前 | ✅ | 启用 |
| run_frontend_tests | 提交前 | ✅ | 启用 |
| check_security_vulnerabilities | 提交前 | ❌ | 启用 |
| check_npm_vulnerabilities | 提交前 | ❌ | 启用 |
| validate_api_schema | 提交前 | ✅ | 启用 |
| sync_database_models | 提交后 | ❌ | 启用 |

### 工具调用 Hooks

| Hook | 触发工具 | 阻塞 | 默认状态 |
|------|---------|------|---------|
| prevent_dangerous_commands | Bash | ✅ | 启用 |
| log_bash_commands | Bash | ❌ | 禁用 |
| backup_before_edit | Edit | ❌ | 启用 |
| track_file_reads | Read | ❌ | 禁用 |

### 会话 Hooks

| Hook | 触发时机 | 阻塞 | 默认状态 |
|------|---------|------|---------|
| check_environment | 会话开始 | ❌ | 启用 |
| check_backend_dependencies | 会话开始 | ❌ | 启用 |
| check_frontend_dependencies | 会话开始 | ❌ | 启用 |
| check_database_connection | 会话开始 | ❌ | 启用 |
| display_project_status | 会话开始 | ❌ | 启用 |
| cleanup_temp_files | 会话结束 | ❌ | 启用 |
| log_errors | 错误发生 | ❌ | 启用 |

## 🔧 环境变量

在 `hooks.json` 中配置的环境变量：

```json
{
  "environment_variables": {
    "PYTHONPATH": "${WORKSPACE_ROOT}/backend",
    "NODE_ENV": "development",
    "CI": "false"
  }
}
```

## 📝 日志位置

- **Hooks 日志**: `.claude/logs/hooks.log`
- **错误日志**: `.claude/error_log.txt`
- **Bash 命令日志**: `.claude/bash_log.txt`（需启用）
- **文件读取日志**: `.claude/read_log.txt`（需启用）
- **会话日志**: `.claude/session_log.txt`（需启用）

## 🐛 故障排除

### Hook 未触发

1. 检查 `enabled: true` 是否设置
2. 验证文件匹配 `pattern` 规则
3. 查看 `.claude/logs/hooks.log`

### Hook 执行失败

1. 查看错误消息
2. 手动运行命令测试
3. 检查工具是否安装

### 性能问题

1. 禁用非关键 hooks
2. 设置 `blocking: false`
3. 增加 `timeout` 值

详细故障排除指南请参阅 [HOOKS_GUIDE.md](HOOKS_GUIDE.md#故障排除)。

## 📦 依赖清单

### Python 工具
- black - 代码格式化
- ruff - Linting
- mypy - 类型检查
- pytest - 测试框架
- pytest-cov - 覆盖率
- pip-audit - 安全扫描

### Node.js 工具
- prettier - 代码格式化
- eslint - Linting
- @typescript-eslint/parser - TS 解析器
- vitest - 测试框架

## 🤝 贡献

欢迎改进建议！请：

1. Fork 项目
2. 创建功能分支
3. 测试新配置
4. 提交 Pull Request

## 📄 许可证

本配置遵循项目主许可证。

## 🔗 相关链接

- [Claude Code 官方文档](https://docs.anthropic.com/claude-code)
- [Black 文档](https://black.readthedocs.io/)
- [Ruff 文档](https://docs.astral.sh/ruff/)
- [Pytest 文档](https://docs.pytest.org/)
- [Vitest 文档](https://vitest.dev/)

---

**版本**: 1.0.0
**更新日期**: 2026-01-09
**维护者**: Claude Code Team
