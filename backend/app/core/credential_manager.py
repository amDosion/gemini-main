"""
统一凭证管理器

提供统一的 API Key 和 Base URL 获取逻辑。
所有路由和服务都应该使用此模块获取凭证。
"""
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging

from ..models.db_models import ConfigProfile, UserSettings
from .encryption import decrypt_data, is_encrypted

logger = logging.getLogger(__name__)


def _decrypt_api_key(api_key: str) -> str:
    """
    解密 API Key（兼容未加密的历史数据）
    
    Args:
        api_key: 可能加密的 API Key
        
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
        # 使用 silent=True 避免在兼容性检查时记录 ERROR
        return decrypt_data(api_key, silent=True)
    except ValueError as e:
        # ENCRYPTION_KEY 未设置，这是配置问题
        logger.warning(
            f"[CredentialManager] ENCRYPTION_KEY not configured. "
            f"Cannot decrypt API key (returning as-is). "
            f"Please set ENCRYPTION_KEY in .env file."
        )
        return api_key
    except Exception as e:
        # 解密失败，可能是未加密的旧数据或密钥不匹配
        # 这种情况在兼容性场景中是正常的，只记录 DEBUG
        logger.debug(
            f"[CredentialManager] API key decryption failed (returning as-is): "
            f"{type(e).__name__} - This may be normal for unencrypted legacy data"
        )
        return api_key


async def get_provider_credentials(
    provider: str,
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None,
    request_base_url: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    获取 Provider 的凭证（API Key 和 Base URL）
    
    优先级：
    1. 请求参数中的 apiKey（用于测试/覆盖）
    2. 数据库激活配置（匹配 provider）
    3. 数据库任意配置（匹配 provider）
    
    Args:
        provider: Provider 标识（google, tongyi, openai 等）
        db: 数据库会话
        user_id: 当前用户 ID
        request_api_key: 请求中的 API Key（可选，用于覆盖）
        request_base_url: 请求中的 Base URL（可选）
        
    Returns:
        Tuple[api_key, base_url]
        
    Raises:
        HTTPException: 如果未找到 API Key
    """
    import time
    import sys
    start_time = time.time()
    
    logger.info(f"[CredentialManager] 🔄 开始获取凭证: provider={provider}, user_id={user_id[:8]}...")
    print(f"[CredentialManager] 🔄 开始获取凭证: provider={provider}, user_id={user_id[:8]}...", file=sys.stderr, flush=True)
    
    # 1. 优先使用请求参数（用于测试/验证连接场景）
    if request_api_key and request_api_key.strip():
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"[CredentialManager] ✅ 使用请求参数中的 API key (耗时: {elapsed:.2f}ms)")
        print(f"[CredentialManager] ✅ 使用请求参数中的 API key (耗时: {elapsed:.2f}ms)", file=sys.stderr, flush=True)
        return request_api_key, request_base_url
    
    # 2. 从数据库获取（正常使用）
    # 获取用户设置（包含激活配置 ID）
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None
    
    # 查询所有匹配 provider 的配置（属于当前用户）
    matching_profiles = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == provider,
        ConfigProfile.user_id == user_id
    ).all()
    
    if not matching_profiles:
        raise HTTPException(
            status_code=401,
            detail=f"API Key not found for provider: {provider}. "
                   f"Please configure it in Settings → Profiles."
        )
    
    # 优先使用激活配置（如果匹配 provider）
    if active_profile_id:
        for profile in matching_profiles:
            if profile.id == active_profile_id and profile.api_key:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"[CredentialManager] ✅ 使用激活配置 '{profile.name}' (耗时: {elapsed:.2f}ms)")
                print(f"[CredentialManager] ✅ 使用激活配置 '{profile.name}' (耗时: {elapsed:.2f}ms)", file=sys.stderr, flush=True)
                decrypted_key = _decrypt_api_key(profile.api_key)
                return decrypted_key, profile.base_url
    
    # 回退：使用第一个匹配 provider 的配置
    for profile in matching_profiles:
        if profile.api_key:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[CredentialManager] ✅ 使用配置 '{profile.name}' (回退, 耗时: {elapsed:.2f}ms)")
            print(f"[CredentialManager] ✅ 使用配置 '{profile.name}' (回退, 耗时: {elapsed:.2f}ms)", file=sys.stderr, flush=True)
            decrypted_key = _decrypt_api_key(profile.api_key)
            return decrypted_key, profile.base_url
    
    # 所有配置都没有 API Key，返回 401 错误
    elapsed = (time.time() - start_time) * 1000
    logger.error(f"[CredentialManager] ❌ 未找到 API Key (耗时: {elapsed:.2f}ms)")
    print(f"[CredentialManager] ❌ 未找到 API Key (耗时: {elapsed:.2f}ms)", file=sys.stderr, flush=True)
    raise HTTPException(
        status_code=401,
        detail=f"API Key not found for provider: {provider}. "
               f"Please configure it in Settings → Profiles."
    )
