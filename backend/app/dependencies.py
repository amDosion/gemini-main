"""
FastAPI 依赖注入

提供服务实例的依赖注入
"""

from typing import Optional
from fastapi import Header, HTTPException

from .services.interactions_service import InteractionsService
from .utils.rate_limiter import RateLimiter
from .utils.research_cache import ResearchCache
from .utils.prompt_security_validator import PromptSecurityValidator


def get_interactions_service(authorization: str = Header(...)) -> InteractionsService:
    """
    获取 InteractionsService 实例
    
    Args:
        authorization: Authorization Header (Bearer Token)
        
    Returns:
        InteractionsService 实例
        
    Raises:
        HTTPException: 认证失败
    """
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    api_key = authorization.split(' ')[1]
    return InteractionsService(api_key)


def get_rate_limiter() -> RateLimiter:
    """获取 RateLimiter 实例"""
    return RateLimiter()


def get_cache() -> ResearchCache:
    """获取 ResearchCache 实例"""
    return ResearchCache()


def get_validator() -> PromptSecurityValidator:
    """获取 PromptSecurityValidator 实例"""
    return PromptSecurityValidator()
