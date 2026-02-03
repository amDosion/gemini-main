"""
用户上下文管理器 - 从请求中提取和管理用户 ID

功能：
1. 从 JWT token 中提取 user_id
2. 提供全局访问当前用户 ID
3. 处理未认证用户
"""

from fastapi import Request, HTTPException, status
from typing import Optional
from ..core.jwt_utils import decode_token, TokenPayload
from jose import JWTError


class UserContextError(Exception):
    """用户上下文错误"""
    pass


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
    import logging
    logger = logging.getLogger(__name__)
    
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
        if payload.type == "access":
            return payload.sub
        return None
    except JWTError:
        return None
    except Exception:
        return None
