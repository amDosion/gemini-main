---
name: backend-router
description: |
  创建和修改 FastAPI 后端路由。适用于：
  - 创建新的 API 端点
  - 添加新的路由模块
  - 修改现有 API 功能
  - 添加认证和权限控制
---

# FastAPI 路由开发技能

## 适用场景

当用户请求以下任务时，使用此技能：
- 创建新的 API 端点
- 添加新的路由模块
- 修改现有 API 功能
- 添加认证和权限控制

## 项目结构

```
backend/app/routers/
├── registry.py         # 统一路由注册
├── auth/               # 认证路由
│   └── auth.py         # 登录、注册、刷新令牌
├── core/               # 核心业务路由
│   ├── chat.py         # 统一聊天 API
│   ├── modes.py        # 统一模式 API
│   └── attachments.py  # 附件处理
├── system/             # 系统管理路由
│   ├── health.py       # 健康检查
│   └── metrics.py      # 指标收集
├── tools/              # 工具路由
│   ├── browse.py       # 网页浏览
│   ├── pdf.py          # PDF 处理
│   └── code_execution.py
├── ai/                 # AI 功能路由
│   ├── embedding.py    # 向量嵌入
│   ├── research.py     # 深度研究
│   └── multi_agent.py  # 多代理
├── models/             # 模型管理路由
│   ├── models.py       # 模型列表
│   └── providers.py    # 提供商管理
├── user/               # 用户路由
│   ├── profiles.py     # 配置管理
│   ├── sessions.py     # 会话管理
│   └── personas.py     # 角色管理
└── storage/            # 存储路由
    └── storage.py      # 文件存储
```

## 路由模板

### 基础路由模块

```python
# routers/xxx/xxx.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from ...core.dependencies import require_current_user, get_current_user_optional
from ...core.database import get_db
from ...services.common.provider_factory import ProviderFactory
from ...core.credential_manager import get_provider_credentials
from ...core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/xxx", tags=["xxx"])


# 请求模型
class XxxRequest(BaseModel):
    """请求模型"""
    message: str = Field(..., description="消息内容")
    modelId: str = Field(..., description="模型 ID")
    options: Optional[dict] = Field(default_factory=dict)

    class Config:
        extra = "allow"


# 响应模型
class XxxResponse(BaseModel):
    """响应模型"""
    content: str
    data: Optional[dict] = None

    class Config:
        populate_by_name = True


# GET 端点
@router.get("/")
async def list_xxx(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取列表"""
    # 所有查询必须加 user_id 过滤
    items = db.query(XxxModel).filter(
        XxxModel.user_id == user_id
    ).all()
    return [item.to_dict() for item in items]


# POST 端点（需要认证）
@router.post("/", response_model=XxxResponse)
async def create_xxx(
    request: XxxRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """创建新项"""
    logger.info(f"[API] Creating xxx for user {user_id}")

    # 获取凭证（自动解密）
    api_key, base_url = await get_provider_credentials(
        provider="gemini",
        db=db,
        user_id=user_id
    )

    # 创建服务实例
    service = ProviderFactory.create(
        provider="gemini",
        api_key=api_key,
        api_url=base_url,
        user_id=user_id,
        db=db
    )

    # 执行业务逻辑
    result = await service.process(request.dict())

    return XxxResponse(
        content=result["content"],
        data=result.get("data")
    )


# PUT 端点
@router.put("/{item_id}")
async def update_xxx(
    item_id: str,
    request: XxxRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """更新项"""
    item = db.query(XxxModel).filter(
        XxxModel.id == item_id,
        XxxModel.user_id == user_id  # 权限检查
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )

    # 更新字段
    for key, value in request.dict(exclude_unset=True).items():
        setattr(item, key, value)

    db.commit()
    return item.to_dict()


# DELETE 端点
@router.delete("/{item_id}")
async def delete_xxx(
    item_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """删除项"""
    item = db.query(XxxModel).filter(
        XxxModel.id == item_id,
        XxxModel.user_id == user_id
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )

    db.delete(item)
    db.commit()
    return {"success": True}
```

### 流式响应路由

```python
from fastapi.responses import StreamingResponse
import json

@router.post("/{provider}/chat")
async def chat_with_provider(
    provider: str,
    request: ChatRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """流式聊天"""
    api_key, base_url = await get_provider_credentials(
        provider=provider,
        db=db,
        user_id=user_id
    )

    service = ProviderFactory.create(
        provider=provider,
        api_key=api_key,
        api_url=base_url,
        user_id=user_id,
        db=db
    )

    if request.stream:
        return StreamingResponse(
            stream_response(service, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        result = await service.chat(
            messages=request.messages,
            model=request.modelId,
            options=request.options
        )
        return result


async def stream_response(service, request):
    """流式响应生成器"""
    try:
        async for chunk in service.chat_stream(
            messages=request.messages,
            model=request.modelId,
            options=request.options
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"[ERROR] Stream failed: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
```

### 在 registry.py 中注册

```python
# routers/registry.py
from .xxx.xxx import router as xxx_router

def register_routes(app: FastAPI):
    """注册所有路由"""
    # ... 其他路由
    app.include_router(xxx_router)
```

## 认证模式

### 强制认证

```python
@router.get("/protected")
async def protected_endpoint(
    user_id: str = Depends(require_current_user)
):
    """必须登录才能访问"""
    return {"user_id": user_id}
```

### 可选认证

```python
@router.get("/optional")
async def optional_endpoint(
    user_id: Optional[str] = Depends(get_current_user_optional)
):
    """登录用户获得更多功能"""
    if user_id:
        return {"authenticated": True, "user_id": user_id}
    return {"authenticated": False}
```

## 错误处理

```python
from fastapi import HTTPException, status

# 标准错误
raise HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Invalid request"
)

# 认证错误
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials"
)

# 权限错误
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Permission denied"
)

# 资源不存在
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Resource not found"
)
```

## 开发步骤

1. **选择路由目录**：根据功能选择合适的子目录
2. **创建路由文件**：使用模板创建新文件
3. **定义 Pydantic 模型**：请求和响应模型
4. **实现端点**：添加认证、业务逻辑
5. **注册路由**：在 registry.py 中添加
6. **测试接口**：使用 FastAPI 文档测试

## 注意事项

- 所有需要认证的端点使用 `Depends(require_current_user)`
- 所有数据库查询必须加 `user_id` 过滤
- API Key 在 `credential_manager` 统一解密
- 使用 Pydantic 模型验证请求/响应
- 流式响应使用 `StreamingResponse`
- 敏感信息不出现在日志中
