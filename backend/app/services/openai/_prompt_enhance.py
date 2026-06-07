"""
OpenAI 视觉提示词增强(image/video)异步辅助。

从 ``_shared`` 拆分而来。依赖 ``_sizes`` 的模型识别与 ``read_field`` 字段访问器,
不反向依赖 ``_shared``,避免循环导入。``_shared`` 重新导出本模块全部公开名称
以维持既有调用方契约不变。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from openai import AsyncOpenAI

from ._sizes import is_gpt_image_model, read_field

logger = logging.getLogger(__name__)


def _is_openai_text_prompt_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    if not normalized:
        return False
    if is_gpt_image_model(normalized):
        return False
    if normalized.startswith(("dall-e", "dalle", "sora", "tts", "whisper")):
        return False
    if any(keyword in normalized for keyword in ("audio", "embedding", "moderation")):
        return False
    return normalized.startswith("gpt-") or (
        normalized.startswith("o") and len(normalized) > 1 and normalized[1].isdigit()
    )


def resolve_image_prompt_enhance_model(model_hint: Optional[str]) -> Optional[str]:
    hint = str(model_hint or "").strip()
    if _is_openai_text_prompt_model(hint):
        return hint
    return None


def normalize_prompt_enhance_thinking_level(thinking_level: Optional[str]) -> Optional[str]:
    level = str(thinking_level or "").strip().lower().replace("-", "_")
    if not level or level in {"auto", "default", "unspecified"}:
        return None
    if level in {"minimal", "low", "medium", "high"}:
        return level
    logger.warning("[OpenAI Image] Invalid prompt enhancement thinking level: %s", thinking_level)
    return None


def _extract_chat_completion_text(response: Any) -> Optional[str]:
    choices = read_field(response, "choices")
    if not isinstance(choices, list):
        choices = getattr(response, "choices", None)
    if not isinstance(choices, list):
        return None

    for choice in choices:
        message = read_field(choice, "message")
        content = read_field(message, "content") if message is not None else None
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                text = read_field(part, "text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts).strip()
    return None


async def _enhance_openai_visual_prompt(
    client: AsyncOpenAI,
    prompt: str,
    *,
    model_hint: Optional[str] = None,
    thinking_level: Optional[str] = None,
    task_label: str,
    task_guidance: str,
    extra_context: Optional[str] = None,
    log_label: str,
) -> Optional[str]:
    original_prompt = str(prompt or "").strip()
    if not original_prompt:
        return None

    enhance_model = resolve_image_prompt_enhance_model(model_hint)
    if not enhance_model:
        logger.warning(
            "[%s] Prompt enhancement requested without a valid OpenAI text model; "
            "using original prompt.",
            log_label,
        )
        return None

    system_prompt = (
        f"You are a professional {task_label} enhancer. Rewrite user input into a direct, "
        f"specific, visually actionable prompt. {task_guidance} "
        "Return only the enhanced prompt text, with no markdown and no explanations."
    )
    user_prompt = f"Original prompt:\n{original_prompt}"
    if extra_context:
        user_prompt += f"\n\n{extra_context}"

    try:
        request_kwargs = {
            "model": enhance_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        reasoning_effort = normalize_prompt_enhance_thinking_level(thinking_level)
        if reasoning_effort:
            request_kwargs["reasoning_effort"] = reasoning_effort
        response = await client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        logger.warning("[%s] Prompt enhancement failed; using original prompt: %s", log_label, exc)
        return None

    enhanced = _extract_chat_completion_text(response)
    return enhanced if enhanced else None


async def enhance_openai_image_prompt(
    client: AsyncOpenAI,
    prompt: str,
    *,
    model_hint: Optional[str] = None,
    thinking_level: Optional[str] = None,
    edit_mode: bool = False,
    has_reference_images: bool = False,
) -> Optional[str]:
    task_label = "image edit instruction" if edit_mode else "image generation prompt"
    extra_context = (
        "This is for image editing with reference image input. Preserve the referenced "
        "subject, product details, identity, and user-specified unchanged areas."
        if edit_mode and has_reference_images
        else None
    )
    return await _enhance_openai_visual_prompt(
        client,
        prompt,
        model_hint=model_hint,
        thinking_level=thinking_level,
        task_label=task_label,
        task_guidance=(
            "Preserve the user's intent, language, subject identity, constraints, "
            "composition requirements, and any negative instructions."
        ),
        extra_context=extra_context,
        log_label="OpenAI Image",
    )


async def enhance_openai_video_prompt(
    client: AsyncOpenAI,
    prompt: str,
    *,
    model_hint: Optional[str] = None,
    thinking_level: Optional[str] = None,
    operation: str = "text_to_video",
) -> Optional[str]:
    operation_label = {
        "image_to_video": "image-to-video prompt",
        "video_extension": "video continuation prompt",
        "video_edit": "video edit instruction",
    }.get(str(operation or "").strip(), "text-to-video prompt")
    operation_context = {
        "image_to_video": (
            "This is for image-to-video generation. Preserve the referenced subject and "
            "turn the still image into a coherent motion plan."
        ),
        "video_extension": (
            "This is for extending an existing video. Preserve scene continuity, subject "
            "identity, lighting, camera direction, and motion from the source clip."
        ),
        "video_edit": (
            "This is for editing an existing video. Preserve source-video content that the "
            "user did not ask to change."
        ),
    }.get(str(operation or "").strip())
    return await _enhance_openai_visual_prompt(
        client,
        prompt,
        model_hint=model_hint,
        thinking_level=thinking_level,
        task_label=operation_label,
        task_guidance=(
            "Preserve the user's intent, language, subject identity, constraints, "
            "composition requirements, and negative instructions. Add concrete motion, "
            "camera movement, pacing, scene continuity, lighting, and visual details when useful."
        ),
        extra_context=operation_context,
        log_label="OpenAI Video",
    )
