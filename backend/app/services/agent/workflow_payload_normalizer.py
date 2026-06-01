"""Shared workflow payload normalization and validation helpers."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .workflow_contract import (
    ALLOWED_AUDIO_OUTPUT_FORMATS,
    ALLOWED_IMAGE_OUTPUT_MIME_TYPES,
    ALLOWED_OUTPUT_FORMATS,
    ALLOWED_VIDEO_ASPECT_RATIOS,
    ALLOWED_VIDEO_INPUT_STRATEGIES,
    ALLOWED_VIDEO_MASK_MODES,
    ALLOWED_VIDEO_SUBTITLE_MODES,
    ALLOWED_WORKFLOW_AGENT_TASK_TYPES,
    ALLOWED_WORKFLOW_NODE_TYPES,
    is_active_inline_provider_token,
    is_auto_inline_model_token,
    normalize_workflow_agent_task_type,
    normalize_workflow_image_edit_mode,
    normalize_workflow_video_mask_mode,
    normalize_workflow_video_resolution,
)

ALLOWED_AGENT_DEFAULT_TASK_TYPES = ALLOWED_WORKFLOW_AGENT_TASK_TYPES
ALLOWED_WORKFLOW_ANALYSIS_TYPES = {
    "comprehensive",
    "statistics",
    "correlation",
    "trends",
    "distribution",
}


def _is_active_inline_provider_token(value: Any) -> bool:
    return is_active_inline_provider_token(value)


def _is_auto_inline_model_token(value: Any) -> bool:
    return is_auto_inline_model_token(value)


def _normalize_agent_task_type(raw_value: Any) -> str:
    return normalize_workflow_agent_task_type(raw_value, fallback="chat")


def _normalize_analysis_type(raw_value: Any) -> str:
    raw = str(raw_value or "").strip().lower()
    aliases = {
        "summary": "statistics",
        "stats": "statistics",
        "statistic": "statistics",
        "trend": "trends",
        "anomaly": "distribution",
        "anomalies": "distribution",
        "all": "comprehensive",
    }
    normalized = aliases.get(raw, raw)
    if normalized in ALLOWED_WORKFLOW_ANALYSIS_TYPES:
        return normalized
    return "comprehensive"


def _clamp_optional_int(value: Any, *, minimum: int, maximum: int) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except Exception:
        return None
    return max(minimum, min(maximum, parsed))


def _clamp_optional_float(value: Any, *, minimum: float, maximum: float) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except Exception:
        return None
    return max(minimum, min(maximum, parsed))


def _coerce_optional_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_optional_choice(value: Any, *, allowed: set[str]) -> Optional[str]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    return text if text in allowed else None


def _normalize_optional_string(value: Any, *, max_length: int = 128) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > max_length:
        return text[:max_length]
    return text


def _normalize_string_list(value: Any, *, max_items: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    normalized: List[str] = []
    seen = set()
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_video_resolution(value: Any) -> Optional[str]:
    return normalize_workflow_video_resolution(value)


def _normalize_workflow_input_payload(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(raw_input or {})

    def _normalize_url_fields(list_field: str, snake_list_field: str, single_field: str, snake_single_field: str) -> None:
        urls = _normalize_string_list(payload.get(list_field))
        if not urls:
            urls = _normalize_string_list(payload.get(snake_list_field))
        single_value = str(payload.get(single_field) or payload.get(snake_single_field) or "").strip()
        if single_value:
            urls = _normalize_string_list([single_value, *urls])
        if urls:
            payload[list_field] = urls
            payload[single_field] = urls[0]
        else:
            payload.pop(list_field, None)
            payload.pop(single_field, None)

    _normalize_url_fields("imageUrls", "image_urls", "imageUrl", "image_url")
    _normalize_url_fields("videoUrls", "video_urls", "videoUrl", "video_url")
    _normalize_url_fields("audioUrls", "audio_urls", "audioUrl", "audio_url")
    _normalize_url_fields("fileUrls", "file_urls", "fileUrl", "file_url")

    if "analysis_type" in payload:
        payload["analysis_type"] = _normalize_analysis_type(payload.get("analysis_type"))
    if "analysisType" in payload:
        payload["analysisType"] = _normalize_analysis_type(payload.get("analysisType"))

    task = str(payload.get("task") or payload.get("prompt") or payload.get("text") or "").strip()
    if task:
        payload["task"] = task
    return payload


def _normalize_workflow_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_nodes: List[Dict[str, Any]] = []
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        node = copy.deepcopy(raw_node)
        data = node.get("data")
        if not isinstance(data, dict):
            normalized_nodes.append(node)
            continue

        task_type = data.get("agentTaskType")
        if task_type is None:
            task_type = data.get("agent_task_type")
        if task_type is not None:
            normalized_task_type = _normalize_agent_task_type(task_type)
            data["agentTaskType"] = normalized_task_type
            data["agent_task_type"] = normalized_task_type
        else:
            normalized_task_type = ""

        normalized_analysis_type = None
        if data.get("toolAnalysisType") is not None:
            normalized_analysis_type = _normalize_analysis_type(data.get("toolAnalysisType"))
            data["toolAnalysisType"] = normalized_analysis_type
        if data.get("tool_analysis_type") is not None:
            normalized_analysis_type = _normalize_analysis_type(data.get("tool_analysis_type"))
            data["tool_analysis_type"] = normalized_analysis_type
        if data.get("analysisType") is not None:
            data["analysisType"] = _normalize_analysis_type(data.get("analysisType"))
        if data.get("analysis_type") is not None:
            data["analysis_type"] = _normalize_analysis_type(data.get("analysis_type"))

        for field_name in ("agentNumberOfImages", "toolNumberOfImages", "numberOfImages", "number_of_images"):
            if field_name in data:
                parsed = _clamp_optional_int(data.get(field_name), minimum=1, maximum=8)
                if parsed is None:
                    data.pop(field_name, None)
                else:
                    data[field_name] = parsed

        if "agentImageEditMaxRetries" in data:
            parsed_retries = _clamp_optional_int(data.get("agentImageEditMaxRetries"), minimum=0, maximum=3)
            data["agentImageEditMaxRetries"] = 1 if parsed_retries is None else parsed_retries
        if "agent_image_edit_max_retries" in data:
            parsed_retries = _clamp_optional_int(data.get("agent_image_edit_max_retries"), minimum=0, maximum=3)
            data["agent_image_edit_max_retries"] = 1 if parsed_retries is None else parsed_retries

        if "agentProductMatchThreshold" in data:
            parsed_threshold = _clamp_optional_int(data.get("agentProductMatchThreshold"), minimum=50, maximum=95)
            data["agentProductMatchThreshold"] = 70 if parsed_threshold is None else parsed_threshold
        if "agent_product_match_threshold" in data:
            parsed_threshold = _clamp_optional_int(data.get("agent_product_match_threshold"), minimum=50, maximum=95)
            data["agent_product_match_threshold"] = 70 if parsed_threshold is None else parsed_threshold

        for field_name in ("agentOutputMimeType", "toolOutputMimeType"):
            if field_name in data:
                normalized_mime = _normalize_optional_choice(data.get(field_name), allowed=ALLOWED_IMAGE_OUTPUT_MIME_TYPES)
                if normalized_mime is None:
                    data.pop(field_name, None)
                else:
                    data[field_name] = normalized_mime

        for field_name in ("agentOutputFormat", "outputFormat"):
            if field_name in data:
                normalized_format = _normalize_optional_choice(data.get(field_name), allowed=ALLOWED_OUTPUT_FORMATS)
                if normalized_format is None:
                    data.pop(field_name, None)
                else:
                    data[field_name] = normalized_format

        for field_name in ("toolEditMode", "agentEditMode"):
            if field_name in data:
                normalized_mode = normalize_workflow_image_edit_mode(data.get(field_name))
                if normalized_mode is None:
                    data.pop(field_name, None)
                else:
                    data[field_name] = normalized_mode

        for list_field, single_field in (
            ("startImageUrls", "startImageUrl"),
            ("startVideoUrls", "startVideoUrl"),
            ("startAudioUrls", "startAudioUrl"),
            ("startFileUrls", "startFileUrl"),
        ):
            list_values = _normalize_string_list(data.get(list_field))
            single_value = str(data.get(single_field) or "").strip()
            if single_value:
                list_values = _normalize_string_list([single_value, *list_values])
            if list_values:
                data[list_field] = list_values
                data[single_field] = list_values[0]
            else:
                data.pop(list_field, None)
                data.pop(single_field, None)

        if normalized_task_type == "video-gen":
            for field_name in ("agentVideoDurationSeconds", "agent_video_duration_seconds"):
                if field_name in data:
                    parsed_duration = _clamp_optional_int(data.get(field_name), minimum=1, maximum=20)
                    if parsed_duration is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = parsed_duration

            for field_name in ("agentVideoExtensionCount", "agent_video_extension_count"):
                if field_name in data:
                    parsed_extension_count = _clamp_optional_int(data.get(field_name), minimum=0, maximum=20)
                    if parsed_extension_count is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = parsed_extension_count

            for field_name in (
                "agentVideoAspectRatio",
                "agent_video_aspect_ratio",
                "videoAspectRatio",
                "video_aspect_ratio",
                "agentAspectRatio",
                "agent_aspect_ratio",
            ):
                if field_name in data:
                    normalized_ratio = _normalize_optional_choice(
                        data.get(field_name),
                        allowed=ALLOWED_VIDEO_ASPECT_RATIOS,
                    )
                    if normalized_ratio is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_ratio

            for field_name in (
                "agentVideoResolution",
                "agent_video_resolution",
                "videoResolution",
                "video_resolution",
                "agentResolutionTier",
                "agent_resolution_tier",
            ):
                if field_name in data:
                    normalized_resolution = _normalize_video_resolution(data.get(field_name))
                    if normalized_resolution is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_resolution

            for field_name in (
                "agentContinueFromPreviousVideo",
                "agent_continue_from_previous_video",
                "agentContinueFromPreviousLastFrame",
                "agent_continue_from_previous_last_frame",
                "agentGenerateAudio",
                "agent_generate_audio",
                "agentPromptExtend",
                "agent_prompt_extend",
            ):
                if field_name in data:
                    data[field_name] = _coerce_optional_bool(data.get(field_name), default=False)

            for field_name in ("agentSubtitleMode", "agent_subtitle_mode"):
                if field_name in data:
                    normalized_subtitle_mode = _normalize_optional_choice(
                        data.get(field_name),
                        allowed=ALLOWED_VIDEO_SUBTITLE_MODES,
                    )
                    if normalized_subtitle_mode is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_subtitle_mode

            for field_name in ("agentVideoMaskMode", "agent_video_mask_mode"):
                if field_name in data:
                    normalized_mask_mode = normalize_workflow_video_mask_mode(data.get(field_name))
                    if normalized_mask_mode is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_mask_mode

            for field_name in ("agentVideoInputStrategy", "agent_video_input_strategy"):
                if field_name in data:
                    normalized_strategy = _normalize_optional_choice(
                        data.get(field_name),
                        allowed=ALLOWED_VIDEO_INPUT_STRATEGIES,
                    )
                    if normalized_strategy is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_strategy

            for field_name, max_length in (
                ("agentSubtitleLanguage", 32),
                ("agent_subtitle_language", 32),
                ("agentSubtitleScript", 4000),
                ("agent_subtitle_script", 4000),
                ("agentStoryboardPrompt", 4000),
                ("agent_storyboard_prompt", 4000),
                ("agentNegativePrompt", 4000),
                ("agent_negative_prompt", 4000),
                ("agentSourceVideoUrl", 2048),
                ("agent_source_video_url", 2048),
                ("agentLastFrameImageUrl", 2048),
                ("agent_last_frame_image_url", 2048),
                ("agentVideoMaskImageUrl", 2048),
                ("agent_video_mask_image_url", 2048),
                ("agentAudioUrl", 2048),
                ("agent_audio_url", 2048),
            ):
                if field_name in data:
                    normalized_text = _normalize_optional_string(data.get(field_name), max_length=max_length)
                    if normalized_text is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_text

            for field_name in ("agentSeed", "agent_seed"):
                if field_name in data:
                    parsed_seed = _clamp_optional_int(data.get(field_name), minimum=-1, maximum=2147483647)
                    if parsed_seed is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = parsed_seed

        if normalized_task_type == "audio-gen":
            for field_name in (
                "agentSpeechSpeed",
                "agent_speech_speed",
                "agentAudioSpeed",
                "agent_audio_speed",
            ):
                if field_name in data:
                    parsed_speed = _clamp_optional_float(data.get(field_name), minimum=0.25, maximum=4.0)
                    if parsed_speed is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = parsed_speed

            for field_name in (
                "agentAudioFormat",
                "agent_audio_format",
                "agentSpeechFormat",
                "agent_speech_format",
            ):
                if field_name in data:
                    normalized_audio_format = _normalize_optional_choice(
                        data.get(field_name),
                        allowed=ALLOWED_AUDIO_OUTPUT_FORMATS,
                    )
                    if normalized_audio_format is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_audio_format

            for field_name in ("agentVoice", "agent_voice"):
                if field_name in data:
                    normalized_voice = _normalize_optional_string(data.get(field_name), max_length=64)
                    if normalized_voice is None:
                        data.pop(field_name, None)
                    else:
                        data[field_name] = normalized_voice

        node["data"] = data
        normalized_nodes.append(node)
    return normalized_nodes


def _normalize_agent_default_task_type(value: Any) -> str:
    return normalize_workflow_agent_task_type(value, fallback="")


def _validate_and_normalize_agent_card(raw_agent_card: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if raw_agent_card is None:
        return None
    if not isinstance(raw_agent_card, dict):
        raise HTTPException(status_code=400, detail="agentCard must be an object")

    normalized_card = copy.deepcopy(raw_agent_card)
    defaults = normalized_card.get("defaults")
    if defaults is None:
        return normalized_card
    if not isinstance(defaults, dict):
        raise HTTPException(status_code=400, detail="agentCard.defaults must be an object")

    raw_task_type = defaults.get("defaultTaskType")
    if raw_task_type is not None:
        normalized_task_type = _normalize_agent_default_task_type(raw_task_type)
        if normalized_task_type not in ALLOWED_AGENT_DEFAULT_TASK_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    "agentCard.defaults.defaultTaskType 不合法，"
                    f"可选值: {sorted(ALLOWED_AGENT_DEFAULT_TASK_TYPES)}"
                ),
            )
        defaults["defaultTaskType"] = normalized_task_type

    vision_defaults = defaults.get("visionUnderstand")
    if vision_defaults is not None:
        if not isinstance(vision_defaults, dict):
            raise HTTPException(status_code=400, detail="agentCard.defaults.visionUnderstand must be an object")
        output_format = vision_defaults.get("outputFormat")
        if output_format is not None:
            normalized_output_format = str(output_format or "").strip().lower()
            if normalized_output_format not in {"text", "json", "markdown"}:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.visionUnderstand.outputFormat must be text/json/markdown",
                )
            vision_defaults["outputFormat"] = normalized_output_format

    data_defaults = defaults.get("dataAnalysis")
    if data_defaults is not None and isinstance(data_defaults, dict):
        output_format = data_defaults.get("outputFormat")
        if output_format is not None:
            normalized_output_format = str(output_format or "").strip().lower()
            if normalized_output_format in {"text", "json", "markdown"}:
                data_defaults["outputFormat"] = normalized_output_format

    image_edit_defaults = defaults.get("imageEdit")
    if image_edit_defaults is not None:
        if not isinstance(image_edit_defaults, dict):
            raise HTTPException(status_code=400, detail="agentCard.defaults.imageEdit must be an object")

        edit_mode = image_edit_defaults.get("editMode")
        if edit_mode is not None:
            normalized_edit_mode = normalize_workflow_image_edit_mode(edit_mode)
            if normalized_edit_mode is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.imageEdit.editMode is not supported",
                )
            image_edit_defaults["editMode"] = normalized_edit_mode

        for field_name, max_length in (
            ("aspectRatio", 32),
            ("imageSize", 32),
            ("resolutionTier", 32),
            ("outputLanguage", 32),
        ):
            if field_name in image_edit_defaults:
                normalized_text = _normalize_optional_string(
                    image_edit_defaults.get(field_name),
                    max_length=max_length,
                )
                if normalized_text is None:
                    image_edit_defaults.pop(field_name, None)
                else:
                    image_edit_defaults[field_name] = normalized_text

        number_of_images = image_edit_defaults.get("numberOfImages", image_edit_defaults.get("number_of_images"))
        if number_of_images is not None:
            parsed_number = _clamp_optional_int(number_of_images, minimum=1, maximum=8)
            if parsed_number is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.imageEdit.numberOfImages must be an integer between 1 and 8",
                )
            image_edit_defaults["numberOfImages"] = parsed_number

        output_mime_type = image_edit_defaults.get("outputMimeType", image_edit_defaults.get("output_mime_type"))
        if output_mime_type is not None:
            normalized_mime_type = _normalize_optional_choice(
                output_mime_type,
                allowed=ALLOWED_IMAGE_OUTPUT_MIME_TYPES,
            )
            if normalized_mime_type is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.imageEdit.outputMimeType must be image/png, image/jpeg, or image/webp",
                )
            image_edit_defaults["outputMimeType"] = normalized_mime_type

        for field_name in ("promptExtend", "addMagicSuffix", "preserveProductIdentity"):
            if field_name in image_edit_defaults:
                image_edit_defaults[field_name] = _coerce_optional_bool(
                    image_edit_defaults.get(field_name),
                    default=False,
                )

        product_match_threshold = image_edit_defaults.get(
            "productMatchThreshold",
            image_edit_defaults.get("product_match_threshold"),
        )
        if product_match_threshold is not None:
            parsed_threshold = _clamp_optional_int(product_match_threshold, minimum=50, maximum=95)
            if parsed_threshold is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.imageEdit.productMatchThreshold must be an integer between 50 and 95",
                )
            image_edit_defaults["productMatchThreshold"] = parsed_threshold

        max_retries = image_edit_defaults.get("maxRetries", image_edit_defaults.get("max_retries"))
        if max_retries is not None:
            parsed_retries = _clamp_optional_int(max_retries, minimum=0, maximum=3)
            if parsed_retries is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.imageEdit.maxRetries must be an integer between 0 and 3",
                )
            image_edit_defaults["maxRetries"] = parsed_retries

    video_defaults = defaults.get("videoGeneration")
    if video_defaults is not None:
        if not isinstance(video_defaults, dict):
            raise HTTPException(status_code=400, detail="agentCard.defaults.videoGeneration must be an object")

        aspect_ratio = video_defaults.get("aspectRatio")
        if aspect_ratio is not None:
            normalized_aspect_ratio = _normalize_optional_choice(
                aspect_ratio,
                allowed=ALLOWED_VIDEO_ASPECT_RATIOS,
            )
            if normalized_aspect_ratio is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.aspectRatio must be 16:9 or 9:16",
                )
            video_defaults["aspectRatio"] = normalized_aspect_ratio

        resolution = video_defaults.get("resolution")
        if resolution is not None:
            normalized_resolution = _normalize_video_resolution(resolution)
            if normalized_resolution is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.resolution must be 720p/1080p/4k or a supported alias",
                )
            video_defaults["resolution"] = normalized_resolution

        duration_seconds = video_defaults.get("durationSeconds", video_defaults.get("duration_seconds"))
        if duration_seconds is not None:
            parsed_duration = _clamp_optional_int(duration_seconds, minimum=1, maximum=20)
            if parsed_duration is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.durationSeconds must be an integer between 1 and 20",
                )
            video_defaults["durationSeconds"] = parsed_duration

        continue_from_previous_video = video_defaults.get("continueFromPreviousVideo")
        if continue_from_previous_video is not None:
            video_defaults["continueFromPreviousVideo"] = _coerce_optional_bool(
                continue_from_previous_video,
                default=False,
            )

        continue_from_previous_last_frame = video_defaults.get("continueFromPreviousLastFrame")
        if continue_from_previous_last_frame is not None:
            video_defaults["continueFromPreviousLastFrame"] = _coerce_optional_bool(
                continue_from_previous_last_frame,
                default=False,
            )

        video_extension_count = video_defaults.get("videoExtensionCount", video_defaults.get("video_extension_count"))
        if video_extension_count is not None:
            parsed_extension_count = _clamp_optional_int(video_extension_count, minimum=0, maximum=20)
            if parsed_extension_count is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.videoExtensionCount must be an integer between 0 and 20",
                )
            video_defaults["videoExtensionCount"] = parsed_extension_count

        video_input_strategy = video_defaults.get(
            "videoInputStrategy",
            video_defaults.get("video_input_strategy"),
        )
        if video_input_strategy is not None:
            normalized_strategy = _normalize_optional_choice(
                video_input_strategy,
                allowed=ALLOWED_VIDEO_INPUT_STRATEGIES,
            )
            if normalized_strategy is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.videoInputStrategy is not supported",
                )
            video_defaults["videoInputStrategy"] = normalized_strategy

        generate_audio = video_defaults.get("generateAudio", video_defaults.get("generate_audio"))
        if generate_audio is not None:
            video_defaults["generateAudio"] = _coerce_optional_bool(generate_audio, default=False)

        prompt_extend = video_defaults.get("promptExtend", video_defaults.get("prompt_extend"))
        if prompt_extend is not None:
            video_defaults["promptExtend"] = _coerce_optional_bool(prompt_extend, default=False)

        subtitle_mode = video_defaults.get("subtitleMode", video_defaults.get("subtitle_mode"))
        if subtitle_mode is not None:
            normalized_subtitle_mode = _normalize_optional_choice(
                subtitle_mode,
                allowed=ALLOWED_VIDEO_SUBTITLE_MODES,
            )
            if normalized_subtitle_mode is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.subtitleMode must be none/vtt/srt/both",
                )
            video_defaults["subtitleMode"] = normalized_subtitle_mode

        for field_name, max_length in (
            ("subtitleLanguage", 32),
            ("subtitleScript", 4000),
            ("storyboardPrompt", 4000),
            ("negativePrompt", 4000),
            ("audioUrl", 2048),
        ):
            if field_name in video_defaults:
                normalized_text = _normalize_optional_string(video_defaults.get(field_name), max_length=max_length)
                if normalized_text is None:
                    video_defaults.pop(field_name, None)
                else:
                    video_defaults[field_name] = normalized_text

        seed = video_defaults.get("seed")
        if seed is not None:
            parsed_seed = _clamp_optional_int(seed, minimum=-1, maximum=2147483647)
            if parsed_seed is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.videoGeneration.seed must be an integer",
                )
            video_defaults["seed"] = parsed_seed

    audio_defaults = defaults.get("audioGeneration")
    legacy_audio_defaults = defaults.get("speechGeneration")
    if audio_defaults is None and legacy_audio_defaults is not None:
        audio_defaults = legacy_audio_defaults
    if audio_defaults is not None:
        if not isinstance(audio_defaults, dict):
            raise HTTPException(status_code=400, detail="agentCard.defaults.audioGeneration must be an object")

        voice = audio_defaults.get("voice")
        if voice is not None:
            normalized_voice = _normalize_optional_string(voice, max_length=64)
            if normalized_voice is None:
                raise HTTPException(status_code=400, detail="agentCard.defaults.audioGeneration.voice cannot be empty")
            audio_defaults["voice"] = normalized_voice

        audio_format = audio_defaults.get("responseFormat", audio_defaults.get("format"))
        if audio_format is not None:
            normalized_audio_format = _normalize_optional_choice(
                audio_format,
                allowed=ALLOWED_AUDIO_OUTPUT_FORMATS,
            )
            if normalized_audio_format is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.audioGeneration.responseFormat must be mp3/wav/opus/aac/flac/pcm",
                )
            audio_defaults["responseFormat"] = normalized_audio_format

        speed = audio_defaults.get("speed")
        if speed is not None:
            parsed_speed = _clamp_optional_float(speed, minimum=0.25, maximum=4.0)
            if parsed_speed is None:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.audioGeneration.speed must be a number between 0.25 and 4.0",
                )
            audio_defaults["speed"] = parsed_speed

        defaults["audioGeneration"] = audio_defaults
        if legacy_audio_defaults is not None:
            defaults["speechGeneration"] = dict(audio_defaults)

    llm_defaults = defaults.get("llm")
    if llm_defaults is not None:
        if not isinstance(llm_defaults, dict):
            raise HTTPException(status_code=400, detail="agentCard.defaults.llm must be an object")

        provider_id = llm_defaults.get("providerId", llm_defaults.get("provider_id"))
        if provider_id is not None:
            normalized_provider = str(provider_id or "").strip()
            if not normalized_provider:
                raise HTTPException(status_code=400, detail="agentCard.defaults.llm.providerId cannot be empty")
            llm_defaults["providerId"] = normalized_provider

        model_id = llm_defaults.get("modelId", llm_defaults.get("model_id"))
        if model_id is not None:
            normalized_model = str(model_id or "").strip()
            if not normalized_model:
                raise HTTPException(status_code=400, detail="agentCard.defaults.llm.modelId cannot be empty")
            llm_defaults["modelId"] = normalized_model

        profile_id = llm_defaults.get("profileId", llm_defaults.get("profile_id"))
        if profile_id is not None:
            normalized_profile = str(profile_id or "").strip()
            if not normalized_profile:
                raise HTTPException(status_code=400, detail="agentCard.defaults.llm.profileId cannot be empty")
            llm_defaults["profileId"] = normalized_profile

        system_prompt = llm_defaults.get("systemPrompt", llm_defaults.get("system_prompt"))
        if system_prompt is not None:
            llm_defaults["systemPrompt"] = str(system_prompt or "").strip()

        temperature = llm_defaults.get("temperature")
        if temperature is not None:
            try:
                normalized_temperature = float(str(temperature).strip())
            except Exception:
                raise HTTPException(status_code=400, detail="agentCard.defaults.llm.temperature must be a number")
            if normalized_temperature < 0 or normalized_temperature > 2:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.llm.temperature must be between 0 and 2",
                )
            llm_defaults["temperature"] = normalized_temperature

        max_tokens = llm_defaults.get("maxTokens", llm_defaults.get("max_tokens"))
        if max_tokens is not None:
            try:
                normalized_max_tokens = int(float(str(max_tokens).strip()))
            except Exception:
                raise HTTPException(status_code=400, detail="agentCard.defaults.llm.maxTokens must be an integer")
            if normalized_max_tokens < 1 or normalized_max_tokens > 65536:
                raise HTTPException(
                    status_code=400,
                    detail="agentCard.defaults.llm.maxTokens must be between 1 and 65536",
                )
            llm_defaults["maxTokens"] = normalized_max_tokens

        prefer_latest = llm_defaults.get("preferLatestModel", llm_defaults.get("prefer_latest_model"))
        if prefer_latest is not None:
            if isinstance(prefer_latest, bool):
                normalized_prefer_latest = prefer_latest
            else:
                normalized_text = str(prefer_latest or "").strip().lower()
                if normalized_text in {"1", "true", "yes", "on"}:
                    normalized_prefer_latest = True
                elif normalized_text in {"0", "false", "no", "off"}:
                    normalized_prefer_latest = False
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="agentCard.defaults.llm.preferLatestModel must be boolean",
                    )
            llm_defaults["preferLatestModel"] = normalized_prefer_latest

    return normalized_card


def _validate_workflow_execute_payload(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Optional[str]:
    """基础工作流结构校验，防止坏图进入执行引擎。"""
    if not isinstance(nodes, list) or len(nodes) == 0:
        return "工作流至少需要一个节点"

    node_ids: List[str] = []
    node_types: Dict[str, str] = {}
    for idx, node in enumerate(nodes):
        node_id = str((node or {}).get("id") or "").strip()
        if not node_id:
            return f"节点[{idx}] 缺少 id"
        node_ids.append(node_id)
        data = (node or {}).get("data")
        node_type = ""
        if isinstance(data, dict):
            node_type = str(data.get("type") or "").strip().lower().replace("-", "_")
        if not node_type:
            node_type = str((node or {}).get("type") or "").strip().lower().replace("-", "_")
        node_types[node_id] = node_type

        if node_type not in ALLOWED_WORKFLOW_NODE_TYPES:
            return f"Unsupported workflow node type: {node_type or '<empty>'}"

        if node_type == "agent":
            node_data = data if isinstance(data, dict) else {}
            agent_id = str(node_data.get("agentId") or node_data.get("agent_id") or "").strip()
            agent_name = str(node_data.get("agentName") or node_data.get("agent_name") or "").strip()
            inline_use_active_profile = str(
                node_data.get("inlineUseActiveProfile")
                or node_data.get("inline_use_active_profile")
                or ""
            ).strip().lower() in {"1", "true", "yes", "on"}
            inline_provider = str(
                node_data.get("inlineProviderId")
                or node_data.get("inline_provider_id")
                or node_data.get("providerId")
                or node_data.get("provider_id")
                or node_data.get("modelOverrideProviderId")
                or node_data.get("model_override_provider_id")
                or ""
            ).strip()
            inline_model = str(
                node_data.get("inlineModelId")
                or node_data.get("inline_model_id")
                or node_data.get("modelId")
                or node_data.get("model_id")
                or node_data.get("modelOverrideModelId")
                or node_data.get("model_override_model_id")
                or ""
            ).strip()
            active_inline_binding = (
                _is_active_inline_provider_token(inline_provider)
                and _is_auto_inline_model_token(inline_model)
            )
            if (
                not agent_id
                and not agent_name
                and not inline_use_active_profile
                and not active_inline_binding
                and (not inline_provider or not inline_model)
            ):
                return (
                    f"智能体节点[{node_id}] 必须配置 agentId / agentName，"
                    "或提供 inlineProviderId + inlineModelId，"
                    "或启用 inlineUseActiveProfile"
                )
        elif node_type == "human":
            node_data = data if isinstance(data, dict) else {}
            has_explicit_auto_approve = "autoApprove" in node_data or "auto_approve" in node_data
            auto_approve_value = node_data.get("autoApprove", node_data.get("auto_approve"))
            auto_approve = (
                auto_approve_value
                if isinstance(auto_approve_value, bool)
                else str(auto_approve_value or "").strip().lower() in {"1", "true", "yes", "on"}
            )
            if not (has_explicit_auto_approve and auto_approve):
                return (
                    f"人工审核节点[{node_id}] 当前没有真实人工确认流程，"
                    "必须显式配置 autoApprove=true 后才能执行"
                )

    unique_node_ids = set(node_ids)
    if len(unique_node_ids) != len(node_ids):
        return "存在重复的节点 id"

    if not isinstance(edges, list):
        return "edges 必须是数组"

    incoming_count: Dict[str, int] = {node_id: 0 for node_id in unique_node_ids}
    outgoing_count: Dict[str, int] = {node_id: 0 for node_id in unique_node_ids}
    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in unique_node_ids}
    reverse_adjacency: Dict[str, List[str]] = {node_id: [] for node_id in unique_node_ids}

    for idx, edge in enumerate(edges):
        source = str((edge or {}).get("source") or "").strip()
        target = str((edge or {}).get("target") or "").strip()
        if not source or not target:
            return f"连线[{idx}] 缺少 source 或 target"
        if source not in unique_node_ids:
            return f"连线[{idx}] 的 source 不存在：{source}"
        if target not in unique_node_ids:
            return f"连线[{idx}] 的 target 不存在：{target}"
        outgoing_count[source] += 1
        incoming_count[target] += 1
        adjacency[source].append(target)
        reverse_adjacency[target].append(source)

    start_ids = [node_id for node_id, node_type in node_types.items() if node_type == "start"]
    end_ids = [node_id for node_id, node_type in node_types.items() if node_type == "end"]

    if len(start_ids) == 0:
        return "工作流必须包含一个开始节点"
    if len(start_ids) > 1:
        return "工作流只能包含一个开始节点"
    if len(end_ids) == 0:
        return "工作流必须包含一个结束节点"
    if len(end_ids) > 1:
        return "工作流只能包含一个结束节点"

    start_id = start_ids[0]
    end_id = end_ids[0]

    if incoming_count.get(start_id, 0) > 0:
        return "开始节点不能有输入连接"
    if outgoing_count.get(start_id, 0) == 0:
        return "开始节点至少需要一条输出连接"
    if incoming_count.get(end_id, 0) == 0:
        return "结束节点至少需要一条输入连接"
    if outgoing_count.get(end_id, 0) > 0:
        return "结束节点不能有输出连接"

    def _bfs(seed: str, graph: Dict[str, List[str]]) -> set:
        visited = set()
        queue = [seed]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for nxt in graph.get(current, []):
                if nxt not in visited:
                    queue.append(nxt)
        return visited

    reachable_from_start = _bfs(start_id, adjacency)
    if end_id not in reachable_from_start:
        return "工作流必须存在从开始节点到结束节点的路径"

    unreachable_nodes = [node_id for node_id in node_ids if node_id not in reachable_from_start]
    if unreachable_nodes:
        preview = ", ".join(unreachable_nodes[:3])
        more = len(unreachable_nodes) - 3
        suffix = f" 等 {len(unreachable_nodes)} 个节点" if more > 0 else ""
        return f"存在未从开始节点连通的节点: {preview}{suffix}"

    can_reach_end = _bfs(end_id, reverse_adjacency)
    no_end_path_nodes = [node_id for node_id in node_ids if node_id not in can_reach_end]
    if no_end_path_nodes:
        preview = ", ".join(no_end_path_nodes[:3])
        more = len(no_end_path_nodes) - 3
        suffix = f" 等 {len(no_end_path_nodes)} 个节点" if more > 0 else ""
        return f"存在无法流向结束节点的节点: {preview}{suffix}"

    return None
