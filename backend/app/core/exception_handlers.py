"""
全局异常处理器

统一管理 FastAPI 应用的所有异常处理逻辑。
"""

import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    全局 422 验证错误处理程序

    记录详细的验证错误信息，帮助诊断前后端字段不匹配问题。

    Args:
        request: FastAPI Request 对象
        exc: 验证异常对象

    Returns:
        JSONResponse: 包含错误详情的 422 响应
    """
    # 获取请求路径
    path = request.url.path

    # 记录详细的验证错误
    errors = exc.errors()
    logger.error(f"[ValidationError] 422 验证失败: {path}")
    logger.error(f"[ValidationError] 错误数量: {len(errors)}")

    for i, err in enumerate(errors):
        field = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "unknown error")
        err_type = err.get("type", "unknown")
        logger.error(f"[ValidationError]   [{i+1}] 字段: {field}, 消息: {msg}, 类型: {err_type}")

    # 返回标准的 422 响应
    return JSONResponse(
        status_code=422,
        content={"detail": errors}
    )


def register_exception_handlers(app: FastAPI):
    """
    注册所有全局异常处理器

    Args:
        app: FastAPI 应用实例
    """
    # 注册 422 验证错误处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    logger.info("✅ Global exception handlers registered")

    # 未来可以在这里添加更多异常处理器：
    # - HTTPException 自定义处理
    # - 通用 Exception 处理
    # - 特定业务异常处理
