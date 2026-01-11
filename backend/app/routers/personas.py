"""
角色管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from ..core.database import SessionLocal
from ..models.db_models import Persona as DBPersona
from ..core.user_context import require_user_id
from ..core.user_scoped_query import UserScopedQuery

router = APIRouter(prefix="/api", tags=["personas"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 角色管理 ====================

@router.get("/personas")
async def get_personas(request: Request, db: Session = Depends(get_db)):
    """获取所有角色"""
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    
    personas = user_query.get_all(DBPersona)
    
    # 如果数据库为空，返回空列表
    if not personas:
        return []
    
    return [persona.to_dict() for persona in personas]


@router.post("/personas")
async def save_personas(personas_data: List[dict], request: Request, db: Session = Depends(get_db)):
    """保存所有角色（批量更新）"""
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    
    try:
        # 删除当前用户的所有现有角色
        user_query.query(DBPersona).delete()
        
        # 添加新角色
        for persona_data in personas_data:
            persona = DBPersona(
                id=persona_data.get("id"),
                user_id=user_id,
                name=persona_data.get("name"),
                description=persona_data.get("description"),
                system_prompt=persona_data.get("systemPrompt"),
                icon=persona_data.get("icon"),
                category=persona_data.get("category"),
                created_at=persona_data.get("createdAt"),
                updated_at=persona_data.get("updatedAt")
            )
            db.add(persona)
        
        db.commit()
        return {"success": True, "count": len(personas_data)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
