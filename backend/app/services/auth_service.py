"""
认证服务 - 处理用户注册、登录、令牌管理等认证相关业务逻辑
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from ..models.db_models import User, RefreshToken, generate_user_id
from ..core.config import settings
from ..core.password import hash_password, verify_password
from ..core.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    TokenPayload
)


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
        """检查注册功能是否启用"""
        return settings.allow_registration

    def get_config(self) -> AuthConfigResponse:
        """获取认证配置"""
        return AuthConfigResponse(allow_registration=self.is_registration_enabled())

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

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                status=user.status
            ),
            tokens=tokens
        )


    def login(self, data: LoginRequest) -> AuthResponse:
        """
        用户登录
        
        Raises:
            InvalidCredentialsError: 无效凭证
            AccountDisabledError: 账户已禁用
        """
        # 查找用户
        user = self.db.query(User).filter(User.email == data.email).first()
        if not user:
            raise InvalidCredentialsError()

        # 验证密码
        if not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError()

        # 检查账户状态
        if user.status != 'active':
            raise AccountDisabledError(user.status_reason)

        # 生成令牌
        tokens = self._create_tokens(user.id)

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

        # 生成新令牌
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
        """创建令牌对"""
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        csrf_token = generate_csrf_token()

        # 存储 refresh_token 哈希（用于撤销）
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        db_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + 
                       __import__('datetime').timedelta(days=settings.jwt_refresh_token_expire_days)
        )
        self.db.add(db_token)
        self.db.commit()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )
