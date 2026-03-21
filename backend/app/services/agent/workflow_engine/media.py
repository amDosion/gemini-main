"""
Media generation and normalization helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Tuple


def build_video_generate_kwargs(engine: Any, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}

    aspect_ratio = engine._get_tool_arg(
        tool_args,
        "aspect_ratio",
        "aspectRatio",
        "video_aspect_ratio",
        "videoAspectRatio",
    )
    aspect_ratio_text = str(aspect_ratio or "").strip()
    if aspect_ratio_text in {"16:9", "9:16"}:
        kwargs["aspect_ratio"] = aspect_ratio_text

    resolution_raw = engine._get_tool_arg(
        tool_args,
        "resolution",
        "video_resolution",
        "videoResolution",
        "resolution_tier",
        "resolutionTier",
        "image_size",
        "imageSize",
    )
    normalized_resolution = engine._resolve_video_resolution(resolution_raw)
    if normalized_resolution is not None:
        kwargs["resolution"] = normalized_resolution

    duration_seconds = engine._to_int(
        engine._get_tool_arg(
            tool_args,
            "duration_seconds",
            "durationSeconds",
            "video_duration_seconds",
            "videoDurationSeconds",
            "duration",
        ),
        default=None,
        minimum=1,
        maximum=20,
    )
    if duration_seconds is not None:
        kwargs["duration_seconds"] = duration_seconds

    video_extension_count = engine._to_int(
        engine._get_tool_arg(
            tool_args,
            "video_extension_count",
            "videoExtensionCount",
        ),
        default=None,
        minimum=0,
        maximum=20,
    )
    if video_extension_count is not None:
        kwargs["video_extension_count"] = video_extension_count

    fps = engine._to_int(
        engine._get_tool_arg(tool_args, "fps", "frame_rate", "frameRate"),
        default=None,
        minimum=1,
        maximum=60,
    )
    if fps is not None:
        kwargs["fps"] = fps

    seed = engine._to_int(engine._get_tool_arg(tool_args, "seed"), default=None)
    if seed is not None:
        kwargs["seed"] = seed

    negative_prompt = engine._get_tool_arg(tool_args, "negative_prompt", "negativePrompt")
    if negative_prompt is not None:
        kwargs["negative_prompt"] = str(negative_prompt)

    prompt_extend = engine._get_tool_arg(
        tool_args,
        "prompt_extend",
        "promptExtend",
        "enhance_prompt",
        "enhancePrompt",
    )
    if prompt_extend is not None:
        kwargs["enhance_prompt"] = engine._to_bool(prompt_extend)

    generate_audio = engine._get_tool_arg(tool_args, "generate_audio", "generateAudio")
    if generate_audio is not None:
        kwargs["generate_audio"] = engine._to_bool(generate_audio)

    person_generation = engine._get_tool_arg(
        tool_args,
        "person_generation",
        "personGeneration",
    )
    if person_generation is not None and str(person_generation).strip():
        kwargs["person_generation"] = str(person_generation).strip()

    subtitle_mode = engine._get_tool_arg(tool_args, "subtitle_mode", "subtitleMode")
    if subtitle_mode is not None and str(subtitle_mode).strip():
        kwargs["subtitle_mode"] = str(subtitle_mode).strip()

    subtitle_language = engine._get_tool_arg(
        tool_args,
        "subtitle_language",
        "subtitleLanguage",
    )
    if subtitle_language is not None and str(subtitle_language).strip():
        kwargs["subtitle_language"] = str(subtitle_language).strip()

    subtitle_script = engine._get_tool_arg(
        tool_args,
        "subtitle_script",
        "subtitleScript",
    )
    if subtitle_script is not None and str(subtitle_script).strip():
        kwargs["subtitle_script"] = str(subtitle_script).strip()

    storyboard_prompt = engine._get_tool_arg(
        tool_args,
        "storyboard_prompt",
        "storyboardPrompt",
    )
    if storyboard_prompt is not None and str(storyboard_prompt).strip():
        kwargs["storyboard_prompt"] = str(storyboard_prompt).strip()

    source_video = engine._get_tool_arg(
        tool_args,
        "source_video",
        "sourceVideo",
        "continuation_video",
        "continuationVideo",
    )
    normalized_source_video = engine._extract_first_video_url(source_video)
    provider_file_name = str(
        engine._get_tool_arg(tool_args, "provider_file_name", "providerFileName")
        or ""
    ).strip()
    provider_file_uri = str(
        engine._get_tool_arg(tool_args, "provider_file_uri", "providerFileUri")
        or ""
    ).strip()
    gcs_uri = str(
        engine._get_tool_arg(tool_args, "gcs_uri", "gcsUri")
        or ""
    ).strip()
    mime_type = str(
        engine._get_tool_arg(tool_args, "mime_type", "mimeType")
        or ""
    ).strip()
    if isinstance(source_video, dict):
        if not provider_file_name:
            provider_file_name = str(
                source_video.get("provider_file_name")
                or source_video.get("providerFileName")
                or ""
            ).strip()
        if not provider_file_uri:
            provider_file_uri = str(
                source_video.get("provider_file_uri")
                or source_video.get("providerFileUri")
                or ""
            ).strip()
        if not gcs_uri:
            gcs_uri = str(source_video.get("gcs_uri") or source_video.get("gcsUri") or "").strip()
        if not mime_type:
            mime_type = str(source_video.get("mime_type") or source_video.get("mimeType") or "").strip()
    if not provider_file_uri and isinstance(tool_args.get("input"), dict):
        provider_file_uri = str(
            tool_args["input"].get("provider_file_uri")
            or tool_args["input"].get("providerFileUri")
            or ""
        ).strip()
    if not provider_file_name and isinstance(tool_args.get("input"), dict):
        provider_file_name = str(
            tool_args["input"].get("provider_file_name")
            or tool_args["input"].get("providerFileName")
            or ""
        ).strip()
    if not gcs_uri and isinstance(tool_args.get("input"), dict):
        gcs_uri = str(tool_args["input"].get("gcs_uri") or tool_args["input"].get("gcsUri") or "").strip()
    if not mime_type and isinstance(tool_args.get("input"), dict):
        mime_type = str(tool_args["input"].get("mime_type") or tool_args["input"].get("mimeType") or "").strip()
    if normalized_source_video:
        if provider_file_uri or gcs_uri or mime_type:
            kwargs["source_video"] = {
                "url": normalized_source_video,
                **({"provider_file_name": provider_file_name} if provider_file_name else {}),
                **({"provider_file_uri": provider_file_uri} if provider_file_uri else {}),
                **({"gcs_uri": gcs_uri} if gcs_uri else {}),
                **({"mime_type": mime_type} if mime_type else {}),
            }
        else:
            kwargs["source_video"] = normalized_source_video
    elif provider_file_name or provider_file_uri or gcs_uri:
        kwargs["source_video"] = {
            **({"provider_file_name": provider_file_name} if provider_file_name else {}),
            **({"provider_file_uri": provider_file_uri} if provider_file_uri else {}),
            **({"gcs_uri": gcs_uri} if gcs_uri else {}),
            **({"mime_type": mime_type} if mime_type else {}),
        }

    source_image = engine._get_tool_arg(
        tool_args,
        "source_image",
        "sourceImage",
        "image_url",
        "imageUrl",
        "reference_image_url",
        "referenceImageUrl",
    )
    normalized_source_image = engine._extract_first_image_url(source_image)
    if normalized_source_image:
        kwargs["source_image"] = normalized_source_image

    last_frame_image = engine._get_tool_arg(
        tool_args,
        "last_frame_image",
        "lastFrameImage",
        "end_frame_image",
        "endFrameImage",
    )
    normalized_last_frame_image = engine._extract_first_image_url(last_frame_image)
    if normalized_last_frame_image:
        kwargs["last_frame_image"] = normalized_last_frame_image

    video_mask_image = engine._get_tool_arg(
        tool_args,
        "video_mask_image",
        "videoMaskImage",
        "mask_image",
        "maskImage",
        "mask_url",
        "maskUrl",
    )
    normalized_video_mask_image = engine._extract_first_image_url(video_mask_image)
    if normalized_video_mask_image:
        kwargs["video_mask_image"] = normalized_video_mask_image

    video_mask_mode = engine._get_tool_arg(
        tool_args,
        "video_mask_mode",
        "videoMaskMode",
        "mask_mode",
        "maskMode",
        "edit_mode",
        "editMode",
    )
    if video_mask_mode is not None:
        kwargs["video_mask_mode"] = str(video_mask_mode).strip()

    last_frame_bridge = engine._get_tool_arg(
        tool_args,
        "use_last_frame_bridge",
        "continue_from_last_frame",
        "continueFromLastFrame",
    )
    if last_frame_bridge is not None:
        kwargs["use_last_frame_bridge"] = engine._to_bool(last_frame_bridge)

    return kwargs


def build_audio_generate_kwargs(engine: Any, tool_args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    kwargs: Dict[str, Any] = {}
    voice = str(
        engine._get_tool_arg(tool_args, "voice", "agent_voice", "agentVoice")
        or "alloy"
    ).strip() or "alloy"

    response_format = engine._get_tool_arg(
        tool_args,
        "response_format",
        "responseFormat",
        "audio_format",
        "audioFormat",
    )
    normalized_response_format = str(response_format or "").strip().lower()
    if normalized_response_format in {"mp3", "wav", "opus", "aac", "flac", "pcm"}:
        kwargs["response_format"] = normalized_response_format

    speed = engine._to_float(
        engine._get_tool_arg(tool_args, "speed", "speech_speed", "speechSpeed", "audio_speed", "audioSpeed"),
        default=None,
        minimum=0.25,
        maximum=4.0,
    )
    if speed is not None:
        kwargs["speed"] = speed

    return voice, kwargs


def normalize_video_service_result(engine: Any, raw_result: Any) -> Dict[str, Any]:
    if isinstance(raw_result, dict):
        normalized: Dict[str, Any] = dict(raw_result)
        video_url = engine._normalize_possible_result_media_url(
            raw_result.get("videoUrl")
            or raw_result.get("video_url")
            or raw_result.get("url")
            or raw_result.get("video")
        )
        if not video_url:
            videos = raw_result.get("videos")
            if isinstance(videos, list):
                for item in videos:
                    if isinstance(item, dict):
                        video_url = engine._normalize_possible_result_media_url(
                            item.get("url") or item.get("videoUrl") or item.get("video_url")
                        )
                    else:
                        video_url = engine._normalize_possible_result_media_url(item)
                    if video_url:
                        break
    else:
        normalized = {}
        video_url = engine._normalize_possible_result_media_url(raw_result)

    if not video_url:
        raise ValueError("视频生成成功但未返回可展示的视频 URL")

    normalized["videoUrl"] = video_url
    normalized["videoUrls"] = [video_url]
    normalized["count"] = 1

    duration_value = normalized.get("durationSeconds", normalized.get("duration", normalized.get("duration_seconds")))
    normalized_duration = engine._to_int(duration_value, default=None, minimum=1, maximum=300)
    if normalized_duration is not None:
        normalized["durationSeconds"] = normalized_duration

    return normalized


def normalize_audio_service_result(
    engine: Any,
    raw_result: Any,
    fallback_format: str = "mp3",
) -> Dict[str, Any]:
    normalized: Dict[str, Any]
    if isinstance(raw_result, dict):
        normalized = dict(raw_result)
        audio_url = engine._normalize_possible_result_media_url(
            raw_result.get("audioUrl")
            or raw_result.get("audio_url")
            or raw_result.get("url")
        )
        audio_blob = raw_result.get("audio")
        if audio_blob is None:
            audio_blob = raw_result.get("content")
        if audio_blob is None:
            audio_blob = raw_result.get("bytes")
        audio_format = str(
            raw_result.get("format")
            or raw_result.get("response_format")
            or fallback_format
            or "mp3"
        ).strip().lower() or "mp3"
        mime_type = str(raw_result.get("mime_type") or raw_result.get("mimeType") or "").strip().lower()
    else:
        normalized = {}
        audio_url = engine._normalize_possible_result_media_url(raw_result)
        audio_blob = raw_result if isinstance(raw_result, (bytes, bytearray)) else None
        audio_format = str(fallback_format or "mp3").strip().lower() or "mp3"
        mime_type = ""

    if audio_format not in {"mp3", "wav", "opus", "aac", "flac", "pcm"}:
        audio_format = str(fallback_format or "mp3").strip().lower() or "mp3"

    if not audio_url and isinstance(audio_blob, (bytes, bytearray)):
        resolved_mime_type = mime_type or engine._guess_audio_mime_type(audio_format)
        encoded_audio = base64.b64encode(bytes(audio_blob)).decode("ascii")
        audio_url = f"data:{resolved_mime_type};base64,{encoded_audio}"

    if not audio_url:
        raise ValueError("语音生成成功但未返回可展示的音频 URL")

    normalized.pop("audio", None)
    normalized.pop("content", None)
    normalized.pop("bytes", None)
    normalized["audioUrl"] = audio_url
    normalized["audioUrls"] = [audio_url]
    normalized["count"] = 1
    normalized["format"] = audio_format
    normalized["mimeType"] = mime_type or engine._guess_audio_mime_type(audio_format)
    return normalized


async def run_video_generate_task(
    engine: Any,
    *,
    provider_id: str,
    model_id: str,
    profile_id: str,
    prompt: str,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    service = await engine._create_provider_service(provider_id=provider_id, profile_id=profile_id)
    generate_video = getattr(service, "generate_video", None)
    if generate_video is None or not callable(generate_video):
        raise ValueError(f"Provider '{provider_id}' does not expose video generation runtime")
    try:
        raw_result = await generate_video(
            prompt=prompt,
            model=model_id,
            **build_video_generate_kwargs(engine, tool_args),
        )
    except NotImplementedError as exc:
        raise ValueError(f"Provider '{provider_id}' does not support video generation runtime") from exc
    normalized = normalize_video_service_result(engine, raw_result)
    return {
        "tool": "video_generate",
        "provider": provider_id,
        "model": model_id,
        "prompt": prompt,
        "summaryText": f"Generated video via {provider_id}/{model_id}.",
        "status": "completed",
        **normalized,
    }


async def run_video_understand_task(
    engine: Any,
    *,
    provider_id: str,
    model_id: str,
    profile_id: str,
    prompt: str,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    service = await engine._create_provider_service(provider_id=provider_id, profile_id=profile_id)
    understand_video = getattr(service, "understand_video", None)
    if understand_video is None or not callable(understand_video):
        raise ValueError(f"Provider '{provider_id}' does not expose video understanding runtime")

    source_video = engine._get_tool_arg(
        tool_args,
        "source_video",
        "sourceVideo",
        "video_url",
        "videoUrl",
        "provider_file_uri",
        "providerFileUri",
        "gcs_uri",
        "gcsUri",
    )
    normalized_source_video = source_video
    if normalized_source_video is None:
        normalized_source_video = engine._extract_first_video_url(tool_args)
    if normalized_source_video is None:
        normalized_source_video = engine._extract_first_video_url(tool_args.get("input"))
    if normalized_source_video is None:
        normalized_source_video = engine._extract_first_video_url(tool_args.get("source"))
    provider_file_uri = str(
        engine._get_tool_arg(tool_args, "provider_file_uri", "providerFileUri")
        or ""
    ).strip()
    gcs_uri = str(
        engine._get_tool_arg(tool_args, "gcs_uri", "gcsUri")
        or ""
    ).strip()
    mime_type = str(
        engine._get_tool_arg(tool_args, "mime_type", "mimeType")
        or ""
    ).strip()
    if not provider_file_uri and isinstance(tool_args.get("input"), dict):
        provider_file_uri = str(
            tool_args["input"].get("provider_file_uri")
            or tool_args["input"].get("providerFileUri")
            or ""
        ).strip()
    if not gcs_uri and isinstance(tool_args.get("input"), dict):
        gcs_uri = str(tool_args["input"].get("gcs_uri") or tool_args["input"].get("gcsUri") or "").strip()
    if not mime_type and isinstance(tool_args.get("input"), dict):
        mime_type = str(tool_args["input"].get("mime_type") or tool_args["input"].get("mimeType") or "").strip()

    if normalized_source_video is None and not provider_file_uri and not gcs_uri:
        raise ValueError("视频理解缺少 source_video / videoUrl 输入")

    source_video_payload: Any = normalized_source_video
    if provider_file_uri or gcs_uri or mime_type:
        source_video_payload = {
            **({"url": normalized_source_video} if normalized_source_video else {}),
            **({"provider_file_uri": provider_file_uri} if provider_file_uri else {}),
            **({"gcs_uri": gcs_uri} if gcs_uri else {}),
            **({"mime_type": mime_type} if mime_type else {}),
        }

    output_format = str(
        engine._get_tool_arg(tool_args, "output_format", "outputFormat") or "markdown"
    ).strip().lower() or "markdown"

    raw_result = await understand_video(
        prompt=prompt,
        model=model_id,
        source_video=source_video_payload,
        output_format=output_format,
    )
    if not isinstance(raw_result, dict):
        raw_result = {"text": str(raw_result or "")}
    return {
        "tool": "video_understand",
        "provider": provider_id,
        "model": model_id,
        "prompt": prompt,
        "summaryText": str(raw_result.get("text") or "已完成视频理解。").strip() or "已完成视频理解。",
        "status": "completed",
        **raw_result,
    }


async def run_video_delete_task(
    engine: Any,
    *,
    provider_id: str,
    profile_id: str,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    service = await engine._create_provider_service(provider_id=provider_id, profile_id=profile_id)
    delete_video = getattr(service, "delete_video", None)
    if delete_video is None or not callable(delete_video):
        raise ValueError(f"Provider '{provider_id}' does not expose video deletion runtime")

    provider_file_name = str(
        engine._get_tool_arg(tool_args, "provider_file_name", "providerFileName", "file_name", "fileName")
        or ""
    ).strip()
    provider_file_uri = str(
        engine._get_tool_arg(tool_args, "provider_file_uri", "providerFileUri")
        or ""
    ).strip()
    gcs_uri = str(
        engine._get_tool_arg(tool_args, "gcs_uri", "gcsUri")
        or ""
    ).strip()

    if not provider_file_name and not provider_file_uri and not gcs_uri:
        raise ValueError("视频删除缺少 provider_file_name / provider_file_uri / gcs_uri")

    raw_result = await delete_video(
        provider_file_name=provider_file_name or None,
        provider_file_uri=provider_file_uri or None,
        gcs_uri=gcs_uri or None,
    )
    if not isinstance(raw_result, dict):
        raw_result = {"deleted": bool(raw_result)}
    return {
        "tool": "video_delete",
        "provider": provider_id,
        "status": "completed",
        "summaryText": "视频资产已删除。",
        **raw_result,
    }


async def run_audio_generate_task(
    engine: Any,
    *,
    provider_id: str,
    model_id: str,
    profile_id: str,
    text: str,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        raise ValueError("语音生成缺少文本输入")

    voice, kwargs = build_audio_generate_kwargs(engine, tool_args)
    service = await engine._create_provider_service(provider_id=provider_id, profile_id=profile_id)
    generate_speech = getattr(service, "generate_speech", None)
    if generate_speech is None or not callable(generate_speech):
        raise ValueError(f"Provider '{provider_id}' does not expose audio generation runtime")
    try:
        raw_result = await generate_speech(
            text=normalized_text,
            voice=voice,
            model=model_id,
            **kwargs,
        )
    except NotImplementedError as exc:
        raise ValueError(f"Provider '{provider_id}' does not support audio generation runtime") from exc
    fallback_format = str(kwargs.get("response_format") or "mp3")
    normalized = normalize_audio_service_result(engine, raw_result, fallback_format=fallback_format)
    return {
        "tool": "audio_generate",
        "provider": provider_id,
        "model": model_id,
        "textInput": normalized_text,
        "voice": voice,
        "summaryText": f"Generated speech audio via {provider_id}/{model_id}.",
        "status": "completed",
        **normalized,
    }


def normalize_image_edit_mode(mode_value: Any, provider_id: str, is_outpaint: bool) -> Optional[str]:
    raw_mode = str(mode_value or "").strip()
    normalized = raw_mode.lower().replace("_", "-")

    if not normalized:
        if is_outpaint:
            return None
        if str(provider_id or "").lower().startswith("google"):
            return "image-chat-edit"
        return None

    if is_outpaint:
        if normalized in {"scale", "offset", "ratio", "upscale"}:
            return normalized

        outpaint_alias_map = {
            "image-outpainting": "scale",
            "image-outpaint": "scale",
            "outpaint": "scale",
            "outpainting": "scale",
            "expand-image": "scale",
            "expand": "scale",
            "image-expand": "scale",
        }
        return outpaint_alias_map.get(normalized, normalized)

    edit_mode_alias_map = {
        "image-chat-edit": "image-chat-edit",
        "image-chat": "image-chat-edit",
        "chat-edit": "image-chat-edit",
        "chat": "image-chat-edit",
        "image-edit": "image-chat-edit",
        "edit-image": "image-chat-edit",
        "image-mask-edit": "image-mask-edit",
        "mask-edit": "image-mask-edit",
        "mask": "image-mask-edit",
        "image-inpainting": "image-inpainting",
        "inpainting": "image-inpainting",
        "inpaint": "image-inpainting",
        "image-background-edit": "image-background-edit",
        "background-edit": "image-background-edit",
        "background": "image-background-edit",
        "image-recontext": "image-recontext",
        "recontext": "image-recontext",
        "product-recontext": "image-recontext",
    }
    return edit_mode_alias_map.get(normalized, normalized)


def normalize_mode_token_for_routing(mode_value: Any) -> str:
    return str(mode_value or "").strip().lower().replace("_", "-")


def is_outpaint_mode_token(normalized_mode: str) -> bool:
    return normalized_mode in {
        "image-outpainting",
        "image-outpaint",
        "outpaint",
        "outpainting",
        "expand-image",
        "expand",
        "image-expand",
        "scale",
        "offset",
        "ratio",
        "upscale",
    }


def resolve_image_tool_route(
    engine: Any,
    normalized_tool_name: str,
    tool_args: Dict[str, Any],
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    routed_args = dict(tool_args or {})
    explicit_mode_raw = engine._get_tool_arg(
        routed_args,
        "mode",
        "edit_mode",
        "editMode",
        "outpaint_mode",
        "outpaintMode",
    )
    explicit_mode = normalize_mode_token_for_routing(explicit_mode_raw)
    has_explicit_mode = explicit_mode_raw is not None and str(explicit_mode_raw).strip() != ""

    if explicit_mode:
        if is_outpaint_mode_token(explicit_mode):
            return True, "image-outpainting", routed_args
        return False, explicit_mode, routed_args

    if normalized_tool_name in ("image_outpaint", "image_outpainting", "expand_image"):
        if not has_explicit_mode:
            routed_args["mode"] = "image-outpainting"
        return True, "image-outpainting", routed_args

    image_edit_tool_mode_map = {
        "image_chat_edit": "image-chat-edit",
        "image_mask_edit": "image-mask-edit",
        "image_inpainting": "image-inpainting",
        "image_background_edit": "image-background-edit",
        "image_recontext": "image-recontext",
    }
    if normalized_tool_name in image_edit_tool_mode_map:
        preferred_mode = image_edit_tool_mode_map[normalized_tool_name]
        if not has_explicit_mode:
            routed_args["mode"] = preferred_mode
        return False, preferred_mode, routed_args

    if normalized_tool_name in ("image_edit", "edit_image"):
        return False, "image-chat-edit", routed_args

    return False, None, routed_args


def normalize_image_service_results(engine: Any, raw_result: Any) -> Dict[str, Any]:
    if isinstance(raw_result, list):
        source_items = raw_result
    elif isinstance(raw_result, dict) and isinstance(raw_result.get("images"), list):
        source_items = raw_result.get("images") or []
    elif raw_result is None:
        source_items = []
    else:
        source_items = [raw_result]

    images: List[Dict[str, Any]] = []
    for index, item in enumerate(source_items):
        image_url = engine._extract_first_image_url(item)
        if not image_url:
            continue

        image_payload: Dict[str, Any] = {"url": image_url, "index": index}
        if isinstance(item, dict):
            mime_type = item.get("mime_type") or item.get("mimeType")
            if isinstance(mime_type, str) and mime_type.strip():
                image_payload["mimeType"] = mime_type.strip()
            enhanced_prompt = item.get("enhanced_prompt") or item.get("enhancedPrompt")
            if isinstance(enhanced_prompt, str) and enhanced_prompt.strip():
                image_payload["enhancedPrompt"] = enhanced_prompt.strip()
            task_id = item.get("task_id") or item.get("taskId")
            if isinstance(task_id, str) and task_id.strip():
                image_payload["taskId"] = task_id.strip()

            passthrough_fields = {
                "attachment_id": "attachmentId",
                "attachmentId": "attachmentId",
                "upload_status": "uploadStatus",
                "uploadStatus": "uploadStatus",
                "cloud_url": "cloudUrl",
                "cloudUrl": "cloudUrl",
                "filename": "filename",
                "fileName": "filename",
                "session_id": "sessionId",
                "sessionId": "sessionId",
                "message_id": "messageId",
                "messageId": "messageId",
                "thoughts": "thoughts",
                "reasoning": "reasoning",
                "thinking": "thinking",
                "thought_summary": "thoughtSummary",
                "thoughtSummary": "thoughtSummary",
                "text_response": "textResponse",
                "textResponse": "textResponse",
                "text": "text",
            }
            for src_key, dst_key in passthrough_fields.items():
                value = item.get(src_key)
                if value is None:
                    continue
                if isinstance(value, str):
                    stripped = value.strip()
                    if not stripped:
                        continue
                    image_payload[dst_key] = stripped
                    continue
                try:
                    json.dumps(value, ensure_ascii=False)
                    image_payload[dst_key] = value
                except Exception:
                    image_payload[dst_key] = str(value)
        images.append(image_payload)

    image_urls = [item["url"] for item in images]
    return {
        "images": images,
        "imageUrls": image_urls,
        "imageUrl": image_urls[0] if image_urls else None,
        "count": len(images),
    }


def trim_normalized_images(normalized: Dict[str, Any], keep_last: int = 1) -> Dict[str, Any]:
    images = normalized.get("images") if isinstance(normalized, dict) else None
    if not isinstance(images, list) or keep_last <= 0:
        return normalized
    if len(images) <= keep_last:
        return normalized
    kept = images[-keep_last:]
    kept_urls = [
        str(item.get("url") or "").strip()
        for item in kept
        if isinstance(item, dict) and str(item.get("url") or "").strip()
    ]
    updated = dict(normalized)
    updated["images"] = kept
    updated["imageUrls"] = kept_urls
    updated["imageUrl"] = kept_urls[0] if kept_urls else None
    updated["count"] = len(kept)
    return updated
