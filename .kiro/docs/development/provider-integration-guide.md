---
inclusion: fileMatch
fileMatchPattern: "backend/app/services/**/*_service.py"
---

# AI 提供商集成规范

## 概述

本项目采用插件化架构，支持多个 AI 提供商。所有提供商必须实现统一接口，确保可替换性和一致性。

---

## 提供商接口定义

### BaseProviderService

所有提供商服务必须继承 `BaseProviderService` 基类：

```python
# backend/app/services/base_provider.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, AsyncGenerator

class BaseProviderService(ABC):
    """AI 提供商基类"""

    def __init__(self, api_key: str, **kwargs):
        """
        初始化提供商服务

        Args:
            api_key: API 密钥
            **kwargs: 其他配置参数
        """
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取可用模型列表

        Returns:
            模型列表，每个模型包含：
            - id: 模型 ID
            - name: 显示名称
            - capabilities: 能力列表（chat, image-gen, etc.）
            - input_token_limit: 输入 token 限制
            - output_token_limit: 输出 token 限制
        """
        pass

    @abstractmethod
    async def send_chat_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送聊天消息

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型 ID
            **kwargs: 其他参数（temperature, max_tokens, etc.）

        Returns:
            响应字典：
            {
                "content": "AI 响应内容",
                "model": "使用的模型 ID",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                    "total_tokens": 300
                },
                "finish_reason": "stop"
            }

        Raises:
            AuthenticationError: 认证失败
            RateLimitError: 速率限制
            APIError: API 错误
        """
        pass

    @abstractmethod
    async def stream_chat_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式发送聊天消息

        Args:
            messages: 消息列表
            model: 模型 ID
            **kwargs: 其他参数

        Yields:
            流式数据块：
            {"type": "content", "text": "部分内容"}
            {"type": "done", "usage": {...}}
        """
        pass

    @abstractmethod
    async def validate_api_key(self) -> bool:
        """
        验证 API 密钥有效性

        Returns:
            True 如果密钥有效，否则 False
        """
        pass

    # 可选方法（提供默认实现）
    async def generate_image(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成图像（可选）"""
        raise NotImplementedError("Image generation not supported")

    async def edit_image(self, image: bytes, prompt: str, **kwargs) -> Dict[str, Any]:
        """编辑图像（可选）"""
        raise NotImplementedError("Image editing not supported")

    async def generate_video(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成视频（可选）"""
        raise NotImplementedError("Video generation not supported")

    async def generate_audio(self, text: str, **kwargs) -> Dict[str, Any]:
        """生成音频（可选）"""
        raise NotImplementedError("Audio generation not supported")
```

---

## 模块化实现要求 ⭐

### 服务拆分原则

每个 AI 提供商服务**必须遵循模块化原则**：

1. **功能模块独立文件** - 每个功能（聊天、图像生成、模型管理等）单独文件
2. **主协调器组装** - 主服务文件负责组装和协调各个模块
3. **文件大小限制** - 单个文件不超过 300 行（理想）
4. **职责单一** - 每个模块只负责一个具体功能

**✅ 正确的目录结构**：
```
backend/app/services/
└── gemini/                    # Google Gemini 提供商
    ├── google_service.py      # 主协调器（组装模块）✅
    ├── chat_handler.py        # 聊天处理模块 ✅
    ├── image_generator.py     # 图像生成模块 ✅
    ├── video_generator.py     # 视频生成模块 ✅
    ├── model_manager.py       # 模型管理模块 ✅
    ├── file_handler.py        # 文件处理模块 ✅
    └── function_handler.py    # 函数调用模块 ✅
```

**❌ 错误的结构**：
```
backend/app/services/
└── gemini/
    └── google_service.py      # 所有功能都在一个文件（2000+ 行）❌
```

---

## 提供商实现示例

### Google Gemini 提供商（模块化实现）

```python
# backend/app/services/gemini/google_service.py
from ..base_provider import BaseProviderService
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .model_manager import ModelManager

class GoogleService(BaseProviderService):
    """Google Gemini 提供商"""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.chat_handler = ChatHandler(api_key)
        self.image_generator = ImageGenerator(api_key)
        self.model_manager = ModelManager(api_key)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取 Google 模型列表"""
        return self.model_manager.get_models()

    async def send_chat_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天消息"""
        try:
            response = await self.chat_handler.send_message(
                messages=messages,
                model=model,
                **kwargs
            )
            return self._format_chat_response(response)

        except Exception as e:
            raise self._handle_error(e)

    async def stream_chat_message(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式聊天"""
        try:
            async for chunk in self.chat_handler.stream_message(
                messages=messages,
                model=model,
                **kwargs
            ):
                yield self._format_stream_chunk(chunk)

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    async def validate_api_key(self) -> bool:
        """验证 API 密钥"""
        try:
            await self.model_manager.list_models()
            return True
        except:
            return False

    async def generate_image(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成图像"""
        return await self.image_generator.generate(prompt, **kwargs)

    def _format_chat_response(self, response) -> Dict[str, Any]:
        """格式化聊天响应为统一格式"""
        return {
            "content": response.text,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "finish_reason": response.finish_reason
        }

    def _format_stream_chunk(self, chunk) -> Dict[str, Any]:
        """格式化流式数据块"""
        if chunk.text:
            return {"type": "content", "text": chunk.text}
        elif chunk.is_done:
            return {"type": "done", "usage": {...}}

    def _handle_error(self, error: Exception):
        """统一错误处理"""
        if "API key" in str(error):
            raise AuthenticationError("Invalid API key")
        elif "rate limit" in str(error):
            raise RateLimitError("Rate limit exceeded")
        else:
            raise APIError(f"Google API error: {error}")
```

---

## 提供商配置注册

### ProviderConfig

在 `provider_config.py` 中注册提供商配置：

```python
# backend/app/services/provider_config.py
class ProviderConfig:
    """提供商配置中心"""

    CONFIGS = {
        "google": {
            "id": "google",
            "name": "Google Gemini",
            "service_class": "GoogleService",
            "base_url": "https://generativelanguage.googleapis.com/v1",
            "required_env_vars": ["GOOGLE_API_KEY"],
            "supports": [
                "chat",
                "image-gen",
                "video-gen",
                "audio-gen",
                "function-calling",
                "streaming"
            ],
            "models": {
                "gemini-2.0-flash-exp": {
                    "name": "Gemini 2.0 Flash (Experimental)",
                    "capabilities": ["chat", "image-input", "thinking"],
                    "input_token_limit": 1000000,
                    "output_token_limit": 8192
                },
                "imagen-3.0-generate-001": {
                    "name": "Imagen 3.0",
                    "capabilities": ["image-gen"],
                    "max_images": 4
                }
            }
        },

        "openai": {
            "id": "openai",
            "name": "OpenAI",
            "service_class": "OpenAIService",
            "base_url": "https://api.openai.com/v1",
            "required_env_vars": ["OPENAI_API_KEY"],
            "supports": ["chat", "image-gen", "audio-gen", "streaming"],
            "models": {
                "gpt-4o": {
                    "name": "GPT-4o",
                    "capabilities": ["chat", "image-input"],
                    "input_token_limit": 128000,
                    "output_token_limit": 16384
                }
            }
        },

        "qwen": {
            "id": "qwen",
            "name": "通义千问",
            "service_class": "QwenService",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "required_env_vars": ["DASHSCOPE_API_KEY"],
            "supports": ["chat", "image-gen", "image-edit", "streaming"],
            "models": {
                "qwen-max": {
                    "name": "通义千问 Max",
                    "capabilities": ["chat"],
                    "input_token_limit": 30000,
                    "output_token_limit": 8000
                }
            }
        }
    }

    @classmethod
    def get_config(cls, provider_id: str) -> Dict[str, Any]:
        """获取提供商配置"""
        if provider_id not in cls.CONFIGS:
            raise ValueError(f"Unknown provider: {provider_id}")
        return cls.CONFIGS[provider_id]

    @classmethod
    def list_providers(cls) -> List[Dict[str, Any]]:
        """列出所有提供商"""
        return [
            {"id": k, "name": v["name"], "supports": v["supports"]}
            for k, v in cls.CONFIGS.items()
        ]
```

---

## 提供商工厂

### ProviderFactory

使用工厂模式创建提供商实例：

```python
# backend/app/services/provider_factory.py
from typing import Type
from .base_provider import BaseProviderService
from .provider_config import ProviderConfig
from .gemini.google_service import GoogleService
from .openai_service import OpenAIService
from .qwen_native import QwenService

class ProviderFactory:
    """提供商工厂"""

    # 注册服务类
    _SERVICE_REGISTRY = {
        "GoogleService": GoogleService,
        "OpenAIService": OpenAIService,
        "QwenService": QwenService,
    }

    @classmethod
    def create(
        cls,
        provider_id: str,
        api_key: str,
        **kwargs
    ) -> BaseProviderService:
        """
        创建提供商服务实例

        Args:
            provider_id: 提供商 ID（如 "google", "openai"）
            api_key: API 密钥
            **kwargs: 其他配置参数

        Returns:
            提供商服务实例

        Raises:
            ValueError: 未知的提供商 ID
        """
        # 获取配置
        config = ProviderConfig.get_config(provider_id)

        # 获取服务类
        service_class_name = config["service_class"]
        service_class = cls._SERVICE_REGISTRY.get(service_class_name)

        if not service_class:
            raise ValueError(f"Service class not found: {service_class_name}")

        # 创建实例
        return service_class(api_key=api_key, **kwargs)

    @classmethod
    def register_service(cls, name: str, service_class: Type[BaseProviderService]):
        """
        注册新的提供商服务类

        Args:
            name: 服务类名称
            service_class: 服务类
        """
        cls._SERVICE_REGISTRY[name] = service_class
```

---

## 错误处理

### 自定义异常

```python
# backend/app/services/exceptions.py
class ProviderError(Exception):
    """提供商基础异常"""
    pass

class AuthenticationError(ProviderError):
    """认证错误"""
    pass

class RateLimitError(ProviderError):
    """速率限制错误"""
    pass

class APIError(ProviderError):
    """API 错误"""
    pass

class ModelNotFoundError(ProviderError):
    """模型不存在"""
    pass

class InvalidParameterError(ProviderError):
    """参数无效"""
    pass
```

### 错误处理示例

```python
async def send_chat_message(self, messages, model, **kwargs):
    """发送聊天消息"""
    try:
        response = await self._api_call(messages, model, **kwargs)
        return response

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif e.response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        elif e.response.status_code == 404:
            raise ModelNotFoundError(f"Model not found: {model}")
        else:
            raise APIError(f"API error: {e.response.text}")

    except httpx.TimeoutException:
        raise APIError("Request timeout")

    except Exception as e:
        raise APIError(f"Unexpected error: {str(e)}")
```

---

## 添加新提供商步骤

### 1. 创建服务类

```python
# backend/app/services/my_provider/my_service.py
from ..base_provider import BaseProviderService

class MyProviderService(BaseProviderService):
    """自定义提供商"""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        # 初始化客户端
        self.client = MyProviderClient(api_key)

    def get_available_models(self):
        """实现方法"""
        ...

    async def send_chat_message(self, messages, model, **kwargs):
        """实现方法"""
        ...

    async def stream_chat_message(self, messages, model, **kwargs):
        """实现方法"""
        ...

    async def validate_api_key(self):
        """实现方法"""
        ...
```

### 2. 注册配置

```python
# backend/app/services/provider_config.py
ProviderConfig.CONFIGS["my-provider"] = {
    "id": "my-provider",
    "name": "My Provider",
    "service_class": "MyProviderService",
    "base_url": "https://api.myprovider.com/v1",
    "required_env_vars": ["MY_PROVIDER_API_KEY"],
    "supports": ["chat", "streaming"],
    "models": {
        "my-model-1": {
            "name": "My Model 1",
            "capabilities": ["chat"],
            "input_token_limit": 100000,
            "output_token_limit": 4096
        }
    }
}
```

### 3. 注册到工厂

```python
# backend/app/services/provider_factory.py
from .my_provider.my_service import MyProviderService

ProviderFactory._SERVICE_REGISTRY["MyProviderService"] = MyProviderService
```

### 4. 添加测试

```python
# backend/tests/test_my_provider.py
import pytest
from app.services.provider_factory import ProviderFactory

@pytest.mark.asyncio
async def test_my_provider_chat():
    """测试聊天功能"""
    service = ProviderFactory.create("my-provider", api_key="test_key")

    response = await service.send_chat_message(
        messages=[{"role": "user", "content": "Hello"}],
        model="my-model-1"
    )

    assert "content" in response
    assert response["model"] == "my-model-1"

@pytest.mark.asyncio
async def test_my_provider_stream():
    """测试流式响应"""
    service = ProviderFactory.create("my-provider", api_key="test_key")

    chunks = []
    async for chunk in service.stream_chat_message(
        messages=[{"role": "user", "content": "Hello"}],
        model="my-model-1"
    ):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert chunks[-1]["type"] == "done"
```

### 5. 更新前端（可选）

如果需要前端支持：

```typescript
// frontend/services/providers/my-provider/MyProviderClient.ts
import { AIProvider } from '../interfaces';

export class MyProviderClient implements AIProvider {
  constructor(private apiKey: string) {}

  async sendMessage(messages, model, options) {
    // 实现
  }

  async *streamMessage(messages, model, options) {
    // 实现
  }
}
```

---

## 最佳实践

### 1. 统一接口
- 所有提供商实现相同接口
- 统一错误格式
- 统一响应格式

### 2. 错误处理
- 捕获所有异常
- 转换为统一错误类型
- 提供详细错误信息

### 3. 配置驱动
- 通过配置文件注册提供商
- 避免硬编码
- 便于扩展

### 4. 测试覆盖
- 单元测试所有方法
- Mock API 调用
- 测试错误场景

### 5. 文档完善
- 注释说明参数和返回值
- 提供使用示例
- 记录已知限制

---

**更新日期**：2026-01-09
**版本**：v1.0.0
