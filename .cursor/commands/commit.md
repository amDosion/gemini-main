# 提交代码

创建一个 Git 提交，自动生成有意义的提交信息。

## 执行步骤

1. **检查当前状态**
   ```bash
   git status
   git diff --staged
   git diff
   ```

2. **分析更改内容**
   - 新增的功能
   - 修复的问题
   - 重构的代码
   - 更新的配置

3. **生成提交信息**

   格式：
   ```
   <type>(<scope>): <description>

   [optional body]

   [optional footer]
   ```

   类型：
   - `feat`: 新功能
   - `fix`: 修复 bug
   - `docs`: 文档更新
   - `style`: 代码格式（不影响功能）
   - `refactor`: 重构
   - `perf`: 性能优化
   - `test`: 测试相关
   - `chore`: 构建/工具相关

   示例：
   ```
   feat(chat): add streaming response support

   - Implement SSE streaming for chat API
   - Add progress indicator in UI
   - Handle connection errors gracefully

   Closes #123
   ```

4. **暂存文件**
   ```bash
   git add <files>
   # 或
   git add .
   ```

5. **创建提交**
   ```bash
   git commit -m "<commit message>"
   ```

## 注意事项

- 不要提交敏感文件（.env, credentials.json 等）
- 确保代码通过测试
- 提交信息使用英文
- 保持提交原子性（一个提交做一件事）

## 使用示例

```
/commit 提交当前所有更改
```

```
/commit 只提交 frontend/ 目录的更改
```

```
/commit 这是一个修复聊天流式响应的 bug fix
```
