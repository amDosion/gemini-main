"""
Models API Router

This module provides API endpoints for getting available models from all providers.
It supports caching to improve performance and reduce API calls.
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple, Any
import logging
import time

from ...core.database import SessionLocal, get_db
from ...models.db_models import ConfigProfile, UserSettings
from ...services.common.model_capabilities import ModelConfig
from ...core.dependencies import require_current_user, get_cache
from ...services.common.provider_factory import ProviderFactory  # ✅ 移到顶部，避免每次请求都导入

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


# Simple in-memory cache
# Format: {provider: {"models": [ModelConfig, ...], "timestamp": float}}
_model_cache: dict[str, dict[str, Any]] = {}
_cache_ttl = 3600  # 1 hour in seconds


# ==================== Helper Functions ====================

def filter_models_by_mode(models: List[ModelConfig], mode: str) -> List[ModelConfig]:
    """
    根据 App Mode 过滤模型列表（后端过滤逻辑）

    Args:
        models: 完整的模型列表
        mode: 应用模式 (chat, image-edit, image-gen, 等)

    Returns:
        过滤后的模型列表
    """
    filtered = []

    for model in models:
        model_id = model.id.lower()
        caps = model.capabilities

        # 根据不同模式应用过滤规则
        should_include = False

        if mode == 'video-gen':
            # 视频生成：包含 veo, sora, luma, video
            should_include = any(keyword in model_id for keyword in ['veo', 'sora', 'luma', 'video'])

        elif mode == 'audio-gen':
            # 音频生成：包含 tts, audio, speech
            should_include = any(keyword in model_id for keyword in ['tts', 'audio', 'speech'])

        elif mode == 'image-gen':
            # 纯文生图模式：排除编辑模型，只包含纯生成模型
            if 'edit' in model_id:
                should_include = False
            else:
                should_include = any(keyword in model_id for keyword in [
                    'dall', 'wanx', 'flux', 'midjourney', '-t2i', 'z-image', 'imagen'
                ])

        elif mode in ['image-edit', 'image-outpainting']:
            # 图像编辑/扩展模式：需要 vision 能力，排除视频和纯文生图模型
            if not caps.vision or 'veo' in model_id:
                should_include = False
            else:
                # 排除纯文生图模型
                is_text_to_image_only = any([
                    'wanx' in model_id and '-t2i' in model_id,  # wanx-t2i 系列
                    'wan2' in model_id and '-t2i' in model_id,  # wan2.x-t2i 系列
                    'z-image-turbo' in model_id,                 # z-image-turbo
                    'dall' in model_id,                          # DALL-E
                    'flux' in model_id,                          # Flux
                    'midjourney' in model_id,                    # Midjourney
                    model_id.startswith('imagen-') and 'edit' not in model_id  # Imagen 纯生成
                ])
                should_include = not is_text_to_image_only

        elif mode == 'virtual-try-on':
            # 虚拟试衣：需要 vision 能力，排除视频生成
            should_include = caps.vision and 'veo' not in model_id

        elif mode == 'deep-research':
            # 深度研究：需要搜索或推理能力
            should_include = caps.search or caps.reasoning

        elif mode == 'pdf-extract':
            # PDF 提取：排除专用媒体生成模型
            excluded_keywords = ['veo', 'tts', 'wanx', 'imagen', '-t2i', 'z-image']
            should_include = not any(keyword in model_id for keyword in excluded_keywords)

        elif mode == 'chat' or not mode:
            # 标准聊天：排除专用视频/音频/图像生成模型
            excluded_keywords = ['veo', 'tts', 'wanx', '-t2i', 'z-image']
            should_include = not any(keyword in model_id for keyword in excluded_keywords)

        else:
            # 未知模式：不过滤
            should_include = True

        if should_include:
            filtered.append(model)

    return filtered


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
    # 导入解密函数
    from ...core.encryption import decrypt_data, is_encrypted
    
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
                logger.warning(f"[Models] Failed to decrypt API key: {e}")
            # 解密失败时返回原值（可能是旧数据或密钥不匹配）
            return api_key
    
    # 1. 优先使用请求参数（用于验证连接）
    if request_api_key:
        logger.info(f"[Models] Using API key from request parameter for {provider}")
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
            logger.info(f"[Models] Using API key from active profile '{active_profile.name}' for {provider}")
            # ✅ 自动解密 API key（用于业务逻辑使用）
            api_key = _decrypt_api_key(active_profile.api_key, silent=True)
            # ✅ 直接使用数据库中的 base_url（已经是完整的 URL）
            return api_key, active_profile.base_url

    # 2.3 回退：查找任意匹配 provider 的配置（属于当前用户）
    any_profile = db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == provider,
        ConfigProfile.user_id == user_id  # 确保配置属于当前用户
    ).first()
    if any_profile and any_profile.api_key:
        logger.info(f"[Models] Using API key from profile '{any_profile.name}' for {provider}")
        # ✅ 自动解密 API key（用于业务逻辑使用）
        api_key = _decrypt_api_key(any_profile.api_key, silent=True)
        # ✅ 直接使用数据库中的 base_url（已经是完整的 URL）
        return api_key, any_profile.base_url

    # 3. 未找到 API Key，返回 401 错误
    raise HTTPException(
        status_code=401,
        detail=f"API Key not found for provider: {provider}. "
               f"Please configure it in Settings → Profiles."
    )


def is_cache_valid(provider: str) -> bool:
    """Check if cached models are still valid."""
    if provider not in _model_cache:
        return False
    
    cache_entry = _model_cache[provider]
    current_time = time.time()
    age = current_time - cache_entry["timestamp"]
    
    return age < _cache_ttl


def get_cached_models(provider: str) -> Optional[List[dict]]:
    """Get models from cache if valid."""
    if is_cache_valid(provider):
        logger.info(f"[Models] Using cached models for {provider}")
        return _model_cache[provider]["models"]
    return None


def cache_models(provider: str, models: List[ModelConfig]) -> None:
    """Cache models for a provider."""
    # Convert ModelConfig to dict for JSON serialization
    models_dict = [model.model_dump() for model in models]
    _model_cache[provider] = {
        "models": models_dict,
        "timestamp": time.time()
    }
    logger.info(f"[Models] Cached {len(models)} models for {provider}")


def clear_cache(provider: Optional[str] = None) -> None:
    """Clear model cache."""
    if provider:
        if provider in _model_cache:
            del _model_cache[provider]
            logger.info(f"[Models] Cleared cache for {provider}")
    else:
        _model_cache.clear()
        logger.info("[Models] Cleared all cache")


# ==================== API Endpoints ====================

@router.get("/{provider}")
async def get_available_models(
    provider: str,
    apiKey: Optional[str] = Query(None, description="API key for the provider (optional, will use database config if not provided)"),
    baseUrl: Optional[str] = Query(None, description="Custom API URL"),
    useCache: bool = Query(True, description="Whether to use cached models"),
    mode: Optional[str] = Query(None, description="Filter models by app mode (chat, image-edit, image-gen, etc.)"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    """
    Get available models for a provider.

    API Key 获取优先级：
    1. Query parameter (apiKey) - 用于测试/覆盖
    2. Database (ConfigProfile table) - 用户在设置中配置的 API Key

    模型过滤 (mode 参数):
    - 如果指定了 mode，后端会根据模式过滤模型列表
    - 支持的模式: chat, image-edit, image-gen, image-outpainting, video-gen, audio-gen, virtual-try-on, deep-research, pdf-extract
    - 示例: /api/models/google?mode=image-edit

    Returns:
        {
            "models": [ModelConfig, ...],  # List of complete model configurations
            "cached": bool,
            "provider": str,
            "filtered_by_mode": str | null  # 如果应用了过滤，返回模式名称
        }
    """
    try:
        # user_id 已通过依赖注入自动获取
        
        logger.info(f"[Models] Getting models for {provider}, user={user_id}, useCache={useCache}")
        start_time = time.time()
        
        from ...services.common.cache_service import CacheService
        cache_service: CacheService = cache
        
        # 生成缓存键（包含 user_id 和 provider，因为不同用户的 API Key 可能不同）
        cache_key = cache_service._make_key("models", provider, user_id)
        
        # 定义数据获取函数
        async def fetch_models():
            # Get credentials from database
            api_key, effective_base_url = await get_provider_credentials(
                provider, db, user_id, apiKey, baseUrl
            )

            # Create provider service (使用顶部导入的 ProviderFactory)
            try:
                service = ProviderFactory.create(
                    provider=provider,
                    api_key=api_key,
                    api_url=effective_base_url,
                    timeout=30.0
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            
            # ✅ 添加请求级别的超时保护：最多等待 28 秒
            # 这样可以确保即使 Provider 内部超时失败，也能在 30 秒内返回
            import asyncio
            try:
                logger.info(f"[Models] Calling service.get_available_models() for {provider}")
                models = await asyncio.wait_for(
                    service.get_available_models(),
                    timeout=28.0
                )
                logger.info(f"[Models] Got {len(models)} models for {provider} in {time.time() - start_time:.2f}s")
            except asyncio.TimeoutError:
                logger.error(f"[Models] Request timed out after 28 seconds for {provider}")
                raise HTTPException(
                    status_code=504,
                    detail=f"Request to {provider} API timed out. Please check your network connection and try again."
                )
            
            # 转换为字典格式（用于缓存）
            models_dict = [model.model_dump() for model in models]
            return models_dict
        
        # 使用 Redis 缓存（TTL: 1 小时）
        was_cached = False
        if useCache:
            try:
                cached_models_dict = await cache_service.get_or_set(
                    cache_key,
                    fetch_models,
                    ttl=3600
                )
                was_cached = True
                # 转换回 ModelConfig 对象（用于过滤）
                from ...services.common.model_capabilities import ModelConfig
                models = [ModelConfig(**m) for m in cached_models_dict]
                logger.info(f"[Models] ✅ 返回缓存模型: {len(models)} 个模型 (耗时: {time.time() - start_time:.2f}s)")
            except Exception as e:
                logger.warning(f"[Models] 缓存获取失败，使用直接查询: {e}")
                models_dict = await fetch_models()
                from ...services.common.model_capabilities import ModelConfig
                models = [ModelConfig(**m) for m in models_dict]
                logger.info(f"[Models] ✅ 直接查询结果: {len(models)} 个模型")
        else:
            # 不使用缓存，直接获取
            models_dict = await fetch_models()
            from ...services.common.model_capabilities import ModelConfig
            models = [ModelConfig(**m) for m in models_dict]
            logger.info(f"[Models] ✅ 直接查询结果（无缓存）: {len(models)} 个模型")

        # ✅ 应用模式过滤（如果指定了 mode 参数）
        filtered_models = models
        if mode:
            logger.info(f"[Models] Applying mode filter: {mode}")
            filtered_models = filter_models_by_mode(models, mode)
            logger.info(f"[Models] Filtered {len(models)} -> {len(filtered_models)} models for mode={mode}")

        # Convert to dict for JSON response
        models_dict = [model.model_dump() for model in filtered_models]

        elapsed = time.time() - start_time
        logger.info(f"[Models] ========== 请求完成 ==========")
        logger.info(f"[Models] 提供商: {provider}")
        logger.info(f"[Models] 最终返回模型数: {len(filtered_models)} 个")
        logger.info(f"[Models] 是否使用缓存: {was_cached}")
        logger.info(f"[Models] 是否应用模式过滤: {mode if mode else '否'}")
        logger.info(f"[Models] 总耗时: {elapsed:.2f}s")
        logger.info(f"[Models] =================================")

        return {
            "models": models_dict,
            "cached": was_cached,
            "provider": provider,
            "filtered_by_mode": mode if mode else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Models] Error getting models for {provider}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{provider}/cache")
async def clear_model_cache(
    provider: str,
    user_id: str = Depends(require_current_user),
    cache = Depends(get_cache)
):
    """
    Clear cached models for a provider (Redis cache).
    
    Clears Redis cache for the specified provider.
    Uses wildcard to clear cache for all users of this provider.
    """
    from ...services.common.cache_service import CacheService
    cache_service: CacheService = cache
    
    # 清除内存缓存（向后兼容）
    clear_cache(provider)
    
    # 清除Redis缓存 - 使用通配符匹配所有用户的该provider缓存
    # 缓存键格式: cache:models:{provider}:{user_id}
    # 使用通配符: cache:models:{provider}:*
    cache_pattern = f"cache:models:{provider}:*"
    deleted = await cache_service.delete(cache_pattern)
    
    logger.info(f"[Models] ✅ Cleared Redis cache for {provider}: deleted {deleted} keys (pattern: {cache_pattern})")
    
    return {
        "message": f"Cache cleared for provider: {provider}",
        "redis_keys_deleted": deleted,
        "pattern": cache_pattern
    }


@router.delete("/cache")
async def clear_all_model_cache(cache = Depends(get_cache)):
    """
    Clear all cached models (Redis cache).
    
    Clears all Redis cache entries for models.
    """
    from ...services.common.cache_service import CacheService
    cache_service: CacheService = cache
    
    # 清除内存缓存（向后兼容）
    clear_cache()
    
    # 清除所有Redis模型缓存
    # 缓存键格式: cache:models:*
    cache_pattern = "cache:models:*"
    deleted = await cache_service.delete(cache_pattern)
    
    logger.info(f"[Models] ✅ Cleared all Redis model cache: deleted {deleted} keys (pattern: {cache_pattern})")
    
    return {
        "message": "All model cache cleared",
        "redis_keys_deleted": deleted,
        "pattern": cache_pattern
    }


@router.get("/cache/status")
async def get_cache_status():
    """Get cache status for all providers."""
    current_time = time.time()
    status = {}
    
    for provider, cache_entry in _model_cache.items():
        age = current_time - cache_entry["timestamp"]
        expires_in = _cache_ttl - age
        
        status[provider] = {
            "cached": True,
            "model_count": len(cache_entry["models"]),
            "age_seconds": int(age),
            "expires_in_seconds": int(max(0, expires_in)),
            "valid": expires_in > 0
        }
    
    return status
