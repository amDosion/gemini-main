"""
配置文件管理路由
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from ..core.database import SessionLocal
from ..models.db_models import ConfigProfile as DBConfigProfile, UserSettings
from ..core.user_context import require_user_id
from ..core.user_scoped_query import UserScopedQuery

router = APIRouter(prefix="/api", tags=["profiles"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ConfigProfilePayload(BaseModel):
    id: str
    name: Optional[str] = None
    providerId: Optional[str] = None
    apiKey: Optional[str] = None
    baseUrl: Optional[str] = None
    protocol: Optional[str] = None
    isProxy: Optional[bool] = None
    hiddenModels: Optional[List[str]] = None
    cachedModelCount: Optional[int] = None
    savedModels: Optional[List[dict]] = None  # 接收完整的 ModelConfig 对象数组
    createdAt: Optional[int] = None
    updatedAt: Optional[int] = None

    class Config:
        extra = "ignore"

# ==================== 配置文件管理 ====================

@router.get("/profiles")
async def get_profiles(request: Request, db: Session = Depends(get_db)):
    """获取所有配置文件"""
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    profiles = user_query.get_all(DBConfigProfile)
    return [profile.to_dict() for profile in profiles]


@router.post("/profiles")
async def create_or_update_profile(profile_data: ConfigProfilePayload, request: Request, db: Session = Depends(get_db)):
    """创建或更新配置文件"""
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    profile_id = profile_data.id

    if not profile_id:
        raise HTTPException(status_code=400, detail="Profile ID is required")

    profile = user_query.get(DBConfigProfile, profile_id)
    
    try:
        if profile:
            # 更新现有配置
            update_data = profile_data.dict(exclude_unset=True)
            if "name" in update_data:
                profile.name = update_data["name"]
            if "providerId" in update_data:
                profile.provider_id = update_data["providerId"]
            if "apiKey" in update_data:
                profile.api_key = update_data["apiKey"]
            if "baseUrl" in update_data:
                profile.base_url = update_data["baseUrl"]
            if "protocol" in update_data:
                profile.protocol = update_data["protocol"]
            if "isProxy" in update_data:
                profile.is_proxy = update_data["isProxy"]
            if "hiddenModels" in update_data:
                profile.hidden_models = update_data["hiddenModels"]
            if "cachedModelCount" in update_data:
                profile.cached_model_count = update_data["cachedModelCount"]
            if "savedModels" in update_data:
                profile.saved_models = update_data["savedModels"]
            profile.updated_at = int(datetime.now().timestamp() * 1000)
        else:
            # 创建新配置
            profile = DBConfigProfile(
                id=profile_data.id,
                user_id=user_id,
                name=profile_data.name or "新配置",
                provider_id=profile_data.providerId or "",
                api_key=profile_data.apiKey or "",
                base_url=profile_data.baseUrl or "",
                protocol=profile_data.protocol or "openai",
                is_proxy=profile_data.isProxy or False,
                hidden_models=profile_data.hiddenModels or [],
                cached_model_count=profile_data.cachedModelCount,
                saved_models=profile_data.savedModels or [],
                created_at=profile_data.createdAt or int(datetime.now().timestamp() * 1000),
                updated_at=profile_data.updatedAt or int(datetime.now().timestamp() * 1000)
            )
            db.add(profile)
        
        db.commit()
        db.refresh(profile)
        return profile.to_dict()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, request: Request, db: Session = Depends(get_db)):
    """删除配置文件"""
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    
    profile = user_query.get(DBConfigProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="配置文件不存在")

    try:
        # Check if the profile to be deleted is the active one
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if settings and settings.active_profile_id == profile_id:
            settings.active_profile_id = None
        
        db.delete(profile)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@router.get("/active-profile")
async def get_active_profile(request: Request, db: Session = Depends(get_db)):
    """获取当前激活的配置文件"""
    user_id = require_user_id(request)
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings or not settings.active_profile_id:
        return {"id": None}
    return {"id": settings.active_profile_id}


@router.post("/active-profile")
async def set_active_profile(data: dict, request: Request, db: Session = Depends(get_db)):
    """设置当前激活的配置文件"""
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    profile_id = data.get("id")

    if not profile_id:
        raise HTTPException(status_code=400, detail="Profile ID is required")

    # Verify ownership of the profile
    profile_to_activate = user_query.get(DBConfigProfile, profile_id)
    if not profile_to_activate:
        raise HTTPException(status_code=404, detail="Profile not found or access denied")

    try:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id, active_profile_id=profile_id)
            db.add(settings)
        else:
            settings.active_profile_id = profile_id
        
        db.commit()
        return {"success": True, "id": profile_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@router.get("/settings/full")
async def get_full_settings(request: Request, db: Session = Depends(get_db)):
    """
    一次性获取所有配置数据
    
    返回：
    - profiles: 所有配置列表
    - activeProfileId: 当前激活的配置 ID
    - activeProfile: 当前激活的配置（完整数据）
    - dashscopeKey: 通义千问的 API Key（用于 DashScope）
    """
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)

    # 1. 获取所有配置
    profiles = user_query.get_all(DBConfigProfile)
    profiles_data = [profile.to_dict() for profile in profiles]
    
    # 2. 获取当前激活的配置 ID
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None
    
    # 3. 获取当前激活的配置（完整数据）
    active_profile = None
    if active_profile_id:
        active_profile = next((p for p in profiles_data if p["id"] == active_profile_id), None)
    
    # 4. 获取 DashScope Key（通义千问的 API Key）
    dashscope_key = ""
    tongyi_profile = next((p for p in profiles_data if p["providerId"] == "tongyi"), None)
    if tongyi_profile:
        dashscope_key = tongyi_profile.get("apiKey", "")
    
    return {
        "profiles": profiles_data,
        "activeProfileId": active_profile_id,
        "activeProfile": active_profile,
        "dashscopeKey": dashscope_key
    }
