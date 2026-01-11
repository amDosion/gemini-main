---
inclusion: manual
---

# Gemini 集成指南

## 核心原则

### 1. 文档优先原则（第一原则）⭐

**在开发任何 Gemini 功能前，必须先阅读官方参考文档**

#### 必读文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 模型使用指南 | `.kiro/specs/参考/python-genai-main/google-genai-models-usage.md` | 了解模型能力和使用方法 |
| Live API 指南 | `.kiro/specs/参考/python-genai-main/google-genai-live-api-usage.md` | 了解实时 API 使用方法 |
| SDK 原始代码 | `.kiro/specs/参考/python-genai-main/google/genai/` | 理解 SDK 实现细节 |

#### 阅读流程

```
1. 阅读模型使用指南
   └─ 了解模型能力、参数、限制
   
2. 查看 SDK 原始代码
   └─ 理解 API 调用方式、数据结构
   
3. 参考项目现有实现
   └─ 查看 backend/app/services/gemini/ 目录
   
4. 开始开发
   └─ 遵循模块化架构原则
```

---

## 架构遵循原则

### 基类继承

**所有 Gemini 服务必须继承 `BaseProviderService` 基类**

```python
# backend/app/services/base_provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator

class BaseProviderService(ABC):
    """提供商服务基类"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        pass

    @abstractmethod
    async def send_chat_message(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天消息"""
        pass

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """生成图像"""
        pass
```

### 模块化实现

```python
# backend/app/services/gemini/google_service.py
from ..base_provider import BaseProviderService
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .model_manager import ModelManager

class GoogleService(BaseProviderService):
    """Google Gemini 服务主协调器"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        
        # 初始化子模块
        self.chat_handler = ChatHandler(api_key)
        self.image_generator = ImageGenerator(api_key)
        self.model_manager = ModelManager(api_key)

    def get_available_models(self):
        """获取可用模型列表"""
        return self.model_manager.list_models()

    async def send_chat_message(self, messages, model, **kwargs):
        """发送聊天消息"""
        return await self.chat_handler.send_message(messages, model, **kwargs)

    async def generate_image(self, prompt, **kwargs):
        """生成图像"""
        return await self.image_generator.generate(prompt, **kwargs)
```

---

## SDK 初始化

### 基础初始化

```python
# backend/app/services/gemini/chat_handler.py
from google import genai
from google.genai import types

class ChatHandler:
    """Gemini 聊天处理器"""

    def __init__(self, api_key: str):
        """初始化聊天处理器
        
        Args:
            api_key: Google API 密钥
        """
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    async def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天消息
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 其他参数
            
        Returns:
            Dict: 响应结果
        """
        # 转换消息格式
        contents = [
            types.Content(
                role=msg["role"],
                parts=[types.Part(text=msg["content"])]
            )
            for msg in messages
        ]
        
        # 调用 API
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**kwargs)
        )
        
        return {
            "message": response.text,
            "role": "assistant",
            "model": model
        }
```

### 流式响应

```python
async def send_message_stream(
    self,
    messages: List[Dict[str, str]],
    model: str,
    **kwargs
) -> AsyncGenerator[str, None]:
    """发送聊天消息（流式）
    
    Args:
        messages: 消息列表
        model: 模型名称
        **kwargs: 其他参数
        
    Yields:
        str: 响应文本片段
    """
    contents = [
        types.Content(
            role=msg["role"],
            parts=[types.Part(text=msg["content"])]
        )
        for msg in messages
    ]
    
    # 流式调用
    async for chunk in self.client.aio.models.generate_content_stream(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(**kwargs)
    ):
        if chunk.text:
            yield chunk.text
```

---

## 图像生成

### Imagen 3 集成

```python
# backend/app/services/gemini/image_generator.py
from google import genai
from google.genai import types
import base64

class ImageGenerator:
    """Gemini 图像生成器"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        safety_filter_level: str = "block_some",
        person_generation: str = "allow_adult",
        **kwargs
    ) -> Dict[str, Any]:
        """生成图像
        
        Args:
            prompt: 图像描述
            aspect_ratio: 宽高比（1:1, 16:9, 9:16, 4:3, 3:4）
            safety_filter_level: 安全过滤级别
            person_generation: 人物生成设置
            **kwargs: 其他参数
            
        Returns:
            Dict: 生成结果
        """
        # 调用 Imagen API
        response = await self.client.aio.models.generate_images(
            model="imagen-3.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                safety_filter_level=safety_filter_level,
                person_generation=person_generation,
                **kwargs
            )
        )
        
        # 提取图像数据
        image = response.generated_images[0]
        image_data = base64.b64encode(image.image.image_bytes).decode()
        
        return {
            "image": f"data:image/png;base64,{image_data}",
            "prompt": prompt,
            "model": "imagen-3.0-generate-001"
        }
```

### 图像编辑

```python
async def edit_image(
    self,
    reference_image: bytes,
    prompt: str,
    mask: Optional[bytes] = None,
    **kwargs
) -> Dict[str, Any]:
    """编辑图像
    
    Args:
        reference_image: 参考图像（字节）
        prompt: 编辑描述
        mask: 遮罩图像（可选）
        **kwargs: 其他参数
        
    Returns:
        Dict: 编辑结果
    """
    # 准备图像数据
    reference_image_part = types.Part(
        inline_data=types.Blob(
            mime_type="image/png",
            data=reference_image
        )
    )
    
    # 准备遮罩（如果提供）
    mask_part = None
    if mask:
        mask_part = types.Part(
            inline_data=types.Blob(
                mime_type="image/png",
                data=mask
            )
        )
    
    # 调用编辑 API
    response = await self.client.aio.models.edit_image(
        model="imagen-3.0-capability-preview-0930",
        prompt=prompt,
        reference_images=[reference_image_part],
        mask=mask_part,
        config=types.EditImageConfig(**kwargs)
    )
    
    # 提取结果
    edited_image = response.generated_images[0]
    image_data = base64.b64encode(edited_image.image.image_bytes).decode()
    
    return {
        "image": f"data:image/png;base64,{image_data}",
        "prompt": prompt,
        "model": "imagen-3.0-capability-preview-0930"
    }
```

---

## 错误处理

### 重试机制

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ChatHandler:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def send_message_with_retry(self, messages, model, **kwargs):
        """发送消息（带重试）
        
        自动重试 3 次，指数退避（2s, 4s, 8s）
        """
        return await self.send_message(messages, model, **kwargs)
```

### 速率限制

```python
from asyncio import Semaphore

class GoogleService:
    def __init__(self, api_key: str, max_concurrent: int = 5):
        super().__init__(api_key)
        self.semaphore = Semaphore(max_concurrent)

    async def send_chat_message(self, messages, model, **kwargs):
        """发送消息（带速率限制）"""
        async with self.semaphore:
            return await self.chat_handler.send_message(messages, model, **kwargs)
```

### 异常处理

```python
from google.genai.errors import APIError, ClientError
from ...core.exceptions import ProviderError, ValidationError

async def send_message(self, messages, model, **kwargs):
    """发送消息（带异常处理）"""
    try:
        # 输入验证
        if not messages:
            raise ValidationError("消息列表不能为空")
        
        # API 调用
        response = await self.client.aio.models.generate_content(...)
        return response
        
    except ClientError as e:
        # 客户端错误（400）
        raise ValidationError(f"请求参数错误: {str(e)}")
        
    except APIError as e:
        # API 错误（500）
        raise ProviderError(f"Gemini API 错误: {str(e)}")
        
    except Exception as e:
        # 未知错误
        raise ProviderError(f"未知错误: {str(e)}")
```

---

## 测试规范

### Mock 测试

```python
# backend/tests/test_chat_handler.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.gemini.chat_handler import ChatHandler

@pytest.fixture
def mock_client():
    """创建 Mock 客户端"""
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(text="Hello!")
    )
    return client

@pytest.fixture
def chat_handler(mock_client):
    """创建 ChatHandler 实例"""
    handler = ChatHandler(api_key="test_key")
    handler.client = mock_client
    return handler

@pytest.mark.asyncio
async def test_send_message(chat_handler):
    """测试发送消息"""
    result = await chat_handler.send_message(
        messages=[{"role": "user", "content": "Hi"}],
        model="gemini-pro"
    )
    
    assert result["message"] == "Hello!"
    assert result["role"] == "assistant"
```

### 集成测试

```python
# backend/tests/test_gemini_integration.py
import pytest
import os
from app.services.gemini.google_service import GoogleService

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="需要 GOOGLE_API_KEY 环境变量"
)
@pytest.mark.asyncio
async def test_real_api_call():
    """测试真实 API 调用"""
    service = GoogleService(api_key=os.getenv("GOOGLE_API_KEY"))
    
    result = await service.send_chat_message(
        messages=[{"role": "user", "content": "Say hello"}],
        model="gemini-1.5-flash"
    )
    
    assert "message" in result
    assert result["role"] == "assistant"
    assert len(result["message"]) > 0
```

---

## 开发检查清单

### 开发前

- [ ] 阅读 Gemini 官方文档
- [ ] 查看 SDK 原始代码
- [ ] 理解现有实现模式
- [ ] 确认 API 密钥配置

### 开发中

- [ ] 继承 `BaseProviderService` 基类
- [ ] 实现所有抽象方法
- [ ] 使用模块化架构（每个功能单独文件）
- [ ] 添加重试机制和速率限制
- [ ] 实现完整的异常处理
- [ ] 添加类型注解和文档字符串
- [ ] 编写单元测试（Mock）

### 开发后

- [ ] 运行单元测试（pytest）
- [ ] 运行集成测试（需要 API 密钥）
- [ ] 验证错误处理（模拟各种错误）
- [ ] 检查代码覆盖率（> 80%）
- [ ] 更新 API 文档
- [ ] 提交代码前检查 git diff
