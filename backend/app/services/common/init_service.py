"""
初始化服务 - 统一初始化 API

提供单一端点获取应用启动所需的所有数据:
- 配置 (Profiles)
- 会话 (Sessions)
- 角色 (Personas)
- 云存储配置 (Storage Configs)
"""
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from collections import defaultdict

from ...core.user_scoped_query import UserScopedQuery
from ...models.db_models import (
    ConfigProfile,
    UserSettings,
    StorageConfig,
    ActiveStorage,
    ChatSession,
    MessageIndex,
    MessageAttachment,
    Persona,
    VertexAIConfig
)
from ...utils.message_utils import get_message_table_class_by_name
from ...utils.message_assembly import assemble_messages_v3

logger = logging.getLogger(__name__)

# 查询超时时间（秒）
QUERY_TIMEOUT = 5


# 已删除重复的 assemble_messages_v3 函数
# 现在使用统一的实现：utils/message_assembly.py


async def _query_profiles(user_id: str, db: Session) -> Dict[str, Any]:
    """
    查询 Profiles 数据（异步包装）
    
    Returns:
        包含 profiles, activeProfileId, activeProfile, dashscopeKey 的字典
    """
    try:
        logger.info(f"[InitService] 查询 Profiles...")
        user_query = UserScopedQuery(db, user_id)
        profiles = user_query.get_all(ConfigProfile)
        profiles_data = [p.to_dict() for p in profiles]
        
        # 查询 Active Profile
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        active_profile_id = settings.active_profile_id if settings else None
        active_profile = None
        
        if active_profile_id:
            active_profile = next(
                (p for p in profiles_data if p["id"] == active_profile_id),
                None
            )
        
        # 提取 DashScope Key
        dashscope_key = ""
        tongyi_profile = next(
            (p for p in profiles_data if p["provider_id"] == "tongyi"),
            None
        )
        if tongyi_profile:
            dashscope_key = tongyi_profile.get("api_key", "")
        
        logger.info(f"[InitService] Profiles 加载成功: {len(profiles_data)} 个配置")
        
        return {
            "profiles": profiles_data,
            "active_profile_id": active_profile_id,
            "active_profile": active_profile,
            "dashscope_key": dashscope_key,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Profiles 加载失败: {e}")
        return {
            "profiles": [],
            "active_profile_id": None,
            "active_profile": None,
            "dashscope_key": "",
            "error": str(e)
        }


async def _query_storage_configs(user_id: str, db: Session) -> Dict[str, Any]:
    """
    查询 Storage Configs 数据（异步包装）
    
    Returns:
        包含 storageConfigs, activeStorageId 的字典
    """
    try:
        logger.info(f"[InitService] 查询 Storage Configs...")
        user_query = UserScopedQuery(db, user_id)
        storage_configs = user_query.get_all(StorageConfig)
        storage_configs_data = [s.to_dict() for s in storage_configs]
        
        # 查询 Active Storage
        active_storage = db.query(ActiveStorage).filter(ActiveStorage.user_id == user_id).first()
        active_storage_id = active_storage.storage_id if active_storage else None
        
        logger.info(f"[InitService] Storage Configs 加载成功: {len(storage_configs_data)} 个配置")
        
        return {
            "storage_configs": storage_configs_data,
            "active_storage_id": active_storage_id,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Storage Configs 加载失败: {e}")
        return {
            "storage_configs": [],
            "active_storage_id": None,
            "error": str(e)
        }


async def _query_sessions(user_id: str, db: Session) -> Dict[str, Any]:
    """
    查询 Sessions 数据（异步包装，v3 架构）
    
    Returns:
        包含 sessions 的字典
    """
    try:
        logger.info(f"[InitService] 查询 Sessions...")
        user_query = UserScopedQuery(db, user_id)
        sessions = user_query.get_all(ChatSession)
        
        if not sessions:
            logger.info(f"[InitService] Sessions 加载成功: 0 个会话")
            return {"sessions": [], "error": None}
        
        session_ids = [s.id for s in sessions]
        
        # 批量查询所有消息索引
        all_indexes = db.query(MessageIndex).filter(
            MessageIndex.session_id.in_(session_ids),
            MessageIndex.user_id == user_id
        ).order_by(MessageIndex.session_id, MessageIndex.seq.asc()).all()
        
        # 按 session_id 分组索引
        indexes_by_session: Dict[str, List[MessageIndex]] = defaultdict(list)
        for idx in all_indexes:
            indexes_by_session[idx.session_id].append(idx)
        
        # 收集所有 message_ids 和 table_names
        all_message_ids = set()
        table_message_ids: Dict[str, set] = defaultdict(set)
        
        for idx in all_indexes:
            all_message_ids.add(idx.id)
            table_message_ids[idx.table_name].add(idx.id)
        
        # 按 table_name 批量查询各模式表
        messages_by_table: Dict[str, Dict[str, Any]] = {}
        
        for table_name, msg_ids in table_message_ids.items():
            if not msg_ids:
                continue
            try:
                table_class = get_message_table_class_by_name(table_name)
                messages = db.query(table_class).filter(
                    table_class.id.in_(list(msg_ids))
                ).all()
                messages_by_table[table_name] = {msg.id: msg for msg in messages}
            except ValueError as e:
                logger.warning(f"[InitService] 未知表名: {table_name}, 错误: {e}")
                continue
        
        # 批量查询所有附件
        attachments_by_message: Dict[str, List[MessageAttachment]] = defaultdict(list)
        
        if all_message_ids:
            all_attachments = db.query(MessageAttachment).filter(
                MessageAttachment.message_id.in_(list(all_message_ids)),
                MessageAttachment.user_id == user_id
            ).all()
            
            for att in all_attachments:
                attachments_by_message[att.message_id].append(att)
        
        # 组装每个会话的结果
        sessions_result = []
        
        for session in sessions:
            session_dict = {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "persona_id": session.persona_id,
                "mode": session.mode
            }
            
            # 检查是否有 v3 数据
            session_indexes = indexes_by_session.get(session.id, [])
            
            if session_indexes:
                session_dict["messages"] = assemble_messages_v3(
                    session.id,
                    session_indexes,
                    messages_by_table,
                    attachments_by_message
                )
            else:
                session_dict["messages"] = []
            
            sessions_result.append(session_dict)
        
        logger.info(f"[InitService] Sessions 加载成功: {len(sessions_result)} 个会话")
        
        return {"sessions": sessions_result, "error": None}
    except Exception as e:
        logger.error(f"[InitService] Sessions 加载失败: {e}")
        return {"sessions": [], "error": str(e)}


async def _query_sessions_with_first_messages(user_id: str, db: Session, limit: int = 20) -> Dict[str, Any]:
    """
    查询会话列表 + 第一个会话的完整消息
    
    注意：
    1. 返回最近的 N 个会话元数据（用于左侧 Sidebar）
    2. 第一个会话必须包含完整消息（不能分页，用于右侧 ChatView）
    3. 其他会话的 messages 为空数组（按需加载）
    
    Returns:
        {
            "sessions": [...],
            "total": int,
            "has_more": bool
        }
    """
    try:
        logger.info(f"[InitService] 查询 Sessions（包含第一个会话的完整消息，limit={limit}）...")

        # ✅ A-5: ChatSession 没有 updated_at 列，按 created_at 排序会让"最近活跃"
        # 的会话被旧创建时间淹没。改为按"最近一条 message 的 timestamp"降序排序，
        # 无消息的会话退回 session.created_at（COALESCE）。
        from sqlalchemy import func
        last_msg_subq = (
            db.query(
                MessageIndex.session_id.label("sid"),
                func.max(MessageIndex.timestamp).label("last_ts"),
            )
            .filter(MessageIndex.user_id == user_id)
            .group_by(MessageIndex.session_id)
            .subquery()
        )
        last_ts_col = func.coalesce(last_msg_subq.c.last_ts, ChatSession.created_at)
        sessions = (
            db.query(ChatSession)
            .outerjoin(last_msg_subq, last_msg_subq.c.sid == ChatSession.id)
            .filter(ChatSession.user_id == user_id)
            .order_by(last_ts_col.desc())
            .limit(limit)
            .all()
        )
        
        if not sessions:
            logger.info(f"[InitService] Sessions 加载成功: 0 个会话")
            return {
                "sessions": [],
                "total": 0,
                "has_more": False,
                "error": None
            }
        
        # ✅ 查询总会话数量（用于分页）
        total_count = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).count()
        
        # ✅ 批量查询每个会话的消息数量（用于显示）
        session_ids = [s.id for s in sessions]
        message_counts = db.query(
            MessageIndex.session_id,
            func.count(MessageIndex.id).label('count')
        ).filter(
            MessageIndex.session_id.in_(session_ids),
            MessageIndex.user_id == user_id
        ).group_by(MessageIndex.session_id).all()
        
        message_count_map = {mc.session_id: mc.count for mc in message_counts}
        
        # ✅ 获取第一个会话的完整消息（不能分页）
        first_session = sessions[0]
        first_session_messages = []
        
        # 查询第一个会话的所有消息索引
        first_indexes = db.query(MessageIndex).filter(
            MessageIndex.session_id == first_session.id,
            MessageIndex.user_id == user_id
        ).order_by(MessageIndex.seq.asc()).all()
        
        if first_indexes:
            # 收集所有 message_ids 和 table_names
            first_message_ids = set()
            first_table_message_ids: Dict[str, set] = defaultdict(set)
            
            for idx in first_indexes:
                first_message_ids.add(idx.id)
                first_table_message_ids[idx.table_name].add(idx.id)
            
            # 按 table_name 批量查询各模式表
            first_messages_by_table: Dict[str, Dict[str, Any]] = {}
            
            for table_name, msg_ids in first_table_message_ids.items():
                if not msg_ids:
                    continue
                try:
                    table_class = get_message_table_class_by_name(table_name)
                    messages = db.query(table_class).filter(
                        table_class.id.in_(list(msg_ids))
                    ).all()
                    first_messages_by_table[table_name] = {msg.id: msg for msg in messages}
                except ValueError as e:
                    logger.warning(f"[InitService] 未知表名: {table_name}, 错误: {e}")
                    continue
            
            # 批量查询所有附件
            first_attachments_by_message: Dict[str, List[MessageAttachment]] = defaultdict(list)
            
            if first_message_ids:
                all_attachments = db.query(MessageAttachment).filter(
                    MessageAttachment.message_id.in_(list(first_message_ids)),
                    MessageAttachment.user_id == user_id
                ).all()
                
                for att in all_attachments:
                    first_attachments_by_message[att.message_id].append(att)
            
            # 组装第一个会话的消息
            first_session_messages = assemble_messages_v3(
                first_session.id,
                first_indexes,
                first_messages_by_table,
                first_attachments_by_message
            )
        
        # ✅ 组装会话结果
        sessions_result = []
        for idx, session in enumerate(sessions):
            session_dict = {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "persona_id": session.persona_id,
                "mode": session.mode,
                "message_count": message_count_map.get(session.id, 0)
            }
            
            if idx == 0:
                # ✅ 第一个会话包含完整消息
                session_dict["messages"] = first_session_messages
            else:
                # ✅ 其他会话 messages 为空数组
                session_dict["messages"] = []
            
            sessions_result.append(session_dict)
        
        has_more = total_count > limit
        
        logger.info(f"[InitService] Sessions 加载成功: {len(sessions_result)} 个会话（第一个包含 {len(first_session_messages)} 条消息）")
        
        return {
            "sessions": sessions_result,
            "total": total_count,
            "has_more": has_more,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Sessions 加载失败: {e}")
        return {
            "sessions": [],
            "total": 0,
            "has_more": False,
            "error": str(e)
        }


async def _query_sessions_metadata_only(
    user_id: str,
    db: Session,
    limit: int = 20,
    offset: int = 0,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    查询会话元数据（仅元数据，不包含消息）

    用于滚动加载更多会话（惰性加载）。

    A-7 cursor 分页:
    - 若提供 cursor（上一页最后一条 session.created_at，毫秒字符串），按
      `created_at < cursor` 过滤，避免大 OFFSET 劣化。
    - total 仅在第一页（无 cursor 且 offset==0）返回，避免每页全表 count(*)。
    - next_cursor 为本页最后一条的 created_at（若 has_more 为真），便于下一次调用。
    - 不带 cursor 时退回 OFFSET 模式（向后兼容）。
    建议在 chat_sessions 上加索引 (user_id, created_at DESC)。

    Returns:
        {
            "sessions": [...],  # messages 为空数组
            "total": int | None,
            "has_more": bool,
            "next_cursor": str | None,
        }
    """
    try:
        logger.info(
            f"[InitService] 查询 Sessions 元数据（limit={limit}, offset={offset}, cursor={cursor}）..."
        )

        from sqlalchemy import func

        base_q = db.query(ChatSession).filter(ChatSession.user_id == user_id)

        cursor_ts: Optional[int] = None
        if cursor:
            try:
                cursor_ts = int(cursor)
                base_q = base_q.filter(ChatSession.created_at < cursor_ts)
            except (TypeError, ValueError):
                logger.warning(f"[InitService] 非法 cursor: {cursor!r}，退回 OFFSET 模式")
                cursor_ts = None

        ordered_q = base_q.order_by(ChatSession.created_at.desc())

        # 多取 1 条用来判断 has_more（避免再发一次 count）
        if cursor_ts is not None:
            page = ordered_q.limit(limit + 1).all()
        else:
            page = ordered_q.offset(offset).limit(limit + 1).all()

        has_more = len(page) > limit
        sessions = page[:limit]

        if not sessions:
            # 仅在首屏才尝试给 total 一个数值
            return {
                "sessions": [],
                "total": 0 if (cursor_ts is None and offset == 0) else None,
                "has_more": False,
                "next_cursor": None,
                "error": None,
            }

        # ✅ total 只在第一页查（避免每次滚动都全表 count）
        total_count: Optional[int] = None
        if cursor_ts is None and offset == 0:
            total_count = db.query(func.count(ChatSession.id)).filter(
                ChatSession.user_id == user_id
            ).scalar() or 0

        # ✅ 批量查询每个会话的消息数量
        session_ids = [s.id for s in sessions]
        message_counts = db.query(
            MessageIndex.session_id,
            func.count(MessageIndex.id).label('count')
        ).filter(
            MessageIndex.session_id.in_(session_ids),
            MessageIndex.user_id == user_id
        ).group_by(MessageIndex.session_id).all()

        message_count_map = {mc.session_id: mc.count for mc in message_counts}

        sessions_result = []
        for session in sessions:
            session_dict = {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "persona_id": session.persona_id,
                "mode": session.mode,
                "message_count": message_count_map.get(session.id, 0),
                "messages": []
            }
            sessions_result.append(session_dict)

        next_cursor: Optional[str] = None
        if has_more and sessions:
            next_cursor = str(sessions[-1].created_at)

        logger.info(
            f"[InitService] Sessions 元数据加载成功: {len(sessions_result)} 个会话, has_more={has_more}"
        )

        return {
            "sessions": sessions_result,
            "total": total_count,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "error": None,
        }
    except Exception as e:
        logger.error(f"[InitService] Sessions 元数据加载失败: {e}")
        return {
            "sessions": [],
            "total": None,
            "has_more": False,
            "next_cursor": None,
            "error": str(e)
        }


async def _query_personas(user_id: str, db: Session) -> Dict[str, Any]:
    """
    查询 Personas 数据（仅查询数据库，不执行初始化）
    
    ✅ 重构后：登录时只从数据库加载，不执行初始化
    初始化只在用户注册时执行
    
    Returns:
        包含 personas 的字典
    """
    try:
        logger.info(f"[InitService] 查询 Personas（用户: {user_id}）...")
        
        user_query = UserScopedQuery(db, user_id)
        personas = user_query.get_all(Persona)
        
        if personas:
            personas_data = [p.to_dict() for p in personas]
            logger.info(f"[InitService] Personas 加载成功: {len(personas_data)} 个角色")
            return {"personas": personas_data, "error": None}
        else:
            # ✅ 如果用户没有 Personas，返回空数组（前端会处理）
            logger.info(f"[InitService] 用户 {user_id} 暂无 Personas（可能尚未注册或注册时初始化失败）")
            return {"personas": [], "error": None}
    except Exception as e:
        logger.error(f"[InitService] Personas 加载失败: {e}", exc_info=True)
        return {"personas": [], "error": str(e)}


async def _query_vertex_ai_config(user_id: str, db: Session) -> Dict[str, Any]:
    """
    查询 Vertex AI 配置数据（异步包装）
    
    Returns:
        包含 vertexAiConfig 的字典
    """
    try:
        logger.info(f"[InitService] 查询 Vertex AI Config...")
        vertex_ai_config = db.query(VertexAIConfig).filter(VertexAIConfig.user_id == user_id).first()
        
        if vertex_ai_config:
            config_data = vertex_ai_config.to_dict()
            logger.info(f"[InitService] Vertex AI Config 加载成功: api_mode={config_data.get('api_mode')}")
            return {"vertex_ai_config": config_data, "error": None}
        else:
            # 返回默认配置
            logger.info(f"[InitService] 无 Imagen 配置，返回默认值")
            return {
                "imagen_config": {
                    "api_mode": "gemini_api",
                    "vertex_ai_project_id": None,
                    "vertex_ai_location": "us-central1",
                    "vertex_ai_credentials_json": None
                },
                "error": None
            }
    except Exception as e:
        logger.warning(f"[InitService] Imagen Config 加载失败，使用默认值: {e}")
        return {
            "imagen_config": {
                "api_mode": "gemini_api",
                "vertex_ai_project_id": None,
                "vertex_ai_location": "us-central1",
                "vertex_ai_credentials_json": None
            },
            "error": str(e)
        }


async def get_init_data(user_id: str, db: Session) -> Dict[str, Any]:
    """
    获取用户初始化数据（使用并行查询优化性能）
    
    Args:
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        包含所有初始化数据的字典
    """
    logger.info(f"[InitService] 开始加载用户初始化数据: user_id={user_id}")
    
    # 初始化返回结构
    result = {
        "profiles": [],
        "active_profile_id": None,
        "active_profile": None,
        "dashscope_key": "",
        "storage_configs": [],
        "active_storage_id": None,
        "sessions": [],
        "personas": [],  # ✅ 重构后：默认返回空数组，不返回默认 Personas
        "imagen_config": None,
        "cached_models": None,
        "_metadata": {
            "timestamp": int(time.time() * 1000),
            "partial_failures": []
        }
    }
    
    try:
        # ✅ A-2: SQLAlchemy 同步 Session 跨任务非线程安全（identity map / 事务边界 /
        # pending 改动并发污染）。原来的 asyncio.gather 让 5 个查询共享同一个 db
        # Session — 即便看似只读，仍属未定义行为。改为串行 await，整体超时仍由
        # asyncio.wait_for 控制。如未来要恢复并发，必须给每个任务注入独立 SessionLocal()。
        async def _serial_collect():
            results = []
            for coro in (
                _query_profiles(user_id, db),
                _query_storage_configs(user_id, db),
                _query_sessions(user_id, db),
                _query_personas(user_id, db),
                _query_vertex_ai_config(user_id, db),
            ):
                try:
                    results.append(await coro)
                except Exception as exc:
                    results.append(exc)
            return results

        profiles_result, storage_result, sessions_result, personas_result, vertex_ai_result = await asyncio.wait_for(
            _serial_collect(),
            timeout=QUERY_TIMEOUT
        )
        
        # 处理 Profiles 结果
        if isinstance(profiles_result, dict) and not profiles_result.get("error"):
            result["profiles"] = profiles_result["profiles"]
            result["active_profile_id"] = profiles_result["active_profile_id"]
            result["active_profile"] = profiles_result["active_profile"]
            result["dashscope_key"] = profiles_result["dashscope_key"]
        else:
            result["_metadata"]["partial_failures"].append("profiles")
            if isinstance(profiles_result, Exception):
                logger.error(f"[InitService] Profiles 查询异常: {profiles_result}")
        
        # 处理 Storage Configs 结果
        if isinstance(storage_result, dict) and not storage_result.get("error"):
            result["storage_configs"] = storage_result["storage_configs"]
            result["active_storage_id"] = storage_result["active_storage_id"]
        else:
            result["_metadata"]["partial_failures"].append("storage_configs")
            if isinstance(storage_result, Exception):
                logger.error(f"[InitService] Storage Configs 查询异常: {storage_result}")
        
        # 处理 Sessions 结果
        if isinstance(sessions_result, dict) and not sessions_result.get("error"):
            result["sessions"] = sessions_result["sessions"]
        else:
            result["_metadata"]["partial_failures"].append("sessions")
            if isinstance(sessions_result, Exception):
                logger.error(f"[InitService] Sessions 查询异常: {sessions_result}")
        
        # 处理 Personas 结果
        if isinstance(personas_result, dict):
            result["personas"] = personas_result["personas"]
            # Personas 失败不算 partial_failures，因为有默认值
        else:
            if isinstance(personas_result, Exception):
                logger.warning(f"[InitService] Personas 查询异常，使用默认值: {personas_result}")
        
        # 处理 Vertex AI Config 结果
        if isinstance(vertex_ai_result, dict) and not vertex_ai_result.get("error"):
            result["vertex_ai_config"] = vertex_ai_result["vertex_ai_config"]
        else:
            # Vertex AI Config 失败不算 partial_failures，因为有默认值
            if isinstance(vertex_ai_result, Exception):
                logger.warning(f"[InitService] Vertex AI Config 查询异常，使用默认值: {vertex_ai_result}")
            result["vertex_ai_config"] = {
                "api_mode": "gemini_api",
                "vertex_ai_project_id": None,
                "vertex_ai_location": "us-central1",
                "vertex_ai_credentials_json": None
            }
        
    except asyncio.TimeoutError:
        logger.error(f"[InitService] 查询超时（{QUERY_TIMEOUT}秒）")
        result["_metadata"]["partial_failures"].append("timeout")
    except Exception as e:
        logger.error(f"[InitService] 并行查询失败: {e}")
        result["_metadata"]["partial_failures"].append("critical_error")
    
    logger.info(f"[InitService] 初始化数据加载完成，部分失败: {result['_metadata']['partial_failures']}")
    
    return result
