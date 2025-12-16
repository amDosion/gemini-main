"""
角色管理路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..core.database import SessionLocal
from ..models.db_models import Persona as DBPersona

router = APIRouter(prefix="/api", tags=["personas"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 角色管理 ====================

@router.get("/personas")
async def get_personas(db: Session = Depends(get_db)):
    """获取所有角色"""
    personas = db.query(DBPersona).all()
    
    # 如果数据库为空，返回默认角色
    if not personas:
        return []
    
    return [persona.to_dict() for persona in personas]


@router.post("/personas")
async def save_personas(personas_data: List[dict], db: Session = Depends(get_db)):
    """保存所有角色（批量更新）"""
    # 删除所有现有角色
    db.query(DBPersona).delete()
    
    # 添加新角色
    for persona_data in personas_data:
        persona = DBPersona(
            id=persona_data.get("id"),
            name=persona_data.get("name"),
            description=persona_data.get("description"),
            system_prompt=persona_data.get("systemPrompt"),
            icon=persona_data.get("icon"),
            category=persona_data.get("category")
        )
        db.add(persona)
    
    db.commit()
    return {"success": True, "count": len(personas_data)}
