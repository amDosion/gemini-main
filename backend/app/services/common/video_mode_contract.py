"""
Backend-first helpers for video-mode controls and attachment normalization.

This module keeps video-mode business semantics out of the router layer.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from .mode_controls_catalog import resolve_mode_controls

VIDEO_MODE_CONTRACT_VERSION = "2026-03-17"
_GOOGLE_VIDEO_PROVIDER = "google"
_VIDEO_GEN_MODE = "video-gen"
_DEFAULT_RUNTIME_API_MODE = "gemini_api"
_MASK_FALLBACK_MODE = "REMOVE"


def _attachment_value(attachment: Any, *keys: str) -> Any:
    if attachment is None:
        return None
    if isinstance(attachment, dict):
        for key in keys:
            if key in attachment:
                return attachment.get(key)
        return None
    for key in keys:
        if hasattr(attachment, key):
            return getattr(attachment, key)
    return None


def _extract_option_values(options: Any) -> List[Any]:
    if not isinstance(options, list):
        return []
    values: List[Any] = []
    for option in options:
        if isinstance(option, dict):
            value = option.get("value")
            if value is not None:
                values.append(value)
        elif option is not None:
            values.append(option)
    return values


def _coerce_positive_int(value: Any) -> Optional[int]:
    try:
        candidate = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None
    if candidate <= 0:
        return None
    return candidate


def _coerce_non_negative_int(value: Any) -> Optional[int]:
    try:
        candidate = int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None
    if candidate < 0:
        return None
    return candidate


def _supports_model_family(model_id: Optional[str], marker: str) -> bool:
    return marker in str(model_id or "").strip().lower()


def attachment_to_media_input(attachment: Any) -> Optional[Dict[str, Any]]:
    candidate_url: Optional[str] = None
    normalized_file_uri = str(
        _attachment_value(attachment, "file_uri", "fileUri") or ""
    ).strip()

    url = _attachment_value(attachment, "url")
    temp_url = _attachment_value(attachment, "temp_url", "tempUrl")
    base64_data = _attachment_value(attachment, "base64_data", "base64Data")
    attachment_id = _attachment_value(attachment, "id", "attachment_id", "attachmentId")
    mime_type = str(
        _attachment_value(attachment, "mime_type", "mimeType") or "application/octet-stream"
    )

    if url:
        candidate_url = str(url)
    elif temp_url:
        candidate_url = str(temp_url)
    elif normalized_file_uri and not normalized_file_uri.startswith(("files/", "gs://")):
        candidate_url = normalized_file_uri
    elif base64_data:
        raw_base64 = str(base64_data)
        if raw_base64.startswith("data:"):
            candidate_url = raw_base64
        else:
            candidate_url = f"data:{mime_type};base64,{raw_base64}"

    has_provider_asset_ref = normalized_file_uri.startswith(("files/", "gs://"))
    if not candidate_url and not attachment_id and not has_provider_asset_ref:
        return None

    payload: Dict[str, Any] = {
        "mime_type": mime_type,
    }
    if normalized_file_uri.startswith("gs://"):
        payload["gcs_uri"] = normalized_file_uri
    elif normalized_file_uri:
        payload["provider_file_uri"] = normalized_file_uri
        if normalized_file_uri.startswith("files/"):
            payload["provider_file_name"] = normalized_file_uri
    if attachment_id:
        payload["attachment_id"] = str(attachment_id)
    if candidate_url:
        payload["url"] = candidate_url
    return payload


def extract_video_mode_attachment_params(
    attachments: Optional[Sequence[Any]],
) -> Dict[str, Any]:
    if not attachments:
        return {}

    video_items: List[Dict[str, Any]] = []
    source_image_items: List[Dict[str, Any]] = []
    last_frame_items: List[Dict[str, Any]] = []
    reference_image_items: List[Dict[str, Any]] = []
    image_items: List[Dict[str, Any]] = []
    mask_items: List[Dict[str, Any]] = []

    for attachment in attachments:
        payload = attachment_to_media_input(attachment)
        if not payload:
            continue
        mime_type = str(
            _attachment_value(attachment, "mime_type", "mimeType")
            or payload.get("mime_type")
            or ""
        ).strip().lower()
        normalized_role = str(
            _attachment_value(attachment, "role") or ""
        ).strip().lower().replace("-", "_")
        has_video_asset_ref = bool(
            str(payload.get("provider_file_name") or "").strip()
            or str(payload.get("provider_file_uri") or "").strip()
            or str(payload.get("gcs_uri") or "").strip()
        )
        if normalized_role == "mask":
            mask_items.append(payload)
            continue
        if normalized_role in {"last_frame", "end_frame", "target_frame"}:
            last_frame_items.append(payload)
            continue
        if normalized_role in {"source", "source_image", "start_frame", "first_frame"}:
            source_image_items.append(payload)
            continue
        if normalized_role in {"reference", "reference_image", "style_reference"}:
            reference_image_items.append(payload)
            continue
        if mime_type.startswith("video/") or has_video_asset_ref:
            video_items.append(payload)
            continue
        if mime_type.startswith("image/"):
            image_items.append(payload)

    params: Dict[str, Any] = {}

    if video_items:
        params["source_video"] = video_items[0]
        if mask_items:
            params["video_mask_image"] = mask_items[0]
        elif image_items:
            params["video_mask_image"] = image_items[0]
            params["video_mask_mode"] = _MASK_FALLBACK_MODE
        return params

    remaining_images = list(image_items)
    if not source_image_items and remaining_images:
        source_image_items.append(remaining_images.pop(0))

    if source_image_items:
        params["source_image"] = source_image_items[0]
    if last_frame_items:
        params["last_frame_image"] = last_frame_items[0]

    extra_refs = [*reference_image_items, *remaining_images]
    if extra_refs:
        params["reference_images"] = {"raw": extra_refs}
    if mask_items:
        params["video_mask_image"] = mask_items[0]

    return params


def merge_video_mode_attachment_params(
    *,
    method_name: str,
    params: Dict[str, Any],
    attachments: Optional[Sequence[Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    merged = dict(params)
    video_params = extract_video_mode_attachment_params(attachments)
    if not video_params:
        return merged, {}

    if method_name == "generate_video":
        for key, value in video_params.items():
            if value is not None and key not in merged:
                merged[key] = value
        return merged, video_params

    if method_name == "understand_video":
        source_video = video_params.get("source_video")
        if source_video is not None and "source_video" not in merged:
            merged["source_video"] = source_video
        return merged, video_params

    if method_name == "delete_video":
        source_video = video_params.get("source_video")
        if isinstance(source_video, dict):
            provider_file_name = str(
                source_video.get("provider_file_name")
                or source_video.get("providerFileName")
                or ""
            ).strip()
            provider_file_uri = str(
                source_video.get("provider_file_uri")
                or source_video.get("providerFileUri")
                or ""
            ).strip()
            gcs_uri = str(
                source_video.get("gcs_uri")
                or source_video.get("gcsUri")
                or ""
            ).strip()
            if provider_file_name and "provider_file_name" not in merged:
                merged["provider_file_name"] = provider_file_name
            if provider_file_uri and "provider_file_uri" not in merged:
                merged["provider_file_uri"] = provider_file_uri
            if gcs_uri and "gcs_uri" not in merged:
                merged["gcs_uri"] = gcs_uri
        return merged, video_params

    return merged, video_params


def resolve_google_video_runtime_api_mode(
    *,
    db: Optional[Session],
    user_id: Optional[str],
) -> str:
    if not db or not user_id:
        return _DEFAULT_RUNTIME_API_MODE
    try:
        from ...models.db_models import VertexAIConfig
    except Exception:
        return _DEFAULT_RUNTIME_API_MODE

    cfg = db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()
    api_mode = str(getattr(cfg, "api_mode", _DEFAULT_RUNTIME_API_MODE) or _DEFAULT_RUNTIME_API_MODE).strip().lower()
    return api_mode or _DEFAULT_RUNTIME_API_MODE


def _build_extension_duration_matrix(
    *,
    default_seconds: Any,
    seconds_options: List[Any],
    extension_counts: List[Any],
    extension_added_seconds: Optional[int],
    max_output_video_seconds: Optional[int],
    max_video_extension_count: Optional[int],
) -> List[Dict[str, Any]]:
    base_values: List[str] = []
    for item in seconds_options:
        value = str(item).strip()
        if value and value not in base_values:
            base_values.append(value)
    if not base_values and default_seconds is not None:
        base_values.append(str(default_seconds).strip())

    normalized_counts: List[int] = []
    for item in extension_counts:
        count = _coerce_non_negative_int(item)
        if count is None:
            continue
        if max_video_extension_count is not None and count > max_video_extension_count:
            continue
        if count not in normalized_counts:
            normalized_counts.append(count)
    if not normalized_counts and max_video_extension_count is not None:
        normalized_counts = list(range(0, max_video_extension_count + 1))

    if not base_values or not normalized_counts or not extension_added_seconds:
        return []

    matrix: List[Dict[str, Any]] = []
    for base_value in base_values:
        base_seconds = _coerce_positive_int(base_value)
        if base_seconds is None:
            continue
        options: List[Dict[str, Any]] = []
        for count in normalized_counts:
            total_seconds = base_seconds + count * extension_added_seconds
            if max_output_video_seconds is not None and total_seconds > max_output_video_seconds:
                continue
            options.append(
                {
                    "count": count,
                    "label": (
                        f"{total_seconds}s (base)"
                        if count == 0
                        else f"{total_seconds}s (+{count} extensions)"
                    ),
                    "total_seconds": total_seconds,
                }
            )
        if options:
            matrix.append(
                {
                    "base_seconds": str(base_seconds),
                    "options": options,
                }
            )
    return matrix


def build_video_mode_contract(schema: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(schema.get("provider") or "").strip().lower()
    mode = str(schema.get("mode") or "").strip().lower()
    if provider != _GOOGLE_VIDEO_PROVIDER or mode != _VIDEO_GEN_MODE:
        return {}

    model_id = str(schema.get("model_id") or "").strip().lower()
    defaults = schema.get("defaults") if isinstance(schema.get("defaults"), dict) else {}
    constraints = schema.get("constraints") if isinstance(schema.get("constraints"), dict) else {}
    param_options = schema.get("param_options") if isinstance(schema.get("param_options"), dict) else {}

    supports_reference_images = _coerce_positive_int(constraints.get("max_reference_image_count")) is not None
    supports_first_last_frame = _supports_model_family(model_id, "veo-3.1")
    supports_video_extension = (
        _supports_model_family(model_id, "veo-3.1")
        and _coerce_positive_int(constraints.get("video_extension_added_seconds")) is not None
    )
    supports_video_mask_image = _supports_model_family(model_id, "veo-2")

    extension_duration_matrix = _build_extension_duration_matrix(
        default_seconds=defaults.get("seconds"),
        seconds_options=_extract_option_values(param_options.get("seconds")),
        extension_counts=_extract_option_values(param_options.get("video_extension_count")),
        extension_added_seconds=_coerce_positive_int(constraints.get("video_extension_added_seconds")),
        max_output_video_seconds=_coerce_positive_int(constraints.get("max_output_video_seconds")),
        max_video_extension_count=_coerce_non_negative_int(constraints.get("max_video_extension_count")),
    )

    attachment_slots = [
        {
            "name": "source_image",
            "label": "Source image",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["source", "source_image", "start_frame", "first_frame"],
            "enabled": True,
        },
        {
            "name": "last_frame_image",
            "label": "Last frame image",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["last_frame", "end_frame", "target_frame"],
            "enabled": supports_first_last_frame,
        },
        {
            "name": "reference_images",
            "label": "Reference images",
            "kind": "image",
            "multiple": True,
            "required": False,
            "roles": ["reference", "reference_image", "style_reference"],
            "enabled": supports_reference_images,
            "max_items": _coerce_positive_int(constraints.get("max_reference_image_count")),
        },
        {
            "name": "source_video",
            "label": "Source video",
            "kind": "video",
            "multiple": False,
            "required": False,
            "roles": ["source_video"],
            "enabled": supports_video_extension or supports_video_mask_image,
        },
        {
            "name": "video_mask_image",
            "label": "Video mask image",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["mask"],
            "enabled": supports_video_mask_image,
        },
    ]

    input_strategies = [
        {
            "id": "text_to_video",
            "label": "Text to video",
            "requires": [],
            "allows": [],
        },
        {
            "id": "image_to_video",
            "label": "Image to video",
            "requires": ["source_image"],
            "allows": ["reference_images"],
        },
    ]
    if supports_first_last_frame:
        input_strategies.append(
            {
                "id": "first_last_frame",
                "label": "First and last frame to video",
                "requires": ["source_image", "last_frame_image"],
                "allows": [],
            }
        )
    if supports_video_extension:
        input_strategies.append(
            {
                "id": "video_extension",
                "label": "Extend source video",
                "requires": ["source_video"],
                "allows": [],
            }
        )
    if supports_video_mask_image:
        input_strategies.append(
            {
                "id": "masked_video_edit",
                "label": "Mask-based video edit",
                "requires": ["source_video", "video_mask_image"],
                "allows": [],
            }
        )

    subtitle_option_values = [
        str(value)
        for value in _extract_option_values(param_options.get("subtitle_mode"))
    ]
    non_none_subtitle_values = [value for value in subtitle_option_values if value != "none"]

    return {
        "version": VIDEO_MODE_CONTRACT_VERSION,
        "runtime_api_mode": str(schema.get("runtime_api_mode") or _DEFAULT_RUNTIME_API_MODE),
        "supports": {
            "generate_audio": constraints.get("supports_generate_audio") is True,
            "person_generation": constraints.get("supports_person_generation") is True,
            "subtitle_sidecar": constraints.get("supports_subtitle_sidecar") is True,
            "storyboard_prompting": constraints.get("supports_storyboard_prompting") is True,
            "tracking_overlay_prompt": constraints.get("supports_tracking_overlay_prompt") is True,
            "reference_images": supports_reference_images,
            "first_last_frame": supports_first_last_frame,
            "video_extension": supports_video_extension,
            "video_mask_image": supports_video_mask_image,
        },
        "attachment_slots": attachment_slots,
        "input_strategies": input_strategies,
        "field_policies": {
            "enhance_prompt": {
                "mandatory": constraints.get("enhance_prompt_mandatory") is True,
                "locked_when_mandatory": constraints.get("enhance_prompt_mandatory") is True,
                "effective_default": bool(defaults.get("enhance_prompt")),
            },
            "generate_audio": {
                "available": constraints.get("supports_generate_audio") is True,
                "forced_value": False if constraints.get("supports_generate_audio") is not True else None,
            },
            "person_generation": {
                "available": constraints.get("supports_person_generation") is True,
                "forced_value": None if constraints.get("supports_person_generation") is not True else None,
            },
            "subtitle_mode": {
                "available": bool(subtitle_option_values),
                "single_sidecar_format": True,
                "default_enabled_mode": non_none_subtitle_values[0] if non_none_subtitle_values else None,
                "supported_values": subtitle_option_values,
            },
            "storyboard_prompt": {
                "preferred": True,
                "deprecated_companion_fields": ["tracked_feature", "tracking_overlay_text"],
            },
        },
        "normalization_rules": [
            "If plain image attachments are sent without explicit roles, the first image becomes source_image and remaining images become reference_images.",
            "If a source_video is present and a loose image is provided without role=mask, the first loose image becomes video_mask_image with video_mask_mode=REMOVE.",
            "Provider asset references (files/... or gs://...) are treated as source_video inputs.",
        ],
        "extension_duration_matrix": extension_duration_matrix,
        "extension_constraints": {
            "added_seconds": _coerce_positive_int(constraints.get("video_extension_added_seconds")),
            "max_extension_count": _coerce_non_negative_int(constraints.get("max_video_extension_count")),
            "max_source_video_seconds": _coerce_positive_int(constraints.get("max_source_video_seconds")),
            "max_output_video_seconds": _coerce_positive_int(constraints.get("max_output_video_seconds")),
            "require_duration_seconds": [
                str(value)
                for value in _extract_option_values(constraints.get("video_extension_require_duration_seconds"))
            ],
            "require_resolution_values": [
                str(value)
                for value in _extract_option_values(constraints.get("video_extension_require_resolution_values"))
            ],
        },
    }


def _allowed_extension_counts_for_seconds(
    contract: Dict[str, Any],
    *,
    base_seconds: str,
) -> Optional[List[int]]:
    matrix = contract.get("extension_duration_matrix")
    if not isinstance(matrix, list):
        return None
    for entry in matrix:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("base_seconds")) != str(base_seconds):
            continue
        options = entry.get("options")
        if not isinstance(options, list):
            return []
        counts: List[int] = []
        for option in options:
            if not isinstance(option, dict):
                continue
            count = _coerce_non_negative_int(option.get("count"))
            if count is not None:
                counts.append(count)
        return counts
    return None


def _derive_video_input_strategy(params: Dict[str, Any], contract: Dict[str, Any]) -> str:
    source_video = params.get("source_video")
    source_image = params.get("source_image")
    last_frame_image = params.get("last_frame_image")
    video_mask_image = params.get("video_mask_image")
    reference_images = params.get("reference_images")
    supports = contract.get("supports") if isinstance(contract.get("supports"), dict) else {}

    if source_video and video_mask_image and supports.get("video_mask_image") is True:
        return "masked_video_edit"
    if source_video:
        return "video_extension"
    if source_image and last_frame_image and supports.get("first_last_frame") is True:
        return "first_last_frame"
    if source_image or reference_images:
        return "image_to_video"
    return "text_to_video"


def normalize_video_generation_request_params(
    *,
    provider: str,
    mode: str,
    model_id: Optional[str],
    params: Dict[str, Any],
    user_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    normalized = dict(params)
    schema = resolve_runtime_mode_controls_schema(
        provider=provider,
        mode=mode,
        model_id=model_id,
        user_id=user_id,
        db=db,
    )
    if not schema:
        return normalized, {}

    contract = schema.get("video_contract") if isinstance(schema.get("video_contract"), dict) else {}
    field_policies = contract.get("field_policies") if isinstance(contract.get("field_policies"), dict) else {}
    runtime_api_mode = str(schema.get("runtime_api_mode") or _DEFAULT_RUNTIME_API_MODE)

    enhance_policy = (
        field_policies.get("enhance_prompt")
        if isinstance(field_policies.get("enhance_prompt"), dict)
        else {}
    )
    if enhance_policy.get("mandatory") is True:
        normalized["enhance_prompt"] = True

    generate_audio_policy = (
        field_policies.get("generate_audio")
        if isinstance(field_policies.get("generate_audio"), dict)
        else {}
    )
    if generate_audio_policy.get("available") is not True:
        normalized["generate_audio"] = False

    person_generation_policy = (
        field_policies.get("person_generation")
        if isinstance(field_policies.get("person_generation"), dict)
        else {}
    )
    if person_generation_policy.get("available") is not True:
        normalized.pop("person_generation", None)

    subtitle_mode = str(normalized.get("subtitle_mode") or "none").strip().lower()
    subtitle_policy = (
        field_policies.get("subtitle_mode")
        if isinstance(field_policies.get("subtitle_mode"), dict)
        else {}
    )
    supported_subtitle_values = (
        subtitle_policy.get("supported_values")
        if isinstance(subtitle_policy.get("supported_values"), list)
        else []
    )
    if supported_subtitle_values and subtitle_mode not in supported_subtitle_values:
        raise ValueError(
            f"Unsupported Google video subtitle_mode '{subtitle_mode}'. Supported values: {supported_subtitle_values}"
        )
    if subtitle_mode == "none":
        normalized.pop("subtitle_script", None)

    storyboard_prompt = str(normalized.get("storyboard_prompt") or "").strip()
    if storyboard_prompt:
        normalized.pop("tracked_feature", None)
        normalized.pop("tracking_overlay_text", None)

    extension_count = _coerce_non_negative_int(normalized.get("video_extension_count"))
    supports = contract.get("supports") if isinstance(contract.get("supports"), dict) else {}
    seconds_value = str(
        normalized.get("seconds")
        if normalized.get("seconds") is not None
        else normalized.get("duration_seconds")
        if normalized.get("duration_seconds") is not None
        else schema.get("defaults", {}).get("seconds")
        or ""
    ).strip()
    if extension_count is not None and extension_count > 0:
        if supports.get("video_extension") is not True:
            raise ValueError(
                f"Google video extension is not supported for model '{model_id}'."
            )
        allowed_counts = _allowed_extension_counts_for_seconds(contract, base_seconds=seconds_value)
        if allowed_counts is not None and extension_count not in allowed_counts:
            raise ValueError(
                f"Unsupported video_extension_count={extension_count} for base seconds={seconds_value}. "
                f"Allowed counts: {allowed_counts}"
            )

    normalization_meta = {
        "runtime_api_mode": runtime_api_mode,
        "input_strategy": _derive_video_input_strategy(normalized, contract),
        "effective_enhance_prompt": bool(normalized.get("enhance_prompt")),
        "subtitle_mode": subtitle_mode,
    }
    return normalized, normalization_meta


def apply_video_mode_runtime_overrides(
    schema: Dict[str, Any],
    *,
    provider: str,
    mode: str,
    runtime_api_mode: Optional[str] = None,
) -> Dict[str, Any]:
    resolved = deepcopy(schema)
    if provider != _GOOGLE_VIDEO_PROVIDER or mode != _VIDEO_GEN_MODE:
        return resolved

    api_mode = str(runtime_api_mode or resolved.get("runtime_api_mode") or _DEFAULT_RUNTIME_API_MODE).strip().lower()
    resolved["runtime_api_mode"] = api_mode or _DEFAULT_RUNTIME_API_MODE

    if resolved["runtime_api_mode"] != "vertex_ai":
        param_options = resolved.get("param_options")
        if isinstance(param_options, dict):
            param_options.pop("generate_audio", None)
            param_options.pop("person_generation", None)
        constraints = resolved.get("constraints")
        if isinstance(constraints, dict):
            constraints["supports_generate_audio"] = False
            constraints["supports_person_generation"] = False
        defaults = resolved.get("defaults")
        if isinstance(defaults, dict):
            defaults["generate_audio"] = False
            defaults["person_generation"] = None

    resolved["video_contract"] = build_video_mode_contract(resolved)
    return resolved


def resolve_runtime_mode_controls_schema(
    *,
    provider: str,
    mode: str,
    model_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    schema = resolve_mode_controls(provider=provider, mode=mode, model_id=model_id)
    if not schema:
        return None
    runtime_api_mode = resolve_google_video_runtime_api_mode(db=db, user_id=user_id)
    return apply_video_mode_runtime_overrides(
        schema,
        provider=provider,
        mode=mode,
        runtime_api_mode=runtime_api_mode,
    )
