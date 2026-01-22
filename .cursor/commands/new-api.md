# 创建新的 API 端点

根据用户描述创建一个新的 FastAPI 路由端点。

## 执行步骤

1. **确定路由位置**
   - 认证相关 → `backend/app/routers/auth/`
   - 核心业务 → `backend/app/routers/core/`
   - 系统管理 → `backend/app/routers/system/`
   - 工具功能 → `backend/app/routers/tools/`
   - AI 功能 → `backend/app/routers/ai/`
   - 用户管理 → `backend/app/routers/user/`
   - 存储相关 → `backend/app/routers/storage/`

2. **创建路由文件**
   使用以下模板：

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from ...core.dependencies import require_current_user
from ...core.database import get_db
from ...core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/[endpoint]", tags=["[tag]"])


# 请求模型
class [Name]Request(BaseModel):
    """请求模型"""
    field1: str = Field(..., description="字段描述")
    field2: Optional[str] = Field(default=None)

    class Config:
        extra = "allow"


# 响应模型
class [Name]Response(BaseModel):
    """响应模型"""
    id: str
    data: dict

    class Config:
        populate_by_name = True


@router.get("/")
async def list_items(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取列表"""
    # 必须加 user_id 过滤
    items = db.query(Model).filter(
        Model.user_id == user_id
    ).all()
    return [item.to_dict() for item in items]


@router.post("/", response_model=[Name]Response)
async def create_item(
    request: [Name]Request,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """创建项目"""
    logger.info(f"[API] Creating item for user {user_id}")
    # 实现创建逻辑
    return [Name]Response(id="...", data={})


@router.put("/{item_id}")
async def update_item(
    item_id: str,
    request: [Name]Request,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """更新项目"""
    item = db.query(Model).filter(
        Model.id == item_id,
        Model.user_id == user_id  # 权限检查
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    # 实现更新逻辑
    return item.to_dict()


@router.delete("/{item_id}")
async def delete_item(
    item_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """删除项目"""
    item = db.query(Model).filter(
        Model.id == item_id,
        Model.user_id == user_id
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

3. **在 registry.py 中注册**
   ```python
   from .xxx.xxx import router as xxx_router
   app.include_router(xxx_router)
   ```

## 规范要求

- 使用 `Depends(require_current_user)` 进行认证
- 所有查询必须加 `user_id` 过滤
- 使用 Pydantic 模型验证请求/响应
- 响应使用 camelCase 格式
- 添加适当的日志记录

## 使用示例

```
/new-api 创建一个工作流模板管理的 CRUD API，支持创建、获取、更新、删除模板
```
