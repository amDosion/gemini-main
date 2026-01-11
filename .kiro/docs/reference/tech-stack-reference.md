# 技术栈详细参考文档

## 概述

本项目采用前后端分离架构，后端使用 Python FastAPI，前端使用 React + TypeScript，支持多个 AI 提供商集成。

---

## 后端技术栈

### 核心框架
- **FastAPI 0.109.0+** - 现代、快速的 Python Web 框架
  - 自动 OpenAPI 文档生成
  - 异步请求处理
  - Pydantic 数据验证
  - 依赖注入系统

- **Uvicorn** - ASGI 服务器
  - 支持 HTTP/1.1 和 HTTP/2
  - WebSocket 支持
  - 自动重载（开发模式）

### 数据库与 ORM
- **SQLAlchemy 2.0+** - Python ORM
  - AsyncSession 支持异步操作
  - 关系模型定义
  - 查询构建器
  - 迁移工具集成

- **Alembic** - 数据库迁移工具
  - 自动生成迁移脚本
  - 版本控制
  - 向前/向后迁移

- **SQLite / PostgreSQL** - 数据库引擎
  - SQLite：开发和小规模部署
  - PostgreSQL：生产环境

### 认证与安全
- **PyJWT** - JWT 令牌生成和验证
  - Access Token（15 分钟）
  - Refresh Token（7 天）
  - HS256 算法

- **Bcrypt** - 密码哈希
  - 慢速哈希算法
  - 盐值自动生成

- **Cryptography (Fernet)** - API 密钥加密
  - 对称加密
  - 密钥存储加密

### AI SDK 集成
- **google-genai 1.55.0+** - Google Gemini 官方 SDK
  - 统一 API（聊天 + 图像生成）
  - 流式响应支持
  - 文件上传 API
  - 工具调用和结构化输出

- **openai** - OpenAI API 客户端
  - ChatGPT 集成
  - 兼容 OpenAI 协议的提供商

- **httpx** - 异步 HTTP 客户端
  - 用于通义千问、其他 API 调用
  - HTTP/2 支持
  - 连接池

### 异步任务
- **Redis Queue + Worker Pool** - 异步任务处理
  - 5 个并发 worker
  - 文件上传队列
  - 任务状态追踪

### 图像处理
- **Pillow** - Python 图像处理库
  - 格式转换
  - 尺寸调整
  - 图像验证

### 文档处理
- **PyPDF** - PDF 提取
  - 文本提取
  - 结构化数据提取
  - 表格识别

### 测试工具
- **pytest** - 测试框架
  - 单元测试
  - 集成测试
  - Fixture 支持

- **pytest-asyncio** - 异步测试支持
- **pytest-cov** - 覆盖率报告
- **pytest-mock** - Mock 支持
- **Hypothesis** - 属性测试

### 开发工具
- **Black** - 代码格式化（行长度 100）
- **Ruff** - 快速 Linter
- **mypy** - 类型检查
- **pip-audit** - 依赖安全扫描

---

## 前端技术栈

### 核心框架
- **React 19.2.1** - UI 库
  - Hooks API
  - 并发渲染
  - 自动批处理

- **TypeScript 5.2** - 类型安全
  - Strict 模式
  - 编译时类型检查
  - 智能提示

### 路由
- **React Router 7.11** - 客户端路由
  - 嵌套路由
  - 懒加载
  - 路由守卫

### 构建工具
- **Vite 6.4.1** - 构建工具
  - ESM 原生支持
  - 极速热更新（HMR）
  - 按需编译
  - 代码分割

### 样式
- **Tailwind CSS 3.4** - 原子化 CSS
  - JIT 模式
  - 自定义设计令牌
  - 响应式设计
  - Dark Mode 支持

### 状态管理
- **React Hooks** - 本地状态管理
  - useState（组件状态）
  - useReducer（复杂状态）
  - useContext（全局状态）
  - useMemo/useCallback（性能优化）

### 数据持久化
- **Dexie.js** - IndexedDB 封装
  - 异步 API
  - 事务支持
  - 查询构建器
  - 版本管理

### HTTP 客户端
- **自定义 apiClient** - 基于 fetch
  - 拦截器（请求/响应）
  - 错误处理
  - 超时控制
  - 取消请求

### AI SDK
- **@google/genai** - Google Gemini 官方 SDK
  - 浏览器环境支持
  - 流式响应
  - 文件上传

### UI 组件
- **Lucide React** - 图标库
  - 轻量级
  - 可定制
  - Tree-shakeable

### Markdown 渲染
- **react-markdown** - Markdown 渲染器
- **react-syntax-highlighter** - 代码高亮
  - 多种主题
  - 语言检测

### 测试工具
- **Vitest 3.2.4** - 测试框架
  - Vite 原生支持
  - Jest 兼容 API
  - 快速执行

- **@testing-library/react** - React 组件测试
  - 用户行为测试
  - 辅助功能测试

### 开发工具
- **Prettier** - 代码格式化
- **ESLint** - 代码检查
- **TypeScript Compiler** - 类型检查

---

## 开发环境

### Node.js
- **版本**：18.x LTS 或更高
- **包管理器**：npm 9.x

### Python
- **版本**：3.10 或更高
- **包管理器**：pip

### 数据库
- **开发**：SQLite 3.x
- **生产**：PostgreSQL 14+

### Redis
- **版本**：7.0+
- **用途**：任务队列、缓存

### Git
- **版本控制**：Git 2.30+
- **代码托管**：GitHub / GitLab / Gitee

---

## 部署架构

### 开发环境
```
前端（Vite Dev Server）：http://localhost:21573
后端（Uvicorn）：http://localhost:21574
数据库（SQLite）：./backend/database.db
Redis：localhost:6379
```

### 生产环境
```
前端：
  - 构建：npm run build
  - 静态文件：dist/
  - 服务器：Nginx / Caddy / Vercel

后端：
  - ASGI：Uvicorn + Gunicorn
  - 进程管理：Systemd / Supervisor
  - 反向代理：Nginx

数据库：
  - PostgreSQL（主数据库）
  - Redis（缓存和队列）

存储：
  - 云存储（阿里云 OSS / AWS S3）
  - 图床（Lsky Pro）
```

---

## API 设计原则

### RESTful API
- **端点命名**：使用复数名词（`/api/sessions`, `/api/models`）
- **HTTP 方法**：
  - GET：查询资源
  - POST：创建资源
  - PUT/PATCH：更新资源
  - DELETE：删除资源

- **状态码**：
  - 200：成功
  - 201：创建成功
  - 400：请求参数错误
  - 401：未认证
  - 403：无权限
  - 404：资源不存在
  - 429：速率限制
  - 500：服务器错误

### 流式响应
- **格式**：Server-Sent Events (SSE)
- **MIME 类型**：`text/event-stream`
- **示例**：
  ```
  data: {"type": "content", "text": "Hello"}

  data: {"type": "content", "text": " World"}

  data: {"type": "done"}
  ```

### 错误格式
```json
{
  "error": "Invalid API key",
  "error_code": "AUTHENTICATION_ERROR",
  "status_code": 401,
  "details": {
    "provider": "google",
    "model": "gemini-2.0-flash-exp"
  }
}
```

---

## 设计模式

### 后端模式

#### 1. Factory Pattern（工厂模式）
- **用途**：创建 AI 提供商服务实例
- **实现**：`ProviderFactory`
- **示例**：
  ```python
  service = ProviderFactory.create('google', api_key='xxx')
  ```

#### 2. Strategy Pattern（策略模式）
- **用途**：不同提供商的不同实现策略
- **实现**：`BaseProviderService` 基类
- **示例**：每个提供商实现自己的 `send_chat_message()`

#### 3. Adapter Pattern（适配器模式）
- **用途**：适配官方 SDK 和统一接口
- **实现**：`OfficialSDKAdapter`
- **示例**：Google GenAI SDK → 统一接口

#### 4. Repository Pattern（仓储模式）
- **用途**：数据访问抽象
- **实现**：SQLAlchemy ORM 模型
- **示例**：`ChatSession`, `ConfigProfile` 模型

### 前端模式

#### 1. Custom Hooks（自定义 Hooks）
- **用途**：复用业务逻辑
- **实现**：`useChat`, `useModels`, `useSettings`
- **示例**：
  ```typescript
  const { sendMessage, messages } = useChat();
  ```

#### 2. Strategy Pattern（策略模式）
- **用途**：不同模式的不同处理逻辑
- **实现**：`ExecutionStrategy`
- **示例**：`ChatHandler`, `ImageGenHandler`

#### 3. Factory Pattern（工厂模式）
- **用途**：创建 LLM 客户端实例
- **实现**：`LLMFactory`
- **示例**：
  ```typescript
  const client = LLMFactory.create('google', apiKey);
  ```

#### 4. Observer Pattern（观察者模式）
- **用途**：状态变化通知
- **实现**：React `useEffect`
- **示例**：监听 `messages` 变化自动滚动

---

## 性能优化策略

### 后端优化
1. **异步 I/O**：使用 `async/await` 和 `aiofiles`
2. **连接池**：SQLAlchemy 连接池、HTTP 连接池
3. **Worker Pool**：5 个并发 worker 处理上传
4. **缓存**：Redis 缓存频繁查询的数据
5. **分页**：大数据集使用分页返回

### 前端优化
1. **代码分割**：React.lazy 和动态 import
2. **缓存**：
   - IndexedDB 缓存对话历史
   - Memory Cache 缓存模型列表
3. **防抖和节流**：输入框、滚动事件
4. **虚拟滚动**：长列表渲染优化
5. **懒加载**：图像懒加载

### 网络优化
1. **流式传输**：聊天响应流式显示
2. **请求去重**：相同请求自动去重
3. **并发控制**：限制并发请求数量
4. **超时控制**：设置合理的超时时间

---

## 安全策略

### 认证和授权
- **JWT 令牌**：Bearer Token 认证
- **密钥加密**：Fernet 对称加密存储 API 密钥
- **密码哈希**：Bcrypt 慢速哈希
- **会话管理**：Token 过期和刷新机制

### 数据安全
- **HTTPS**：生产环境强制 HTTPS
- **CORS**：配置允许的来源
- **输入验证**：Pydantic 验证所有输入
- **SQL 注入防护**：使用 ORM 参数化查询
- **XSS 防护**：React 默认转义

### API 安全
- **速率限制**：防止滥用
- **API 密钥验证**：每次请求验证密钥有效性
- **错误信息**：不泄露敏感信息

---

## 第三方服务

### AI 提供商
- **Google Cloud** - Gemini API、Imagen API、Veo API
- **OpenAI** - GPT 系列模型
- **阿里云** - 通义千问、通义万相
- **Ollama** - 本地大模型

### 云存储
- **阿里云 OSS** - 对象存储
- **AWS S3** - 对象存储
- **Google Drive** - 文件存储
- **腾讯云 COS** - 对象存储
- **Lsky Pro** - 图床服务

### 监控和日志
- **Grafana Loki**（可选）- 日志聚合
- **Prometheus**（可选）- 指标监控

---

## 开发工具链

### IDE 推荐
- **VS Code** - 推荐插件：
  - Python (Microsoft)
  - Pylance (类型检查)
  - ESLint (代码检查)
  - Prettier (格式化)
  - Tailwind CSS IntelliSense
  - Kiro AI (AI 辅助开发)

### CLI 工具
- **npm** - 前端依赖管理
- **pip** - Python 依赖管理
- **git** - 版本控制
- **psql** - PostgreSQL 客户端
- **redis-cli** - Redis 客户端

### 浏览器工具
- **Chrome DevTools** - 调试工具
- **React DevTools** - React 组件调试
- **Redux DevTools** - 状态调试（如使用）

---

## 技术约束

### 浏览器支持
- **现代浏览器**：Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **不支持**：IE 11 及以下

### 移动端支持
- **当前状态**：桌面优先，移动端部分适配
- **计划**：Q3 2026 完整移动端支持

### 系统要求

#### 开发环境
- **操作系统**：Windows 10+, macOS 11+, Linux (Ubuntu 20.04+)
- **内存**：8GB RAM 最低，16GB 推荐
- **磁盘**：20GB 可用空间

#### 生产环境
- **CPU**：2 核心最低，4 核心推荐
- **内存**：4GB RAM 最低，8GB 推荐
- **磁盘**：50GB 可用空间（含数据库）
- **网络**：稳定的互联网连接（访问 AI API）

---

## 技术债务和改进计划

### 已知问题
1. **前端状态管理**：使用多个 Hooks，缺乏统一状态管理（考虑 Zustand/Jotai）
2. **错误处理**：部分错误处理不统一，需要标准化
3. **测试覆盖率**：前端测试覆盖率较低（< 50%）
4. **移动端适配**：响应式设计不完整

### 改进计划
1. **Q2 2026**：引入统一状态管理库
2. **Q2 2026**：提升前端测试覆盖率到 70%+
3. **Q3 2026**：完整移动端适配
4. **Q3 2026**：实现完整的错误追踪系统

---

## 技术选型原则

### 1. 成熟稳定优先
- 选择经过验证的主流技术栈
- 避免使用实验性或过于新的技术

### 2. 社区活跃
- 优先选择有活跃社区支持的库
- 确保有充足的文档和示例

### 3. 类型安全
- 后端使用 Python 类型注解
- 前端使用 TypeScript strict 模式
- 利用类型系统减少运行时错误

### 4. 性能优先
- 选择性能更好的库（如 Vite 代替 Webpack）
- 优化构建速度和运行时性能

### 5. 可维护性
- 代码结构清晰
- 遵循设计模式
- 充分的测试覆盖

---

**更新日期**：2026-01-09
**版本**：v1.0.0
**维护者**：技术团队
