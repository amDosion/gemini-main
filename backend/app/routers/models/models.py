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

"""
Vertex AI 专用模型分类

基于 Google 官方 SDK 文档定义的模型分类规则：
- 图像生成 (image-gen): imagen-*-generate-*, gemini-*-image-*
- 图像编辑 (image-edit): imagen-3.0-capability-001, imagen-4.0-ingredients-preview
- 图像放大 (image-upscale): imagen-4.0-upscale-preview
- 图像分割 (image-segmentation): image-segmentation-001
- 虚拟试衣 (virtual-try-on): virtual-try-on-*, virtual-try-on-preview-*
- 产品重构 (product-recontext): imagen-product-recontext-*
"""

# Imagen 图像生成模型（纯文生图，不支持编辑）
IMAGEN_GENERATE_MODELS = [
    'imagen-3.0-generate-001',
    'imagen-3.0-generate-002',
    'imagen-3.0-fast-generate-001',
    'imagen-4.0-generate-preview',
    'imagen-4.0-ultra-generate-preview',
]

# Imagen 图像编辑模型（支持 mask 编辑、背景替换等）
IMAGEN_EDIT_MODELS = [
    'imagen-3.0-capability-001',      # 主要编辑模型
    'imagen-4.0-ingredients-preview', # 高级编辑模型
]

# 图像放大模型
IMAGE_UPSCALE_MODELS = [
    'imagen-4.0-upscale-preview',
]

# 图像分割模型
IMAGE_SEGMENTATION_MODELS = [
    'image-segmentation-001',
]

# 虚拟试衣模型
VIRTUAL_TRY_ON_MODELS = [
    'virtual-try-on-001',
    'virtual-try-on-preview-08-04',
]

# 产品重构模型
PRODUCT_RECONTEXT_MODELS = [
    'imagen-product-recontext-preview-06-30',
]


def _matches_model_list(model_id: str, model_list: list) -> bool:
    """检查模型是否匹配静态模型列表（支持前缀匹配）"""
    lower_id = model_id.lower()
    for m in model_list:
        lower_m = m.lower()
        # 精确匹配或前缀匹配（处理版本号后缀）
        if lower_id == lower_m or lower_id.startswith(lower_m.rsplit('-', 1)[0] if '-' in lower_m else lower_m):
            return True
    return False


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
            # 纯文生图模式：排除编辑、放大、分割、试衣、重构模型
            if _matches_model_list(model.id, IMAGEN_EDIT_MODELS):
                should_include = False
            elif _matches_model_list(model.id, IMAGE_UPSCALE_MODELS):
                should_include = False
            elif _matches_model_list(model.id, IMAGE_SEGMENTATION_MODELS):
                should_include = False
            elif _matches_model_list(model.id, VIRTUAL_TRY_ON_MODELS):
                should_include = False
            elif _matches_model_list(model.id, PRODUCT_RECONTEXT_MODELS):
                should_include = False
            elif 'edit' in model_id:
                should_include = False
            else:
                # 包含 Imagen 生成模型
                if _matches_model_list(model.id, IMAGEN_GENERATE_MODELS):
                    should_include = True
                else:
                    # 专门的图像生成模型
                    is_specialized = any(keyword in model_id for keyword in [
                        'dall', 'wanx', 'flux', 'midjourney', '-t2i', 'z-image'
                    ]) or ('imagen' in model_id and 'generate' in model_id)
                    # ✅ 支持 Gemini Image 模型
                    is_gemini_image = 'gemini' in model_id and 'image' in model_id
                    # ✅ 支持 Nano-Banana 系列
                    is_nano_banana = 'nano-banana' in model_id
                    should_include = is_specialized or is_gemini_image or is_nano_banana

        elif mode == 'image-upscale':
            # 图像放大模式：只包含放大模型
            should_include = _matches_model_list(model.id, IMAGE_UPSCALE_MODELS) or 'upscale' in model_id

        elif mode == 'image-segmentation':
            # 图像分割模式：只包含分割模型
            should_include = _matches_model_list(model.id, IMAGE_SEGMENTATION_MODELS) or 'segmentation' in model_id

        elif mode == 'product-recontext':
            # 产品重构模式
            should_include = _matches_model_list(model.id, PRODUCT_RECONTEXT_MODELS) or 'recontext' in model_id

        elif mode in ['image-edit', 'image-outpainting', 'image-chat-edit', 'image-mask-edit',
                      'image-inpainting', 'image-background-edit', 'image-recontext']:
            # 图像编辑模式：支持 Imagen 编辑模型 + Gemini 视觉模型
            # ✅ 优先包含 Imagen 编辑专用模型
            if _matches_model_list(model.id, IMAGEN_EDIT_MODELS):
                should_include = True
            # ✅ 背景编辑模式包含产品重构模型
            elif mode in ['image-background-edit', 'image-recontext']:
                if _matches_model_list(model.id, PRODUCT_RECONTEXT_MODELS):
                    should_include = True
                elif 'veo' in model_id or not caps.vision:
                    should_include = False
                else:
                    is_text_to_image_only = any([
                        'wanx' in model_id, '-t2i' in model_id, 'z-image-turbo' in model_id,
                        'dall' in model_id, 'flux' in model_id, 'midjourney' in model_id,
                        _matches_model_list(model.id, IMAGEN_GENERATE_MODELS),
                        _matches_model_list(model.id, IMAGE_UPSCALE_MODELS),
                    ])
                    should_include = not is_text_to_image_only
            elif 'veo' in model_id or not caps.vision:
                should_include = False
            else:
                # 排除纯文生图模型
                is_text_to_image_only = any([
                    'wanx' in model_id, '-t2i' in model_id, 'z-image-turbo' in model_id,
                    'dall' in model_id, 'flux' in model_id, 'midjourney' in model_id,
                    _matches_model_list(model.id, IMAGEN_GENERATE_MODELS),
                    _matches_model_list(model.id, IMAGE_UPSCALE_MODELS),
                ])
                should_include = not is_text_to_image_only

        elif mode == 'virtual-try-on':
            # 虚拟试衣模式：优先虚拟试衣专用模型
            if _matches_model_list(model.id, VIRTUAL_TRY_ON_MODELS):
                should_include = True
            elif 'try-on' in model_id or 'tryon' in model_id:
                should_include = True
            else:
                # 回退到有视觉能力的模型
                should_include = (caps.vision and 'veo' not in model_id and
                                 not _matches_model_list(model.id, IMAGE_UPSCALE_MODELS) and
                                 not _matches_model_list(model.id, IMAGE_SEGMENTATION_MODELS))

        elif mode == 'deep-research':
            # 深度研究：需要搜索或推理能力
            should_include = caps.search or caps.reasoning

        elif mode == 'pdf-extract':
            # PDF 提取：排除专用媒体生成模型
            excluded_keywords = ['veo', 'tts', 'wanx', 'imagen', '-t2i', 'z-image',
                               'segmentation', 'upscale', 'try-on']
            should_include = not any(keyword in model_id for keyword in excluded_keywords)

        elif mode == 'chat' or not mode:
            # 标准聊天：排除所有专用媒体模型
            excluded_keywords = ['veo', 'tts', 'wanx', '-t2i', 'z-image', 'imagen',
                               'segmentation', 'upscale', 'try-on', 'recontext']
            embedding_keywords = ['embedding', 'aqa']
            is_media = any(keyword in model_id for keyword in excluded_keywords)
            is_embedding = any(keyword in model_id for keyword in embedding_keywords)
            should_include = not is_media and not is_embedding

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
    api_key: Optional[str] = Query(None, description="API key for the provider (optional, will use database config if not provided)"),
    base_url: Optional[str] = Query(None, description="Custom API URL"),
    use_cache: bool = Query(True, description="Whether to use cached models"),
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
        
        logger.info(f"[Models] Getting models for {provider}, user={user_id}, use_cache={use_cache}")
        start_time = time.time()
        
        from ...services.common.cache_service import CacheService
        cache_service: CacheService = cache
        
        # 生成缓存键（包含 user_id 和 provider，因为不同用户的 API Key 可能不同）
        cache_key = cache_service._make_key("models", provider, user_id)
        
        # 定义数据获取函数
        async def fetch_models():
            # Get credentials from database
            api_key_resolved, effective_base_url = await get_provider_credentials(
                provider, db, user_id, api_key, base_url
            )

            # Create provider service (使用顶部导入的 ProviderFactory)
            try:
                service = ProviderFactory.create(
                    provider=provider,
                    api_key=api_key_resolved,
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
        if use_cache:
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
