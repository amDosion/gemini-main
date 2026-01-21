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

logger = logging.getLogger(__name__)

# 查询超时时间（秒）
QUERY_TIMEOUT = 5


def assemble_messages_v3(
    session_id: str,
    indexes: List[MessageIndex],
    messages_by_table: Dict[str, Dict[str, Any]],
    attachments_by_message: Dict[str, List[MessageAttachment]]
) -> List[Dict[str, Any]]:
    """
    组装单个会话的消息列表 (v3 架构)
    
    复用 sessions.py 的逻辑
    """
    assembled_messages = []
    
    for idx in indexes:
        # 从模式表获取消息
        table_messages = messages_by_table.get(idx.table_name, {})
        msg = table_messages.get(idx.id)
        
        if not msg:
            logger.warning(f"消息不存在: id={idx.id}, table={idx.table_name}")
            continue
        
        # 转换为字典
        msg_dict = msg.to_dict()
        
        # 从索引表获取 mode 字段
        msg_dict['mode'] = idx.mode
        
        # 附加附件
        atts = attachments_by_message.get(idx.id, [])
        if atts:
            msg_dict['attachments'] = [att.to_dict() for att in atts]
        else:
            msg_dict['attachments'] = []
        
        assembled_messages.append(msg_dict)
    
    return assembled_messages


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
            (p for p in profiles_data if p["providerId"] == "tongyi"),
            None
        )
        if tongyi_profile:
            dashscope_key = tongyi_profile.get("apiKey", "")
        
        logger.info(f"[InitService] Profiles 加载成功: {len(profiles_data)} 个配置")
        
        return {
            "profiles": profiles_data,
            "activeProfileId": active_profile_id,
            "activeProfile": active_profile,
            "dashscopeKey": dashscope_key,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Profiles 加载失败: {e}")
        return {
            "profiles": [],
            "activeProfileId": None,
            "activeProfile": None,
            "dashscopeKey": "",
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
            "storageConfigs": storage_configs_data,
            "activeStorageId": active_storage_id,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Storage Configs 加载失败: {e}")
        return {
            "storageConfigs": [],
            "activeStorageId": None,
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
                "createdAt": session.created_at,
                "personaId": session.persona_id,
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
            "hasMore": bool
        }
    """
    try:
        logger.info(f"[InitService] 查询 Sessions（包含第一个会话的完整消息，limit={limit}）...")
        
        # ✅ 查询会话列表（按更新时间排序）
        from sqlalchemy import func
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(
            ChatSession.created_at.desc()  # 按创建时间排序，获取最新的会话
        ).limit(limit).all()
        
        if not sessions:
            logger.info(f"[InitService] Sessions 加载成功: 0 个会话")
            return {
                "sessions": [],
                "total": 0,
                "hasMore": False,
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
                "createdAt": session.created_at,
                "personaId": session.persona_id,
                "mode": session.mode,
                "messageCount": message_count_map.get(session.id, 0)
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
            "hasMore": has_more,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Sessions 加载失败: {e}")
        return {
            "sessions": [],
            "total": 0,
            "hasMore": False,
            "error": str(e)
        }


async def _query_sessions_metadata_only(user_id: str, db: Session, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    查询会话元数据（仅元数据，不包含消息）
    
    用于滚动加载更多会话（惰性加载）
    
    Returns:
        {
            "sessions": [...],  # messages 为空数组
            "total": int,
            "hasMore": bool
        }
    """
    try:
        logger.info(f"[InitService] 查询 Sessions 元数据（limit={limit}, offset={offset}）...")
        
        # ✅ 查询会话列表（按创建时间排序）
        from sqlalchemy import func
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(
            ChatSession.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        if not sessions:
            return {
                "sessions": [],
                "total": 0,
                "hasMore": False,
                "error": None
            }
        
        # ✅ 查询总会话数量
        total_count = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).count()
        
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
        
        # ✅ 组装会话结果（messages 为空数组）
        sessions_result = []
        for session in sessions:
            session_dict = {
                "id": session.id,
                "title": session.title,
                "createdAt": session.created_at,
                "personaId": session.persona_id,
                "mode": session.mode,
                "messageCount": message_count_map.get(session.id, 0),
                "messages": []  # ✅ 滚动加载的会话 messages 为空数组
            }
            sessions_result.append(session_dict)
        
        has_more = (offset + limit) < total_count
        
        logger.info(f"[InitService] Sessions 元数据加载成功: {len(sessions_result)} 个会话")
        
        return {
            "sessions": sessions_result,
            "total": total_count,
            "hasMore": has_more,
            "error": None
        }
    except Exception as e:
        logger.error(f"[InitService] Sessions 元数据加载失败: {e}")
        return {
            "sessions": [],
            "total": 0,
            "hasMore": False,
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
        logger.info(f"[InitService] 查询 Personas（用户: {user_id[:8]}...）...")
        
        # ✅ 只查询数据库，不执行初始化
        user_query = UserScopedQuery(db, user_id)
        personas = user_query.get_all(Persona)
        
        if personas:
            personas_data = [p.to_dict() for p in personas]
            logger.info(f"[InitService] Personas 加载成功: {len(personas_data)} 个角色")
            return {"personas": personas_data, "error": None}
        else:
            # ✅ 如果用户没有 Personas，返回空数组（前端会处理）
            logger.info(f"[InitService] 用户 {user_id[:8]}... 暂无 Personas（可能尚未注册或注册时初始化失败）")
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
            logger.info(f"[InitService] Vertex AI Config 加载成功: api_mode={config_data.get('apiMode')}")
            return {"vertexAiConfig": config_data, "error": None}
        else:
            # 返回默认配置
            logger.info(f"[InitService] 无 Imagen 配置，返回默认值")
            return {
                "imagenConfig": {
                    "apiMode": "gemini_api",
                    "vertexAiProjectId": None,
                    "vertexAiLocation": "us-central1",
                    "vertexAiCredentialsJson": None
                },
                "error": None
            }
    except Exception as e:
        logger.warning(f"[InitService] Imagen Config 加载失败，使用默认值: {e}")
        return {
            "imagenConfig": {
                "apiMode": "gemini_api",
                "vertexAiProjectId": None,
                "vertexAiLocation": "us-central1",
                "vertexAiCredentialsJson": None
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
        "activeProfileId": None,
        "activeProfile": None,
        "dashscopeKey": "",
        "storageConfigs": [],
        "activeStorageId": None,
        "sessions": [],
        "personas": [],  # ✅ 重构后：默认返回空数组，不返回默认 Personas
        "imagenConfig": None,
        "cachedModels": None,
        "_metadata": {
            "timestamp": int(time.time() * 1000),
            "partialFailures": []
        }
    }
    
    try:
        # 使用 asyncio.gather() 并行查询所有数据源（带超时）
        profiles_task = _query_profiles(user_id, db)
        storage_task = _query_storage_configs(user_id, db)
        sessions_task = _query_sessions(user_id, db)
        personas_task = _query_personas(user_id, db)
        vertex_ai_task = _query_vertex_ai_config(user_id, db)
        
        # 并行执行所有查询，设置超时
        profiles_result, storage_result, sessions_result, personas_result, vertex_ai_result = await asyncio.wait_for(
            asyncio.gather(
                profiles_task,
                storage_task,
                sessions_task,
                personas_task,
                vertex_ai_task,
                return_exceptions=True  # 不让单个查询失败影响整体
            ),
            timeout=QUERY_TIMEOUT
        )
        
        # 处理 Profiles 结果
        if isinstance(profiles_result, dict) and not profiles_result.get("error"):
            result["profiles"] = profiles_result["profiles"]
            result["activeProfileId"] = profiles_result["activeProfileId"]
            result["activeProfile"] = profiles_result["activeProfile"]
            result["dashscopeKey"] = profiles_result["dashscopeKey"]
        else:
            result["_metadata"]["partialFailures"].append("profiles")
            if isinstance(profiles_result, Exception):
                logger.error(f"[InitService] Profiles 查询异常: {profiles_result}")
        
        # 处理 Storage Configs 结果
        if isinstance(storage_result, dict) and not storage_result.get("error"):
            result["storageConfigs"] = storage_result["storageConfigs"]
            result["activeStorageId"] = storage_result["activeStorageId"]
        else:
            result["_metadata"]["partialFailures"].append("storageConfigs")
            if isinstance(storage_result, Exception):
                logger.error(f"[InitService] Storage Configs 查询异常: {storage_result}")
        
        # 处理 Sessions 结果
        if isinstance(sessions_result, dict) and not sessions_result.get("error"):
            result["sessions"] = sessions_result["sessions"]
        else:
            result["_metadata"]["partialFailures"].append("sessions")
            if isinstance(sessions_result, Exception):
                logger.error(f"[InitService] Sessions 查询异常: {sessions_result}")
        
        # 处理 Personas 结果
        if isinstance(personas_result, dict):
            result["personas"] = personas_result["personas"]
            # Personas 失败不算 partialFailures，因为有默认值
        else:
            if isinstance(personas_result, Exception):
                logger.warning(f"[InitService] Personas 查询异常，使用默认值: {personas_result}")
        
        # 处理 Vertex AI Config 结果
        if isinstance(vertex_ai_result, dict) and not vertex_ai_result.get("error"):
            result["vertexAiConfig"] = vertex_ai_result["vertexAiConfig"]
        else:
            # Vertex AI Config 失败不算 partialFailures，因为有默认值
            if isinstance(vertex_ai_result, Exception):
                logger.warning(f"[InitService] Vertex AI Config 查询异常，使用默认值: {vertex_ai_result}")
            result["vertexAiConfig"] = {
                "apiMode": "gemini_api",
                "vertexAiProjectId": None,
                "vertexAiLocation": "us-central1",
                "vertexAiCredentialsJson": None
            }
        
    except asyncio.TimeoutError:
        logger.error(f"[InitService] 查询超时（{QUERY_TIMEOUT}秒）")
        result["_metadata"]["partialFailures"].append("timeout")
    except Exception as e:
        logger.error(f"[InitService] 并行查询失败: {e}")
        result["_metadata"]["partialFailures"].append("critical_error")
    
    logger.info(f"[InitService] 初始化数据加载完成，部分失败: {result['_metadata']['partialFailures']}")
    
    return result
