# 创建 Pull Request

创建一个 GitHub Pull Request。

## 执行步骤

1. **检查当前分支状态**
   ```bash
   git status
   git log --oneline -10
   git diff master...HEAD
   ```

2. **确保分支已推送**
   ```bash
   git push -u origin <branch-name>
   ```

3. **分析所有提交**
   - 收集分支上的所有提交
   - 理解整体更改范围
   - 识别主要功能和修复

4. **生成 PR 描述**

   格式：
   ```markdown
   ## Summary
   - [主要更改点 1]
   - [主要更改点 2]
   - [主要更改点 3]

   ## Changes
   - **[模块/文件]**: [具体更改]
   - **[模块/文件]**: [具体更改]

   ## Test plan
   - [ ] [测试项 1]
   - [ ] [测试项 2]
   - [ ] [测试项 3]

   ## Screenshots (if applicable)
   [截图或 GIF]

   ## Related issues
   Closes #[issue-number]
   ```

5. **创建 PR**
   ```bash
   gh pr create --title "<title>" --body "<body>"
   ```

## PR 标题规范

格式：`<type>(<scope>): <description>`

示例：
- `feat(chat): add streaming response support`
- `fix(auth): resolve token refresh issue`
- `refactor(api): simplify provider factory`

## 检查清单

- [ ] 代码通过 lint 检查
- [ ] 所有测试通过
- [ ] 文档已更新（如需要）
- [ ] 没有敏感信息泄露
- [ ] PR 描述清晰完整

## 使用示例

```
/pr 创建一个 PR，将当前分支合并到 master
```

```
/pr 创建 PR 并关联 issue #42
```

```
/pr 这个 PR 添加了新的图像编辑功能
```
