"""
配置文件管理路由
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from ...core.database import SessionLocal
from ...models.db_models import ConfigProfile as DBConfigProfile, UserSettings
from ...core.dependencies import require_current_user
from ...core.user_scoped_query import UserScopedQuery
from ...core.encryption import encrypt_data, decrypt_data, is_encrypted

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profiles"])


def _encrypt_api_key(api_key: str) -> str:
    """
    加密 API Key（如果尚未加密）

    Args:
        api_key: 原始或已加密的 API Key

    Returns:
        加密后的 API Key
    """
    if not api_key:
        return api_key

    # 如果已经加密，直接返回
    if is_encrypted(api_key):
        return api_key

    try:
        encrypted = encrypt_data(api_key)
        logger.debug("[Profiles] API key encrypted successfully")
        return encrypted
    except Exception as e:
        # 如果加密失败（如未配置 ENCRYPTION_KEY），记录警告但不阻止操作
        logger.warning(f"[Profiles] API key encryption failed (storing plain): {e}")
        return api_key


def _decrypt_api_key(api_key: str) -> str:
    """
    解密 API Key（兼容未加密的历史数据）

    Args:
        api_key: 加密或明文的 API Key

    Returns:
        解密后的 API Key
    """
    if not api_key:
        return api_key

    # 如果不是加密格式，直接返回（兼容历史数据）
    if not is_encrypted(api_key):
        return api_key

    try:
        # 使用 silent=True 避免在兼容性检查时记录 ERROR
        decrypted = decrypt_data(api_key, silent=True)
        return decrypted
    except ValueError as e:
        # ENCRYPTION_KEY 未设置，这是配置问题
        logger.warning(
            f"[Profiles] ENCRYPTION_KEY not configured. "
            f"Cannot decrypt API key (returning as-is). "
            f"Please set ENCRYPTION_KEY in .env file."
        )
        return api_key
    except Exception as e:
        # 解密失败，可能是未加密的旧数据或密钥不匹配
        # 这种情况在兼容性场景中是正常的，只记录 DEBUG
        logger.debug(
            f"[Profiles] API key decryption failed (returning as-is): "
            f"{type(e).__name__} - This may be normal for unencrypted legacy data"
        )
        return api_key


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
async def get_profiles(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取所有配置文件（API Key 自动解密）"""
    user_query = UserScopedQuery(db, user_id)
    profiles = user_query.get_all(DBConfigProfile)

    # 解密 API Key 后返回
    result = []
    for profile in profiles:
        profile_dict = profile.to_dict()
        profile_dict["apiKey"] = _decrypt_api_key(profile_dict.get("apiKey", ""))
        result.append(profile_dict)
    return result


@router.post("/profiles")
async def create_or_update_profile(
    profile_data: ConfigProfilePayload,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """创建或更新配置文件"""
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
                # 加密存储 API Key
                profile.api_key = _encrypt_api_key(update_data["apiKey"])
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
            # 创建新配置（加密存储 API Key）
            profile = DBConfigProfile(
                id=profile_data.id,
                user_id=user_id,
                name=profile_data.name or "新配置",
                provider_id=profile_data.providerId or "",
                api_key=_encrypt_api_key(profile_data.apiKey or ""),
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
async def delete_profile(
    profile_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """删除配置文件"""
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
async def get_active_profile(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取当前激活的配置文件"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings or not settings.active_profile_id:
        return {"id": None}
    return {"id": settings.active_profile_id}


@router.post("/active-profile")
async def set_active_profile(
    data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """设置当前激活的配置文件"""
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
async def get_full_settings(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    一次性获取所有配置数据（API Key 自动解密）

    返回：
    - profiles: 所有配置列表
    - activeProfileId: 当前激活的配置 ID
    - activeProfile: 当前激活的配置（完整数据）
    - dashscopeKey: 通义千问的 API Key（用于 DashScope）
    """
    user_query = UserScopedQuery(db, user_id)

    # 1. 获取所有配置（解密 API Key）
    profiles = user_query.get_all(DBConfigProfile)
    profiles_data = []
    for profile in profiles:
        profile_dict = profile.to_dict()
        profile_dict["apiKey"] = _decrypt_api_key(profile_dict.get("apiKey", ""))
        profiles_data.append(profile_dict)

    # 2. 获取当前激活的配置 ID
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    # 3. 获取当前激活的配置（完整数据）
    active_profile = None
    if active_profile_id:
        active_profile = next((p for p in profiles_data if p["id"] == active_profile_id), None)

    # 4. 获取 DashScope Key（通义千问的 API Key，已解密）
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
