"""
Model Capabilities Module

This module provides centralized model capability configuration.
It defines the data structures for model capabilities and provides
functions to infer capabilities based on provider and model ID.
"""

from pydantic import BaseModel
from typing import Optional, Any, Dict, List, Sequence, Tuple
import re


class Capabilities(BaseModel):
    """Model capability configuration"""
    vision: bool = False      # Vision/multimodal capability
    search: bool = False      # Search/grounding capability
    reasoning: bool = False   # Reasoning/thinking capability
    coding: bool = False      # Code optimization capability


class ModelTraits(BaseModel):
    """Computed model traits used by frontend model selection."""
    multimodal_understanding: bool = False
    deep_research: bool = False
    thinking: bool = False


class ModelConfig(BaseModel):
    """Complete model configuration"""
    id: str                           # Model ID
    name: str                         # Display name
    description: str                  # Model description
    capabilities: Capabilities        # Capability configuration
    context_window: Optional[int] = None  # Context window size
    traits: Optional[ModelTraits] = None  # Optional traits for frontend decision logic


_NON_MULTIMODAL_UNDERSTANDING_KEYWORDS: Tuple[str, ...] = (
    "imagen",
    "veo",
    "sora",
    "luma",
    "tts",
    "audio",
    "speech",
    "image-segmentation",
    "segmentation",
    "virtual-try-on",
    "try-on",
    "tryon",
    "recontext",
    "upscale",
    "wanx",
    "wan2",
    "-t2i",
    "z-image",
    "dall",
    "flux",
    "midjourney",
    "automl",
    "earth-ai",
    "embedding",
    "aqa",
    "native-audio",
    "computer-use",
    "image-generation",
    "-image",
    "customtools",
)


def get_google_capabilities(model_id: str) -> Capabilities:
    """
    Get capabilities for Google models.

    Rules:
    - gemini-1.5-*, gemini-2.0-*, gemini-2.5-*, gemini-3.0-*: vision=true, search=true
    - *-thinking-*: vision=true, reasoning=true, search=false
    - gemini-2.5-pro, gemini-3.0-pro: vision=true, search=true, reasoning=true
    - deep-research-* (Deep Research models): search=true, reasoning=true
    - nano-banana-* (Nano-Banana series): vision=true, search=true, reasoning varies
    - gemini-*-image-* (Image generation/editing models): vision=true, search=true
      - gemini-3.x image models: reasoning=true (supports thinking)
    - imagen-*-generate-*: vision=true (image generation)
    - imagen-*-capability-*: vision=true (image editing)
    - imagen-*-upscale-*: vision=true (image upscaling)
    - imagen-product-recontext-*: vision=true (product recontext)
    - image-segmentation-*: vision=true (image segmentation)
    - virtual-try-on-*: vision=true (virtual try-on)
    - *-code-*: coding=true only
    """
    lower_id = model_id.lower()

    vision = False
    search = False
    reasoning = False
    coding = False

    # === Specialized Vertex AI Models (Image/Media Processing) ===

    # Image Segmentation models: vision only
    if "segmentation" in lower_id:
        return Capabilities(vision=True)

    # Virtual Try-On models: vision only
    if "try-on" in lower_id or "tryon" in lower_id:
        return Capabilities(vision=True)

    # Product Recontext models: vision only
    if "recontext" in lower_id:
        return Capabilities(vision=True)

    # Imagen models with specific capabilities
    if lower_id.startswith("imagen") or "imagen" in lower_id:
        # Upscale models: vision only
        if "upscale" in lower_id:
            return Capabilities(vision=True)
        # Capability/edit models: vision only
        if "capability" in lower_id or "ingredients" in lower_id:
            return Capabilities(vision=True)
        # Generate models: vision only
        if "generate" in lower_id:
            return Capabilities(vision=True)
        # Default imagen: vision only
        return Capabilities(vision=True)

    # Code models: coding only
    if "-code-" in lower_id or lower_id.endswith("-code"):
        return Capabilities(coding=True)

    # Deep Research models: search + reasoning
    if "deep-research" in lower_id:
        return Capabilities(search=True, reasoning=True)

    # Thinking models: vision + reasoning, no search
    if "-thinking-" in lower_id or lower_id.endswith("-thinking"):
        return Capabilities(vision=True, reasoning=True)

    # Gemini 2.5-pro and 3.0-pro: all capabilities except coding
    if lower_id in ["gemini-2.5-pro", "gemini-3.0-pro", "gemini-2.5-pro-latest", "gemini-3.0-pro-latest"]:
        return Capabilities(vision=True, search=True, reasoning=True)

    # Nano-Banana models
    if "nano-banana" in lower_id:
        # Nano-Banana Pro: support thinking/reasoning
        if "pro" in lower_id:
            return Capabilities(vision=True, search=True, reasoning=True)
        # Standard Nano-Banana: vision + search only
        return Capabilities(vision=True, search=True)

    # Gemini models with -image- substring
    if "-image-" in lower_id or "-image" in lower_id:
        # Gemini 3.x image models (including flash/pro preview): support thinking/reasoning
        if "gemini-3" in lower_id:
            return Capabilities(vision=True, search=True, reasoning=True)
        # Other image models: vision + search only
        return Capabilities(vision=True, search=True)

    # Standard Gemini models: vision + search
    if lower_id.startswith("gemini-3."):
        vision = True
        search = True

    gemini_patterns = ["gemini-1.5", "gemini-2.0", "gemini-2.5", "gemini-3.0", "gemini-3-", "gemini-pro", "gemini-flash"]
    for pattern in gemini_patterns:
        if pattern in lower_id:
            vision = True
            search = True
            break

    return Capabilities(vision=vision, search=search, reasoning=reasoning, coding=coding)


def get_qwen_capabilities(model_id: str) -> Capabilities:
    """
    Get capabilities for Qwen models.

    Rules:
    - *-vl-* or ends with -vl: vision=true
    - qwq-* or *-thinking: reasoning=true
    - qwen-* (not vl/wanx): search=true
    - qwen-coder-*: search=true, coding=true
    - wanx* / wan2*: vision=true (image generation)
    - qwen-image-edit-*, qwen-*-image-*: vision=true (image editing)
    - qwen-deep-research: search=true, reasoning=true
    """
    lower_id = model_id.lower()

    vision = False
    search = False
    reasoning = False
    coding = False

    # Vision models: -vl- or ends with -vl
    if "-vl-" in lower_id or lower_id.endswith("-vl"):
        vision = True

    # Image generation models: wanx* or wan2*
    if lower_id.startswith("wanx") or lower_id.startswith("wan2"):
        vision = True

    # Image editing models: qwen-image-edit-*, qwen-*-image-*
    # Example: qwen-image-edit-plus, qwen-plus-image-editor (if exists)
    if "image-edit" in lower_id or ("qwen" in lower_id and "-image-" in lower_id):
        vision = True

    # Reasoning models: qwq-* or *-thinking
    if lower_id.startswith("qwq") or "-thinking" in lower_id or lower_id.endswith("-thinking"):
        reasoning = True

    # Deep research: search + reasoning
    if "deep-research" in lower_id:
        search = True
        reasoning = True

    # Coder models: search + coding
    if "coder" in lower_id:
        search = True
        coding = True
    
    # Standard Qwen models: search (if not vl/wanx/wan2)
    if lower_id.startswith("qwen") and not vision and "coder" not in lower_id:
        search = True
    
    return Capabilities(vision=vision, search=search, reasoning=reasoning, coding=coding)


def get_openai_capabilities(model_id: str) -> Capabilities:
    """
    Get capabilities for OpenAI models.

    Rules:
    - gpt-4o*, gpt-4-turbo*, gpt-4-vision*: vision=true
    - o1*, o3*, o4*: reasoning=true
    - *-code*, codex*: coding=true
    - dall-e*: vision=true (image generation)
    """
    lower_id = model_id.lower()

    vision = False
    search = False
    reasoning = False
    coding = False

    # Image generation models
    if lower_id.startswith("dall-e") or lower_id.startswith("dalle"):
        return Capabilities(vision=True)

    # TTS/Audio models
    if lower_id.startswith("tts") or "audio" in lower_id or "whisper" in lower_id:
        return Capabilities()

    # Reasoning models: o1, o3, o4 series
    if lower_id.startswith("o1") or lower_id.startswith("o3") or lower_id.startswith("o4"):
        reasoning = True
        # o1/o3/o4 pro and full versions have vision
        if "pro" in lower_id or not lower_id.endswith("-mini"):
            vision = True

    # Vision models: gpt-4o, gpt-4-turbo, gpt-4-vision
    if "gpt-4o" in lower_id or "gpt-4-turbo" in lower_id or "gpt-4-vision" in lower_id:
        vision = True

    # Coding models
    if "-code" in lower_id or lower_id.startswith("codex") or "codex" in lower_id:
        coding = True

    return Capabilities(vision=vision, search=search, reasoning=reasoning, coding=coding)


def get_ollama_capabilities(model_id: str) -> Capabilities:
    """
    Get capabilities for Ollama models.

    Rules:
    - *vision*, *-vl-*, *llava*: vision=true
    - *code*, *coder*, *starcoder*: coding=true
    - *deepseek-r1*, *qwq*: reasoning=true
    """
    lower_id = model_id.lower()

    vision = False
    reasoning = False
    coding = False

    # Vision models
    if "vision" in lower_id or "-vl" in lower_id or "llava" in lower_id or "bakllava" in lower_id:
        vision = True

    # Reasoning models
    if "deepseek-r1" in lower_id or lower_id.startswith("qwq"):
        reasoning = True

    # Coding models
    if "code" in lower_id or "coder" in lower_id or "starcoder" in lower_id:
        coding = True

    return Capabilities(vision=vision, reasoning=reasoning, coding=coding)



def get_grok_capabilities(model_id: str) -> Capabilities:
    """
    Get capabilities for Grok models.

    Rules:
    - grok-3*, grok-4*: vision=true (chat models with image understanding)
    - *-thinking*, *-expert*, *-heavy*, *-mini*: reasoning=true
    - grok-imagine-*: vision=true (image/video generation)
    """
    lower_id = model_id.lower()

    vision = False
    search = False
    reasoning = False
    coding = False

    # Image and video generation models
    if "imagine" in lower_id:
        return Capabilities(vision=True)

    # Thinking/reasoning models
    if "thinking" in lower_id or "expert" in lower_id or "heavy" in lower_id or "mini" in lower_id:
        reasoning = True
        vision = True
        return Capabilities(vision=vision, reasoning=reasoning)

    # Standard chat models (grok-3, grok-4, etc.)
    if lower_id.startswith(("grok-3", "grok-4")):
        vision = True

    return Capabilities(vision=vision, search=search, reasoning=reasoning, coding=coding)


def get_generic_capabilities(model_id: str) -> Capabilities:
    """
    Generic capability inference for unknown providers.
    Uses common model naming conventions.
    """
    lower_id = model_id.lower()

    vision = False
    search = False
    reasoning = False
    coding = False

    # Vision
    if "vision" in lower_id or "-vl" in lower_id or "gpt-4o" in lower_id:
        vision = True

    # Reasoning
    if "thinking" in lower_id or lower_id.startswith("o1") or lower_id.startswith("o3"):
        reasoning = True

    # Coding
    if "code" in lower_id or "coder" in lower_id:
        coding = True

    return Capabilities(vision=vision, search=search, reasoning=reasoning, coding=coding)


def get_model_capabilities(provider: str, model_id: str) -> Capabilities:
    """
    Get capabilities for a model based on provider and model ID.

    Args:
        provider: Provider identifier (google, tongyi, openai, etc.)
        model_id: Model ID

    Returns:
        Capabilities object
    """
    provider_lower = provider.lower()

    if provider_lower == "google":
        return get_google_capabilities(model_id)
    elif provider_lower in ["tongyi", "qwen"]:
        return get_qwen_capabilities(model_id)
    elif provider_lower == "openai":
        return get_openai_capabilities(model_id)
    elif provider_lower == "ollama":
        return get_ollama_capabilities(model_id)
    elif provider_lower == "grok":
        return get_grok_capabilities(model_id)
    else:
        # 对于未知 provider，尝试通用关键词匹配
        return get_generic_capabilities(model_id)


def is_multimodal_understanding_model(
    provider: str,
    model_id: str,
    capabilities: Optional[Capabilities] = None,
) -> bool:
    """
    Determine whether model is suitable for multimodal understanding tasks.

    This mirrors legacy frontend filtering rules and is now centralized in backend.
    """
    _ = provider  # reserved for provider-specific expansion
    lower_id = (model_id or "").lower().strip()
    if not lower_id or "gemini" not in lower_id:
        return False

    caps = capabilities if capabilities is not None else get_model_capabilities(provider, model_id)
    if not caps.vision:
        return False

    return not any(keyword in lower_id for keyword in _NON_MULTIMODAL_UNDERSTANDING_KEYWORDS)


def is_deep_research_model(provider: str, model_id: str) -> bool:
    """
    Determine whether a model can be used as a Deep Research agent.

    Deep Research agents must be explicit deep-research models. This avoids
    silently routing to regular chat/reasoning models.
    """
    provider_lower = (provider or "").lower()
    lower_id = (model_id or "").lower().strip()
    if not lower_id:
        return False

    # Current providers expose dedicated Deep Research models via id naming.
    if provider_lower in {"google", "google-custom", "tongyi", "qwen"}:
        return "deep-research" in lower_id

    return "deep-research" in lower_id


def get_model_traits(
    provider: str,
    model_id: str,
    capabilities: Optional[Capabilities] = None,
    model_name: Optional[str] = None,
) -> ModelTraits:
    """
    Compute frontend-facing traits in backend as a single source of truth.
    """
    caps = capabilities if capabilities is not None else get_model_capabilities(provider, model_id)
    lower_name = str(model_name or "").strip().lower()
    deep_research = is_deep_research_model(provider, model_id) or ("deep research" in lower_name)

    return ModelTraits(
        multimodal_understanding=is_multimodal_understanding_model(provider, model_id, caps),
        deep_research=deep_research,
        thinking=bool(caps.reasoning),
    )


def get_model_name(model_id: str) -> str:
    """
    Generate a display name from model ID.
    
    Args:
        model_id: Model ID
    
    Returns:
        Human-readable display name
    """
    # Replace hyphens and underscores with spaces, capitalize words
    name = model_id.replace("-", " ").replace("_", " ")
    return " ".join(word.capitalize() for word in name.split())


def get_model_description(provider: str, model_id: str) -> str:
    """
    Generate a meaningful description from model ID.
    
    Args:
        provider: Provider identifier (google, tongyi, etc.)
        model_id: Model ID
    
    Returns:
        Human-readable description
    """
    lower_id = model_id.lower()
    
    # Google models
    if provider.lower() == "google":
        # Imagen models (image generation)
        if "imagen" in lower_id:
            if "4.0" in lower_id:
                if "ultra" in lower_id:
                    return "Advanced image generation model with high quality output"
                elif "fast" in lower_id:
                    return "Fast image generation model optimized for speed"
                else:
                    return "Latest image generation model with enhanced quality"
            elif "3.0" in lower_id:
                if "capability" in lower_id:
                    return "Image editing and manipulation capabilities"
                else:
                    return "High-quality image generation model"
            else:
                return "Image generation model for creating images from text"
        
        # Veo models (video generation)
        if "veo" in lower_id:
            if "3.1" in lower_id:
                if "fast" in lower_id:
                    return "Fast video generation model optimized for speed"
                else:
                    return "Latest video generation model with enhanced quality"
            elif "3.0" in lower_id:
                if "fast" in lower_id:
                    return "Fast video generation model optimized for speed"
                else:
                    return "Video generation model for creating videos from text"
            elif "2.0" in lower_id:
                return "Video generation model for creating videos from text"
            else:
                return "Video generation model for creating videos from text"
        
        # Gemini Image models (multimodal image generation/editing)
        if "gemini" in lower_id and ("image" in lower_id or "-i-" in lower_id):
            if "gemini-3" in lower_id:
                return "Advanced multimodal image generation and editing with reasoning"
            elif "2.5" in lower_id:
                return "Fast multimodal image generation and editing"
            elif "2.0" in lower_id:
                return "Multimodal image generation and editing"
            else:
                return "Multimodal image generation and editing model"
        
        # Gemini models (chat/multimodal)
        if "gemini" in lower_id:
            if "3.0" in lower_id or "3.1" in lower_id or "3-" in lower_id:
                if "pro" in lower_id:
                    return "Advanced multimodal model with vision, search, and reasoning"
                else:
                    return "Latest multimodal model with enhanced capabilities"
            elif "2.5" in lower_id:
                if "pro" in lower_id:
                    return "Advanced multimodal model with vision, search, and reasoning"
                elif "flash" in lower_id:
                    # 检查是否有特殊变体（lite, preview等）
                    if "lite" in lower_id:
                        return "Lightweight fast multimodal model with vision and search"
                    elif "preview" in lower_id:
                        return "Preview version - Fast multimodal model with vision and search"
                    else:
                        return "Fast multimodal model with vision and search"
                else:
                    return "Multimodal model with advanced capabilities"
            elif "2.0" in lower_id:
                if "flash" in lower_id:
                    if "exp" in lower_id:
                        return "Experimental fast multimodal model"
                    else:
                        return "Fast multimodal model with vision capabilities"
                else:
                    return "Multimodal model with standard capabilities"
            elif "1.5" in lower_id:
                if "pro" in lower_id:
                    return "Advanced multimodal model with large context window (1M tokens)"
                elif "flash" in lower_id:
                    return "Fast multimodal model with standard capabilities"
                else:
                    return "Multimodal model with standard capabilities"
            elif "pro" in lower_id:
                return "Advanced multimodal model with enhanced capabilities"
            elif "flash" in lower_id:
                return "Fast multimodal model optimized for speed"
            else:
                return "Multimodal AI model for text and vision tasks"
        
        # Embedding models
        if "embedding" in lower_id or "gecko" in lower_id:
            return "Text embedding for semantic search and similarity"
        
        # Deep Research models
        if "deep-research" in lower_id:
            if "pro" in lower_id:
                return "Advanced research model with search and reasoning capabilities"
            else:
                return "Research model with search and reasoning capabilities"
        
        # Thinking models
        if "thinking" in lower_id:
            return "Advanced reasoning model with thinking capabilities"
        
        # Code models
        if "code" in lower_id:
            return "Specialized model for code generation and optimization"
        
        # Nano-Banana models
        if "nano-banana" in lower_id:
            if "pro" in lower_id:
                return "Advanced multimodal model with vision, search, and reasoning"
            else:
                return "Multimodal model with vision and search capabilities"
        
        # Default for Google models
        return f"AI model for various tasks"
    
    # Qwen/Tongyi models
    elif provider.lower() in ["tongyi", "qwen"]:
        if "qwen" in lower_id:
            if "vl" in lower_id or lower_id.endswith("-vl"):
                return "Qwen Vision-Language Model - Multimodal model with vision capabilities"
            elif "coder" in lower_id:
                return "Qwen Coder - Code generation and optimization model"
            elif "deep-research" in lower_id:
                return "Qwen Deep Research - Research model with search and reasoning"
            elif "thinking" in lower_id:
                return "Qwen Thinking - Advanced reasoning model"
            elif "wanx" in lower_id or "wan2" in lower_id:
                return "Qwen WanX - Image generation model"
            elif "image-edit" in lower_id:
                return "Qwen Image Edit - Image editing model"
            else:
                return f"Qwen AI model: {model_id}"
        else:
            return f"Tongyi AI model: {model_id}"
    
    # Default
    return f"{provider.capitalize()} AI model: {model_id}"


def get_context_window(provider: str, model_id: str) -> Optional[int]:
    """
    Get context window size for a model.
    
    Args:
        provider: Provider identifier
        model_id: Model ID
    
    Returns:
        Context window size or None if unknown
    """
    lower_id = model_id.lower()
    
    # Google models
    if provider.lower() == "google":
        if "gemini-1.5" in lower_id or "gemini-2" in lower_id:
            return 1000000  # 1M tokens
        if "gemini-pro" in lower_id:
            return 32768
    
    # Qwen models
    if provider.lower() in ["tongyi", "qwen"]:
        if "qwen2.5" in lower_id or "qwen-2.5" in lower_id:
            return 131072  # 128K
        if "qwen2" in lower_id or "qwen-2" in lower_id:
            return 32768
        if "qwen-long" in lower_id:
            return 10000000  # 10M
    
    return None


def build_model_config(provider: str, model_id: str, display_name: str = None) -> ModelConfig:
    """
    Build a complete ModelConfig from provider and model ID.
    
    Args:
        provider: Provider identifier
        model_id: Model ID
    
    Returns:
        Complete ModelConfig object
    """
    model_name = display_name if display_name else get_model_name(model_id)
    capabilities = get_model_capabilities(provider, model_id)
    return ModelConfig(
        id=model_id,
        name=model_name,
        description=get_model_description(provider, model_id),
        capabilities=capabilities,
        context_window=get_context_window(provider, model_id),
        traits=get_model_traits(
            provider=provider,
            model_id=model_id,
            capabilities=capabilities,
            model_name=model_name,
        ),
    )


# =============================================================================
# Runtime Mode Capability (Provider + Mode)
# =============================================================================

_PROVIDER_ALIASES: Dict[str, str] = {
    "google-custom": "google",
}

# Modes implemented at router/runtime layer rather than provider service methods.
_ROUTE_IMPLEMENTED_MODES = {
    "multi-agent",
}

# Known unsupported provider/mode combos.
_KNOWN_UNSUPPORTED: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("tongyi", "video-gen"): (
        "mode_not_implemented",
        "Tongyi provider does not support video generation yet.",
    ),
    ("tongyi", "audio-gen"): (
        "mode_not_implemented",
        "Tongyi provider does not support audio generation yet.",
    ),
}

# Google modes that require Vertex AI configuration.
_GOOGLE_VERTEX_REQUIRED_MODES = {
    "image-mask-edit",
    "image-inpainting",
    "image-background-edit",
    "image-recontext",
    "image-outpainting",
    "virtual-try-on",
}


def _normalize_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(value, value)


def _resolve_google_vertex_state(
    db: Optional[Any],
    user_id: Optional[str],
) -> Dict[str, Any]:
    state = {
        "api_mode": "gemini_api",
        "vertex_ready": False,
        "has_project_id": False,
        "has_credentials": False,
    }
    if not db or not user_id:
        return state

    try:
        from ...models.db_models import VertexAIConfig
    except Exception:
        return state

    cfg = db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()
    if not cfg:
        return state

    api_mode = str(cfg.api_mode or "gemini_api").strip().lower()
    has_project = bool(cfg.vertex_ai_project_id)
    has_credentials = bool(cfg.vertex_ai_credentials_json)

    state["api_mode"] = api_mode
    state["has_project_id"] = has_project
    state["has_credentials"] = has_credentials
    state["vertex_ready"] = api_mode == "vertex_ai" and has_project and has_credentials
    return state


def _get_provider_service_class(provider: str):
    from .provider_factory import ProviderFactory

    if not ProviderFactory._initialized:
        ProviderFactory._auto_register()
    return ProviderFactory._providers.get(provider)


def _evaluate_mode_capability(
    provider: str,
    mode_item: Dict[str, Any],
    service_class: Any,
    google_vertex_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    mode_id = str(mode_item.get("id") or "").strip()
    method_name = str(mode_item.get("service_method") or "").strip()

    result: Dict[str, Any] = {
        "mode": mode_id,
        "runtime_enabled": True,
        "provider_method": method_name,
        "reason_code": None,
        "reason": None,
        "required_api_mode": None,
    }

    if service_class is None:
        result["runtime_enabled"] = False
        result["reason_code"] = "provider_not_registered"
        result["reason"] = f"Provider '{provider}' is not registered."
        return result

    if mode_id in _ROUTE_IMPLEMENTED_MODES:
        result["provider_method"] = "workflow_runtime"
        return result

    method = getattr(service_class, method_name, None) if method_name else None
    if not callable(method):
        result["runtime_enabled"] = False
        result["reason_code"] = "provider_method_missing"
        result["reason"] = (
            f"Provider '{provider}' does not expose method '{method_name}' for mode '{mode_id}'."
        )
        return result

    unsupported = _KNOWN_UNSUPPORTED.get((provider, mode_id))
    if unsupported:
        code, reason = unsupported
        result["runtime_enabled"] = False
        result["reason_code"] = code
        result["reason"] = reason
        return result

    if provider == "google" and mode_id in _GOOGLE_VERTEX_REQUIRED_MODES:
        api_mode = str((google_vertex_state or {}).get("api_mode") or "gemini_api").lower()
        vertex_ready = bool((google_vertex_state or {}).get("vertex_ready"))
        result["required_api_mode"] = "vertex_ai"

        if api_mode != "vertex_ai":
            result["runtime_enabled"] = False
            result["reason_code"] = "requires_vertex_ai"
            result["reason"] = (
                f"Mode '{mode_id}' requires Vertex AI configuration (current api_mode={api_mode})."
            )
            return result

        if not vertex_ready:
            result["runtime_enabled"] = False
            result["reason_code"] = "vertex_config_incomplete"
            result["reason"] = (
                "Vertex AI mode is enabled but project_id/credentials are incomplete."
            )
            return result

    return result


def build_provider_mode_capabilities(
    provider: str,
    db: Optional[Any] = None,
    user_id: Optional[str] = None,
    mode_catalog: Optional[Sequence[Dict[str, Any]]] = None,
    include_internal: bool = False,
) -> Dict[str, Any]:
    """
    Build the dedicated runtime capability snapshot for provider modes.

    This snapshot is intentionally separate from model-availability catalogs
    returned by `/api/models` and `/api/init/critical`.
    """
    normalized_provider = _normalize_provider(provider)

    if mode_catalog is None:
        from ...core.mode_method_mapper import get_mode_catalog
        catalog_items = get_mode_catalog(include_internal=include_internal)
    else:
        catalog_items = [dict(item) for item in mode_catalog]

    service_class = _get_provider_service_class(normalized_provider)
    google_vertex_state = (
        _resolve_google_vertex_state(db=db, user_id=user_id)
        if normalized_provider == "google"
        else None
    )

    mode_results: Dict[str, Dict[str, Any]] = {}
    for mode_item in catalog_items:
        capability = _evaluate_mode_capability(
            provider=normalized_provider,
            mode_item=mode_item,
            service_class=service_class,
            google_vertex_state=google_vertex_state,
        )
        mode_id = str(mode_item.get("id") or "")
        if mode_id:
            mode_results[mode_id] = capability

    snapshot: Dict[str, Any] = {
        "provider": provider,
        "normalized_provider": normalized_provider,
        "modes": mode_results,
    }

    if normalized_provider == "google":
        snapshot["api_mode"] = google_vertex_state.get("api_mode") if google_vertex_state else "gemini_api"
        snapshot["vertex_ready"] = bool(google_vertex_state and google_vertex_state.get("vertex_ready"))
        snapshot["has_project_id"] = bool(google_vertex_state and google_vertex_state.get("has_project_id"))
        snapshot["has_credentials"] = bool(google_vertex_state and google_vertex_state.get("has_credentials"))

    return snapshot
