"""
统一凭证管理器 - 提供统一的 API Key 和 Base URL 获取逻辑

功能：
1. 从数据库获取 Provider 凭证（API Key 和 Base URL）
2. 自动解密已加密的 API keys
3. 支持请求参数覆盖（用于测试）
4. 优先级：请求参数 > 激活配置 > 任意匹配配置
"""

import logging
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models.db_models import UserSettings, ConfigProfile
from .encryption import decrypt_data, is_encrypted

logger = logging.getLogger(__name__)


async def get_provider_credentials(
    provider: str,
    db: Session,
    user_id: str,
    request_api_key: Optional[str] = None,
    request_base_url: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    从数据库获取 Provider 的凭证（API Key 和 Base URL）

    优先级：
    1. 请求参数（用于测试/覆盖）- 验证连接时使用
    2. 数据库配置 - 正常使用时使用
       - 优先使用激活配置（如果匹配 provider）
       - 回退到任意匹配 provider 的配置

    Args:
        provider: Provider 标识（google, openai, tongyi 等）
        db: 数据库会话
        user_id: 当前用户 ID
        request_api_key: 请求中的 API Key（可选，用于覆盖）
        request_base_url: 请求中的 Base URL（可选，用于验证）

    Returns:
        Tuple[api_key, base_url]

    Raises:
        HTTPException: 如果未找到 API Key
    """
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
                logger.warning(f"[CredentialManager] Failed to decrypt API key: {e}")
            # ✅ 解密失败时抛出异常，而不是返回加密的值
            # 返回加密的值会导致 API 调用失败（如 "API key expired"）
            raise
    
    # 1. 优先使用请求参数（用于验证连接）
    if request_api_key and request_api_key.strip():
        logger.info(f"[CredentialManager] Using API key from request parameter for {provider}")
        # 请求参数通常是明文，直接使用
        return request_api_key, request_base_url

    # 2. 从数据库获取（正常使用）
    # 2.1 获取当前激活的配置 ID
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    # 2.2 如果有激活配置，检查是否匹配请求的 provider
    if active_profile_id:
        active_profile = db.query(ConfigProfile).filter(
            ConfigProfile.id == active_profile_id,
            ConfigProfile.provider_id == provider,
            ConfigProfile.user_id == user_id  # 确保配置属于当前用户
        ).first()
        if active_profile and active_profile.api_key:
            logger.info(f"[CredentialManager] Using API key from active profile '{active_profile.name}' for {provider}")
            # ✅ 自动解密 API key（用于业务逻辑使用）
            # 使用 silent=True 保持与 chat 模式一致的行为
            api_key = _decrypt_api_key(active_profile.api_key, silent=True)
            # ✅ 直接使用数据库中的 base_url（已经是完整的 URL）
            return api_key, active_profile.base_url

    # 2.3 回退：查找任意匹配 provider 的配置（属于当前用户）
    any_profile = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == provider,
        ConfigProfile.user_id == user_id  # 确保配置属于当前用户
    ).first()
    if any_profile and any_profile.api_key:
        logger.info(f"[CredentialManager] Using API key from profile '{any_profile.name}' for {provider}")
        # ✅ 自动解密 API key（用于业务逻辑使用）
        # 使用 silent=True 保持与 chat 模式一致的行为
        api_key = _decrypt_api_key(any_profile.api_key, silent=True)
        # ✅ 直接使用数据库中的 base_url（已经是完整的 URL）
        return api_key, any_profile.base_url

    # 3. 未找到 API Key，返回 401 错误
    raise HTTPException(
        status_code=401,
        detail=f"API Key not found for provider: {provider}. "
               f"Please configure it in Settings → Profiles."
    )
