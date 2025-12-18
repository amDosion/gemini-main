---
inclusion: always
---

# 多 MCP 协作开发规则

## 概述

本规则定义了 Kiro 与三个 AI MCP 服务（Codex、Gemini、Claude）的协作流程。整个开发过程分为两个阶段：

1. **设计阶段**：Kiro 独立完成 Spec 三文档设计
2. **实现阶段**：三个 MCP 协作完成代码开发

## 第一阶段：Kiro 设计 Spec 文档（前提条件）

在任何代码实现之前，Kiro 必须先完成以下三个文档的设计：

### 1.1 需求文档 `requirements.md`

**Kiro 职责**：
- 与用户沟通，理解功能需求
- 编写用户故事（User Story）
- 定义验收标准（Acceptance Criteria）
- 使用 EARS 模式编写需求
- 创建术语表（Glossary）

**文档结构**：
```markdown
# Requirements Document

## Introduction
[功能概述]

## Glossary
[术语定义]

## Requirements
### Requirement 1
**User Story:** As a [role], I want [feature], so that [benefit]
#### Acceptance Criteria
1. WHEN [event], THE [System] SHALL [response]
2. ...
```

**完成标志**：用户明确批准需求文档

### 1.2 设计文档 `design.md`

**Kiro 职责**：
- 基于需求设计系统架构
- 定义组件和接口
- 设计数据模型
- 制定正确性属性（Correctness Properties）
- 规划测试策略

**文档结构**：
```markdown
# Design Document

## Overview
## Architecture
## Components and Interfaces
## Data Models
## Correctness Properties
## Error Handling
## Testing Strategy
```

**完成标志**：用户明确批准设计文档

### 1.3 任务文档 `tasks.md`

**Kiro 职责**：
- 将设计拆分为可执行的编码任务
- 定义任务依赖关系
- 标注任务类型（后端/前端/全栈）
- 关联需求编号

**文档结构**：
```markdown
# Implementation Plan

- [ ] 1. 任务组名称
  - [ ] 1.1 后端任务：实现 XXX API
    - 类型：backend
    - Requirements: 1.1, 1.2
  - [ ] 1.2 前端任务：实现 XXX 组件
    - 类型：frontend
    - Requirements: 2.1
```

**完成标志**：用户明确批准任务文档

---

## 第二阶段：MCP 协作实现

**前提条件**：三个 Spec 文档已全部完成并获得用户批准

### 2.1 MCP 角色分工

| MCP 服务 | 角色 | 职责范围 | 调用工具 |
|---------|------|---------|---------|
| **Codex** | 后端开发者 | Python、FastAPI、SQLAlchemy、Redis、数据库操作 | `mcp_codex_codex` |
| **Gemini** | 前端开发者 | TypeScript、Vue、React、CSS、组件开发 | `mcp_gemini_gemini` |
| **Claude** | 代码分析师 | 代码搜索、文件读取、方案分析、代码审查 | `mcp_claude_code_mcp_*` |
| **Kiro** | 项目经理 | 文件写入、任务管理、流程协调 | `fsWrite`, `strReplace`, `taskStatus` |

### 2.2 实现流程

当用户指定 Spec 目录（如 `.kiro/specs/xxx/`）开始实现时：

```
┌─────────────────────────────────────────────────────────────┐
│  步骤 1：Claude MCP 读取文档                                 │
│  ├─ mcp_claude_code_mcp_readFile({spec}/design.md)          │
│  ├─ mcp_claude_code_mcp_readFile({spec}/requirements.md)    │
│  └─ mcp_claude_code_mcp_readFile({spec}/tasks.md)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 2：逐个执行任务                                        │
│  └─ 对每个未完成的任务执行步骤 3-7                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 3：Claude MCP 分析任务                                 │
│  ├─ mcp_claude_code_mcp_grep 搜索相关代码                   │
│  ├─ mcp_claude_code_mcp_readFile 读取相关文件               │
│  └─ mcp_claude_code_mcp_think 分析实现方案                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 4：判断任务类型并分配 MCP                              │
│  ├─ 后端任务 → Codex MCP                                    │
│  ├─ 前端任务 → Gemini MCP                                   │
│  └─ 全栈任务 → Codex + Gemini MCP                           │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  步骤 5a：     │ │  步骤 5b：     │ │  步骤 5c：     │
│  Codex 编写    │ │  Gemini 编写   │ │  两者分别编写  │
│  后端代码      │ │  前端代码      │ │  各自代码      │
└────────────────┘ └────────────────┘ └────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 6：Kiro 写入文件                                       │
│  ├─ fsWrite 创建新文件                                      │
│  └─ strReplace 修改现有文件                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 7：Claude MCP 代码审查                                 │
│  ├─ mcp_claude_code_mcp_codeReview 审查代码                 │
│  ├─ 发现问题 → 返回步骤 4 修复                              │
│  └─ 审查通过 → 继续                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 8：Kiro 标记任务完成                                   │
│  └─ taskStatus(task, "completed")                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    [继续下一个任务]
```

### 2.3 任务类型判断规则

**后端任务关键词**：
- `backend`, `api`, `endpoint`, `route`
- `database`, `model`, `schema`, `migration`
- `service`, `repository`, `worker`
- `Python`, `FastAPI`, `SQLAlchemy`, `Redis`

**前端任务关键词**：
- `frontend`, `component`, `view`, `page`
- `style`, `CSS`, `UI`, `UX`
- `TypeScript`, `Vue`, `React`, `hook`
- `store`, `state`, `composable`

**全栈任务关键词**：
- `fullstack`, `both`, `end-to-end`
- 同时涉及 API 和组件

### 2.4 MCP 调用规范

#### Codex MCP 调用（后端）

```python
mcp_codex_codex(
    PROMPT="""
    ## 任务
    {任务描述}
    
    ## 需求
    {相关需求内容}
    
    ## 设计
    {相关设计内容}
    
    ## 现有代码
    {Claude 分析得到的相关代码}
    
    ## 要求
    - 使用 Python 3.11+
    - 遵循 FastAPI 最佳实践
    - 包含类型注解
    - 包含文档字符串
    """,
    cd="D:\\gemini-main\\gemini-main\\backend",
    sandbox="read-only"
)
```

#### Gemini MCP 调用（前端）

```python
mcp_gemini_gemini(
    PROMPT="""
    ## 任务
    {任务描述}
    
    ## 需求
    {相关需求内容}
    
    ## 设计
    {相关设计内容}
    
    ## 现有代码
    {Claude 分析得到的相关代码}
    
    ## 要求
    - 使用 TypeScript
    - 遵循 Vue 3 Composition API
    - 包含类型定义
    - 包含注释
    """,
    cd="D:\\gemini-main\\gemini-main\\frontend",
    sandbox=false
)
```

#### Claude MCP 调用（分析与审查）

```python
# 搜索相关代码
mcp_claude_code_mcp_grep(
    pattern="cache|缓存",
    path="D:\\gemini-main\\gemini-main"
)

# 读取文件
mcp_claude_code_mcp_readFile(
    file_path="D:\\gemini-main\\gemini-main\\backend\\app\\services\\cache.py"
)

# 分析方案
mcp_claude_code_mcp_think(
    thought="分析缓存实现方案：1. 需要考虑... 2. 最佳实践是..."
)

# 代码审查
mcp_claude_code_mcp_codeReview(
    code="def get_cache(): ..."
)
```

### 2.5 代码审查标准

Claude MCP 审查时必须检查：

| 类别 | 检查项 |
|-----|-------|
| **错误** | 逻辑错误、边界条件、空值处理、异常处理 |
| **安全** | SQL 注入、XSS、CSRF、敏感数据暴露、认证授权 |
| **性能** | N+1 查询、内存泄漏、不必要的计算、缓存策略 |
| **规范** | 命名规范、代码风格、注释完整性、类型注解 |
| **测试** | 可测试性、边界用例覆盖 |

---

## 完整示例

```markdown
## 用户请求
请执行 .kiro/specs/frontend-cache/ 目录下的任务

## AI 执行流程

### 步骤 1：读取 Spec 文档

#### 1.1 读取设计文档
mcp_claude_code_mcp_readFile("D:\\gemini-main\\gemini-main\\.kiro\\specs\\frontend-cache\\design.md")
→ 理解缓存系统架构、组件设计、数据模型

#### 1.2 读取需求文档
mcp_claude_code_mcp_readFile("D:\\gemini-main\\gemini-main\\.kiro\\specs\\frontend-cache\\requirements.md")
→ 理解用户故事、验收标准

#### 1.3 读取任务列表
mcp_claude_code_mcp_readFile("D:\\gemini-main\\gemini-main\\.kiro\\specs\\frontend-cache\\tasks.md")
→ 获取待执行任务列表

### 步骤 2：执行任务 1.1（后端：实现缓存服务）

#### 2.1 Claude 分析
mcp_claude_code_mcp_grep(pattern="cache", path="backend")
mcp_claude_code_mcp_readFile("backend/app/services/base.py")
mcp_claude_code_mcp_think(thought="缓存服务需要...")

#### 2.2 Codex 编写后端代码
mcp_codex_codex(
    PROMPT="实现 CacheService 类，包含 get/set/delete 方法...",
    cd="backend",
    sandbox="read-only"
)
→ 返回 Python 代码

#### 2.3 Kiro 写入文件
fsWrite("backend/app/services/cache.py", code)

#### 2.4 Claude 审查
mcp_claude_code_mcp_codeReview(code)
→ 审查通过

#### 2.5 标记完成
taskStatus("1.1 实现缓存服务", "completed")

### 步骤 3：执行任务 1.2（前端：实现缓存状态组件）

#### 3.1 Claude 分析
mcp_claude_code_mcp_grep(pattern="component", path="frontend/src")
mcp_claude_code_mcp_think(thought="组件需要...")

#### 3.2 Gemini 编写前端代码
mcp_gemini_gemini(
    PROMPT="实现 CacheStatus.vue 组件，显示缓存状态...",
    cd="frontend",
    sandbox=false
)
→ 返回 Vue 代码

#### 3.3 Kiro 写入文件
fsWrite("frontend/src/components/CacheStatus.vue", code)

#### 3.4 Claude 审查
mcp_claude_code_mcp_codeReview(code)
→ 审查通过

#### 3.5 标记完成
taskStatus("1.2 实现缓存状态组件", "completed")

### 继续执行后续任务...
```

---

## 注意事项

1. **前提条件**：必须先有 Kiro 设计的三个 Spec 文档
2. **顺序执行**：先读文档，再逐个执行任务
3. **正确分配**：后端用 Codex，前端用 Gemini，分析审查用 Claude
4. **必须审查**：每次代码修改后必须用 Claude 审查
5. **逐个完成**：一个任务完成后再执行下一个
6. **Gemini 配置**：调用时设置 `sandbox=false`
7. **Codex 配置**：调用时设置 `sandbox="read-only"`

---

## 第三阶段：高级工具规则（必须遵守）

以下规则是对基础流程的强制性优化，所有任务执行时必须遵守。

### 3.1 文件操作 - 统一使用 Desktop Commander MCP

**所有文件操作必须使用 Desktop Commander MCP**，不再使用 Kiro 原生工具或 Claude MCP 的文件工具。

| 操作 | 工具 | 说明 |
|------|------|------|
| 读取文件 | `mcp_desktop_commander_mcp_read_file` | 必须使用绝对路径 |
| 批量读取 | `mcp_desktop_commander_mcp_read_multiple_files` | 一次读取多个文件 |
| 写入文件 | `mcp_desktop_commander_mcp_write_file` | mode: rewrite/append |
| 精确替换 | `mcp_desktop_commander_mcp_edit_block` | 修改现有文件必须用此工具 |
| 搜索代码 | `mcp_desktop_commander_mcp_start_search` | searchType: files/content |
| 目录列表 | `mcp_desktop_commander_mcp_list_directory` | 查看目录结构 |
| 文件信息 | `mcp_desktop_commander_mcp_get_file_info` | 获取行数、大小 |

**调用示例**：
```python
# 读取文件
mcp_desktop_commander_mcp_read_file(path="/absolute/path/to/file.ts")

# 写入新文件
mcp_desktop_commander_mcp_write_file(
    path="/absolute/path/to/new_file.ts",
    content="// 文件内容",
    mode="rewrite"
)

# 精确替换（修改现有文件）
mcp_desktop_commander_mcp_edit_block(
    file_path="/absolute/path/to/file.ts",
    old_string="原始代码块",
    new_string="新代码块"
)

# 搜索代码内容
mcp_desktop_commander_mcp_start_search(
    path="/absolute/path/to/project",
    pattern="searchPattern",
    searchType="content",
    filePattern="*.ts"
)
```

### 3.2 深度思考 - Sequential Thinking MCP

**复杂任务必须使用 Sequential Thinking 进行多轮推理**：

```python
mcp_sequential_thinking_sequentialthinking(
    thought="当前思考内容...",
    thoughtNumber=1,        # 当前轮次
    totalThoughts=5,        # 预计总轮次
    nextThoughtNeeded=True  # 是否需要继续
)
```

**必须使用的场景**：
- 架构设计决策
- 复杂 Bug 排查
- 性能优化分析
- 代码重构策略
- 任务开始前的方案分析
- 代码审查时的自问自答

### 3.3 上下文持久化 - Redis MCP

**所有 Spec 执行必须保存上下文到 Redis**，确保跨会话可恢复。

**Key 命名规范**：
| Key 模式 | 用途 |
|---------|------|
| `spec:{name}:context` | 当前任务进度、已完成任务、关键文件 |
| `spec:{name}:decisions` | 设计决策记录 |
| `api:contract:{endpoint}` | API 契约定义 |
| `task:{spec}:{id}:result` | 单个任务执行结果 |

**会话开始时**：
```python
# 检查是否有未完成的 Spec
mcp_redis_list(pattern="spec:*:context")

# 恢复上下文
mcp_redis_get(key="spec:{name}:context")
```

**任务完成时**：
```python
# 保存进度
mcp_redis_set(
    key="spec:{name}:context",
    value='{"current_task":"1.2","completed":["1.1"],"key_files":[...]}',
    expireSeconds=604800  # 7天
)
```

### 3.4 前后端 API 一致性测试

**当后端 API 开发完成后，必须编写前端 API 测试**，验证完整数据流。

#### 3.4.1 后端 API 分析

```python
# 分析 FastAPI 项目结构
mcp_fastapi_mcp_server_analyze_fastapi_structure()

# 获取所有 API 端点
mcp_fastapi_mcp_server_get_api_endpoints()

# 获取数据模型
mcp_fastapi_mcp_server_get_data_models()

# 搜索特定端点
mcp_fastapi_mcp_server_search_endpoint(pattern="sessions")
```

#### 3.4.2 前端 API 测试要求

后端 API 完成后，前端必须编写对应的**单元测试/集成测试**：

**测试文件位置**：`frontend/__tests__/api/{endpoint}.test.ts`

**测试内容必须包含**：
1. 正常请求 - 验证请求参数和响应数据结构
2. 错误处理 - 验证 4xx/5xx 错误处理
3. 数据类型 - 验证 TypeScript 类型与后端一致
4. 边界条件 - 空数据、大数据量等

**测试示例**：
```typescript
// frontend/__tests__/api/sessions.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { sessionsApi } from '@/services/api/sessions';

describe('Sessions API 数据流测试', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('GET /api/sessions - 获取会话列表', async () => {
    const mockData = [{ id: '1', title: 'Test', createdAt: '2024-01-01' }];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData)
    });

    const result = await sessionsApi.getSessions();
    
    // 验证请求
    expect(fetch).toHaveBeenCalledWith('/api/sessions', expect.objectContaining({
      method: 'GET',
      headers: expect.any(Object)
    }));
    
    // 验证响应数据结构
    expect(result).toBeInstanceOf(Array);
    expect(result[0]).toHaveProperty('id');
    expect(result[0]).toHaveProperty('title');
    expect(result[0]).toHaveProperty('createdAt');
  });

  it('POST /api/sessions - 创建会话', async () => {
    const newSession = { title: 'New Session' };
    const mockResponse = { id: '2', ...newSession, createdAt: '2024-01-01' };
    
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    const result = await sessionsApi.createSession(newSession);
    
    // 验证请求体
    expect(fetch).toHaveBeenCalledWith('/api/sessions', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(newSession)
    }));
    
    // 验证响应
    expect(result.id).toBeDefined();
  });

  it('错误处理 - 500 服务器错误', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error'
    });

    await expect(sessionsApi.getSessions()).rejects.toThrow();
  });

  it('错误处理 - 网络错误', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network Error'));

    await expect(sessionsApi.getSessions()).rejects.toThrow('Network Error');
  });
});
```

#### 3.4.3 数据流验证清单

| 检查项 | 验证方法 | 通过标准 |
|-------|---------|---------|
| API 端点存在 | `mcp_fastapi_mcp_server_search_endpoint` | 返回匹配结果 |
| 请求参数类型 | 对比 Pydantic 模型和 TypeScript 类型 | 类型一致 |
| 响应数据结构 | 前端测试验证字段 | 字段名、类型匹配 |
| 错误处理 | 前端测试覆盖错误场景 | 错误被正确捕获 |
| 认证授权 | 测试带/不带 Token | 权限控制正确 |

#### 3.4.4 保存 API 契约

```python
mcp_redis_set(
    key="api:contract:sessions",
    value='{"endpoint":"/api/sessions","methods":["GET","POST"],"request_types":{...},"response_types":{...}}'
)
```

---

## 优化后的完整流程

```
┌─────────────────────────────────────────────────────────────┐
│  步骤 0：恢复上下文                                          │
│  └─ mcp_redis_get("spec:{name}:context")                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 1：读取 Spec 文档（Desktop Commander）                 │
│  └─ mcp_desktop_commander_mcp_read_multiple_files(...)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 2：深度思考分析（Sequential Thinking）                 │
│  └─ mcp_sequential_thinking_sequentialthinking(...)         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 3：搜索相关代码（Desktop Commander）                   │
│  └─ mcp_desktop_commander_mcp_start_search(...)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 4：生成代码                                            │
│  ├─ 后端 → mcp_codex_codex(sandbox="read-only")             │
│  └─ 前端 → mcp_gemini_gemini(sandbox=false)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 5：写入文件（Desktop Commander）                       │
│  ├─ 新文件 → mcp_desktop_commander_mcp_write_file           │
│  └─ 修改 → mcp_desktop_commander_mcp_edit_block             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 6：代码审查（Claude + Sequential Thinking）            │
│  ├─ mcp_claude_code_mcp_codeReview(code)                    │
│  └─ mcp_sequential_thinking_sequentialthinking(自问自答)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 7：前后端 API 一致性测试（涉及 API 时）                │
│  ├─ mcp_fastapi_mcp_server_get_api_endpoints()              │
│  ├─ 编写前端 API 单元测试                                   │
│  └─ 验证数据流一致性                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 8：保存上下文（Redis）                                 │
│  └─ mcp_redis_set("spec:{name}:context", ...)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤 9：标记任务完成                                        │
│  └─ taskStatus(task, "completed")                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 工具选择速查表

| 需求 | 必须使用的工具 |
|------|---------------|
| 读取文件 | `mcp_desktop_commander_mcp_read_file` |
| 批量读取 | `mcp_desktop_commander_mcp_read_multiple_files` |
| 写入文件 | `mcp_desktop_commander_mcp_write_file` |
| 修改文件 | `mcp_desktop_commander_mcp_edit_block` |
| 搜索代码 | `mcp_desktop_commander_mcp_start_search` |
| 深度思考 | `mcp_sequential_thinking_sequentialthinking` |
| 代码审查 | `mcp_claude_code_mcp_codeReview` |
| 后端开发 | `mcp_codex_codex` |
| 前端开发 | `mcp_gemini_gemini` |
| API 分析 | `mcp_fastapi_mcp_server_*` |
| 上下文存储 | `mcp_redis_*` |
| Lint 检查 | `mcp_eslint_mcp_lint_files` |
