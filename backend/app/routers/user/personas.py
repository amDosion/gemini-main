"""
角色管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import logging

from ...core.database import SessionLocal
from ...models.db_models import Persona as DBPersona
from ...core.dependencies import require_current_user
from ...core.user_scoped_query import UserScopedQuery
from ...services.common.persona_init_service import DEFAULT_PERSONAS, create_default_personas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["personas"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 角色管理 ====================

@router.get("/personas")
async def get_personas(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取所有角色"""
    user_query = UserScopedQuery(db, user_id)
    
    personas = user_query.get_all(DBPersona)
    
    # 如果数据库为空，返回空列表
    if not personas:
        return []
    
    return [persona.to_dict() for persona in personas]


@router.post("/personas")
async def save_personas(
    personas_data: List[dict],
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """保存所有角色（批量更新）"""
    import time
    user_query = UserScopedQuery(db, user_id)
    
    try:
        # 获取现有 Personas 的创建时间（用于保留原始创建时间）
        existing_personas = user_query.get_all(DBPersona)
        created_at_map = {p.id: p.created_at for p in existing_personas}
        
        # 删除当前用户的所有现有角色
        user_query.query(DBPersona).delete()
        
        current_timestamp = int(time.time() * 1000)  # 毫秒时间戳
        
        # 添加新角色
        for persona_data in personas_data:
            persona_id = persona_data.get("id")
            # 如果 Persona 已存在，保留原始创建时间；否则使用当前时间
            created_at = created_at_map.get(persona_id, current_timestamp)
            
            persona = DBPersona(
                id=persona_id,
                user_id=user_id,
                name=persona_data.get("name"),
                description=persona_data.get("description"),
                system_prompt=persona_data.get("systemPrompt"),
                icon=persona_data.get("icon"),
                category=persona_data.get("category"),
                created_at=created_at,
                updated_at=current_timestamp  # 总是更新为当前时间
            )
            db.add(persona)
        
        db.commit()
        return {"success": True, "count": len(personas_data)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@router.post("/personas/reset")
async def reset_personas(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    重置 Personas 为默认值
    
    删除用户的所有现有 Personas，然后重新创建默认 Personas。
    注意：这会删除用户的所有自定义 Personas！
    """
    user_query = UserScopedQuery(db, user_id)
    
    try:
        # 删除当前用户的所有现有 Personas
        deleted_count = user_query.query(DBPersona).delete()
        logger.info(f"[Personas] 用户 {user_id} 删除了 {deleted_count} 个现有 Personas")
        
        # 使用通用函数重新创建默认 Personas
        created_count = create_default_personas(user_id, db)
        
        return {
            "success": True,
            "count": created_count,
            "message": f"Reset to {created_count} default personas"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"[Personas] ❌ 重置 Personas 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset personas: {e}")
