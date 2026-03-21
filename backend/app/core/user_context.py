"""
用户上下文管理器 - 从请求中提取和管理用户 ID

功能：
1. 从 JWT token 中提取 user_id
2. 提供全局访问当前用户 ID
3. 处理未认证用户
"""

from fastapi import Request, HTTPException, status
from datetime import datetime, timezone
from typing import Optional
from ..core.jwt_utils import decode_token, TokenPayload
from ..core.database import SessionLocal
from ..models.db_models import User
from jose import JWTError
import logging


class UserContextError(Exception):
    """用户上下文错误"""
    pass


logger = logging.getLogger(__name__)


def _is_access_token_active_in_db(user_id: str, access_token: str) -> bool:
    """
    校验 access token 是否仍为该用户当前有效会话。

    判定规则：
    1. 用户存在且状态为 active
    2. 用户表中保存的 access_token 与请求 token 完全一致
    3. token_expires_at 未过期
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if user.status != "active":
            return False

        if not user.access_token or user.access_token != access_token:
            return False

        if not user.token_expires_at:
            return False

        expires_at = user.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= datetime.now(timezone.utc):
            return False

        return True
    except Exception as e:
        # 鉴权失败默认拒绝（fail closed）
        logger.error(f"[UserContext] 数据库校验 access_token 失败: {e}", exc_info=True)
        return False
    finally:
        db.close()


def get_current_user_id(request: Request) -> Optional[str]:
    """
    从请求中获取当前用户 ID（不强制要求认证）
    
    优先级：
    1. Authorization header（Bearer token 认证）- ✅ 优先使用
    2. Cookie 中的 access_token（向后兼容）
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        用户 ID 或 None（如果未认证）
    """
    token = None
    token_source = None
    
    try:
        # ✅ 1. 优先从 Authorization header 获取 token
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                token_source = "Authorization header"
        
        # 2. 如果 Authorization header 中没有，尝试从 Cookie 获取（向后兼容）
        if not token:
            token = request.cookies.get("access_token")
            if token:
                token_source = "Cookie (access_token)"
        
        # 3. 如果都没有 token，返回 None
        if not token:
            logger.debug(f"[UserContext] 未找到 token (路径: {request.url.path})")
            return None
        
        # 解码 token
        payload: TokenPayload = decode_token(token)
        
        # 验证 token 类型
        if payload.type != "access":
            logger.warning(f"[UserContext] Token 类型错误: {payload.type} (路径: {request.url.path})")
            return None

        # ✅ 核心：校验 token 是否仍为用户当前有效会话（logout 后立即失效）
        if not _is_access_token_active_in_db(payload.sub, token):
            logger.info(
                "[UserContext] access_token 已失效或已撤销 (来源: %s, 路径: %s)",
                token_source,
                request.url.path,
            )
            return None
        
        user_id = payload.sub
        logger.debug(f"[UserContext] 提取 user_id: {user_id} (来源: {token_source}, 路径: {request.url.path})")
        
        return user_id
        
    except JWTError as e:
        logger.warning(f"[UserContext] JWT 解码失败 (来源: {token_source}, 路径: {request.url.path}): {e}")
        return None
    except Exception as e:
        logger.error(f"[UserContext] 提取 user_id 时发生错误 (路径: {request.url.path}): {e}", exc_info=True)
        return None


def require_user_id(request: Request) -> str:
    """
    要求用户已认证，否则抛出异常
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        用户 ID
        
    Raises:
        HTTPException: 401 Unauthorized（未认证或 token 无效）
    """
    user_id = get_current_user_id(request)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_id


def extract_user_id_from_token(token: str) -> Optional[str]:
    """
    从 token 字符串中提取用户 ID
    
    Args:
        token: JWT token 字符串
        
    Returns:
        用户 ID 或 None（如果 token 无效）
    """
    try:
        payload: TokenPayload = decode_token(token)
        if payload.type == "access" and _is_access_token_active_in_db(payload.sub, token):
            return payload.sub
        return None
    except JWTError:
        return None
    except Exception:
        return None
