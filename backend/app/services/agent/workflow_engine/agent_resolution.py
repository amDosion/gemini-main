"""
Agent/profile/model selection helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import inspect
import json
import logging
import re
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

ACTIVE_INLINE_PROVIDER_TOKENS = {
    "__active__",
    "__current__",
    "active",
    "current",
    "active-profile",
    "current-profile",
}
AUTO_INLINE_MODEL_TOKENS = {
    "",
    "__auto__",
    "__active__",
    "auto",
    "active",
    "current",
    "active-profile",
    "current-profile",
}


def get_workflow_user_id(engine: Any) -> str:
    user_id = getattr(engine.llm_service, "user_id", "")
    return str(user_id or "").strip()


def extract_agent_card_defaults(engine: Any, agent: Any) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}
    raw_agent_card = getattr(agent, "agent_card_json", None)
    if not raw_agent_card:
        return defaults
    try:
        parsed_agent_card = json.loads(raw_agent_card)
        if isinstance(parsed_agent_card, dict):
            raw_defaults = parsed_agent_card.get("defaults")
            if isinstance(raw_defaults, dict):
                defaults = raw_defaults
    except Exception:
        logger.warning(
            "[WorkflowEngine] Failed to parse agent_card_json for agent %s",
            getattr(agent, "id", ""),
            exc_info=True,
        )
    return defaults


def extract_agent_llm_defaults(engine: Any, agent_card_defaults: Dict[str, Any]) -> Dict[str, Any]:
    _ = engine
    llm_defaults = agent_card_defaults.get("llm") if isinstance(agent_card_defaults, dict) else None
    if not isinstance(llm_defaults, dict):
        return {}
    return llm_defaults


def resolve_llm_default_value(engine: Any, payload: Dict[str, Any], *keys: str) -> Any:
    _ = engine
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


async def invoke_llm_chat(
    engine: Any,
    *,
    provider_id: str,
    model_id: str,
    messages: List[Dict[str, Any]],
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    profile_id: str = "",
) -> Dict[str, Any]:
    chat_method = getattr(engine.llm_service, "chat", None)
    if chat_method is None or not callable(chat_method):
        raise ValueError("llm_service.chat is not available")

    kwargs: Dict[str, Any] = {
        "provider_id": provider_id,
        "model_id": model_id,
        "messages": messages,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    normalized_profile_id = str(profile_id or "").strip()
    if normalized_profile_id:
        supports_profile_kwarg = False
        try:
            signature = inspect.signature(chat_method)
            for param in signature.parameters.values():
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    supports_profile_kwarg = True
                    break
            if not supports_profile_kwarg and "profile_id" in signature.parameters:
                supports_profile_kwarg = True
        except Exception:
            supports_profile_kwarg = True
        if supports_profile_kwarg:
            kwargs["profile_id"] = normalized_profile_id

    return await chat_method(**kwargs)


async def create_provider_service(engine: Any, provider_id: str, profile_id: str = "") -> Any:
    creator = getattr(engine, "_create_tool_provider_service", None)
    if creator is None or not callable(creator):
        raise ValueError("_create_tool_provider_service is not available")

    normalized_profile_id = str(profile_id or "").strip()
    if not normalized_profile_id:
        return await creator(provider_id)

    supports_profile_kwarg = False
    try:
        signature = inspect.signature(creator)
        for param in signature.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                supports_profile_kwarg = True
                break
        if not supports_profile_kwarg and "profile_id" in signature.parameters:
            supports_profile_kwarg = True
    except Exception:
        supports_profile_kwarg = True

    if supports_profile_kwarg:
        return await creator(provider_id=provider_id, profile_id=normalized_profile_id)
    return await creator(provider_id)


def is_active_inline_provider_token(engine: Any, value: Any) -> bool:
    _ = engine
    return str(value or "").strip().lower() in ACTIVE_INLINE_PROVIDER_TOKENS


def is_auto_inline_model_token(engine: Any, value: Any) -> bool:
    _ = engine
    return str(value or "").strip().lower() in AUTO_INLINE_MODEL_TOKENS


def should_resolve_inline_from_active_profile(
    engine: Any,
    *,
    node_data: Dict[str, Any],
    inline_provider_id: str,
    inline_model_id: str,
) -> bool:
    explicit_flag = engine._to_bool(
        node_data.get("inlineUseActiveProfile", node_data.get("inline_use_active_profile")),
        default=False,
    )
    if explicit_flag:
        return True
    return (
        engine._is_active_inline_provider_token(inline_provider_id)
        and engine._is_auto_inline_model_token(inline_model_id)
    )


def get_user_profiles(engine: Any, user_id: str) -> List[Any]:
    from ....models.db_models import ConfigProfile

    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id or engine.db is None:
        return []

    cached = engine._profiles_cache.get(normalized_user_id)
    if cached is not None:
        return cached

    profiles = engine.db.query(ConfigProfile).filter(
        ConfigProfile.user_id == normalized_user_id
    ).all()
    engine._profiles_cache[normalized_user_id] = profiles
    return profiles


def generate_workflow_frontend_session_id(engine: Any) -> str:
    user_id = engine._get_workflow_user_id()
    user_hint = re.sub(r"[^a-zA-Z0-9]+", "-", user_id).strip("-")[:16] or "workflow"
    return f"wf-{user_hint}-{uuid.uuid4().hex[:10]}"


def extract_model_version(engine: Any, model_id: str) -> float:
    _ = engine
    lowered = str(model_id or "").lower()
    numbers = re.findall(r"\d+(?:\.\d+)?", lowered)
    if not numbers:
        return 0.0
    try:
        return max(float(number) for number in numbers)
    except Exception:
        return 0.0


def looks_like_google_chat_image_edit_model(engine: Any, model_id: str) -> bool:
    _ = engine
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if "imagen" in lowered:
        return False
    if "gemini" in lowered and "image" in lowered:
        return True
    if any(token in lowered for token in ("flash-image", "pro-image", "nano-banana")):
        return True
    return False


def looks_like_image_generation_model(engine: Any, model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("veo", "sora", "luma", "video", "tts", "whisper", "embedding", "segmentation", "upscale", "try-on", "recontext")):
        return False
    if any(token in lowered for token in ("wan2.6-image", "qwen-image-edit", "-i2i")):
        return False
    if lowered.startswith("wan") and "image" in lowered and "-t2i" not in lowered:
        return False
    if any(token in lowered for token in ("capability", "ingredients", "edit", "inpaint", "outpaint")):
        return False
    return any(token in lowered for token in ("imagen", "image", "dall", "wanx", "-t2i", "z-image", "flux", "midjourney", "nano-banana"))


def looks_like_image_edit_model(engine: Any, model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if engine._looks_like_google_chat_image_edit_model(lowered):
        return True
    if any(token in lowered for token in ("wan2.6-image", "qwen-image-edit", "-i2i")):
        return True
    if lowered.startswith("wan") and "image" in lowered and "-t2i" not in lowered:
        return True
    if any(token in lowered for token in ("capability", "ingredients", "edit", "inpaint", "outpaint", "mask", "recontext")):
        return True
    if "imagen" in lowered and "generate" not in lowered:
        return True
    return False


def looks_like_video_generation_model(engine: Any, model_id: str) -> bool:
    _ = engine
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("veo", "sora", "luma")):
        return True
    return "video" in lowered and not any(token in lowered for token in ("vision", "audio", "speech", "whisper"))


def looks_like_audio_generation_model(engine: Any, model_id: str) -> bool:
    _ = engine
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("whisper", "asr", "transcribe", "transcription")):
        return False
    return lowered.startswith("tts") or "-tts" in lowered or "speech" in lowered


def looks_like_vision_understand_model(engine: Any, model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("veo", "sora", "luma", "video", "tts", "audio", "speech", "whisper", "embedding", "segmentation", "upscale")):
        return False
    if any(token in lowered for token in ("imagen", "wanx", "dall", "midjourney", "flux", "-t2i", "z-image", "wan2.6-image", "qwen-image-edit")):
        return False
    if engine._looks_like_google_chat_image_edit_model(lowered):
        return True
    if "gemini" in lowered and any(token in lowered for token in ("flash", "pro", "image")):
        return True
    if "-vl-" in lowered or lowered.endswith("-vl"):
        return True
    if any(token in lowered for token in ("gpt-4o", "claude-3", "qwen-vl", "qwen2-vl", "qwen2.5-vl")):
        return True
    return False


def looks_like_text_model(engine: Any, model_id: str) -> bool:
    _ = engine
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    blocked_tokens = (
        "imagen", "image", "wanx", "dall", "midjourney", "-t2i",
        "veo", "sora", "luma", "video", "tts", "whisper", "embedding", "segmentation", "upscale",
        "try-on", "tryon", "recontext", "inpaint", "outpaint",
        "edit", "mask", "aqa", "audio", "speech", "realtime", "live",
    )
    return not any(token in lowered for token in blocked_tokens)


def is_candidate_for_agent_task(
    engine: Any,
    model_id: str,
    agent_task_type: str,
    preferred_mode: str = "",
) -> bool:
    normalized_task = str(agent_task_type or "").strip().lower().replace("_", "-")
    normalized_mode = str(preferred_mode or "").strip().lower().replace("_", "-")

    if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
        return engine._looks_like_vision_understand_model(model_id)
    if normalized_task == "image-gen":
        return engine._looks_like_image_generation_model(model_id)
    if normalized_task == "image-edit":
        if normalized_mode == "image-chat-edit" and engine._looks_like_google_chat_image_edit_model(model_id):
            return True
        return engine._looks_like_image_edit_model(model_id)
    if normalized_task == "video-gen":
        return engine._looks_like_video_generation_model(model_id)
    if normalized_task == "audio-gen":
        return engine._looks_like_audio_generation_model(model_id)
    return engine._looks_like_text_model(model_id)


def rank_model_for_agent_task(
    engine: Any,
    model_id: str,
    agent_task_type: str,
    preferred_mode: str = "",
) -> Tuple[int, int, float]:
    lowered = str(model_id or "").lower()
    normalized_task = str(agent_task_type or "").strip().lower().replace("_", "-")
    normalized_mode = str(preferred_mode or "").strip().lower().replace("_", "-")
    preview_penalty = 1 if any(flag in lowered for flag in ("preview", "-exp", "_exp", "experimental")) else 0
    version_score = engine._extract_model_version(lowered)

    if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
        if engine._looks_like_google_chat_image_edit_model(lowered):
            family_rank = 0
        elif engine._looks_like_vision_understand_model(lowered):
            family_rank = 1
        else:
            family_rank = 9
        return (family_rank, preview_penalty, -version_score)

    if normalized_task == "image-gen":
        if "imagen" in lowered and "generate" in lowered:
            family_rank = 0
        elif any(token in lowered for token in ("-t2i", "wanx")):
            family_rank = 1
        elif "dall" in lowered:
            family_rank = 2
        elif "image" in lowered:
            family_rank = 3
        else:
            family_rank = 9
        return (family_rank, preview_penalty, -version_score)

    if normalized_task == "image-edit":
        if normalized_mode == "image-chat-edit" and engine._looks_like_google_chat_image_edit_model(lowered):
            family_rank = 0
        elif any(token in lowered for token in ("wan2.6-image", "qwen-image-edit", "-i2i")):
            family_rank = 1
        elif engine._looks_like_image_edit_model(lowered):
            family_rank = 2
        else:
            family_rank = 9
        return (family_rank, preview_penalty, -version_score)

    if normalized_task == "video-gen":
        if "veo-3.1" in lowered and "preview" in lowered:
            family_rank = 0
            preview_penalty = 0
        elif "veo-3.0" in lowered and "preview" in lowered:
            family_rank = 1
            preview_penalty = 0
        elif "veo" in lowered:
            family_rank = 2
        elif "sora" in lowered:
            family_rank = 3
        elif "luma" in lowered:
            family_rank = 4
        elif "video" in lowered:
            family_rank = 5
        else:
            family_rank = 9
        return (family_rank, preview_penalty, -version_score)

    if normalized_task == "audio-gen":
        if lowered.startswith("tts-1-hd"):
            family_rank = 0
        elif lowered.startswith("tts-1"):
            family_rank = 1
        elif "tts" in lowered:
            family_rank = 2
        elif "speech" in lowered:
            family_rank = 3
        else:
            family_rank = 9
        return (family_rank, preview_penalty, -version_score)

    if "gemini" in lowered and "2.5-pro" in lowered:
        family_rank = 0
    elif "gemini" in lowered and "2.5-flash" in lowered:
        family_rank = 1
    elif "gemini" in lowered and "2.0-flash" in lowered:
        family_rank = 2
    elif "gemini" in lowered:
        family_rank = 3
    else:
        family_rank = 4
    return (family_rank, preview_penalty, -version_score)


def list_saved_model_ids(engine: Any, profile: Any) -> List[str]:
    cache_profile_id = str(getattr(profile, "id", "") or f"obj-{id(profile)}")
    cache_updated_at = int(getattr(profile, "updated_at", 0) or 0)
    cache_key = f"{cache_profile_id}:{cache_updated_at}"
    cached = engine._saved_model_ids_cache.get(cache_key)
    if cached is not None:
        return list(cached)

    raw_models = getattr(profile, "saved_models", None) or []
    if isinstance(raw_models, str):
        try:
            raw_models = json.loads(raw_models)
        except Exception:
            raw_models = []

    model_ids: List[str] = []
    if isinstance(raw_models, list):
        for item in raw_models:
            if isinstance(item, dict):
                model_id = (item.get("id") or item.get("model_id") or "").strip()
            else:
                model_id = str(item or "").strip()
            if model_id:
                model_ids.append(model_id)
    engine._saved_model_ids_cache[cache_key] = list(model_ids)
    return model_ids


def get_default_image_model(engine: Any, provider_id: str, operation: str) -> str:
    _ = engine
    lowered = (provider_id or "").lower()
    if operation == "generate":
        if lowered.startswith("google"):
            return "imagen-3.0-generate-002"
        if lowered.startswith("openai"):
            return "dall-e-3"
        if lowered.startswith("tongyi") or lowered.startswith("dashscope"):
            return "wan2.6-t2i"
    else:
        if lowered.startswith("google"):
            return "imagen-3.0-capability-001"
        if lowered.startswith("tongyi") or lowered.startswith("dashscope"):
            return "wan2.6-image"
    return ""


def get_default_video_model(engine: Any, provider_id: str) -> str:
    _ = engine
    lowered = (provider_id or "").lower()
    if lowered.startswith("google"):
        return "veo-3.1-generate-preview"
    if lowered.startswith("openai"):
        return "sora-2"
    return ""


def get_default_audio_model(engine: Any, provider_id: str) -> str:
    _ = engine
    lowered = (provider_id or "").lower()
    if lowered.startswith("openai"):
        return "tts-1"
    return ""


def select_image_model(engine: Any, profile: Any, operation: str) -> str:
    model_ids = engine._list_saved_model_ids(profile)
    matcher = engine._looks_like_image_generation_model if operation == "generate" else engine._looks_like_image_edit_model
    for model_id in model_ids:
        if matcher(model_id):
            return model_id

    for model_id in model_ids:
        lowered = model_id.lower()
        if "image" in lowered or "imagen" in lowered or "wanx" in lowered or "dall" in lowered:
            return model_id

    default_model = engine._get_default_image_model(getattr(profile, "provider_id", ""), operation)
    if default_model:
        return default_model
    return model_ids[0] if model_ids else ""


def default_text_model_for_provider(engine: Any, provider_id: str) -> str:
    _ = engine
    lowered = str(provider_id or "").lower()
    if lowered.startswith("google"):
        return "gemini-2.5-flash"
    if lowered.startswith("openai"):
        return "gpt-4o-mini"
    if lowered.startswith("tongyi") or lowered.startswith("dashscope"):
        return "qwen-plus"
    if lowered.startswith("ollama"):
        return "llama3.1:8b"
    return ""


def select_text_chat_target(
    engine: Any,
    requested_provider: str = "",
    requested_model: str = "",
    requested_profile_id: str = "",
) -> Tuple[str, str]:
    from ....models.db_models import UserSettings

    user_id = engine._get_workflow_user_id()
    if not user_id:
        raise ValueError("无法识别当前用户，无法执行文本模型调用")

    profiles = engine._get_user_profiles(user_id)
    profiles = [profile for profile in profiles if getattr(profile, "api_key", None)]
    if not profiles:
        raise ValueError("未找到可用 Provider API Key，请先在设置中配置")

    normalized_profile_id = str(requested_profile_id or "").strip()
    if normalized_profile_id:
        profile_match = next(
            (
                profile for profile in profiles
                if str(getattr(profile, "id", "") or "").strip() == normalized_profile_id
            ),
            None,
        )
        if not profile_match:
            raise ValueError(f"未找到 Profile 配置：{requested_profile_id}")
        profiles = [profile_match]

    if requested_provider:
        requested = requested_provider.strip().lower()
        profiles = [
            profile for profile in profiles
            if (
                str(getattr(profile, "provider_id", "")).lower() == requested
                or str(getattr(profile, "provider_id", "")).lower().startswith(requested)
                or requested.startswith(str(getattr(profile, "provider_id", "")).lower())
            )
        ]
        if not profiles:
            raise ValueError(f"未找到 Provider 配置：{requested_provider}")
    else:
        settings = engine.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        active_profile_id = settings.active_profile_id if settings else None
        if active_profile_id:
            active = next((profile for profile in profiles if profile.id == active_profile_id), None)
            if active:
                profiles = [active] + [profile for profile in profiles if profile.id != active_profile_id]

    selected_profile = profiles[0]
    provider_id = str(getattr(selected_profile, "provider_id", "")).strip()
    model_ids = engine._list_saved_model_ids(selected_profile)

    if requested_model and requested_model.strip():
        return provider_id, requested_model.strip()

    for model_id in model_ids:
        if engine._looks_like_text_model(model_id):
            return provider_id, model_id

    if model_ids:
        return provider_id, model_ids[0]

    default_model = engine._default_text_model_for_provider(provider_id)
    if default_model:
        return provider_id, default_model
    raise ValueError(f"Provider {provider_id} 未找到可用文本模型")


def rank_provider_profiles_for_tool(
    engine: Any,
    requested_provider: str,
    operation: str,
    requested_profile_id: str = "",
) -> List[Any]:
    from ....models.db_models import UserSettings

    user_id = engine._get_workflow_user_id()
    if not user_id:
        raise ValueError("无法识别当前用户，无法执行图像工具")

    profiles = engine._get_user_profiles(user_id)
    profiles = [profile for profile in profiles if getattr(profile, "api_key", None)]
    if not profiles:
        raise ValueError("未找到可用 Provider API Key，请先在设置中配置")

    normalized_requested_profile_id = str(requested_profile_id or "").strip()
    preferred_profile = None
    if normalized_requested_profile_id:
        preferred_profile = next(
            (
                profile for profile in profiles
                if str(getattr(profile, "id", "") or "").strip() == normalized_requested_profile_id
            ),
            None,
        )
        if preferred_profile is None:
            raise ValueError(f"未找到 Profile 配置：{requested_profile_id}")

    def score(profile: Any) -> int:
        provider_id = str(getattr(profile, "provider_id", "")).lower()
        if operation == "generate":
            if any(engine._looks_like_image_generation_model(model_id) for model_id in engine._list_saved_model_ids(profile)):
                return 0
            if provider_id.startswith("google"):
                return 1
            if provider_id.startswith("openai"):
                return 2
            if provider_id.startswith("tongyi") or provider_id.startswith("dashscope"):
                return 3
            return 9

        if any(engine._looks_like_image_edit_model(model_id) for model_id in engine._list_saved_model_ids(profile)):
            return 0
        if provider_id.startswith("google"):
            return 1
        if provider_id.startswith("tongyi") or provider_id.startswith("dashscope"):
            return 2
        return 9

    if requested_provider:
        requested = requested_provider.strip().lower()
        if preferred_profile is not None:
            preferred_provider = str(getattr(preferred_profile, "provider_id", "") or "").strip().lower()
            if not (
                preferred_provider == requested
                or preferred_provider.startswith(requested)
                or requested.startswith(preferred_provider)
            ):
                raise ValueError(
                    f"Profile {requested_profile_id} 不匹配 Provider {requested_provider}"
                )
        matched = [
            profile for profile in profiles
            if (
                str(getattr(profile, "provider_id", "")).lower() == requested
                or str(getattr(profile, "provider_id", "")).lower().startswith(requested)
                or requested.startswith(str(getattr(profile, "provider_id", "")).lower())
            )
        ]
        if not matched:
            raise ValueError(f"未找到 Provider 配置：{requested_provider}")

        if preferred_profile is not None:
            preferred_score = score(preferred_profile)
            if preferred_score >= 9:
                raise ValueError(f"Profile {requested_profile_id} 不支持当前图像工具操作")
            matched = [preferred_profile] + [
                profile for profile in matched
                if str(getattr(profile, "id", "") or "").strip() != normalized_requested_profile_id
            ]

        ranked_matched = sorted(
            matched,
            key=lambda profile: (
                0 if normalized_requested_profile_id and str(getattr(profile, "id", "") or "").strip() == normalized_requested_profile_id else 1,
                score(profile),
                -int(getattr(profile, "updated_at", 0) or 0),
            ),
        )
        if score(ranked_matched[0]) >= 9:
            raise ValueError(f"Provider {requested_provider} 不支持当前图像工具操作")
        matched_ids = {str(getattr(profile, "id", "")) for profile in ranked_matched}
        ranked_fallback = sorted(
            [
                profile for profile in profiles
                if str(getattr(profile, "id", "")) not in matched_ids and score(profile) < 9
            ],
            key=lambda profile: (score(profile), -int(getattr(profile, "updated_at", 0) or 0))
        )
        return ranked_matched + ranked_fallback

    if preferred_profile is not None:
        preferred_score = score(preferred_profile)
        if preferred_score >= 9:
            raise ValueError(f"Profile {requested_profile_id} 不支持当前图像工具操作")
        ranked_fallback = sorted(
            [
                profile for profile in profiles
                if str(getattr(profile, "id", "") or "").strip() != normalized_requested_profile_id and score(profile) < 9
            ],
            key=lambda profile: (score(profile), -int(getattr(profile, "updated_at", 0) or 0)),
        )
        return [preferred_profile] + ranked_fallback

    settings = engine.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    active_profile_id = settings.active_profile_id if settings else None
    active_first: List[Any] = []
    if active_profile_id:
        active = next((profile for profile in profiles if profile.id == active_profile_id), None)
        if active and score(active) < 9:
            active_first = [active]

    ranked = sorted(
        [profile for profile in profiles if score(profile) < 9],
        key=lambda profile: (score(profile), -int(getattr(profile, "updated_at", 0) or 0))
    )
    if not ranked:
        raise ValueError("当前配置中没有可用于图像工具的 Provider")
    if active_first:
        active_id = str(getattr(active_first[0], "id", ""))
        return active_first + [profile for profile in ranked if str(getattr(profile, "id", "")) != active_id]
    return ranked


def select_provider_profile_for_tool(engine: Any, requested_provider: str, operation: str, requested_profile_id: str = "") -> Any:
    ranked_profiles = engine._rank_provider_profiles_for_tool(
        requested_provider=requested_provider,
        operation=operation,
        requested_profile_id=requested_profile_id,
    )
    if not ranked_profiles:
        raise ValueError("当前配置中没有可用于图像工具的 Provider")
    return ranked_profiles[0]


def is_usable_requested_image_model(engine: Any, model_id: str, operation: str) -> bool:
    normalized = str(model_id or "").strip()
    if not normalized:
        return False

    matcher = engine._looks_like_image_generation_model if operation == "generate" else engine._looks_like_image_edit_model
    if matcher(normalized):
        return True

    lowered = normalized.lower()
    if any(token in lowered for token in ("image", "imagen", "wanx", "dall", "flux", "midjourney")):
        return True
    if any(token in lowered for token in ("capability", "ingredients", "edit", "inpaint", "outpaint", "mask", "recontext")):
        return True

    if engine._looks_like_text_model(normalized):
        return False
    return True


def resolve_image_model_for_profile(engine: Any, profile: Any, operation: str, requested_model: str = "") -> str:
    preferred = str(requested_model or "").strip()
    if preferred and engine._is_usable_requested_image_model(preferred, operation=operation):
        return preferred
    return engine._select_image_model(profile, operation=operation)


def list_candidate_image_models(
    engine: Any,
    profile: Any,
    operation: str,
    requested_model: str = "",
    preferred_mode: str = "",
) -> List[str]:
    provider_id = str(getattr(profile, "provider_id", "") or "")
    saved_model_ids = engine._list_saved_model_ids(profile)
    matcher = engine._looks_like_image_generation_model if operation == "generate" else engine._looks_like_image_edit_model

    def is_image_like(model_id: str) -> bool:
        lowered = str(model_id or "").lower()
        if not lowered:
            return False
        if matcher(lowered):
            return True
        return any(
            token in lowered for token in (
                "image", "imagen", "wanx", "dall", "flux", "midjourney",
                "capability", "ingredients", "edit", "inpaint", "outpaint", "mask", "recontext",
            )
        )

    def rank_model(model_id: str) -> int:
        lowered = str(model_id or "").lower()
        penalty = 0
        if any(flag in lowered for flag in ("preview", "-exp", "_exp", "experimental")):
            penalty += 3
        if operation == "generate":
            if "imagen-3.0-generate" in lowered:
                base = 0
            elif "imagen" in lowered and "generate" in lowered:
                base = 1
            elif "wanx" in lowered or "dall" in lowered:
                base = 2
            elif "gemini" in lowered and "image" in lowered:
                base = 4
            elif "image" in lowered:
                base = 5
            else:
                base = 8
        else:
            if "imagen-3.0-capability" in lowered:
                base = 0
            elif "imagen" in lowered and any(token in lowered for token in ("capability", "ingredients", "edit")):
                base = 1
            elif "wanx" in lowered:
                base = 2
            elif any(token in lowered for token in ("edit", "inpaint", "outpaint", "mask", "recontext")):
                base = 3
            elif "image" in lowered:
                base = 5
            else:
                base = 8
        return base + penalty

    candidates: List[str] = []
    preferred = str(requested_model or "").strip()
    if preferred:
        candidates.append(preferred)

    image_like_saved = [model_id for model_id in saved_model_ids if is_image_like(model_id)]
    image_like_saved.sort(key=rank_model)
    candidates.extend(image_like_saved)

    default_model = engine._get_default_image_model(provider_id=provider_id, operation=operation)
    if default_model:
        candidates.append(default_model)

    dedup: List[str] = []
    seen = set()
    for model_id in candidates:
        normalized = str(model_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        dedup.append(normalized)

    normalized_mode = str(preferred_mode or "").strip().lower().replace("_", "-")
    if (
        operation == "edit"
        and normalized_mode == "image-chat-edit"
        and provider_id.lower().startswith("google")
    ):
        chat_models = [model_id for model_id in dedup if engine._looks_like_google_chat_image_edit_model(model_id)]
        if chat_models:
            return chat_models
        fallback_models = ["gemini-2.5-flash-image"]
        if preferred and preferred not in fallback_models:
            fallback_models.append(preferred)
        return fallback_models
    return dedup


async def create_tool_provider_service(engine: Any, provider_id: str, profile_id: str = "") -> Any:
    from ...common.provider_factory import ProviderFactory
    from ...llm.credentials_resolver import ProviderCredentialsResolver

    user_id = engine._get_workflow_user_id()
    if not user_id:
        raise ValueError("无法识别当前用户，无法加载 Provider 凭证")

    resolver = ProviderCredentialsResolver()
    api_key, base_url = await resolver.resolve(
        provider_id=provider_id,
        db=engine.db,
        user_id=user_id,
        profile_id=str(profile_id or "").strip() or None,
    )
    return ProviderFactory.create(
        provider=provider_id,
        api_key=api_key,
        api_url=base_url,
        user_id=user_id,
        db=engine.db,
    )


def select_profile_target_for_agent_task(
    engine: Any,
    *,
    agent_task_type: str,
    requested_provider: str = "",
    requested_model: str = "",
    requested_profile_id: str = "",
    preferred_mode: str = "",
) -> Tuple[str, str, str]:
    from ....models.db_models import UserSettings

    user_id = engine._get_workflow_user_id()
    if not user_id:
        raise ValueError("无法识别当前用户，无法为内联智能体解析 Provider")
    if engine.db is None:
        raise ValueError("当前工作流缺少数据库上下文，无法为内联智能体解析 Provider")

    profiles = engine._get_user_profiles(user_id)
    profiles = [profile for profile in profiles if getattr(profile, "api_key", None)]
    if not profiles:
        raise ValueError("未找到可用 Provider API Key，请先在设置中配置")

    normalized_task = str(agent_task_type or "").strip().lower().replace("_", "-") or "chat"
    normalized_requested_provider = str(requested_provider or "").strip().lower()
    normalized_requested_profile = str(requested_profile_id or "").strip()

    active_profile_id = ""
    settings = engine.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if settings and getattr(settings, "active_profile_id", None):
        active_profile_id = str(settings.active_profile_id or "").strip()

    if normalized_requested_profile:
        profile_match = next(
            (
                profile for profile in profiles
                if str(getattr(profile, "id", "") or "").strip() == normalized_requested_profile
            ),
            None,
        )
        if profile_match is None:
            raise ValueError(f"未找到 Profile 配置：{requested_profile_id}")
        profiles = [profile_match] + [
            profile for profile in profiles
            if str(getattr(profile, "id", "") or "").strip() != normalized_requested_profile
        ]

    if normalized_requested_provider:
        filtered_profiles = []
        for profile in profiles:
            profile_provider = str(getattr(profile, "provider_id", "") or "").strip().lower()
            if not profile_provider:
                continue
            if (
                profile_provider == normalized_requested_provider
                or profile_provider.startswith(normalized_requested_provider)
                or normalized_requested_provider.startswith(profile_provider)
            ):
                filtered_profiles.append(profile)
        if not filtered_profiles:
            raise ValueError(f"未找到 Provider 配置：{requested_provider}")
        profiles = filtered_profiles
    elif active_profile_id:
        active_profile = next(
            (
                profile for profile in profiles
                if str(getattr(profile, "id", "") or "").strip() == active_profile_id
            ),
            None,
        )
        if active_profile is not None:
            profiles = [active_profile] + [
                profile for profile in profiles
                if str(getattr(profile, "id", "") or "").strip() != active_profile_id
            ]

    candidate_rows: List[Tuple[Any, str, str]] = []
    for profile in profiles:
        provider_id = str(getattr(profile, "provider_id", "") or "").strip()
        if not provider_id:
            continue
        candidate_model = engine._resolve_preferred_model_for_agent_task(
            provider_id=provider_id,
            requested_model=str(requested_model or "").strip() if normalized_requested_provider else "",
            agent_task_type=normalized_task,
            preferred_mode=preferred_mode,
            preferred_profile_id=str(getattr(profile, "id", "") or "").strip(),
        )
        if not candidate_model:
            continue
        if not engine._is_candidate_for_agent_task(
            model_id=candidate_model,
            agent_task_type=normalized_task,
            preferred_mode=preferred_mode,
        ):
            continue
        candidate_rows.append((profile, provider_id, candidate_model))

    if not candidate_rows:
        if normalized_requested_provider:
            raise ValueError(
                f"Provider {requested_provider} 未找到支持任务 {normalized_task} 的模型"
            )
        raise ValueError(f"当前配置中没有可用于任务 {normalized_task} 的 Provider")

    candidate_rows.sort(
        key=lambda item: (
            0 if normalized_requested_profile and str(getattr(item[0], "id", "") or "").strip() == normalized_requested_profile else 1,
            0 if active_profile_id and str(getattr(item[0], "id", "") or "").strip() == active_profile_id else 1,
            engine._rank_model_for_agent_task(
                item[2],
                normalized_task,
                preferred_mode,
            ),
            -int(getattr(item[0], "updated_at", 0) or 0),
        )
    )
    chosen_profile, chosen_provider, chosen_model = candidate_rows[0]
    return (
        chosen_provider,
        chosen_model,
        str(getattr(chosen_profile, "id", "") or "").strip(),
    )


def resolve_preferred_model_for_agent_task(
    engine: Any,
    provider_id: str,
    requested_model: str,
    agent_task_type: str,
    preferred_mode: str = "",
    preferred_profile_id: str = "",
) -> str:
    user_id = engine._get_workflow_user_id()
    if not user_id or engine.db is None:
        return str(requested_model or "").strip()

    normalized_provider = str(provider_id or "").strip().lower()
    if not normalized_provider:
        return str(requested_model or "").strip()

    profiles = engine._get_user_profiles(user_id)

    matching_profiles = []
    for profile in profiles:
        if not getattr(profile, "api_key", None):
            continue
        profile_provider = str(getattr(profile, "provider_id", "") or "").strip().lower()
        if not profile_provider:
            continue
        if (
            profile_provider == normalized_provider
            or profile_provider.startswith(normalized_provider)
            or normalized_provider.startswith(profile_provider)
        ):
            matching_profiles.append(profile)

    if not matching_profiles:
        return str(requested_model or "").strip()

    matching_profiles.sort(key=lambda profile: -int(getattr(profile, "updated_at", 0) or 0))
    normalized_preferred_profile = str(preferred_profile_id or "").strip()
    if normalized_preferred_profile:
        preferred_profile = next(
            (
                profile for profile in matching_profiles
                if str(getattr(profile, "id", "") or "").strip() == normalized_preferred_profile
            ),
            None,
        )
        if preferred_profile is not None:
            matching_profiles = [
                preferred_profile,
                *[
                    profile for profile in matching_profiles
                    if str(getattr(profile, "id", "") or "").strip() != normalized_preferred_profile
                ],
            ]

    candidate_models: List[str] = []
    for profile in matching_profiles:
        for model_id in engine._list_saved_model_ids(profile):
            if engine._is_candidate_for_agent_task(
                model_id=model_id,
                agent_task_type=agent_task_type,
                preferred_mode=preferred_mode,
            ):
                candidate_models.append(model_id)

    normalized_task = str(agent_task_type or "").strip().lower().replace("_", "-")
    normalized_mode = str(preferred_mode or "").strip().lower().replace("_", "-")
    requested = str(requested_model or "").strip()
    requested_is_candidate = bool(
        requested and engine._is_candidate_for_agent_task(
            model_id=requested,
            agent_task_type=agent_task_type,
            preferred_mode=preferred_mode,
        )
    )
    if requested_is_candidate:
        candidate_models.append(requested)

    dedup: List[str] = []
    seen: Set[str] = set()
    for model_id in candidate_models:
        normalized = str(model_id or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        dedup.append(normalized)

    if not dedup:
        if normalized_task == "image-gen":
            fallback = engine._get_default_image_model(normalized_provider, operation="generate")
            return fallback or requested
        if normalized_task == "image-edit":
            if normalized_mode == "image-chat-edit" and normalized_provider.startswith("google"):
                return "gemini-3.1-flash-image-preview"
            fallback = engine._get_default_image_model(normalized_provider, operation="edit")
            return fallback or requested
        if normalized_task == "video-gen":
            fallback = engine._get_default_video_model(normalized_provider)
            return fallback or requested
        if normalized_task == "audio-gen":
            fallback = engine._get_default_audio_model(normalized_provider)
            return fallback or requested
        fallback = engine._default_text_model_for_provider(normalized_provider)
        return fallback or requested

    ranked = sorted(
        dedup,
        key=lambda model_id: engine._rank_model_for_agent_task(
            model_id=model_id,
            agent_task_type=agent_task_type,
            preferred_mode=preferred_mode,
        ),
    )
    chosen = ranked[0] if ranked else ""
    if chosen and engine._is_candidate_for_agent_task(
        model_id=chosen,
        agent_task_type=agent_task_type,
        preferred_mode=preferred_mode,
    ):
        return chosen

    if normalized_task == "image-gen":
        fallback = engine._get_default_image_model(normalized_provider, operation="generate")
        return fallback or requested
    if normalized_task == "image-edit":
        if normalized_mode == "image-chat-edit" and normalized_provider.startswith("google"):
            return "gemini-3.1-flash-image-preview"
        fallback = engine._get_default_image_model(normalized_provider, operation="edit")
        return fallback or requested
    if normalized_task == "video-gen":
        fallback = engine._get_default_video_model(normalized_provider)
        return fallback or requested
    if normalized_task == "audio-gen":
        fallback = engine._get_default_audio_model(normalized_provider)
        return fallback or requested
    fallback = engine._default_text_model_for_provider(normalized_provider)
    return fallback or requested


def build_inline_agent(engine: Any, *, node_id: str, node_data: Dict[str, Any]) -> Optional[Any]:
    inline_provider_id = str(
        node_data.get("inlineProviderId")
        or node_data.get("inline_provider_id")
        or node_data.get("providerId")
        or node_data.get("provider_id")
        or node_data.get("modelOverrideProviderId")
        or node_data.get("model_override_provider_id")
        or ""
    ).strip()
    inline_model_id = str(
        node_data.get("inlineModelId")
        or node_data.get("inline_model_id")
        or node_data.get("modelId")
        or node_data.get("model_id")
        or node_data.get("modelOverrideModelId")
        or node_data.get("model_override_model_id")
        or ""
    ).strip()
    inline_name = str(
        node_data.get("inlineAgentName")
        or node_data.get("inline_agent_name")
        or node_data.get("agentName")
        or node_data.get("agent_name")
        or node_data.get("label")
        or f"Inline Agent {node_id}"
    ).strip() or f"Inline Agent {node_id}"
    inline_prompt = str(
        node_data.get("inlineSystemPrompt")
        or node_data.get("inline_system_prompt")
        or node_data.get("agentSystemPrompt")
        or node_data.get("agent_system_prompt")
        or node_data.get("systemPrompt")
        or node_data.get("system_prompt")
        or ""
    ).strip()
    inline_description = str(
        node_data.get("description")
        or node_data.get("inlineDescription")
        or node_data.get("inline_description")
        or ""
    ).strip()
    inline_temperature = engine._to_float(
        node_data.get("agentTemperature", node_data.get("agent_temperature")),
        default=0.7,
    )
    inline_max_tokens = engine._to_int(
        node_data.get("agentMaxTokens", node_data.get("agent_max_tokens")),
        default=4096,
        minimum=1,
        maximum=65536,
    )
    inline_task_type = str(
        node_data.get("agentTaskType")
        or node_data.get("agent_task_type")
        or "chat"
    ).strip()
    normalized_task_type = inline_task_type.lower().replace("_", "-") if inline_task_type else "chat"
    inline_profile_id = str(
        node_data.get("inlineProfileId")
        or node_data.get("inline_profile_id")
        or node_data.get("modelOverrideProfileId")
        or node_data.get("model_override_profile_id")
        or ""
    ).strip()
    preferred_mode = str(
        node_data.get("agentEditMode")
        or node_data.get("agent_edit_mode")
        or ""
    ).strip()

    if engine._should_resolve_inline_from_active_profile(
        node_data=node_data,
        inline_provider_id=inline_provider_id,
        inline_model_id=inline_model_id,
    ):
        resolved_provider_id, resolved_model_id, resolved_profile_id = engine._select_profile_target_for_agent_task(
            agent_task_type=normalized_task_type,
            requested_profile_id=inline_profile_id,
            preferred_mode=preferred_mode,
        )
        if not inline_provider_id or engine._is_active_inline_provider_token(inline_provider_id):
            inline_provider_id = resolved_provider_id
        if not inline_model_id or engine._is_auto_inline_model_token(inline_model_id):
            inline_model_id = resolved_model_id
        inline_profile_id = inline_profile_id or resolved_profile_id

    if not inline_provider_id or not inline_model_id:
        return None

    defaults_payload: Dict[str, Any] = {
        "defaultTaskType": normalized_task_type,
    }
    if inline_profile_id:
        defaults_payload["llm"] = {
            "profileId": inline_profile_id,
        }
    inline_agent_card_json = json.dumps(
        {
            "defaults": defaults_payload,
        },
        ensure_ascii=False,
    )
    return SimpleNamespace(
        id=f"inline::{node_id}",
        user_id=engine._get_workflow_user_id(),
        name=inline_name,
        description=inline_description,
        agent_type="inline",
        provider_id=inline_provider_id,
        model_id=inline_model_id,
        system_prompt=inline_prompt,
        temperature=inline_temperature if inline_temperature is not None else 0.7,
        max_tokens=inline_max_tokens if inline_max_tokens is not None else 4096,
        icon=str(node_data.get("icon") or "🤖"),
        color=str(node_data.get("iconColor") or node_data.get("color") or "#14b8a6"),
        agent_card_json=inline_agent_card_json,
    )


def should_use_adk_runtime(engine: Any, agent: Any, provider_id: str, agent_task_type: str) -> bool:
    _ = engine
    normalized_provider = str(provider_id or "").strip().lower()
    if not normalized_provider.startswith("google"):
        return False

    normalized_task = str(agent_task_type or "").strip().lower().replace("_", "-")
    if normalized_task in {"image-gen", "image-edit", "video-gen", "audio-gen"}:
        return False

    agent_type = str(getattr(agent, "agent_type", "") or "").strip().lower()
    return agent_type in {"adk", "google-adk"}


async def run_adk_text_chat(
    engine: Any,
    *,
    agent: Any,
    provider_id: str,
    model_id: str,
    system_prompt: str,
    prompt: str,
    node_id: str,
    profile_id: str = "",
) -> Dict[str, Any]:
    from ...gemini.agent.adk_agent import ADKAgent
    from ..adk_builtin_tools import build_adk_builtin_tools
    from ...gemini.agent.adk_runner import ADKRunner
    from ...llm.credentials_resolver import ProviderCredentialsResolver

    user_id = engine._get_workflow_user_id()
    if not user_id:
        raise ValueError("workflow user_id is empty; cannot run ADK agent")

    resolver = ProviderCredentialsResolver()
    api_key, _ = await resolver.resolve(
        provider_id=provider_id,
        db=engine.db,
        user_id=user_id,
        profile_id=str(profile_id or "").strip() or None,
    )
    if not str(api_key or "").strip():
        raise ValueError(f"missing API key for provider: {provider_id}")

    adk_agent = ADKAgent(
        db=engine.db,
        model=str(model_id or "").strip(),
        name=str(getattr(agent, "name", "ADK Agent") or "ADK Agent"),
        instruction=system_prompt,
        tools=build_adk_builtin_tools(),
    )
    if not adk_agent.is_available:
        raise RuntimeError("google.adk SDK is not available in current runtime")

    session_id = f"{engine._generate_workflow_frontend_session_id()}-{re.sub(r'[^a-zA-Z0-9]+', '-', node_id)[:20]}"
    runner = ADKRunner(
        db=engine.db,
        agent_id=str(getattr(agent, "id", "") or ""),
        app_name="gemini-workflow-adk",
        adk_agent=adk_agent,
    )
    response = await runner.run_once(
        user_id=user_id,
        session_id=session_id,
        input_data=str(prompt or ""),
        google_api_key=str(api_key or "").strip(),
    )
    response["session_id"] = session_id
    return response
