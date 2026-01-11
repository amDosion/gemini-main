"""
认证路由 - 处理用户注册、登录、登出、令牌刷新等
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from ..core.database import get_db
from ..core.config import settings
from ..services.auth_service import (
    AuthService,
    AuthConfigResponse,
    RegisterRequest,
    LoginRequest,
    UserResponse,
    AuthResponse,
    RegistrationDisabledError,
    EmailExistsError,
    PasswordMismatchError,
    InvalidCredentialsError,
    AccountDisabledError,
    InvalidTokenError,
    TokenExpiredError,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_auth_cookies(response: Response, tokens) -> None:
    """设置认证相关的 cookies"""
    import os
    # 开发环境使用 HTTP，生产环境使用 HTTPS
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    secure = is_production
    samesite = "strict" if is_production else "lax"
    
    # Access Token (httpOnly)
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        path="/"
    )
    # Refresh Token (httpOnly, 仅 refresh 端点可用)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        path="/api/auth/refresh"
    )
    # CSRF Token (JS 可读)
    response.set_cookie(
        key="csrf_token",
        value=tokens.csrf_token,
        httponly=False,  # JS 需要读取
        secure=secure,
        samesite=samesite,
        max_age=settings.jwt_access_token_expire_minutes * 60
    )


def clear_auth_cookies(response: Response) -> None:
    """清除认证相关的 cookies"""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")
    response.delete_cookie(key="csrf_token", path="/")


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config(db: Session = Depends(get_db)):
    """获取认证配置（注册开关状态）"""
    auth_service = AuthService(db)
    return auth_service.get_config()


@router.post("/register")
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """用户注册 - 返回 token 而不是设置 cookie"""
    auth_service = AuthService(db)
    try:
        result = auth_service.register(data)
        # ✅ 返回用户信息和 token，前端存储在 localStorage
        return {
            "user": result.user.dict(),
            "access_token": result.tokens.access_token,
            "refresh_token": result.tokens.refresh_token,
            "token_type": result.tokens.token_type,
            "expires_in": result.tokens.expires_in
        }
    except RegistrationDisabledError:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    except EmailExistsError:
        raise HTTPException(status_code=400, detail="Email already exists")
    except PasswordMismatchError:
        raise HTTPException(status_code=400, detail="Passwords do not match")


@router.post("/login")
async def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """用户登录 - 返回 token 而不是设置 cookie"""
    auth_service = AuthService(db)
    try:
        result = auth_service.login(data)
        # ✅ 返回用户信息和 token，前端存储在 localStorage
        return {
            "user": result.user.dict(),
            "access_token": result.tokens.access_token,
            "refresh_token": result.tokens.refresh_token,
            "token_type": result.tokens.token_type,
            "expires_in": result.tokens.expires_in
        }
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except AccountDisabledError as e:
        raise HTTPException(status_code=403, detail=e.message)


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    """用户登出 - 清除数据库中的 token"""
    auth_service = AuthService(db)
    
    # ✅ 从 Authorization header 获取 token
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            try:
                # 验证 token 并获取用户 ID
                payload = auth_service.validate_token(token)
                # 清除用户表中的 token
                user = auth_service.get_user_by_id(payload.sub)
                if user:
                    user.access_token = None
                    user.token_expires_at = None
                    db.commit()
            except Exception:
                pass  # Token 可能已无效，忽略错误
    
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """刷新访问令牌 - 从 Authorization header 获取 refresh token"""
    auth_service = AuthService(db)
    
    # ✅ 从 Authorization header 获取 refresh token
    auth_header = request.headers.get("Authorization")
    refresh_token = None
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            refresh_token = parts[1]
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    try:
        tokens = auth_service.refresh_tokens(refresh_token)
        # ✅ 更新用户表中的 access_token
        payload = auth_service.validate_token(refresh_token)
        user = auth_service.get_user_by_id(payload.sub)
        if user:
            user.access_token = tokens.access_token
            user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
            db.commit()
        # ✅ 返回新的 token，前端存储在 localStorage
        return {
            "access_token": tokens.access_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in
        }
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """获取当前用户信息 - 从 Authorization header 获取 token"""
    auth_service = AuthService(db)
    
    # ✅ 从 Authorization header 获取 token
    auth_header = request.headers.get("Authorization")
    access_token = None
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            access_token = parts[1]
    
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        return auth_service.get_current_user(access_token)
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
