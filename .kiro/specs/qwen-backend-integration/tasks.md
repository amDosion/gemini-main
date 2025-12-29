# Implementation Plan

## 任务概览

本任务计划定义了通义千问后端集成的实现任务，目标是使用 `qwen_native.py` 实现后端 API。

**总体策略**：
- 使用 `qwen_native.py` 调用 DashScope API
- 提供与前端兼容的 API 接口
- 支持渐进式迁移
- 保持最小化前端改动

**任务分组**：
1. 后端 API 实现（聊天、模型列表）
2. 格式转换和适配
3. 测试和验证
4. 前端适配（后续任务）

---

## 任务列表

- [x] 1. 后端聊天 API 实现
  - [x] 1.1 创建聊天路由
    - 类型：backend
    - Requirements: 1.1, 1.3, 1.4
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：实现 `POST /api/chat/tongyi` 聊天端点
    - 依赖：无
    - 预计时间：2 小时
  
  - [x] 1.2 实现消息格式转换
    - 类型：backend
    - Requirements: 1.3
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：将前端 Message 格式转换为 qwen_native.py 格式
    - 依赖：1.1
    - 预计时间：1 小时
  
  - [x] 1.3 集成 qwen_native.py 流式聊天
    - 类型：backend
    - Requirements: 1.1, 1.3
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：调用 `QwenNativeProvider.stream_chat()` 方法
    - 依赖：1.1, 1.2
    - 预计时间：2 小时
  
  - [x] 1.4 实现响应格式转换
    - 类型：backend
    - Requirements: 1.4
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：将 qwen_native.py StreamChunk 转换为前端 StreamUpdate 格式
    - 依赖：1.3
    - 预计时间：1.5 小时
  
  - [x] 1.5 实现搜索结果转换
    - 类型：backend
    - Requirements: 1.4
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：将 DashScope 搜索结果转换为 groundingMetadata 格式
    - 依赖：1.4
    - 预计时间：1 小时
  
  - [x] 1.6 实现错误处理
    - 类型：backend
    - Requirements: 1.5
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：捕获并转换 qwen_native.py 异常为 HTTP 错误
    - 依赖：1.3
    - 预计时间：1 小时
  
  - [x] 1.7 实现日志记录
    - 类型：backend
    - Requirements: 1.8
    - 文件：`backend/app/api/routes/tongyi_chat.py`
    - 描述：记录请求信息、模型、token 使用量
    - 依赖：1.3
    - 预计时间：0.5 小时

- [x] 2. 后端模型列表 API 实现
  - [x] 2.1 创建模型列表路由
    - 类型：backend
    - Requirements: 1.2
    - 文件：`backend/app/api/routes/tongyi_models.py`
    - 描述：实现 `GET /api/models/tongyi` 模型列表端点
    - 依赖：无
    - 预计时间：1 小时
  
  - [x] 2.2 集成 qwen_native.py 模型列表
    - 类型：backend
    - Requirements: 1.2
    - 文件：`backend/app/api/routes/tongyi_models.py`
    - 描述：调用 `QwenNativeProvider.get_available_models()` 方法
    - 依赖：2.1
    - 预计时间：1 小时
  
  - [x] 2.3 实现模型配置转换
    - 类型：backend
    - Requirements: 1.2, 1.4
    - 文件：`backend/app/api/routes/tongyi_models.py`
    - 描述：将模型 ID 列表转换为 ModelConfig 格式
    - 依赖：2.2
    - 预计时间：2 小时
  
  - [x] 2.4 实现模型元数据注册表
    - 类型：backend
    - Requirements: 1.2
    - 文件：`backend/app/api/routes/tongyi_models.py`
    - 描述：创建与前端 models.ts 一致的模型元数据
    - 依赖：2.3
    - 预计时间：1.5 小时
  
  - [x] 2.5 实现缓存机制
    - 类型：backend
    - Requirements: 1.7
    - 文件：`backend/app/routers/tongyi_models.py`
    - 描述：使用内存缓存模型列表（TTL: 1 小时）
    - 依赖：2.3
    - 预计时间：1 小时

- [x] 3. 路由注册和配置
  - [x] 3.1 注册聊天路由
    - 类型：backend
    - Requirements: 所有
    - 文件：`backend/app/main.py`
    - 描述：将聊天路由注册到 FastAPI 应用
    - 依赖：1.7
    - 预计时间：0.5 小时
  
  - [x] 3.2 注册模型列表路由
    - 类型：backend
    - Requirements: 所有
    - 文件：`backend/app/main.py`
    - 描述：将模型列表路由注册到 FastAPI 应用
    - 依赖：2.5
    - 预计时间：0.5 小时
  
  - [x] 3.3 配置 CORS
    - 类型：backend
    - Requirements: 所有
    - 文件：`backend/app/main.py`
    - 描述：配置 CORS 允许前端域名（已有配置，验证通过）
    - 依赖：3.1, 3.2
    - 预计时间：0.5 小时

- [ ] 4. 测试和验证
  - [ ] 4.1 编写消息转换单元测试
    - 类型：backend
    - Requirements: 1.3
    - 文件：`backend/tests/test_tongyi_chat.py`
    - 描述：测试消息格式转换逻辑
    - 依赖：1.2
    - 预计时间：1 小时
  
  - [ ] 4.2 编写响应转换单元测试
    - 类型：backend
    - Requirements: 1.4
    - 文件：`backend/tests/test_tongyi_chat.py`
    - 描述：测试响应格式转换逻辑
    - 依赖：1.4
    - 预计时间：1 小时
  
  - [ ] 4.3 编写模型配置转换单元测试
    - 类型：backend
    - Requirements: 1.2
    - 文件：`backend/tests/test_tongyi_models.py`
    - 描述：测试模型配置转换逻辑
    - 依赖：2.3
    - 预计时间：1 小时
  
  - [ ] 4.4 编写聊天 API 集成测试
    - 类型：backend
    - Requirements: 1.1, 1.3, 1.4
    - 文件：`backend/tests/test_tongyi_integration.py`
    - 描述：测试聊天 API 端到端流程
    - 依赖：3.3
    - 预计时间：2 小时
  
  - [ ] 4.5 编写模型列表 API 集成测试
    - 类型：backend
    - Requirements: 1.2
    - 文件：`backend/tests/test_tongyi_integration.py`
    - 描述：测试模型列表 API
    - 依赖：3.3
    - 预计时间：1 小时
  
  - [ ] 4.6 编写流式响应测试
    - 类型：backend
    - Requirements: 1.3
    - 文件：`backend/tests/test_tongyi_streaming.py`
    - 描述：测试 SSE 流式响应
    - 依赖：3.3
    - 预计时间：2 小时
  
  - [ ] 4.7 手动测试后端 API
    - 类型：backend
    - Requirements: 所有
    - 描述：使用 Postman/curl 测试后端 API
    - 依赖：3.3
    - 预计时间：1 小时

- [x] 5. 文档和部署
  - [x] 5.1 更新 API 文档
    - 类型：documentation
    - Requirements: 所有
    - 文件：`docs/api/tongyi-backend.md`
    - 描述：记录后端 API 的使用方法
    - 依赖：3.3
    - 预计时间：1.5 小时
  
  - [x] 5.2 编写前端迁移指南
    - 类型：documentation
    - Requirements: 1.9
    - 文件：`docs/migration/tongyi-frontend.md`
    - 描述：指导前端如何迁移到后端 API
    - 依赖：3.3
    - 预计时间：1 小时

---

## 任务详细说明

### 1.1 创建聊天路由

**目标**：实现 `POST /api/chat/tongyi` 聊天端点

**实现要点**：
```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import json

router = APIRouter(prefix="/api/chat", tags=["tongyi-chat"])

class Message(BaseModel):
    role: str
    content: str
    isError: Optional[bool] = False

class ChatOptions(BaseModel):
    enableSearch: Optional[bool] = False
    enableThinking: Optional[bool] = False
    temperature: Optional[float] = 1.0

class ChatRequest(BaseModel):
    modelId: str
    messages: List[Message]
    message: str
    options: ChatOptions
    apiKey: str

@router.post("/tongyi")
async def chat_tongyi(request: ChatRequest):
    """
    通义千问聊天 API
    """
    try:
        # 1. 初始化 QwenNativeProvider
        from app.services.qwen_native import QwenNativeProvider
        
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
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**验收标准**：
- ✅ 能够接收 POST 请求
- ✅ 能够解析请求体（ChatRequest）
- ✅ 能够初始化 QwenNativeProvider
- ✅ 能够返回 SSE 流式响应

### 1.2 实现消息格式转换

**目标**：将前端 Message 格式转换为 qwen_native.py 格式

**实现要点**：
```python
def convert_messages(history: List[Message], current_message: str) -> List[dict]:
    """
    转换消息格式
    
    前端格式:
    {
      role: "user" | "model" | "system",
      content: str,
      isError: bool
    }
    
    qwen_native.py 格式:
    {
      "role": "user" | "assistant" | "system",
      "content": str
    }
    """
    messages = []
    
    # 转换历史消息
    for msg in history:
        # 跳过错误消息
        if msg.isError:
            continue
        
        # 跳过空消息
        if not msg.content:
            continue
        
        # 转换角色名称
        role = msg.role
        if role == "model":
            role = "assistant"
        
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

**验收标准**：
- ✅ 能够转换历史消息
- ✅ 能够跳过错误消息
- ✅ 能够跳过空消息
- ✅ 能够转换角色名称（model → assistant）
- ✅ 能够添加当前消息

### 1.4 实现响应格式转换

**目标**：将 qwen_native.py StreamChunk 转换为前端 StreamUpdate 格式

**实现要点**：
```python
def convert_to_stream_update(chunk: dict) -> dict:
    """
    转换响应格式
    
    qwen_native.py 格式:
    {
      "content": str,
      "chunk_type": "reasoning" | "content" | "done",
      "prompt_tokens": int,
      "completion_tokens": int,
      "total_tokens": int,
      "search_results": List[dict]
    }
    
    前端格式:
    {
      "text": str,
      "chunk_type": "reasoning" | "content" | "done",
      "usage": {...},
      "groundingMetadata": {...}
    }
    """
    result = {
        "text": chunk.get("content", ""),
        "chunk_type": chunk.get("chunk_type", "content")
    }
    
    # 添加 usage 信息（仅在 done chunk）
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

**验收标准**：
- ✅ 能够转换基本字段（content → text）
- ✅ 能够保留 chunk_type
- ✅ 能够转换 usage 信息
- ✅ 能够转换搜索结果为 groundingMetadata

### 2.3 实现模型配置转换

**目标**：将模型 ID 列表转换为 ModelConfig 格式

**实现要点**：
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
    "qwen-max": {
        "name": "Qwen Max",
        "description": "Alibaba's most capable large model. Excellent at complex reasoning.",
        "capabilities": {"vision": False, "reasoning": False, "coding": True, "search": True},
        "score": 100
    },
    # ... 其他模型
}

def convert_to_model_configs(model_ids: List[str]) -> List[dict]:
    """
    转换模型配置
    """
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
            # 默认配置（未知模型）
            lower_id = model_id.lower()
            models.append({
                "id": model_id,
                "name": model_id,
                "description": "DashScope Model",
                "capabilities": {
                    "vision": "vl" in lower_id or "image" in lower_id or "wanx" in lower_id,
                    "reasoning": "qwq" in lower_id or "thinking" in lower_id,
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

**验收标准**：
- ✅ 能够从注册表获取模型元数据
- ✅ 能够为未知模型生成默认配置
- ✅ 能够按 score 排序
- ✅ 能够返回与前端兼容的格式

---

## 任务依赖关系

```
1.1 创建聊天路由
 ├─ 1.2 实现消息格式转换
 │   └─ 1.3 集成 qwen_native.py 流式聊天
 │       ├─ 1.4 实现响应格式转换
 │       │   └─ 1.5 实现搜索结果转换
 │       ├─ 1.6 实现错误处理
 │       └─ 1.7 实现日志记录
 │           └─ 3.1 注册聊天路由

2.1 创建模型列表路由
 └─ 2.2 集成 qwen_native.py 模型列表
     └─ 2.3 实现模型配置转换
         ├─ 2.4 实现模型元数据注册表
         └─ 2.5 实现缓存机制
             └─ 3.2 注册模型列表路由

3.1 + 3.2 → 3.3 配置 CORS
 └─ 4.1-4.7 测试和验证
     └─ 5.1-5.2 文档和部署
```

---

## 预计总时间

- 后端聊天 API：9 小时
- 后端模型列表 API：6.5 小时
- 路由注册和配置：1.5 小时
- 测试：9 小时
- 文档：2.5 小时
- **总计**：28.5 小时

---

## 风险和缓解措施

### 风险 1：qwen_native.py 响应格式变化

**描述**：qwen_native.py 的响应格式可能与预期不一致

**缓解措施**：
- 编写详细的单元测试验证格式转换
- 添加日志记录实际响应格式
- 提供降级方案（返回原始响应）

### 风险 2：流式响应缓冲问题

**描述**：某些反向代理可能会缓冲流式响应

**缓解措施**：
- 在响应中添加 `X-Accel-Buffering: no` header
- 在 Nginx 配置中禁用缓冲
- 测试不同的反向代理配置

### 风险 3：前端兼容性问题

**描述**：后端 API 响应格式与前端期望不一致

**缓解措施**：
- 详细对比前端和后端的数据格式
- 编写集成测试验证端到端流程
- 提供前端适配示例代码

---

## 成功标准

### 功能完整性

- ✅ 后端聊天 API 正常工作
- ✅ 后端模型列表 API 正常工作
- ✅ 支持流式响应（SSE）
- ✅ 支持网页搜索功能
- ✅ 支持思考模式
- ✅ 响应格式与前端兼容

### 性能指标

- ✅ 首字节延迟 < 1 秒
- ✅ 流式响应实时转发
- ✅ 支持 100 并发请求
- ✅ 模型列表缓存命中率 > 90%

### 质量指标

- ✅ 单元测试覆盖率 > 80%
- ✅ 集成测试通过率 100%
- ✅ 无安全漏洞
- ✅ 无性能瓶颈

---

## 后续任务（前端适配）

- [x] 6. 前端适配
  - [x] 6.1 修改 DashScopeProvider 使用后端 API
    - 类型：frontend
    - 文件：`frontend/services/providers/tongyi/DashScopeProvider.ts`
    - 描述：使用相对路径 `/api/chat/tongyi` 和 `/api/models/tongyi`，由 Vite 代理转发
    - 完成时间：2025-12-28
  - [x] 6.2 清理环境变量配置
    - 类型：frontend
    - 文件：`.env.local`, `frontend/env.d.ts`
    - 描述：移除不再需要的 `VITE_BACKEND_URL` 环境变量
    - 完成时间：2025-12-28
  - [ ] 6.3 测试前端集成
  - [x] 6.4 移除前端的 DashScope 直接调用代码（视觉模型除外）
    - 完成时间：2025-12-28
    - 描述：视觉模型现在也使用后端 API，已移除 OpenAI 兼容层回退

- [x] 7. 视觉模型（qwen-vl-*）后端原生 API 支持
  - [x] 7.1 后端添加 MultiModalConversation 支持
    - 类型：backend
    - 文件：`backend/app/services/qwen_native.py`
    - 描述：添加 `_sync_multimodal_chat()` 和 `_sync_stream_multimodal_chat()` 方法
    - 完成时间：2025-12-28
  - [x] 7.2 后端聊天 API 支持图片附件
    - 类型：backend
    - 文件：`backend/app/routers/tongyi_chat.py`
    - 描述：添加 `Attachment` 模型和 `convert_multimodal_messages()` 函数
    - 完成时间：2025-12-28
  - [x] 7.3 前端移除视觉模型的 OpenAI 兼容层回退
    - 类型：frontend
    - 文件：`frontend/services/providers/tongyi/DashScopeProvider.ts`
    - 描述：视觉模型统一使用后端 API，传递 `attachments` 参数
    - 完成时间：2025-12-28

- [x] 8. 修复后端启动错误
  - [x] 8.1 修复 qwen_native.py 模块依赖问题
    - 类型：backend
    - 文件：`backend/app/services/qwen_native.py`
    - 描述：移除不存在的依赖（`native_sdk_base.py`、`AIProvider` 枚举、`..base` 模块），使其成为独立可用的模块
    - 问题原因：`qwen_native.py` 从另一个项目复制过来，但依赖的基类和枚举没有一起复制
    - 修复内容：
      1. 移除 `from models.ai_config.enums import AIProvider` 导入
      2. 移除 `from .native_sdk_base import NativeSDKBase` 导入
      3. 移除 `from ..base import AIServiceError` 导入
      4. 在文件内定义异常类（`AIServiceError`、`APIKeyError`、`RateLimitError`、`ModelNotFoundError`、`InvalidRequestError`）
      5. 移除 `NativeSDKBase` 继承，改为独立类
      6. 添加 `_handle_error()` 方法
      7. 添加 `stream_chat()` 异步方法
    - 完成时间：2025-12-28
  - [x] 8.2 修复路由文件的导入语句
    - 类型：backend
    - 文件：`backend/app/routers/tongyi_chat.py`、`backend/app/routers/tongyi_models.py`
    - 描述：将绝对导入改为相对导入（带回退）
    - 问题原因：使用 `from app.services.qwen_native import ...` 绝对导入，但其他路由文件使用相对导入
    - 修复内容：
      ```python
      # 原代码
      from app.services.qwen_native import QwenNativeProvider
      
      # 修改为（参考 tryon.py 的导入模式）
      try:
          from ..services.qwen_native import QwenNativeProvider
      except ImportError:
          try:
              from services.qwen_native import QwenNativeProvider
          except ImportError:
              from backend.app.services.qwen_native import QwenNativeProvider
      ```
    - 完成时间：2025-12-28

- [x] 9. Z-Image 模型支持
  - [x] 9.1 修复 Z-Image 路由问题
    - 类型：frontend
    - 文件：`frontend/services/providers/tongyi/api.ts`
    - 描述：在 `resolveDashUrl()` 函数中添加 Z-Image 模型检测，使用 `multimodal-generation/generation` 端点
    - 问题原因：Z-Image 模型（`z-image-turbo`、`z-image`、`z-image-omni-base`）错误地使用了 `text2image/image-synthesis` 端点
    - 修复内容：
      ```typescript
      // 添加 Z-Image 检测
      if (modelId?.startsWith('z-image')) {
          return `${root}/api/v1/services/aigc/multimodal-generation/generation`;
      }
      ```
    - 完成时间：2025-12-28
  - [x] 9.2 添加 Z-Image 请求格式支持
    - 类型：frontend
    - 文件：`frontend/services/providers/tongyi/image-gen.ts`
    - 描述：添加 `generateZImage()` 和 `submitZImageSync()` 函数，使用 `messages` 数组格式
    - 修复内容：
      1. 添加 `getZImageResolution()` 分辨率映射函数
      2. 添加 `generateZImage()` 专用生成函数
      3. 添加 `submitZImageSync()` 同步调用函数
      4. Z-Image 响应格式：`output.choices[0].message.content[{image: url}]`
    - 完成时间：2025-12-28
