"""
Models API Router

This module provides API endpoints for getting available models from all providers.
It supports caching to improve performance and reduce API calls.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple, Any, Dict
import logging
import time

from ...core.database import get_db
from ...models.db_models import ConfigProfile, UserSettings, VertexAIConfig
from ...services.common.model_capabilities import (
    ModelConfig,
    Capabilities,
    ModelTraits,
    build_model_config,
    get_model_traits,
)
from ...core.dependencies import require_current_user, get_cache
from ...services.common.google_model_catalog import (
    IMAGEN_GENERATE_MODELS,
    IMAGEN_EDIT_MODELS,
    IMAGE_UPSCALE_MODELS,
    IMAGE_SEGMENTATION_MODELS,
    VIRTUAL_TRY_ON_MODELS,
    PRODUCT_RECONTEXT_MODELS,
    get_static_google_vertex_models,
)
from ...core.mode_method_mapper import get_mode_catalog
from ..system.admin import require_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])

MODEL_CAPABILITY_CACHE_VERSION = "2026-03-05-v2"
UNSUPPORTED_GENERAL_MODEL_KEYWORDS = [
    "embedding",
    "aqa",
    "moderation",
    "realtime",
    "transcribe",
    "transcription",
    "whisper",
]


# Simple in-memory cache
# Format: {provider: {"models": [ModelConfig, ...], "timestamp": float}}
_model_cache: dict[str, dict[str, Any]] = {}
_cache_ttl = 3600  # 1 hour in seconds


# ==================== Helper Functions ====================

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

        elif mode == 'image-outpainting':
            # 图像扩展模式：支持编辑模型（扩图）+ 放大模型（upscale 子模式）
            # ✅ 包含编辑模型（用于 ratio, scale, offset 子模式）
            if _matches_model_list(model.id, IMAGEN_EDIT_MODELS):
                should_include = True
            # ✅ 包含放大模型（用于 upscale 子模式）
            elif _matches_model_list(model.id, IMAGE_UPSCALE_MODELS):
                should_include = True
            # ✅ 包含分割模型
            elif _matches_model_list(model.id, IMAGE_SEGMENTATION_MODELS):
                should_include = True
            elif 'veo' in model_id or not caps.vision:
                should_include = False
            else:
                # 排除纯文生图模型（但不排除放大模型）
                is_text_to_image_only = any([
                    'wanx' in model_id, '-t2i' in model_id, 'z-image-turbo' in model_id,
                    'dall' in model_id, 'flux' in model_id, 'midjourney' in model_id,
                    _matches_model_list(model.id, IMAGEN_GENERATE_MODELS),
                ])
                should_include = not is_text_to_image_only

        elif mode in ['image-edit', 'image-chat-edit', 'image-mask-edit',
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

        elif mode == 'pdf-extract':
            # PDF 提取：排除专用媒体生成模型
            excluded_keywords = ['veo', 'tts', 'wanx', 'wan2', 'imagen', '-t2i', 'z-image',
                               'segmentation', 'upscale', 'try-on']
            is_media = any(keyword in model_id for keyword in excluded_keywords)
            is_unsupported_general = any(keyword in model_id for keyword in UNSUPPORTED_GENERAL_MODEL_KEYWORDS)
            should_include = not is_media and not is_unsupported_general

        elif mode in ['chat', 'multi-agent'] or not mode:
            # 标准聊天：排除所有专用媒体模型
            excluded_keywords = ['veo', 'tts', 'wanx', 'wan2', '-t2i', 'z-image', 'imagen',
                               'segmentation', 'upscale', 'try-on', 'recontext']
            is_media = any(keyword in model_id for keyword in excluded_keywords)
            is_unsupported_general = any(keyword in model_id for keyword in UNSUPPORTED_GENERAL_MODEL_KEYWORDS)
            should_include = not is_media and not is_unsupported_general

        else:
            # 未知模式：不过滤
            should_include = True

        if should_include:
            filtered.append(model)

    return filtered


def _get_effective_profile(provider: str, db: Session, user_id: str) -> Optional[ConfigProfile]:
    """
    获取当前 provider 对应的生效配置：
    1) 当前激活 profile（若 provider 匹配）
    2) 任意同 provider profile（按更新时间倒序）
    """
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None

    if active_profile_id:
        active_profile = db.query(ConfigProfile).filter(
            ConfigProfile.id == active_profile_id,
            ConfigProfile.provider_id == provider,
            ConfigProfile.user_id == user_id
        ).first()
        if active_profile:
            return active_profile

    return db.query(ConfigProfile).filter(
        ConfigProfile.provider_id == provider,
        ConfigProfile.user_id == user_id
    ).order_by(ConfigProfile.updated_at.desc()).first()


def _get_profile_cache_scope(provider: str, db: Session, user_id: str) -> str:
    """
    为模型缓存生成 profile 维度作用域，避免不同 profile 之间缓存串用。
    """
    profile = _get_effective_profile(provider, db, user_id)
    profile_scope = "no-profile"
    if profile:
        profile_scope = f"{profile.id}:{int(profile.updated_at or 0)}"

    if provider != "google":
        return f"{profile_scope}|caps:{MODEL_CAPABILITY_CACHE_VERSION}"

    vertex_config = _get_vertex_ai_config(db, user_id)
    if not vertex_config:
        return f"{profile_scope}|no-vertex|caps:{MODEL_CAPABILITY_CACHE_VERSION}"

    vertex_updated_ms = 0
    if vertex_config.updated_at:
        try:
            vertex_updated_ms = int(vertex_config.updated_at.timestamp() * 1000)
        except Exception:
            vertex_updated_ms = 0

    return (
        f"{profile_scope}|"
        f"vertex:{vertex_config.id}:{vertex_config.api_mode}:{vertex_updated_ms}|"
        f"caps:{MODEL_CAPABILITY_CACHE_VERSION}"
    )


def _normalize_context_window(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_trait_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _extract_raw_traits(raw_model: Dict[str, Any]) -> Dict[str, bool]:
    raw_traits = raw_model.get("traits")
    if not isinstance(raw_traits, dict):
        return {}

    return {
        "multimodal_understanding": _normalize_trait_bool(
            raw_traits.get("multimodal_understanding", raw_traits.get("multimodalUnderstanding", False))
        ),
        "deep_research": _normalize_trait_bool(
            raw_traits.get("deep_research", raw_traits.get("deepResearch", False))
        ),
        "thinking": _normalize_trait_bool(raw_traits.get("thinking", False)),
    }


def _build_merged_traits(
    provider: str,
    model_id: str,
    model_name: str,
    capabilities: Capabilities,
    raw_traits: Dict[str, bool],
) -> ModelTraits:
    inferred_traits = get_model_traits(
        provider=provider,
        model_id=model_id,
        capabilities=capabilities,
        model_name=model_name,
    )
    return ModelTraits(
        multimodal_understanding=inferred_traits.multimodal_understanding or raw_traits.get("multimodal_understanding", False),
        deep_research=inferred_traits.deep_research or raw_traits.get("deep_research", False),
        thinking=inferred_traits.thinking or raw_traits.get("thinking", False),
    )


def _ensure_model_traits(provider: str, model: ModelConfig) -> ModelConfig:
    inferred_traits = get_model_traits(
        provider=provider,
        model_id=model.id,
        capabilities=model.capabilities,
        model_name=model.name,
    )
    existing_traits = model.traits or ModelTraits()
    merged_traits = ModelTraits(
        multimodal_understanding=inferred_traits.multimodal_understanding or existing_traits.multimodal_understanding,
        deep_research=inferred_traits.deep_research or existing_traits.deep_research,
        thinking=inferred_traits.thinking or existing_traits.thinking,
    )
    if model.traits == merged_traits:
        return model
    return model.model_copy(update={"traits": merged_traits})


def _get_vertex_ai_config(db: Session, user_id: str) -> Optional[VertexAIConfig]:
    return db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()


def _parse_saved_models(raw_saved_models: Any) -> List[dict]:
    if not raw_saved_models:
        return []
    if isinstance(raw_saved_models, list):
        return [item for item in raw_saved_models if isinstance(item, dict)]
    return []


def _extract_saved_model_ids(raw_saved_models: Any) -> List[str]:
    model_ids: List[str] = []
    for item in _parse_saved_models(raw_saved_models):
        model_id = str(item.get("id") or item.get("model_id") or "").strip()
        if model_id:
            model_ids.append(model_id)
    return model_ids


def _merge_saved_models(
    provider: str,
    models: List[ModelConfig],
    raw_saved_models: Any,
    source: str
) -> List[ModelConfig]:
    """
    合并 saved_models 到 provider 返回模型。
    - 已存在模型：以 saved_models 补充描述/能力
    - 不存在模型：直接加入（保证 UI 可见）
    """
    saved_models = _parse_saved_models(raw_saved_models)
    if not saved_models:
        return models

    merged: Dict[str, ModelConfig] = {m.id: m for m in models}
    added = 0
    updated = 0

    for raw_model in saved_models:
        model_id = str(raw_model.get("id") or "").strip()
        if not model_id:
            continue

        raw_caps = raw_model.get("capabilities")
        caps_dict = raw_caps if isinstance(raw_caps, dict) else {}
        raw_traits = _extract_raw_traits(raw_model)
        context_window = (
            _normalize_context_window(raw_model.get("context_window"))
            or _normalize_context_window(raw_model.get("contextWindow"))
        )

        if model_id in merged:
            existing = merged[model_id]
            merged_name = str(raw_model.get("name") or existing.name)
            merged_capabilities = Capabilities(
                # 仅允许 saved_models "补充" 能力，不允许旧缓存降级能力
                vision=existing.capabilities.vision or bool(caps_dict.get("vision", False)),
                search=existing.capabilities.search or bool(caps_dict.get("search", False)),
                reasoning=existing.capabilities.reasoning or bool(caps_dict.get("reasoning", False)),
                coding=existing.capabilities.coding or bool(caps_dict.get("coding", False)),
            )
            merged[model_id] = ModelConfig(
                id=existing.id,
                name=merged_name,
                description=str(raw_model.get("description") or existing.description),
                capabilities=merged_capabilities,
                traits=_build_merged_traits(
                    provider=provider,
                    model_id=existing.id,
                    model_name=merged_name,
                    capabilities=merged_capabilities,
                    raw_traits=raw_traits,
                ),
                context_window=context_window if context_window is not None else existing.context_window,
            )
            updated += 1
            continue

        inferred = build_model_config(provider, model_id)
        merged_name = str(raw_model.get("name") or model_id)
        merged_capabilities = Capabilities(
            # 仅允许 saved_models 补充能力，不允许旧缓存覆盖推断能力。
            vision=bool(caps_dict.get("vision", False)) or inferred.capabilities.vision,
            search=bool(caps_dict.get("search", False)) or inferred.capabilities.search,
            reasoning=bool(caps_dict.get("reasoning", False)) or inferred.capabilities.reasoning,
            coding=bool(caps_dict.get("coding", False)) or inferred.capabilities.coding,
        )
        merged[model_id] = ModelConfig(
            id=model_id,
            name=merged_name,
            description=str(raw_model.get("description") or f"Model: {model_id}"),
            capabilities=merged_capabilities,
            traits=_build_merged_traits(
                provider=provider,
                model_id=model_id,
                model_name=merged_name,
                capabilities=merged_capabilities,
                raw_traits=raw_traits,
            ),
            context_window=context_window if context_window is not None else inferred.context_window,
        )
        added += 1

    if added or updated:
        logger.info(
            f"[Models] merged saved_models ({source}): +{added}, updated={updated}"
        )

    return list(merged.values())


def _merge_google_vertex_static_models(provider: str, models: List[ModelConfig]) -> List[ModelConfig]:
    """
    Merge Google API + Vertex static model catalog in backend as a single source.
    """
    if provider != "google":
        return models

    existing_ids = {m.id for m in models}
    merged = list(models)

    for model_id in get_static_google_vertex_models():
        if model_id in existing_ids:
            continue
        merged.append(build_model_config("google", model_id))
        existing_ids.add(model_id)

    return merged


def _build_mode_catalog(
    models: List[ModelConfig],
    preferred_model_ids: List[str],
) -> List[dict]:
    """
    Build provider model-availability catalog for frontend navigation.
    """
    catalog_items: List[dict] = []
    for item in get_mode_catalog(include_internal=False):
        filter_mode = str(item.get("filter_mode") or item["id"])
        available_models = filter_models_by_mode(models, filter_mode)
        catalog_items.append({
            **item,
            "has_models": len(available_models) > 0,
            "available_model_count": len(available_models),
            "default_model_id": _select_default_model_id(available_models, preferred_model_ids),
        })
    return catalog_items


def _build_preferred_model_ids(
    provider: str,
    effective_profile: Optional[ConfigProfile],
    vertex_config: Optional[VertexAIConfig]
) -> List[str]:
    preferred_ids: List[str] = []
    seen: set[str] = set()

    profile_ids = _extract_saved_model_ids(
        effective_profile.saved_models if effective_profile else None
    )
    for model_id in profile_ids:
        if model_id in seen:
            continue
        seen.add(model_id)
        preferred_ids.append(model_id)

    if provider == "google" and vertex_config:
        vertex_ids = _extract_saved_model_ids(vertex_config.saved_models)
        for model_id in vertex_ids:
            if model_id in seen:
                continue
            seen.add(model_id)
            preferred_ids.append(model_id)

    return preferred_ids


def _select_default_model_id(
    filtered_models: List[ModelConfig],
    preferred_model_ids: List[str]
) -> Optional[str]:
    if not filtered_models:
        return None

    model_ids = {m.id for m in filtered_models}
    for preferred_id in preferred_model_ids:
        if preferred_id in model_ids:
            return preferred_id

    return filtered_models[0].id


def _resolve_mode_filtered_models(
    models: List[ModelConfig],
    mode: Optional[str],
) -> List[ModelConfig]:
    """
    Resolve the models exposed for a requested mode.

    The visible models for a mode are determined only by the provider's
    saved model set and the backend mode filter. Runtime executability is
    reported separately and must not hide models that are already present
    in the profile database.
    """
    if not mode:
        return models

    return filter_models_by_mode(models, str(mode))


def _resolve_mode_view(
    models: List[ModelConfig],
    preferred_model_ids: List[str],
    *,
    mode: Optional[str] = None,
) -> Tuple[List[dict], List[ModelConfig], Optional[str]]:
    """
    Single-source mode resolution for both navigation state and model exposure.

    Returns:
        mode_catalog: provider-wide mode catalog with model-set availability
        filtered_models: models exposed for the requested mode (or all models)
        default_model_id: default model for the filtered result set
    """
    mode_catalog = _build_mode_catalog(
        models=models,
        preferred_model_ids=preferred_model_ids,
    )
    filtered_models = _resolve_mode_filtered_models(models, mode)
    default_model_id = _select_default_model_id(filtered_models, preferred_model_ids)
    return mode_catalog, filtered_models, default_model_id


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
    effective_profile = _get_effective_profile(provider, db, user_id)
    if effective_profile and effective_profile.api_key:
        logger.info(
            f"[Models] Using API key from profile '{effective_profile.name}' for {provider}"
        )
        api_key = _decrypt_api_key(effective_profile.api_key, silent=True)
        return api_key, effective_profile.base_url

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
    use_cache: bool = Query(True, description="Whether to use cached models"),
    api_key: Optional[str] = Query(None, description="Override API key for verification requests"),
    base_url: Optional[str] = Query(None, description="Override base URL for verification requests"),
    mode: Optional[str] = Query(None, description="Filter models by app mode (chat, image-edit, image-gen, etc.)"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    """
    Get available models for a provider.

    模型过滤 (mode 参数):
    - 如果指定了 mode，后端会根据模式过滤模型列表
    - 支持的模式: chat, image-edit, image-gen, image-outpainting, video-gen, audio-gen, virtual-try-on, pdf-extract
    - 示例: /api/models/google?mode=image-edit

    Returns:
        {
            "models": [ModelConfig, ...],  # List of complete model configurations
            "cached": bool,
            "provider": str,
            "filtered_by_mode": str | null,  # 如果应用了过滤，返回模式名称
            "default_model_id": str | null,  # 当前返回模型列表对应的默认模型
            "mode_catalog": [ ... ]          # provider/profile 模型集合下的模式模型可用性
        }
    """
    try:
        # user_id 已通过依赖注入自动获取

        is_verify_request = bool(api_key or base_url)
        # Verify 请求必须实时拉取，避免旧缓存导致假结果
        if is_verify_request and use_cache:
            use_cache = False

        logger.info(f"[Models] Getting models for {provider}, user={user_id}, use_cache={use_cache}")
        start_time = time.time()

        from ...services.common.cache_service import CacheService
        cache_service: CacheService = cache

        # 生成缓存键（包含生效 profile 范围，避免不同 profile 串缓存）
        profile_scope = _get_profile_cache_scope(provider, db, user_id)
        cache_key = cache_service._make_key("models", provider, user_id, profile_scope)

        # 定义数据获取函数
        async def fetch_models():
            # Verify 模式：实时调用 Provider 接口获取模型列表
            if is_verify_request:
                provider_api_key, provider_base_url = await get_provider_credentials(
                    provider=provider,
                    db=db,
                    user_id=user_id,
                    request_api_key=api_key,
                    request_base_url=base_url
                )

                from ...services.common.provider_factory import ProviderFactory
                service = ProviderFactory.create(
                    provider=provider,
                    api_key=provider_api_key,
                    api_url=provider_base_url,
                    user_id=user_id,
                    db=db,
                    timeout=60.0
                )
                live_models = await service.get_available_models()
                return [model.model_dump() for model in live_models]

            # 普通模式：DB-only，不调用 provider 接口，只返回数据库 saved_models
            models: List[ModelConfig] = []
            effective_profile = _get_effective_profile(provider, db, user_id)
            models = _merge_saved_models(
                provider=provider,
                models=models,
                raw_saved_models=effective_profile.saved_models if effective_profile else None,
                source=f"profile:{effective_profile.id if effective_profile else 'none'}"
            )

            vertex_config = _get_vertex_ai_config(db, user_id) if provider == "google" else None
            if vertex_config:
                models = _merge_saved_models(
                    provider=provider,
                    models=models,
                    raw_saved_models=vertex_config.saved_models,
                    source=f"vertex:{vertex_config.id}"
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
                models = [ModelConfig(**m) for m in cached_models_dict]
                logger.info(f"[Models] ✅ 返回缓存模型: {len(models)} 个模型 (耗时: {time.time() - start_time:.2f}s)")
            except Exception as e:
                logger.warning(f"[Models] 缓存获取失败，使用直接查询: {e}")
                models_dict = await fetch_models()
                models = [ModelConfig(**m) for m in models_dict]
                logger.info(f"[Models] ✅ 直接查询结果: {len(models)} 个模型")
        else:
            # 不使用缓存，直接获取
            models_dict = await fetch_models()
            models = [ModelConfig(**m) for m in models_dict]
            logger.info(f"[Models] ✅ 直接查询结果（无缓存）: {len(models)} 个模型")

        # 后端统一计算 traits，前端优先消费该字段，仅在缺失时做最小兼容 fallback。
        models = [_ensure_model_traits(provider, model) for model in models]

        effective_profile = _get_effective_profile(provider, db, user_id)
        vertex_config = _get_vertex_ai_config(db, user_id) if provider == "google" else None
        preferred_model_ids = _build_preferred_model_ids(provider, effective_profile, vertex_config)
        # 过滤用户隐藏的模型（Verify 请求跳过，显示全部模型供选择）
        hidden_ids = set()
        if not is_verify_request and effective_profile and hasattr(effective_profile, 'hidden_models') and effective_profile.hidden_models:
            raw_hidden = effective_profile.hidden_models
            if isinstance(raw_hidden, list):
                hidden_ids = set(raw_hidden)
            if hidden_ids:
                models = [m for m in models if m.id not in hidden_ids]
                logger.debug(f"[Models] Filtered {len(hidden_ids)} hidden models, {len(models)} remaining")

        all_provider_models = models

        mode_catalog, filtered_models, default_model_id = _resolve_mode_view(
            models=all_provider_models,
            preferred_model_ids=preferred_model_ids,
            mode=mode,
        )
        if mode:
            logger.debug(f"[Models] Applying mode filter: {mode}")
            logger.debug(f"[Models] Filtered {len(all_provider_models)} -> {len(filtered_models)} models for mode={mode}")

        # Convert to dict for JSON response
        models_dict = [model.model_dump() for model in filtered_models]

        elapsed = time.time() - start_time
        logger.debug(f"[Models] ========== 请求完成 ==========")
        logger.info(f"[Models] 提供商: {provider}")
        logger.debug(f"[Models] 最终返回模型数: {len(filtered_models)} 个")
        logger.debug(f"[Models] 是否使用缓存: {was_cached}")
        logger.debug(f"[Models] 是否应用模式过滤: {mode if mode else '否'}")
        logger.debug(f"[Models] 总耗时: {elapsed:.2f}s")
        logger.debug(f"[Models] =================================")

        return {
            "models": models_dict,
            "cached": was_cached,
            "provider": provider,
            "filtered_by_mode": mode if mode else None,
            "profile_scope": profile_scope,
            "default_model_id": default_model_id,
            "mode_catalog": mode_catalog
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
    # 缓存键格式: cache:models:{provider}:{user_id}:{profile_scope}
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
async def clear_all_model_cache(
    _: str = Depends(require_admin_user),
    cache = Depends(get_cache)
):
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
async def get_cache_status(_: str = Depends(require_current_user)):
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
