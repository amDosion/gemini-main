# PR 检查失败问题分析与修复方案

> **创建日期**: 2026-01-18
> **问题**: GitHub Actions PR 标题检查失败
> **错误码**: Exit code 2 (语法错误)

---

## 🔴 错误信息

```bash
0s
Run if [[ ! "docs: 完善附件处理分析文档，添加统一后端化设计方案" =~ ^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .+ ]]; then
  if [[ ! "docs: 完善附件处理分析文档，添加统一后端化设计方案" =~ ^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .+ ]]; then
    echo "❌ PR title does not follow conventional commits format"
    echo "Expected format: type(scope): description"
    echo "Types: feat, fix, docs, style, refactor, test, chore"
    exit 1
  fi
  shell: /usr/bin/bash -e {0}
/home/runner/work/_temp/f0464fd0-e958-4285-90ce-ffa82c36f144.sh: line 1: syntax error in conditional expression
Error: Process completed with exit code 2.
```

---

## 🔍 问题分析

### 1. 语法错误 (Syntax Error)

**错误位置**：
```bash
syntax error in conditional expression
```

**根本原因**：
Bash 中的 `[[` 条件表达式在使用正则表达式时，某些特殊字符需要转义或引用。

### 2. 正则表达式问题

**当前正则表达式**：
```regex
^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .+
```

**问题点**：

1. **`(\(.+\))?` 部分**：
   - `\(` 和 `\)` 在 `[[` 中可能被解释为分组，而不是字面的括号
   - 应该使用 `\(` 来匹配字面括号

2. **`: ` 之间的空格**：
   - 正则表达式要求 `: ` (冒号 + 空格)
   - PR 标题是 `docs: 完善...`（有空格，符合要求）

3. **`.+` 部分**：
   - `.+` 匹配任意字符（包括中文）
   - 理论上应该可以匹配中文字符

### 3. 重复的 if 语句

**代码问题**：
```bash
if [[ ! "docs: ..." =~ ^... ]]; then
  if [[ ! "docs: ..." =~ ^... ]]; then  # ❌ 重复的条件
    echo "❌ PR title does not follow..."
    exit 1
  fi
```

**可能的原因**：
- 脚本生成错误
- 或者外层 if 应该是其他条件

---

## ✅ 修复方案

### 方案 1：修复正则表达式语法（推荐）

**问题**：正则表达式在 Bash `[[` 中的特殊字符处理

**修复**：

#### 修复前（有问题）:
```yaml
- name: Check PR title format
  run: |
    PR_TITLE="${{ github.event.pull_request.title }}"
    if [[ ! "$PR_TITLE" =~ ^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: .+ ]]; then
      echo "❌ PR title does not follow conventional commits format"
      exit 1
    fi
```

#### 修复后（正确）:
```yaml
- name: Check PR title format
  run: |
    PR_TITLE="${{ github.event.pull_request.title }}"
    # 修复正则表达式：使用变量存储正则，避免转义问题
    REGEX='^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?: .+'

    if [[ ! "$PR_TITLE" =~ $REGEX ]]; then
      echo "❌ PR title does not follow conventional commits format"
      echo "Expected format: type(scope): description"
      echo "Types: feat, fix, docs, style, refactor, test, chore"
      echo "Your title: $PR_TITLE"
      exit 1
    fi

    echo "✅ PR title format is correct"
```

**关键改动**：
1. ✅ 使用变量 `REGEX` 存储正则表达式（避免转义问题）
2. ✅ 将 `(\(.+\))?` 改为 `(\([^)]+\))?`（更精确的括号匹配）
3. ✅ 移除重复的 if 语句
4. ✅ 添加调试信息（显示实际的 PR 标题）

### 方案 2：使用 grep 替代正则匹配（备选）

```yaml
- name: Check PR title format
  run: |
    PR_TITLE="${{ github.event.pull_request.title }}"

    # 使用 grep 进行正则匹配（更稳定）
    if ! echo "$PR_TITLE" | grep -Pq '^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?: .+'; then
      echo "❌ PR title does not follow conventional commits format"
      echo "Expected format: type(scope): description"
      echo "Types: feat, fix, docs, style, refactor, test, chore"
      echo "Your title: $PR_TITLE"
      exit 1
    fi

    echo "✅ PR title format is correct"
```

**优点**：
- ✅ `grep -P` 支持 Perl 兼容的正则表达式（更强大）
- ✅ 避免 Bash `[[` 的转义问题

### 方案 3：使用 Python 脚本（最稳定）

**创建脚本** `.github/scripts/check-pr-title.py`:
```python
#!/usr/bin/env python3
import re
import sys

def check_pr_title(title):
    """检查 PR 标题格式"""
    # Conventional Commits 格式
    pattern = r'^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?: .+'

    if not re.match(pattern, title):
        print(f"❌ PR title does not follow conventional commits format")
        print(f"Expected format: type(scope): description")
        print(f"Types: feat, fix, docs, style, refactor, test, chore")
        print(f"Your title: {title}")
        return False

    print(f"✅ PR title format is correct: {title}")
    return True

if __name__ == "__main__":
    pr_title = sys.argv[1]
    if not check_pr_title(pr_title):
        sys.exit(1)
```

**workflow 调用**:
```yaml
- name: Check PR title format
  run: |
    python .github/scripts/check-pr-title.py "${{ github.event.pull_request.title }}"
```

**优点**：
- ✅ Python 正则表达式更稳定
- ✅ 支持中文字符
- ✅ 易于调试和扩展

---

## 📝 完整的 Workflow 文件示例

### 文件位置：`.github/workflows/pr-check.yml`

```yaml
name: PR Title Check

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

jobs:
  check-pr-title:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Check PR title format
        run: |
          PR_TITLE="${{ github.event.pull_request.title }}"

          # 使用变量存储正则表达式
          REGEX='^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?: .+'

          if [[ ! "$PR_TITLE" =~ $REGEX ]]; then
            echo "❌ PR title does not follow conventional commits format"
            echo ""
            echo "Expected format:"
            echo "  type(scope): description"
            echo ""
            echo "Valid types:"
            echo "  - feat: A new feature"
            echo "  - fix: A bug fix"
            echo "  - docs: Documentation only changes"
            echo "  - style: Code style changes (formatting, etc.)"
            echo "  - refactor: Code refactoring"
            echo "  - test: Adding or updating tests"
            echo "  - chore: Other changes (build, CI, etc.)"
            echo ""
            echo "Examples:"
            echo "  ✅ feat: add user authentication"
            echo "  ✅ feat(auth): add login page"
            echo "  ✅ fix: resolve memory leak in image processing"
            echo "  ✅ docs: update README with installation guide"
            echo ""
            echo "Your title: $PR_TITLE"
            exit 1
          fi

          echo "✅ PR title format is correct: $PR_TITLE"
```

---

## 🧪 测试用例

### 有效的 PR 标题 ✅

```
feat: add user authentication
feat(auth): add login page
fix: resolve memory leak in image processing
fix(api): handle null pointer exception
docs: update README with installation guide
docs(api): add API documentation
style: format code with prettier
refactor: simplify attachment processing logic
refactor(frontend): extract reusable components
test: add unit tests for attachment utils
chore: update dependencies
chore(ci): configure GitHub Actions
```

### 无效的 PR 标题 ❌

```
Add user authentication           # ❌ 缺少 type
feat add user authentication      # ❌ 缺少冒号
feat:add user authentication      # ❌ 冒号后缺少空格
feature: add login                # ❌ type 错误（应该是 feat）
feat():add login                  # ❌ scope 为空
```

### 中文 PR 标题测试

```
✅ docs: 完善附件处理分析文档，添加统一后端化设计方案
✅ feat: 实现用户认证功能
✅ fix(backend): 修复图片上传内存泄漏问题
✅ refactor: 重构附件处理逻辑
```

---

## 🔧 实施步骤

### 步骤 1：创建 `.github/workflows/pr-check.yml`

```bash
# 创建目录
mkdir -p .github/workflows

# 创建文件
cat > .github/workflows/pr-check.yml << 'EOF'
name: PR Title Check

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

jobs:
  check-pr-title:
    runs-on: ubuntu-latest

    steps:
      - name: Check PR title format
        run: |
          PR_TITLE="${{ github.event.pull_request.title }}"
          REGEX='^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?: .+'

          if [[ ! "$PR_TITLE" =~ $REGEX ]]; then
            echo "❌ PR title does not follow conventional commits format"
            echo "Expected format: type(scope): description"
            echo "Types: feat, fix, docs, style, refactor, test, chore"
            echo "Your title: $PR_TITLE"
            exit 1
          fi

          echo "✅ PR title format is correct: $PR_TITLE"
EOF
```

### 步骤 2：提交并推送

```bash
git add .github/workflows/pr-check.yml
git commit -m "fix(ci): 修复 PR 标题检查的正则表达式语法错误"
git push origin file-ops-arch-b75fb
```

### 步骤 3：验证修复

1. 创建一个新的 PR（或编辑现有 PR 标题）
2. 观察 GitHub Actions 是否通过
3. 如果仍失败，查看日志并调整

---

## 🐛 常见问题排查

### Q1: 为什么我的中文 PR 标题不匹配？

**A**: `.+` 应该可以匹配中文字符。如果不行，检查：
1. 确保正则表达式中没有 ASCII 限制
2. 使用 `.*` 替代 `.+`（允许空描述，不推荐）
3. 使用 Python 脚本（方案 3）

### Q2: 如何临时禁用 PR 检查？

**A**: 在 workflow 文件中添加条件：
```yaml
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]
    branches-ignore:
      - 'hotfix/**'  # 忽略 hotfix 分支
```

### Q3: 如何允许更多的 commit types？

**A**: 修改正则表达式，添加新的 types：
```bash
REGEX='^(feat|fix|docs|style|refactor|test|chore|perf|build|ci)(\([^)]+\))?: .+'
```

---

## 📚 参考资料

- [Conventional Commits 规范](https://www.conventionalcommits.org/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Bash 正则表达式指南](https://www.gnu.org/software/bash/manual/html_node/Pattern-Matching.html)

---

## 🎯 总结

**问题根源**：
- Bash `[[` 中的正则表达式语法错误
- `(\(.+\))?` 部分的转义问题

**推荐修复**：
- ✅ 使用变量存储正则表达式（方案 1）
- ✅ 将 `(\(.+\))` 改为 `(\([^)]+\))`
- ✅ 添加调试信息

**验证方法**：
```bash
# 本地测试
PR_TITLE="docs: 完善附件处理分析文档，添加统一后端化设计方案"
REGEX='^(feat|fix|docs|style|refactor|test|chore)(\([^)]+\))?: .+'

if [[ "$PR_TITLE" =~ $REGEX ]]; then
  echo "✅ 匹配成功"
else
  echo "❌ 匹配失败"
fi
```

**预期结果**：
```
✅ 匹配成功
✅ PR title format is correct: docs: 完善附件处理分析文档，添加统一后端化设计方案
```
