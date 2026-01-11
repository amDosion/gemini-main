# 上下文优化检查清单

## ⚠️ 关键警告

**在开始任何任务前，必须阅读本检查清单！**

本文档定义了 Kiro 主 Agent 如何最大化利用所有可用工具来避免上下文爆炸，节省 Token，提高执行效率。

**核心原则**：避免直接读取大文件、重复读取文档、主 Agent 直接调用 Codex/Gemini。

---

## 1. 工具使用优先级

### 1.1 优先级表

| 优先级 | 工具 | 用途 | Token 节省 | 何时使用 |
|-------|------|------|-----------|---------|
| 🥇 **最高** | **context-gatherer subagent + readFile** | 读取项目文档 | 100% (主 Agent 0 token) | 读取项目内部文档（Spec、Steering、代码） |
| 🥈 **最高** | **Context7 MCP** | 读取外部库文档 | 90% (20K → 2K) | 读取外部库文档（FastAPI、React、Gemini SDK） |
| 🥉 **高** | **general-purpose subagent** | 代码生成 | 90% (30K → 3K) | 调用 Codex/Gemini 生成代码 |
| 4️⃣ **中** | **Redis MCP** | 缓存摘要 | 避免重复 | 缓存文档摘要、避免重复读取 |
| 5️⃣ **中** | **Desktop Commander MCP** | 文件操作 | N/A | 写入文件、编辑文件（不用于读取） |
| 6️⃣ **低** | **Hooks** | 自动化 | 减少负担 | 自动化重复任务 |

### 1.2 禁止操作（会导致上下文爆炸）

| 禁止操作 | 原因 | 正确做法 |
|---------|------|---------|
| ❌ **主 Agent 直接 readFile** 读取大文件（> 5K tokens） | 直接加载到主 Agent 上下文 | 使用 context-gatherer subagent + readFile |
| ❌ **主 Agent 直接 readMultipleFiles** 读取多个文件（> 3 个） | 上下文爆炸 | 使用 context-gatherer subagent + readMultipleFiles |
| ❌ 主 Agent 直接调用 **Codex/Gemini MCP** | 占用主 Agent 上下文 | 使用 general-purpose subagent |
| ❌ 主 Agent 直接调用 **Sequential Thinking/Claude Code MCP** | 占用主 Agent 上下文 | 使用 general-purpose subagent |
| ❌ 重复读取相同文档（不使用缓存） | 浪费 Token | 使用 Redis MCP 缓存摘要 |
| ❌ 使用 **Desktop Commander** 读取文档 | 不支持结构化摘要 | 使用 context-gatherer subagent + readFile |
| ❌ 使用 **fsWrite/fsAppend** 写入文件 | 不符合架构规范 | 使用 Desktop Commander MCP |
| ❌ **Context7 读取项目 Spec** | Context7 仅用于外部库文档 | 使用 context-gatherer subagent + readFile |

---

## 2. 标准工作流程

### 2.1 读取文档流程

```
用户请求：读取 Spec 文档
    │
    ▼
❌ 错误做法：readFile(".kiro/specs/feature/requirements.md")
    └─ 问题：直接加载 20K tokens 到主 Agent 上下文
    
✅ 正确做法：使用 Context7 MCP
    └─ mcp_context7_query_docs(
         libraryId="/project/specs/feature",
         query="Summarize requirements, design, and tasks"
       )
    └─ 返回：结构化摘要（~2K tokens）
    └─ Token 节省：90%
```

### 2.2 探索代码流程

```
用户请求：探索后端代码
    │
    ▼
❌ 错误做法：readMultipleFiles([...20个文件...])
    └─ 问题：加载 50K tokens 到主 Agent 上下文
    
✅ 正确做法：使用 context-gatherer subagent
    └─ invokeSubAgent(
         name="context-gatherer",
         prompt="Explore backend codebase for [feature] related files",
         explanation="Gathering code context"
       )
    └─ 返回：现有模式和最佳实践（~5K tokens）
    └─ Token 节省：90%
```

### 2.3 代码生成流程

```
用户请求：生成后端代码
    │
    ▼
❌ 错误做法：直接调用 mcp_codex_codex(...)
    └─ 问题：占用主 Agent 上下文，无法并行
    
✅ 正确做法：使用 general-purpose subagent
    └─ invokeSubAgent(
         name="general-task-execution",
         prompt="Use Codex to generate [feature] code based on requirements",
         explanation="Parallel code generation"
       )
    └─ 返回：生成的代码 + SESSION_ID
    └─ Token 节省：90%
    └─ 并行度：5x
```

### 2.4 文件写入流程

```
用户请求：写入文件
    │
    ▼
❌ 错误做法：fsWrite(path="...", text="...")
    └─ 问题：不符合架构规范
    
✅ 正确做法：使用 Desktop Commander MCP
    ├─ 新文件 → mcp_desktop_commander_mcp_write_file(
    │              path="D:\\gemini-main\\gemini-main\\backend\\...",
    │              content="...",
    │              mode="rewrite"
    │            )
    └─ 修改文件 → mcp_desktop_commander_mcp_edit_block(
                   file_path="D:\\gemini-main\\gemini-main\\backend\\...",
                   old_string="...",
                   new_string="..."
                 )
```

---

## 3. 场景化检查清单

### 3.1 场景 1：读取 Spec 文档

**任务**：读取 `.kiro/specs/feature/requirements.md`

**检查清单**：
- [ ] ❌ 不使用 `readFile`
- [ ] ❌ 不使用 `readMultipleFiles`
- [ ] ❌ 不使用 Desktop Commander 读取
- [ ] ✅ 使用 Context7 MCP：`mcp_context7_query_docs`
- [ ] ✅ 指定 `libraryId="/project/specs/feature"`
- [ ] ✅ 提供清晰的 `query` 参数
- [ ] ✅ 检查是否有 Redis 缓存可用

**示例**：
```python
# ✅ 正确做法
result = mcp_context7_query_docs(
    libraryId="/project/specs/feature",
    query="Summarize the requirements, design decisions, and implementation tasks"
)
# 返回：结构化摘要（~2K tokens）

# ❌ 错误做法
content = readFile(
    path=".kiro/specs/feature/requirements.md",
    explanation="Reading requirements"
)
# 问题：直接加载 20K tokens
```

### 3.2 场景 2：探索项目代码

**任务**：探索后端代码，找到相关文件

**检查清单**：
- [ ] ❌ 不使用 `readFile` 逐个读取文件
- [ ] ❌ 不使用 `readMultipleFiles` 批量读取
- [ ] ❌ 不使用 `grepSearch` 搜索代码
- [ ] ✅ 使用 context-gatherer subagent
- [ ] ✅ 提供清晰的探索目标
- [ ] ✅ 指定需要关注的模式和最佳实践
- [ ] ✅ 信任 subagent 返回的结果

**示例**：
```python
# ✅ 正确做法
result = invokeSubAgent(
    name="context-gatherer",
    prompt="""Explore backend codebase for authentication related files.
    
    Focus on:
    1. Existing authentication patterns
    2. JWT token handling
    3. Password hashing methods
    4. API endpoint structure
    
    Provide a summary of current implementation and best practices.""",
    explanation="Gathering authentication context"
)
# 返回：现有模式和最佳实践（~5K tokens）

# ❌ 错误做法
files = [
    "backend/app/routers/auth.py",
    "backend/app/services/auth_service.py",
    "backend/app/core/password.py",
    # ... 20 个文件
]
contents = readMultipleFiles(
    paths=files,
    explanation="Reading auth files"
)
# 问题：加载 50K tokens
```

### 3.3 场景 3：生成后端代码

**任务**：使用 Codex 生成后端代码

**检查清单**：
- [ ] ❌ 不直接调用 `mcp_codex_codex`
- [ ] ❌ 不在主 Agent 上下文中生成代码
- [ ] ✅ 使用 general-purpose subagent
- [ ] ✅ 提供清晰的生成要求
- [ ] ✅ 指定需要遵循的规范
- [ ] ✅ 记录返回的 SESSION_ID
- [ ] ✅ 使用 SESSION_ID 进行续问

**示例**：
```python
# ✅ 正确做法
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Codex MCP to generate authentication API code.
    
    Requirements:
    1. FastAPI router with JWT authentication
    2. Password hashing with bcrypt
    3. Input validation with Pydantic
    4. Error handling for all edge cases
    
    Follow the patterns from context-gatherer results.
    Use sandbox="read-only" mode.
    Working directory: D:\\gemini-main\\gemini-main\\backend""",
    explanation="Parallel code generation with Codex"
)
# 返回：生成的代码 + SESSION_ID

# ❌ 错误做法
result = mcp_codex_codex(
    PROMPT="Generate authentication API",
    sandbox="read-only",
    cd="D:\\gemini-main\\gemini-main\\backend"
)
# 问题：占用主 Agent 上下文，无法并行
```

### 3.4 场景 4：生成前端代码

**任务**：使用 Gemini 生成前端代码

**检查清单**：
- [ ] ❌ 不直接调用 `mcp_gemini_gemini`
- [ ] ❌ 不在主 Agent 上下文中生成代码
- [ ] ✅ 使用 general-purpose subagent
- [ ] ✅ 提供清晰的生成要求
- [ ] ✅ 指定需要遵循的规范
- [ ] ✅ 记录返回的 SESSION_ID
- [ ] ✅ 使用 SESSION_ID 进行续问

**示例**：
```python
# ✅ 正确做法
result = invokeSubAgent(
    name="general-task-execution",
    prompt="""Use Gemini MCP to generate React component code.
    
    Requirements:
    1. TypeScript with strict types
    2. React Hooks for state management
    3. Tailwind CSS for styling
    4. Accessibility compliant
    
    Follow the patterns from context-gatherer results.
    Use sandbox=False mode.
    Working directory: D:\\gemini-main\\gemini-main\\frontend""",
    explanation="Parallel code generation with Gemini"
)
# 返回：生成的代码 + SESSION_ID

# ❌ 错误做法
result = mcp_gemini_gemini(
    PROMPT="Generate React component",
    sandbox=False,
    cd="D:\\gemini-main\\gemini-main\\frontend"
)
# 问题：占用主 Agent 上下文，无法并行
```

### 3.5 场景 5：写入文件

**任务**：写入生成的代码到文件

**检查清单**：
- [ ] ❌ 不使用 `fsWrite`
- [ ] ❌ 不使用 `fsAppend`
- [ ] ❌ 不使用 `strReplace`
- [ ] ✅ 使用 Desktop Commander MCP
- [ ] ✅ 使用绝对路径
- [ ] ✅ 新文件使用 `write_file`
- [ ] ✅ 修改文件使用 `edit_block`
- [ ] ✅ 验证文件写入成功

**示例**：
```python
# ✅ 正确做法（新文件）
mcp_desktop_commander_mcp_write_file(
    path="D:\\gemini-main\\gemini-main\\backend\\app\\routers\\auth.py",
    content="""from fastapi import APIRouter, Depends
from ..services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def login(credentials: LoginRequest):
    return await AuthService.login(credentials)
""",
    mode="rewrite"
)

# ✅ 正确做法（修改文件）
mcp_desktop_commander_mcp_edit_block(
    file_path="D:\\gemini-main\\gemini-main\\backend\\app\\routers\\auth.py",
    old_string="""@router.post("/login")
async def login(credentials: LoginRequest):
    return await AuthService.login(credentials)""",
    new_string="""@router.post("/login")
async def login(
    credentials: LoginRequest,
    user_id: int = Depends(require_user_id)
):
    return await AuthService.login(credentials, user_id)"""
)

# ❌ 错误做法
fsWrite(
    path="backend/app/routers/auth.py",
    text="..."
)
# 问题：不符合架构规范
```

### 3.6 场景 6：缓存文档摘要

**任务**：缓存 Context7 返回的文档摘要

**检查清单**：
- [ ] ✅ 使用 Redis MCP 缓存摘要
- [ ] ✅ 设置合理的过期时间（24 小时）
- [ ] ✅ 包含文件哈希值用于验证
- [ ] ✅ 读取前先检查缓存
- [ ] ✅ 缓存失效时重新生成

**示例**：
```python
# ✅ 缓存摘要
import json
import hashlib

# 1. 生成文件哈希
file_hash = hashlib.md5(file_content.encode()).hexdigest()

# 2. 缓存摘要
mcp_redis_set(
    key="context7:summary:specs/feature/requirements",
    value=json.dumps({
        "summary": result["summary"],
        "key_points": result["key_points"],
        "last_updated": "2026-01-10",
        "file_hash": file_hash
    }),
    expireSeconds=86400  # 24 小时
)

# 3. 读取缓存
cached = mcp_redis_get(key="context7:summary:specs/feature/requirements")
if cached:
    summary = json.loads(cached)
    # 验证文件是否更新
    if summary["file_hash"] == current_file_hash:
        use_cached_summary(summary)
    else:
        regenerate_summary()
```

---

## 4. 性能指标

### 4.1 Token 使用对比

| 场景 | 传统方法 | 优化方法 | 节省比例 |
|------|---------|---------|---------|
| 读取 Spec 文档 | 20K tokens | 2K tokens | 90% |
| 探索项目代码 | 50K tokens | 5K tokens | 90% |
| 生成后端代码 | 30K tokens | 3K tokens | 90% |
| 生成前端代码 | 30K tokens | 3K tokens | 90% |
| **总计** | **130K tokens** | **13K tokens** | **90%** |

### 4.2 执行时间对比

| 场景 | 传统方法 | 优化方法 | 节省比例 |
|------|---------|---------|---------|
| 读取文档 | 10s | 3s | 70% |
| 探索代码 | 20s | 5s | 75% |
| 生成代码（串行） | 60s | 15s | 75% |
| 生成代码（并行） | 60s | 12s | 80% |
| **总计** | **150s** | **35s** | **77%** |

### 4.3 并行度对比

| 方法 | 并行任务数 | 说明 |
|------|-----------|------|
| 传统方法 | 1 | 主 Agent 串行执行 |
| 优化方法 | 5+ | 多个 subagents 并行执行 |
| **提升** | **5x** | 并行度提升 5 倍 |

---

## 5. 常见错误和修正

### 5.1 错误 1：直接读取大文件

**错误代码**：
```python
content = readFile(
    path=".kiro/specs/feature/requirements.md",
    explanation="Reading requirements"
)
# 问题：加载 20K tokens
```

**修正代码**：
```python
result = mcp_context7_query_docs(
    libraryId="/project/specs/feature",
    query="Summarize requirements, design, and tasks"
)
# Token 节省：90%
```

### 5.2 错误 2：批量读取多个文件

**错误代码**：
```python
files = [
    "backend/app/routers/auth.py",
    "backend/app/services/auth_service.py",
    # ... 20 个文件
]
contents = readMultipleFiles(
    paths=files,
    explanation="Reading auth files"
)
# 问题：加载 50K tokens
```

**修正代码**：
```python
result = invokeSubAgent(
    name="context-gatherer",
    prompt="Explore backend authentication code",
    explanation="Gathering auth context"
)
# Token 节省：90%
```

### 5.3 错误 3：主 Agent 直接调用 Codex

**错误代码**：
```python
result = mcp_codex_codex(
    PROMPT="Generate authentication API",
    sandbox="read-only",
    cd="D:\\gemini-main\\gemini-main\\backend"
)
# 问题：占用主 Agent 上下文
```

**修正代码**：
```python
result = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Codex to generate authentication API",
    explanation="Parallel code generation"
)
# Token 节省：90%，并行度提升 5x
```

### 5.4 错误 4：使用 fsWrite 写入文件

**错误代码**：
```python
fsWrite(
    path="backend/app/routers/auth.py",
    text="..."
)
# 问题：不符合架构规范
```

**修正代码**：
```python
mcp_desktop_commander_mcp_write_file(
    path="D:\\gemini-main\\gemini-main\\backend\\app\\routers\\auth.py",
    content="...",
    mode="rewrite"
)
# 符合架构规范
```

### 5.5 错误 5：重复读取相同文档

**错误代码**：
```python
# 第一次读取
content1 = readFile(path=".kiro/specs/feature/requirements.md")

# ... 一些操作 ...

# 第二次读取（重复）
content2 = readFile(path=".kiro/specs/feature/requirements.md")
# 问题：浪费 Token
```

**修正代码**：
```python
# 第一次读取
result = mcp_context7_query_docs(
    libraryId="/project/specs/feature",
    query="Summarize requirements"
)

# 缓存摘要
mcp_redis_set(
    key="context7:summary:specs/feature/requirements",
    value=json.dumps(result),
    expireSeconds=86400
)

# 第二次读取（使用缓存）
cached = mcp_redis_get(key="context7:summary:specs/feature/requirements")
if cached:
    result = json.loads(cached)
# Token 节省：100%（第二次读取）
```

---

## 6. 实施检查清单

### 6.1 任务开始前

- [ ] 识别任务类型（读取文档/探索代码/生成代码/写入文件）
- [ ] 查看本检查清单，确认正确的工具使用方法
- [ ] 检查是否有 Redis 缓存可用
- [ ] 规划并行执行策略（如果适用）

### 6.2 读取文档时

- [ ] ❌ 不使用 `readFile`
- [ ] ❌ 不使用 `readMultipleFiles`
- [ ] ❌ 不使用 Desktop Commander 读取
- [ ] ✅ 使用 Context7 MCP
- [ ] ✅ 提供清晰的 query 参数
- [ ] ✅ 缓存返回的摘要

### 6.3 探索代码时

- [ ] ❌ 不使用 `readFile` 逐个读取
- [ ] ❌ 不使用 `readMultipleFiles` 批量读取
- [ ] ❌ 不使用 `grepSearch` 搜索代码
- [ ] ✅ 使用 context-gatherer subagent
- [ ] ✅ 提供清晰的探索目标
- [ ] ✅ 信任 subagent 返回的结果

### 6.4 生成代码时

- [ ] ❌ 不直接调用 Codex/Gemini MCP
- [ ] ❌ 不在主 Agent 上下文中生成
- [ ] ✅ 使用 general-purpose subagent
- [ ] ✅ 提供清晰的生成要求
- [ ] ✅ 记录 SESSION_ID
- [ ] ✅ 规划并行执行

### 6.5 写入文件时

- [ ] ❌ 不使用 `fsWrite`
- [ ] ❌ 不使用 `fsAppend`
- [ ] ❌ 不使用 `strReplace`
- [ ] ✅ 使用 Desktop Commander MCP
- [ ] ✅ 使用绝对路径
- [ ] ✅ 验证写入成功

### 6.6 任务完成后

- [ ] 检查 Token 使用情况
- [ ] 验证是否遵循了所有规则
- [ ] 记录任何违规行为
- [ ] 更新 Redis 缓存（如果适用）

---

## 7. 故障排除

### 7.1 问题：Context7 MCP 返回空结果

**症状**：
```python
result = mcp_context7_query_docs(
    libraryId="/project/specs/feature",
    query="Summarize requirements"
)
# 返回：空或错误
```

**解决方案**：
1. 检查 `libraryId` 是否正确
2. 确认文档是否存在
3. 简化 `query` 参数
4. 检查 Context7 MCP 配置

### 7.2 问题：context-gatherer 超时

**症状**：
```python
result = invokeSubAgent(
    name="context-gatherer",
    prompt="Explore entire codebase",
    explanation="Gathering context"
)
# 错误：超时
```

**解决方案**：
1. 缩小探索范围（指定具体目录）
2. 提供更清晰的探索目标
3. 分步执行（先探索后端，再探索前端）

### 7.3 问题：general-purpose subagent 返回错误代码

**症状**：
```python
result = invokeSubAgent(
    name="general-task-execution",
    prompt="Use Codex to generate code",
    explanation="Code generation"
)
# 返回：有错误的代码
```

**解决方案**：
1. 提供更详细的生成要求
2. 包含现有代码模式和最佳实践
3. 使用 SESSION_ID 反馈问题进行修正
4. 最多迭代 3 次

### 7.4 问题：Desktop Commander 写入失败

**症状**：
```python
mcp_desktop_commander_mcp_write_file(
    path="backend/app/routers/auth.py",
    content="...",
    mode="rewrite"
)
# 错误：写入失败
```

**解决方案**：
1. 检查路径是否为绝对路径
2. 确认文件未被占用
3. 检查权限是否足够
4. 验证目录是否存在

---

## 8. 总结

### 8.1 核心要点

1. **Context7 MCP**：读取所有文档（Spec、库文档、API 文档）
2. **context-gatherer subagent**：探索项目代码，收集相关上下文
3. **general-purpose subagent**：调用 Codex/Gemini 生成代码
4. **Redis MCP**：缓存文档摘要，避免重复读取
5. **Desktop Commander MCP**：写入文件，编辑文件（不用于读取）
6. **Hooks**：自动化重复任务，减少主 Agent 负担

### 8.2 预期效果

| 指标 | 传统方法 | 优化方法 | 提升 |
|------|---------|---------|------|
| Token 使用 | 130K | 13K | 90% ↓ |
| 执行时间 | 150s | 35s | 77% ↓ |
| 并行度 | 1 | 5+ | 5x ↑ |

### 8.3 快速参考

**读取文档**：
```python
mcp_context7_query_docs(libraryId="...", query="...")
```

**探索代码**：
```python
invokeSubAgent(name="context-gatherer", prompt="...", explanation="...")
```

**生成代码**：
```python
invokeSubAgent(name="general-task-execution", prompt="Use Codex/Gemini to...", explanation="...")
```

**写入文件**：
```python
mcp_desktop_commander_mcp_write_file(path="...", content="...", mode="rewrite")
```

**缓存摘要**：
```python
mcp_redis_set(key="...", value=json.dumps(...), expireSeconds=86400)
```

---

**最后更新**：2026-01-10  
**版本**：v1.0.0  
**维护者**：技术团队
