---
inclusion: manual
---

# 项目结构

## 项目概览

```
gemini-main/
├── backend/                    # 后端 FastAPI 应用
├── frontend/                   # 前端 React 应用
├── .claude/                    # Claude Code 配置
├── .kiro/                      # Kiro AI 配置和文档
├── docs/                       # 项目文档
├── package.json                # 前端依赖配置
├── vite.config.ts              # Vite 构建配置
├── tailwind.config.cjs         # Tailwind CSS 配置
└── tsconfig.json               # TypeScript 配置
```

---

## 后端结构

### 目录树

```
backend/
├── app/                        # 应用主目录
│   ├── core/                   # 核心模块
│   │   ├── config.py           # 应用配置
│   │   ├── database.py         # 数据库连接
│   │   ├── password.py         # 密码处理
│   │   ├── encryption.py       # 加密工具
│   │   ├── user_context.py     # 用户上下文
│   │   └── user_scoped_query.py# 用户作用域查询
│   │
│   ├── models/                 # 数据模型
│   │   └── db_models.py        # SQLAlchemy 模型定义
│   │
│   ├── routers/                # API 路由
│   │   ├── __init__.py         # 路由注册
│   │   ├── auth.py             # 认证相关 API
│   │   ├── chat.py             # 通用聊天 API
│   │   ├── google_chat.py      # Google 聊天 API
│   │   ├── models.py           # 模型列表 API
│   │   ├── providers.py        # 提供商配置 API
│   │   ├── generate.py         # 图像/视频/音频生成 API
│   │   ├── imagen_config.py    # Imagen 配置 API
│   │   ├── sessions.py         # 会话管理 API
│   │   ├── personas.py         # Persona 管理 API
│   │   ├── profiles.py         # 配置档案 API
│   │   ├── storage.py          # 云存储 API
│   │   ├── tongyi_models.py    # 通义模型 API
│   │   └── init.py             # 初始化数据 API
│   │
│   ├── services/               # 业务逻辑服务
│   │   ├── base_provider.py    # 提供商基类
│   │   ├── provider_factory.py # 提供商工厂
│   │   ├── provider_config.py  # 提供商配置中心
│   │   ├── api_key_service.py  # API 密钥服务
│   │   ├── auth_service.py     # 认证服务
│   │   ├── model_capabilities.py # 模型能力查询
│   │   ├── init_service.py     # 初始化服务
│   │   ├── openai_service.py   # OpenAI 服务
│   │   ├── qwen_native.py      # 通义千问服务
│   │   ├── upload_worker_pool.py # 上传队列
│   │   │
│   │   ├── gemini/             # Google Gemini 服务集合
│   │   │   ├── google_service.py    # 主协调器
│   │   │   ├── sdk_initializer.py   # SDK 初始化
│   │   │   ├── chat_handler.py      # 聊天处理
│   │   │   ├── image_generator.py   # 图像生成
│   │   │   ├── model_manager.py     # 模型管理
│   │   │   ├── file_handler.py      # 文件处理
│   │   │   ├── function_handler.py  # 函数调用
│   │   │   ├── imagen_coordinator.py# Imagen 协调器
│   │   │   └── official/            # 官方 SDK 适配
│   │   │
│   │   ├── storage/            # 云存储服务
│   │   │   ├── base.py         # 存储基类
│   │   │   ├── s3_provider.py  # AWS S3
│   │   │   ├── aliyun_provider.py # 阿里云 OSS
│   │   │   ├── google_provider.py # Google Drive
│   │   │   ├── tencent_provider.py# 腾讯云 COS
│   │   │   ├── lsky_provider.py# Lsky 图床
│   │   │   └── local_provider.py # 本地存储
│   │   │
│   │   └── ollama/             # Ollama 服务
│   │       └── ollama.py       # Ollama API 客户端
│   │
│   ├── utils/                  # 工具函数
│   │   └── message_utils.py    # 消息处理工具
│   │
│   └── main.py                 # 应用入口
│
├── scripts/                    # 辅助脚本
│   ├── insert_user.py          # 插入用户
│   ├── generate_user_token.py  # 生成用户令牌
│   └── sync_genai_sdk.py       # 同步 GenAI SDK
│
├── tests/                      # 测试文件
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   └── conftest.py             # pytest 配置
│
├── migrations/                 # 数据库迁移
│   └── alembic/                # Alembic 迁移文件
│
├── requirements.txt            # 生产依赖
├── requirements-dev.txt        # 开发依赖
└── pytest.ini                  # pytest 配置
```

### 文件命名规范

#### Python 文件
- **模块名**：小写 + 下划线（`snake_case`）
  - ✅ `chat_handler.py`
  - ✅ `image_generator.py`
  - ❌ `ChatHandler.py`
  - ❌ `imageGenerator.py`

- **类名**：大驼峰（`PascalCase`）
  - ✅ `ChatHandler`
  - ✅ `ImageGenerator`
  - ❌ `chatHandler`

- **函数名**：小写 + 下划线（`snake_case`）
  - ✅ `send_message()`
  - ✅ `get_available_models()`
  - ❌ `sendMessage()`

- **常量名**：大写 + 下划线（`UPPER_SNAKE_CASE`）
  - ✅ `MAX_FILE_SIZE`
  - ✅ `DEFAULT_MODEL`
  - ❌ `maxFileSize`

#### 测试文件
- **单元测试**：`test_<module_name>.py`
  - ✅ `test_chat_handler.py`
  - ✅ `test_provider_factory.py`

- **集成测试**：`test_<feature>_integration.py`
  - ✅ `test_google_integration.py`
  - ✅ `test_image_gen_integration.py`

### 导入顺序

```python
# 1. 标准库
import os
import json
from typing import Optional, Dict, Any

# 2. 第三方库
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# 3. 本地模块（相对导入）
from ..core.config import settings
from ..models.db_models import ChatSession
from ..services.provider_factory import ProviderFactory
```

### 路由结构规范

```python
# backend/app/routers/chat.py
from fastapi import APIRouter, Depends
from ..core.user_context import require_user_id

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/")
async def send_message(
    request: ChatRequest,
    user_id: int = Depends(require_user_id)
):
    """发送聊天消息"""
    ...

@router.get("/history")
async def get_history(
    session_id: str,
    user_id: int = Depends(require_user_id)
):
    """获取聊天历史"""
    ...
```

---

## 前端结构

### 目录树

```
frontend/
├── components/                 # React 组件
│   ├── layout/                 # 布局组件
│   │   ├── AppLayout.tsx       # 主布局
│   │   ├── Header.tsx          # 头部
│   │   ├── Sidebar.tsx         # 侧边栏
│   │   └── WelcomeScreen.tsx   # 欢迎页
│   │
│   ├── auth/                   # 认证组件
│   │   ├── LoginPage.tsx       # 登录页
│   │   └── RegisterPage.tsx    # 注册页
│   │
│   ├── views/                  # 视图组件（按模式）
│   │   ├── ChatView.tsx        # 聊天视图
│   │   ├── ImageGenView.tsx    # 图像生成视图
│   │   ├── ImageEditView.tsx   # 图像编辑视图
│   │   ├── VideoGenView.tsx    # 视频生成视图
│   │   └── AudioGenView.tsx    # 音频生成视图
│   │
│   ├── chat/                   # 聊天 UI 组件
│   │   ├── MessageItem.tsx     # 消息项
│   │   ├── MarkdownRenderer.tsx# Markdown 渲染
│   │   ├── InputArea.tsx       # 输入区域
│   │   └── input/              # 输入子组件
│   │       ├── PromptInput.tsx
│   │       └── ModeSelector.tsx
│   │
│   ├── modals/                 # 弹窗组件
│   │   ├── SettingsModal.tsx   # 设置弹窗
│   │   └── settings/           # 设置子页面
│   │       ├── ProfilesTab.tsx # 配置档案
│   │       ├── ImagenTab.tsx   # Imagen 配置
│   │       └── StorageTab.tsx  # 云存储配置
│   │
│   ├── common/                 # 通用组件
│   │   ├── LoadingSpinner.tsx
│   │   ├── ErrorView.tsx
│   │   └── ImageCompare.tsx
│   │
│   └── controls/               # 控制面板
│       ├── modes/              # 按模式的控制
│       │   ├── ChatControls.tsx
│       │   ├── ImageGenControls.tsx
│       │   └── VideoGenControls.tsx
│       └── constants.ts        # 控制常数
│
├── hooks/                      # 自定义 Hooks
│   ├── useAuth.ts              # 认证
│   ├── useChat.ts              # 聊天
│   ├── useModels.ts            # 模型
│   ├── useSettings.ts          # 设置
│   ├── useSessions.ts          # 会话
│   ├── usePersonas.ts          # Persona
│   ├── useControlsState.ts     # 控制状态
│   ├── useInitData.ts          # 初始化数据
│   │
│   └── handlers/               # 处理器
│       ├── ChatHandlerClass.ts # 聊天策略
│       ├── ImageGenHandlerClass.ts # 图像生成策略
│       ├── BaseHandler.ts      # 策略基类
│       └── types.ts            # 类型定义
│
├── services/                   # 服务层
│   ├── apiClient.ts            # API 客户端
│   ├── auth.ts                 # 认证服务
│   ├── llmService.ts           # LLM 统一接口
│   ├── LLMFactory.ts           # LLM 工厂
│   ├── db.ts                   # IndexedDB
│   ├── configurationService.ts # 配置服务
│   │
│   ├── providers/              # 提供商客户端
│   │   ├── interfaces.ts       # 接口定义
│   │   ├── UnifiedProviderClient.ts # 统一客户端
│   │   ├── openai/
│   │   │   └── OpenAIProvider.ts
│   │   ├── google/
│   │   │   ├── fileService.ts
│   │   │   └── media/
│   │   │       ├── image-gen.ts
│   │   │       └── image-edit.ts
│   │   └── tongyi/
│   │       ├── api.ts
│   │       └── image-gen.ts
│   │
│   └── storage/                # 存储服务
│       ├── BlobStorageService.ts
│       └── storageUpload.ts
│
├── types/                      # 类型定义
│   ├── types.ts                # 核心类型
│   ├── storage.ts              # 存储类型
│   ├── ollama.ts               # Ollama 类型
│   └── imagen-config.ts        # Imagen 配置类型
│
├── utils/                      # 工具函数
│   └── cursorUtils.ts          # 光标工具
│
├── App.tsx                     # 应用根组件
├── main.tsx                    # 应用入口
└── index.html                  # HTML 模板
```

### 文件命名规范

#### TypeScript/React 文件
- **组件文件**：大驼峰（`PascalCase.tsx`）
  - ✅ `ChatView.tsx`
  - ✅ `MessageItem.tsx`
  - ❌ `chatView.tsx`

- **Hooks 文件**：小驼峰 + use 前缀（`useXxx.ts`）
  - ✅ `useChat.ts`
  - ✅ `useModels.ts`
  - ❌ `chat.ts`

- **服务文件**：小驼峰（`camelCase.ts`）
  - ✅ `apiClient.ts`
  - ✅ `llmService.ts`
  - ❌ `APIClient.ts`

- **类型文件**：小写（`types.ts`）
  - ✅ `types.ts`
  - ✅ `interfaces.ts`

- **工具文件**：小驼峰 + Utils 后缀（`xxxUtils.ts`）
  - ✅ `cursorUtils.ts`
  - ✅ `dateUtils.ts`

#### 测试文件
- **组件测试**：`<ComponentName>.test.tsx`
  - ✅ `ChatView.test.tsx`
  - ✅ `MessageItem.test.tsx`

- **Hook 测试**：`<hookName>.test.ts`
  - ✅ `useChat.test.ts`

- **服务测试**：`<serviceName>.test.ts`
  - ✅ `apiClient.test.ts`

### 组件结构规范

```typescript
// frontend/components/chat/MessageItem.tsx
import React, { useMemo } from 'react';
import { MessageItemProps } from './types';
import MarkdownRenderer from './MarkdownRenderer';

/**
 * 消息项组件
 *
 * 渲染单条聊天消息，支持 Markdown 格式化
 *
 * @param message - 消息对象
 * @param onEdit - 编辑回调
 */
export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onEdit
}) => {
  // 1. Hooks
  const isUser = useMemo(() => message.role === 'user', [message.role]);

  // 2. 事件处理
  const handleEdit = () => {
    onEdit(message.id);
  };

  // 3. 渲染
  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      <MarkdownRenderer content={message.content} />
      {isUser && (
        <button onClick={handleEdit}>编辑</button>
      )}
    </div>
  );
};

export default MessageItem;
```

### 导入顺序

```typescript
// 1. React 核心
import React, { useState, useEffect } from 'react';

// 2. 第三方库
import { useNavigate } from 'react-router-dom';
import { Send, Image, File } from 'lucide-react';

// 3. 本地组件
import MessageItem from './MessageItem';
import InputArea from './InputArea';

// 4. Hooks
import { useChat } from '../../hooks/useChat';
import { useModels } from '../../hooks/useModels';

// 5. 服务
import { apiClient } from '../../services/apiClient';

// 6. 类型
import type { Message, AppMode } from '../../types/types';

// 7. 样式
import './ChatView.css';
```

### 自定义 Hook 规范

```typescript
// frontend/hooks/useChat.ts
import { useState, useCallback } from 'react';
import { apiClient } from '../services/apiClient';
import type { Message } from '../types/types';

interface UseChatResult {
  messages: Message[];
  loading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
}

/**
 * 聊天 Hook
 *
 * 管理聊天状态和消息发送
 *
 * @param sessionId - 会话 ID
 * @returns 聊天状态和方法
 */
export const useChat = (sessionId: string): UseChatResult => {
  // 1. 状态定义
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 2. 方法定义
  const sendMessage = useCallback(async (content: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post('/api/chat', {
        session_id: sessionId,
        message: content
      });

      setMessages(prev => [...prev, response.data]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  // 3. 返回值
  return {
    messages,
    loading,
    error,
    sendMessage,
    clearMessages
  };
};
```

---

## 架构原则

### 1. 模块化组织原则（Modular Organization）⭐ **核心原则**

#### 服务层模块化
每个服务功能必须**单独文件存放**，然后由**主文件协调**：

**❌ 错误示例**（所有功能在一个文件）：
```python
# backend/app/services/google_service.py（不推荐）
class GoogleService:
    def chat(self): ...
    def generate_image(self): ...
    def generate_video(self): ...
    def upload_file(self): ...
    def manage_models(self): ...
    # ... 500+ 行代码
```

**✅ 正确示例**（功能分离，主文件协调）：
```python
# backend/app/services/gemini/chat_handler.py
class ChatHandler:
    """聊天功能处理器"""
    def send_message(self): ...
    def stream_message(self): ...

# backend/app/services/gemini/image_generator.py
class ImageGenerator:
    """图像生成处理器"""
    def generate(self): ...
    def edit(self): ...

# backend/app/services/gemini/model_manager.py
class ModelManager:
    """模型管理器"""
    def list_models(self): ...
    def get_model_info(self): ...

# backend/app/services/gemini/google_service.py（主协调器）
class GoogleService(BaseProviderService):
    """Google Gemini 服务主协调器"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        # 组装各个功能模块
        self.chat_handler = ChatHandler(api_key)
        self.image_generator = ImageGenerator(api_key)
        self.model_manager = ModelManager(api_key)

    def send_chat_message(self, messages, model, **kwargs):
        """协调聊天功能"""
        return self.chat_handler.send_message(messages, model, **kwargs)

    def generate_image(self, prompt, **kwargs):
        """协调图像生成功能"""
        return self.image_generator.generate(prompt, **kwargs)
```

**优势**：
- ✅ 修改聊天功能不影响图像生成
- ✅ 每个文件职责单一，易于理解
- ✅ 便于单独测试每个功能模块
- ✅ 团队成员可以并行开发不同模块

#### UI层模块化
每个UI功能必须**单独组件文件**，然后由**协调组件组装**：

**❌ 错误示例**（单一大组件）：
```typescript
// frontend/components/ChatView.tsx（不推荐）
export const ChatView = () => {
  // 消息列表渲染
  const renderMessages = () => { ... }

  // 输入区域渲染
  const renderInput = () => { ... }

  // 侧边栏渲染
  const renderSidebar = () => { ... }

  // 设置面板渲染
  const renderSettings = () => { ... }

  return (
    <div>
      {renderMessages()}
      {renderInput()}
      {renderSidebar()}
      {renderSettings()}
    </div>
  );
  // ... 1000+ 行代码
};
```

**✅ 正确示例**（组件分离，协调组装）：
```typescript
// frontend/components/chat/MessageList.tsx
export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  return (
    <div className="message-list">
      {messages.map(msg => (
        <MessageItem key={msg.id} message={msg} />
      ))}
    </div>
  );
};

// frontend/components/chat/InputArea.tsx
export const InputArea: React.FC<InputAreaProps> = ({ onSend }) => {
  return (
    <div className="input-area">
      <PromptInput onSubmit={onSend} />
      <AttachmentButton />
    </div>
  );
};

// frontend/components/chat/ChatSidebar.tsx
export const ChatSidebar: React.FC<SidebarProps> = ({ sessions }) => {
  return (
    <div className="sidebar">
      <SessionList sessions={sessions} />
    </div>
  );
};

// frontend/components/chat/ChatView.tsx（协调组件）
export const ChatView: React.FC = () => {
  const { messages, sendMessage } = useChat();
  const { sessions } = useSessions();

  return (
    <div className="chat-view">
      <ChatSidebar sessions={sessions} />
      <div className="main">
        <MessageList messages={messages} />
        <InputArea onSend={sendMessage} />
      </div>
    </div>
  );
};
```

**优势**：
- ✅ 修改输入框样式不影响消息列表
- ✅ 每个组件可以独立开发和测试
- ✅ 便于复用（InputArea 可用于多个视图）
- ✅ 降低组件复杂度，提高可维护性

#### 目录组织规范

**后端服务目录**：
```
backend/app/services/
├── base_provider.py           # 提供商基类
├── provider_factory.py        # 工厂（协调器）
│
├── gemini/                    # Google Gemini 服务
│   ├── google_service.py      # 主协调器（组装各模块）
│   ├── chat_handler.py        # 聊天处理模块
│   ├── image_generator.py     # 图像生成模块
│   ├── video_generator.py     # 视频生成模块
│   ├── model_manager.py       # 模型管理模块
│   ├── file_handler.py        # 文件处理模块
│   └── function_handler.py    # 函数调用模块
│
├── openai/                    # OpenAI 服务
│   ├── openai_service.py      # 主协调器
│   ├── chat_client.py         # 聊天客户端
│   └── image_client.py        # 图像客户端
│
└── storage/                   # 云存储服务
    ├── storage_service.py     # 主协调器
    ├── s3_provider.py         # S3 提供商
    ├── oss_provider.py        # OSS 提供商
    └── base.py                # 存储基类
```

**前端组件目录**：
```
frontend/components/
├── chat/                      # 聊天模块
│   ├── ChatView.tsx           # 协调组件（组装子组件）
│   ├── MessageList.tsx        # 消息列表子组件
│   ├── MessageItem.tsx        # 消息项子组件
│   ├── InputArea.tsx          # 输入区域子组件
│   ├── ChatSidebar.tsx        # 侧边栏子组件
│   └── input/                 # 输入子模块
│       ├── PromptInput.tsx
│       ├── AttachmentButton.tsx
│       └── ModeSelector.tsx
│
├── views/                     # 视图模块
│   ├── ImageGenView.tsx       # 协调组件
│   ├── image-gen/             # 图像生成子模块
│   │   ├── PromptPanel.tsx
│   │   ├── ParameterPanel.tsx
│   │   └── ResultGallery.tsx
│   │
│   └── VideoGenView.tsx       # 协调组件
│       └── video-gen/         # 视频生成子模块
│           ├── PromptPanel.tsx
│           └── PreviewPlayer.tsx
│
└── modals/                    # 弹窗模块
    ├── SettingsModal.tsx      # 协调组件
    └── settings/              # 设置子模块
        ├── ProfilesTab.tsx
        ├── ImagenTab.tsx
        └── StorageTab.tsx
```

#### 实施检查清单

创建新功能时，确保：

**后端服务**：
- [ ] 每个功能模块有独立文件（如 `chat_handler.py`）
- [ ] 主协调器文件负责组装（如 `google_service.py`）
- [ ] 单个文件不超过 300 行（理想）
- [ ] 模块之间通过接口通信
- [ ] 每个模块有对应的测试文件

**前端组件**：
- [ ] 每个子功能有独立组件文件
- [ ] 协调组件负责组装和状态管理
- [ ] 单个组件文件不超过 200 行（理想）
- [ ] 子组件通过 Props 接收数据
- [ ] 每个组件有对应的测试文件

---

### 2. 关注点分离（Separation of Concerns）

#### 后端
- **路由层**（routers/）：仅处理 HTTP 请求/响应
- **服务层**（services/）：业务逻辑实现
- **数据层**（models/）：数据模型定义
- **核心层**（core/）：通用功能（配置、认证）

#### 前端
- **组件层**（components/）：UI 渲染
- **Hooks 层**（hooks/）：状态管理和业务逻辑
- **服务层**（services/）：API 调用和数据处理
- **类型层**（types/）：类型定义

### 3. 单一职责原则（Single Responsibility Principle）

每个文件/类/函数只负责一个功能：

✅ **好的示例**：
```typescript
// useAuth.ts - 仅处理认证
export const useAuth = () => {
  const login = async (username, password) => { ... };
  const logout = () => { ... };
  return { login, logout };
};

// useModels.ts - 仅处理模型
export const useModels = () => {
  const fetchModels = async () => { ... };
  const filterModels = (mode) => { ... };
  return { models, fetchModels, filterModels };
};
```

❌ **不好的示例**：
```typescript
// useApp.ts - 混合多个职责
export const useApp = () => {
  const login = () => { ... };         // 认证
  const fetchModels = () => { ... };   // 模型
  const sendMessage = () => { ... };   // 聊天
  // ... 太多职责
};
```

### 4. 依赖注入（Dependency Injection）

#### 后端
使用 FastAPI 的依赖注入：

```python
from fastapi import Depends
from ..core.user_context import require_user_id

@router.post("/")
async def endpoint(
    user_id: int = Depends(require_user_id),  # 注入用户 ID
    db: AsyncSession = Depends(get_db)         # 注入数据库会话
):
    ...
```

#### 前端
通过参数传递依赖：

```typescript
interface ChatHandlerProps {
  apiClient: APIClient;  // 注入 API 客户端
  storage: Storage;      // 注入存储服务
}

class ChatHandler {
  constructor(private deps: ChatHandlerProps) {}

  async execute() {
    await this.deps.apiClient.post(...);
  }
}
```

### 5. 接口优于实现（Program to Interface）

定义接口，实现可替换：

```python
# backend/app/services/base_provider.py
class BaseProviderService(ABC):
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        pass

    @abstractmethod
    async def send_chat_message(self, messages: List[Dict]) -> Dict:
        pass

# 具体实现
class GoogleService(BaseProviderService):
    def get_available_models(self):
        return [...]

    async def send_chat_message(self, messages):
        return {...}
```

---

## 路径别名

### 后端
使用相对导入：

```python
from ..core.config import settings       # 上两级的 core
from ..models.db_models import User      # 上两级的 models
from .utils import helper_function       # 同级的 utils
```

### 前端
使用 TypeScript 路径别名（配置在 `tsconfig.json`）：

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["frontend/*"],
      "@components/*": ["frontend/components/*"],
      "@hooks/*": ["frontend/hooks/*"],
      "@services/*": ["frontend/services/*"],
      "@types/*": ["frontend/types/*"]
    }
  }
}
```

使用示例：

```typescript
import { useChat } from '@hooks/useChat';
import { apiClient } from '@services/apiClient';
import type { Message } from '@types/types';
```

---

## 代码组织最佳实践

### 1. 小文件原则
- 单个文件不超过 500 行（理想 < 300 行）
- 如果文件过大，拆分为多个模块
- 每个模块专注一个功能

### 2. 目录扁平化
- 避免过深的嵌套（建议 ≤ 3 层）
- 使用功能分组而非类型分组

✅ **好的结构**：
```
services/
  gemini/
    chat_handler.py
    image_generator.py
  openai/
    client.py
```

❌ **不好的结构**：
```
services/
  handlers/
    gemini/
      chat/
        handler.py  # 过深
```

### 3. 按功能组织
- 相关文件放在一起
- 例如：聊天相关组件放在 `components/chat/`

### 4. 测试文件位置
- 与源文件并列或在 `tests/` 目录
- 保持相同的目录结构

---

## 配置文件位置

### 后端
```
backend/
├── requirements.txt       # 生产依赖
├── requirements-dev.txt   # 开发依赖
├── pytest.ini            # pytest 配置
├── .ruff.toml            # Ruff 配置
└── alembic.ini           # Alembic 配置
```

### 前端
```
root/
├── package.json          # npm 依赖
├── vite.config.ts        # Vite 配置
├── tsconfig.json         # TypeScript 配置
├── tailwind.config.cjs   # Tailwind 配置
├── .prettierrc           # Prettier 配置
└── .eslintrc             # ESLint 配置
```

---

## 特殊目录

### `.claude/` - Claude Code 配置
```
.claude/
├── hooks.json            # Hooks 配置
├── HOOKS_GUIDE.md        # Hooks 指南
└── scripts/              # 辅助脚本
```

### `.kiro/` - Kiro AI 配置
```
.kiro/
├── steering/             # Steering 规则
│   ├── product.md        # 产品概述
│   ├── tech.md           # 技术栈
│   └── structure.md      # 项目结构
├── settings/             # 设置
│   └── mcp.json          # MCP 配置
└── specs/                # 规格文档
```

---

**更新日期**：2026-01-09
**版本**：v1.0.0
**维护者**：技术团队
