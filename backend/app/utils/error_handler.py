import logging
import re
import traceback

from fastapi import HTTPException

from ..core.config import settings

logger = logging.getLogger(__name__)


# 常见 provider API key 形态——用于在日志中脱敏 error 字符串，避免 key 片段被持久化或转发到第三方监控
_KEY_PATTERNS = (
    re.compile(r"(sk-[A-Za-z0-9_-]{4})[A-Za-z0-9_-]{8,}"),  # OpenAI / Anthropic style
    re.compile(r"(AIza[A-Za-z0-9_-]{4})[A-Za-z0-9_-]{20,}"),  # Google API key
    re.compile(r"(gsk_[A-Za-z0-9]{4})[A-Za-z0-9]{8,}"),  # Groq
    re.compile(r"(Bearer\s+[A-Za-z0-9_\-\.]{4})[A-Za-z0-9_\-\.]+", re.IGNORECASE),  # Bearer tokens
    re.compile(
        r"((?:api[_-]?key|access[_-]?token|secret)[\s=:\"']+[A-Za-z0-9_-]{0,4})"
        r"[A-Za-z0-9_-]{12,}",
        re.IGNORECASE,
    ),
)


def _mask_keys_in_text(text: str) -> str:
    """对自由文本中的 API key/Token 形态做脱敏，保留前缀以便定位 provider。"""
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "...redacted", text)
    return text


_RATE_LIMIT_KEYWORDS = (
    "429", "resource_exhausted", "exceeded your current quota",
    "rate limit", "quota", "too many requests",
)
_BAD_REQUEST_KEYWORDS = ("invalid", "bad request", "bad_request", "invalid_argument")
_BAD_GATEWAY_KEYWORDS = ("502", "bad gateway", "upstream_error", "upstream request failed")
_SERVICE_UNAVAILABLE_KEYWORDS = ("503", "overloaded", "unavailable")
_TIMEOUT_KEYWORDS = ("timeout", "timed out", "readtimeout", "request timed out")


def classify_provider_error_code(error_str: str) -> int:
    """根据错误消息字符串推断 HTTP 状态码。

    统一的 provider 错误分类逻辑，供所有路由复用。
    """
    lowered = str(error_str or "").lower()
    if any(kw in lowered for kw in _RATE_LIMIT_KEYWORDS):
        return 429
    if any(kw in lowered for kw in _BAD_REQUEST_KEYWORDS):
        return 400
    if any(kw in lowered for kw in _BAD_GATEWAY_KEYWORDS):
        return 502
    if any(kw in lowered for kw in _SERVICE_UNAVAILABLE_KEYWORDS):
        return 503
    if any(kw in lowered for kw in _TIMEOUT_KEYWORDS):
        return 504
    return 500


_ERROR_DETAILS = {
    429: {
        "error": "RESOURCE_EXHAUSTED",
        "message": "API配额已用尽",
        "suggestions": ["等待配额重置", "升级到更高配额计划", "减少请求频率"],
    },
    400: {
        "error": "INVALID_ARGUMENT",
        "message": "请求参数无效",
        "suggestions": ["检查prompt格式", "确认agent名称正确", "验证工具配置"],
    },
    503: {
        "error": "SERVICE_UNAVAILABLE",
        "message": "服务暂时过载",
        "suggestions": ["稍后重试", "使用指数退避策略"],
    },
    504: {
        "error": "GATEWAY_TIMEOUT",
        "message": "上游服务响应超时",
        "suggestions": ["稍后重试", "降低分辨率或生成数量", "检查上游代理状态"],
    },
    502: {
        "error": "BAD_GATEWAY",
        "message": "上游网关请求失败",
        "suggestions": ["稍后重试", "检查上游代理状态"],
    },
}


def handle_gemini_error(error: Exception) -> HTTPException:
    """Handle Gemini API errors.

    生产环境(settings.is_production)只返回模板化 message，不暴露原始 provider 错误字符串
    (避免泄露 API key 片段、内部域名、堆栈等)；非生产环境保留 original_error 便于调试。
    生产环境下原始错误仍写入服务端日志。
    """
    error_str = str(error)
    status_code = classify_provider_error_code(error_str)
    is_prod = settings.is_production

    if is_prod:
        # 生产环境：日志记录脱敏后的错误 + traceback，响应只给模板
        masked = _mask_keys_in_text(error_str)
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        logger.error(
            f"[handle_gemini_error] status={status_code} provider_error={masked!r}\n"
            f"traceback:\n{''.join(tb)}"
        )

    template = _ERROR_DETAILS.get(status_code)
    if template is None:
        detail: dict = {
            "error": "INTERNAL_ERROR",
            "message": "内部错误" if is_prod else f"内部错误: {error_str}",
            "suggestions": ["联系技术支持", "查看错误日志"],
        }
        if not is_prod:
            detail["original_error"] = error_str
        return HTTPException(status_code=500, detail=detail)

    detail = {**template}
    if not is_prod:
        detail["original_error"] = error_str
    return HTTPException(status_code=status_code, detail=detail)
