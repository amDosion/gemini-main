"""
配置文件管理路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from ..core.database import SessionLocal
from ..models.db_models import ConfigProfile as DBConfigProfile, UserSettings

router = APIRouter(prefix="/api", tags=["profiles"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 配置文件管理 ====================

@router.get("/profiles")
async def get_profiles(db: Session = Depends(get_db)):
    """获取所有配置文件"""
    profiles = db.query(DBConfigProfile).all()
    return [profile.to_dict() for profile in profiles]


@router.post("/profiles")
async def create_or_update_profile(profile_data: dict, db: Session = Depends(get_db)):
    """创建或更新配置文件"""
    profile_id = profile_data.get("id")
    
    # 查找现有配置
    profile = db.query(DBConfigProfile).filter(DBConfigProfile.id == profile_id).first()
    
    if profile:
        # 更新现有配置
        profile.name = profile_data.get("name", profile.name)
        profile.provider_id = profile_data.get("providerId", profile.provider_id)
        profile.api_key = profile_data.get("apiKey", profile.api_key)
        profile.base_url = profile_data.get("baseUrl", profile.base_url)
        profile.protocol = profile_data.get("protocol", profile.protocol)
        profile.is_proxy = profile_data.get("isProxy", profile.is_proxy)
        profile.hidden_models = profile_data.get("hiddenModels", profile.hidden_models)
        profile.cached_model_count = profile_data.get("cachedModelCount", profile.cached_model_count)
        profile.saved_models = profile_data.get("savedModels", profile.saved_models)
        profile.updated_at = int(datetime.now().timestamp() * 1000)
    else:
        # 创建新配置
        profile = DBConfigProfile(
            id=profile_id,
            name=profile_data.get("name", "新配置"),
            provider_id=profile_data.get("providerId", ""),
            api_key=profile_data.get("apiKey", ""),
            base_url=profile_data.get("baseUrl", ""),
            protocol=profile_data.get("protocol", "openai"),
            is_proxy=profile_data.get("isProxy", False),
            hidden_models=profile_data.get("hiddenModels", []),
            cached_model_count=profile_data.get("cachedModelCount"),
            saved_models=profile_data.get("savedModels", []),
            created_at=profile_data.get("createdAt", int(datetime.now().timestamp() * 1000)),
            updated_at=profile_data.get("updatedAt", int(datetime.now().timestamp() * 1000))
        )
        db.add(profile)
    
    db.commit()
    db.refresh(profile)
    return profile.to_dict()


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    """删除配置文件"""
    profile = db.query(DBConfigProfile).filter(DBConfigProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="配置文件不存在")
    
    db.delete(profile)
    db.commit()
    return {"success": True}


@router.get("/active-profile")
async def get_active_profile(db: Session = Depends(get_db)):
    """获取当前激活的配置文件"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == "default").first()
    if not settings or not settings.active_profile_id:
        return {"id": None}
    return {"id": settings.active_profile_id}


@router.post("/active-profile")
async def set_active_profile(data: dict, db: Session = Depends(get_db)):
    """设置当前激活的配置文件"""
    profile_id = data.get("id")
    
    settings = db.query(UserSettings).filter(UserSettings.user_id == "default").first()
    if not settings:
        settings = UserSettings(user_id="default", active_profile_id=profile_id)
        db.add(settings)
    else:
        settings.active_profile_id = profile_id
    
    db.commit()
    return {"success": True, "id": profile_id}


@router.get("/settings/full")
async def get_full_settings(db: Session = Depends(get_db)):
    """
    一次性获取所有配置数据
    
    返回：
    - profiles: 所有配置列表
    - activeProfileId: 当前激活的配置 ID
    - activeProfile: 当前激活的配置（完整数据）
    - dashscopeKey: 通义千问的 API Key（用于 DashScope）
    """
    # 1. 获取所有配置
    profiles = db.query(DBConfigProfile).all()
    profiles_data = [profile.to_dict() for profile in profiles]
    
    # 2. 获取当前激活的配置 ID
    settings = db.query(UserSettings).filter(UserSettings.user_id == "default").first()
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
