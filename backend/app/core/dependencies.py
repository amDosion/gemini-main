"""
FastAPI 依赖注入

提供服务实例的依赖注入和统一认证依赖
"""

from typing import Optional
from fastapi import Header, HTTPException, Request, Depends
from ..utils.rate_limiter import RateLimiter
from ..utils.research_cache import ResearchCache
from ..utils.prompt_security_validator import PromptSecurityValidator
from .user_context import get_current_user_id, require_user_id
from ..services.common.cache_service import get_cache_service


# ==================== 统一认证依赖 ====================

def require_current_user(request: Request) -> str:
    """
    统一认证依赖函数 - 要求用户已认证
    
    用于 FastAPI Depends，自动从请求中提取 user_id。
    如果未认证，抛出 401 异常。
    
    使用方式：
        @router.post("/endpoint")
        async def endpoint(
            user_id: str = Depends(require_current_user),
            ...
        ):
            # user_id 已自动注入
            pass
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        用户 ID
        
    Raises:
        HTTPException: 401 Unauthorized（未认证或 token 无效）
    """
    return require_user_id(request)


def get_current_user_optional(request: Request) -> Optional[str]:
    """
    可选认证依赖函数 - 不强制要求认证
    
    用于 FastAPI Depends，自动从请求中提取 user_id。
    如果未认证，返回 None（不抛出异常）。
    
    使用方式：
        @router.post("/endpoint")
        async def endpoint(
            user_id: Optional[str] = Depends(get_current_user_optional),
            ...
        ):
            if user_id:
                # 已认证用户
                pass
            else:
                # 未认证用户
                pass
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        用户 ID 或 None（如果未认证）
    """
    return get_current_user_id(request)


# ==================== 其他依赖 ====================

def get_rate_limiter() -> RateLimiter:
    """获取 RateLimiter 实例"""
    return RateLimiter()


def get_research_cache() -> ResearchCache:
    """获取 ResearchCache 实例"""
    return ResearchCache()


def get_validator() -> PromptSecurityValidator:
    """获取 PromptSecurityValidator 实例"""
    return PromptSecurityValidator()


# ==================== 缓存服务依赖 ====================

async def get_cache():
    """
    获取 Redis 缓存服务实例（依赖注入）
    
    使用方式：
        @router.get("/endpoint")
        async def endpoint(
            cache: CacheService = Depends(get_cache),
            ...
        ):
            # 使用缓存
            data = await cache.get("key")
    """
    return await get_cache_service()
