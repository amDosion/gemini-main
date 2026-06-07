"""
统一初始化 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from sqlalchemy.orm import Session
import logging

from ...core.database import SessionLocal, get_db
from ...core.dependencies import require_current_user
from ...middleware.case_conversion_middleware import case_conversion_options
from ...services.common.init_service import get_init_data
from ..models.models import (
    _merge_saved_models,
    _get_effective_profile,
    _get_vertex_ai_config,
    _build_preferred_model_ids,
    _resolve_mode_view,
    _ensure_model_traits,
    filter_models_by_mode,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["init"])


@router.get("/init/critical")
@case_conversion_options(always_convert_response=True)
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
    - cachedModels: 过滤 hidden 后的全部模型列表（Header 需要显示模型选择器）
    - cachedModeCatalog: 各 mode 的模型可用性目录
    - cachedChatModels: chat 模式的预过滤模型列表（默认首屏）
    - cachedDefaultModelId: chat 模式的默认模型 ID
    - dashscopeKey: 通义千问的 API Key（如果使用通义千问）
    
    优化：返回预过滤的模型数据，前端初始化时无需额外请求 /api/models
    """
    from ...services.common.init_service import _query_profiles
    
    try:
        profiles_result = await _query_profiles(user_id, db)

        cached_models = None
        cached_mode_catalog = []
        cached_chat_models = None
        cached_default_model_id = None
        active_profile = profiles_result.get("active_profile")
        provider_id = str((active_profile or {}).get("provider_id") or "").strip().lower()

        if provider_id:
            # ✅ A-6: 复用 _query_profiles 已查到的 active_profile_id，避免再次 UserSettings 查询
            effective_profile = _get_effective_profile(
                provider_id, db, user_id,
                active_profile_id_hint=profiles_result.get("active_profile_id"),
            )
            vertex_config = _get_vertex_ai_config(db, user_id) if provider_id == "google" else None

            models = _merge_saved_models(
                provider=provider_id,
                models=[],
                raw_saved_models=effective_profile.saved_models if effective_profile else None,
                source=f"init-profile:{effective_profile.id if effective_profile else 'none'}"
            )

            if vertex_config:
                models = _merge_saved_models(
                    provider=provider_id,
                    models=models,
                    raw_saved_models=vertex_config.saved_models,
                    source=f"init-vertex:{vertex_config.id}"
                )

            # 统一计算 traits（与 /api/models/{provider} 保持一致）
            models = [_ensure_model_traits(provider_id, model) for model in models]

            # 过滤 hidden models（与 /api/models/{provider} 保持一致）
            if effective_profile and hasattr(effective_profile, 'hidden_models') and effective_profile.hidden_models:
                raw_hidden = effective_profile.hidden_models
                if isinstance(raw_hidden, list):
                    hidden_ids = set(raw_hidden)
                    if hidden_ids:
                        models = [m for m in models if m.id not in hidden_ids]
                        logger.info(f"[Init] Filtered {len(hidden_ids)} hidden models, {len(models)} remaining")

            preferred_model_ids = _build_preferred_model_ids(provider_id, effective_profile, vertex_config)

            # 完整模型列表（过滤 hidden 后）
            cached_models = [model.model_dump() for model in models]

            # 计算 modeCatalog + chat 模式的预过滤模型
            cached_mode_catalog, chat_filtered, cached_default_model_id = _resolve_mode_view(
                models=models,
                preferred_model_ids=preferred_model_ids,
                mode="chat",
            )
            cached_chat_models = [model.model_dump() for model in chat_filtered]

            logger.info(
                f"[Init] Critical data: {len(cached_models)} all models, "
                f"{len(cached_chat_models)} chat models, "
                f"default={cached_default_model_id}"
            )

        return {
            "profiles": profiles_result.get("profiles", []),
            "active_profile_id": profiles_result.get("active_profile_id"),
            "active_profile": profiles_result.get("active_profile"),
            "cached_models": cached_models,
            "cached_mode_catalog": cached_mode_catalog,
            "cached_chat_models": cached_chat_models,
            "cached_default_model_id": cached_default_model_id,
            "dashscope_key": profiles_result.get("dashscope_key", "")
        }
    except Exception as e:
        logger.error(f"Failed to load critical initialization data for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to load critical initialization data. Please try again later."
        )


@router.get("/init/sessions/more")
@case_conversion_options(always_convert_response=True)
async def get_more_sessions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    mode: str | None = Query(None, max_length=64),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    滚动加载更多会话元数据（惰性加载）

    用于 Sidebar 滚动到底部时加载更多会话
    只返回会话元数据，messages 为空数组

    A-7: 支持 cursor 分页（首选）。cursor 为上一页最后一条 session 的 created_at
    时间戳（毫秒，字符串）。若提供，过滤 `created_at < cursor`，避免 OFFSET
    大数据集劣化。无 cursor 时退回 OFFSET 模式以保持兼容。total 仅在第一页
    （无 cursor 且 offset==0）时返回，避免每页全表 count(*)。

    建议在 chat_sessions 上加索引 (user_id, created_at DESC) 以最大化收益。
    """
    from ...services.common.init_service import _query_sessions_metadata_only

    try:
        result = await _query_sessions_metadata_only(
            user_id, db, limit=limit, offset=offset, cursor=cursor, mode=mode
        )
        return {
            "sessions": result.get("sessions", []),
            "total": result.get("total"),
            "hasMore": result.get("has_more", False),
            "nextCursor": result.get("next_cursor"),
        }
    except Exception as e:
        # A-10: 不再静默返空——前端能区分加载错误与"无更多数据"
        logger.error(f"Failed to load more sessions for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to load more sessions")


@router.get("/init/non-critical")
@case_conversion_options(always_convert_response=True)
async def get_non_critical_init_data(
    mode: str = Query("chat", max_length=64),
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
        _query_sessions_with_first_messages,
        _query_personas,
        _query_storage_configs,
        _query_vertex_ai_config
    )

    # A-2: SQLAlchemy 同步 Session 在并发任务下不安全（identity map / 事务边界 /
    # pending 改动会被并发污染）。即便这些查询当前看起来"只读"，共享单一 db
    # Session 跑 asyncio.gather 仍属未定义行为。改为串行 await：性能损失 ~10ms，
    # 换数据一致性。如未来要恢复并发，必须给每个任务注入独立 SessionLocal()。
    async def _safe(coro, label: str):
        try:
            return await coro
        except Exception as exc:
            logger.warning(f"[Init/non-critical] {label} 查询失败: {exc}", exc_info=True)
            return exc

    try:
        sessions_result = await _safe(
            _query_sessions_with_first_messages(user_id, db, limit=20, mode=mode),
            "sessions"
        )
        personas_result = await _safe(_query_personas(user_id, db), "personas")
        storage_result = await _safe(_query_storage_configs(user_id, db), "storage")
        vertex_ai_result = await _safe(_query_vertex_ai_config(user_id, db), "vertex_ai")

        # models-middleware-2: _query_vertex_ai_config returns the config under
        # "vertex_ai_config" (existing) or "imagen_config" (defaults) — never
        # "imagenConfig", so this field was always None. Read the correct key.
        # models-middleware-1: never ship the service-account credential blob to the
        # client; redact it and expose only a presence flag.
        imagen_config = None
        if isinstance(vertex_ai_result, dict):
            imagen_config = vertex_ai_result.get("vertex_ai_config") or vertex_ai_result.get("imagen_config")
            if isinstance(imagen_config, dict) and imagen_config.get("vertex_ai_credentials_json"):
                imagen_config = {
                    **imagen_config,
                    "vertex_ai_credentials_json": None,
                    "has_vertex_ai_credentials": True,
                }

        return {
            "sessions": sessions_result.get("sessions", []) if isinstance(sessions_result, dict) else [],
            "sessionsTotal": sessions_result.get("total", 0) if isinstance(sessions_result, dict) else 0,
            "sessionsHasMore": sessions_result.get("has_more", False) if isinstance(sessions_result, dict) else False,
            "sessionsMode": mode,
            "personas": personas_result.get("personas", []) if isinstance(personas_result, dict) else [],
            "storageConfigs": storage_result.get("storage_configs", []) if isinstance(storage_result, dict) else [],
            "activeStorageId": storage_result.get("active_storage_id") if isinstance(storage_result, dict) else None,
            "imagenConfig": imagen_config
        }
    except Exception as e:
        logger.error(f"Failed to load non-critical initialization data for user {user_id}: {e}", exc_info=True)
        # 非关键数据失败不影响主流程，返回空数据
        return {
            "sessions": [],
            "sessionsTotal": 0,
            "sessionsHasMore": False,
            "sessionsMode": mode,
            "personas": [],
            "storageConfigs": [],
            "activeStorageId": None,
            "imagenConfig": None
        }


@router.get("/init")
@case_conversion_options(always_convert_response=True)
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
