"""
全局异常处理器

统一管理 FastAPI 应用的异常映射，并输出统一错误结构：
{
  "code": "...",
  "message": "...",
  "details": ...,
  "request_id": "..."   # 可选
}
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any, Optional, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_ERROR_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
    504: "gateway_timeout",
}

_DEFAULT_MESSAGE_BY_STATUS = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    422: "Request validation failed",
    429: "Too many requests",
    500: "Internal server error",
    503: "Service unavailable",
    504: "Gateway timeout",
}


def _extract_request_id(request: Request) -> Optional[str]:
    request_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
    if request_id:
        return request_id
    state = getattr(request, "state", None)
    state_request_id = getattr(state, "request_id", None)
    if isinstance(state_request_id, str) and state_request_id:
        return state_request_id
    return None


def _default_error_code(status_code: int) -> str:
    if status_code >= 500:
        return "internal_error"
    return _ERROR_CODE_BY_STATUS.get(status_code, f"http_{status_code}")


def _default_message(status_code: int) -> str:
    if status_code >= 500:
        return _DEFAULT_MESSAGE_BY_STATUS[500]
    if status_code in _DEFAULT_MESSAGE_BY_STATUS:
        return _DEFAULT_MESSAGE_BY_STATUS[status_code]
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


def _build_error_response(
    *,
    request: Request,
    status_code: int,
    code: Optional[str] = None,
    message: Optional[str] = None,
    details: Any = None,
) -> JSONResponse:
    resolved_code = code or _default_error_code(status_code)
    resolved_message = message or _default_message(status_code)
    request_id = _extract_request_id(request)

    payload: dict[str, Any] = {
        "code": resolved_code,
        "message": resolved_message,
        "details": details,
    }
    if request_id:
        payload["request_id"] = request_id

    return JSONResponse(status_code=status_code, content=payload)


def _normalize_http_exception_detail(status_code: int, detail: Any) -> Tuple[Optional[str], Optional[str], Any]:
    is_server_error = status_code >= 500
    code: Optional[str] = None
    message: Optional[str] = None
    details: Any = None

    if isinstance(detail, dict):
        code = detail.get("code") or detail.get("error")
        detail_message = detail.get("message")
        if isinstance(detail_message, str) and detail_message:
            message = detail_message

        if not is_server_error:
            if "details" in detail:
                details = detail.get("details")
            elif "detail" in detail and not isinstance(detail.get("detail"), str):
                details = detail.get("detail")
            else:
                extras = {
                    k: v for k, v in detail.items()
                    if k not in {"code", "error", "message"}
                }
                details = extras or None
    elif isinstance(detail, list):
        if not is_server_error:
            details = detail
    elif isinstance(detail, str):
        if not is_server_error:
            message = detail
    elif detail is not None:
        if not is_server_error:
            details = detail

    return code, message, details


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 请求参数校验异常处理。"""
    path = request.url.path
    errors = exc.errors()
    logger.warning("[ValidationError] %s failed with %s validation error(s)", path, len(errors))
    return _build_error_response(
        request=request,
        status_code=422,
        code="validation_error",
        message=_DEFAULT_MESSAGE_BY_STATUS[422],
        details=errors,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTPException 映射处理（保留状态码语义）。"""
    code, message, details = _normalize_http_exception_detail(exc.status_code, exc.detail)
    if exc.status_code >= 500:
        logger.error("[HTTPException] %s %s", request.url.path, exc.status_code)
    else:
        logger.info("[HTTPException] %s %s", request.url.path, exc.status_code)
    return _build_error_response(
        request=request,
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理，避免泄露内部错误细节。"""
    logger.exception("[UnhandledException] %s failed: %s", request.url.path, type(exc).__name__)
    return _build_error_response(
        request=request,
        status_code=500,
        code="internal_error",
        message=_DEFAULT_MESSAGE_BY_STATUS[500],
        details=None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    logger.info("✅ Global exception handlers registered")
