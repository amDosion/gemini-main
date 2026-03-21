"""
认证路由 - 处理用户注册、登录、登出、令牌刷新等
"""
import logging
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from ...core.database import get_db
from ...core.config import settings
from ...services.common.auth_service import (
    AuthService,
    AuthConfigResponse,
    TokenPair,
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
    UserResponse,
    RegistrationDisabledError,
    EmailExistsError,
    PasswordMismatchError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    SamePasswordError,
    AccountDisabledError,
    InvalidTokenError,
    TokenExpiredError,
)
from ...core.dependencies import require_current_user
from ...services.common.persona_init_service import ensure_personas_initialized
from ...services.common.system_config_service import (
    initialize_system_configs,
    get_client_ip,
    is_private_ip,
    get_ip_info
)
from ...services.agent.agent_seed_service import ensure_seed_agents, get_default_seed_agents
from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
from ...models.db_models import IPLoginHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@dataclass(frozen=True)
class CookiePolicy:
    secure: bool
    samesite: str


@dataclass(frozen=True)
class AuthCookieSpec:
    key: str
    value: str
    path: str
    max_age: int
    httponly: bool


@dataclass(frozen=True)
class AuthCookieClearSpec:
    key: str
    path: str
    httponly: bool | None = None


def _build_cookie_policy() -> CookiePolicy:
    """
    统一 Cookie 安全策略：
    - 生产环境：secure=True, samesite=strict（不允许弱回退）
    - 非生产环境：secure=False, samesite=lax
    """
    if settings.is_production:
        return CookiePolicy(secure=True, samesite="strict")
    return CookiePolicy(secure=False, samesite="lax")


def _build_auth_cookie_specs(tokens: TokenPair) -> tuple[AuthCookieSpec, ...]:
    access_max_age = settings.jwt_access_token_expire_minutes * 60
    refresh_max_age = settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    return (
        AuthCookieSpec(
            key="access_token",
            value=tokens.access_token,
            path="/",
            max_age=access_max_age,
            httponly=True,
        ),
        AuthCookieSpec(
            key="refresh_token",
            value=tokens.refresh_token,
            path="/api/auth/refresh",
            max_age=refresh_max_age,
            httponly=True,
        ),

    )


def _build_auth_cookie_clear_specs() -> tuple[AuthCookieClearSpec, ...]:
    return (
        AuthCookieClearSpec(key="access_token", path="/", httponly=True),
        AuthCookieClearSpec(key="refresh_token", path="/api/auth/refresh", httponly=True),
    )


def set_auth_cookies(response: Response, tokens: TokenPair) -> None:
    """统一设置认证相关 cookies（access/refresh/csrf）"""
    policy = _build_cookie_policy()
    for cookie in _build_auth_cookie_specs(tokens):
        response.set_cookie(
            key=cookie.key,
            value=cookie.value,
            httponly=cookie.httponly,
            secure=policy.secure,
            samesite=policy.samesite,
            max_age=cookie.max_age,
            path=cookie.path,
        )


def clear_auth_cookies(response: Response) -> None:
    """统一清除认证相关 cookies"""
    policy = _build_cookie_policy()
    for cookie in _build_auth_cookie_clear_specs():
        delete_kwargs = {
            "key": cookie.key,
            "path": cookie.path,
            "secure": policy.secure,
            "samesite": policy.samesite,
        }
        if cookie.httponly is not None:
            delete_kwargs["httponly"] = cookie.httponly
        response.delete_cookie(**delete_kwargs)


@router.get("/config")
async def get_auth_config(db: Session = Depends(get_db)):
    """获取认证配置（注册开关状态）"""
    logger.info("[Auth] 收到获取配置请求")
    auth_service = AuthService(db)
    try:
        config = auth_service.get_config()
        logger.info(f"[Auth] 成功返回配置: allow_registration={config.allow_registration}")
        # 返回 snake_case，由中间件转换为 camelCase
        return {"allow_registration": config.allow_registration}
    except Exception as e:
        error_msg = str(e).lower()
        # ✅ 详细的错误分类和日志记录
        if "no such table" in error_msg or "does not exist" in error_msg:
            logger.error("[Auth] 数据库表不存在，系统可能未正确初始化")
        elif "no row" in error_msg or "none" in error_msg:
            logger.error("[Auth] SystemConfig 记录不存在，系统配置未初始化")
        elif "connection" in error_msg or "connect" in error_msg:
            logger.error("[Auth] 数据库连接失败")
        else:
            logger.error(f"[Auth] 获取配置失败: {e}", exc_info=True)
        # ✅ 返回通用错误消息，不泄露实现细节
        raise HTTPException(status_code=500, detail="Failed to get auth config")


@router.get("/ip-info")
async def get_ip_info_endpoint(request: Request):
    """
    获取客户端 IP 信息（用于测试和调试）
    
    返回：
    - detected_ip: 检测到的客户端 IP
    - is_private: 是否为私有 IP
    - ip_info: IP 详细信息（地理位置等，可选）
    - headers: 相关的请求头信息
    """
    try:
        # 获取客户端 IP
        detected_ip = get_client_ip(request, prefer_public=True)
        is_private = is_private_ip(detected_ip)
        
        # 获取相关请求头
        relevant_headers = {
            "X-Forwarded-For": request.headers.get("X-Forwarded-For"),
            "X-Real-IP": request.headers.get("X-Real-IP"),
            "CF-Connecting-IP": request.headers.get("CF-Connecting-IP"),
            "True-Client-IP": request.headers.get("True-Client-IP"),
            "X-Client-IP": request.headers.get("X-Client-IP"),
            "User-Agent": request.headers.get("User-Agent"),
        }
        
        # 可选：获取 IP 详细信息（地理位置等）
        ip_info = None
        if detected_ip and detected_ip != "unknown" and not is_private:
            try:
                ip_info = await get_ip_info(detected_ip)
            except Exception as e:
                logger.debug(f"[Auth] 获取 IP 信息失败: {e}")
        
        return {
            "detected_ip": detected_ip,
            "is_private": is_private,
            "ip_info": ip_info,
            "headers": relevant_headers,
            "client_host": request.client.host if request.client else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get IP info: {str(e)}")


@router.post("/register")
async def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """用户注册 - 返回 token 而不是设置 cookie"""
    auth_service = AuthService(db)
    try:
        result = auth_service.register(data)
        user_response = auth_service.get_current_user(result.tokens.access_token)

        # ✅ 注册后立即初始化统一 seed 集（列表接口会幂等补齐缺失项）
        created_agents = ensure_seed_agents(db, user_response.id, seeds=get_default_seed_agents())
        logger.info(
            "[Auth] Default agents initialized for new user %s: created=%s",
            user_response.id,
            created_agents,
        )

        # ✅ 为新用户初始化默认 Personas
        try:
            ensure_personas_initialized(user_response.id, db)
        except Exception as e:
            # Personas 初始化失败不应该阻止注册，只记录警告
            logger.warning(f"Failed to initialize default personas for new user {user_response.id}: {e}")

        # ✅ 为新用户自动初始化 Starter 工作流模板（注册后立即可用）
        template_service = WorkflowTemplateService(db=db)
        created_templates = await template_service.ensure_starter_templates(user_response.id)
        logger.info(
            "[Auth] Starter templates initialized for new user %s: created=%s",
            user_response.id,
            len(created_templates),
        )

        # ✅ 检查用户是否有活跃的配置文件（新用户通常为 false）
        from ...models.db_models import UserSettings
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_response.id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 返回用户信息和 token，前端存储在 localStorage
        return {
            "user": user_response.dict(),
            "access_token": result.tokens.access_token,
            "refresh_token": result.tokens.refresh_token,
            "token_type": result.tokens.token_type,
            "expires_in": result.tokens.expires_in,
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """用户登录 - 返回 token 并设置 Cookie（用于 EventSource 认证）"""
    auth_service = AuthService(db)
    try:
        # 获取客户端 IP 和 User-Agent
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        
        result = auth_service.login(data, ip_address=ip_address, user_agent=user_agent)
        user_response = auth_service.get_current_user(result.tokens.access_token)

        # ✅ 检查用户是否有活跃的配置文件（优化：减少前端初始化请求）
        from ...models.db_models import UserSettings
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_response.id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 统一安全 Cookie 策略（生产环境强制 secure + strict）
        set_auth_cookies(response, result.tokens)

        # ✅ 返回用户信息和 token，前端存储在 localStorage
        return {
            "user": user_response.dict(),
            "access_token": result.tokens.access_token,
            "refresh_token": result.tokens.refresh_token,
            "token_type": result.tokens.token_type,
            "expires_in": result.tokens.expires_in,
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except AccountDisabledError as e:
        raise HTTPException(status_code=403, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """用户登出 - 清除数据库中的 token 并撤销 refresh_token"""
    auth_service = AuthService(db)
    
    # ✅ 统一清除 Cookie
    clear_auth_cookies(response)
    
    # ✅ 从 Authorization header 获取 access_token
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            access_token = parts[1]
            try:
                # 验证 access_token 并获取用户 ID
                payload = auth_service.validate_token(access_token)
                user_id = payload.sub
                
                # 清除用户表中的 access_token
                user = auth_service.get_user_by_id(user_id)
                if user:
                    user.access_token = None
                    user.token_expires_at = None
                    db.commit()
                
                # ✅ 撤销该用户所有未过期的 refresh_token
                from ...models.db_models import RefreshToken
                now = datetime.now(timezone.utc)
                db.query(RefreshToken).filter(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now
                ).update({"revoked_at": now})
                
                # ✅ 记录登出到 IPLoginHistory
                ip_address = get_client_ip(request)
                user_agent = request.headers.get("User-Agent")
                ip_history = IPLoginHistory(
                    user_id=user_id,
                    ip_address=ip_address,
                    action="logout",
                    user_agent=user_agent
                )
                db.add(ip_history)
                db.commit()
                
                logger.info(f"[Logout] ✅ 用户 {user_id} 登出成功 (IP: {ip_address})")
            except Exception as e:
                logger.error(f"[Logout] Error revoking tokens: {e}")
                pass  # Token 可能已无效，忽略错误
    
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
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
        payload = auth_service.validate_token(tokens.refresh_token)  # 使用新的 refresh_token
        user_id = payload.sub
        user = auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user.access_token = tokens.access_token
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        db.commit()
        
        # ✅ 记录 token 刷新到 IPLoginHistory
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        try:
            ip_history = IPLoginHistory(
                user_id=user.id,
                ip_address=ip_address,
                action="token_refresh",
                user_agent=user_agent
            )
            db.add(ip_history)
            db.commit()
        except Exception as e:
            logger.warning(f"[Auth] 记录 token 刷新历史失败: {e}")

        # ✅ 检查用户是否有活跃的配置文件
        from ...models.db_models import UserSettings
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 统一安全 Cookie 策略（生产环境强制 secure + strict）
        set_auth_cookies(response, tokens)

        # ✅ 返回新的 access_token 和 refresh_token
        return {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,  # ✅ 新增：返回新的 refresh_token
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.get("/me")
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
        user_response = auth_service.get_current_user(access_token)

        # ✅ 检查用户是否有活跃的配置文件
        from ...models.db_models import UserSettings
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_response.id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 返回用户信息 + 配置状态
        return {
            **user_response.dict(),
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        # ✅ 捕获其他异常（如数据库错误），避免返回 500 错误
        logger.error(f"[Auth] 获取当前用户失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch user information")


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """修改当前用户密码"""
    auth_service = AuthService(db)

    try:
        auth_service.change_password(
            user_id=user_id,
            current_password=data.current_password,
            new_password=data.new_password,
            confirm_password=data.confirm_password
        )
        return {"success": True, "message": "Password updated successfully"}
    except PasswordMismatchError:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    except InvalidCurrentPasswordError:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    except SamePasswordError:
        raise HTTPException(status_code=400, detail="New password must be different from current password")
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Not authenticated")
