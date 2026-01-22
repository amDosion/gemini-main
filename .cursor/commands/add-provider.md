# 添加新的 AI 提供商

为项目添加一个新的 AI 提供商集成。

## 提供商类型判断

首先确定提供商类型：
- **OpenAI 兼容**：API 格式与 OpenAI 相同（如 DeepSeek、Moonshot）→ 只需配置
- **完整实现**：独特的 API 格式（如 Google Gemini、阿里通义）→ 需要完整实现

## OpenAI 兼容提供商（简单）

### 只需一步：添加配置

```python
# backend/app/services/common/provider_config.py

PROVIDER_CONFIGS = {
    # ... 现有提供商

    "[new-provider]": ProviderConfig(
        id="[new-provider]",
        name="[Provider Name]",
        description="[提供商描述]",
        default_model="[default-model-id]",
        default_api_url="https://api.[provider].com/v1",
        capabilities=["chat"],  # 支持的功能列表
        models_endpoint="/models",
        is_openai_compatible=True,
        requires_api_key=True
    )
}
```

完成！系统会自动使用 OpenAI 服务类处理请求。

## 完整实现提供商（复杂）

### 步骤 1：创建服务类

```python
# backend/app/services/[provider]/[provider]_service.py

from typing import AsyncGenerator, List, Dict, Any, Optional
from sqlalchemy.orm import Session

from ..common.base_provider import BaseProviderService
from ..common.errors import ProviderError
from ...core.logger import get_logger

logger = get_logger(__name__)


class [Provider]Service(BaseProviderService):
    """[Provider] 提供商服务"""

    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None
    ):
        super().__init__(api_key, api_url, user_id, db)
        self.default_model = "[default-model]"

    def _create_client(self):
        """创建 API 客户端"""
        import [provider]_sdk
        return [provider]_sdk.Client(
            api_key=self.api_key,
            base_url=self.api_url
        )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """非流式聊天"""
        logger.info(f"[API] [Provider] chat: {model}")

        try:
            response = await self.client.chat(
                model=model or self.default_model,
                messages=self._format_messages(messages),
                **options
            )

            return {
                "content": response.content,
                "model": response.model,
                "usage": {
                    "inputTokens": response.usage.input,
                    "outputTokens": response.usage.output
                }
            }
        except Exception as e:
            logger.error(f"[ERROR] [Provider] chat failed: {e}")
            raise ProviderError(str(e), "[PROVIDER]_API_ERROR")

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式聊天"""
        try:
            stream = await self.client.chat_stream(
                model=model or self.default_model,
                messages=self._format_messages(messages),
                **options
            )

            async for chunk in stream:
                yield {"type": "text", "content": chunk.content}

            yield {"type": "done"}
        except Exception as e:
            yield {"type": "error", "error": str(e)}

    def _format_messages(self, messages: List[Dict]) -> List[Dict]:
        """转换消息格式"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"
            formatted.append({"role": role, "content": msg.get("content", "")})
        return formatted
```

### 步骤 2：注册到工厂

```python
# backend/app/services/common/provider_factory.py

from ..[provider].[provider]_service import [Provider]Service

ProviderFactory.register("[provider]", [Provider]Service)
```

### 步骤 3：添加配置

```python
# backend/app/services/common/provider_config.py

PROVIDER_CONFIGS = {
    "[provider]": ProviderConfig(
        id="[provider]",
        name="[Provider Name]",
        default_model="[model-id]",
        capabilities=["chat", "image-gen"],  # 支持的功能
        is_openai_compatible=False,
        requires_api_key=True
    )
}
```

### 步骤 4：前端配置（如需特殊处理）

```typescript
// frontend/services/providers.ts
export const PROVIDERS = [
  // ...
  {
    id: '[provider]',
    name: '[Provider Name]',
    requiresApiKey: true,
    supportsCustomUrl: false
  }
];
```

## 检查清单

### OpenAI 兼容
- [ ] 添加 provider_config.py 配置

### 完整实现
- [ ] 创建服务类目录和文件
- [ ] 实现 chat 和 chat_stream 方法
- [ ] 注册到 provider_factory.py
- [ ] 添加 provider_config.py 配置
- [ ] 前端添加提供商选项（如需要）

## 使用示例

```
/add-provider 添加 Groq 提供商，它是 OpenAI 兼容的，API 地址是 https://api.groq.com/openai/v1
```

```
/add-provider 添加 Anthropic Claude 提供商，需要完整实现
```
