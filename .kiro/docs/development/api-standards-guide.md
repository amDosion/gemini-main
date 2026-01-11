---
inclusion: fileMatch
fileMatchPattern: "backend/app/routers/**/*.py"
---

# API 设计规范

## RESTful API 原则

### 端点命名

#### 资源命名
- **使用复数名词**：`/api/sessions`, `/api/models`, `/api/personas`
- **使用小写和连字符**：`/api/chat-sessions`（避免下划线）
- **避免动词**：使用 HTTP 方法表示操作

✅ **好的示例**：
```
GET    /api/sessions          # 获取会话列表
POST   /api/sessions          # 创建新会话
GET    /api/sessions/:id      # 获取单个会话
PUT    /api/sessions/:id      # 更新会话
DELETE /api/sessions/:id      # 删除会话
```

❌ **不好的示例**：
```
GET /api/getSessions
POST /api/createSession
POST /api/session/delete/:id
```

#### 子资源命名
```
GET /api/sessions/:id/messages        # 获取会话的消息
POST /api/sessions/:id/messages       # 在会话中添加消息
GET /api/profiles/:id/api-keys        # 获取配置的 API 密钥
```

### HTTP 方法

| 方法 | 用途 | 请求体 | 幂等性 | 示例 |
|------|------|--------|--------|------|
| GET | 查询资源 | 无 | ✅ | GET /api/models |
| POST | 创建资源 | 有 | ❌ | POST /api/sessions |
| PUT | 完整更新 | 有 | ✅ | PUT /api/sessions/:id |
| PATCH | 部分更新 | 有 | ✅ | PATCH /api/sessions/:id |
| DELETE | 删除资源 | 无 | ✅ | DELETE /api/sessions/:id |

### HTTP 状态码

#### 成功响应（2xx）
- **200 OK** - 成功查询或更新
- **201 Created** - 成功创建资源（返回资源 URI）
- **204 No Content** - 成功但无返回内容（如 DELETE）

#### 客户端错误（4xx）
- **400 Bad Request** - 请求参数错误
- **401 Unauthorized** - 未认证（缺少或无效 token）
- **403 Forbidden** - 无权限访问
- **404 Not Found** - 资源不存在
- **409 Conflict** - 资源冲突（如重复创建）
- **422 Unprocessable Entity** - 语义错误（参数验证失败）
- **429 Too Many Requests** - 速率限制

#### 服务器错误（5xx）
- **500 Internal Server Error** - 服务器内部错误
- **502 Bad Gateway** - 上游服务错误
- **503 Service Unavailable** - 服务不可用
- **504 Gateway Timeout** - 上游服务超时

---

## 请求规范

### 认证
使用 Bearer Token（JWT）：

```python
@router.post("/api/chat")
async def send_message(
    request: ChatRequest,
    user_id: int = Depends(require_user_id)  # 自动提取和验证 JWT
):
    ...
```

请求头示例：
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 请求体格式

#### JSON 格式（默认）
```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., min_length=1, description="用户消息")
    model: str | None = Field(None, description="指定模型")
    attachments: list[str] | None = Field(None, description="附件列表")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "解释量子计算原理",
                "model": "gemini-2.0-flash-exp",
                "attachments": []
            }
        }
```

#### 文件上传（multipart/form-data）
```python
@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Depends(require_user_id)
):
    ...
```

### 查询参数
```python
@router.get("/api/models")
async def get_models(
    provider: str | None = Query(None, description="筛选提供商"),
    mode: str | None = Query(None, description="筛选模式"),
    limit: int = Query(100, ge=1, le=500, description="返回数量")
):
    ...
```

---

## 响应规范

### 成功响应

#### 单个资源
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My Chat Session",
  "created_at": "2026-01-09T10:30:00Z",
  "updated_at": "2026-01-09T12:00:00Z"
}
```

#### 资源列表
```json
{
  "items": [
    { "id": "1", "name": "Session 1" },
    { "id": "2", "name": "Session 2" }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

#### 创建响应（201）
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Session created successfully",
  "created_at": "2026-01-09T10:30:00Z"
}
```

### 错误响应

#### 统一错误格式
```python
class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误消息")
    error_code: str = Field(..., description="错误码")
    status_code: int = Field(..., description="HTTP 状态码")
    details: dict[str, Any] | None = Field(None, description="详细信息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

#### 示例错误响应
```json
{
  "error": "Invalid API key for Google provider",
  "error_code": "AUTHENTICATION_ERROR",
  "status_code": 401,
  "details": {
    "provider": "google",
    "model": "gemini-2.0-flash-exp"
  },
  "timestamp": "2026-01-09T10:30:00Z"
}
```

#### 验证错误（422）
```json
{
  "error": "Validation failed",
  "error_code": "VALIDATION_ERROR",
  "status_code": 422,
  "details": {
    "errors": [
      {
        "field": "message",
        "message": "Field required",
        "type": "missing"
      },
      {
        "field": "model",
        "message": "String should have at least 1 character",
        "type": "string_too_short"
      }
    ]
  },
  "timestamp": "2026-01-09T10:30:00Z"
}
```

### 错误码定义

```python
# backend/app/core/error_codes.py
class ErrorCode:
    """标准错误码"""

    # 认证错误（1xxx）
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # 授权错误（2xxx）
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_QUOTA = "INSUFFICIENT_QUOTA"

    # 验证错误（3xxx）
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # 资源错误（4xxx）
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"

    # AI 提供商错误（5xxx）
    PROVIDER_API_ERROR = "PROVIDER_API_ERROR"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"

    # 文件错误（6xxx）
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_UPLOAD_FAILED = "FILE_UPLOAD_FAILED"

    # 系统错误（9xxx）
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
```

---

## 流式响应

### SSE（Server-Sent Events）
用于聊天流式响应：

```python
@router.post("/api/chat/stream")
async def stream_chat(
    request: ChatRequest,
    user_id: int = Depends(require_user_id)
):
    """流式聊天"""

    async def generate():
        try:
            # 流式生成内容
            async for chunk in provider.stream_chat(request.message):
                # SSE 格式：data: {json}\n\n
                yield f"data: {json.dumps(chunk)}\n\n"

            # 结束标记
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            # 错误流式返回
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )
```

### 流式数据格式

#### 内容块
```json
{
  "type": "content",
  "text": "部分响应内容",
  "index": 0
}
```

#### 工具调用
```json
{
  "type": "tool_call",
  "tool": "web_search",
  "arguments": {"query": "量子计算"}
}
```

#### 思考过程
```json
{
  "type": "thinking",
  "content": "AI 思考过程...",
  "done": false
}
```

#### 完成标记
```json
{
  "type": "done",
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 300,
    "total_tokens": 450
  }
}
```

#### 错误
```json
{
  "type": "error",
  "error": "Rate limit exceeded",
  "error_code": "PROVIDER_RATE_LIMIT"
}
```

---

## 分页

### 查询参数
```python
@router.get("/api/sessions")
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: int = Depends(require_user_id)
):
    offset = (page - 1) * page_size
    sessions = await db.query(...).limit(page_size).offset(offset)
    total = await db.query(...).count()

    return {
        "items": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
```

### 响应格式
```json
{
  "items": [...],
  "total": 150,
  "page": 2,
  "page_size": 20,
  "total_pages": 8
}
```

---

## 版本控制

### URL 版本
```python
router = APIRouter(prefix="/api/v1/chat")  # v1 版本
router = APIRouter(prefix="/api/v2/chat")  # v2 版本
```

### 请求头版本（推荐）
```python
from fastapi import Header

@router.get("/api/models")
async def get_models(
    api_version: str = Header("1", alias="X-API-Version")
):
    if api_version == "2":
        # v2 逻辑
    else:
        # v1 逻辑
```

---

## 速率限制

### 响应头
```python
from fastapi import Response

@router.post("/api/chat")
async def send_message(
    request: ChatRequest,
    response: Response
):
    # 添加速率限制头
    response.headers["X-RateLimit-Limit"] = "100"      # 限制
    response.headers["X-RateLimit-Remaining"] = "95"  # 剩余
    response.headers["X-RateLimit-Reset"] = "1704790800"  # 重置时间

    return {...}
```

### 超限响应（429）
```json
{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "status_code": 429,
  "details": {
    "limit": 100,
    "remaining": 0,
    "reset_at": "2026-01-09T11:00:00Z"
  },
  "timestamp": "2026-01-09T10:30:00Z"
}
```

---

## CORS 配置

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:21573",  # 开发环境
        "https://app.example.com"  # 生产环境
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## OpenAPI 文档

### 路由文档
```python
@router.post(
    "/api/chat",
    summary="发送聊天消息",
    description="向 AI 模型发送消息并获取响应",
    response_model=ChatResponse,
    responses={
        200: {"description": "成功响应"},
        401: {"description": "未认证"},
        422: {"description": "参数验证失败"},
        500: {"description": "服务器错误"}
    },
    tags=["Chat"]
)
async def send_message(
    request: ChatRequest,
    user_id: int = Depends(require_user_id)
):
    """
    发送聊天消息

    - **session_id**: 会话 ID
    - **message**: 用户消息内容
    - **model**: 可选的模型 ID
    - **attachments**: 可选的附件列表
    """
    ...
```

### 模型文档
```python
class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str = Field(
        ...,
        description="会话 ID",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户消息内容",
        example="解释量子计算的原理"
    )
    model: str | None = Field(
        None,
        description="指定使用的模型 ID",
        example="gemini-2.0-flash-exp"
    )
```

---

## 最佳实践

### 1. 使用 Pydantic 模型
- ✅ 自动参数验证
- ✅ 自动生成 OpenAPI 文档
- ✅ 类型安全

### 2. 依赖注入认证
```python
user_id: int = Depends(require_user_id)  # 统一认证
```

### 3. 异常处理中间件
```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "error_code": "HTTP_ERROR",
            "status_code": exc.status_code
        }
    )
```

### 4. 请求日志
```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info(f"{request.method} {request.url} - {response.status_code} - {duration:.3f}s")
    return response
```

### 5. 统一响应格式
所有 API 使用统一的响应格式，便于前端处理。

---

**更新日期**：2026-01-09
**版本**：v1.0.0
