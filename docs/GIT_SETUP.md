# Git 配置和使用指南

## 📋 目录

- [初始配置](#初始配置)
- [分支管理](#分支管理)
- [提交规范](#提交规范)
- [Pull Request 流程](#pull-request-流程)
- [常用命令](#常用命令)

## 🔧 初始配置

### 1. 配置用户信息

```bash
# 设置全局用户名和邮箱
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### 2. 配置远程仓库

```bash
# 查看远程仓库
git remote -v

# 添加远程仓库（如果需要）
git remote add origin https://github.com/amDosion/gemini-main.git

# 更新远程仓库 URL
git remote set-url origin https://github.com/amDosion/gemini-main.git
```

### 3. 配置凭证管理

推荐使用 Windows Credential Manager（已自动配置）：

```bash
# 查看凭证配置
git config --global credential.helper

# 如果需要，可以配置 SSH 密钥
ssh-keygen -t ed25519 -C "your.email@example.com"
```

## 🌿 分支管理

### 分支命名规范

- `feature/` - 新功能分支
- `fix/` - Bug 修复分支
- `docs/` - 文档更新分支
- `refactor/` - 重构分支
- `test/` - 测试相关分支
- `chore/` - 构建/工具相关分支

### 创建和切换分支

```bash
# 从 master 创建新分支
git checkout master
git pull origin master
git checkout -b feature/your-feature-name

# 切换分支
git checkout branch-name

# 查看所有分支
git branch -a
```

### 分支同步

```bash
# 更新本地 master 分支
git checkout master
git pull origin master

# 将 master 的更改合并到当前分支
git checkout feature/your-feature-name
git merge master
```

## 📝 提交规范

### Conventional Commits 格式

提交信息格式：`<type>(<scope>): <description>`

**类型 (Type)**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动
- `perf`: 性能优化
- `ci`: CI 配置

**示例**:
```bash
git commit -m "feat: 添加用户登录功能"
git commit -m "fix(api): 修复登录接口的认证错误"
git commit -m "docs: 更新 API 文档"
git commit -m "refactor: 重构用户服务模块"
```

### 提交最佳实践

1. **提交前检查**:
   ```bash
   git status
   git diff
   ```

2. **添加文件**:
   ```bash
   # 添加所有更改
   git add .
   
   # 添加特定文件
   git add path/to/file
   ```

3. **提交更改**:
   ```bash
   git commit -m "type: 描述"
   ```

4. **推送更改**:
   ```bash
   git push origin branch-name
   ```

## 🔀 Pull Request 流程

### 1. 准备工作

```bash
# 确保本地 master 是最新的
git checkout master
git pull origin master

# 创建新分支
git checkout -b feature/your-feature-name
```

### 2. 进行更改

- 编写代码
- 添加测试
- 更新文档
- 遵循代码规范

### 3. 提交更改

```bash
# 添加更改
git add .

# 提交（使用规范的提交信息）
git commit -m "feat: 添加新功能"

# 推送分支
git push origin feature/your-feature-name
```

### 4. 创建 Pull Request

1. 在 GitHub 上打开你的分支
2. 点击 "New Pull Request"
3. 填写 PR 模板中的所有信息：
   - 描述变更内容
   - 关联相关 Issue
   - 选择变更类型
   - 添加测试说明
   - 完成检查清单
4. 提交 PR

### 5. 代码审查

- 等待审查者反馈
- 根据反馈进行修改
- 推送新的提交（会自动更新 PR）

### 6. 合并 PR

- 审查通过后，维护者会合并 PR
- 合并后可以删除分支：
  ```bash
  git checkout master
  git pull origin master
  git branch -d feature/your-feature-name
  ```

## 🛠️ 常用命令

### 查看状态和历史

```bash
# 查看工作区状态
git status

# 查看提交历史
git log --oneline -10

# 查看文件差异
git diff

# 查看分支图
git log --graph --oneline --all
```

### 撤销更改

```bash
# 撤销工作区的更改（未 add）
git checkout -- file-name

# 撤销已 add 但未 commit 的更改
git reset HEAD file-name

# 修改最后一次提交
git commit --amend
```

### 同步远程

```bash
# 获取远程更新
git fetch origin

# 拉取并合并
git pull origin branch-name

# 推送本地更改
git push origin branch-name

# 强制推送（谨慎使用）
git push origin branch-name --force
```

### 解决冲突

```bash
# 合并时出现冲突
git merge branch-name

# 查看冲突文件
git status

# 手动解决冲突后
git add .
git commit -m "fix: 解决合并冲突"
```

## 🔐 安全注意事项

1. **不要提交敏感信息**:
   - 密码、密钥、Token
   - 个人隐私信息
   - 配置文件中的敏感数据

2. **使用 .gitignore**:
   - 确保敏感文件在 .gitignore 中
   - 定期检查 .gitignore 配置

3. **凭证管理**:
   - 使用 Git Credential Manager
   - 或使用 SSH 密钥
   - 不要将密码存储在配置文件中

## 📚 相关资源

- [Git 官方文档](https://git-scm.com/doc)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [贡献指南](../.github/CONTRIBUTING.md)
