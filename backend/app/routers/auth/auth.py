"""
认证路由 - 处理用户注册、登录、登出、令牌刷新等
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from ...core.database import get_db
from ...core.config import settings
from ...services.common.auth_service import (
    AuthService,
    AuthConfigResponse,
    TokenPair,
    UserResponse,
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
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
from ...core.user_context import extract_user_id_from_token
from ...services.common.persona_init_service import ensure_personas_initialized
from ...services.common.system_config_service import (
    get_client_ip,
    is_private_ip,
)
from ...services.agent.agent_seed_service import ensure_seed_agents, get_default_seed_agents
from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
from ...models.db_models import IPLoginHistory, RefreshToken, UserSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"


def _safe_auth_log_text(value: object, *, label: str = "error") -> str:
    if value is None:
        return "None"
    text = str(value)
    if not text:
        return f"<empty {label}>"
    return f"<redacted {label}; type={type(value).__name__}; length={len(text)}>"


class PublicTokenResponse(BaseModel):
    token_type: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    expires_in: int = Field(ge=1, le=31_536_000)


class AuthSessionResponse(PublicTokenResponse):
    user: UserResponse
    has_active_profile: bool = False


class AuthRefreshResponse(PublicTokenResponse):
    has_active_profile: bool = False


class CurrentUserResponse(UserResponse):
    has_active_profile: bool = False


class LogoutResponse(BaseModel):
    message: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)


class IpInfoResponse(BaseModel):
    detected_ip: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    is_private: bool


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


def _request_is_https(request: Request | None) -> bool:
    """
    判断请求是否经由 HTTPS（用于 cookie 安全策略）。

    - 直连 HTTPS：request.url.scheme == "https"
    - 反代场景：X-Forwarded-Proto: https（取第一个值）

    cookie 加固为 fail-safe：即便误判 HTTPS，Secure cookie 至多在纯 HTTP 下不发送，
    不会造成凭证泄露。
    """
    if request is None:
        return False

    url = getattr(request, "url", None)
    scheme = getattr(url, "scheme", None)
    if isinstance(scheme, str) and scheme.lower() == "https":
        return True

    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        first = forwarded_proto.split(",")[0].strip().lower()
        if first == "https":
            return True

    return False


def _build_cookie_policy(request: Request | None = None) -> CookiePolicy:
    """
    统一 Cookie 安全策略：
    - 生产环境：secure=True, samesite=strict（不允许弱回退）
    - 任意 HTTPS 请求：secure=True, samesite=strict（即使非生产环境）
    - 其余非生产、纯 HTTP：secure=False, samesite=lax（便于本地开发）
    """
    if settings.is_production or _request_is_https(request):
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


def set_auth_cookies(response: Response, tokens: TokenPair, request: Request | None = None) -> None:
    """统一设置认证相关 cookies（access/refresh/csrf）"""
    policy = _build_cookie_policy(request)
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


def clear_auth_cookies(response: Response, request: Request | None = None) -> None:
    """统一清除认证相关 cookies"""
    policy = _build_cookie_policy(request)
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


def _get_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def _iter_request_tokens(request: Request, *, cookie_name: str) -> list[str]:
    tokens: list[str] = []

    bearer_token = _get_bearer_token(request.headers.get("Authorization"))
    if bearer_token:
        tokens.append(bearer_token)

    cookie_token = request.cookies.get(cookie_name)
    if cookie_token and cookie_token not in tokens:
        tokens.append(cookie_token)

    return tokens


def _get_request_token(request: Request, *, cookie_name: str) -> str | None:
    """
    Resolve an auth token from request state.

    Authorization header wins so API clients can explicitly override browser
    cookies. Browser UI can rely on httpOnly cookies without exposing refresh
    tokens to localStorage.
    """
    tokens = _iter_request_tokens(request, cookie_name=cookie_name)
    return tokens[0] if tokens else None


def _get_valid_request_token(
    request: Request,
    *,
    cookie_name: str,
    is_valid_token: Callable[[str], bool],
) -> str | None:
    """Return the first request token that is valid for this endpoint."""
    for token in _iter_request_tokens(request, cookie_name=cookie_name):
        if is_valid_token(token):
            return token
    return None


def _build_public_token_response(tokens: TokenPair) -> dict[str, object]:
    """Return non-secret token metadata; access/refresh tokens stay in httpOnly cookies."""
    return {
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
    }


@router.get("/config", response_model=AuthConfigResponse)
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
            logger.error("[Auth] 获取配置失败: %s", _safe_auth_log_text(e))
        # ✅ 返回通用错误消息，不泄露实现细节
        raise HTTPException(status_code=500, detail="Failed to get auth config")


@router.get("/ip-info", response_model=IpInfoResponse)
async def get_ip_info_endpoint(
    request: Request,
    user_id: str = Depends(require_current_user),
):
    """
    获取调用方自身的客户端 IP 概要（需登录）。

    安全说明（S4）：
    - 需要认证（require_current_user），不再对匿名请求开放。
    - 仅返回调用方自己的 IP 及是否私有 IP；不回显任何原始转发头、
      内部 client_host 或地理位置信息，避免内部基础设施细节泄露。
    """
    detected_ip = get_client_ip(request, prefer_public=True)
    is_private = is_private_ip(detected_ip)
    return {
        "detected_ip": detected_ip,
        "is_private": is_private,
    }


@router.post("/register", response_model=AuthSessionResponse)
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """用户注册 - 返回 token 并设置 Cookie（兼容注册即登录）"""
    auth_service = AuthService(db)
    # Security: apply same IP-block gate used by /login to prevent blocked IPs from registering
    ip_address_reg = get_client_ip(request)
    if ip_address_reg and auth_service._check_ip_blocked(ip_address_reg):
        logger.warning("[Auth] Blocked IP attempted registration: %s", ip_address_reg)
        raise HTTPException(status_code=403, detail="Your IP address has been blocked")
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
            logger.warning(
                "Failed to initialize default personas for new user %s: %s",
                user_response.id,
                _safe_auth_log_text(e),
            )

        # ✅ 为新用户自动初始化 Starter 工作流模板（注册后立即可用）
        template_service = WorkflowTemplateService(db=db)
        created_templates = await template_service.ensure_starter_templates(user_response.id)
        logger.info(
            "[Auth] Starter templates initialized for new user %s: created=%s",
            user_response.id,
            len(created_templates),
        )

        # ✅ 检查用户是否有活跃的配置文件（新用户通常为 false）
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_response.id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        set_auth_cookies(response, result.tokens, request)

        # refresh_token 只设置到 httpOnly Cookie，不返回给浏览器 JS。
        return {
            "user": user_response.model_dump(),
            **_build_public_token_response(result.tokens),
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except RegistrationDisabledError:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    except EmailExistsError:
        raise HTTPException(status_code=400, detail="Email already exists")
    except PasswordMismatchError:
        raise HTTPException(status_code=400, detail="Passwords do not match")


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """用户登录 - 返回用户信息并设置 httpOnly Cookie。"""
    auth_service = AuthService(db)
    try:
        # 获取客户端 IP 和 User-Agent
        ip_address = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        
        result = auth_service.login(data, ip_address=ip_address, user_agent=user_agent)
        # ✅ A-4: 复用 auth_service.login 内已构造的 UserResponse，避免再次查询 user + IPLoginHistory
        user_response = result.user

        # ✅ 检查用户是否有活跃的配置文件（优化：减少前端初始化请求）
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_response.id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 统一安全 Cookie 策略（生产环境/HTTPS 强制 secure + strict）
        set_auth_cookies(response, result.tokens, request)

        # refresh_token 只设置到 httpOnly Cookie，不返回给浏览器 JS。
        return {
            "user": user_response.model_dump(),
            **_build_public_token_response(result.tokens),
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except AccountDisabledError as e:
        raise HTTPException(status_code=403, detail=e.message)
    except HTTPException:
        # 透传 auth_service 内部主动抛出的 HTTPException（如 429 频率限制、403 IP 封禁）
        raise
    except Exception as e:
        # ✅ A-1/C-8: 不向客户端泄漏内部异常细节，服务端日志只保留摘要。
        logger.error("[Auth] 登录失败 (email=%s): %s", data.email, _safe_auth_log_text(e))
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """用户登出 - 清除数据库中的 token 并撤销 refresh_token"""
    auth_service = AuthService(db)
    
    # ✅ 统一清除 Cookie
    clear_auth_cookies(response, request)
    
    access_token = _get_valid_request_token(
        request,
        cookie_name="access_token",
        is_valid_token=lambda token: extract_user_id_from_token(token) is not None,
    )
    if access_token:
        try:
            # 验证 access_token 并获取用户 ID
            payload = auth_service.validate_token(access_token)
            user_id = payload.sub

            # Wrap all three writes in one transaction so a partial failure rolls back cleanly
            user = auth_service.get_user_by_id(user_id)
            if user:
                user.access_token = None
                user.token_expires_at = None

            # 撤销该用户所有未过期的 refresh_token
            now = datetime.now(timezone.utc)
            db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now
            ).update({"revoked_at": now})

            # 记录登出到 IPLoginHistory
            ip_address = get_client_ip(request)
            user_agent = request.headers.get("User-Agent")
            ip_history = IPLoginHistory(
                user_id=user_id,
                ip_address=ip_address,
                action="logout",
                user_agent=user_agent
            )
            db.add(ip_history)
            db.commit()  # single commit for all three writes

            logger.info(f"[Logout] ✅ 用户 {user_id} 登出成功 (IP: {ip_address})")
        except (InvalidTokenError, TokenExpiredError):
            # Token already invalid or expired — revocation is a no-op; cookies are already cleared above
            logger.info("[Logout] Token invalid or expired during logout; cookies already cleared")
            db.rollback()
        except Exception as e:
            # Unexpected error: roll back any partial writes and log; cookies are already cleared
            logger.error("[Logout] Error revoking tokens: %s", _safe_auth_log_text(e))
            db.rollback()
    
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=AuthRefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """刷新访问令牌 - Header 优先，httpOnly refresh Cookie 兜底"""
    auth_service = AuthService(db)

    refresh_token = _get_valid_request_token(
        request,
        cookie_name="refresh_token",
        is_valid_token=auth_service.is_refresh_token_usable,
    )
    
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
            logger.warning("[Auth] 记录 token 刷新历史失败: %s", _safe_auth_log_text(e))

        # ✅ 检查用户是否有活跃的配置文件
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 统一安全 Cookie 策略（生产环境/HTTPS 强制 secure + strict）
        set_auth_cookies(response, tokens, request)

        # refresh_token 只设置到 httpOnly Cookie，不返回给浏览器 JS。
        return {
            **_build_public_token_response(tokens),
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """获取当前用户信息 - Header 优先，httpOnly access Cookie 兜底。

    core-3: 本端点全部为同步 DB 调用（无 await）。声明为同步 def 后，FastAPI 会在
    线程池中执行，避免在事件循环线程上阻塞（extract_user_id_from_token /
    auth_service.get_current_user / db.query 均为同步 SessionLocal 查询）。
    """
    auth_service = AuthService(db)

    access_token = _get_valid_request_token(
        request,
        cookie_name="access_token",
        is_valid_token=lambda token: extract_user_id_from_token(token) is not None,
    )

    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        if not extract_user_id_from_token(access_token):
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user_response = auth_service.get_current_user(access_token)

        # ✅ 检查用户是否有活跃的配置文件
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_response.id
        ).first()

        has_active_profile = (
            user_settings is not None and
            user_settings.active_profile_id is not None
        )

        # ✅ 返回用户信息 + 配置状态
        return {
            **user_response.model_dump(),
            "has_active_profile": has_active_profile  # ✅ 新增：配置状态
        }
    except (InvalidTokenError, TokenExpiredError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except HTTPException:
        raise
    except Exception as e:
        # ✅ 捕获其他异常（如数据库错误），避免返回 500 错误
        logger.error("[Auth] 获取当前用户失败: %s", _safe_auth_log_text(e))
        raise HTTPException(status_code=500, detail="Failed to fetch user information")


@router.post("/change-password", response_model=ChangePasswordResponse)
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
