---
name: api-integration
description: |
  添加新的 AI 提供商或 API 集成。适用于：
  - 集成新的 AI 提供商
  - 添加 OpenAI 兼容提供商
  - 配置 API 端点和模型
  - 实现前后端完整集成
---

# API 集成技能

## 适用场景

当用户请求以下任务时，使用此技能：
- 集成新的 AI 提供商（如新的 LLM 服务）
- 添加 OpenAI 兼容提供商
- 配置新的 API 端点和模型
- 实现前后端完整的 API 集成

## 提供商类型

### 1. 完整实现提供商
需要完整实现服务类，如 Google Gemini、阿里通义千问

### 2. OpenAI 兼容提供商
只需配置，自动复用 OpenAI 服务类，如 DeepSeek、Moonshot

## 添加 OpenAI 兼容提供商

### 步骤 1：后端配置

```python
# backend/app/services/common/provider_config.py

PROVIDER_CONFIGS = {
    # ... 其他提供商

    "new-provider": ProviderConfig(
        id="new-provider",
        name="New Provider",
        description="新提供商描述",
        default_model="new-model-v1",
        default_api_url="https://api.newprovider.com/v1",
        capabilities=["chat"],  # 支持的功能
        models_endpoint="/models",  # 模型列表端点
        is_openai_compatible=True,  # 标记为 OpenAI 兼容
        requires_api_key=True
    )
}
```

### 步骤 2：前端添加提供商选项

```typescript
// frontend/services/providers.ts 或相关配置文件

export const PROVIDERS = [
  // ... 其他提供商
  {
    id: 'new-provider',
    name: 'New Provider',
    description: '新提供商描述',
    requiresApiKey: true,
    supportsCustomUrl: false,
    defaultModels: ['new-model-v1', 'new-model-v2']
  }
];
```

### 步骤 3：添加模型配置

```typescript
// frontend/types/types.ts 或 modelFilter.ts

export const MODEL_CONFIGS = {
  // ... 其他模型
  'new-model-v1': {
    provider: 'new-provider',
    capabilities: ['chat'],
    contextWindow: 128000,
    maxOutputTokens: 8192
  }
};
```

## 添加完整提供商

### 步骤 1：后端服务实现

```python
# backend/app/services/newprovider/newprovider_service.py

from ..common.base_provider import BaseProviderService
from typing import AsyncGenerator, List, Dict, Any

class NewProviderService(BaseProviderService):
    """新提供商服务"""

    def _create_client(self):
        import newprovider_sdk
        return newprovider_sdk.Client(api_key=self.api_key)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = await self.client.chat(
            messages=messages,
            model=model,
            **options
        )
        return {"content": response.text}

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async for chunk in self.client.chat_stream(messages, model):
            yield {"type": "text", "content": chunk.text}
        yield {"type": "done"}
```

### 步骤 2：注册到工厂

```python
# backend/app/services/common/provider_factory.py

from ..newprovider.newprovider_service import NewProviderService

ProviderFactory.register("new-provider", NewProviderService)
```

### 步骤 3：添加配置

```python
# backend/app/services/common/provider_config.py

PROVIDER_CONFIGS = {
    "new-provider": ProviderConfig(
        id="new-provider",
        name="New Provider",
        default_model="new-model",
        capabilities=["chat", "image-gen"],
        is_openai_compatible=False
    )
}
```

### 步骤 4：前端服务（如需特殊处理）

```typescript
// frontend/services/providers/newprovider.ts

import { apiClient } from '../apiClient';

export const newProviderApi = {
  async chat(messages: Message[], model: string, options: ChatOptions) {
    return apiClient.post('/api/modes/new-provider/chat', {
      messages,
      modelId: model,
      options
    });
  },

  async generateImage(prompt: string, options: ImageOptions) {
    return apiClient.post('/api/modes/new-provider/image-gen', {
      prompt,
      options
    });
  }
};
```

## API 端点约定

### 聊天 API
```
POST /api/modes/{provider}/chat
```

### 模式 API
```
POST /api/modes/{provider}/{mode}
```

### 模型列表
```
GET /api/models/{provider}
```

## 请求格式

### 聊天请求
```json
{
  "modelId": "model-name",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "message": "New message",
  "options": {
    "temperature": 0.7,
    "maxTokens": 4096,
    "enableSearch": false
  },
  "stream": true
}
```

### 图像生成请求
```json
{
  "modelId": "image-model",
  "prompt": "A beautiful sunset",
  "options": {
    "aspectRatio": "16:9",
    "numberOfImages": 1
  }
}
```

## 流式响应格式

```
data: {"type": "text", "content": "Hello"}

data: {"type": "text", "content": " world"}

data: {"type": "thinking", "content": "Analyzing..."}

data: {"type": "done"}

data: [DONE]
```

## 前端处理流式响应

```typescript
// frontend/hooks/handlers/ChatHandlerClass.ts

async *processStream(context: ExecutionContext) {
  const response = await fetch('/api/modes/provider/chat', {
    method: 'POST',
    body: JSON.stringify({...}),
    signal: context.signal
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        const chunk = JSON.parse(data);
        yield chunk;
      }
    }
  }
}
```

## 测试集成

### 后端测试
```python
# tests/test_new_provider.py
import pytest
from app.services.newprovider.newprovider_service import NewProviderService

@pytest.mark.asyncio
async def test_chat():
    service = NewProviderService(api_key="test-key")
    result = await service.chat(
        messages=[{"role": "user", "content": "Hello"}],
        model="test-model",
        options={}
    )
    assert "content" in result
```

### 前端测试
```typescript
// __tests__/newprovider.test.ts
import { newProviderApi } from '../services/providers/newprovider';

describe('NewProvider API', () => {
  it('should send chat request', async () => {
    const result = await newProviderApi.chat(
      [{ role: 'user', content: 'Hello' }],
      'test-model',
      {}
    );
    expect(result.content).toBeDefined();
  });
});
```

## 检查清单

- [ ] 后端：添加 provider_config.py 配置
- [ ] 后端：实现或复用服务类
- [ ] 后端：在 provider_factory.py 注册
- [ ] 前端：添加提供商选项
- [ ] 前端：添加模型配置
- [ ] 前端：实现特殊处理（如需要）
- [ ] 测试：后端单元测试
- [ ] 测试：前端集成测试
- [ ] 文档：更新 README
