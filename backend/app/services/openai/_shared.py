"""
OpenAI 服务共享辅助函数。
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Set

from openai import AsyncOpenAI

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_IMAGE_REQUEST_TIMEOUT_SECONDS = 240.0
DEFAULT_IMAGE_REQUEST_MAX_RETRIES = 0

logger = logging.getLogger(__name__)

INTERNAL_OPTION_KEYS: Set[str] = {
    "base_url",
    "frontend_session_id",
    "session_id",
    "message_id",
    "active_image_url",
    "enable_search",
    "enable_thinking",
    "enable_code_execution",
    "enable_browser",
    "enable_grounding",
    "reference_images",
    "enhance_prompt",
    "enhance_prompt_model",
    "openai_responses_model",
    "openai_previous_response_id",
}

CHAT_ALLOWED_OPTION_KEYS: Set[str] = {
    "temperature",
    "max_tokens",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "seed",
    "stop",
    "response_format",
    "logit_bias",
    "n",
    "user",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "stream_options",
}

IMAGE_ALLOWED_OPTION_KEYS: Set[str] = {
    "size",
    "quality",
    "style",
    "n",
    "response_format",
    "user",
    "background",
    "moderation",
    "output_format",
    "output_compression",
    "partial_images",
}

IMAGE_EDIT_ALLOWED_OPTION_KEYS: Set[str] = {
    "size",
    "quality",
    "n",
    "response_format",
    "user",
    "background",
    "moderation",
    "output_format",
    "output_compression",
    "input_fidelity",
    "mask",
    "partial_images",
}

SPEECH_ALLOWED_OPTION_KEYS: Set[str] = {
    "model",
    "response_format",
    "speed",
    "instructions",
}

IMAGE_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "16:9": "1792x1024",
}

GPT_IMAGE_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "4:3": "1152x864",
    "3:4": "864x1152",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
}

GPT_IMAGE_2_MAX_SIZE_BY_ASPECT_RATIO = {
    "1:1": "2880x2880",
    "4:3": "2880x2160",
    "3:4": "2160x2880",
    "16:9": "3840x2160",
    "9:16": "2160x3840",
    "3:2": "3456x2304",
    "2:3": "2304x3456",
}

GPT_IMAGE_2_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO = {
    "1K": {
        "1:1": "1024x1024",
        "4:3": "1152x864",
        "3:4": "864x1152",
        "16:9": "1280x720",
        "9:16": "720x1280",
        "3:2": "1536x1024",
        "2:3": "1024x1536",
    },
    "2K": {
        "1:1": "2048x2048",
        "4:3": "2048x1536",
        "3:4": "1536x2048",
        "16:9": "2048x1152",
        "9:16": "1152x2048",
        "3:2": "2304x1536",
        "2:3": "1536x2304",
    },
    "MAX": GPT_IMAGE_2_MAX_SIZE_BY_ASPECT_RATIO,
    "4K": GPT_IMAGE_2_MAX_SIZE_BY_ASPECT_RATIO,
}

GPT_IMAGE_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO = {
    "1K": {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "3:2": "1536x1024",
    },
}

GPT_IMAGE_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}
GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3840
GPT_IMAGE_2_MAX_ASPECT_RATIO = 3.0
DALL_E_2_SIZES = {"256x256", "512x512", "1024x1024"}
DALL_E_3_SIZES = {"1024x1024", "1024x1792", "1792x1024"}

AUDIO_MIME_TYPE_BY_FORMAT = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/pcm",
}


def build_async_client(
    api_key: str,
    base_url: Optional[str] = None,
    *,
    timeout: float = 120.0,
    max_retries: int = 3,
    client: Optional[AsyncOpenAI] = None,
) -> AsyncOpenAI:
    if client is not None:
        return client

    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url or DEFAULT_BASE_URL,
        timeout=timeout,
        max_retries=max_retries,
    )


def is_official_openai_base_url(base_url: Optional[str]) -> bool:
    return str(base_url or DEFAULT_BASE_URL).strip().rstrip("/") == DEFAULT_BASE_URL.rstrip("/")


def coerce_openai_image_timeout(value: Optional[Any]) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return DEFAULT_IMAGE_REQUEST_TIMEOUT_SECONDS
    if timeout <= 0:
        return DEFAULT_IMAGE_REQUEST_TIMEOUT_SECONDS
    return timeout


def coerce_openai_image_max_retries(value: Optional[Any]) -> int:
    try:
        retries = int(value)
    except (TypeError, ValueError):
        return DEFAULT_IMAGE_REQUEST_MAX_RETRIES
    return max(0, retries)


def with_openai_image_client_options(
    client: AsyncOpenAI,
    *,
    timeout: float,
    max_retries: int,
) -> AsyncOpenAI:
    with_options = getattr(client, "with_options", None)
    if not callable(with_options):
        return client
    return with_options(timeout=timeout, max_retries=max_retries)


def elapsed_ms(start_time: float) -> float:
    return (time.perf_counter() - start_time) * 1000


def filter_allowed_kwargs(
    kwargs: Mapping[str, Any],
    *,
    allowed_keys: Iterable[str],
    aliases: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    alias_map = aliases or {}
    allowed = set(allowed_keys)
    filtered: Dict[str, Any] = {}

    for key, value in kwargs.items():
        if value is None:
            continue
        normalized_key = alias_map.get(key, key)
        if normalized_key in INTERNAL_OPTION_KEYS:
            continue
        if normalized_key not in allowed:
            continue
        filtered[normalized_key] = value

    return filtered


def prepare_kwargs_for_openai_method(method: Any, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    prepared = dict(kwargs)
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return prepared

    params = signature.parameters
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return prepared

    passthrough: Dict[str, Any] = {}
    accepted: Dict[str, Any] = {}
    for key, value in prepared.items():
        if key in params:
            accepted[key] = value
        else:
            passthrough[key] = value

    if not passthrough:
        return accepted

    if "extra_body" not in params:
        return accepted

    extra_body = accepted.get("extra_body")
    merged_extra_body = dict(extra_body) if isinstance(extra_body, Mapping) else {}
    merged_extra_body.update(passthrough)
    accepted["extra_body"] = merged_extra_body
    return accepted


def is_gpt_image_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    return normalized.startswith("gpt-image") or normalized.startswith("chatgpt-image")


def is_gpt_image_2_model(model: str) -> bool:
    normalized = str(model or "").strip().lower()
    return normalized.startswith("gpt-image-2")


def is_valid_gpt_image_2_size(size: str) -> bool:
    value = str(size or "").strip().lower()
    if value == "auto":
        return True
    if "x" not in value:
        return False
    width_raw, height_raw = value.split("x", 1)
    try:
        width = int(width_raw)
        height = int(height_raw)
    except ValueError:
        return False
    if width <= 0 or height <= 0:
        return False
    if width > GPT_IMAGE_2_MAX_EDGE or height > GPT_IMAGE_2_MAX_EDGE:
        return False
    if width % 16 != 0 or height % 16 != 0:
        return False
    pixels = width * height
    if pixels < GPT_IMAGE_2_MIN_PIXELS or pixels > GPT_IMAGE_2_MAX_PIXELS:
        return False
    long_edge = max(width, height)
    short_edge = min(width, height)
    return long_edge / short_edge <= GPT_IMAGE_2_MAX_ASPECT_RATIO


def normalize_image_size(model: str, size: Optional[Any]) -> Optional[str]:
    value = str(size or "").strip()
    if not value:
        return None

    lower_model = str(model or "").strip().lower()
    lowered_value = value.lower()
    normalized_tier = value.upper()
    if is_gpt_image_2_model(lower_model) and normalized_tier in GPT_IMAGE_2_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO:
        return None
    if is_gpt_image_2_model(lower_model):
        return lowered_value if is_valid_gpt_image_2_size(lowered_value) else None
    if is_gpt_image_model(lower_model):
        return lowered_value if lowered_value in GPT_IMAGE_SIZES else None
    if lower_model.startswith("dall-e-2"):
        return lowered_value if lowered_value in DALL_E_2_SIZES else None
    if lower_model.startswith("dall-e-3"):
        return lowered_value if lowered_value in DALL_E_3_SIZES else None
    if "x" in lowered_value or lowered_value == "auto":
        return lowered_value
    return None


def map_image_resolution_to_size(
    model: str,
    resolution: Optional[Any],
    aspect_ratio: Optional[str],
) -> Optional[str]:
    value = str(resolution or "").strip()
    if not value:
        return None

    if value.lower() == "auto" and is_gpt_image_model(model):
        return "auto"

    if is_gpt_image_2_model(model):
        tier_map = GPT_IMAGE_2_SIZE_BY_RESOLUTION_AND_ASPECT_RATIO.get(value.upper())
        if tier_map:
            aspect = str(aspect_ratio or "").strip() or "1:1"
            return tier_map.get(aspect) or tier_map.get("1:1")

    return normalize_image_size(model, value)


def map_image_aspect_ratio_to_size(model: str, aspect_ratio: Optional[str]) -> Optional[str]:
    value = str(aspect_ratio or "").strip()
    if not value:
        return None

    mapped = (
        GPT_IMAGE_SIZE_BY_ASPECT_RATIO.get(value)
        if is_gpt_image_model(model)
        else IMAGE_SIZE_BY_ASPECT_RATIO.get(value)
    )
    if not mapped:
        return None

    if str(model or "").strip().lower().startswith("dall-e-2") and mapped != "1024x1024":
        return "1024x1024"

    return mapped


def normalize_image_api_kwargs(
    model: str,
    kwargs: Mapping[str, Any],
    *,
    allowed_keys: Iterable[str] = IMAGE_ALLOWED_OPTION_KEYS,
) -> Dict[str, Any]:
    normalized = filter_allowed_kwargs(
        kwargs,
        allowed_keys=allowed_keys,
        aliases={
            "number_of_images": "n",
            "num_images": "n",
            "output_mime_type": "output_format",
            "output_compression_quality": "output_compression",
        },
    )

    size = normalize_image_size(model, normalized.get("size"))
    if not size:
        normalized.pop("size", None)
    if not size:
        size = map_image_resolution_to_size(
            model,
            kwargs.get("image_resolution") or kwargs.get("resolution"),
            kwargs.get("image_aspect_ratio") or kwargs.get("aspect_ratio"),
        )
    if not size:
        size = map_image_aspect_ratio_to_size(
            model,
            kwargs.get("image_aspect_ratio") or kwargs.get("aspect_ratio"),
        )
    if size:
        normalized["size"] = str(size).strip()

    if "n" in normalized:
        try:
            count = int(normalized["n"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported OpenAI image count: {normalized['n']}") from exc
        if str(model or "").strip().lower().startswith("dall-e-3"):
            count = 1
        else:
            count = max(1, min(count, 10))
        normalized["n"] = count
    elif str(model or "").strip().lower().startswith("dall-e-3"):
        normalized["n"] = 1

    is_gpt_image = is_gpt_image_model(model)

    if is_gpt_image:
        normalized.pop("response_format", None)
        normalized.pop("style", None)
    else:
        response_format = str(normalized.get("response_format") or "").strip().lower()
        if response_format and response_format not in {"url", "b64_json"}:
            normalized.pop("response_format", None)
        normalized.pop("background", None)
        normalized.pop("moderation", None)
        normalized.pop("output_format", None)
        normalized.pop("output_compression", None)
        normalized.pop("input_fidelity", None)

    if is_gpt_image_2_model(model):
        # Official docs state gpt-image-2 always processes inputs at high fidelity
        # and does not allow changing this edit/reference-image parameter.
        normalized.pop("input_fidelity", None)

    output_format = str(normalized.get("output_format") or "").strip().lower()
    if output_format.startswith("image/"):
        output_format = output_format.split("/", 1)[1]
    if output_format and output_format not in {"png", "jpeg", "webp"}:
        normalized.pop("output_format", None)
        output_format = ""
    elif output_format:
        normalized["output_format"] = output_format
    if is_gpt_image_2_model(model) and "output_format" not in normalized:
        normalized["output_format"] = "png"
        output_format = "png"

    if "output_compression" in normalized:
        if output_format not in {"jpeg", "webp"}:
            normalized.pop("output_compression", None)
        else:
            try:
                output_compression = int(normalized["output_compression"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Unsupported OpenAI image output_compression: {normalized['output_compression']}"
                ) from exc
            normalized["output_compression"] = max(0, min(output_compression, 100))

    quality = str(normalized.get("quality") or "").strip().lower()
    if quality:
        allowed_quality = (
            {"auto", "low", "medium", "high"}
            if is_gpt_image
            else {"standard", "hd"}
        )
        if quality not in allowed_quality:
            normalized.pop("quality", None)
        else:
            normalized["quality"] = quality
    if is_gpt_image_2_model(model) and "quality" not in normalized:
        normalized["quality"] = "high"

    background = str(normalized.get("background") or "").strip().lower()
    if background:
        allowed_background = (
            {"auto", "opaque"}
            if is_gpt_image_2_model(model)
            else {"auto", "opaque", "transparent"}
        )
        if not is_gpt_image or background not in allowed_background:
            normalized.pop("background", None)
        else:
            normalized["background"] = background

    moderation = str(normalized.get("moderation") or "").strip().lower()
    if moderation:
        if not is_gpt_image or moderation not in {"auto", "low"}:
            normalized.pop("moderation", None)
        else:
            normalized["moderation"] = moderation

    input_fidelity = str(normalized.get("input_fidelity") or "").strip().lower()
    if input_fidelity:
        if input_fidelity not in {"low", "high"}:
            normalized.pop("input_fidelity", None)
        else:
            normalized["input_fidelity"] = input_fidelity

    if str(model or "").strip().lower().startswith("dall-e-2"):
        normalized.pop("quality", None)
        normalized.pop("style", None)

    return normalized


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


# 扇出并发上限: 与 ResponsesImageService 保持一致, 并尊重网关的 per-user 并发限制
# (sub2api 默认 user_concurrency=5)。避免 n=10 时一次打满并发触发 429/502。
# 默认值; 可经 OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY 环境变量按部署调优。
IMAGE_FANOUT_MAX_CONCURRENCY = 4

# 显式哨兵: 与“调用方主动传入 max_concurrency=None”区分; 默认时按环境变量解析。
_FANOUT_CONCURRENCY_DEFAULT = object()


def resolve_image_fanout_max_concurrency() -> int:
    """解析图像扇出并发上限。

    读取 ``OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY`` 环境变量; 缺省、非法或 <=0
    时回退到 ``IMAGE_FANOUT_MAX_CONCURRENCY`` (默认 4)。允许按部署/网关 per-user
    并发限制调优而无需改代码。
    """
    raw = os.environ.get("OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY")
    if raw is None:
        return IMAGE_FANOUT_MAX_CONCURRENCY
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return IMAGE_FANOUT_MAX_CONCURRENCY
    if value <= 0:
        return IMAGE_FANOUT_MAX_CONCURRENCY
    return value


async def call_image_api_with_fanout(
    request_call: Callable[[int], Awaitable[Any]],
    count: int,
    *,
    max_concurrency: Any = _FANOUT_CONCURRENCY_DEFAULT,
) -> Any:
    """发起图像请求；当请求张数 > 1 时,扇出为 N 个并发的单图(n=1)调用。

    背景(经验证据,见 .investigations/2026-06-02-openai-batch-image-502.md):
    官方 OpenAI Images API 的 ``n`` 参数合法取值为 1-10,原生批量本应可用。
    但部分 OpenAI 兼容网关——尤其是把 ``/v1/images/generations`` 转译为
    Responses API ``image_generation`` 工具的订阅/OAuth 代理——并不支持原生
    ``n``:n>1 会被上游拒绝(``Unknown parameter: 'tools[0].n'``)并以 502 暴露。
    而单图(n=1)请求在所有后端都稳定可用。

    因此对 count>1 一律扇出为 count 个 n=1 调用并合并 ``.data``——原生批量后端与
    订阅/OAuth 后端都能拿回 N 张图,同时保持公开契约不变(返回对象的 ``.data``
    持有 N 个图像项)。并发受 ``max_concurrency`` 闸约束以免超过网关 per-user
    并发限制; 未显式传入时按 ``OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY`` 解析。
    count<=1 时直接透传,不引入额外开销。

    部分成功语义(partial-success): 各扇出腿相互独立。某一腿失败(例如单次上游
    502)不得丢弃其它已完成且已计费的腿——使用 ``return_exceptions=True`` 收集,
    合并所有成功腿的 ``.data`` 并对失败腿记录警告。仅当所有腿都失败时, 才抛出
    第一个异常(保留可诊断的失败路径)。
    """
    safe_count = max(1, count)
    if safe_count == 1:
        return await request_call(1)

    if max_concurrency is _FANOUT_CONCURRENCY_DEFAULT or max_concurrency is None:
        resolved_concurrency = resolve_image_fanout_max_concurrency()
    else:
        resolved_concurrency = int(max_concurrency)

    semaphore = asyncio.Semaphore(max(1, min(resolved_concurrency, safe_count)))

    async def _bounded_call() -> Any:
        async with semaphore:
            return await request_call(1)

    settled = await asyncio.gather(
        *(_bounded_call() for _ in range(safe_count)),
        return_exceptions=True,
    )

    merged_data: List[Any] = []
    successes: List[Any] = []
    first_error: Optional[BaseException] = None
    failure_count = 0
    for resp in settled:
        if isinstance(resp, BaseException):
            failure_count += 1
            if first_error is None:
                first_error = resp
            continue
        successes.append(resp)
        merged_data.extend(getattr(resp, "data", None) or [])

    if not successes:
        # 全部失败: 抛出第一个异常以保留可诊断的失败路径。
        assert first_error is not None  # for type-checkers; loop guarantees this
        raise first_error

    if failure_count:
        logger.warning(
            "[OpenAI fan-out] %s/%s image legs failed; returning %s partial result(s). "
            "First error: %s",
            failure_count,
            safe_count,
            len(merged_data),
            first_error,
        )

    base = successes[0]
    try:
        base.data = merged_data
        return base
    except Exception:  # pragma: no cover - 兜底: 部分响应对象不可变
        return SimpleNamespace(data=merged_data)


def image_response_to_results(response: Any, request_kwargs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    results = []
    for item in getattr(response, "data", []) or []:
        image_url = extract_image_url(item, request_kwargs)
        if not image_url:
            continue
        results.append({
            "url": image_url,
            "revised_prompt": read_field(item, "revised_prompt"),
            "mime_type": infer_image_result_mime_type(item, request_kwargs),
        })
    return results


def responses_image_response_to_results(
    response: Any,
    *,
    output_format: Optional[str] = None,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    mime_type = image_output_format_to_mime_type(output_format)
    response_id = read_field(response, "id")
    output_text = read_field(response, "output_text", "outputText")

    for item in read_field(response, "output") or []:
        if read_field(item, "type") != "image_generation_call":
            continue
        image_base64 = read_field(item, "result")
        if not isinstance(image_base64, str) or not image_base64:
            continue
        result: Dict[str, Any] = {
            "url": f"data:{mime_type};base64,{image_base64}",
            "mime_type": mime_type,
        }
        if isinstance(response_id, str) and response_id:
            result["openai_response_id"] = response_id
        if isinstance(output_text, str) and output_text:
            result["text"] = output_text
        results.append(result)

    return results


def extract_image_url(item: Any, request_kwargs: Mapping[str, Any]) -> Optional[str]:
    direct_url = read_field(item, "url")
    if isinstance(direct_url, str) and direct_url:
        return direct_url

    b64_json = read_field(item, "b64_json")
    if isinstance(b64_json, str) and b64_json:
        mime_type = infer_image_result_mime_type(item, request_kwargs)
        return f"data:{mime_type};base64,{b64_json}"

    return None


def infer_image_result_mime_type(item: Any, request_kwargs: Mapping[str, Any]) -> str:
    explicit_mime = read_field(item, "mime_type", "mimeType")
    if isinstance(explicit_mime, str) and explicit_mime:
        return explicit_mime
    return image_output_format_to_mime_type(request_kwargs.get("output_format"))


def read_field(item: Any, *field_names: str) -> Any:
    if isinstance(item, dict):
        for field_name in field_names:
            if field_name in item:
                return item[field_name]
        return None

    for field_name in field_names:
        value = getattr(item, field_name, None)
        if value is not None:
            return value
    return None


def audio_format_to_mime_type(audio_format: str) -> str:
    normalized = str(audio_format or "").strip().lower()
    return AUDIO_MIME_TYPE_BY_FORMAT.get(normalized, "audio/mpeg")


def image_output_format_to_mime_type(output_format: Optional[str]) -> str:
    normalized = str(output_format or "").strip().lower()
    if normalized == "jpeg":
        return "image/jpeg"
    if normalized == "webp":
        return "image/webp"
    return "image/png"


def to_data_url(content: bytes, mime_type: str) -> str:
    import base64

    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


async def read_binary_response_content(response: Any) -> bytes:
    if hasattr(response, "read"):
        content = response.read()
        if inspect.isawaitable(content):
            content = await content
        return _coerce_binary_content(content)

    if hasattr(response, "content"):
        return _coerce_binary_content(response.content)

    return _coerce_binary_content(response)


def _coerce_binary_content(content: Any) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    raise RuntimeError(f"Unsupported binary response type: {type(content).__name__}")
