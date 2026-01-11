---
inclusion: manual
---

# 新功能开发流程

## 核心原则

### 1. Spec 文档优先（第一原则）⭐

**在任何代码实现前，必须先完成 Spec 文档**

#### 三个必需文档

| 文档 | 职责 | 内容 |
|------|------|------|
| `requirements.md` | 需求定义 | 用户故事、验收标准、EARS 模式需求 |
| `design.md` | 设计方案 | 系统架构、组件接口、数据模型 |
| `tasks.md` | 任务分解 | 可执行编码任务、依赖关系 |

---

## 开发流程

### 第一阶段：需求分析

```
1. 理解用户需求
   └─ 与用户确认功能范围和目标
   
2. 创建 requirements.md
   └─ 定义用户故事和验收标准
   
3. 用户审查需求
   └─ 确认需求完整性和准确性
```

#### requirements.md 模板

```markdown
# Requirements Document

## Introduction
[功能概述和背景]

## Glossary
- **术语1**: 定义
- **术语2**: 定义

## Requirements

### Requirement 1: [需求名称]

**User Story:** As a [角色], I want [功能], so that [收益]

#### Acceptance Criteria
1. WHEN [事件], THE [System] SHALL [响应]
2. WHEN [事件], THE [System] SHALL [响应]

#### Priority
High / Medium / Low

#### Dependencies
- Requirement 2

### Requirement 2: [需求名称]

**User Story:** As a [角色], I want [功能], so that [收益]

#### Acceptance Criteria
1. WHEN [事件], THE [System] SHALL [响应]

#### Priority
High / Medium / Low

## Non-Functional Requirements

### Performance
- 响应时间 < 2s
- 并发用户 > 100

### Security
- JWT 认证
- API 密钥加密

### Scalability
- 支持水平扩展
- 数据库分片

## Constraints
- 必须使用 FastAPI
- 必须支持 TypeScript
- 必须兼容现有架构
```

---

### 第二阶段：设计方案

```
1. 阅读 requirements.md
   └─ 理解所有需求和约束
   
2. 设计系统架构
   └─ 确定组件和接口
   
3. 创建 design.md
   └─ 文档化设计决策
   
4. 用户审查设计
   └─ 确认设计可行性
```

#### design.md 模板

```markdown
# Design Document

## Architecture Overview

### System Architecture

```
Frontend (React + TypeScript)
    ↓ HTTP/WebSocket
Backend (FastAPI + Python)
    ↓ SQL
Database (SQLite/PostgreSQL)
```

### Component Diagram

```
┌─────────────────┐
│  Frontend       │
│  - ChatView     │
│  - MessageList  │
│  - InputArea    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Backend        │
│  - Router       │
│  - Service      │
│  - Model        │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Database       │
│  - Users        │
│  - Sessions     │
│  - Messages     │
└─────────────────┘
```

## Component Design

### Frontend Components

#### ChatView (Main Component)
- **职责**: 协调聊天界面
- **Props**: None
- **State**: 
  - messages: Message[]
  - isLoading: boolean
- **Hooks**:
  - useChatLogic()
  - useFileUpload()

#### MessageList (Sub Component)
- **职责**: 显示消息列表
- **Props**:
  - messages: Message[]
- **State**: None

### Backend Services

#### ChatService
- **职责**: 处理聊天逻辑
- **Methods**:
  - send_message(session_id, message, model)
  - get_chat_history(session_id)
- **Dependencies**:
  - ProviderFactory
  - Database

### Data Models

#### User Model
```python
class User(Base):
    id: int
    username: str
    email: str
    created_at: datetime
```

#### ChatSession Model
```python
class ChatSession(Base):
    id: int
    user_id: int
    session_id: str
    provider: str
    model: str
    created_at: datetime
```

#### ChatMessage Model
```python
class ChatMessage(Base):
    id: int
    session_id: str
    role: str
    content: str
    timestamp: datetime
```

## API Design

### Endpoints

#### POST /api/chat/
- **描述**: 发送聊天消息
- **请求**:
  ```json
  {
    "session_id": "string",
    "message": "string",
    "model": "string",
    "provider": "string"
  }
  ```
- **响应**:
  ```json
  {
    "message": "string",
    "role": "string",
    "timestamp": "datetime"
  }
  ```

#### GET /api/chat/{session_id}/history
- **描述**: 获取聊天历史
- **响应**:
  ```json
  {
    "messages": [
      {
        "role": "string",
        "content": "string",
        "timestamp": "datetime"
      }
    ]
  }
  ```

## Database Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);
```

## Design Decisions

### Decision 1: 使用 FastAPI
- **原因**: 高性能、异步支持、自动文档生成
- **替代方案**: Flask, Django
- **权衡**: 学习曲线 vs 性能优势

### Decision 2: 使用 SQLite
- **原因**: 简单、无需额外配置、适合开发
- **替代方案**: PostgreSQL, MySQL
- **权衡**: 功能限制 vs 简单性

## Security Considerations

- JWT 认证
- API 密钥加密存储
- SQL 注入防护（使用 ORM）
- XSS 防护（输入验证）
- CORS 配置

## Performance Considerations

- 数据库索引（session_id, user_id）
- 连接池（数据库连接）
- 缓存（Redis）
- 异步 I/O（FastAPI + asyncio）

## Testing Strategy

- 单元测试（pytest）
- 集成测试（API 端点）
- E2E 测试（Playwright）
- 覆盖率目标：> 80%
```

---

### 第三阶段：任务分解

```
1. 阅读 requirements.md 和 design.md
   └─ 理解需求和设计
   
2. 分解为可执行任务
   └─ 每个任务 < 4 小时
   
3. 创建 tasks.md
   └─ 定义任务和依赖关系
   
4. 自动批准文档
   └─ 进入代码实现阶段
```

#### tasks.md 模板

```markdown
# Implementation Tasks

## Task Breakdown

### Phase 1: 数据库和模型（2 小时）

#### Task 1.1: 创建数据库模型
- **描述**: 创建 User, ChatSession, ChatMessage 模型
- **文件**: `backend/app/models/user.py`, `backend/app/models/chat.py`
- **验收标准**:
  - [ ] 所有模型定义完成
  - [ ] 关系正确配置
  - [ ] 索引正确创建
- **依赖**: None
- **估时**: 1 小时

#### Task 1.2: 创建数据库迁移
- **描述**: 使用 Alembic 创建迁移脚本
- **文件**: `backend/alembic/versions/xxx_create_tables.py`
- **验收标准**:
  - [ ] 迁移脚本生成
  - [ ] 迁移成功执行
  - [ ] 数据库表创建
- **依赖**: Task 1.1
- **估时**: 0.5 小时

#### Task 1.3: 编写模型测试
- **描述**: 测试模型创建、查询、更新、删除
- **文件**: `backend/tests/test_models.py`
- **验收标准**:
  - [ ] 所有 CRUD 操作测试通过
  - [ ] 关系测试通过
  - [ ] 覆盖率 > 90%
- **依赖**: Task 1.1
- **估时**: 0.5 小时

### Phase 2: 后端服务层（4 小时）

#### Task 2.1: 创建 ChatService
- **描述**: 实现聊天服务逻辑
- **文件**: `backend/app/services/chat_service.py`
- **验收标准**:
  - [ ] send_message() 实现
  - [ ] get_chat_history() 实现
  - [ ] 错误处理完整
- **依赖**: Task 1.1
- **估时**: 2 小时

#### Task 2.2: 编写服务测试
- **描述**: 测试 ChatService 所有方法
- **文件**: `backend/tests/test_chat_service.py`
- **验收标准**:
  - [ ] 所有方法测试通过
  - [ ] Mock 外部依赖
  - [ ] 覆盖率 > 85%
- **依赖**: Task 2.1
- **估时**: 1 小时

#### Task 2.3: 集成 ProviderFactory
- **描述**: 集成提供商工厂模式
- **文件**: `backend/app/services/chat_service.py`
- **验收标准**:
  - [ ] 支持多个提供商
  - [ ] 提供商切换正常
  - [ ] 错误处理完整
- **依赖**: Task 2.1
- **估时**: 1 小时

### Phase 3: 后端 API 层（3 小时）

#### Task 3.1: 创建聊天路由
- **描述**: 实现 /api/chat/ 端点
- **文件**: `backend/app/routers/chat.py`
- **验收标准**:
  - [ ] POST /api/chat/ 实现
  - [ ] GET /api/chat/{session_id}/history 实现
  - [ ] 输入验证完整
  - [ ] 错误处理完整
- **依赖**: Task 2.1
- **估时**: 2 小时

#### Task 3.2: 编写 API 测试
- **描述**: 测试所有 API 端点
- **文件**: `backend/tests/test_chat_api.py`
- **验收标准**:
  - [ ] 所有端点测试通过
  - [ ] 错误情况测试通过
  - [ ] 覆盖率 > 80%
- **依赖**: Task 3.1
- **估时**: 1 小时

### Phase 4: 前端组件（5 小时）

#### Task 4.1: 创建 ChatView 组件
- **描述**: 实现主聊天界面
- **文件**: `frontend/components/ChatView.tsx`
- **验收标准**:
  - [ ] 组件渲染正常
  - [ ] 状态管理正确
  - [ ] Props 类型正确
- **依赖**: None
- **估时**: 1.5 小时

#### Task 4.2: 创建 MessageList 组件
- **描述**: 实现消息列表
- **文件**: `frontend/components/MessageList.tsx`
- **验收标准**:
  - [ ] 消息显示正常
  - [ ] 滚动行为正确
  - [ ] 样式符合设计
- **依赖**: Task 4.1
- **估时**: 1 小时

#### Task 4.3: 创建 InputArea 组件
- **描述**: 实现输入区域
- **文件**: `frontend/components/InputArea.tsx`
- **验收标准**:
  - [ ] 输入功能正常
  - [ ] 发送按钮正常
  - [ ] 键盘快捷键支持
- **依赖**: Task 4.1
- **估时**: 1 小时

#### Task 4.4: 创建 useChatLogic Hook
- **描述**: 实现聊天逻辑 Hook
- **文件**: `frontend/hooks/useChatLogic.ts`
- **验收标准**:
  - [ ] 发送消息功能
  - [ ] 获取历史功能
  - [ ] 错误处理
- **依赖**: Task 4.1
- **估时**: 1.5 小时

### Phase 5: 集成和测试（2 小时）

#### Task 5.1: 前后端集成
- **描述**: 连接前端和后端
- **文件**: `frontend/services/api.ts`
- **验收标准**:
  - [ ] API 调用正常
  - [ ] 错误处理完整
  - [ ] 类型定义正确
- **依赖**: Task 3.1, Task 4.4
- **估时**: 1 小时

#### Task 5.2: E2E 测试
- **描述**: 端到端测试
- **文件**: `tests/e2e/test_chat_flow.spec.ts`
- **验收标准**:
  - [ ] 完整聊天流程测试通过
  - [ ] 错误情况测试通过
- **依赖**: Task 5.1
- **估时**: 1 小时

## Task Dependencies

```
Task 1.1 (数据库模型)
    ├─→ Task 1.2 (数据库迁移)
    ├─→ Task 1.3 (模型测试)
    └─→ Task 2.1 (ChatService)
            ├─→ Task 2.2 (服务测试)
            ├─→ Task 2.3 (集成 ProviderFactory)
            └─→ Task 3.1 (聊天路由)
                    ├─→ Task 3.2 (API 测试)
                    └─→ Task 5.1 (前后端集成)
                            └─→ Task 5.2 (E2E 测试)

Task 4.1 (ChatView)
    ├─→ Task 4.2 (MessageList)
    ├─→ Task 4.3 (InputArea)
    └─→ Task 4.4 (useChatLogic)
            └─→ Task 5.1 (前后端集成)
```

## Total Estimation
- Phase 1: 2 小时
- Phase 2: 4 小时
- Phase 3: 3 小时
- Phase 4: 5 小时
- Phase 5: 2 小时
- **Total: 16 小时**

## Risk Assessment

### High Risk
- Task 2.3: 集成 ProviderFactory（复杂度高）
- Task 5.2: E2E 测试（环境依赖）

### Medium Risk
- Task 2.1: ChatService（业务逻辑复杂）
- Task 4.4: useChatLogic（状态管理复杂）

### Low Risk
- Task 1.1: 数据库模型（标准操作）
- Task 4.2: MessageList（简单组件）
```

---

### 第四阶段：代码实现

```
1. 按照 tasks.md 顺序执行任务
   └─ 遵循依赖关系
   
2. 每完成一个任务
   └─ 运行测试
   └─ 标记任务完成
   
3. 遵循场景规则
   └─ 后端开发 → backend-development.md
   └─ 前端开发 → frontend-development.md
   └─ Gemini 集成 → gemini-integration.md
   └─ MCP 协作 → mcp-collaboration.md
```

---

## 开发检查清单

### Spec 文档阶段

- [ ] 创建 requirements.md
- [ ] 定义所有用户故事
- [ ] 定义所有验收标准
- [ ] 用户审查需求
- [ ] 创建 design.md
- [ ] 设计系统架构
- [ ] 设计组件接口
- [ ] 设计数据模型
- [ ] 设计 API 端点
- [ ] 用户审查设计
- [ ] 创建 tasks.md
- [ ] 分解所有任务
- [ ] 定义任务依赖
- [ ] 估算任务时间
- [ ] 自动批准文档

### 代码实现阶段

- [ ] 按照 tasks.md 顺序执行
- [ ] 遵循场景规则
- [ ] 每个任务完成后运行测试
- [ ] 标记任务完成状态
- [ ] 更新文档（如果需要）

### 完成阶段

- [ ] 所有任务完成
- [ ] 所有测试通过
- [ ] 代码覆盖率达标
- [ ] 代码审查通过
- [ ] 文档更新完成
- [ ] 用户验收测试通过

---

## 最佳实践

### 1. 需求必须可验证

```markdown
# ❌ 错误示例
- 系统应该快速响应

# ✅ 正确示例
- WHEN 用户发送消息, THE System SHALL 在 2 秒内返回响应
```

### 2. 设计必须可实现

```markdown
# ❌ 错误示例
- 使用最先进的 AI 技术

# ✅ 正确示例
- 使用 Google Gemini API 进行聊天
- 使用 Imagen 3 API 进行图像生成
```

### 3. 任务必须可执行

```markdown
# ❌ 错误示例
- 实现聊天功能

# ✅ 正确示例
- Task 2.1: 创建 ChatService
  - 实现 send_message() 方法
  - 实现 get_chat_history() 方法
  - 添加错误处理
  - 估时: 2 小时
```

---

## 常见问题

### 问题 1：需求不明确

**解决方案**：
1. 与用户确认需求
2. 使用 EARS 模式定义需求
3. 添加验收标准

### 问题 2：设计过于复杂

**解决方案**：
1. 简化架构
2. 遵循 KISS 原则
3. 优先实现核心功能

### 问题 3：任务估时不准确

**解决方案**：
1. 参考历史数据
2. 添加缓冲时间（20%）
3. 定期更新估时

---

## 文档模板路径

- **requirements.md**: `.kiro/specs/[feature-name]/requirements.md`
- **design.md**: `.kiro/specs/[feature-name]/design.md`
- **tasks.md**: `.kiro/specs/[feature-name]/tasks.md`

---

## 相关文档

- [后端开发规范](./backend-development.md)
- [前端开发规范](./frontend-development.md)
- [Gemini 集成指南](./gemini-integration.md)
- [MCP 协作流程](./mcp-collaboration.md)
- [代码重构指南](./refactoring.md)
