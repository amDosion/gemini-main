# Design Document

## Overview

本设计文档定义了通义千问后端集成的架构设计，目标是将前端的 DashScope API 调用迁移到后端。

**设计目标**：
- 使用 `qwen_native.py` 调用 DashScope API
- 提供与前端兼容的 API 接口
- 支持渐进式迁移，降低风险
- 提高安全性（API Key 在后端管理）
- 优化性能（缓存、连接池）

**设计原则**：
- 最小化前端改动
- 保持向后兼容
- 支持功能开关和回滚
- 统一错误处理
- 完善日志监控

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│  前端 (Browser)                                              │
│  ├─ DashScopeProvider.ts                                    │
│  ├─ chat.ts (streamNativeDashScope)                         │
│  ├─ models.ts (getTongYiModels)                             │
│  └─ api.ts (resolveDashUrl)                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP Request
                              │ (逐步迁移到后端 API)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  后端 API (FastAPI)                                          │
│  ├─ /api/chat/tongyi (聊天 API)                             │
│  ├─ /api/models/tongyi (模型列表 API)                       │
│  └─ Feature Flag (功能开关)                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 调用
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  qwen_native.py (通义千问原生 SDK)                           │
│  ├─ QwenNativeProvider                                      │
│  ├─ _sync_chat() / _sync_stream_chat()                     │
│  ├─ get_available_models()                                  │
│  └─ _format_response() / _format_stream_chunk()            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ DashScope SDK
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  DashScope API (阿里云)                                      │
│  └─ https://dashscope.aliyuncs.com/*                        │
└─────────────────────────────────────────────────────────────┘
```

### 迁移策略

**阶段一：后端 API 实现**（本次任务）
1. 实现 `/api/chat/tongyi` 聊天 API
2. 实现 `/api/models/tongyi` 模型列表 API
3. 集成 `qwen_native.py`
4. 实现响应格式转换

**阶段二：前端适配**（后续任务）
1. 修改 `DashScopeProvider.ts`，添加后端 API 调用逻辑
2. 添加功能开关，控制使用后端 API 还是直接调用
3. 保留回滚机制（后端失败时回退到前端直接调用）

**阶段三：全面迁移**（后续任务）
1. 默认使用后端 API
2. 移除前端的 DashScope 直接调用代码
3. 清理前端的 API Key 配置

## Components and Interfaces

### 1. 聊天 API

**端点**: `POST /api/chat/tongyi`

**请求体**:
```typescript
{
  modelId: string;              // 模型 ID
  messages: Message[];          // 消息历史
  message: string;              // 当前消息
  attachments: Attachment[];    // 附件（图片等）
  options: ChatOptions;         // 聊天选项
  apiKey: string;               // DashScope API Key
}
```

**响应**: SSE 流式响应

```
data: {"text": "你好", "chunk_type": "content"}

data: {"text": "", "chunk_type": "done", "usage": {...}}
```

**实现逻辑**:
```python
@router.post("/api/chat/tongyi")
async def chat_tongyi(request: ChatRequest):
    # 1. 初始化 QwenNativeProvider
    provider = QwenNativeProvider(
        api_key=request.apiKey,
        connection_mode="official"
    )
    
    # 2. 转换消息格式
    messages = convert_messages(request.messages, request.message)
    
    # 3. 调用流式聊天
    async def generate():
        async for chunk in provider.stream_chat(
            messages=messages,
            model=request.modelId,
            enable_search=request.options.enableSearch,
            enable_thinking=request.options.enableThinking,
            temperature=request.options.temperature
        ):
            # 4. 转换响应格式
            stream_update = convert_to_stream_update(chunk)
            yield f"data: {json.dumps(stream_update)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 2. 模型列表 API

**端点**: `GET /api/models/tongyi`

**查询参数**:
```
apiKey: string  // DashScope API Key
```

**响应**:
```typescript
{
  models: ModelConfig[]
}
```

**ModelConfig 格式**:
```typescript
{
  id: string;
  name: string;
  description: string;
  capabilities: {
    vision: boolean;
    reasoning: boolean;
    coding: boolean;
    search: boolean;
  };
  baseModelId: string;
}
```

**实现逻辑**:
```python
@router.get("/api/models/tongyi")
async def get_tongyi_models(apiKey: str):
    # 1. 检查缓存
    cache_key = f"tongyi_models:{apiKey[:8]}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 2. 初始化 QwenNativeProvider
    provider = QwenNativeProvider(api_key=apiKey)
    
    # 3. 获取模型列表
    model_ids = await provider.get_available_models()
    
    # 4. 转换为 ModelConfig 格式
    models = convert_to_model_configs(model_ids)
    
    # 5. 缓存结果（1 小时）
    await redis.setex(cache_key, 3600, json.dumps(models))
    
    return {"models": models}
```

### 3. 消息格式转换

**前端 Message 格式**:
```typescript
{
  role: "user" | "model" | "system";
  content: string;
  attachments?: Attachment[];
  isError?: boolean;
}
```

**qwen_native.py 消息格式**:
```python
{
  "role": "user" | "assistant" | "system",
  "content": str
}
```

**转换逻辑**:
```python
def convert_messages(history: List[Message], current_message: str) -> List[dict]:
    messages = []
    
    # 转换历史消息
    for msg in history:
        if msg.isError:
            continue
        if not msg.content:
            continue
        
        role = "assistant" if msg.role == "model" else msg.role
        messages.append({
            "role": role,
            "content": msg.content
        })
    
    # 添加当前消息
    if current_message:
        messages.append({
            "role": "user",
            "content": current_message
        })
    
    return messages
```

### 4. 响应格式转换

**qwen_native.py StreamChunk 格式**:
```python
{
  "content": str,
  "chunk_type": "reasoning" | "content" | "done",
  "finish_reason": Optional[str],
  "prompt_tokens": Optional[int],
  "completion_tokens": Optional[int],
  "total_tokens": Optional[int],
  "search_results": Optional[List[dict]]
}
```

**前端 StreamUpdate 格式**:
```typescript
{
  text: string;
  chunk_type?: "reasoning" | "content" | "done";
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  groundingMetadata?: {
    groundingChunks: Array<{
      web: {
        uri: string;
        title: string;
      }
    }>
  };
}
```

**转换逻辑**:
```python
def convert_to_stream_update(chunk: dict) -> dict:
    result = {
        "text": chunk.get("content", ""),
        "chunk_type": chunk.get("chunk_type", "content")
    }
    
    # 添加 usage 信息
    if chunk.get("chunk_type") == "done":
        result["usage"] = {
            "prompt_tokens": chunk.get("prompt_tokens", 0),
            "completion_tokens": chunk.get("completion_tokens", 0),
            "total_tokens": chunk.get("total_tokens", 0)
        }
    
    # 转换搜索结果
    if chunk.get("search_results"):
        result["groundingMetadata"] = {
            "groundingChunks": [
                {
                    "web": {
                        "uri": item.get("url", ""),
                        "title": item.get("title", "Source")
                    }
                }
                for item in chunk["search_results"]
            ]
        }
    
    return result
```

### 5. 模型配置转换

**qwen_native.py 返回**: `List[str]` (模型 ID 列表)

**前端期望**: `List[ModelConfig]`

**转换逻辑**:
```python
# 模型元数据注册表（与前端 models.ts 保持一致）
TONGYI_MODEL_REGISTRY = {
    "qwen-deep-research": {
        "name": "Qwen Deep Research",
        "description": "Specialized model for deep web research and complex query resolution.",
        "capabilities": {"vision": False, "reasoning": True, "coding": True, "search": True},
        "score": 110
    },
    "qwq-32b": {
        "name": "Qwen QwQ 32B",
        "description": "Reasoning-focused model with Deep Thinking capabilities.",
        "capabilities": {"vision": False, "reasoning": True, "coding": True, "search": False},
        "score": 105
    },
    # ... 其他模型
}

def convert_to_model_configs(model_ids: List[str]) -> List[dict]:
    models = []
    
    for model_id in model_ids:
        # 从注册表获取元数据
        if model_id in TONGYI_MODEL_REGISTRY:
            meta = TONGYI_MODEL_REGISTRY[model_id]
            models.append({
                "id": model_id,
                "name": meta["name"],
                "description": meta["description"],
                "capabilities": meta["capabilities"],
                "baseModelId": model_id,
                "_score": meta.get("score", 0)
            })
        else:
            # 默认配置
            models.append({
                "id": model_id,
                "name": model_id,
                "description": "DashScope Model",
                "capabilities": {
                    "vision": "vl" in model_id.lower() or "image" in model_id.lower(),
                    "reasoning": "qwq" in model_id.lower(),
                    "coding": True,
                    "search": False
                },
                "baseModelId": model_id,
                "_score": 0
            })
    
    # 排序（按 score 降序）
    models.sort(key=lambda x: x.get("_score", 0), reverse=True)
    
    return models
```

## Data Models

### 请求模型

```python
from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str  # "user" | "model" | "system"
    content: str
    isError: Optional[bool] = False

class Attachment(BaseModel):
    url: Optional[str]
    name: Optional[str]
    type: Optional[str]

class ChatOptions(BaseModel):
    enableSearch: Optional[bool] = False
    enableThinking: Optional[bool] = False
    temperature: Optional[float] = 1.0
    maxTokens: Optional[int] = None

class ChatRequest(BaseModel):
    modelId: str
    messages: List[Message]
    message: str
    attachments: List[Attachment] = []
    options: ChatOptions
    apiKey: str
```

### 响应模型

```python
class StreamUpdate(BaseModel):
    text: str
    chunk_type: Optional[str] = "content"
    usage: Optional[dict] = None
    groundingMetadata: Optional[dict] = None

class ModelConfig(BaseModel):
    id: str
    name: str
    description: str
    capabilities: dict
    baseModelId: str
```

## Error Handling

### 错误类型映射

```python
from app.services.base import (
    APIKeyError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError
)

ERROR_STATUS_MAP = {
    APIKeyError: 401,
    RateLimitError: 429,
    ModelNotFoundError: 404,
    InvalidRequestError: 400
}

@router.post("/api/chat/tongyi")
async def chat_tongyi(request: ChatRequest):
    try:
        # ... 业务逻辑
    except APIKeyError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ModelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 错误响应格式

```json
{
  "detail": "错误描述",
  "error_code": "DashScope 错误码（如果有）",
  "status_code": 401
}
```

## Testing Strategy

### 1. 单元测试

**测试内容**:
- 消息格式转换逻辑
- 响应格式转换逻辑
- 模型配置转换逻辑
- 错误处理逻辑

**工具**: pytest

**示例**:
```python
def test_convert_messages():
    history = [
        Message(role="user", content="你好"),
        Message(role="model", content="你好！有什么可以帮助你的吗？")
    ]
    current_message = "介绍一下你自己"
    
    result = convert_messages(history, current_message)
    
    assert len(result) == 3
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"
    assert result[2]["content"] == "介绍一下你自己"
```

### 2. 集成测试

**测试内容**:
- 聊天 API 端到端测试
- 模型列表 API 测试
- 流式响应测试
- 错误处理测试

**工具**: pytest + httpx.AsyncClient

**示例**:
```python
@pytest.mark.asyncio
async def test_chat_api():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/tongyi",
            json={
                "modelId": "qwen-turbo",
                "messages": [],
                "message": "你好",
                "attachments": [],
                "options": {"enableSearch": False},
                "apiKey": "test-api-key"
            }
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
```

### 3. 性能测试

**测试内容**:
- 并发请求测试（100 并发）
- 流式响应延迟测试
- 缓存效果测试

**工具**: locust

## Security Considerations

### 1. API Key 保护

**措施**:
- API Key 从请求体中提取，不在 URL 中传递
- 不在日志中记录完整 API Key（只记录前 8 位）
- 不在错误响应中暴露 API Key

### 2. 输入验证

**措施**:
- 使用 Pydantic 验证请求参数
- 限制消息长度（最大 10000 字符）
- 限制消息数量（最大 100 条）

### 3. 速率限制

**措施**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/chat/tongyi")
@limiter.limit("60/minute")
async def chat_tongyi(request: ChatRequest):
    # ...
```

## Performance Optimization

### 1. 连接池

**优化**:
```python
# qwen_native.py 已实现连接池
# 无需额外配置
```

### 2. 缓存

**优化**:
```python
# 模型列表缓存（1 小时）
@router.get("/api/models/tongyi")
async def get_tongyi_models(apiKey: str):
    cache_key = f"tongyi_models:{apiKey[:8]}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # ... 获取模型列表
    
    await redis.setex(cache_key, 3600, json.dumps(models))
    return {"models": models}
```

### 3. 异步 I/O

**优化**:
- 使用 `async/await` 处理所有 I/O 操作
- 使用 `qwen_native.py` 的异步方法

## Deployment Considerations

### 1. 环境变量

**配置**:
```bash
# 无需额外环境变量
# API Key 由前端在请求中提供
```

### 2. 日志配置

**配置**:
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 记录请求信息
logger.info(f"[Tongyi Chat] model={model_id}, search={enable_search}, thinking={enable_thinking}")
logger.info(f"[Tongyi Chat] usage: prompt={prompt_tokens}, completion={completion_tokens}")
```

### 3. 监控指标

**指标**:
- 请求总数（按模型分类）
- 请求成功率
- 平均响应时间
- Token 使用量
- 错误率（按错误类型分类）

## Future Enhancements

### 1. 数据库集成

**场景**: 从数据库读取用户的 API Key

**实现**:
```python
@router.post("/api/chat/tongyi")
async def chat_tongyi(request: ChatRequest, user_id: str = Depends(get_current_user)):
    # 从数据库读取 API Key
    api_key = await get_user_api_key(user_id, provider="tongyi")
    
    provider = QwenNativeProvider(api_key=api_key)
    # ...
```

### 2. 请求队列

**场景**: 处理高并发请求

**实现**:
```python
# 使用 Celery 或 RQ 实现异步任务队列
@router.post("/api/chat/tongyi")
async def chat_tongyi(request: ChatRequest):
    task_id = await queue.enqueue(process_chat, request)
    return {"task_id": task_id}
```

### 3. 多模型支持

**场景**: 支持其他 AI 提供商（OpenAI、Anthropic）

**实现**:
```python
# 统一接口
@router.post("/api/chat/{provider}")
async def chat(provider: str, request: ChatRequest):
    if provider == "tongyi":
        provider_instance = QwenNativeProvider(...)
    elif provider == "openai":
        provider_instance = OpenAIProvider(...)
    # ...
```
