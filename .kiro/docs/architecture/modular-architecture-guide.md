---
inclusion: manual
---

# 模块化架构原则 🎯

> **核心原则**：每个服务功能必须单独文件存放，然后由主文件协调。每个UI功能必须单独组件文件，然后由协调组件组装。

---

## 为什么需要模块化？

### 问题：单一大文件的弊端

**后端单一大文件示例**（❌ 不推荐）：
```python
# backend/app/services/google_service.py（2000+ 行）
class GoogleService:
    def __init__(self):
        # 初始化代码 100+ 行
        ...

    def send_chat_message(self):
        # 聊天逻辑 200+ 行
        ...

    def stream_chat_message(self):
        # 流式聊天 150+ 行
        ...

    def generate_image(self):
        # 图像生成 300+ 行
        ...

    def generate_video(self):
        # 视频生成 250+ 行
        ...

    def upload_file(self):
        # 文件上传 100+ 行
        ...

    def manage_models(self):
        # 模型管理 200+ 行
        ...
    # ... 还有更多功能
```

**导致的问题**：
- 😖 修改聊天功能时，可能不小心影响图像生成
- 🤯 文件太大，难以查找和理解
- 🐛 测试困难，无法单独测试某个功能
- 👥 团队协作冲突（多人修改同一文件）
- 🔄 代码复用困难
- 📝 维护成本高

---

## 解决方案：模块化架构

### 1. 服务层模块化

**✅ 推荐的模块化结构**：

```
backend/app/services/
└── gemini/
    ├── google_service.py      # 主协调器（100 行）
    ├── chat_handler.py        # 聊天模块（200 行）
    ├── image_generator.py     # 图像生成模块（250 行）
    ├── video_generator.py     # 视频生成模块（200 行）
    ├── model_manager.py       # 模型管理模块（150 行）
    └── file_handler.py        # 文件处理模块（100 行）
```

**主协调器示例**：
```python
# backend/app/services/gemini/google_service.py
from ..base_provider import BaseProviderService
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .model_manager import ModelManager

class GoogleService(BaseProviderService):
    """Google Gemini 服务主协调器

    职责：组装和协调各个功能模块
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)

        # 组装功能模块
        self.chat_handler = ChatHandler(api_key)
        self.image_generator = ImageGenerator(api_key)
        self.model_manager = ModelManager(api_key)

    def send_chat_message(self, messages, model, **kwargs):
        """协调聊天功能"""
        return self.chat_handler.send_message(messages, model, **kwargs)

    def generate_image(self, prompt, **kwargs):
        """协调图像生成功能"""
        return self.image_generator.generate(prompt, **kwargs)

    def get_available_models(self):
        """协调模型管理功能"""
        return self.model_manager.list_models()
```

**功能模块示例**：
```python
# backend/app/services/gemini/chat_handler.py
class ChatHandler:
    """聊天功能处理器

    职责：专注于聊天相关的所有逻辑
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = self._init_client()

    def send_message(self, messages, model, **kwargs):
        """发送聊天消息"""
        # 聊天逻辑实现
        ...

    def stream_message(self, messages, model, **kwargs):
        """流式聊天"""
        # 流式逻辑实现
        ...

    def _init_client(self):
        """初始化客户端（私有方法）"""
        ...
```

---

### 2. UI层模块化

**✅ 推荐的组件化结构**：

```
frontend/components/
└── chat/
    ├── ChatView.tsx           # 协调组件（80 行）
    ├── MessageList.tsx        # 消息列表（100 行）
    ├── MessageItem.tsx        # 消息项（80 行）
    ├── InputArea.tsx          # 输入区域（120 行）
    └── ChatSidebar.tsx        # 侧边栏（100 行）
```

**协调组件示例**：
```typescript
// frontend/components/chat/ChatView.tsx
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { ChatSidebar } from './ChatSidebar';
import { useChat } from '@hooks/useChat';

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

**功能组件示例**：
```typescript
// frontend/components/chat/MessageList.tsx
interface MessageListProps {
  messages: Message[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  return (
    <div className="message-list">
      {messages.map(msg => (
        <MessageItem key={msg.id} message={msg} />
      ))}
    </div>
  );
};
```

---

## 实施规范

### 后端服务模块化检查清单

创建新服务时，确保：

- [ ] **目录结构**：每个提供商有独立目录
  ```
  services/my-provider/
    ├── my_provider_service.py  # 主协调器
    ├── chat_handler.py         # 功能模块
    └── ...
  ```

- [ ] **主协调器职责**：
  - ✅ 初始化和组装功能模块
  - ✅ 实现 `BaseProviderService` 接口
  - ✅ 协调方法调用（委托给功能模块）
  - ❌ 不包含具体业务逻辑

- [ ] **功能模块职责**：
  - ✅ 专注于单一功能（聊天、图像生成等）
  - ✅ 完整实现该功能的所有逻辑
  - ✅ 可以独立测试
  - ❌ 不直接调用其他功能模块

- [ ] **文件大小**：
  - 主协调器：< 200 行（理想）
  - 功能模块：< 300 行（理想）

- [ ] **测试覆盖**：
  - 每个功能模块有对应测试文件
  - 测试文件与源文件在同一目录或 `tests/` 目录

### 前端组件模块化检查清单

创建新视图时，确保：

- [ ] **目录结构**：每个视图有独立目录
  ```
  components/my-feature/
    ├── MyFeatureView.tsx       # 协调组件
    ├── ComponentA.tsx          # 子组件
    └── ComponentB.tsx          # 子组件
  ```

- [ ] **协调组件职责**：
  - ✅ 管理状态（通过 Hooks）
  - ✅ 组装和布局子组件
  - ✅ 处理数据流和事件
  - ❌ 不包含复杂的UI渲染逻辑

- [ ] **功能组件职责**：
  - ✅ 专注于单一UI功能
  - ✅ 通过 Props 接收数据
  - ✅ 可以独立复用和测试
  - ❌ 不直接管理全局状态

- [ ] **文件大小**：
  - 协调组件：< 150 行（理想）
  - 功能组件：< 200 行（理想）

- [ ] **Props 设计**：
  - 类型定义清晰
  - 接口简洁（< 10 个 props）
  - 避免传递整个对象（按需传递）

---

## 重构指南

### 何时重构？

如果文件出现以下情况，应考虑重构：

- 📏 **文件过大**：> 500 行
- 🔄 **职责过多**：包含 3+ 个不同功能
- 🐛 **测试困难**：无法单独测试某个功能
- 👥 **冲突频繁**：团队成员经常修改同一文件
- 📝 **难以理解**：新成员需要很长时间才能理解

### 重构步骤

#### 后端服务重构

1. **识别功能边界**
   ```python
   # 原文件：google_service.py（2000行）
   # 功能识别：
   # - 聊天（300行）
   # - 图像生成（400行）
   # - 视频生成（300行）
   # - 模型管理（200行）
   # - 文件处理（150行）
   ```

2. **创建功能模块文件**
   ```bash
   mkdir backend/app/services/gemini
   touch backend/app/services/gemini/chat_handler.py
   touch backend/app/services/gemini/image_generator.py
   touch backend/app/services/gemini/video_generator.py
   ```

3. **提取功能到模块**
   ```python
   # 从 google_service.py 移动到 chat_handler.py
   class ChatHandler:
       # 聊天相关的所有代码
       ...
   ```

4. **创建主协调器**
   ```python
   # google_service.py 变为协调器
   class GoogleService(BaseProviderService):
       def __init__(self, api_key):
           self.chat = ChatHandler(api_key)
           self.image = ImageGenerator(api_key)
   ```

5. **更新测试**
   ```bash
   # 创建模块测试
   touch backend/tests/test_chat_handler.py
   touch backend/tests/test_image_generator.py
   ```

#### 前端组件重构

1. **识别组件边界**
   ```typescript
   // 原组件：ChatView.tsx（1000行）
   // 功能识别：
   // - 消息列表（200行）
   // - 输入区域（300行）
   // - 侧边栏（200行）
   // - 设置面板（150行）
   ```

2. **创建子组件文件**
   ```bash
   mkdir frontend/components/chat
   touch frontend/components/chat/MessageList.tsx
   touch frontend/components/chat/InputArea.tsx
   touch frontend/components/chat/ChatSidebar.tsx
   ```

3. **提取功能到子组件**
   ```typescript
   // MessageList.tsx
   export const MessageList = ({ messages }) => {
       // 消息列表相关的所有代码
       ...
   };
   ```

4. **重写协调组件**
   ```typescript
   // ChatView.tsx 变为协调组件
   export const ChatView = () => {
       return (
           <>
               <MessageList messages={messages} />
               <InputArea onSend={sendMessage} />
               <ChatSidebar sessions={sessions} />
           </>
       );
   };
   ```

---

## 常见问题

### Q1: 如何确定模块边界？

**A**: 遵循以下原则：
- ✅ 功能内聚：相关功能放在一起
- ✅ 独立性：模块之间低耦合
- ✅ 可测试：能够独立测试
- ✅ 可复用：模块可以在其他地方复用

### Q2: 模块之间如何通信？

**A**:
- **后端**：通过主协调器传递数据，模块不直接调用其他模块
- **前端**：通过 Props 传递数据和回调函数

### Q3: 文件太小会不会影响性能？

**A**: 不会。现代打包工具（Vite、Webpack）会自动优化。模块化带来的可维护性收益远大于文件数量增加的影响。

### Q4: 已有大文件如何重构？

**A**:
1. 不要一次性重构所有功能
2. 每次重构一个功能模块
3. 确保测试通过后再继续
4. 逐步迁移，降低风险

### Q5: 如何避免过度拆分？

**A**:
- 单个文件 < 500 行才考虑拆分
- 功能确实独立才拆分
- 避免为了拆分而拆分

---

## 收益总结

### 开发效率提升

| 指标 | 单一大文件 | 模块化架构 | 提升 |
|------|-----------|-----------|------|
| 查找代码 | 5-10 分钟 | < 1 分钟 | 5-10x |
| 修改功能 | 30 分钟 | 10 分钟 | 3x |
| 测试时间 | 难以单独测试 | 快速单元测试 | 5x |
| 团队冲突 | 频繁 | 罕见 | 10x |
| 代码复用 | 困难 | 容易 | - |

### 质量提升

- ✅ **可维护性**：代码清晰，易于理解
- ✅ **可测试性**：单元测试覆盖率提高
- ✅ **可扩展性**：添加新功能无需修改现有代码
- ✅ **健壮性**：模块隔离，减少相互影响

---

## 强制执行

### Code Review 检查

提交 PR 时，Reviewer 必须检查：

- [ ] 新增服务是否遵循模块化原则？
- [ ] 新增组件是否遵循模块化原则？
- [ ] 文件是否过大（> 500 行）？
- [ ] 是否有单元测试？

### 自动化检查

使用 Claude Hooks 自动检查：

```json
{
  "hooks": {
    "before_commit": [
      {
        "name": "check_file_size",
        "description": "检查文件大小",
        "command": "python scripts/check_file_size.py",
        "enabled": true
      }
    ]
  }
}
```

---

**更新日期**：2026-01-09
**版本**：v1.0.0
**状态**：强制执行 ✅
