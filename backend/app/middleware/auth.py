"""
认证中间件 - 处理 JWT 令牌验证和 CSRF 保护
"""
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException, Depends

from ..core.jwt_utils import decode_token, TokenPayload


# 不需要认证的路径
PUBLIC_PATHS = [
    "/",                    # 根路径健康检查
    "/health",              # 健康检查
    "/api/auth/config",     # 获取认证配置（注册开关）
    "/api/auth/login",      # 登录
    "/api/auth/register",   # 注册
    "/api/auth/refresh",    # 刷新令牌（使用 refresh_token cookie）
]


# AuthMiddleware removed - using Depends(require_current_user) instead


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
