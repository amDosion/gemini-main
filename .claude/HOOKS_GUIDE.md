# Claude Agent Hooks 使用指南

## 📚 目录
- [概述](#概述)
- [快速开始](#快速开始)
- [Hooks 详解](#hooks-详解)
- [自定义工作流](#自定义工作流)
- [最佳实践](#最佳实践)
- [故障排除](#故障排除)

---

## 概述

本项目配置了全面的 Claude Agent Hooks 系统，用于自动化开发工作流程，包括：

- ✅ **代码质量检查**：自动格式化、类型检查、Linting
- 🧪 **自动化测试**：提交前运行测试套件
- 🔒 **安全扫描**：依赖漏洞检测、危险命令拦截
- 📝 **日志记录**：操作审计、错误跟踪
- 🚀 **工作流自动化**：一键部署检查、新功能脚手架

---

## 快速开始

### 1. 环境要求

确保已安装以下工具：

```bash
# 检查环境
python --version    # Python 3.10+
node --version      # Node.js 18+
npm --version       # npm 9+
git --version       # Git 2.30+

# 后端工具
pip install black ruff mypy pytest pytest-cov pip-audit

# 前端工具（已在 package.json 中）
npm install -D prettier eslint @typescript-eslint/parser vitest
```

### 2. 启用 Hooks

编辑 `.claude/hooks.json`，设置 `enabled: true` 启用所需的 hooks。

### 3. 测试 Hooks

```bash
# 测试文件格式化
echo "print('test')" > test_file.py
# Claude Code 将自动触发 format_python_code hook

# 测试提交前检查
git add .
git commit -m "test commit"
# 将触发 run_backend_tests 和 run_frontend_tests hooks
```

---

## Hooks 详解

### 📝 文件写入钩子

#### `before_file_write`

**1. format_python_code**
- **触发时机**：写入 Python 文件前
- **作用**：使用 Black 格式化代码（行长度 100）
- **阻塞**：是（格式化失败将阻止写入）
- **配置**：
  ```json
  {
    "pattern": "backend/**/*.py",
    "command": "black --line-length 100 --quiet ${FILE}"
  }
  ```

**2. format_typescript_code**
- **触发时机**：写入 TypeScript/TSX 文件前
- **作用**：使用 Prettier 格式化代码
- **阻塞**：是
- **配置**：创建 `.prettierrc` 文件定制规则

**3. validate_json_syntax**
- **触发时机**：写入 JSON 文件前
- **作用**：验证 JSON 语法正确性
- **阻塞**：是（防止无效 JSON 文件）

#### `after_file_write`

**1. python_type_check**
- **触发时机**：写入 Python 文件后
- **作用**：使用 mypy 进行类型检查
- **阻塞**：否（异步提示）
- **忽略错误**：`--ignore-missing-imports`

**2. typescript_type_check**
- **触发时机**：写入 TypeScript 文件后
- **作用**：使用 tsc 进行类型检查
- **阻塞**：否

**3. lint_python**
- **触发时机**：写入 Python 文件后
- **作用**：使用 Ruff 检查代码质量
- **自动修复**：`--fix` 参数

**4. lint_typescript**
- **触发时机**：写入 TypeScript 文件后
- **作用**：使用 ESLint 检查代码质量
- **默认状态**：禁用（需手动启用）

---

### 🔄 Git 提交钩子

#### `before_commit`

**1. run_backend_tests**
- **触发条件**：修改了 `backend/**/*.py` 文件
- **作用**：运行后端单元测试
- **阻塞**：是（测试失败将阻止提交）
- **命令**：`pytest tests/ -v --tb=short`

**2. run_frontend_tests**
- **触发条件**：修改了 `frontend/**/*.{ts,tsx}` 文件
- **作用**：运行前端单元测试
- **阻塞**：是
- **命令**：`npm run test -- --run --reporter=verbose`

**3. check_security_vulnerabilities**
- **触发条件**：修改了 `backend/requirements*.txt`
- **作用**：使用 pip-audit 扫描依赖漏洞
- **阻塞**：否（提示但不阻止）

**4. check_npm_vulnerabilities**
- **触发条件**：修改了 `package.json`
- **作用**：使用 npm audit 扫描依赖漏洞
- **阻塞**：否

**5. validate_api_schema**
- **触发条件**：修改了 `backend/app/routers/**/*.py`
- **作用**：验证 API Schema 一致性
- **阻塞**：是

#### `after_commit`

**1. sync_database_models**
- **触发条件**：修改了 `backend/app/models/*.py`
- **作用**：提醒检查数据库迁移
- **提示**：⚠️ Database models changed. Consider creating migration script.

**2. update_api_documentation**
- **触发条件**：修改了 `backend/app/routers/**/*.py`
- **作用**：重新生成 OpenAPI 文档
- **默认状态**：禁用

---

### 🛠️ 工具调用钩子

#### `on_tool_call.Bash`

**1. prevent_dangerous_commands**
- **触发时机**：每次 Claude 执行 Bash 命令前
- **作用**：拦截危险命令
- **拦截列表**：
  - `rm -rf /`
  - `DROP TABLE`
  - `truncate`
  - `mkfs`
- **阻塞**：是（危险命令将被拒绝）

**2. log_bash_commands**
- **触发时机**：每次 Bash 命令执行
- **作用**：记录命令到 `.claude/bash_log.txt`
- **默认状态**：禁用

#### `on_tool_call.Edit`

**1. backup_before_edit**
- **触发时机**：编辑 `backend/app/core/**/*.py` 文件前
- **作用**：创建带时间戳的备份文件
- **备份位置**：`${FILE}.backup.${timestamp}`

#### `on_tool_call.Read`

**1. track_file_reads**
- **触发时机**：每次文件读取
- **作用**：记录读取操作到 `.claude/read_log.txt`
- **默认状态**：禁用

---

### 🎬 会话钩子

#### `on_session_start`

会话开始时自动执行的检查：

1. **check_environment**：验证 Python/Node/npm 版本
2. **check_backend_dependencies**：检查后端依赖完整性
3. **check_frontend_dependencies**：检查前端依赖完整性
4. **check_database_connection**：测试数据库连接
5. **display_project_status**：显示 Git 状态和最近提交

#### `on_session_end`

会话结束时的清理任务：

1. **cleanup_temp_files**：删除 `.pyc` 和 `__pycache__`
2. **save_session_summary**：保存会话摘要（默认禁用）

#### `on_error`

错误发生时的响应：

1. **log_errors**：记录错误到 `.claude/error_log.txt`
2. **check_backend_logs**：显示最近 20 行后端日志

---

## 自定义工作流

### 🧪 运行完整测试套件

```bash
# 在 Claude Code 中执行
/workflow run_full_test_suite
```

**执行步骤**：
1. 运行后端测试（带覆盖率报告）
2. 运行前端测试（带覆盖率报告）
3. 运行集成测试

---

### 🚀 部署前检查

```bash
/workflow deploy_check
```

**执行步骤**：
1. 构建前端（`npm run build`）
2. TypeScript 编译检查
3. 运行完整测试套件
4. 安全漏洞扫描
5. 环境变量验证

---

### 🔧 设置开发环境

```bash
/workflow setup_dev_environment
```

**执行步骤**：
1. 安装后端依赖
2. 安装前端依赖
3. 初始化数据库
4. 运行数据库迁移
5. 填充测试数据

---

### ➕ 添加新 AI 提供商

```bash
/workflow add_new_provider PROVIDER_NAME=azure
```

**生成文件**：
```
backend/app/services/azure/
  ├── __init__.py
  └── client.py

frontend/services/providers/azure/
  └── index.ts
```

**后续步骤提示**：
1. 实现 `BaseProviderService` 接口
2. 在 `ProviderConfig` 中注册
3. 添加到 `UnifiedProviderClient`

---

### 🎨 添加新生成模式

```bash
/workflow add_new_mode MODE_NAME=3d-model-gen
```

**生成文件**：
```
backend/app/routers/3d-model-gen.py
frontend/components/views/3d-model-genView.tsx
frontend/hooks/handlers/3d-model-genHandlerClass.ts
frontend/controls/modes/3d-model-genControls.tsx
```

**后续步骤提示**：
1. 添加到 `AppMode` 类型
2. 在 `strategyRegistry` 中注册 Handler
3. 在 `App.tsx` 中添加路由

---

### 🗄️ 数据库迁移

```bash
/workflow database_migration MIGRATION_MESSAGE="add user roles table"
```

**执行步骤**：
1. 生成迁移文件（`alembic revision --autogenerate`）
2. 提示检查迁移文件
3. 应用迁移（`alembic upgrade head`）
4. 验证数据库 Schema

---

## 最佳实践

### 1. 渐进式启用

**初期（学习阶段）**：
```json
{
  "format_python_code": { "enabled": true },
  "format_typescript_code": { "enabled": true },
  "prevent_dangerous_commands": { "enabled": true }
}
```

**中期（开发阶段）**：
```json
{
  "python_type_check": { "enabled": true },
  "typescript_type_check": { "enabled": true },
  "run_backend_tests": { "enabled": true }
}
```

**后期（生产准备）**：
```json
{
  "check_security_vulnerabilities": { "enabled": true },
  "validate_api_schema": { "enabled": true },
  "run_frontend_tests": { "enabled": true }
}
```

### 2. 性能优化

**问题**：Hooks 执行过慢
**解决**：
- 禁用非阻塞 hooks（`blocking: false`）
- 使用 `parallel_execution: true`（谨慎使用）
- 增加 `timeout` 限制
- 缓存工具输出（如 mypy）

### 3. 测试策略

**快速反馈循环**：
```json
{
  "run_backend_tests": {
    "command": "pytest tests/unit/ -v --tb=short",
    "blocking": true
  }
}
```

**完整测试**：
```bash
# 使用工作流
/workflow run_full_test_suite
```

### 4. 日志管理

**启用关键日志**：
```json
{
  "log_errors": { "enabled": true },
  "log_bash_commands": { "enabled": false },  // 仅调试时启用
  "track_file_reads": { "enabled": false }    // 仅性能分析时启用
}
```

**定期清理**：
```bash
# 清理旧日志
rm -rf .claude/logs/*.log.old
```

### 5. 团队协作

**共享配置**：
```bash
# 提交 hooks.json 到版本控制
git add .claude/hooks.json
git commit -m "chore: add Claude Agent hooks configuration"
```

**个人定制**：
```bash
# 创建本地覆盖配置
cp .claude/hooks.json .claude/hooks.local.json
# 在 .gitignore 中添加
echo ".claude/hooks.local.json" >> .gitignore
```

---

## 故障排除

### 问题 1：Hook 执行超时

**现象**：
```
Error: Hook 'run_backend_tests' timed out after 120000ms
```

**解决方案**：
```json
{
  "settings": {
    "timeout": 300000  // 增加到 5 分钟
  }
}
```

---

### 问题 2：Python 工具找不到

**现象**：
```
Error: black: command not found
```

**解决方案**：
```bash
# 安装缺失工具
cd backend
pip install black ruff mypy pytest

# 或安装开发依赖
pip install -r requirements-dev.txt
```

---

### 问题 3：测试失败阻止提交

**现象**：
```
Hook 'run_backend_tests' failed with exit code 1
Commit blocked.
```

**解决方案**：

**选项 A**：修复测试
```bash
cd backend
pytest tests/ -v  # 查看失败详情
# 修复代码后重新提交
```

**选项 B**：临时禁用（不推荐）
```json
{
  "run_backend_tests": {
    "enabled": false  // 或 "blocking": false
  }
}
```

**选项 C**：跳过 Hook（Git 原生）
```bash
git commit --no-verify -m "WIP: fixing tests"
```

---

### 问题 4：Windows 路径问题

**现象**：
```
Error: cannot find file: D:\gemini-main\gemini-main\backend\app\main.py
```

**解决方案**：
```json
{
  "command": "cd backend && python app/main.py",  // 使用相对路径
  // 或
  "command": "python ${FILE}"  // 使用变量
}
```

---

### 问题 5：Hook 未触发

**检查清单**：
1. ✅ `enabled: true` 已设置
2. ✅ 文件匹配 `pattern` 规则
3. ✅ Hook 类型正确（before/after）
4. ✅ 没有语法错误（JSON 验证）

**调试方法**：
```bash
# 查看 Claude Code 日志
cat .claude/logs/hooks.log

# 手动执行命令测试
cd backend && pytest tests/ -v
```

---

## 高级配置

### 1. 条件执行

```json
{
  "run_backend_tests": {
    "condition": "git diff --cached --name-only | grep -q 'backend/app/'",
    "command": "cd backend && pytest tests/"
  }
}
```

### 2. 环境变量注入

```json
{
  "environment_variables": {
    "PYTHONPATH": "${WORKSPACE_ROOT}/backend",
    "TESTING": "true",
    "DATABASE_URL": "sqlite:///./test.db"
  }
}
```

### 3. 多步骤 Hook

```json
{
  "complex_validation": {
    "steps": [
      { "command": "black --check ${FILE}" },
      { "command": "mypy ${FILE}" },
      { "command": "pytest tests/test_${FILENAME}.py" }
    ]
  }
}
```

### 4. 通知集成

```json
{
  "settings": {
    "notification": {
      "on_failure": true,
      "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    }
  }
}
```

---

## 相关资源

- [Claude Code 官方文档](https://docs.anthropic.com/claude-code)
- [项目协作指南](.kiro/steering/claude-mcp-collaboration.md)
- [MCP 工具使用指南](.kiro/steering/mcp-usage-guide.md)
- [Black 代码风格](https://black.readthedocs.io/)
- [Ruff Linter](https://docs.astral.sh/ruff/)
- [Pytest 文档](https://docs.pytest.org/)
- [Vitest 文档](https://vitest.dev/)

---

## 贡献指南

欢迎提交改进建议！

1. 创建 Issue 描述问题或需求
2. Fork 项目并创建功能分支
3. 测试新 Hook 配置
4. 提交 Pull Request

**提交格式**：
```
chore(hooks): add new hook for [purpose]

- Hook 名称: [name]
- 触发时机: [timing]
- 作用: [description]
- 测试结果: [test results]
```

---

## 更新日志

### v1.0.0 (2026-01-09)
- ✨ 初始版本发布
- 🎯 支持 Python/TypeScript 代码格式化
- 🧪 集成测试套件 Hooks
- 🔒 添加安全扫描 Hooks
- 🚀 提供 6 个自定义工作流
- 📝 完整的文档和故障排除指南

---

## 许可证

本配置遵循项目主许可证。
