"""
Mode controls catalog loader and validator.

Single source for provider+mode control options:
- aspect ratios
- resolution tiers
- resolution map
- defaults / constraints
"""

from __future__ import annotations

from copy import deepcopy
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CATALOG_CACHE: Optional[Dict[str, Any]] = None
_CATALOG_MTIME: Optional[float] = None
_PROVIDER_ALIASES: Dict[str, str] = {
    "google-custom": "google",
    "qwen": "tongyi",
}
_MODE_ALIASES: Dict[str, str] = {
    "image-chat-edit": "image-edit",
    "image-inpainting": "image-edit",
    "image-background-edit": "image-edit",
    "image-recontext": "image-edit",
}
_GOOGLE_VIDEO_RESOLUTION_ALIASES: Dict[str, str] = {
    "1K": "720p",
    "720P": "720p",
    "1280X720": "720p",
    "1280*720": "720p",
    "720X1280": "720p",
    "720*1280": "720p",
    "2K": "1080p",
    "1080P": "1080p",
    "1920X1080": "1080p",
    "1920*1080": "1080p",
    "1080X1920": "1080p",
    "1080*1920": "1080p",
    "1792X1024": "1080p",
    "1792*1024": "1080p",
    "1024X1792": "1080p",
    "1024*1792": "1080p",
    "4K": "4k",
    "2160P": "4k",
    "3840X2160": "4k",
    "3840*2160": "4k",
    "2160X3840": "4k",
    "2160*3840": "4k",
}


def _apply_legacy_param_aliases(
    provider: str,
    mode: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = dict(params)

    if _PROVIDER_ALIASES.get(provider, provider) == "google" and mode == "video-gen":
        for key in ("resolution", "image_resolution", "image_size"):
            value = normalized.get(key)
            if value is None:
                continue
            alias = _GOOGLE_VIDEO_RESOLUTION_ALIASES.get(str(value).strip().upper())
            if alias:
                normalized[key] = alias

        if "seconds" in normalized and normalized.get("seconds") is not None:
            try:
                seconds_value = int(str(normalized["seconds"]).strip())
                if seconds_value > 0:
                    normalized["seconds"] = str(seconds_value)
            except (TypeError, ValueError):
                pass
        if "duration_seconds" in normalized and normalized.get("duration_seconds") is not None:
            try:
                duration_value = int(str(normalized["duration_seconds"]).strip())
                if duration_value > 0:
                    normalized["duration_seconds"] = duration_value
                    normalized.setdefault("seconds", str(duration_value))
            except (TypeError, ValueError):
                pass
        if "video_extension_count" in normalized and normalized.get("video_extension_count") is not None:
            try:
                extension_value = int(str(normalized["video_extension_count"]).strip())
                if extension_value >= 0:
                    normalized["video_extension_count"] = extension_value
            except (TypeError, ValueError):
                pass

    return normalized


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "mode_controls_catalog.json"


def _read_catalog() -> Dict[str, Any]:
    path = _catalog_path()
    if not path.exists():
        raise FileNotFoundError(f"Mode controls catalog not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_catalog(force_reload: bool = False) -> Dict[str, Any]:
    global _CATALOG_CACHE, _CATALOG_MTIME

    path = _catalog_path()
    mtime = path.stat().st_mtime if path.exists() else None

    if (
        not force_reload
        and _CATALOG_CACHE is not None
        and _CATALOG_MTIME is not None
        and mtime is not None
        and mtime == _CATALOG_MTIME
    ):
        return _CATALOG_CACHE

    catalog = _read_catalog()
    _CATALOG_CACHE = catalog
    _CATALOG_MTIME = mtime
    return catalog


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _matches_model(match: Dict[str, Any], model_id: Optional[str]) -> bool:
    if not match:
        return False
    if not model_id:
        return False

    model = str(model_id).lower()

    equals = match.get("equals")
    if equals and model != str(equals).lower():
        return False

    starts_with = match.get("starts_with")
    if starts_with and not model.startswith(str(starts_with).lower()):
        return False

    contains = match.get("contains")
    if contains and str(contains).lower() not in model:
        return False

    contains_any = match.get("contains_any")
    if contains_any:
        if not isinstance(contains_any, list):
            return False
        lowered = [str(item).lower() for item in contains_any]
        if not any(item in model for item in lowered):
            return False

    pattern = match.get("regex")
    if pattern:
        if not re.search(str(pattern), model, flags=re.IGNORECASE):
            return False

    return True


def _extract_values(options: Any) -> List[Any]:
    if not isinstance(options, list):
        return []
    values: List[Any] = []
    for option in options:
        if isinstance(option, dict):
            value = option.get("value")
            if isinstance(value, (str, int, float, bool)):
                values.append(value)
        elif isinstance(option, (str, int, float, bool)):
            values.append(option)
    return values


def _validate_numeric_range(
    key: str,
    value: Any,
    range_cfg: Dict[str, Any],
    provider: str,
    mode: str,
) -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"Invalid {key}: {value}. Expected number for {provider}/{mode}"
        )

    min_v = range_cfg.get("min")
    max_v = range_cfg.get("max")
    step = range_cfg.get("step")

    if isinstance(min_v, (int, float)) and value < min_v:
        raise ValueError(
            f"Invalid {key}: {value}. Must be >= {min_v} for {provider}/{mode}"
        )
    if isinstance(max_v, (int, float)) and value > max_v:
        raise ValueError(
            f"Invalid {key}: {value}. Must be <= {max_v} for {provider}/{mode}"
        )

    if (
        isinstance(step, (int, float))
        and step > 0
        and isinstance(min_v, (int, float))
    ):
        offset = (float(value) - float(min_v)) / float(step)
        # Allow tiny float error tolerance
        if abs(offset - round(offset)) > 1e-6:
            raise ValueError(
                f"Invalid {key}: {value}. Must match step={step} from min={min_v} for {provider}/{mode}"
            )


def resolve_mode_controls(
    provider: str,
    mode: str,
    model_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    resolved_provider = _PROVIDER_ALIASES.get(provider, provider)
    resolved_mode = _MODE_ALIASES.get(mode, mode)
    catalog = load_catalog()
    providers = catalog.get("providers", {})
    provider_cfg = providers.get(resolved_provider)
    if not isinstance(provider_cfg, dict):
        return None

    modes_cfg = provider_cfg.get("modes", {})
    mode_cfg = modes_cfg.get(resolved_mode)
    if not isinstance(mode_cfg, dict):
        return None

    resolved = deepcopy(mode_cfg)
    variants = resolved.pop("model_variants", [])
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            match = variant.get("match", {})
            if not isinstance(match, dict):
                continue
            if _matches_model(match, model_id):
                override = {k: v for k, v in variant.items() if k != "match"}
                resolved = _deep_merge(resolved, override)
                break

    resolved["schema_version"] = str(catalog.get("version", "unknown"))
    resolved["provider"] = resolved_provider
    resolved["requested_provider"] = provider
    resolved["mode"] = resolved_mode
    resolved["requested_mode"] = mode
    if model_id:
        resolved["model_id"] = model_id
    return resolved


def validate_params_with_catalog(
    provider: str,
    mode: str,
    model_id: Optional[str],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate key mode parameters via single-source catalog.
    """
    params = _apply_legacy_param_aliases(provider, mode, params)
    schema = resolve_mode_controls(provider, mode, model_id)
    if not schema:
        return params

    allowed_aspects = _extract_values(schema.get("aspect_ratios"))
    allowed_tiers = _extract_values(schema.get("resolution_tiers"))
    param_options = schema.get("param_options")
    numeric_ranges = schema.get("numeric_ranges")

    for key in ("aspect_ratio", "image_aspect_ratio", "output_ratio"):
        value = params.get(key)
        if value is None or not allowed_aspects:
            continue
        if value not in allowed_aspects:
            raise ValueError(
                f"Invalid {key}: {value}. Allowed values for {provider}/{mode}: {allowed_aspects}"
            )

    for key in ("resolution", "image_resolution", "image_size"):
        value = params.get(key)
        if value is None or not allowed_tiers:
            continue
        if value not in allowed_tiers:
            raise ValueError(
                f"Invalid {key}: {value}. Allowed values for {provider}/{mode}: {allowed_tiers}"
            )

    if isinstance(param_options, dict):
        for key, option_list in param_options.items():
            if key not in params:
                continue
            value = params.get(key)
            if value is None:
                continue
            allowed_values = _extract_values(option_list)
            if allowed_values and value not in allowed_values:
                raise ValueError(
                    f"Invalid {key}: {value}. Allowed values for {provider}/{mode}: {allowed_values}"
                )

    if isinstance(numeric_ranges, dict):
        for key, range_cfg in numeric_ranges.items():
            if key not in params:
                continue
            if not isinstance(range_cfg, dict):
                continue
            value = params.get(key)
            if value is None:
                continue
            _validate_numeric_range(
                key=key,
                value=value,
                range_cfg=range_cfg,
                provider=provider,
                mode=mode,
            )

    return params
