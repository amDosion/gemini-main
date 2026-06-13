"""
角色管理路由
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field, JsonValue
from sqlalchemy.orm import Session
from typing import Dict, List
import logging

from ...core.database import SessionLocal, get_db
from ...models.db_models import Persona as DBPersona
from ...core.dependencies import require_current_user
from ...core.user_scoped_query import UserScopedQuery
from ...middleware.case_conversion_middleware import case_conversion_options
from ...services.common.persona_init_service import DEFAULT_PERSONAS, create_default_personas
from ...utils.log_sanitization import summarize_text_for_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["personas"])
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"


class ResetPersonasResponse(BaseModel):
    success: bool
    count: int = Field(ge=0, le=10_000)
    message: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)


class SavePersonasResponse(BaseModel):
    success: bool
    count: int = Field(ge=0, le=10_000)


class PersonaResponse(BaseModel):
    id: str = Field(max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    user_id: str = Field(max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    name: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    description: str = Field(max_length=4096, pattern=r"^[\s\S]*$")
    system_prompt: str = Field(max_length=100_000, pattern=r"^[\s\S]*$")
    icon: str = Field(max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)
    category: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)


# ==================== 角色管理 ====================

@router.get("/personas", response_model=List[PersonaResponse])
@case_conversion_options(always_convert_response=True)
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


@router.post("/personas", response_model=SavePersonasResponse)
async def save_personas(
    personas_data: List[Dict[str, JsonValue]] = Body(..., max_length=10_000),
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

            # 兼容 case-conversion 中间件后的 snake_case 与直传 camelCase
            system_prompt = persona_data.get("system_prompt")
            if system_prompt is None:
                system_prompt = persona_data.get("systemPrompt")
            
            persona = DBPersona(
                id=persona_id,
                user_id=user_id,
                name=persona_data.get("name"),
                description=persona_data.get("description"),
                system_prompt=system_prompt,
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
        logger.error(
            "[Personas] save personas failed: %s",
            summarize_text_for_log(e, label="error"),
        )
        raise HTTPException(status_code=500, detail="Failed to save personas")


@router.post("/personas/reset", response_model=ResetPersonasResponse)
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
        logger.error(
            "[Personas] reset personas failed: %s",
            summarize_text_for_log(e, label="error"),
        )
        raise HTTPException(status_code=500, detail="Failed to reset personas")
