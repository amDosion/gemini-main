"""
Model Capabilities Module

This module provides centralized model capability configuration.
It defines the data structures for model capabilities and provides
functions to infer capabilities based on provider and model ID.
"""

from pydantic import BaseModel
from typing import Optional
import re


class Capabilities(BaseModel):
    """Model capability configuration"""
    vision: bool = False      # Vision/multimodal capability
    search: bool = False      # Search/grounding capability
    reasoning: bool = False   # Reasoning/thinking capability
    coding: bool = False      # Code optimization capability


class ModelConfig(BaseModel):
    """Complete model configuration"""
    id: str                           # Model ID
    name: str                         # Display name
    description: str                  # Model description
    capabilities: Capabilities        # Capability configuration
    context_window: Optional[int] = None  # Context window size


def get_google_capabilities(model_id: str) -> Capabilities:
    """
    Get capabilities for Google models.

    Rules:
    - gemini-1.5-*, gemini-2.0-*, gemini-2.5-*, gemini-3.0-*: vision=true, search=true
    - *-thinking-*: vision=true, reasoning=true, search=false
    - gemini-2.5-pro, gemini-3.0-pro: vision=true, search=true, reasoning=true
    - deep-research-* (Deep Research models): search=true, reasoning=true
      - deep-research-pro-preview-12-2025: search=true, reasoning=true
      - deep-research-pro: search=true, reasoning=true
    - nano-banana-* (Nano-Banana series): vision=true, search=true, reasoning varies
      - nano-banana-pro-* (Nano-Banana Pro): vision=true, search=true, reasoning=true
      - nano-banana-* (Standard): vision=true, search=true, reasoning=false
    - gemini-*-image-* (Image generation/editing models): vision=true, search=true, reasoning varies
      - gemini-3-pro-image-preview: vision=true, search=true, reasoning=true
      - gemini-2.5-flash-image: vision=true, search=true, reasoning=false
    - imagen-*: vision=true only
    - *-code-*: coding=true only
    """
    lower_id = model_id.lower()

    vision = False
    search = False
    reasoning = False
    coding = False

    # Imagen models: vision only
    if lower_id.startswith("imagen"):
        return Capabilities(vision=True)

    # Code models: coding only
    if "-code-" in lower_id or lower_id.endswith("-code"):
        return Capabilities(coding=True)

    # Deep Research models: search + reasoning
    # These models are designed for deep research tasks with search and reasoning capabilities
    if "deep-research" in lower_id:
        return Capabilities(search=True, reasoning=True)

    # Thinking models: vision + reasoning, no search
    if "-thinking-" in lower_id or lower_id.endswith("-thinking"):
        return Capabilities(vision=True, reasoning=True)

    # Gemini 2.5-pro and 3.0-pro: all capabilities except coding
    if lower_id in ["gemini-2.5-pro", "gemini-3.0-pro", "gemini-2.5-pro-latest", "gemini-3.0-pro-latest"]:
        return Capabilities(vision=True, search=True, reasoning=True)

    # Gemini Image generation/editing models (Nano-Banana series)
    # These models support multimodal input/output with response_modalities=['TEXT', 'IMAGE']
    # and can use Google Search via tools=[{"google_search": {}}]
    
    # Nano-Banana models (explicit model IDs without -image- substring)
    # Example: nano-banana-pro-preview, nano-banana-pro, nano-banana-preview, nano-banana
    if "nano-banana" in lower_id:
        # Nano-Banana Pro: support thinking/reasoning
        if "pro" in lower_id:
            return Capabilities(vision=True, search=True, reasoning=True)
        # Standard Nano-Banana: vision + search only
        return Capabilities(vision=True, search=True)
    
    # Gemini models with -image- substring
    if "-image-" in lower_id or "-image" in lower_id:
        # Gemini 3.x Pro Image models: support thinking/reasoning
        # Example: gemini-3-pro-image-preview, gemini-3.0-pro-image-preview
        if ("gemini-3" in lower_id or "gemini-3.0" in lower_id) and "pro" in lower_id:
            return Capabilities(vision=True, search=True, reasoning=True)
        # Other image models: vision + search only
        # Example: gemini-2.5-flash-image, gemini-2.5-flash-image-preview
        return Capabilities(vision=True, search=True)

    # Standard Gemini models: vision + search
    # Extended to include Gemini 3.x series
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
    else:
        # Default: all false
        return Capabilities()


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


def build_model_config(provider: str, model_id: str) -> ModelConfig:
    """
    Build a complete ModelConfig from provider and model ID.
    
    Args:
        provider: Provider identifier
        model_id: Model ID
    
    Returns:
        Complete ModelConfig object
    """
    return ModelConfig(
        id=model_id,
        name=get_model_name(model_id),
        description=f"{provider.capitalize()} model: {model_id}",
        capabilities=get_model_capabilities(provider, model_id),
        context_window=get_context_window(provider, model_id)
    )
