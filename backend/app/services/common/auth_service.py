"""
认证服务 - 处理用户注册、登录、令牌管理等认证相关业务逻辑
"""
import hashlib
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ...models.db_models import User, RefreshToken, LoginAttempt, IPBlocklist, IPLoginHistory, generate_user_id
from ...core.config import settings
from ...core.password import hash_password, verify_password
from ...core.jwt_utils import (
    ExpiredSignatureError,
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    TokenPayload
)
from ...utils.log_sanitization import summarize_text_for_log
from .system_config_service import get_system_config

logger = logging.getLogger(__name__)
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"
_LOGIN_ATTEMPT_LOCK_STRIPE_COUNT = 256
_LOGIN_ATTEMPT_LOCK_STRIPES = tuple(
    threading.Lock() for _ in range(_LOGIN_ATTEMPT_LOCK_STRIPE_COUNT)
)


def _stable_lock_key(text_value: str) -> int:
    digest = hashlib.sha256(text_value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) & ((1 << 63) - 1)


def _login_attempt_lock_names(email: Optional[str], ip_address: str) -> tuple[str, ...]:
    names = {f"ip:{str(ip_address or 'unknown').strip() or 'unknown'}"}
    normalized_email = str(email or "").strip().lower()
    if normalized_email:
        names.add(f"email:{normalized_email}")
    return tuple(sorted(names))


@contextmanager
def _process_login_attempt_locks(email: Optional[str], ip_address: str):
    names = _login_attempt_lock_names(email, ip_address)
    stripe_indexes = sorted(
        {
            _stable_lock_key(f"process-login-attempt:{name}") % _LOGIN_ATTEMPT_LOCK_STRIPE_COUNT
            for name in names
        }
    )
    locks = [_LOGIN_ATTEMPT_LOCK_STRIPES[index] for index in stripe_indexes]
    for lock in locks:
        lock.acquire()
    try:
        yield
    finally:
        for lock in reversed(locks):
            lock.release()


# ============================================
# Pydantic 模型
# ============================================

class AuthConfigResponse(BaseModel):
    """认证配置响应"""
    allow_registration: bool


class RegisterRequest(BaseModel):
    """注册请求"""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=1024, pattern=r"^[^\x00-\x1F\x7F]+$")
    confirm_password: str = Field(min_length=8, max_length=1024, pattern=r"^[^\x00-\x1F\x7F]+$")
    name: Optional[str] = Field(default=None, max_length=128, pattern=r"^[^\x00-\x1F\x7F]*$")


class LoginRequest(BaseModel):
    """登录请求"""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=1024, pattern=r"^[^\x00-\x1F\x7F]+$")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=1024, pattern=r"^[^\x00-\x1F\x7F]+$")
    new_password: str = Field(min_length=8, max_length=1024, pattern=r"^[^\x00-\x1F\x7F]+$")
    confirm_password: str = Field(min_length=8, max_length=1024, pattern=r"^[^\x00-\x1F\x7F]+$")


class UserResponse(BaseModel):
    """用户响应（不包含敏感信息）"""
    id: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    email: str = Field(max_length=254, pattern=NO_CONTROL_CHARS_PATTERN)
    name: Optional[str] = Field(default=None, max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    status: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    is_admin: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenPair(BaseModel):
    """令牌对"""
    access_token: str
    refresh_token: str
    csrf_token: str
    token_type: str = "Bearer"
    expires_in: int  # access_token 过期时间（秒）


class AuthResponse(BaseModel):
    """认证响应"""
    user: UserResponse
    tokens: TokenPair


# ============================================
# 异常类
# ============================================

class AuthError(Exception):
    """认证错误基类"""
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class RegistrationDisabledError(AuthError):
    """注册功能已禁用"""
    def __init__(self):
        super().__init__("Registration is disabled", "REGISTRATION_DISABLED")


class EmailExistsError(AuthError):
    """邮箱已存在"""
    def __init__(self):
        super().__init__("Email already exists", "EMAIL_EXISTS")


class PasswordMismatchError(AuthError):
    """密码不匹配"""
    def __init__(self):
        super().__init__("Passwords do not match", "PASSWORD_MISMATCH")


class InvalidCredentialsError(AuthError):
    """无效凭证"""
    def __init__(self):
        super().__init__("Invalid email or password", "INVALID_CREDENTIALS")


class InvalidCurrentPasswordError(AuthError):
    """当前密码错误"""
    def __init__(self):
        super().__init__("Current password is incorrect", "INVALID_CURRENT_PASSWORD")


class SamePasswordError(AuthError):
    """新密码与旧密码相同"""
    def __init__(self):
        super().__init__("New password must be different from current password", "SAME_PASSWORD")


class AccountDisabledError(AuthError):
    """账户已禁用"""
    def __init__(self, reason: Optional[str] = None):
        msg = f"Account is disabled: {reason}" if reason else "Account is disabled"
        super().__init__(msg, "ACCOUNT_DISABLED")


class TokenExpiredError(AuthError):
    """令牌已过期"""
    def __init__(self):
        super().__init__("Token expired", "TOKEN_EXPIRED")


class InvalidTokenError(AuthError):
    """无效令牌"""
    def __init__(self):
        super().__init__("Invalid token", "INVALID_TOKEN")


# ============================================
# AuthService 类
# ============================================

class AuthService:
    """认证服务类"""

    def __init__(self, db: Session):
        self.db = db

    def is_registration_enabled(self) -> bool:
        """检查注册功能是否启用（从数据库读取）"""
        try:
            config = get_system_config(self.db)
            result = config.allow_registration
            logger.info(f"[AuthService] 从数据库读取 allow_registration: {result}")
            return result
        except Exception as e:
            logger.error(f"[AuthService] 读取系统配置失败: {e}", exc_info=True)
            # 如果读取失败，默认返回 False（不允许注册）
            return False

    def get_config(self) -> AuthConfigResponse:
        """获取认证配置"""
        allow_registration = self.is_registration_enabled()
        logger.info(f"[AuthService] 返回认证配置: allow_registration={allow_registration}")
        return AuthConfigResponse(allow_registration=allow_registration)

    def _check_ip_blocked(self, ip_address: str) -> bool:
        """检查 IP 是否被封禁"""
        blocked = self.db.query(IPBlocklist).filter(
            IPBlocklist.ip_address == ip_address
        ).first()
        
        if not blocked:
            return False
        
        # 检查是否已过期
        if blocked.expires_at and blocked.expires_at < datetime.now(timezone.utc):
            # 过期了，删除记录
            self.db.delete(blocked)
            self.db.commit()
            return False
        
        return True

    def _record_login_attempt(self, email: Optional[str], ip_address: str, success: bool, user_agent: Optional[str] = None) -> None:
        """
        记录登录尝试到 LoginAttempt 表（用于防暴力破解）
        
        Args:
            email: 登录邮箱
            ip_address: IP 地址
            success: 是否成功
            user_agent: 用户代理
        """
        try:
            attempt = LoginAttempt(
                email=email,
                ip_address=ip_address,
                success=success,
                user_agent=user_agent
            )
            self.db.add(attempt)
            self.db.commit()
        except Exception as e:
            logger.error(f"[AuthService] 记录登录尝试失败: {e}", exc_info=True)
            self.db.rollback()
    
    def _record_ip_login_history(self, user_id: str, ip_address: str, action: str, user_agent: Optional[str] = None, commit: bool = True) -> None:
        """
        记录 IP 登录历史到 IPLoginHistory 表（用于历史追踪和安全分析）

        Args:
            user_id: 用户 ID
            ip_address: IP 地址
            action: 操作类型（login, logout, failed_login, token_refresh）
            user_agent: 用户代理
            commit: 是否立即提交（A-3: 登录成功路径传 False 以合并到外层事务一次提交）
        """
        try:
            ip_history = IPLoginHistory(
                user_id=user_id,
                ip_address=ip_address,
                action=action,
                user_agent=user_agent
            )
            self.db.add(ip_history)
            if commit:
                self.db.commit()
        except Exception as e:
            logger.warning(f"[AuthService] 记录 IP 登录历史失败: {e}")
            if commit:
                self.db.rollback()

    def _check_login_attempts(self, email: Optional[str], ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        检查登录尝试次数是否超过限制
        
        Returns:
            (is_allowed, error_message)
        """
        # 获取配置
        config = get_system_config(self.db)
        max_attempts = config.max_login_attempts
        max_ip_attempts = config.max_login_attempts_per_ip
        lockout_duration = config.login_lockout_duration
        
        # 计算时间窗口（最近 lockout_duration 秒）
        time_window = datetime.now(timezone.utc) - timedelta(seconds=lockout_duration)
        
        # 检查 IP 级别的失败次数
        ip_failed_count = self.db.query(func.count(LoginAttempt.id)).filter(
            and_(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success == False,
                LoginAttempt.created_at >= time_window
            )
        ).scalar() or 0
        
        if ip_failed_count >= max_ip_attempts:
            return False, f"Too many login attempts from this IP. Please try again later."
        
        # 检查邮箱级别的失败次数
        if email:
            email_failed_count = self.db.query(func.count(LoginAttempt.id)).filter(
                and_(
                    LoginAttempt.email == email,
                    LoginAttempt.success == False,
                    LoginAttempt.created_at >= time_window
                )
            ).scalar() or 0
            
            if email_failed_count >= max_attempts:
                return False, f"Too many failed login attempts for this email. Please try again later."
        
        return True, None

    def _acquire_login_attempt_db_locks(self, email: Optional[str], ip_address: str) -> None:
        dialect = getattr(getattr(self.db, "bind", None), "dialect", None)
        if dialect is None or getattr(dialect, "name", "") != "postgresql":
            return
        for name in _login_attempt_lock_names(email, ip_address):
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:k)"),
                {"k": _stable_lock_key(f"login-attempt:{name}")},
            )

    def _assert_login_attempt_allowed_locked(
        self,
        email: Optional[str],
        ip_address: str,
    ) -> None:
        from fastapi import HTTPException

        with _process_login_attempt_locks(email, ip_address):
            self._acquire_login_attempt_db_locks(email, ip_address)
            is_allowed, error_msg = self._check_login_attempts(email, ip_address)
            if not is_allowed:
                raise HTTPException(status_code=429, detail=error_msg)

    def _record_failed_login_attempt_or_raise(
        self,
        email: Optional[str],
        ip_address: str,
        user_agent: Optional[str] = None,
    ) -> None:
        from fastapi import HTTPException

        with _process_login_attempt_locks(email, ip_address):
            self._acquire_login_attempt_db_locks(email, ip_address)
            is_allowed, error_msg = self._check_login_attempts(email, ip_address)
            if not is_allowed:
                raise HTTPException(status_code=429, detail=error_msg)
            self._record_login_attempt(email, ip_address, False, user_agent)

    # W02R-002: stable application-defined key for the first-admin advisory lock.
    _FIRST_ADMIN_LOCK_KEY = 7723391011

    def _acquire_first_admin_bootstrap_lock(self) -> None:
        """Serialize the first-admin bootstrap decision (CWE-362).

        On PostgreSQL, take a transaction-scoped advisory lock held until commit,
        so concurrent registrations on an empty instance serialize through the
        count->insert->commit critical section and only the first becomes admin.
        SQLite serializes writers already, so no lock is issued there.
        """
        dialect = getattr(getattr(self.db, "bind", None), "dialect", None)
        if dialect is not None and getattr(dialect, "name", "") == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:k)"),
                {"k": self._FIRST_ADMIN_LOCK_KEY},
            )

    def register(self, data: RegisterRequest) -> AuthResponse:
        """
        用户注册
        
        Raises:
            RegistrationDisabledError: 注册功能已禁用
            EmailExistsError: 邮箱已存在
            PasswordMismatchError: 密码不匹配
        """
        # 检查注册开关
        if not self.is_registration_enabled():
            raise RegistrationDisabledError()

        # 检查密码匹配
        if data.password != data.confirm_password:
            raise PasswordMismatchError()

        # 检查邮箱是否已存在
        existing_user = self.db.query(User).filter(User.email == data.email).first()
        if existing_user:
            raise EmailExistsError()

        # W02R-002: serialize the first-admin bootstrap decision so two concurrent
        # registrations on an empty instance cannot both be granted admin (CWE-362).
        self._acquire_first_admin_bootstrap_lock()

        # 创建用户（首个注册用户默认授予管理员）
        user_count = self.db.query(func.count(User.id)).scalar() or 0
        is_first_user = user_count == 0
        user = User(
            id=generate_user_id(),
            email=data.email,
            password_hash=hash_password(data.password),
            name=data.name or data.email.split('@')[0],
            status='active',
            is_admin=is_first_user
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # 生成令牌
        tokens = self._create_tokens(user.id)

        # ✅ 将 access_token 存储到用户表
        user.access_token = tokens.access_token
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self.db.commit()

        # 统一从 token 中提取 user_id 获取用户信息
        user_response = self.get_current_user(tokens.access_token)

        return AuthResponse(
            user=user_response,
            tokens=tokens
        )


    def login(self, data: LoginRequest, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> AuthResponse:
        """
        用户登录（带防暴力破解保护）
        
        Args:
            data: 登录请求数据
            ip_address: 客户端 IP 地址
            user_agent: 用户代理字符串
        
        Raises:
            InvalidCredentialsError: 无效凭证
            AccountDisabledError: 账户已禁用
            HTTPException: 登录尝试次数过多
        """
        from fastapi import HTTPException
        
        # 检查 IP 是否被封禁
        if ip_address and self._check_ip_blocked(ip_address):
            logger.warning(f"[AuthService] 封禁的 IP 尝试登录: {ip_address}")
            raise HTTPException(status_code=403, detail="Your IP address has been blocked")
        
        client_ip = ip_address or "unknown"

        # 检查登录尝试次数。This first check avoids password work for already
        # locked identities; failed attempts re-check and reserve under the same
        # identity lock before recording the failure.
        try:
            self._assert_login_attempt_allowed_locked(data.email, client_ip)
        except HTTPException as exc:
            logger.warning(
                "[AuthService] 登录尝试次数过多: %s, ip=%s",
                summarize_text_for_log(data.email, label="email"),
                ip_address,
            )
            raise exc
        
        # 查找用户
        user = self.db.query(User).filter(User.email == data.email).first()
        
        # 验证密码
        password_valid = False
        if user:
            password_valid = verify_password(data.password, user.password_hash)
        
        # 记录登录尝试（无论成功或失败）- 用于防暴力破解
        if password_valid:
            self._record_login_attempt(data.email, client_ip, True, user_agent)
        else:
            self._record_failed_login_attempt_or_raise(data.email, client_ip, user_agent)
        
        if not user or not password_valid:
            # 登录失败，记录到 IPLoginHistory（如果用户存在）
            if user:
                self._record_ip_login_history(user.id, client_ip, "failed_login", user_agent)
            raise InvalidCredentialsError()

        # 检查账户状态
        if user.status != 'active':
            raise AccountDisabledError(user.status_reason)

        # 生成令牌（_create_tokens 内部会 commit 一次：撤销旧 token + 写入新 RefreshToken）
        tokens = self._create_tokens(user.id)

        # ✅ A-3: 合并 user.access_token 更新 + ip_login_history 写入到同一次 commit
        try:
            user.access_token = tokens.access_token
            user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
            # 登录成功 IP 历史用 commit=False，与 user 字段更新合并提交
            self._record_ip_login_history(user.id, ip_address or "unknown", "login", user_agent, commit=False)
            self.db.commit()
        except Exception as commit_err:
            self.db.rollback()
            logger.error(f"[AuthService] 登录提交事务失败: {commit_err}", exc_info=True)
            raise

        logger.info(
            "[AuthService] ✅ 用户登录成功: %s (IP: %s)",
            summarize_text_for_log(user.email, label="email"),
            ip_address,
        )

        # ✅ A-4: 直接复用已查到的 user 实例构造 UserResponse，不再通过 token 反查
        # last_login_at 从本次 ip_history 即可推断（now()），避免再查 IPLoginHistory
        now_dt = datetime.now(timezone.utc)
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            is_admin=bool(user.is_admin),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=now_dt,
        )

        return AuthResponse(
            user=user_response,
            tokens=tokens
        )

    def validate_token(self, token: str) -> TokenPayload:
        """
        验证令牌

        Raises:
            InvalidTokenError: 无效令牌
            TokenExpiredError: 令牌已过期
        """
        # ✅ A-8: 显式区分 JWT 异常类别，保留诊断上下文（避免吞掉所有 Exception）
        try:
            payload = decode_token(token)
        except ExpiredSignatureError:
            logger.warning("[AuthService] Token 已过期 (JWT ExpiredSignatureError)")
            raise TokenExpiredError()
        except JWTError as e:
            logger.warning(f"[AuthService] Token 无效: {type(e).__name__}: {e}")
            raise InvalidTokenError()
        except TokenExpiredError:
            raise
        except Exception as e:
            # 非预期异常类型——记录类型以便定位，仍按无效令牌处理
            logger.warning(f"[AuthService] Token 解码异常: {type(e).__name__}: {e}")
            raise InvalidTokenError()

        # 内部 exp 检查（兼容测试或自定义 payload 场景，
        # 这里仍需基于 payload.exp 判定，以与 is_token_expired 行为一致）
        if payload.exp < int(datetime.now(timezone.utc).timestamp()):
            raise TokenExpiredError()
        return payload

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据 ID 获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_current_user(self, token: str) -> UserResponse:
        """
        获取当前用户
        
        Raises:
            InvalidTokenError: 无效令牌
            TokenExpiredError: 令牌已过期
        """
        payload = self.validate_token(token)
        user = self.get_user_by_id(payload.sub)
        if not user:
            raise InvalidTokenError()

        last_login_record = self.db.query(IPLoginHistory).filter(
            IPLoginHistory.user_id == user.id,
            IPLoginHistory.action == "login"
        ).order_by(IPLoginHistory.created_at.desc()).first()

        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status,
            is_admin=bool(user.is_admin),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=last_login_record.created_at if last_login_record else None
        )

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        confirm_password: str
    ) -> None:
        """
        修改用户密码

        Raises:
            InvalidTokenError: 用户不存在
            PasswordMismatchError: 新密码与确认密码不一致
            InvalidCurrentPasswordError: 当前密码错误
            SamePasswordError: 新旧密码相同
        """
        user = self.get_user_by_id(user_id)
        if not user:
            raise InvalidTokenError()

        if new_password != confirm_password:
            raise PasswordMismatchError()

        if not verify_password(current_password, user.password_hash):
            raise InvalidCurrentPasswordError()

        # 避免“修改后和旧密码一致”的无效操作
        if verify_password(new_password, user.password_hash):
            raise SamePasswordError()

        user.password_hash = hash_password(new_password)
        self.db.commit()


    def _get_usable_refresh_token_row(
        self,
        refresh_token: str,
        *,
        for_update: bool = False,
    ) -> tuple[TokenPayload, RefreshToken]:
        payload = self.validate_token(refresh_token)
        if payload.type != 'refresh':
            raise InvalidTokenError()

        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        query = self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash)
        if for_update:
            # W02R-001: lock the row so concurrent refreshes of the same token serialize
            # (single-use rotation). On backends without row locking this is a no-op.
            query = query.with_for_update()

        db_token = query.first()
        if db_token is None or db_token.revoked_at is not None:
            raise InvalidTokenError()

        expires_at = db_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise TokenExpiredError()

        # W02R-001: 绝不为非活跃账户铸发新的会话凭据（与 access-token 校验路径一致）。
        user = self.get_user_by_id(payload.sub)
        if user is None or getattr(user, "status", None) != "active":
            raise InvalidTokenError()

        return payload, db_token

    def is_refresh_token_usable(self, refresh_token: str) -> bool:
        try:
            self._get_usable_refresh_token_row(refresh_token)
            return True
        except (InvalidTokenError, TokenExpiredError):
            return False

    def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """
        刷新令牌
        
        刷新时会：
        1. 撤销旧的 refresh_token
        2. 清理该用户的过期/旧 token
        3. 生成新的 token 对
        
        Raises:
            InvalidTokenError: 无效令牌
            TokenExpiredError: 令牌已过期
        """
        # W02R-001: 失败闭合。仅当 refresh JWT 对应一个“已存储且未撤销”的 DB 行时才接受。
        # 缺失行（已轮换/已清理）或已撤销行都不得铸发新令牌，否则服务端撤销无法生效。
        payload, db_token = self._get_usable_refresh_token_row(refresh_token, for_update=True)

        # ✅ 撤销当前使用的 refresh_token（单次使用 + 轮换）
        db_token.revoked_at = datetime.now(timezone.utc)
        self.db.commit()

        # 生成新令牌（_create_tokens 会自动清理旧 token）
        return self._create_tokens(payload.sub)

    def invalidate_refresh_token(self, refresh_token: str) -> None:
        """撤销刷新令牌"""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        if db_token:
            db_token.revoked_at = datetime.now(timezone.utc)
            self.db.commit()

    def _create_tokens(self, user_id: str) -> TokenPair:
        """
        创建令牌对
        
        同时清理该用户的旧 token：
        - 撤销所有未过期的旧 refresh_token（防止重复登录）
        - 删除已过期或已撤销超过 7 天的旧记录（防止数据库无限增长）
        """
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        csrf_token = generate_csrf_token()

        now = datetime.now(timezone.utc)
        
        # 1. 撤销该用户所有未过期的旧 refresh_token（防止重复登录时的唯一约束冲突）
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now
        ).update({"revoked_at": now})

        # 2. 清理已过期或已撤销超过 7 天的旧记录（防止数据库无限增长）
        cleanup_threshold = now - timedelta(days=7)
        deleted_count = self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            # 已过期 或 已撤销超过 7 天
            (
                (RefreshToken.expires_at < now) |
                (
                    (RefreshToken.revoked_at.isnot(None)) &
                    (RefreshToken.revoked_at < cleanup_threshold)
                )
            )
        ).delete()
        
        if deleted_count > 0:
            logger.debug(f"[AuthService] 清理了用户 {user_id} 的 {deleted_count} 个旧 refresh_token")

        # 3. 存储新的 refresh_token 哈希（用于撤销）
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        db_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + 
                       timedelta(days=settings.jwt_refresh_token_expire_days)
        )
        self.db.add(db_token)
        self.db.commit()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )
