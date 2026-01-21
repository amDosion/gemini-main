"""
认证服务 - 处理用户注册、登录、令牌管理等认证相关业务逻辑
"""
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from pydantic import BaseModel, EmailStr, Field

from ...models.db_models import User, RefreshToken, LoginAttempt, IPBlocklist, IPLoginHistory, generate_user_id
from ...core.config import settings
from ...core.password import hash_password, verify_password
from ...core.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    TokenPayload
)
from .system_config_service import get_system_config, get_client_ip

logger = logging.getLogger(__name__)


# ============================================
# Pydantic 模型
# ============================================

class AuthConfigResponse(BaseModel):
    """认证配置响应"""
    allow_registration: bool


class RegisterRequest(BaseModel):
    """注册请求"""
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    """登录请求"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """用户响应（不包含敏感信息）"""
    id: str
    email: str
    name: Optional[str]
    status: str

    class Config:
        from_attributes = True


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
    
    def _record_ip_login_history(self, user_id: str, ip_address: str, action: str, user_agent: Optional[str] = None) -> None:
        """
        记录 IP 登录历史到 IPLoginHistory 表（用于历史追踪和安全分析）
        
        Args:
            user_id: 用户 ID
            ip_address: IP 地址
            action: 操作类型（login, logout, failed_login, token_refresh）
            user_agent: 用户代理
        """
        try:
            ip_history = IPLoginHistory(
                user_id=user_id,
                ip_address=ip_address,
                action=action,
                user_agent=user_agent
            )
            self.db.add(ip_history)
            self.db.commit()
        except Exception as e:
            logger.warning(f"[AuthService] 记录 IP 登录历史失败: {e}")
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

        # 创建用户
        user = User(
            id=generate_user_id(),
            email=data.email,
            password_hash=hash_password(data.password),
            name=data.name or data.email.split('@')[0],
            status='active'
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

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                status=user.status
            ),
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
        
        # 检查登录尝试次数
        is_allowed, error_msg = self._check_login_attempts(data.email, ip_address or "unknown")
        if not is_allowed:
            logger.warning(f"[AuthService] 登录尝试次数过多: email={data.email}, ip={ip_address}")
            raise HTTPException(status_code=429, detail=error_msg)
        
        # 查找用户
        user = self.db.query(User).filter(User.email == data.email).first()
        
        # 验证密码
        password_valid = False
        if user:
            password_valid = verify_password(data.password, user.password_hash)
        
        # 记录登录尝试（无论成功或失败）- 用于防暴力破解
        self._record_login_attempt(data.email, ip_address or "unknown", password_valid, user_agent)
        
        if not user or not password_valid:
            # 登录失败，记录到 IPLoginHistory（如果用户存在）
            if user:
                self._record_ip_login_history(user.id, ip_address or "unknown", "failed_login", user_agent)
            raise InvalidCredentialsError()

        # 检查账户状态
        if user.status != 'active':
            raise AccountDisabledError(user.status_reason)

        # 生成令牌
        tokens = self._create_tokens(user.id)

        # ✅ 将 access_token 存储到用户表
        user.access_token = tokens.access_token
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self.db.commit()
        
        # ✅ 登录成功后，记录到 IPLoginHistory（用于历史追踪）
        self._record_ip_login_history(user.id, ip_address or "unknown", "login", user_agent)

        logger.info(f"[AuthService] ✅ 用户登录成功: {user.email} (IP: {ip_address})")

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                status=user.status
            ),
            tokens=tokens
        )

    def validate_token(self, token: str) -> TokenPayload:
        """
        验证令牌
        
        Raises:
            InvalidTokenError: 无效令牌
            TokenExpiredError: 令牌已过期
        """
        try:
            payload = decode_token(token)
            # 检查是否过期
            if payload.exp < int(datetime.now(timezone.utc).timestamp()):
                raise TokenExpiredError()
            return payload
        except Exception:
            raise InvalidTokenError()

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
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status
        )


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
        # 验证 refresh_token
        payload = self.validate_token(refresh_token)
        if payload.type != 'refresh':
            raise InvalidTokenError()

        # 检查令牌是否被撤销
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        if db_token and db_token.revoked_at:
            raise InvalidTokenError()
        
        # ✅ 撤销当前使用的 refresh_token
        if db_token:
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
