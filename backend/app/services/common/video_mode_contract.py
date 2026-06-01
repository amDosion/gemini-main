"""
Backend-first helpers for video-mode controls and attachment normalization.

This module keeps video-mode business semantics out of the router layer.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from .mode_controls_catalog import resolve_mode_controls
from ...utils.attachment_handler import is_base64_url

VIDEO_MODE_CONTRACT_VERSION = "2026-03-17"
_GOOGLE_VIDEO_PROVIDER = "google"
_TONGYI_VIDEO_PROVIDER = "tongyi"
_OPENAI_VIDEO_PROVIDER = "openai"
_GROK_VIDEO_PROVIDER = "grok"
_VIDEO_GEN_MODE = "video-gen"
_IMAGE_GEN_MODE = "image-gen"
_DEFAULT_RUNTIME_API_MODE = "gemini_api"
_TONGYI_RUNTIME_API_MODE = "dashscope"
_OPENAI_RUNTIME_API_MODE = "openai_videos"
_GROK_RUNTIME_API_MODE = "grok_video"
_MASK_FALLBACK_MODE = "REMOVE"
_OUTPUT_MIME_CONTROL_KEYS = ("output_mime_type", "output_compression_quality")


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


def _remove_output_mime_controls(schema: Dict[str, Any]) -> None:
    defaults = schema.get("defaults")
    if isinstance(defaults, dict):
        for key in _OUTPUT_MIME_CONTROL_KEYS:
            defaults.pop(key, None)

    param_options = schema.get("param_options")
    if isinstance(param_options, dict):
        param_options.pop("output_mime_type", None)

    numeric_ranges = schema.get("numeric_ranges")
    if isinstance(numeric_ranges, dict):
        numeric_ranges.pop("output_compression_quality", None)


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


def _is_tongyi_video_model(model_id: Optional[str]) -> bool:
    model = str(model_id or "").strip().lower()
    return (
        "happyhorse" in model
        or model.startswith("wan2.7-t2v")
        or model.startswith("wan2.7-i2v")
        or model.startswith("wan2.7-r2v")
        or model.startswith("wan2.7-videoedit")
        or model.startswith("wan2.7-video-edit")
    )


def _is_tongyi_text_to_video_model(model_id: Optional[str]) -> bool:
    model = str(model_id or "").strip().lower()
    return model.endswith("-t2v") or "-t2v" in model


def _is_tongyi_image_to_video_model(model_id: Optional[str]) -> bool:
    model = str(model_id or "").strip().lower()
    return model.endswith("-i2v") or "-i2v" in model


def _is_tongyi_reference_to_video_model(model_id: Optional[str]) -> bool:
    model = str(model_id or "").strip().lower()
    return model.endswith("-r2v") or "-r2v" in model


def _is_tongyi_video_edit_model(model_id: Optional[str]) -> bool:
    model = str(model_id or "").strip().lower()
    return "videoedit" in model or "video-edit" in model


def _is_tongyi_video_provider(provider: Optional[str]) -> bool:
    return str(provider or "").strip().lower() == _TONGYI_VIDEO_PROVIDER


def _is_openai_sora_video_model(model_id: Optional[str]) -> bool:
    return str(model_id or "").strip().lower().startswith("sora")


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
        if is_base64_url(raw_base64):
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
    *,
    provider: Optional[str] = None,
    mode: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not attachments:
        return {}

    video_items: List[Dict[str, Any]] = []
    audio_items: List[Dict[str, Any]] = []
    source_image_items: List[Dict[str, Any]] = []
    last_frame_items: List[Dict[str, Any]] = []
    reference_image_items: List[Dict[str, Any]] = []
    image_items: List[Dict[str, Any]] = []
    mask_items: List[Dict[str, Any]] = []
    normalized_provider = str(provider or "").strip().lower()
    normalized_mode = str(mode or "").strip().lower()
    is_tongyi_video = normalized_provider == _TONGYI_VIDEO_PROVIDER and normalized_mode == _VIDEO_GEN_MODE
    is_tongyi_i2v = is_tongyi_video and _is_tongyi_image_to_video_model(model_id)
    is_tongyi_r2v = is_tongyi_video and _is_tongyi_reference_to_video_model(model_id)
    is_tongyi_videoedit = is_tongyi_video and _is_tongyi_video_edit_model(model_id)

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
        is_video_payload = mime_type.startswith("video/") or has_video_asset_ref
        if normalized_role in {"source_video", "first_clip", "reference_video"}:
            video_items.append(payload)
            continue
        if normalized_role in {"source", "reference"} and is_video_payload:
            video_items.append(payload)
            continue
        if normalized_role == "mask":
            mask_items.append(payload)
            continue
        if normalized_role in {"audio", "driving_audio", "voice", "soundtrack"}:
            audio_items.append(payload)
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
        if is_video_payload:
            video_items.append(payload)
            continue
        if mime_type.startswith("audio/"):
            audio_items.append(payload)
            continue
        if mime_type.startswith("image/"):
            image_items.append(payload)

    params: Dict[str, Any] = {}

    if video_items:
        params["source_video"] = video_items[0]
        if audio_items:
            params["audio_url"] = audio_items[0]

        if is_tongyi_videoedit or is_tongyi_r2v:
            reference_items = [*reference_image_items, *image_items]
            if reference_items:
                params["reference_images"] = {"raw": reference_items}
            return params

        if is_tongyi_i2v:
            if last_frame_items:
                params["last_frame_image"] = last_frame_items[0]
            elif image_items:
                params["last_frame_image"] = image_items[0]
            return params

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
    if audio_items:
        params["audio_url"] = audio_items[0]

    return params


def merge_video_mode_attachment_params(
    *,
    method_name: str,
    params: Dict[str, Any],
    attachments: Optional[Sequence[Any]],
    provider: Optional[str] = None,
    mode: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    merged = dict(params)
    video_params = extract_video_mode_attachment_params(
        attachments,
        provider=provider,
        mode=mode,
        model_id=model_id,
    )
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
    max_source_video_seconds: Optional[int],
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
            if count > 0 and max_source_video_seconds is not None:
                last_source_seconds = base_seconds + max(count - 1, 0) * extension_added_seconds
                if last_source_seconds > max_source_video_seconds:
                    continue
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


def _build_chained_extension_duration_matrix(
    *,
    default_seconds: Any,
    seconds_options: List[Any],
    max_video_extension_count: int,
    max_output_video_seconds: Optional[int] = None,
) -> List[Dict[str, Any]]:
    base_values: List[str] = []
    for item in seconds_options:
        value = str(item).strip()
        if value and value not in base_values:
            base_values.append(value)
    if not base_values and default_seconds is not None:
        value = str(default_seconds).strip()
        if value:
            base_values.append(value)

    matrix: List[Dict[str, Any]] = []
    for base_value in base_values:
        base_seconds = _coerce_positive_int(base_value)
        if base_seconds is None:
            continue
        options: List[Dict[str, Any]] = []
        for count in range(0, max_video_extension_count + 1):
            total_seconds = base_seconds * (count + 1)
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


def _expand_seconds_range_options(
    *,
    default_seconds: Any,
    seconds_range: Dict[str, Any],
) -> List[int]:
    min_seconds = _coerce_positive_int(seconds_range.get("min"))
    max_seconds = _coerce_positive_int(seconds_range.get("max"))
    step_seconds = _coerce_positive_int(seconds_range.get("step")) or 1
    values: List[int] = []
    if min_seconds is not None and max_seconds is not None and min_seconds <= max_seconds:
        values = list(range(min_seconds, max_seconds + 1, step_seconds))
        if values and values[-1] != max_seconds:
            values.append(max_seconds)

    default_value = _coerce_positive_int(default_seconds)
    if default_value is not None and default_value not in values:
        values.append(default_value)
    return sorted(values)


def _build_tongyi_video_mode_contract(schema: Dict[str, Any]) -> Dict[str, Any]:
    model_id = str(schema.get("model_id") or "").strip().lower()
    defaults = schema.get("defaults") if isinstance(schema.get("defaults"), dict) else {}
    constraints = schema.get("constraints") if isinstance(schema.get("constraints"), dict) else {}
    param_options = schema.get("param_options") if isinstance(schema.get("param_options"), dict) else {}

    is_t2v = _is_tongyi_text_to_video_model(model_id)
    is_i2v = _is_tongyi_image_to_video_model(model_id)
    is_r2v = _is_tongyi_reference_to_video_model(model_id)
    is_videoedit = _is_tongyi_video_edit_model(model_id)
    is_known_tongyi_video = _is_tongyi_video_model(model_id)

    supports = {
        "text_to_video": is_t2v or not is_known_tongyi_video,
        "first_frame_to_video": is_i2v,
        "first_last_frame": is_i2v,
        "video_continuation": is_i2v,
        "video_continuation_to_last_frame": is_i2v,
        "video_extension": is_known_tongyi_video,
        "reference_to_video": is_r2v,
        "video_edit": is_videoedit,
        "video_mask_image": False,
        "reference_images": is_r2v or is_videoedit,
        "reference_video": is_r2v,
        "driving_audio": is_i2v,
        "generate_audio": False,
        "subtitle_sidecar": False,
        "storyboard_prompting": is_known_tongyi_video,
        "tracking_overlay_prompt": False,
    }
    max_extension_count = _coerce_non_negative_int(constraints.get("max_video_extension_count")) or 8
    max_output_video_seconds = _coerce_positive_int(constraints.get("max_output_video_seconds"))
    extension_duration_matrix = (
        _build_chained_extension_duration_matrix(
            default_seconds=defaults.get("seconds"),
            seconds_options=_extract_option_values(param_options.get("seconds")),
            max_video_extension_count=max_extension_count,
            max_output_video_seconds=max_output_video_seconds,
        )
        if is_known_tongyi_video
        else []
    )

    attachment_slots = [
        {
            "name": "source_image",
            "label": "首帧图",
            "kind": "image",
            "multiple": False,
            "required": is_i2v,
            "roles": ["source", "source_image", "start_frame", "first_frame"],
            "enabled": is_i2v,
        },
        {
            "name": "last_frame_image",
            "label": "尾帧图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["last_frame", "end_frame", "target_frame"],
            "enabled": is_i2v,
        },
        {
            "name": "source_video",
            "label": "源视频",
            "kind": "video",
            "multiple": False,
            "required": is_videoedit,
            "roles": ["source_video", "source", "first_clip", "reference_video"],
            "enabled": is_i2v or is_r2v or is_videoedit,
        },
        {
            "name": "reference_video",
            "label": "参考视频",
            "kind": "video",
            "multiple": False,
            "required": False,
            "roles": ["reference_video", "reference"],
            "enabled": is_r2v,
        },
        {
            "name": "reference_images",
            "label": "参考图",
            "kind": "image",
            "multiple": True,
            "required": False,
            "roles": ["reference", "reference_image", "style_reference"],
            "enabled": is_r2v,
            "max_items": 9 if is_r2v else None,
        },
        {
            "name": "video_edit_reference_images",
            "label": "视频编辑参考图",
            "kind": "image",
            "multiple": True,
            "required": False,
            "roles": ["reference", "reference_image", "style_reference"],
            "enabled": is_videoedit,
            "max_items": 4,
        },
        {
            "name": "driving_audio",
            "label": "驱动音频",
            "kind": "audio",
            "multiple": False,
            "required": False,
            "roles": ["audio", "driving_audio", "voice", "soundtrack"],
            "enabled": is_i2v,
        },
        {
            "name": "video_mask_image",
            "label": "视频遮罩图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["mask"],
            "enabled": False,
        },
    ]

    input_strategies: List[Dict[str, Any]] = []
    if is_t2v or not is_known_tongyi_video:
        input_strategies.append(
            {
                "id": "text_to_video",
                "label": "文生视频",
                "requires": [],
                "allows": [],
            }
        )
    if is_i2v:
        input_strategies.extend(
            [
                {
                    "id": "first_frame_to_video",
                    "label": "图生视频",
                    "requires": ["source_image"],
                    "allows": ["driving_audio"],
                },
                {
                    "id": "first_last_frame_to_video",
                    "label": "首尾帧生视频",
                    "requires": ["source_image", "last_frame_image"],
                    "allows": ["driving_audio"],
                },
                {
                    "id": "video_continuation",
                    "label": "视频延长",
                    "requires": ["source_video"],
                    "allows": ["driving_audio"],
                },
                {
                    "id": "video_continuation_to_last_frame",
                    "label": "延长到尾帧",
                    "requires": ["source_video", "last_frame_image"],
                    "allows": ["driving_audio"],
                },
            ]
        )
    if is_r2v:
        input_strategies.append(
            {
                "id": "reference_to_video",
                "label": "参考生视频",
                "requires": [],
                "allows": ["source_video", "reference_video", "reference_images"],
            }
        )
    if is_videoedit:
        input_strategies.append(
            {
                "id": "video_edit",
                "label": "视频编辑",
                "requires": ["source_video"],
                "allows": ["video_edit_reference_images"],
            }
        )

    return {
        "version": VIDEO_MODE_CONTRACT_VERSION,
        "runtime_api_mode": _TONGYI_RUNTIME_API_MODE,
        "supports": supports,
        "attachment_slots": attachment_slots,
        "input_strategies": input_strategies,
        "provider_payload_media_types": [
            "first_frame",
            "last_frame",
            "first_clip",
            "driving_audio",
            "reference_image",
            "reference_video",
            "video",
        ],
        "field_policies": {
            "enhance_prompt": {
                "mandatory": False,
                "locked_when_mandatory": False,
                "effective_default": bool(defaults.get("enhance_prompt")),
            },
            "generate_audio": {
                "available": False,
                "forced_value": False,
            },
            "subtitle_mode": {
                "available": False,
                "single_sidecar_format": False,
                "default_enabled_mode": None,
                "supported_values": [],
            },
            "storyboard_prompt": {
                "preferred": is_known_tongyi_video,
                "deprecated_companion_fields": [],
            },
        },
        "normalization_rules": [
            "Tongyi text-to-video sends no media inputs.",
            "Tongyi image-to-video maps source_image to first_frame and source_video to first_clip.",
            "Tongyi image-to-video maps explicit last_frame_image to last_frame.",
            "Tongyi reference-to-video maps source_video to reference_video and reference_images.raw to reference_image.",
            "Tongyi video edit maps source_video to video and loose images to reference_image, not video_mask_image.",
        ],
        "media_limits": {
            "max_reference_image_count": 9 if is_r2v else 4 if is_videoedit else 0,
            "max_reference_video_count": 1 if is_r2v else 0,
            "max_driving_audio_count": 1 if is_i2v else 0,
        },
        "extension_duration_matrix": extension_duration_matrix,
        "extension_constraints": {
            "added_seconds": None,
            "max_extension_count": max_extension_count if is_known_tongyi_video else 0,
            "max_source_video_seconds": None,
            "max_output_video_seconds": max_output_video_seconds,
            "require_duration_seconds": [],
            "require_resolution_values": [],
        },
        "constraints": constraints,
    }


def _build_openai_video_mode_contract(schema: Dict[str, Any]) -> Dict[str, Any]:
    model_id = str(schema.get("model_id") or "").strip().lower()
    defaults = schema.get("defaults") if isinstance(schema.get("defaults"), dict) else {}
    constraints = schema.get("constraints") if isinstance(schema.get("constraints"), dict) else {}
    param_options = schema.get("param_options") if isinstance(schema.get("param_options"), dict) else {}
    is_sora = _is_openai_sora_video_model(model_id) or not model_id
    max_extension_count = _coerce_non_negative_int(constraints.get("max_video_extension_count")) or 8
    max_output_video_seconds = _coerce_positive_int(constraints.get("max_output_video_seconds"))
    extension_duration_matrix = (
        _build_chained_extension_duration_matrix(
            default_seconds=defaults.get("seconds"),
            seconds_options=_extract_option_values(param_options.get("seconds")),
            max_video_extension_count=max_extension_count,
            max_output_video_seconds=max_output_video_seconds,
        )
        if is_sora
        else []
    )

    supports = {
        "text_to_video": is_sora,
        "image_to_video": is_sora,
        "first_frame_to_video": is_sora,
        "video_extension": is_sora,
        "video_edit": is_sora,
        "first_last_frame": False,
        "video_mask_image": False,
        "reference_images": False,
        "reference_video": False,
        "generate_audio": False,
        "subtitle_sidecar": False,
        "storyboard_prompting": is_sora,
        "tracking_overlay_prompt": False,
    }

    attachment_slots = [
        {
            "name": "source_image",
            "label": "首帧图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["source", "source_image", "start_frame", "first_frame"],
            "enabled": is_sora,
        },
        {
            "name": "source_video",
            "label": "源视频",
            "kind": "video",
            "multiple": False,
            "required": False,
            "roles": ["source_video", "source"],
            "enabled": is_sora,
        },
        {
            "name": "last_frame_image",
            "label": "尾帧图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["last_frame", "end_frame", "target_frame"],
            "enabled": False,
        },
        {
            "name": "video_mask_image",
            "label": "遮罩图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["mask"],
            "enabled": False,
        },
    ]

    input_strategies: List[Dict[str, Any]] = []
    if is_sora:
        input_strategies = [
            {
                "id": "text_to_video",
                "label": "文生视频",
                "requires": [],
                "allows": [],
            },
            {
                "id": "image_to_video",
                "label": "图生视频",
                "requires": ["source_image"],
                "allows": [],
            },
            {
                "id": "video_extension",
                "label": "视频延长",
                "requires": ["source_video"],
                "allows": [],
            },
            {
                "id": "video_edit",
                "label": "视频编辑",
                "requires": ["source_video"],
                "allows": [],
            },
        ]

    return {
        "version": VIDEO_MODE_CONTRACT_VERSION,
        "runtime_api_mode": _OPENAI_RUNTIME_API_MODE,
        "supports": supports,
        "attachment_slots": attachment_slots,
        "input_strategies": input_strategies,
        "sub_modes": input_strategies,
        "field_policies": {
            "enhance_prompt": {
                "mandatory": False,
                "locked_when_mandatory": False,
                "effective_default": False,
            },
            "generate_audio": {
                "available": False,
                "forced_value": False,
            },
            "subtitle_mode": {
                "available": False,
                "single_sidecar_format": False,
                "default_enabled_mode": None,
                "supported_values": [],
            },
            "storyboard_prompt": {
                "preferred": is_sora,
                "deprecated_companion_fields": [],
            },
        },
        "normalization_rules": [
            "OpenAI text_to_video calls videos.create with no media input.",
            "OpenAI image_to_video maps source_image to videos.create input_reference.",
            "OpenAI video_extension maps source_video to videos.extend.",
            "OpenAI video_edit maps source_video to videos.edit.",
        ],
        "extension_duration_matrix": extension_duration_matrix,
        "extension_constraints": {
            "added_seconds": None,
            "max_extension_count": max_extension_count if is_sora else 0,
            "max_source_video_seconds": None,
            "max_output_video_seconds": max_output_video_seconds,
            "require_duration_seconds": [],
            "require_resolution_values": [],
        },
        "constraints": constraints,
    }


def _build_grok_video_mode_contract(schema: Dict[str, Any]) -> Dict[str, Any]:
    defaults = schema.get("defaults") if isinstance(schema.get("defaults"), dict) else {}
    constraints = schema.get("constraints") if isinstance(schema.get("constraints"), dict) else {}
    numeric_ranges = schema.get("numeric_ranges") if isinstance(schema.get("numeric_ranges"), dict) else {}
    seconds_range = numeric_ranges.get("seconds") if isinstance(numeric_ranges.get("seconds"), dict) else {}
    if not seconds_range:
        seconds_range = {
            "min": constraints.get("min_seconds"),
            "max": constraints.get("max_seconds"),
            "step": constraints.get("seconds_step") or 1,
        }
    default_seconds = defaults.get("seconds") or 10
    min_seconds = _coerce_positive_int(seconds_range.get("min")) or 6
    max_seconds = _coerce_positive_int(seconds_range.get("max")) or 30
    seconds_options = _expand_seconds_range_options(
        default_seconds=default_seconds,
        seconds_range=seconds_range,
    )
    max_extension_count = _coerce_non_negative_int(constraints.get("max_video_extension_count")) or 8

    return {
        "version": VIDEO_MODE_CONTRACT_VERSION,
        "runtime_api_mode": _GROK_RUNTIME_API_MODE,
        "supports": {
            "text_to_video": True,
            "image_to_video": True,
            "first_frame_to_video": True,
            "video_extension": True,
            "storyboard_prompting": True,
            "generate_audio": False,
            "subtitle_sidecar": False,
            "video_mask_image": False,
            "reference_images": False,
            "reference_video": False,
            "tracking_overlay_prompt": False,
        },
        "attachment_slots": [
            {
                "name": "source_image",
                "label": "首帧图",
                "kind": "image",
                "multiple": False,
                "required": False,
                "roles": ["source", "source_image", "start_frame", "first_frame"],
                "enabled": True,
            },
            {
                "name": "source_video",
                "label": "源视频",
                "kind": "video",
                "multiple": False,
                "required": False,
                "roles": ["source_video", "source"],
                "enabled": True,
            },
        ],
        "input_strategies": [
            {"id": "text_to_video", "label": "文生视频", "requires": [], "allows": []},
            {"id": "image_to_video", "label": "图生视频", "requires": ["source_image"], "allows": []},
            {"id": "video_extension", "label": "视频延长", "requires": [], "allows": ["source_video"]},
        ],
        "field_policies": {
            "enhance_prompt": {
                "mandatory": False,
                "locked_when_mandatory": False,
                "effective_default": False,
            },
            "generate_audio": {
                "available": False,
                "forced_value": False,
            },
            "subtitle_mode": {
                "available": False,
                "single_sidecar_format": False,
                "default_enabled_mode": None,
                "supported_values": [],
            },
            "storyboard_prompt": {
                "preferred": True,
                "deprecated_companion_fields": [],
            },
        },
        "extension_duration_matrix": _build_chained_extension_duration_matrix(
            default_seconds=default_seconds,
            seconds_options=seconds_options,
            max_video_extension_count=max_extension_count,
            max_output_video_seconds=None,
        ),
        "extension_constraints": {
            "added_seconds": None,
            "max_extension_count": max_extension_count,
            "max_source_video_seconds": None,
            "max_output_video_seconds": None,
            "require_duration_seconds": [],
            "require_resolution_values": [],
        },
        "constraints": constraints,
    }


def build_video_mode_contract(schema: Dict[str, Any]) -> Dict[str, Any]:
    provider = str(schema.get("provider") or "").strip().lower()
    mode = str(schema.get("mode") or "").strip().lower()
    if provider == _TONGYI_VIDEO_PROVIDER and mode == _VIDEO_GEN_MODE:
        return _build_tongyi_video_mode_contract(schema)
    if provider == _OPENAI_VIDEO_PROVIDER and mode == _VIDEO_GEN_MODE:
        return _build_openai_video_mode_contract(schema)
    if provider == _GROK_VIDEO_PROVIDER and mode == _VIDEO_GEN_MODE:
        return _build_grok_video_mode_contract(schema)

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
        max_source_video_seconds=_coerce_positive_int(constraints.get("max_source_video_seconds")),
        max_output_video_seconds=_coerce_positive_int(constraints.get("max_output_video_seconds")),
        max_video_extension_count=_coerce_non_negative_int(constraints.get("max_video_extension_count")),
    )

    attachment_slots = [
        {
            "name": "source_image",
            "label": "首帧图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["source", "source_image", "start_frame", "first_frame"],
            "enabled": True,
        },
        {
            "name": "last_frame_image",
            "label": "尾帧图",
            "kind": "image",
            "multiple": False,
            "required": False,
            "roles": ["last_frame", "end_frame", "target_frame"],
            "enabled": supports_first_last_frame,
        },
        {
            "name": "reference_images",
            "label": "参考图",
            "kind": "image",
            "multiple": True,
            "required": False,
            "roles": ["reference", "reference_image", "style_reference"],
            "enabled": supports_reference_images,
            "max_items": _coerce_positive_int(constraints.get("max_reference_image_count")),
        },
        {
            "name": "source_video",
            "label": "源视频",
            "kind": "video",
            "multiple": False,
            "required": False,
            "roles": ["source_video"],
            "enabled": supports_video_extension or supports_video_mask_image,
        },
        {
            "name": "video_mask_image",
            "label": "视频遮罩图",
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
            "label": "文生视频",
            "requires": [],
            "allows": [],
        },
        {
            "id": "image_to_video",
            "label": "图生视频",
            "requires": ["source_image"],
            "allows": ["reference_images"],
        },
    ]
    if supports_first_last_frame:
        input_strategies.append(
            {
                "id": "first_last_frame",
                "label": "首尾帧生视频",
                "requires": ["source_image", "last_frame_image"],
                "allows": [],
            }
        )
    if supports_video_extension:
        input_strategies.append(
            {
                "id": "video_extension",
                "label": "视频延长",
                "requires": ["source_video"],
                "allows": [],
            }
        )
    if supports_video_mask_image:
        input_strategies.append(
            {
                "id": "masked_video_edit",
                "label": "遮罩视频编辑",
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


def _requested_video_input_strategy(params: Dict[str, Any], contract: Dict[str, Any]) -> Optional[str]:
    requested = str(
        params.get("video_input_strategy")
        or params.get("videoInputStrategy")
        or ""
    ).strip()
    if not requested:
        return None
    strategies = contract.get("input_strategies")
    if not isinstance(strategies, list):
        return requested
    allowed = {
        str(strategy.get("id") or "").strip()
        for strategy in strategies
        if isinstance(strategy, dict) and str(strategy.get("id") or "").strip()
    }
    if allowed and requested not in allowed:
        raise ValueError(
            f"Unsupported video_input_strategy '{requested}'. Supported values: {sorted(allowed)}"
        )
    return requested


def _video_strategy_map(contract: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    strategies = contract.get("input_strategies")
    if not isinstance(strategies, list):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        strategy_id = str(strategy.get("id") or "").strip()
        if strategy_id:
            result[strategy_id] = strategy
    return result


def _has_video_slot(params: Dict[str, Any], slot_name: str) -> bool:
    if slot_name in {"source_image", "last_frame_image", "source_video", "video_mask_image"}:
        return bool(params.get(slot_name))
    if slot_name in {"driving_audio", "audio_url"}:
        return bool(params.get("audio_url") or params.get("audioUrl"))
    if slot_name in {"reference_images", "video_edit_reference_images"}:
        reference_images = params.get("reference_images")
        if not isinstance(reference_images, dict):
            return False
        raw = reference_images.get("raw")
        if isinstance(raw, list):
            return any(bool(item) for item in raw)
        return bool(raw)
    if slot_name == "reference_video":
        return bool(params.get("source_video") or params.get("reference_video"))
    return bool(params.get(slot_name))


def _validate_video_input_strategy_requirements(
    *,
    params: Dict[str, Any],
    contract: Dict[str, Any],
    strategy_id: str,
    model_id: Optional[str],
) -> None:
    strategies = _video_strategy_map(contract)
    if not strategies:
        return
    strategy = strategies.get(strategy_id)
    if strategy is None:
        if strategy_id == "text_to_video":
            raise ValueError(
                f"Video model '{model_id}' requires one of the supported media strategies; "
                "attach source_image, source_video, last_frame_image, or reference_images."
            )
        allowed = sorted(strategies)
        raise ValueError(
            f"Unsupported video_input_strategy '{strategy_id}' for model '{model_id}'. "
            f"Supported values: {allowed}"
        )

    requires = strategy.get("requires")
    if not isinstance(requires, list):
        requires = []
    missing = [
        str(slot)
        for slot in requires
        if str(slot).strip() and not _has_video_slot(params, str(slot))
    ]
    if missing:
        raise ValueError(
            f"video_input_strategy '{strategy_id}' requires missing media slot(s): {missing}"
        )

    if requires:
        return

    supports = contract.get("supports") if isinstance(contract.get("supports"), dict) else {}
    if supports.get("reference_to_video") is True:
        if not (
            _has_video_slot(params, "source_video")
            or _has_video_slot(params, "reference_video")
            or _has_video_slot(params, "source_image")
            or _has_video_slot(params, "reference_images")
        ):
            raise ValueError(
                f"video_input_strategy '{strategy_id}' requires one of: "
                "source_video, reference_video, source_image, reference_images"
            )


def _derive_video_input_strategy(params: Dict[str, Any], contract: Dict[str, Any]) -> str:
    source_video = params.get("source_video")
    source_image = params.get("source_image")
    last_frame_image = params.get("last_frame_image")
    video_mask_image = params.get("video_mask_image")
    reference_images = params.get("reference_images")
    supports = contract.get("supports") if isinstance(contract.get("supports"), dict) else {}

    if source_video and supports.get("video_edit") is True:
        return "video_edit"
    if supports.get("reference_to_video") is True and (source_video or source_image or reference_images):
        return "reference_to_video"
    if source_video and last_frame_image and supports.get("video_continuation_to_last_frame") is True:
        return "video_continuation_to_last_frame"
    if source_video and supports.get("video_continuation") is True:
        return "video_continuation"
    if (
        source_image
        and last_frame_image
        and supports.get("first_last_frame") is True
        and supports.get("first_frame_to_video") is True
    ):
        return "first_last_frame_to_video"
    if source_image and supports.get("first_frame_to_video") is True:
        return "first_frame_to_video"
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
    for image_count_key in ("number_of_images", "numberOfImages", "num_images", "numImages", "n"):
        normalized.pop(image_count_key, None)

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
                f"Video extension is not supported for provider '{provider}' model '{model_id}'."
            )
        allowed_counts = _allowed_extension_counts_for_seconds(contract, base_seconds=seconds_value)
        if allowed_counts is not None and extension_count not in allowed_counts:
            raise ValueError(
                f"Unsupported video_extension_count={extension_count} for base seconds={seconds_value}. "
                f"Allowed counts: {allowed_counts}"
            )

    effective_input_strategy = (
        _requested_video_input_strategy(normalized, contract)
        or _derive_video_input_strategy(normalized, contract)
    )
    _validate_video_input_strategy_requirements(
        params=normalized,
        contract=contract,
        strategy_id=effective_input_strategy,
        model_id=model_id,
    )

    normalization_meta = {
        "runtime_api_mode": runtime_api_mode,
        "input_strategy": effective_input_strategy,
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
    api_mode = str(runtime_api_mode or resolved.get("runtime_api_mode") or _DEFAULT_RUNTIME_API_MODE).strip().lower()
    if provider == _GOOGLE_VIDEO_PROVIDER and mode == _IMAGE_GEN_MODE:
        resolved["runtime_api_mode"] = api_mode or _DEFAULT_RUNTIME_API_MODE
        if resolved["runtime_api_mode"] != "vertex_ai":
            _remove_output_mime_controls(resolved)
        return resolved

    if provider == _TONGYI_VIDEO_PROVIDER and mode == _VIDEO_GEN_MODE:
        resolved["runtime_api_mode"] = _TONGYI_RUNTIME_API_MODE
        resolved["video_contract"] = build_video_mode_contract(resolved)
        return resolved

    if provider == _OPENAI_VIDEO_PROVIDER and mode == _VIDEO_GEN_MODE:
        resolved["runtime_api_mode"] = _OPENAI_RUNTIME_API_MODE
        constraints = resolved.setdefault("constraints", {})
        if isinstance(constraints, dict):
            unsupported = list(constraints.get("unsupported_params") or [])
            for key in (
                "negative_prompt",
                "seed",
                "generate_audio",
                "subtitle_mode",
                "subtitle_language",
                "subtitle_script",
            ):
                if key not in unsupported:
                    unsupported.append(key)
            unsupported = [
                key
                for key in unsupported
                if key not in {"enhance_prompt", "prompt_extend", "storyboard_prompt", "storyboard_segments"}
            ]
            constraints["unsupported_params"] = unsupported
        resolved["video_contract"] = build_video_mode_contract(resolved)
        return resolved

    if provider == _GROK_VIDEO_PROVIDER and mode == _VIDEO_GEN_MODE:
        resolved["runtime_api_mode"] = _GROK_RUNTIME_API_MODE
        resolved["video_contract"] = build_video_mode_contract(resolved)
        return resolved

    if provider != _GOOGLE_VIDEO_PROVIDER or mode != _VIDEO_GEN_MODE:
        return resolved

    resolved["runtime_api_mode"] = api_mode or _DEFAULT_RUNTIME_API_MODE

    if resolved["runtime_api_mode"] != "vertex_ai":
        param_options = resolved.get("param_options")
        if isinstance(param_options, dict):
            param_options.pop("generate_audio", None)
        constraints = resolved.get("constraints")
        if isinstance(constraints, dict):
            constraints["supports_generate_audio"] = False
        defaults = resolved.get("defaults")
        if isinstance(defaults, dict):
            defaults["generate_audio"] = False
    else:
        constraints = resolved.get("constraints")
        if isinstance(constraints, dict):
            resolution_values = [
                str(option.get("value"))
                for option in resolved.get("resolution_tiers", [])
                if isinstance(option, dict) and str(option.get("value") or "").strip()
            ]
            constraints["video_extension_require_resolution_values"] = (
                resolution_values
                or constraints.get("video_extension_require_resolution_values")
                or ["720p", "1080p", "4k"]
            )
            constraints.setdefault("max_source_video_seconds", 141)
            constraints.setdefault("max_output_video_seconds", 148)
            constraints.setdefault("max_video_extension_count", 20)

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
    normalized_provider = str(provider or "").strip().lower()
    runtime_api_mode = (
        resolve_google_video_runtime_api_mode(db=db, user_id=user_id)
        if normalized_provider == _GOOGLE_VIDEO_PROVIDER
        else None
    )
    return apply_video_mode_runtime_overrides(
        schema,
        provider=normalized_provider,
        mode=mode,
        runtime_api_mode=runtime_api_mode,
    )
