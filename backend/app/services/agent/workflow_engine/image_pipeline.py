"""
Image generation, editing, and vision helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def normalize_resolution_tier(engine: Any, value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None

    normalized = raw.lower().replace(" ", "").replace("*", "x")
    normalized = normalized.replace("×", "x")

    mapping = {
        "1k": "1K",
        "1.0k": "1K",
        "1024": "1K",
        "1024x1024": "1K",
        "1.25k": "1.25K",
        "1280": "1.25K",
        "1280x1280": "1.25K",
        "1.5k": "1.5K",
        "1536": "1.5K",
        "1536x1536": "1.5K",
        "2k": "2K",
        "2.0k": "2K",
        "2048": "2K",
        "2048x2048": "2K",
        "4k": "4K",
        "4.0k": "4K",
        "4096": "4K",
        "4096x4096": "4K",
        "512": "1K",
        "512x512": "1K",
    }
    return mapping.get(normalized, raw if raw in {"1K", "1.25K", "1.5K", "2K", "4K"} else None)


def resolve_google_image_size(engine: Any, value: Any) -> Optional[str]:
    """
    Google Imagen currently accepts image_size in {"1K", "2K"}.
    Normalize workflow resolution tokens into the supported range.
    """
    tier = engine._normalize_resolution_tier(value)
    if not tier:
        return None
    if tier in {"1K", "1.25K"}:
        return "1K"
    if tier in {"1.5K", "2K", "4K"}:
        return "2K"
    return None


def resolve_tongyi_resolution(engine: Any, value: Any) -> Optional[str]:
    """
    Tongyi image generation expects resolution tier values such as:
    1K / 1.25K / 1.5K / 2K.
    """
    tier = engine._normalize_resolution_tier(value)
    if not tier:
        return None
    if tier == "4K":
        return "2K"
    if tier in {"1K", "1.25K", "1.5K", "2K"}:
        return tier
    return None


def resolve_generic_image_size(engine: Any, value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None

    normalized = raw.lower().replace(" ", "").replace("*", "x").replace("×", "x")
    if re.fullmatch(r"\d{3,5}x\d{3,5}", normalized):
        return normalized

    tier = engine._normalize_resolution_tier(raw)
    if not tier:
        return None
    if tier in {"1K", "1.25K"}:
        return "1024x1024"
    if tier == "1.5K":
        return "1536x1536"
    if tier in {"2K", "4K"}:
        return "1792x1024"
    return None


def build_generate_kwargs(engine: Any, provider_id: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    lowered = (provider_id or "").lower()
    kwargs: Dict[str, Any] = {}

    if lowered.startswith("google"):
        number_of_images = engine._get_tool_arg(tool_args, "number_of_images", "numberOfImages", "n", "num_images")
        aspect_ratio = engine._get_tool_arg(tool_args, "aspect_ratio", "aspectRatio")
        image_size_raw = engine._get_tool_arg(
            tool_args,
            "image_size",
            "imageSize",
            "resolution",
            "resolution_tier",
            "resolutionTier",
        )
        image_style = engine._get_tool_arg(tool_args, "image_style", "imageStyle", "style")
        output_mime_type = engine._get_tool_arg(tool_args, "output_mime_type", "outputMimeType", "mimeType")
        output_compression_quality = engine._get_tool_arg(tool_args, "output_compression_quality", "outputCompressionQuality")
        prompt_extend = engine._get_tool_arg(
            tool_args,
            "prompt_extend",
            "promptExtend",
            "enable_prompt_optimize",
            "enhance_prompt",
        )

        if number_of_images is not None:
            parsed = engine._to_int(number_of_images, minimum=1, maximum=8)
            if parsed is not None:
                kwargs["number_of_images"] = parsed
        if aspect_ratio is not None:
            kwargs["aspect_ratio"] = str(aspect_ratio)
        normalized_google_size = engine._resolve_google_image_size(image_size_raw)
        if normalized_google_size is not None:
            kwargs["image_size"] = normalized_google_size
        if image_style is not None:
            kwargs["image_style"] = str(image_style)
        if output_mime_type is not None:
            kwargs["output_mime_type"] = str(output_mime_type)
        if output_compression_quality is not None:
            parsed = engine._to_int(output_compression_quality, minimum=1, maximum=100)
            if parsed is not None:
                kwargs["output_compression_quality"] = parsed
        if prompt_extend is not None:
            kwargs["enhance_prompt"] = engine._to_bool(prompt_extend)
        return kwargs

    if lowered.startswith("tongyi") or lowered.startswith("dashscope"):
        num_images = engine._get_tool_arg(tool_args, "num_images", "numberOfImages", "number_of_images", "n")
        aspect_ratio = engine._get_tool_arg(tool_args, "aspect_ratio", "aspectRatio")
        resolution_raw = engine._get_tool_arg(
            tool_args,
            "resolution",
            "resolution_tier",
            "resolutionTier",
            "imageResolution",
            "size",
            "image_size",
            "imageSize",
        )
        style = engine._get_tool_arg(tool_args, "style", "imageStyle")
        negative_prompt = engine._get_tool_arg(tool_args, "negative_prompt", "negativePrompt")
        seed = engine._get_tool_arg(tool_args, "seed")
        prompt_extend = engine._get_tool_arg(tool_args, "prompt_extend", "promptExtend", "enable_prompt_optimize")
        add_magic_suffix = engine._get_tool_arg(tool_args, "add_magic_suffix", "addMagicSuffix")

        if num_images is not None:
            parsed = engine._to_int(num_images, minimum=1, maximum=4)
            if parsed is not None:
                kwargs["num_images"] = parsed
        if aspect_ratio is not None:
            kwargs["aspect_ratio"] = str(aspect_ratio)
        normalized_tongyi_resolution = engine._resolve_tongyi_resolution(resolution_raw)
        if normalized_tongyi_resolution is not None:
            kwargs["resolution"] = normalized_tongyi_resolution
        if style is not None:
            kwargs["style"] = str(style)
        if negative_prompt is not None:
            kwargs["negative_prompt"] = str(negative_prompt)
        if seed is not None:
            parsed = engine._to_int(seed)
            if parsed is not None:
                kwargs["seed"] = parsed
        if prompt_extend is not None:
            kwargs["promptExtend"] = engine._to_bool(prompt_extend)
        if add_magic_suffix is not None:
            kwargs["addMagicSuffix"] = engine._to_bool(add_magic_suffix, default=True)
        return kwargs

    size_raw = engine._get_tool_arg(tool_args, "size", "resolution", "image_size", "imageSize")
    quality = engine._get_tool_arg(tool_args, "quality")
    style = engine._get_tool_arg(tool_args, "style", "imageStyle")
    n = engine._get_tool_arg(tool_args, "n", "number_of_images", "numberOfImages")
    response_format = engine._get_tool_arg(tool_args, "response_format", "responseFormat")

    resolved_size = engine._resolve_generic_image_size(size_raw)
    if resolved_size is not None:
        kwargs["size"] = resolved_size
    if quality is not None:
        kwargs["quality"] = str(quality)
    if style is not None:
        kwargs["style"] = str(style)
    if n is not None:
        parsed = engine._to_int(n, minimum=1, maximum=10)
        if parsed is not None:
            kwargs["n"] = parsed
    if response_format is not None:
        kwargs["response_format"] = str(response_format)
    return kwargs


def resolve_video_resolution(engine: Any, value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None

    normalized = raw.lower().replace(" ", "").replace("*", "x").replace("×", "x")
    mapping = {
        "1k": "720p",
        "720p": "720p",
        "1280": "720p",
        "1280x720": "720p",
        "720x1280": "720p",
        "2k": "1080p",
        "1080p": "1080p",
        "1920": "1080p",
        "1920x1080": "1080p",
        "1080x1920": "1080p",
        "4k": "4k",
        "2160p": "4k",
        "3840x2160": "4k",
        "2160x3840": "4k",
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized in {"720p", "1080p", "4k"}:
        return normalized
    return None


def guess_audio_mime_type(engine: Any, audio_format: str) -> str:
    normalized_format = str(audio_format or "").strip().lower()
    mime_map = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "pcm": "audio/pcm",
    }
    return mime_map.get(normalized_format, "audio/mpeg")


def build_image_edit_kwargs(
    engine: Any,
    provider_id: str,
    tool_args: Dict[str, Any],
    is_outpaint: bool,
    preferred_mode: Optional[str] = None,
) -> Dict[str, Any]:
    lowered = (provider_id or "").lower()
    kwargs: Dict[str, Any] = {}
    raw_mode = engine._get_tool_arg(tool_args, "mode", "edit_mode", "editMode", "outpaint_mode", "outpaintMode")
    mode = engine._normalize_image_edit_mode(
        mode_value=raw_mode if raw_mode is not None else preferred_mode,
        provider_id=provider_id,
        is_outpaint=is_outpaint,
    )

    if lowered.startswith("google"):
        number_of_images = engine._get_tool_arg(tool_args, "number_of_images", "numberOfImages", "n", "num_images")
        aspect_ratio = engine._get_tool_arg(tool_args, "aspect_ratio", "aspectRatio")
        image_size = engine._get_tool_arg(tool_args, "image_size", "imageSize", "resolution")
        prompt_extend = engine._get_tool_arg(
            tool_args,
            "prompt_extend",
            "promptExtend",
            "enable_prompt_optimize",
            "enhance_prompt",
        )
        enhance_prompt_model = engine._get_tool_arg(
            tool_args,
            "enhance_prompt_model",
            "enhancePromptModel",
        )
        frontend_session_id = engine._get_tool_arg(
            tool_args,
            "frontend_session_id",
            "frontendSessionId",
            "session_id",
            "sessionId",
        )
        message_id = engine._get_tool_arg(
            tool_args,
            "message_id",
            "messageId",
        )

        if str(mode or "").strip().lower() == "image-chat-edit" and not frontend_session_id:
            frontend_session_id = engine._generate_workflow_frontend_session_id()

        if mode is not None:
            kwargs["mode"] = str(mode)
        if number_of_images is not None:
            parsed = engine._to_int(number_of_images, minimum=1, maximum=8)
            if parsed is not None:
                kwargs["number_of_images"] = parsed
        if aspect_ratio is not None:
            kwargs["aspect_ratio"] = str(aspect_ratio)
        if image_size is not None:
            resolved_size = engine._resolve_google_image_size(image_size)
            kwargs["image_size"] = resolved_size if resolved_size else str(image_size)
        if prompt_extend is not None:
            kwargs["enhance_prompt"] = engine._to_bool(prompt_extend)
        if enhance_prompt_model is not None:
            kwargs["enhance_prompt_model"] = str(enhance_prompt_model)
        if frontend_session_id is not None:
            kwargs["frontend_session_id"] = str(frontend_session_id)
        if message_id is not None:
            kwargs["message_id"] = str(message_id)

        if is_outpaint:
            for arg_key in ("x_scale", "y_scale", "left_offset", "right_offset", "top_offset", "bottom_offset", "angle"):
                value = engine._get_tool_arg(tool_args, arg_key)
                if value is not None:
                    parsed = engine._to_float(value)
                    if parsed is not None:
                        kwargs[arg_key] = parsed
            output_ratio = engine._get_tool_arg(tool_args, "output_ratio", "outputRatio")
            if output_ratio is not None:
                kwargs["output_ratio"] = str(output_ratio)
        return kwargs

    if lowered.startswith("tongyi") or lowered.startswith("dashscope"):
        number_of_images = engine._get_tool_arg(tool_args, "number_of_images", "numberOfImages", "n", "num_images")
        negative_prompt = engine._get_tool_arg(tool_args, "negative_prompt", "negativePrompt")
        seed = engine._get_tool_arg(tool_args, "seed")
        prompt_extend = engine._get_tool_arg(tool_args, "prompt_extend", "promptExtend", "enable_prompt_optimize")

        if mode is not None:
            kwargs["mode"] = str(mode)
        if number_of_images is not None:
            parsed = engine._to_int(number_of_images, minimum=1, maximum=4)
            if parsed is not None:
                kwargs["number_of_images"] = parsed
        if negative_prompt is not None:
            kwargs["negative_prompt"] = str(negative_prompt)
        if seed is not None:
            parsed = engine._to_int(seed)
            if parsed is not None:
                kwargs["seed"] = parsed
        if prompt_extend is not None:
            kwargs["promptExtend"] = engine._to_bool(prompt_extend)
        return kwargs

    if mode is not None:
        kwargs["mode"] = str(mode)
    return kwargs


async def run_image_generate_tool(engine: Any, tool_args: Dict[str, Any], latest_input: Any) -> Dict[str, Any]:
    prompt = (
        engine._get_tool_arg(tool_args, "prompt", "text")
        or engine._extract_text_from_value(latest_input)
        or "生成一张图片"
    )
    requested_provider = engine._get_tool_arg(tool_args, "provider_id", "providerId", "provider")
    requested_model = str(engine._get_tool_arg(tool_args, "model_id", "modelId", "model") or "").strip()
    requested_profile_id = str(
        engine._get_tool_arg(tool_args, "profile_id", "profileId", "provider_profile_id", "providerProfileId")
        or ""
    ).strip()
    if requested_profile_id:
        ranked_profiles = engine._rank_provider_profiles_for_tool(
            str(requested_provider or ""),
            operation="generate",
            requested_profile_id=requested_profile_id,
        )
    else:
        ranked_profiles = engine._rank_provider_profiles_for_tool(
            str(requested_provider or ""),
            operation="generate",
        )

    attempt_errors: List[str] = []
    for attempt_index, profile in enumerate(ranked_profiles):
        provider_id = str(getattr(profile, "provider_id", "")).strip()
        candidate_models = engine._list_candidate_image_models(
            profile=profile,
            operation="generate",
            requested_model=requested_model if attempt_index == 0 else "",
        )
        if not candidate_models:
            attempt_errors.append(f"{provider_id}: 未找到可用图像生成模型")
            continue
        service = await engine._create_provider_service(
            provider_id=provider_id,
            profile_id=str(getattr(profile, "id", "") or ""),
        )
        kwargs = engine._build_generate_kwargs(provider_id=provider_id, tool_args=tool_args)

        for model_id in candidate_models[:4]:
            try:
                raw_result = await service.generate_image(
                    prompt=prompt,
                    model=model_id,
                    **kwargs,
                )
                normalized = engine._normalize_image_service_results(raw_result)
                if not normalized.get("imageUrl"):
                    raise ValueError("图像生成成功但未返回可展示的图片 URL")
                return {
                    "tool": "image_generate",
                    "provider": provider_id,
                    "model": model_id,
                    "prompt": prompt,
                    "summaryText": f"Generated {normalized.get('count', 0)} image(s) via {provider_id}/{model_id}.",
                    "status": "completed",
                    **normalized,
                }
            except NotImplementedError:
                attempt_errors.append(f"{provider_id}/{model_id}: Provider 暂不支持图像生成")
            except Exception as exc:
                attempt_errors.append(f"{provider_id}/{model_id}: {str(exc) or type(exc).__name__}")

    error_preview = "；".join(attempt_errors[:3]) if attempt_errors else "未获取到可用 Provider"
    raise ValueError(f"图像生成失败，已尝试 {len(ranked_profiles)} 个 Provider：{error_preview}")


async def run_image_edit_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
    is_outpaint: bool = False,
    preferred_mode: Optional[str] = None,
) -> Dict[str, Any]:
    source_image_url = (
        engine._get_tool_arg(tool_args, "image_url", "imageUrl", "source_image_url", "sourceImageUrl", "url")
        or engine._extract_first_image_url(latest_input)
    )
    if not source_image_url:
        raise ValueError("图片编辑工具缺少输入图片，请在参数中提供 imageUrl")

    base_edit_prompt = (
        engine._get_tool_arg(tool_args, "edit_prompt", "editPrompt", "prompt", "text")
        or engine._extract_text_from_value(latest_input)
        or ("扩展图片边界" if is_outpaint else "优化图片细节")
    )
    requested_provider = engine._get_tool_arg(tool_args, "provider_id", "providerId", "provider")
    operation = "outpaint" if is_outpaint else "edit"
    requested_model = str(engine._get_tool_arg(tool_args, "model_id", "modelId", "model") or "").strip()
    requested_profile_id = str(
        engine._get_tool_arg(tool_args, "profile_id", "profileId", "provider_profile_id", "providerProfileId")
        or ""
    ).strip()
    parsed_max_retries = engine._to_int(
        engine._get_tool_arg(tool_args, "max_retries", "maxRetries"),
        default=0,
        minimum=0,
        maximum=3,
    )
    max_retries = 0 if parsed_max_retries is None else parsed_max_retries
    per_attempt_timeout_seconds = engine._to_int(
        engine._get_tool_arg(
            tool_args,
            "single_attempt_timeout_seconds",
            "singleAttemptTimeoutSeconds",
            "request_timeout_seconds",
            "requestTimeoutSeconds",
        ),
        default=180,
        minimum=30,
        maximum=900,
    ) or 180
    validation_timeout_seconds = engine._to_int(
        engine._get_tool_arg(
            tool_args,
            "validation_timeout_seconds",
            "validationTimeoutSeconds",
        ),
        default=60,
        minimum=10,
        maximum=300,
    ) or 60
    max_models_per_provider = engine._to_int(
        engine._get_tool_arg(
            tool_args,
            "max_models_per_provider",
            "maxModelsPerProvider",
        ),
        default=2,
        minimum=1,
        maximum=4,
    ) or 2
    preserve_product_identity = engine._to_bool(
        engine._get_tool_arg(tool_args, "preserve_product_identity", "preserveProductIdentity"),
        default=True,
    )
    output_language = str(
        engine._get_tool_arg(tool_args, "output_language", "outputLanguage") or "en"
    ).strip().lower()
    product_match_threshold = engine._to_int(
        engine._get_tool_arg(tool_args, "product_match_threshold", "productMatchThreshold"),
        default=70,
        minimum=50,
        maximum=95,
    ) or 70

    if requested_profile_id:
        ranked_profiles = engine._rank_provider_profiles_for_tool(
            str(requested_provider or ""),
            operation=operation,
            requested_profile_id=requested_profile_id,
        )
    else:
        ranked_profiles = engine._rank_provider_profiles_for_tool(
            str(requested_provider or ""),
            operation=operation,
        )

    attempt_errors: List[str] = []
    for attempt_index, profile in enumerate(ranked_profiles):
        provider_id = str(getattr(profile, "provider_id", "")).strip()
        raw_mode_value = engine._get_tool_arg(
            tool_args,
            "mode",
            "edit_mode",
            "editMode",
            "outpaint_mode",
            "outpaintMode",
        )
        effective_mode = engine._normalize_image_edit_mode(
            mode_value=raw_mode_value if raw_mode_value is not None else preferred_mode,
            provider_id=provider_id,
            is_outpaint=is_outpaint,
        )
        candidate_models = engine._list_candidate_image_models(
            profile=profile,
            operation=operation,
            requested_model=requested_model if attempt_index == 0 else "",
            preferred_mode=effective_mode or "",
        )
        if not candidate_models:
            attempt_errors.append(f"{provider_id}: 未找到可用图像编辑模型")
            continue

        service = await engine._create_provider_service(
            provider_id=provider_id,
            profile_id=str(getattr(profile, "id", "") or ""),
        )
        provider_source_image = engine._normalize_reference_image_for_provider(
            source_image_url=source_image_url,
            provider_id=provider_id,
        )
        reference_images: Dict[str, Any] = {"raw": provider_source_image}
        mask_url = engine._get_tool_arg(tool_args, "mask_url", "maskUrl")
        if mask_url:
            reference_images["mask"] = mask_url
        kwargs = engine._build_image_edit_kwargs(
            provider_id=provider_id,
            tool_args=tool_args,
            is_outpaint=is_outpaint,
            preferred_mode=effective_mode,
        )

        for model_id in candidate_models[:max_models_per_provider]:
            feedback_hint = ""
            last_validation: Dict[str, Any] = {}
            prompt_for_try = engine._build_guarded_edit_prompt(
                base_prompt=base_edit_prompt,
                preserve_product_identity=preserve_product_identity,
                output_language=output_language,
                feedback_hint=feedback_hint,
            )
            for retry_idx in range(max_retries + 1):
                try:
                    if is_outpaint:
                        raw_result = await asyncio.wait_for(
                            service.expand_image(
                                prompt=prompt_for_try,
                                model=model_id,
                                reference_images=reference_images,
                                **kwargs,
                            ),
                            timeout=per_attempt_timeout_seconds,
                        )
                    else:
                        raw_result = await asyncio.wait_for(
                            service.edit_image(
                                prompt=prompt_for_try,
                                model=model_id,
                                reference_images=reference_images,
                                **kwargs,
                            ),
                            timeout=per_attempt_timeout_seconds,
                        )
                    normalized = engine._normalize_image_service_results(raw_result)
                    requested_images = engine._to_int(
                        engine._get_tool_arg(tool_args, "number_of_images", "numberOfImages", "n", "num_images"),
                        default=1,
                        minimum=1,
                        maximum=8,
                    ) or 1
                    normalized = engine._trim_normalized_images(normalized, keep_last=requested_images)
                    if not normalized.get("imageUrl"):
                        raise ValueError("图片编辑执行完成，但未返回可展示的图片 URL")

                    validation = await asyncio.wait_for(
                        engine._validate_image_edit_result(
                            source_image_url=source_image_url,
                            result_image_url=str(normalized.get("imageUrl") or "").strip(),
                            provider_id=provider_id,
                            profile=profile,
                            preserve_product_identity=preserve_product_identity,
                            product_match_threshold=product_match_threshold,
                        ),
                        timeout=validation_timeout_seconds,
                    )
                    last_validation = validation
                    if validation.get("passed", True):
                        result = {
                            "tool": "image_outpaint" if is_outpaint else "image_edit",
                            "provider": provider_id,
                            "model": model_id,
                            "sourceImageUrl": source_image_url,
                            "editPrompt": prompt_for_try,
                            "summaryText": (
                                f"Edited image via {provider_id}/{model_id}"
                                f" (attempt {retry_idx + 1}/{max_retries + 1})."
                            ),
                            "status": "completed",
                            "validation": validation,
                            "attempt": retry_idx + 1,
                            "maxAttempts": max_retries + 1,
                            **normalized,
                        }
                        if kwargs.get("mode"):
                            result["mode"] = kwargs.get("mode")
                        return result

                    validation_reason = "; ".join(validation.get("issues", [])[:2]) or "quality gate failed"
                    attempt_errors.append(
                        f"{provider_id}/{model_id}#try{retry_idx + 1}: validation_failed({validation_reason})"
                    )
                    feedback_hint = validation.get("suggestion", "") or validation_reason
                    prompt_for_try = engine._build_guarded_edit_prompt(
                        base_prompt=base_edit_prompt,
                        preserve_product_identity=preserve_product_identity,
                        output_language=output_language,
                        feedback_hint=feedback_hint,
                    )
                except NotImplementedError:
                    action = "扩图" if is_outpaint else "图片编辑"
                    attempt_errors.append(f"{provider_id}/{model_id}: Provider 暂不支持{action}")
                    break
                except asyncio.TimeoutError:
                    attempt_errors.append(
                        f"{provider_id}/{model_id}#try{retry_idx + 1}: timeout({per_attempt_timeout_seconds}s)"
                    )
                    if retry_idx >= max_retries:
                        break
                except Exception as exc:
                    attempt_errors.append(
                        f"{provider_id}/{model_id}#try{retry_idx + 1}: {str(exc) or type(exc).__name__}"
                    )
                    if retry_idx >= max_retries:
                        break
                    feedback_hint = (
                        last_validation.get("suggestion", "")
                        if isinstance(last_validation, dict)
                        else ""
                    )
                    prompt_for_try = engine._build_guarded_edit_prompt(
                        base_prompt=base_edit_prompt,
                        preserve_product_identity=preserve_product_identity,
                        output_language=output_language,
                        feedback_hint=feedback_hint,
                    )

    action_label = "扩图" if is_outpaint else "图片编辑"
    error_preview = "；".join(attempt_errors[:3]) if attempt_errors else "未获取到可用 Provider"
    raise ValueError(f"{action_label}失败，已尝试 {len(ranked_profiles)} 个 Provider：{error_preview}")


def sanitize_vision_text_prompt(engine: Any, text: str) -> str:
    raw = str(text or "")
    if not raw.strip():
        return ""

    sanitized = re.sub(
        r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\n\r]+",
        "[ATTACHED_IMAGE_DATA]",
        raw,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(https?://\S+|file://\S+)",
        "[IMAGE_REFERENCE_URL]",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"([A-Za-z]:\\[^\s]+?\.(?:png|jpg|jpeg|webp|gif|bmp|svg))",
        "[IMAGE_REFERENCE_PATH]",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(/[^\s]+?\.(?:png|jpg|jpeg|webp|gif|bmp|svg))",
        "[IMAGE_REFERENCE_PATH]",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized.strip()


def build_vision_understand_prompt(engine: Any, base_prompt: str) -> str:
    task_prompt = engine._sanitize_vision_text_prompt(str(base_prompt or "").strip())
    analysis_contract = (
        "You are a multimodal ecommerce image analyst.\n"
        "Analyze ONLY the attached image pixels.\n"
        "Do not infer object/category from filename, URL text, or prior assumptions.\n"
        "If a detail is uncertain, use \"unknown\" with low confidence.\n"
        "Return STRICT JSON only with keys:\n"
        "{\n"
        "  \"primaryObject\": string,\n"
        "  \"category\": string,\n"
        "  \"colors\": [string],\n"
        "  \"materials\": [string],\n"
        "  \"visualEvidence\": [string],\n"
        "  \"keepElements\": [string],\n"
        "  \"avoidElements\": [string],\n"
        "  \"confidence\": number\n"
        "}"
    )
    if task_prompt:
        return f"{task_prompt}\n\n{analysis_contract}"
    return analysis_contract


def build_vision_understand_summary(engine: Any, analysis: Dict[str, Any], fallback_text: str = "") -> str:
    primary_object = str(
        analysis.get("primaryObject")
        or analysis.get("primary_object")
        or analysis.get("category")
        or ""
    ).strip()
    colors = analysis.get("colors")
    top_color = ""
    if isinstance(colors, list):
        for item in colors:
            color_text = str(item or "").strip()
            if color_text:
                top_color = color_text
                break
    confidence = analysis.get("confidence")
    confidence_text = ""
    if confidence is not None and str(confidence).strip():
        confidence_text = str(confidence).strip()

    summary_parts: List[str] = []
    if primary_object:
        summary_parts.append(f"识别主体：{primary_object}")
    if top_color:
        summary_parts.append(f"主色：{top_color}")
    if confidence_text:
        summary_parts.append(f"置信度：{confidence_text}")
    if summary_parts:
        return "；".join(summary_parts)

    cleaned_fallback = engine._strip_markdown_code_fence(str(fallback_text or "").strip())
    if cleaned_fallback:
        return cleaned_fallback[:240]
    return "已完成图片理解。"


async def run_vision_understand_task(
    engine: Any,
    *,
    provider_id: str,
    model_id: str,
    system_prompt: str,
    prompt: str,
    source_image_url: str,
    temperature: float,
    max_tokens: int,
    profile_id: str = "",
) -> Dict[str, Any]:
    normalized_source = engine._normalize_reference_image_for_provider(
        source_image_url=source_image_url,
        provider_id=provider_id,
    )
    if not normalized_source:
        raise ValueError("图片理解任务缺少有效参考图")

    final_prompt = engine._build_vision_understand_prompt(prompt)
    if str(system_prompt or "").strip():
        final_prompt = (
            f"[System Instructions]\n{str(system_prompt).strip()}\n[End System Instructions]\n\n"
            f"{final_prompt}"
        )

    attachments = [{
        "mimeType": engine._guess_image_mime_type_from_reference(normalized_source),
        "url": normalized_source,
    }]

    chat_kwargs: Dict[str, Any] = {
        "temperature": temperature,
    }
    if str(provider_id or "").lower().startswith("google"):
        chat_kwargs["max_output_tokens"] = max_tokens
    else:
        chat_kwargs["max_tokens"] = max_tokens

    service = await engine._create_provider_service(
        provider_id=provider_id,
        profile_id=profile_id,
    )
    response = await service.chat(
        messages=[{
            "role": "user",
            "content": final_prompt,
            "attachments": attachments,
        }],
        model=model_id,
        **chat_kwargs,
    )

    raw_text = str(response.get("content") or response.get("text") or "").strip()
    analysis = engine._extract_json_object_from_text(raw_text)
    summary_text = engine._build_vision_understand_summary(analysis, fallback_text=raw_text)

    return {
        "text": summary_text,
        "analysis": analysis,
        "rawText": raw_text,
        "referenceImageUrl": source_image_url,
        "usage": response.get("usage", {}) if isinstance(response, dict) else {},
    }


def build_guarded_edit_prompt(
    engine: Any,
    base_prompt: str,
    preserve_product_identity: bool,
    output_language: str = "en",
    feedback_hint: str = "",
) -> str:
    prompt = str(base_prompt or "").strip()
    if not prompt:
        prompt = "Enhance the image for ecommerce use."

    constraints: List[str] = []
    if preserve_product_identity:
        constraints.append(
            "Keep EXACT same product identity: product category/type, colorway, material, shape, silhouette, "
            "structure, and visible logo/pattern. Never morph product into a different object."
        )
    if output_language.startswith("en"):
        constraints.append("All on-image copy must be ENGLISH only.")
    constraints.append(
        "Do not place text over model face/body or the core product area. Keep text in top margin and safe corners."
    )

    if feedback_hint:
        constraints.append(f"Retry fix focus: {str(feedback_hint).strip()}")

    guard_block = "\n".join(f"- {line}" for line in constraints if line)
    return (
        f"{prompt}\n\n"
        "Mandatory constraints:\n"
        f"{guard_block}"
    ).strip()


def extract_json_object_from_text(engine: Any, text: str) -> Dict[str, Any]:
    raw = engine._strip_markdown_code_fence(str(text or "").strip())
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        snippet = raw[start:end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def select_google_vision_eval_model(engine: Any, profile: Any) -> str:
    saved_models = engine._list_saved_model_ids(profile)

    def looks_like_vision_chat(model_id: str) -> bool:
        lowered = str(model_id or "").lower()
        if not lowered:
            return False
        if "imagen" in lowered:
            return False
        if "gemini" in lowered and any(token in lowered for token in ("flash", "pro", "image")):
            return True
        return any(token in lowered for token in ("nano-banana", "flash-image"))

    candidates = [model_id for model_id in saved_models if looks_like_vision_chat(model_id)]

    def rank(model_id: str) -> int:
        lowered = str(model_id or "").lower()
        score = 0
        if "2.5" in lowered:
            score -= 30
        if "pro" in lowered:
            score -= 10
        if "flash" in lowered:
            score -= 8
        if "image" in lowered:
            score -= 3
        if any(flag in lowered for flag in ("preview", "-exp", "_exp", "experimental")):
            score += 15
        return score

    if candidates:
        return sorted(candidates, key=rank)[0]

    return "gemini-2.5-flash"


async def validate_image_edit_result(
    engine: Any,
    source_image_url: str,
    result_image_url: str,
    provider_id: str,
    profile: Any,
    preserve_product_identity: bool,
    product_match_threshold: int,
) -> Dict[str, Any]:
    if not preserve_product_identity:
        return {"checked": False, "passed": True, "issues": []}
    if not source_image_url or not result_image_url:
        return {"checked": False, "passed": True, "issues": []}

    lowered_provider = str(provider_id or "").lower()
    if not lowered_provider.startswith("google"):
        return {
            "checked": False,
            "passed": True,
            "issues": [],
            "reason": "vision_check_not_supported_for_provider",
        }

    eval_model = engine._select_google_vision_eval_model(profile)
    source_payload = engine._normalize_reference_image_for_provider(source_image_url, "google")
    result_payload = engine._normalize_reference_image_for_provider(result_image_url, "google")

    attachments = [
        {"mimeType": "image/png", "url": source_payload},
        {"mimeType": "image/png", "url": result_payload},
    ]

    eval_prompt = (
        "You are an ecommerce creative QA judge.\n"
        "Attachment #1 is the SOURCE product image.\n"
        "Attachment #2 is the EDITED output image.\n"
        "Evaluate product identity consistency and output STRICT JSON only:\n"
        "{\n"
        '  "product_match": true|false,\n'
        '  "product_score": 0-100,\n'
        '  "overlap_risk": "low|medium|high",\n'
        '  "issues": ["..."],\n'
        '  "suggestion": "..."\n'
        "}\n"
        "Rules:\n"
        "- Fail if edited image turns product into a different object category/type.\n"
        "- Fail if color/material/shape/silhouette changes significantly.\n"
        "- Evaluate overlap risk for text covering model face/body or product core area."
    )

    try:
        service = await engine._create_provider_service(
            "google",
            profile_id=str(getattr(profile, "id", "") or ""),
        )
        response = await service.chat(
            messages=[{
                "role": "user",
                "content": eval_prompt,
                "attachments": attachments,
            }],
            model=eval_model,
            temperature=0.1,
            max_tokens=300,
        )
        raw_text = str(response.get("content") or response.get("text") or "").strip()
        parsed = engine._extract_json_object_from_text(raw_text)
        if not parsed:
            return {
                "checked": False,
                "passed": True,
                "issues": [],
                "reason": "vision_parse_failed",
            }
        if "product_match" not in parsed and "product_score" not in parsed:
            return {
                "checked": False,
                "passed": True,
                "issues": [],
                "reason": "vision_parse_incomplete",
            }
        score = engine._to_int(parsed.get("product_score"), default=0, minimum=0, maximum=100) or 0
        match_flag = bool(parsed.get("product_match"))
        passed = bool(match_flag and score >= product_match_threshold)
        overlap_risk = str(parsed.get("overlap_risk") or "").strip().lower()
        issues = parsed.get("issues")
        issue_list = issues if isinstance(issues, list) else []
        issue_list = [str(item).strip() for item in issue_list if str(item).strip()]

        result: Dict[str, Any] = {
            "checked": True,
            "passed": passed,
            "productScore": score,
            "productMatch": match_flag,
            "threshold": product_match_threshold,
            "overlapRisk": overlap_risk or "unknown",
            "issues": issue_list,
            "suggestion": str(parsed.get("suggestion") or "").strip(),
        }
        if not result["suggestion"] and issue_list:
            result["suggestion"] = issue_list[0]
        return result
    except Exception as exc:
        logger.warning(f"[WorkflowEngine] image edit validation skipped: {exc}")
        return {
            "checked": False,
            "passed": True,
            "issues": [],
            "reason": f"vision_check_failed:{type(exc).__name__}",
        }
