"""
Provider Templates API 路由

职责：
- 提供 Provider Templates 配置 API
- 支持前端动态加载 Provider 配置

端点：
- GET /api/providers/templates - 获取所有 Provider Templates

创建时间: 2026-01-05
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

# 支持多种导入方式
try:
    from ...services.common.provider_config import ProviderConfig
except ImportError:
    from app.services.common.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/templates")
async def get_templates() -> List[Dict[str, Any]]:
    """
    获取所有 Provider Templates 配置
    
    Returns:
        List of provider template configurations
    
    Example Response:
        [
            {
                "id": "google",
                "name": "Google Gemini",
                "protocol": "google",
                "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
                "defaultModel": "gemini-2.0-flash-exp",
                "description": "Native Google SDK. Supports Vision, Search & Thinking.",
                "isCustom": false,
                "icon": "gemini"
            },
            ...
        ]
    """
    try:
        logger.info("[Provider Templates] Loading provider templates")
        
        templates = ProviderConfig.get_provider_templates()
        
        logger.info(f"[Provider Templates] Loaded {len(templates)} templates")
        
        return templates
    
    except Exception as e:
        logger.error(f"[Provider Templates] Error loading templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load provider templates: {str(e)}"
        )
