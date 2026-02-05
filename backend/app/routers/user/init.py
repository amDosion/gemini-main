"""
统一初始化 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
import logging

from ...core.database import SessionLocal, get_db
from ...core.dependencies import require_current_user
from ...services.common.init_service import get_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["init"])


@router.get("/init/critical")
async def get_critical_init_data(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取关键初始化数据（阻塞渲染）
    
    关键数据包括：
    - profiles: 提供商配置列表（Header 需要显示提供商选择器）
    - activeProfileId: 当前激活的提供商ID
    - activeProfile: 当前激活的提供商配置（包含 providerId, apiKey 等）
    - cachedModels: 缓存的模型列表（从 activeProfile.savedModels 获取，Header 需要显示模型选择器）
    - dashscopeKey: 通义千问的 API Key（如果使用通义千问）
    
    注意：这些数据是 chat 模式正常工作的前提，必须在首次渲染前加载
    """
    from ...services.common.init_service import _query_profiles
    
    try:
        profiles_result = await _query_profiles(user_id, db)

        # ✅ 从 active_profile 中提取 cachedModels（saved_models）
        # 注意：此时数据还是 snake_case，还没有经过 Middleware 转换
        cached_models = None
        if profiles_result.get("active_profile") and profiles_result["active_profile"].get("saved_models"):
            cached_models = profiles_result["active_profile"]["saved_models"]

        return {
            "profiles": profiles_result.get("profiles", []),
            "active_profile_id": profiles_result.get("active_profile_id"),
            "active_profile": profiles_result.get("active_profile"),
            "cached_models": cached_models,
            "dashscope_key": profiles_result.get("dashscope_key", "")
        }
    except Exception as e:
        logger.error(f"Failed to load critical initialization data for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to load critical initialization data. Please try again later."
        )


@router.get("/init/sessions/more")
async def get_more_sessions(
    offset: int = 0,
    limit: int = 20,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    滚动加载更多会话元数据（惰性加载）
    
    用于 Sidebar 滚动到底部时加载更多会话
    只返回会话元数据，messages 为空数组
    """
    from ...services.common.init_service import _query_sessions_metadata_only
    from fastapi import Query
    
    try:
        result = await _query_sessions_metadata_only(user_id, db, limit=limit, offset=offset)
        return {
            "sessions": result.get("sessions", []),
            "total": result.get("total", 0),
            "hasMore": result.get("hasMore", False)
        }
    except Exception as e:
        logger.error(f"Failed to load more sessions for user {user_id}: {e}", exc_info=True)
        return {
            "sessions": [],
            "total": 0,
            "hasMore": False
        }


@router.get("/init/non-critical")
async def get_non_critical_init_data(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取非关键初始化数据（后台加载）
    
    非关键数据包括：
    - sessions: 会话列表（最近的 20 个）
      * 第一个会话包含完整消息（不能分页，用于右侧 ChatView）
      * 其他会话 messages 为空数组（按需加载）
    - sessionsTotal: 总会话数量（用于分页）
    - sessionsHasMore: 是否还有更多会话（用于滚动加载）
    - personas: 角色列表
    - storageConfigs: 云存储配置
    - imagenConfig: Imagen 配置
    """
    from ...services.common.init_service import (
        _query_sessions_with_first_messages,  # ✅ 返回会话列表 + 第一个会话的完整消息
        _query_personas, 
        _query_storage_configs,
        _query_vertex_ai_config
    )
    import asyncio
    
    try:
        # 并行查询非关键数据
        sessions_result, personas_result, storage_result, vertex_ai_result = await asyncio.gather(
            _query_sessions_with_first_messages(user_id, db, limit=20),  # ✅ 第一个会话包含完整消息
            _query_personas(user_id, db),
            _query_storage_configs(user_id, db),
            _query_vertex_ai_config(user_id, db),
            return_exceptions=True
        )
        
        return {
            "sessions": sessions_result.get("sessions", []) if isinstance(sessions_result, dict) else [],
            "sessionsTotal": sessions_result.get("total", 0) if isinstance(sessions_result, dict) else 0,
            "sessionsHasMore": sessions_result.get("hasMore", False) if isinstance(sessions_result, dict) else False,
            "personas": personas_result.get("personas", []) if isinstance(personas_result, dict) else [],
            "storageConfigs": storage_result.get("storage_configs", []) if isinstance(storage_result, dict) else [],
            "activeStorageId": storage_result.get("active_storage_id") if isinstance(storage_result, dict) else None,
            "imagenConfig": vertex_ai_result.get("imagenConfig") if isinstance(vertex_ai_result, dict) else None
        }
    except Exception as e:
        logger.error(f"Failed to load non-critical initialization data for user {user_id}: {e}", exc_info=True)
        # 非关键数据失败不影响主流程，返回空数据
        return {
            "sessions": [],
            "sessionsTotal": 0,
            "sessionsHasMore": False,
            "personas": [],
            "storageConfigs": [],
            "activeStorageId": None,
            "imagenConfig": None
        }


@router.get("/init")
async def get_init(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    统一初始化端点 - 返回应用启动所需的所有数据（向后兼容）
    
    注意：此端点保留用于向后兼容，新实现应使用 /init/critical 和 /init/non-critical
    """
    try:
        # 调用 init_service 获取所有初始化数据
        init_data = await get_init_data(user_id, db)
        return init_data
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to load initialization data for user {user_id}: {e}", exc_info=True)
        # 返回 500 错误
        raise HTTPException(
            status_code=500,
            detail="Failed to load initialization data. Please try again later."
        )
