# 贡献指南 (Contributing Guide)

感谢你对这个项目的兴趣！我们欢迎所有形式的贡献。

## 🚀 开始之前

1. **Fork 仓库** - 点击 GitHub 上的 Fork 按钮
2. **克隆仓库** - `git clone https://github.com/your-username/gemini-main.git`
3. **创建分支** - `git checkout -b feature/your-feature-name`

## 📝 开发流程

### 1. 创建 Issue

在开始工作之前，请先创建一个 Issue 来描述你想要做的更改。这有助于：
- 避免重复工作
- 获得反馈和建议
- 确保更改符合项目目标

### 2. 创建分支

```bash
# 从 master 分支创建新分支
git checkout master
git pull origin master
git checkout -b feature/your-feature-name
```

### 3. 进行更改

- 遵循项目的代码风格
- 添加必要的注释
- 更新相关文档
- 添加/更新测试

### 4. 提交更改

使用清晰的提交信息：

```bash
git add .
git commit -m "feat: 添加新功能描述"
```

**提交信息格式**:
- `feat:` - 新功能
- `fix:` - Bug 修复
- `docs:` - 文档更新
- `style:` - 代码格式（不影响代码运行）
- `refactor:` - 重构
- `test:` - 测试相关
- `chore:` - 构建过程或辅助工具的变动

### 5. 推送更改

```bash
git push origin feature/your-feature-name
```

### 6. 创建 Pull Request

1. 在 GitHub 上打开你的分支
2. 点击 "New Pull Request"
3. 填写 PR 模板中的所有信息
4. 等待审查

## 📋 代码规范

### 前端 (TypeScript/React)

- 使用 TypeScript 进行类型检查
- 遵循 ESLint 规则
- 使用 Prettier 格式化代码
- 组件使用函数式组件和 Hooks

### 后端 (Python)

- 遵循 PEP 8 代码风格
- 使用类型提示 (Type Hints)
- 添加文档字符串 (Docstrings)
- 保持函数简洁

## 🧪 测试

- 为新功能添加测试
- 确保所有测试通过
- 保持或提高测试覆盖率

## 📝 文档

- 更新相关文档
- 添加代码注释
- 更新 README（如需要）

## 🔍 代码审查

- 所有 PR 都需要至少一个审查者批准
- 审查者可能会要求更改
- 请及时响应审查意见

## ✅ 检查清单

在提交 PR 之前，请确保：

- [ ] 代码遵循项目规范
- [ ] 已添加必要的测试
- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] 提交信息清晰
- [ ] PR 描述完整

## 🐛 报告 Bug

如果发现 Bug，请：

1. 检查是否已有相关 Issue
2. 如果没有，创建新的 Bug Report Issue
3. 提供详细的复现步骤
4. 包含环境信息和错误日志

## 💡 提出功能建议

如果有新功能的想法：

1. 检查是否已有相关 Issue
2. 创建 Feature Request Issue
3. 详细描述功能需求和使用场景

## 📞 获取帮助

如有问题，可以：

- 创建 Issue
- 查看现有文档
- 联系维护者

感谢你的贡献！🎉
