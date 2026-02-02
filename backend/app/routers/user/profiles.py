"""
配置文件管理路由
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from ...core.database import SessionLocal, get_db
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
        api_key: API Key（可能是明文或已加密）

    Returns:
        加密后的 API Key
    """
    if not api_key:
        return api_key
    
    # 如果已经是加密的，直接返回
    if is_encrypted(api_key):
        return api_key
    
    # 明文 API Key，加密后返回
    try:
        return encrypt_data(api_key)
    except Exception as e:
        logger.error(f"[Profiles] Failed to encrypt API key: {e}")
        raise


def _decrypt_api_key(api_key: str, silent: bool = False) -> str:
    """
    解密 API Key（如果已加密）

    Args:
        api_key: API Key（可能是明文或已加密）
        silent: 如果为 True，解密失败时不记录错误（用于兼容性检查）

    Returns:
        解密后的 API Key（如果未加密则原样返回）
    """
    if not api_key:
        return api_key
    
    # 如果未加密，直接返回
    if not is_encrypted(api_key):
        return api_key
    
    # 尝试解密
    try:
        return decrypt_data(api_key, silent=silent)
    except Exception as e:
        if not silent:
            logger.warning(f"[Profiles] Failed to decrypt API key: {e}")
        # 解密失败时返回原值（可能是旧数据或密钥不匹配）
        return api_key


class ConfigProfilePayload(BaseModel):
    id: str
    name: Optional[str] = None
    provider_id: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    protocol: Optional[str] = None
    is_proxy: Optional[bool] = None
    hidden_models: Optional[List[str]] = None
    cached_model_count: Optional[int] = None
    saved_models: Optional[List[dict]] = None  # 接收完整的 ModelConfig 对象数组
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    class Config:
        extra = "ignore"

# ==================== 配置文件管理 ====================

@router.get("/profiles")
async def get_profiles(
    edit_mode: bool = False,  # 编辑模式：True 时解密返回，False 时返回加密值
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取所有配置文件
    
    Args:
        edit_mode: 编辑模式，True 时解密 API Key 返回，False 时返回加密值
    """
    user_query = UserScopedQuery(db, user_id)
    profiles = user_query.get_all(DBConfigProfile)

    result = []
    for profile in profiles:
        profile_dict = profile.to_dict()
        
        # 根据 edit_mode 决定是否解密 API Key
        if edit_mode and profile_dict.get("api_key"):
            # 编辑模式：解密返回给前端
            try:
                profile_dict["api_key"] = _decrypt_api_key(profile_dict["api_key"], silent=True)
                logger.debug(f"[Profiles] Decrypted API key for edit mode (profile={profile.id})")
            except Exception as e:
                logger.warning(f"[Profiles] Failed to decrypt API key in edit mode: {e}")
                # 解密失败时返回加密值（前端可以显示错误）
        # 非编辑模式：返回加密值（或 None）
        
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
            if "provider_id" in update_data:
                profile.provider_id = update_data["provider_id"]
            if "api_key" in update_data:
                # 保存 API Key（加密存储）
                api_key_to_save = update_data["api_key"]
                
                # 判断是否已经是加密的（通过一致性检查）
                existing_encrypted = profile.api_key
                
                if existing_encrypted and existing_encrypted == api_key_to_save:
                    # 用户没有修改 API Key，保持加密状态
                    logger.debug(f"[Profiles] API key unchanged, keeping encrypted value (profile={profile.id})")
                    # 不需要更新，保持原值
                else:
                    # 新的 API Key 或修改过的 API Key，需要加密保存
                    try:
                        # 检查是否已经是加密格式
                        if is_encrypted(api_key_to_save):
                            # 如果已经是加密的，直接保存（可能是前端传递回来的加密值）
                            profile.api_key = api_key_to_save
                            logger.debug(f"[Profiles] Saved encrypted API key (already encrypted) (profile={profile.id})")
                        else:
                            # 明文 API Key，加密后保存
                            # 先检查是否与数据库中解密后的值相同（避免不必要的加密操作）
                            if existing_encrypted:
                                try:
                                    if is_encrypted(existing_encrypted):
                                        existing_decrypted = _decrypt_api_key(existing_encrypted, silent=True)
                                        if existing_decrypted == api_key_to_save:
                                            # 用户没有修改 API Key，保持加密状态
                                            logger.debug(f"[Profiles] API key unchanged (decrypted comparison), keeping encrypted value (profile={profile.id})")
                                            # 不需要更新，保持原值
                                        else:
                                            # 新的 API Key，加密后保存
                                            profile.api_key = _encrypt_api_key(api_key_to_save)
                                            logger.info(f"[Profiles] Encrypted and saved new API key (profile={profile.id})")
                                    else:
                                        # 数据库中是明文（旧数据），加密后保存
                                        profile.api_key = _encrypt_api_key(api_key_to_save)
                                        logger.info(f"[Profiles] Encrypted and saved API key (migrated from plaintext) (profile={profile.id})")
                                except Exception as e:
                                    # 解密失败，可能是密钥不匹配，当作新 API Key 处理
                                    logger.warning(f"[Profiles] Failed to decrypt existing API key for comparison: {e}")
                                    profile.api_key = _encrypt_api_key(api_key_to_save)
                                    logger.info(f"[Profiles] Encrypted and saved new API key (decryption failed) (profile={profile.id})")
                            else:
                                # 数据库中没有 API Key，加密后保存
                                profile.api_key = _encrypt_api_key(api_key_to_save)
                                logger.info(f"[Profiles] Encrypted and saved new API key (first time) (profile={profile.id})")
                    except Exception as e:
                        logger.error(f"[Profiles] Failed to encrypt API key: {e}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to encrypt API key: {str(e)}"
                        )
            if "base_url" in update_data:
                profile.base_url = update_data["base_url"]
            if "protocol" in update_data:
                profile.protocol = update_data["protocol"]
            if "is_proxy" in update_data:
                profile.is_proxy = update_data["is_proxy"]
            if "hidden_models" in update_data:
                profile.hidden_models = update_data["hidden_models"]
            if "cached_model_count" in update_data:
                profile.cached_model_count = update_data["cached_model_count"]
            if "saved_models" in update_data:
                profile.saved_models = update_data["saved_models"]
            profile.updated_at = int(datetime.now().timestamp() * 1000)
        else:
            # 创建新配置（加密存储 API Key）
            api_key_to_save = profile_data.api_key or ""
            if api_key_to_save:
                # 只有提供了 API Key 才加密保存
                if is_encrypted(api_key_to_save):
                    # 如果已经是加密的，直接保存
                    encrypted_api_key = api_key_to_save
                else:
                    # 明文 API Key，加密后保存
                    encrypted_api_key = _encrypt_api_key(api_key_to_save)
            else:
                encrypted_api_key = ""
            
            profile = DBConfigProfile(
                id=profile_data.id,
                user_id=user_id,
                name=profile_data.name or "新配置",
                provider_id=profile_data.provider_id or "",
                api_key=encrypted_api_key,
                base_url=profile_data.base_url or "",
                protocol=profile_data.protocol or "openai",
                is_proxy=profile_data.is_proxy or False,
                hidden_models=profile_data.hidden_models or [],
                cached_model_count=profile_data.cached_model_count,
                saved_models=profile_data.saved_models or [],
                created_at=profile_data.created_at or int(datetime.now().timestamp() * 1000),
                updated_at=profile_data.updated_at or int(datetime.now().timestamp() * 1000)
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
    edit_mode: bool = False,  # 编辑模式：True 时解密返回，False 时返回加密值
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    一次性获取所有配置数据

    Args:
        edit_mode: 编辑模式，True 时解密 API Key 返回，False 时返回加密值

    返回：
    - profiles: 所有配置列表
    - activeProfileId: 当前激活的配置 ID
    - activeProfile: 当前激活的配置（完整数据）
    - dashscopeKey: 通义千问的 API Key（用于 DashScope）
    """
    user_query = UserScopedQuery(db, user_id)

    # 1. 获取所有配置
    profiles = user_query.get_all(DBConfigProfile)
    profiles_data = []
    for profile in profiles:
        profile_dict = profile.to_dict()
        
        # 根据 edit_mode 决定是否解密 API Key
        if edit_mode and profile_dict.get("api_key"):
            # 编辑模式：解密返回给前端
            try:
                profile_dict["api_key"] = _decrypt_api_key(profile_dict["api_key"], silent=True)
                logger.debug(f"[Profiles] Decrypted API key for edit mode in full settings (profile={profile.id})")
            except Exception as e:
                logger.warning(f"[Profiles] Failed to decrypt API key in edit mode: {e}")
                # 解密失败时返回加密值
        # 非编辑模式：返回加密值（或 None）
        
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
    tongyi_profile = next((p for p in profiles_data if p["provider_id"] == "tongyi"), None)
    if tongyi_profile:
        dashscope_key = tongyi_profile.get("api_key", "")

    return {
        "profiles": profiles_data,
        "active_profile_id": active_profile_id,
        "active_profile": active_profile,
        "dashscope_key": dashscope_key
    }
