"""
中间件配置模块

统一管理 FastAPI 应用的所有中间件配置。
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any

logger = logging.getLogger(__name__)


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
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
    )

    logger.info(f"{prefixes.get('success', '✅')} CORS middleware configured")
    logger.info(f"{prefixes.get('info', 'ℹ️')} Allowed origins: {cors_origins}")

    # 未来可以在这里添加更多中间件：
    # - GZipMiddleware (响应压缩)
    # - RateLimitMiddleware (限流)
    # - RequestIDMiddleware (请求 ID 追踪)
    # - TimingMiddleware (请求耗时统计)
