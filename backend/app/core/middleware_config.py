"""
中间件配置模块

统一管理 FastAPI 应用的所有中间件配置。
"""

import os
import logging
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Scope, Receive, Send, Message
from typing import Optional, Any

from .config import settings

logger = logging.getLogger(__name__)

DEFAULT_GZIP_MINIMUM_SIZE = 1024
GZIP_MINIMUM_SIZE_ENV_VAR = "GZIP_MINIMUM_SIZE"


def _resolve_gzip_minimum_size() -> int:
    raw = os.getenv(GZIP_MINIMUM_SIZE_ENV_VAR, str(DEFAULT_GZIP_MINIMUM_SIZE)).strip()
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%r, fallback to default=%s",
            GZIP_MINIMUM_SIZE_ENV_VAR,
            raw,
            DEFAULT_GZIP_MINIMUM_SIZE,
        )
        return DEFAULT_GZIP_MINIMUM_SIZE
    return max(0, value)


class SecurityHeadersMiddleware:
    """为所有 HTTP 响应注入基础安全头（若下游未设置）。"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                if "x-content-type-options" not in headers:
                    headers["X-Content-Type-Options"] = "nosniff"
                if "x-frame-options" not in headers:
                    headers["X-Frame-Options"] = "DENY"
                if "referrer-policy" not in headers:
                    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestIDMiddleware:
    """透传或生成请求 ID，并写入 request.state 与响应头。"""

    header_name = "x-request-id"

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id: Optional[str] = None
        for name, value in scope.get("headers", []):
            if name.lower() == self.header_name.encode("latin-1"):
                request_id = value.decode("latin-1").strip()
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        state = scope.setdefault("state", {})
        if isinstance(state, dict):
            state["request_id"] = request_id

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers["X-Request-ID"] = request_id
            await send(message)

        await self.app(scope, receive, send_wrapper)


def configure_middlewares(
    app: FastAPI,
    case_conversion_middleware: Optional[Any] = None,
    case_conversion_available: bool = False,
    log_prefixes: Optional[dict] = None
):
    """
    配置所有中间件

    中间件执行顺序（洋葱模型，后添加的在外层）：
    - 请求流向: 请求 → CORS → CaseConversion → 路由
    - 响应流向: 响应 ← CORS ← CaseConversion ← 路由

    Args:
        app: FastAPI 应用实例
        case_conversion_middleware: CaseConversionMiddleware 类（如果可用）
        case_conversion_available: Case conversion middleware 是否可用
        log_prefixes: 日志前缀字典
    """
    prefixes = log_prefixes or {}

    # 1. CaseConversion 中间件（camelCase <-> snake_case 自动转换）
    if case_conversion_available and case_conversion_middleware:
        app.add_middleware(case_conversion_middleware)
        logger.info(f"{prefixes.get('success', '✅')} Case conversion middleware enabled (camelCase <-> snake_case)")
    else:
        logger.warning(f"{prefixes.get('warning', '⚠️')} Case conversion middleware NOT available")

    # 2. CORS 中间件（跨域资源共享）
    # 注意：使用 httpOnly Cookie 时，allow_origins 不能为 "*"
    cors_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:21573,http://127.0.0.1:21573"
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,  # 允许 Cookie
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", "X-Request-ID"],
    )

    logger.info(f"{prefixes.get('success', '✅')} CORS middleware configured")
    logger.info(f"{prefixes.get('info', 'ℹ️')} Allowed origins: {cors_origins}")

    # 3. Trusted Host 中间件（Host header allowlist）
    trusted_hosts = settings.trusted_hosts
    if trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
        logger.info(f"{prefixes.get('success', '✅')} Trusted host middleware enabled")
        logger.info(f"{prefixes.get('info', 'ℹ️')} Allowed hosts: {trusted_hosts}")
    else:
        logger.warning(f"{prefixes.get('warning', '⚠️')} Trusted host middleware skipped (empty host allowlist)")

    # 4. GZip 中间件（响应压缩）
    gzip_minimum_size = _resolve_gzip_minimum_size()
    app.add_middleware(GZipMiddleware, minimum_size=gzip_minimum_size)
    logger.info(f"{prefixes.get('success', '✅')} GZip middleware enabled (minimum_size={gzip_minimum_size})")

    # 5. 安全响应头中间件
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info(f"{prefixes.get('success', '✅')} Security headers middleware enabled")

    # 6. 请求 ID 中间件（透传或生成）
    app.add_middleware(RequestIDMiddleware)
    logger.info(f"{prefixes.get('success', '✅')} Request ID middleware enabled")
