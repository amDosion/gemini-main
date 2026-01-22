---
name: backend-service
description: |
  创建和修改后端业务服务。适用于：
  - 创建新的 AI 提供商服务
  - 添加新的业务逻辑服务
  - 修改现有服务功能
  - 实现新的 AI 功能
---

# 后端服务开发技能

## 适用场景

当用户请求以下任务时，使用此技能：
- 创建新的 AI 提供商服务
- 添加新的业务逻辑服务
- 修改现有服务功能
- 实现新的 AI 功能（图像生成、编辑等）

## 项目结构

```
backend/app/services/
├── common/                 # 通用服务
│   ├── base_provider.py    # 提供商基类
│   ├── provider_config.py  # 提供商配置
│   ├── provider_factory.py # 提供商工厂
│   ├── auth_service.py     # 认证服务
│   ├── attachment_service.py # 附件服务
│   ├── embedding_service.py # 嵌入服务
│   ├── errors.py           # 错误定义
│   └── model_capabilities.py # 模型能力
├── gemini/                 # Google Gemini
│   ├── google_service.py   # 主服务
│   ├── chat_handler.py     # 聊天处理
│   ├── image_generator.py  # 图像生成
│   ├── image_edit_*.py     # 图像编辑
│   └── agent/              # 智能体
├── openai/                 # OpenAI
│   ├── openai_service.py
│   ├── chat_handler.py
│   └── image_generator.py
├── tongyi/                 # 通义千问
│   └── tongyi_service.py
└── ollama/                 # Ollama
    └── ollama_service.py
```

## 服务模板

### 提供商服务基类

```python
# services/common/base_provider.py
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional
from sqlalchemy.orm import Session

class BaseProviderService(ABC):
    """提供商服务基类"""

    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.user_id = user_id
        self.db = db
        self._client = None

    @property
    def client(self):
        """懒加载客户端"""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @abstractmethod
    def _create_client(self):
        """创建 API 客户端"""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """非流式聊天"""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式聊天"""
        pass

    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """图像生成（可选实现）"""
        raise NotImplementedError("Image generation not supported")

    async def edit_image(
        self,
        image: bytes,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """图像编辑（可选实现）"""
        raise NotImplementedError("Image editing not supported")
```

### 新提供商服务实现

```python
# services/xxx/xxx_service.py
from typing import AsyncGenerator, List, Dict, Any, Optional
from sqlalchemy.orm import Session

from ..common.base_provider import BaseProviderService
from ..common.errors import ProviderError, APIKeyError
from ...core.logger import get_logger

logger = get_logger(__name__)


class XxxService(BaseProviderService):
    """Xxx 提供商服务"""

    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None
    ):
        super().__init__(api_key, api_url, user_id, db)
        self.default_model = "xxx-default"

    def _create_client(self):
        """创建 API 客户端"""
        import xxx_sdk

        return xxx_sdk.Client(
            api_key=self.api_key,
            base_url=self.api_url or "https://api.xxx.com"
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """非流式聊天"""
        logger.info(f"[API] Xxx chat with model: {model}")

        try:
            # 转换消息格式
            formatted_messages = self._format_messages(messages)

            # 调用 API
            response = await self.client.chat.create(
                model=model or self.default_model,
                messages=formatted_messages,
                temperature=options.get("temperature", 0.7),
                max_tokens=options.get("maxTokens", 4096)
            )

            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "inputTokens": response.usage.prompt_tokens,
                    "outputTokens": response.usage.completion_tokens
                }
            }

        except Exception as e:
            logger.error(f"[ERROR] Xxx chat failed: {e}")
            raise ProviderError(str(e), "XXX_API_ERROR")

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式聊天"""
        logger.info(f"[API] Xxx stream chat with model: {model}")

        try:
            formatted_messages = self._format_messages(messages)

            stream = await self.client.chat.create(
                model=model or self.default_model,
                messages=formatted_messages,
                temperature=options.get("temperature", 0.7),
                max_tokens=options.get("maxTokens", 4096),
                stream=True
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {
                        "type": "text",
                        "content": chunk.choices[0].delta.content
                    }

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"[ERROR] Xxx stream failed: {e}")
            yield {"type": "error", "error": str(e)}

    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """图像生成"""
        logger.info(f"[API] Xxx image generation: {prompt[:50]}...")

        response = await self.client.images.generate(
            model=model or "xxx-image",
            prompt=prompt,
            n=kwargs.get("n", 1),
            size=kwargs.get("size", "1024x1024")
        )

        return {
            "images": [
                {"url": img.url, "b64": img.b64_json}
                for img in response.data
            ]
        }

    def _format_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """转换消息格式"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            # 统一角色名称
            if role == "model":
                role = "assistant"

            formatted.append({
                "role": role,
                "content": msg.get("content", "")
            })
        return formatted
```

### 在工厂中注册

```python
# services/common/provider_factory.py

from ..xxx.xxx_service import XxxService

# 在类初始化或模块加载时注册
ProviderFactory.register("xxx", XxxService)
```

### 在配置中添加

```python
# services/common/provider_config.py

PROVIDER_CONFIGS = {
    # ... 其他提供商
    "xxx": ProviderConfig(
        id="xxx",
        name="Xxx AI",
        description="Xxx AI 服务",
        default_model="xxx-default",
        capabilities=["chat", "image-gen"],
        models_endpoint="/v1/models",
        is_openai_compatible=False
    )
}
```

## 通用服务模板

### 业务逻辑服务

```python
# services/common/xxx_service.py
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ...core.logger import get_logger
from ...models.db_models import XxxModel

logger = get_logger(__name__)


class XxxBusinessService:
    """Xxx 业务服务"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    async def create(self, data: Dict[str, Any]) -> XxxModel:
        """创建"""
        item = XxxModel(
            user_id=self.user_id,
            **data
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        logger.info(f"[OK] Created xxx: {item.id}")
        return item

    async def get_by_id(self, item_id: str) -> Optional[XxxModel]:
        """获取单个"""
        return self.db.query(XxxModel).filter(
            XxxModel.id == item_id,
            XxxModel.user_id == self.user_id
        ).first()

    async def list_all(self) -> List[XxxModel]:
        """获取列表"""
        return self.db.query(XxxModel).filter(
            XxxModel.user_id == self.user_id
        ).order_by(XxxModel.created_at.desc()).all()

    async def update(
        self,
        item_id: str,
        data: Dict[str, Any]
    ) -> Optional[XxxModel]:
        """更新"""
        item = await self.get_by_id(item_id)
        if not item:
            return None

        for key, value in data.items():
            if hasattr(item, key):
                setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)
        logger.info(f"[OK] Updated xxx: {item_id}")
        return item

    async def delete(self, item_id: str) -> bool:
        """删除"""
        item = await self.get_by_id(item_id)
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()
        logger.info(f"[OK] Deleted xxx: {item_id}")
        return True
```

## 错误处理

```python
# services/common/errors.py
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ErrorContext:
    provider_id: str
    operation: str
    request_id: str
    user_id: Optional[str] = None

class ProviderError(Exception):
    """提供商错误基类"""
    def __init__(
        self,
        message: str,
        code: str,
        context: Optional[ErrorContext] = None,
        recoverable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.context = context
        self.recoverable = recoverable

class APIKeyError(ProviderError):
    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message, "API_KEY_ERROR", recoverable=False)

class RateLimitError(ProviderError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT", recoverable=True)

class TimeoutError(ProviderError):
    def __init__(self, message: str = "Request timeout"):
        super().__init__(message, "TIMEOUT", recoverable=True)
```

## 开发步骤

1. **确定服务类型**：提供商服务或业务服务
2. **创建服务文件**：在相应目录创建
3. **实现基类方法**：chat、chat_stream 等
4. **注册到工厂**：在 provider_factory.py 中添加
5. **添加配置**：在 provider_config.py 中添加
6. **测试服务**：编写单元测试

## 注意事项

- 继承 `BaseProviderService` 实现提供商服务
- 使用工厂模式创建服务实例
- API Key 已在路由层解密
- 所有查询必须加 `user_id` 过滤
- 使用 `AsyncGenerator` 实现流式响应
- 错误使用 `ProviderError` 体系
