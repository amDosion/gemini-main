"""
Provider parameter whitelist validation.

Validate user-supplied option/extra keys before provider method invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, Optional, Set


INVALID_PROVIDER_PARAMS_CODE = "invalid_provider_params"


def _snake_to_camel(name: str) -> str:
    if not name:
        return name
    if "_" not in name:
        return name
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _camel_to_snake(name: str) -> str:
    if not name:
        return name
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _expand_key_aliases(keys: Iterable[str]) -> Set[str]:
    expanded: Set[str] = set()
    for key in keys:
        if not key:
            continue
        expanded.add(key)
        expanded.add(_snake_to_camel(key))
        expanded.add(_camel_to_snake(key))
    return {key for key in expanded if key}


_CHAT_OPTION_KEYS = _expand_key_aliases(
    {
        "base_url",
        "temperature",
        "max_tokens",
        "top_p",
        "top_k",
        "enable_search",
        "enable_thinking",
        "enable_code_execution",
        "enable_browser",
        "enable_grounding",
        "persona_id",
        "mcp_server_key",
        # Keep compatibility for provider-specific chat flags.
        "plugins",
        "connection_mode",
        "client_preference",
        "operation_type",
    }
)

_OPENAI_STANDARD_CHAT_OPTION_KEYS = _expand_key_aliases(
    {
        # Standard OpenAI chat completion params.
        "frequency_penalty",
        "presence_penalty",
        "seed",
        "stop",
        "response_format",
        "logit_bias",
        "n",
        "user",
    }
)

# Provider-level extension map for chat params.
# New providers can be added here without changing validation flow.
_PROVIDER_CHAT_OPTION_EXTRAS: Dict[str, Set[str]] = {
    "openai": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "openrouter": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "deepseek": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "siliconflow": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "moonshot": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "zhipu": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "doubao": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "hunyuan": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "nvidia": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
    "ollama": _OPENAI_STANDARD_CHAT_OPTION_KEYS,
}

_MODE_OPTION_KEYS = _expand_key_aliases(
    {
        "base_url",
        "temperature",
        "max_tokens",
        "top_p",
        "top_k",
        "enable_search",
        "enable_thinking",
        "enable_code_execution",
        "enable_browser",
        "enable_grounding",
        "size",
        "quality",
        "style",
        "resolution",
        "seconds",
        "number_of_images",
        "aspect_ratio",
        "image_aspect_ratio",
        "image_resolution",
        "image_style",
        "edit_mode",
        "frontend_session_id",
        "session_id",
        "message_id",
        "active_image_url",
        "negative_prompt",
        "guidance_scale",
        "mask_dilation",
        "seed",
        "output_mime_type",
        "output_format",
        "output_compression_quality",
        "enhance_prompt",
        "enhance_prompt_model",
        "prompt_extend",
        "add_magic_suffix",
        "outpaint_mode",
        "x_scale",
        "y_scale",
        "left_offset",
        "right_offset",
        "top_offset",
        "bottom_offset",
        "output_ratio",
        "upscale_factor",
        "layers",
        "canvas_w",
        "canvas_h",
        "max_text_boxes",
        "locale",
        "layer_doc",
        "simplify_tolerance",
        "smooth_iterations",
        "use_bezier",
        "bezier_smoothness",
        "threshold",
        "blur_radius",
        "voice",
        "base_steps",
        "mask_mode",
        "seconds",
        "duration_seconds",
        "video_extension_count",
        "storyboard_shot_seconds",
        "generate_audio",
        "person_generation",
        "subtitle_mode",
        "subtitle_language",
        "subtitle_script",
        "storyboard_prompt",
        "tracked_feature",
        "tracking_overlay_text",
        "source_video",
        "continuation_video",
        "source_image",
        "last_frame_image",
        "use_last_frame_bridge",
        "video_mask_image",
        "video_mask_mode",
        "provider_file_name",
        "provider_file_uri",
        "gcs_uri",
        "delete_target",
    }
)

_MODE_EXTRA_KEYS = _expand_key_aliases(
    {
        # Known extra payload keys used by current mode services/workflows.
        "workflow",
        "messages",
        "target_clothing",
        "template_type",
        "additional_instructions",
        "pdf_bytes",
        "pdf_url",
        "n",
        "num_images",
        "number_of_images",
        "negative_prompt",
        "prompt_extend",
        "add_magic_suffix",
        "enhance_prompt",
        "enhance_prompt_model",
        "mask_dilation",
        "guidance_scale",
        "output_mime_type",
        "output_format",
        "output_compression_quality",
        "x_scale",
        "y_scale",
        "left_offset",
        "right_offset",
        "top_offset",
        "bottom_offset",
        "output_ratio",
        "upscale_factor",
        "angle",
        "watermark",
        "response_format",
        "voice",
        "base_steps",
        "mask_mode",
        "seconds",
        "duration_seconds",
        "video_extension_count",
        "storyboard_shot_seconds",
        "generate_audio",
        "person_generation",
        "subtitle_mode",
        "subtitle_language",
        "subtitle_script",
        "storyboard_prompt",
        "tracked_feature",
        "tracking_overlay_text",
        "source_video",
        "continuation_video",
        "source_image",
        "last_frame_image",
        "use_last_frame_bridge",
        "video_mask_image",
        "video_mask_mode",
        "provider_file_name",
        "provider_file_uri",
        "gcs_uri",
        "delete_target",
    }
)

_MODE_ALLOWED_KEYS = _MODE_OPTION_KEYS | _MODE_EXTRA_KEYS


@dataclass(frozen=True)
class ProviderParamValidationError(Exception):
    provider: str
    scope: str
    invalid_params: tuple[str, ...]
    allowed_params: tuple[str, ...]

    @property
    def message(self) -> str:
        return (
            f"Invalid provider params for provider='{self.provider}', scope='{self.scope}': "
            f"{', '.join(self.invalid_params)}"
        )

    def to_http_detail(self) -> Dict[str, Any]:
        return {
            "code": INVALID_PROVIDER_PARAMS_CODE,
            "message": self.message,
            "details": {
                "provider": self.provider,
                "scope": self.scope,
                "invalid_params": list(self.invalid_params),
                "allowed_params": list(self.allowed_params),
            },
        }


def _normalize_keys(keys: Optional[Iterable[Any]]) -> Set[str]:
    if not keys:
        return set()
    normalized: Set[str] = set()
    for key in keys:
        if isinstance(key, str) and key:
            normalized.add(key)
    return normalized


def _raise_if_invalid(
    *,
    provider: str,
    scope: str,
    keys: Set[str],
    allowed_keys: Set[str],
) -> None:
    invalid = sorted(key for key in keys if key not in allowed_keys)
    if not invalid:
        return

    raise ProviderParamValidationError(
        provider=provider,
        scope=scope,
        invalid_params=tuple(invalid),
        allowed_params=tuple(sorted(allowed_keys)),
    )


def validate_chat_option_keys(
    *,
    provider: str,
    option_keys: Optional[Iterable[Any]],
) -> None:
    provider_key = (provider or "").strip().lower()
    allowed_keys = set(_CHAT_OPTION_KEYS)
    allowed_keys |= _PROVIDER_CHAT_OPTION_EXTRAS.get(provider_key, set())
    _raise_if_invalid(
        provider=provider,
        scope="chat",
        keys=_normalize_keys(option_keys),
        allowed_keys=allowed_keys,
    )


def validate_mode_param_keys(
    *,
    provider: str,
    mode: str,
    option_keys: Optional[Iterable[Any]],
    extra_keys: Optional[Iterable[Any]],
) -> None:
    keys = _normalize_keys(option_keys) | _normalize_keys(extra_keys)
    _raise_if_invalid(
        provider=provider,
        scope=f"mode:{mode}",
        keys=keys,
        allowed_keys=_MODE_ALLOWED_KEYS,
    )
