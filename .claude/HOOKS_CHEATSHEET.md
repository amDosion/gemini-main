# Claude Agent Hooks 快速参考

## 🎯 一页速查

### 核心命令

```bash
# 环境设置
.\.claude\scripts\setup_hooks.ps1    # Windows
bash .claude/scripts/setup_hooks.sh  # Linux/macOS

# 工作流执行
/workflow run_full_test_suite        # 完整测试
/workflow deploy_check               # 部署检查
/workflow setup_dev_environment      # 环境设置
/workflow add_new_provider           # 添加提供商
/workflow add_new_mode               # 添加模式
/workflow database_migration         # 数据库迁移
```

### 配置文件位置

| 文件 | 路径 | 用途 |
|------|------|------|
| 主配置 | `.claude/hooks.json` | Hooks 定义 |
| 使用指南 | `.claude/HOOKS_GUIDE.md` | 详细文档 |
| 快速参考 | `.claude/HOOKS_CHEATSHEET.md` | 本文件 |
| Python 配置 | `backend/.ruff.toml` | Ruff 配置 |
| 前端配置 | `.prettierrc` | Prettier 配置 |
| TypeScript 配置 | `tsconfig.json` | TS 编译配置 |

### Hooks 类型

| 类型 | 触发时机 | 示例 |
|------|---------|------|
| `before_file_write` | 文件写入前 | 格式化代码 |
| `after_file_write` | 文件写入后 | 类型检查 |
| `before_commit` | Git 提交前 | 运行测试 |
| `after_commit` | Git 提交后 | 更新文档 |
| `on_tool_call` | 工具调用时 | 拦截危险命令 |
| `on_session_start` | 会话开始 | 环境检查 |
| `on_session_end` | 会话结束 | 清理临时文件 |
| `on_error` | 错误发生 | 记录日志 |

### 变量占位符

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `${FILE}` | 完整文件路径 | `D:\gemini-main\backend\app\main.py` |
| `${FILENAME}` | 文件名（无扩展名）| `main` |
| `${COMMAND}` | Bash 命令内容 | `pytest tests/` |
| `${ERROR_MESSAGE}` | 错误消息 | `Type error in line 42` |
| `${WORKSPACE_ROOT}` | 工作区根目录 | `D:\gemini-main\gemini-main` |

### 启用/禁用 Hooks

```json
{
  "hooks": {
    "before_file_write": [
      {
        "name": "format_python_code",
        "enabled": true,        // ✅ 启用
        "blocking": true        // 🚫 阻塞模式
      }
    ]
  }
}
```

### 阻塞 vs 非阻塞

| 模式 | `blocking: true` | `blocking: false` |
|------|-----------------|-------------------|
| 执行失败 | ❌ 阻止操作 | ⚠️ 显示警告，继续操作 |
| 用途 | 强制检查（格式化、测试）| 提示性检查（Linting、日志）|

### 常用模式匹配

| 模式 | 匹配文件 |
|------|---------|
| `**/*.py` | 所有 Python 文件 |
| `backend/**/*.py` | 后端 Python 文件 |
| `frontend/**/*.{ts,tsx}` | 前端 TS/TSX 文件 |
| `**/*.json` | 所有 JSON 文件 |
| `*.md` | 根目录 Markdown 文件 |
| `tests/**/*.py` | 测试文件 |
| `backend/app/core/**/*.py` | 核心模块 |

### 快速配置模板

#### 1. 仅格式化（最小配置）

```json
{
  "hooks": {
    "before_file_write": [
      {
        "name": "format_python_code",
        "pattern": "backend/**/*.py",
        "command": "black --line-length 100 --quiet ${FILE}",
        "enabled": true,
        "blocking": true
      },
      {
        "name": "format_typescript_code",
        "pattern": "frontend/**/*.{ts,tsx}",
        "command": "npx prettier --write ${FILE}",
        "enabled": true,
        "blocking": true
      }
    ]
  }
}
```

#### 2. 格式化 + 类型检查

```json
{
  "hooks": {
    "before_file_write": [
      { "name": "format_python_code", "enabled": true, "blocking": true },
      { "name": "format_typescript_code", "enabled": true, "blocking": true }
    ],
    "after_file_write": [
      { "name": "python_type_check", "enabled": true, "blocking": false },
      { "name": "typescript_type_check", "enabled": true, "blocking": false }
    ]
  }
}
```

#### 3. 完整保护（生产配置）

```json
{
  "hooks": {
    "before_file_write": "ALL ENABLED",
    "after_file_write": "ALL ENABLED",
    "before_commit": "ALL ENABLED",
    "on_tool_call": {
      "Bash": [
        { "name": "prevent_dangerous_commands", "enabled": true }
      ],
      "Edit": [
        { "name": "backup_before_edit", "enabled": true }
      ]
    },
    "on_session_start": "ALL ENABLED",
    "on_error": "ALL ENABLED"
  }
}
```

### 调试 Hooks

```bash
# 查看日志
cat .claude/logs/hooks.log
tail -f .claude/logs/hooks.log  # 实时查看

# 查看错误日志
cat .claude/error_log.txt

# 查看 Bash 命令日志（需启用）
cat .claude/bash_log.txt

# 手动测试命令
black --line-length 100 backend/app/main.py
npx prettier --write frontend/App.tsx
cd backend && pytest tests/ -v
```

### 工具安装检查

```bash
# Python 工具
black --version
ruff --version
mypy --version
pytest --version
pip-audit --version

# Node.js 工具
npx prettier --version
npx eslint --version
npx tsc --version
npx vitest --version
```

### 性能优化

| 问题 | 解决方案 |
|------|---------|
| Hooks 太慢 | 设置 `blocking: false` |
| 测试超时 | 增加 `timeout` 值 |
| 格式化重复 | 使用缓存工具 |
| 类型检查慢 | 使用增量模式（`mypy --cache-dir`）|

### 禁用特定 Hook

**临时禁用（编辑配置）：**
```json
{
  "name": "run_backend_tests",
  "enabled": false
}
```

**Git 跳过 Hooks：**
```bash
git commit --no-verify -m "WIP: skip hooks"
```

### 错误代码速查

| 错误 | 含义 | 解决方案 |
|------|------|---------|
| `exit code 1` | 命令执行失败 | 查看错误消息 |
| `timeout` | 超时 | 增加 `timeout` 值 |
| `command not found` | 工具未安装 | 运行 `setup_hooks.sh` |
| `pattern not matched` | 文件不匹配 | 检查 `pattern` 规则 |
| `syntax error` | JSON 语法错误 | 验证 JSON 格式 |

### 团队协作建议

1. **提交 `hooks.json` 到版本控制** - 团队共享配置
2. **创建 `.claude/hooks.local.json`** - 个人定制（加入 `.gitignore`）
3. **文档化自定义规则** - 在 README 中说明
4. **定期更新依赖** - `npm update` / `pip install --upgrade`
5. **代码审查配置变更** - 重大改动需审批

### 常见工作流场景

#### 场景 1：修复格式化问题

```bash
# 后端
cd backend
black --line-length 100 app/
ruff check app/ --fix

# 前端
npx prettier --write frontend/
```

#### 场景 2：运行测试并查看覆盖率

```bash
# 后端
cd backend
pytest tests/ -v --cov=app --cov-report=html

# 前端
npm run test -- --coverage
```

#### 场景 3：安全扫描

```bash
# Python 依赖
cd backend
pip-audit --desc

# Node.js 依赖
npm audit --audit-level=moderate
npm audit fix  # 自动修复
```

#### 场景 4：添加新功能

```bash
# 1. 创建功能分支
git checkout -b feature/new-provider

# 2. 使用脚手架
/workflow add_new_provider PROVIDER_NAME=anthropic

# 3. 实现功能（Claude Code 会触发 Hooks）

# 4. 运行测试
/workflow run_full_test_suite

# 5. 提交代码（自动运行 before_commit hooks）
git add .
git commit -m "feat: add Anthropic provider"
```

#### 场景 5：部署准备

```bash
# 运行完整检查
/workflow deploy_check

# 检查输出确保所有步骤通过
# ✅ Build successful
# ✅ TypeScript compilation passed
# ✅ All tests passed
# ✅ No security vulnerabilities
# ✅ Environment variables valid
```

### 日志文件轮转

```bash
# 手动清理旧日志
rm -rf .claude/logs/*.log.old

# 或使用 logrotate 自动管理（Linux）
# 配置在 /etc/logrotate.d/claude-hooks
```

### Hook 优先级

1. **before_file_write** - 最高优先级（阻止无效文件）
2. **after_file_write** - 高优先级（验证文件质量）
3. **before_commit** - 中优先级（确保提交质量）
4. **on_tool_call** - 中优先级（安全拦截）
5. **after_commit** - 低优先级（通知/文档）
6. **on_session_start/end** - 低优先级（环境管理）

### 资源链接

| 资源 | 链接 |
|------|------|
| 完整指南 | `.claude/HOOKS_GUIDE.md` |
| 配置文件 | `.claude/hooks.json` |
| 项目文档 | `.claude/README.md` |
| Black 文档 | https://black.readthedocs.io/ |
| Ruff 文档 | https://docs.astral.sh/ruff/ |
| Pytest 文档 | https://docs.pytest.org/ |
| Prettier 文档 | https://prettier.io/docs/ |
| Vitest 文档 | https://vitest.dev/ |

---

**提示**: 这是一个快速参考。详细说明请查阅 [HOOKS_GUIDE.md](HOOKS_GUIDE.md)。

**版本**: 1.0.0 | **更新**: 2026-01-09
