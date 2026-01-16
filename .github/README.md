# GitHub 配置说明

本目录包含项目的 GitHub 相关配置文件。

## 📁 目录结构

```
.github/
├── ISSUE_TEMPLATE/          # Issue 模板
│   ├── bug_report.md        # Bug 报告模板
│   └── feature_request.md   # 功能请求模板
├── PULL_REQUEST_TEMPLATE/   # PR 模板
│   └── default.md          # 默认 PR 模板
├── workflows/              # GitHub Actions 工作流
│   ├── pr-check.yml        # PR 检查工作流
│   └── code-quality.yml    # 代码质量检查工作流
├── CONTRIBUTING.md         # 贡献指南
└── README.md               # 本文件
```

## 🔧 功能说明

### Issue 模板

- **bug_report.md**: 用于报告 Bug 的标准模板
- **feature_request.md**: 用于提出新功能请求的模板

### Pull Request 模板

- **default.md**: 创建 PR 时的默认模板，包含：
  - 变更描述
  - 相关 Issue
  - 变更类型
  - 测试说明
  - 检查清单

### GitHub Actions

- **pr-check.yml**: 自动检查 PR 标题和描述格式
- **code-quality.yml**: 自动运行代码质量检查（ESLint、flake8 等）

## 📝 使用说明

### 创建 Issue

1. 点击 "New Issue"
2. 选择对应的模板（Bug 报告 或 功能请求）
3. 填写模板中的信息
4. 提交 Issue

### 创建 Pull Request

1. Fork 仓库并创建新分支
2. 进行更改并提交
3. 推送分支到 GitHub
4. 点击 "New Pull Request"
5. 系统会自动填充 PR 模板
6. 填写所有必要信息
7. 提交 PR

## 🔍 PR 检查规则

PR 标题需要遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

- `feat:` - 新功能
- `fix:` - Bug 修复
- `docs:` - 文档更新
- `style:` - 代码格式
- `refactor:` - 重构
- `test:` - 测试
- `chore:` - 构建/工具

示例：
- ✅ `feat: 添加用户认证功能`
- ✅ `fix(api): 修复登录接口错误`
- ❌ `更新代码` (不符合格式)

## 📚 相关文档

- [贡献指南](../.github/CONTRIBUTING.md)
- [项目 README](../README.md)
