"""
认证中间件 - 处理 JWT 令牌验证和 CSRF 保护
"""
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.jwt_utils import decode_token, TokenPayload
from ..core.database import get_db
from ..services.auth_service import AuthService, InvalidTokenError, TokenExpiredError


# 不需要认证的路径
PUBLIC_PATHS = [
    "/",                    # 根路径健康检查
    "/health",              # 健康检查
    "/api/auth/config",     # 获取认证配置（注册开关）
    "/api/auth/login",      # 登录
    "/api/auth/register",   # 注册
    "/api/auth/refresh",    # 刷新令牌（使用 refresh_token cookie）
]


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 跳过公开路径
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        # 从 cookie 获取 access_token
        access_token = request.cookies.get("access_token")
        if not access_token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"}
            )

        # 验证令牌
        try:
            payload = decode_token(access_token)
            # 将用户信息注入到 request.state
            request.state.user_id = payload.sub
            request.state.token_payload = payload
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"}
            )

        # 对于状态变更请求，验证 CSRF token
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("X-CSRF-Token")
            
            # 跳过登录/注册/刷新的 CSRF 验证（它们在 PUBLIC_PATHS 中）
            if csrf_cookie and csrf_header:
                if csrf_cookie != csrf_header:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF validation failed"}
                    )

        return await call_next(request)


async def get_current_user(request: Request) -> Optional[str]:
    """
    获取当前用户 ID（依赖注入）
    
    用法:
        @router.get("/me")
        async def get_me(user_id: str = Depends(get_current_user)):
            ...
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def require_auth(func: Callable):
    """
    认证装饰器（用于需要认证的路由）
    
    用法:
        @router.get("/protected")
        @require_auth
        async def protected_route(request: Request):
            user_id = request.state.user_id
            ...
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not getattr(request.state, "user_id", None):
            raise HTTPException(status_code=401, detail="Not authenticated")
        return await func(request, *args, **kwargs)
    return wrapper
