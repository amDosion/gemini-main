---
inclusion: manual
---

# 代码重构指南

## 核心原则

### 1. 模块化重构（第一原则）⭐

**将大文件拆分为小模块，每个模块单一职责**

#### 重构目标

| 层级 | 重构前 | 重构后 |
|------|--------|--------|
| 后端文件 | 500-2000 行 | 150-250 行/模块 |
| 前端组件 | 300-800 行 | 100-150 行/组件 |
| 服务类 | 单一大类 | 主协调器 + 功能模块 |

---

## 重构流程

### 第一步：识别功能边界

```python
# 重构前：google_service.py（2000+ 行）
class GoogleService:
    def __init__(self):
        # 初始化代码 100+ 行
        ...

    def send_chat_message(self):
        # 聊天逻辑 200+ 行
        ...

    def generate_image(self):
        # 图像生成 300+ 行
        ...

    def generate_video(self):
        # 视频生成 250+ 行
        ...

    def upload_file(self):
        # 文件上传 150+ 行
        ...

    def list_models(self):
        # 模型列表 100+ 行
        ...
```

**识别功能边界**：
1. 聊天功能 → `chat_handler.py`
2. 图像生成 → `image_generator.py`
3. 视频生成 → `video_generator.py`
4. 文件处理 → `file_handler.py`
5. 模型管理 → `model_manager.py`
6. 主协调器 → `google_service.py`

---

### 第二步：创建模块文件

```python
# chat_handler.py（200 行）
from google import genai
from typing import List, Dict, Any

class ChatHandler:
    """聊天功能模块"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    async def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天消息"""
        # 实现聊天逻辑
        ...

    async def send_message_stream(self, messages, model, **kwargs):
        """发送聊天消息（流式）"""
        # 实现流式聊天
        ...
```

```python
# image_generator.py（250 行）
from google import genai
from typing import Dict, Any, Optional

class ImageGenerator:
    """图像生成模块"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    async def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成图像"""
        # 实现图像生成逻辑
        ...

    async def edit(self, reference_image: bytes, prompt: str, **kwargs):
        """编辑图像"""
        # 实现图像编辑逻辑
        ...
```

---

### 第三步：提取主协调器

```python
# google_service.py（100 行）
from ..base_provider import BaseProviderService
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .video_generator import VideoGenerator
from .file_handler import FileHandler
from .model_manager import ModelManager

class GoogleService(BaseProviderService):
    """Google Gemini 服务主协调器
    
    职责：
    1. 组装各个功能模块
    2. 提供统一的服务接口
    3. 协调模块间的交互
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)
        
        # 初始化功能模块
        self.chat_handler = ChatHandler(api_key)
        self.image_generator = ImageGenerator(api_key)
        self.video_generator = VideoGenerator(api_key)
        self.file_handler = FileHandler(api_key)
        self.model_manager = ModelManager(api_key)

    # 聊天功能
    async def send_chat_message(self, messages, model, **kwargs):
        """发送聊天消息"""
        return await self.chat_handler.send_message(messages, model, **kwargs)

    async def send_chat_message_stream(self, messages, model, **kwargs):
        """发送聊天消息（流式）"""
        async for chunk in self.chat_handler.send_message_stream(messages, model, **kwargs):
            yield chunk

    # 图像功能
    async def generate_image(self, prompt, **kwargs):
        """生成图像"""
        return await self.image_generator.generate(prompt, **kwargs)

    async def edit_image(self, reference_image, prompt, **kwargs):
        """编辑图像"""
        return await self.image_generator.edit(reference_image, prompt, **kwargs)

    # 视频功能
    async def generate_video(self, prompt, **kwargs):
        """生成视频"""
        return await self.video_generator.generate(prompt, **kwargs)

    # 文件功能
    async def upload_file(self, file_data, **kwargs):
        """上传文件"""
        return await self.file_handler.upload(file_data, **kwargs)

    # 模型管理
    def get_available_models(self):
        """获取可用模型列表"""
        return self.model_manager.list_models()
```

---

### 第四步：更新测试

```python
# 重构前：test_google_service.py（1000+ 行）
# 所有功能的测试都在一个文件中

# 重构后：拆分为多个测试文件
# test_chat_handler.py（200 行）
# test_image_generator.py（250 行）
# test_video_generator.py（200 行）
# test_file_handler.py（150 行）
# test_model_manager.py（100 行）
# test_google_service.py（100 行）- 只测试协调逻辑
```

```python
# test_chat_handler.py
import pytest
from app.services.gemini.chat_handler import ChatHandler

@pytest.fixture
def chat_handler():
    return ChatHandler(api_key="test_key")

@pytest.mark.asyncio
async def test_send_message(chat_handler):
    """测试发送消息"""
    # 测试聊天功能
    ...

@pytest.mark.asyncio
async def test_send_message_stream(chat_handler):
    """测试流式消息"""
    # 测试流式聊天
    ...
```

```python
# test_google_service.py
import pytest
from app.services.gemini.google_service import GoogleService

@pytest.fixture
def google_service():
    return GoogleService(api_key="test_key")

@pytest.mark.asyncio
async def test_service_initialization(google_service):
    """测试服务初始化"""
    # 验证所有模块都已初始化
    assert google_service.chat_handler is not None
    assert google_service.image_generator is not None
    assert google_service.video_generator is not None

@pytest.mark.asyncio
async def test_service_coordination(google_service):
    """测试服务协调"""
    # 测试主协调器的协调逻辑
    ...
```

---

## 前端重构

### React 组件重构

#### 重构前

```tsx
// ChatView.tsx（800 行）
export const ChatView: React.FC = () => {
  // 状态管理 50+ 行
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  // ... 更多状态

  // 消息处理逻辑 100+ 行
  const handleSendMessage = async () => {
    // 发送消息逻辑
    ...
  };

  // 文件上传逻辑 80+ 行
  const handleFileUpload = async (file: File) => {
    // 文件上传逻辑
    ...
  };

  // 图像生成逻辑 100+ 行
  const handleImageGeneration = async (prompt: string) => {
    // 图像生成逻辑
    ...
  };

  // 渲染逻辑 400+ 行
  return (
    <div>
      {/* 消息列表 */}
      <div>
        {messages.map(msg => (
          <div key={msg.id}>
            {/* 复杂的消息渲染逻辑 */}
          </div>
        ))}
      </div>

      {/* 输入区域 */}
      <div>
        {/* 复杂的输入区域 */}
      </div>

      {/* 工具栏 */}
      <div>
        {/* 复杂的工具栏 */}
      </div>
    </div>
  );
};
```

#### 重构后

```tsx
// ChatView.tsx（150 行）- 主协调组件
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { Toolbar } from './Toolbar';
import { useChatLogic } from '../hooks/useChatLogic';
import { useFileUpload } from '../hooks/useFileUpload';
import { useImageGeneration } from '../hooks/useImageGeneration';

export const ChatView: React.FC = () => {
  // 使用自定义 Hooks 提取逻辑
  const { messages, sendMessage, isLoading } = useChatLogic();
  const { uploadFile, uploadProgress } = useFileUpload();
  const { generateImage, isGenerating } = useImageGeneration();

  return (
    <div className="chat-view">
      <MessageList messages={messages} />
      <InputArea
        onSendMessage={sendMessage}
        onUploadFile={uploadFile}
        onGenerateImage={generateImage}
        isLoading={isLoading || isGenerating}
      />
      <Toolbar uploadProgress={uploadProgress} />
    </div>
  );
};
```

```tsx
// MessageList.tsx（100 行）
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

```tsx
// InputArea.tsx（120 行）
interface InputAreaProps {
  onSendMessage: (text: string) => void;
  onUploadFile: (file: File) => void;
  onGenerateImage: (prompt: string) => void;
  isLoading: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({
  onSendMessage,
  onUploadFile,
  onGenerateImage,
  isLoading
}) => {
  const [input, setInput] = useState("");

  const handleSubmit = () => {
    if (input.trim()) {
      onSendMessage(input);
      setInput("");
    }
  };

  return (
    <div className="input-area">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={isLoading}
      />
      <button onClick={handleSubmit} disabled={isLoading}>
        发送
      </button>
    </div>
  );
};
```

```tsx
// hooks/useChatLogic.ts（150 行）
export const useChatLogic = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async (text: string) => {
    setIsLoading(true);
    try {
      // 发送消息逻辑
      const response = await chatAPI.sendMessage(text);
      setMessages(prev => [...prev, response]);
    } catch (error) {
      console.error("发送消息失败:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return { messages, sendMessage, isLoading };
};
```

---

## 重构检查清单

### 重构前

- [ ] 识别大文件（后端 > 500 行，前端 > 300 行）
- [ ] 分析功能边界和职责
- [ ] 规划模块拆分方案
- [ ] 确认依赖关系
- [ ] 备份原始代码

### 重构中

- [ ] 创建模块文件（每个功能单独文件）
- [ ] 提取主协调器（组装模块）
- [ ] 更新导入路径
- [ ] 保持接口一致性
- [ ] 逐步迁移功能（一次一个模块）
- [ ] 每次迁移后运行测试

### 重构后

- [ ] 运行所有测试（确保功能正常）
- [ ] 检查代码覆盖率（不应降低）
- [ ] 验证文件大小（符合目标）
- [ ] 更新文档（反映新结构）
- [ ] 代码审查（确认重构质量）
- [ ] 提交代码前检查 git diff

---

## 重构模式

### 后端服务重构模式

```
大服务类（2000+ 行）
    ↓
主协调器（100 行）+ 功能模块（150-250 行/模块）
```

### 前端组件重构模式

```
大组件（800+ 行）
    ↓
主组件（150 行）+ 子组件（100-150 行/组件）+ 自定义 Hooks（150 行/Hook）
```

### 测试重构模式

```
大测试文件（1000+ 行）
    ↓
模块测试文件（200 行/模块）+ 集成测试文件（100 行）
```

---

## 常见问题

### 问题 1：重构后测试失败

**原因**：导入路径错误或接口不一致

**解决方案**：
1. 检查所有导入路径
2. 确保接口签名一致
3. 逐步迁移，每次迁移后运行测试

### 问题 2：模块间循环依赖

**原因**：模块拆分不合理

**解决方案**：
1. 重新分析功能边界
2. 提取共享逻辑到独立模块
3. 使用依赖注入解耦

### 问题 3：重构后性能下降

**原因**：过度拆分或不必要的抽象

**解决方案**：
1. 性能分析（找出瓶颈）
2. 合并过小的模块
3. 优化模块间通信

---

## 重构示例

### 完整示例：后端服务重构

**重构前**：
- `google_service.py`（2000 行）

**重构后**：
- `google_service.py`（100 行）- 主协调器
- `chat_handler.py`（200 行）- 聊天模块
- `image_generator.py`（250 行）- 图像生成模块
- `video_generator.py`（200 行）- 视频生成模块
- `file_handler.py`（150 行）- 文件处理模块
- `model_manager.py`（100 行）- 模型管理模块

**效果**：
- 文件大小减少 80%（2000 → 150-250 行/模块）
- 测试覆盖率提升 15%（65% → 80%）
- 代码可维护性显著提升

### 完整示例：前端组件重构

**重构前**：
- `ChatView.tsx`（800 行）

**重构后**：
- `ChatView.tsx`（150 行）- 主组件
- `MessageList.tsx`（100 行）- 消息列表
- `MessageItem.tsx`（80 行）- 消息项
- `InputArea.tsx`（120 行）- 输入区域
- `Toolbar.tsx`（100 行）- 工具栏
- `useChatLogic.ts`（150 行）- 聊天逻辑 Hook
- `useFileUpload.ts`（100 行）- 文件上传 Hook
- `useImageGeneration.ts`（100 行）- 图像生成 Hook

**效果**：
- 组件大小减少 81%（800 → 80-150 行/组件）
- 逻辑复用性提升（自定义 Hooks）
- 组件可测试性显著提升
