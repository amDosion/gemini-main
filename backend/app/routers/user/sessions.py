"""
会话管理路由 (v3 架构)

v3 架构采用"按模式分表 + 消息索引表"设计：
- message_index: 消息索引表，存储消息路由信息
- messages_chat/messages_image_gen/messages_video_gen/messages_generic: 模式表
- message_attachments: 附件表
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from sqlalchemy.orm import Session
from typing import Annotated, List, Dict, Any, Set, Optional
from datetime import datetime
from collections import defaultdict
import json
import copy
import logging
from pydantic import BaseModel, Field, JsonValue, RootModel

logger = logging.getLogger(__name__)

from ...core.database import SessionLocal, get_db
from ...models.db_models import (
    ChatSession as DBChatSession,
    MessageIndex,
    MessageAttachment,
    MessageHistoryState,
    SessionHistoryPreference,
    UploadTask
)
from ...utils.message_utils import (
    get_table_name_for_mode,
    get_message_table_class_by_name,
    extract_metadata
)
from ...core.dependencies import require_current_user, get_cache
from ...middleware.case_conversion_middleware import case_conversion_options
from ...core.user_scoped_query import UserScopedQuery
from ...utils.message_assembly import assemble_messages_v3
from ...utils.attachment_handler import is_base64_url, is_blob_url, is_http_url
from ...utils.log_sanitization import summarize_text_for_log


router = APIRouter(prefix="/api", tags=["sessions"])


def _summarize_url_for_log(value: Optional[str]) -> str:
    if not value:
        return "none"
    if is_base64_url(value):
        return f"base64(len={len(value)})"
    if is_blob_url(value):
        return f"blob(len={len(value)})"
    if is_http_url(value):
        return f"http(len={len(value)})"
    return f"other(len={len(value)})"


class HistoryStateUpdateRequest(BaseModel):
    is_favorite: Optional[bool] = None


class HistoryPreferenceUpdateRequest(BaseModel):
    show_favorites_only: Optional[bool] = None


TimestampMs = Annotated[int, Field(ge=0, le=4_102_444_800_000)]
SessionDynamicObject = Annotated[Dict[str, JsonValue], Field(max_length=256)]


class SessionResponse(BaseModel):
    id: str = Field(min_length=1, max_length=512)
    title: str = Field(max_length=512)
    messages: List[SessionDynamicObject] = Field(default_factory=list, max_length=10_000)
    created_at: TimestampMs
    persona_id: Optional[str] = Field(default=None, max_length=256)
    mode: Optional[str] = Field(default=None, max_length=128)


class SessionListResponse(RootModel[List[SessionResponse]]):
    root: List[SessionResponse] = Field(max_length=10_000)


class DeleteSessionResponse(BaseModel):
    success: bool


class SessionHistoryStateResponse(BaseModel):
    message_id: str = Field(min_length=1, max_length=512)
    is_favorite: bool
    updated_at: TimestampMs


class SessionHistoryStatesResponse(BaseModel):
    states: List[SessionHistoryStateResponse] = Field(default_factory=list, max_length=10_000)


class SessionHistoryPreferenceResponse(BaseModel):
    show_favorites_only: bool
    updated_at: Optional[int] = Field(default=None, ge=0, le=4_102_444_800_000)


class SessionAttachmentResponse(BaseModel):
    id: str = Field(min_length=1, max_length=512)
    message_id: str = Field(min_length=1, max_length=512)
    user_id: str = Field(min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=512)
    mime_type: Optional[str] = Field(default=None, max_length=128)
    name: Optional[str] = Field(default=None, max_length=512)
    url: Optional[str] = Field(default=None, max_length=4096)
    temp_url: Optional[str] = Field(default=None, max_length=4096)
    file_uri: Optional[str] = Field(default=None, max_length=4096)
    upload_status: Optional[str] = Field(default=None, max_length=64)
    upload_task_id: Optional[str] = Field(default=None, max_length=512)
    upload_error: Optional[str] = Field(default=None, max_length=4096)
    google_file_uri: Optional[str] = Field(default=None, max_length=4096)
    google_file_expiry: Optional[int] = Field(default=None, ge=0, le=4_102_444_800_000)
    size: Optional[int] = Field(default=None, ge=0, le=10_000_000_000)
    task_id: Optional[str] = Field(default=None, max_length=512)
    task_status: Optional[str] = Field(default=None, max_length=64)


# ==================== v3 辅助函数（已移至 utils/message_assembly.py）====================

# 已删除重复的 assemble_messages_v3 函数
# 现在使用统一的实现：utils/message_assembly.py


# ==================== 会话管理 ====================

@router.get(
    "/sessions",
    responses={200: {"model": SessionListResponse, "description": "User chat sessions"}},
)
@case_conversion_options(always_convert_response=True)
async def get_sessions(
    mode: Optional[str] = Query(None, description="按 mode 过滤；不传则返回该用户所有 session"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    """
    获取会话 (v3 架构，带 Redis 缓存)

    Per-mode 完全独立(Sprint 3 方案 1):每个 session 在创建时绑定 mode；
    传入 ?mode=xxx 时只返回该 mode 的 session,UI 不同 mode 看到独立的会话列表。

    缓存策略:
    - 缓存键: cache:sessions:{user_id}:{mode_or_all}
    - TTL: 5 分钟
    - 失效: 写/删时使用通配 cache:sessions:{user_id}:* 清除所有 mode 变体
    """
    from ...services.common.cache_service import CacheService
    cache_service: CacheService = cache

    # 缓存键包含 mode segment, 避免不同 mode 列表互相污染
    cache_key = cache_service._make_key("sessions", user_id, mode or "_all")

    # 定义数据获取函数
    async def fetch_sessions():
        user_query = UserScopedQuery(db, user_id)

        # 1. 查询会话(可按 mode 过滤)
        session_query = user_query.query(DBChatSession)
        if mode:
            session_query = session_query.filter(DBChatSession.mode == mode)
        sessions = session_query.all()
        if not sessions:
            return []
        
        session_ids = [s.id for s in sessions]
        
        # 2. 批量查询所有消息索引（按 session_id, seq 排序）
        all_indexes = db.query(MessageIndex).filter(
            MessageIndex.session_id.in_(session_ids),
            MessageIndex.user_id == user_id
        ).order_by(MessageIndex.session_id, MessageIndex.seq.asc()).all()
        
        # 按 session_id 分组索引
        indexes_by_session: Dict[str, List[MessageIndex]] = defaultdict(list)
        for idx in all_indexes:
            indexes_by_session[idx.session_id].append(idx)
        
        # 3. 收集所有 message_ids 和 table_names
        all_message_ids: Set[str] = set()
        table_message_ids: Dict[str, Set[str]] = defaultdict(set)
        
        for idx in all_indexes:
            all_message_ids.add(idx.id)
            table_message_ids[idx.table_name].add(idx.id)
        
        # 4. 按 table_name 批量查询各模式表
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
                logger.warning(
                    "[Sessions] 未知表名: %s, 错误: %s",
                    summarize_text_for_log(table_name, label="table"),
                    summarize_text_for_log(e, label="error"),
                )
                continue
        
        # 5. 批量查询所有附件
        attachments_by_message: Dict[str, List[MessageAttachment]] = defaultdict(list)
        
        if all_message_ids:
            all_attachments = db.query(MessageAttachment).filter(
                MessageAttachment.message_id.in_(list(all_message_ids)),
                MessageAttachment.user_id == user_id
            ).all()
            
            for att in all_attachments:
                attachments_by_message[att.message_id].append(att)
        
        # 6. 组装每个会话的结果
        result = []
        
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
                # ✅ 使用 v3 查询逻辑
                session_dict["messages"] = assemble_messages_v3(
                    session.id,
                    session_indexes,
                    messages_by_table,
                    attachments_by_message
                )
            else:
                # 无消息数据
                session_dict["messages"] = []
            
            result.append(session_dict)
        
        return result
    
    # 使用缓存（TTL: 5 分钟）
    try:
        sessions = await cache_service.get_or_set(
            cache_key,
            fetch_sessions,
            ttl=300
        )
        return sessions
    except Exception as e:
        logger.warning(
            "[Sessions] 缓存获取失败，使用直接查询: %s",
            summarize_text_for_log(e, label="error"),
        )
        # 缓存失败时，直接查询数据库
        return await fetch_sessions()



@router.post(
    "/sessions",
    responses={200: {"model": SessionResponse, "description": "Created or updated session"}},
)
async def create_or_update_session(
    session_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    """
    创建或更新会话 (v3 架构)
    
    实现逻辑：
    1. upsert ChatSession 元数据
    2. 收敛删除：计算 existing_ids - posted_ids，删除前端已移除的消息
    3. 取消关联的 UploadTask（避免孤儿记录）
    4. 使用内存字典 mode_last_msg 构建 parent_id
    5. 增量 upsert 消息到对应模式表
    6. 增量 upsert 附件到 message_attachments
    7. 实现云 URL 保护逻辑（优先级：UploadTask > 旧附件 > 前端）
    
    注意：更新消息时会保留已上传完成的附件 URL，避免前端覆盖后端的上传结果
    """
    user_query = UserScopedQuery(db, user_id)
    session_id = session_data.get("id")
    new_messages = session_data.get("messages", [])
    posted_mode = session_data.get("mode")

    # 1. upsert ChatSession
    session = user_query.get(DBChatSession, session_id)

    if session:
        # 更新现有会话元数据
        # Sprint 3 方案 1: mode 在创建后不可变(per-mode session 完全独立)
        if posted_mode is not None and posted_mode != session.mode:
            raise HTTPException(
                status_code=409,
                detail=f"session.mode is immutable (existing={session.mode!r}, posted={posted_mode!r})"
            )
        session.title = session_data.get("title", session.title)
        session.persona_id = session_data.get("persona_id", session.persona_id)
    else:
        # 创建新会话: mode 必填
        if not posted_mode or not isinstance(posted_mode, str) or not posted_mode.strip():
            raise HTTPException(
                status_code=400,
                detail="session.mode is required when creating a new session (Sprint 3: per-mode independence)"
            )
        session = DBChatSession(
            id=session_id,
            user_id=user_id,
            title=session_data.get("title", "新对话"),
            created_at=session_data.get("created_at", int(datetime.now().timestamp() * 1000)),
            persona_id=session_data.get("persona_id"),
            mode=posted_mode.strip()
        )
        db.add(session)
    
    # 2. 收敛删除：计算需要删除的消息
    posted_ids = {msg["id"] for msg in new_messages}
    
    existing_indexes = db.query(MessageIndex).filter(
        MessageIndex.session_id == session_id,
        MessageIndex.user_id == user_id
    ).all()
    existing_ids = {idx.id for idx in existing_indexes}
    
    deleted_ids = existing_ids - posted_ids
    
    if deleted_ids:
        # 按 table_name 分组
        deleted_indexes = [idx for idx in existing_indexes if idx.id in deleted_ids]
        tables_to_delete: Dict[str, List[str]] = defaultdict(list)
        for idx in deleted_indexes:
            tables_to_delete[idx.table_name].append(idx.id)
        
        # ✅ 先查询需要取消的上传任务（必须在删除附件之前）
        deleted_attachments = db.query(MessageAttachment).filter(
            MessageAttachment.message_id.in_(list(deleted_ids)),
            MessageAttachment.user_id == user_id
        ).all()
        deleted_attachment_ids = [att.id for att in deleted_attachments]
        
        # ✅ 取消关联的上传任务（避免孤儿记录）
        if deleted_attachment_ids:
            db.query(UploadTask).filter(
                UploadTask.attachment_id.in_(deleted_attachment_ids)
            ).update({
                "status": "cancelled",
                "error_message": "附件已被删除"
            }, synchronize_session=False)
        
        # 删除模式表消息
        for table_name, ids in tables_to_delete.items():
            try:
                table_class = get_message_table_class_by_name(table_name)
                db.query(table_class).filter(table_class.id.in_(ids)).delete(synchronize_session=False)
            except ValueError:
                logger.warning(f"[Sessions] 删除时未知表名: {table_name}")
        
        # 删除索引表
        db.query(MessageIndex).filter(MessageIndex.id.in_(list(deleted_ids)), MessageIndex.user_id == user_id).delete(synchronize_session=False)
        
        # 删除附件
        db.query(MessageAttachment).filter(MessageAttachment.message_id.in_(list(deleted_ids)), MessageAttachment.user_id == user_id).delete(synchronize_session=False)
        # 删除历史状态（收藏等 UI 状态）
        db.query(MessageHistoryState).filter(
            MessageHistoryState.user_id == user_id,
            MessageHistoryState.message_id.in_(list(deleted_ids))
        ).delete(synchronize_session=False)

        logger.info(f"[Sessions] 收敛删除: 删除了 {len(deleted_ids)} 条消息")
    
    # 3. 预查询：获取所有现有附件和已完成的上传任务（用于云 URL 保护）
    current_attachment_ids = []
    for msg in new_messages:
        for att in msg.get("attachments", []):
            if att.get("id"):
                current_attachment_ids.append(att["id"])
    
    # 查询现有附件
    existing_attachments: Dict[str, MessageAttachment] = {}
    if current_attachment_ids:
        atts = db.query(MessageAttachment).filter(
            MessageAttachment.id.in_(current_attachment_ids),
            MessageAttachment.user_id == user_id
        ).all()
        existing_attachments = {att.id: att for att in atts}
    
    # 查询已完成的上传任务
    completed_tasks: Dict[str, UploadTask] = {}
    owned_current_attachment_ids = list(existing_attachments.keys())
    if owned_current_attachment_ids:
        tasks = db.query(UploadTask).filter(
            UploadTask.attachment_id.in_(owned_current_attachment_ids),
            UploadTask.status == 'completed',
            UploadTask.target_url.isnot(None)
        ).all()
        completed_tasks = {task.attachment_id: task for task in tasks}
    
    # 4. 增量 upsert 消息（使用内存构建 parent_id）
    mode_last_msg: Dict[str, str] = {}  # 内存追踪每个模式的最后一条消息 ID

    # ── 批量预加载（消除 N+1 查询）──
    new_message_ids = {msg["id"] for msg in new_messages}

    # 预加载 MessageIndex
    _preloaded_indexes: Dict[str, MessageIndex] = {}
    if new_message_ids:
        _idx_rows = db.query(MessageIndex).filter(
            MessageIndex.id.in_(list(new_message_ids)),
            MessageIndex.user_id == user_id
        ).all()
        _preloaded_indexes = {idx.id: idx for idx in _idx_rows}

    # 预加载模式表消息（按 table_name 分组）
    _preloaded_mode_msgs: Dict[str, Dict[str, Any]] = {}
    _table_msg_ids: Dict[str, set] = defaultdict(set)
    for msg in new_messages:
        _tn = get_table_name_for_mode(msg.get("mode", "chat"))
        _table_msg_ids[_tn].add(msg["id"])
    for _tn, _ids in _table_msg_ids.items():
        try:
            _tc = get_message_table_class_by_name(_tn)
            _rows = db.query(_tc).filter(_tc.id.in_(list(_ids))).all()
            _preloaded_mode_msgs[_tn] = {r.id: r for r in _rows}
        except ValueError as e:
            # 未知 mode 名 → 此 table 的预加载跳过；下游会回落到逐条 INSERT。
            # 保留 warning 让运维感知不合规的 mode 值，避免重复数据沉默写入。
            logger.warning(
                "[sessions] skip preload for unknown mode table %s: %s",
                summarize_text_for_log(_tn, label="table"),
                summarize_text_for_log(e, label="error"),
            )

    # 预加载附件（按 (message_id, att_id) 索引）
    _preloaded_atts: Dict[tuple, MessageAttachment] = {}
    _all_att_pairs = []
    for msg in new_messages:
        for att in msg.get("attachments", []):
            if att.get("id"):
                _all_att_pairs.append((msg["id"], att["id"]))
    if _all_att_pairs:
        _att_ids_set = list({aid for _, aid in _all_att_pairs})
        _msg_ids_set = list({mid for mid, _ in _all_att_pairs})
        _att_rows = db.query(MessageAttachment).filter(
            MessageAttachment.id.in_(_att_ids_set),
            MessageAttachment.message_id.in_(_msg_ids_set),
            MessageAttachment.user_id == user_id
        ).all()
        for _a in _att_rows:
            _preloaded_atts[(_a.message_id, _a.id)] = _a
    # ── 批量预加载结束 ──

    for seq, msg in enumerate(new_messages):
        msg_id = msg["id"]
        mode = msg.get("mode", "chat")
        timestamp = msg.get("timestamp", int(datetime.now().timestamp() * 1000))

        # Sprint 3 方案 1: 强制 message.mode == session.mode
        # 拒绝跨 mode 写入(如把 image-gen 的消息写入 chat session)
        if mode != session.mode:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"message.mode={mode!r} mismatches session.mode={session.mode!r} "
                    f"(msg_id={msg_id!r}); cross-mode messages are not allowed under per-mode session model"
                )
            )

        # 确定 table_name
        table_name = get_table_name_for_mode(mode)

        # 从内存获取 parent_id（而非查询 DB）
        parent_id = mode_last_msg.get(mode)

        # upsert message_index（从预加载字典查找）
        index = _preloaded_indexes.get(msg_id)
        if not index:
            index = MessageIndex(
                id=msg_id,
                session_id=session_id,
                user_id=user_id,
                mode=mode,
                table_name=table_name,
                seq=seq,
                timestamp=timestamp,
                parent_id=parent_id
            )
            db.add(index)
        else:
            index.seq = seq
            index.parent_id = parent_id
            index.mode = mode
            index.table_name = table_name

        # upsert 模式表（从预加载字典查找）
        table_class = get_message_table_class_by_name(table_name)
        message = _preloaded_mode_msgs.get(table_name, {}).get(msg_id)

        # ✅ 调试：检查 thoughts/text_response/enhanced_prompt 是否存在于消息中
        extracted_meta = extract_metadata(msg)
        if extracted_meta:
            # 只记录关键字段，不记录完整内容
            meta_keys = list(extracted_meta.keys())
            has_thoughts = 'thoughts' in extracted_meta
            has_text_response = 'text_response' in extracted_meta
            has_enhanced_prompt = 'enhanced_prompt' in extracted_meta
            logger.debug("[Sessions] 消息 %s 的 metadata 字段: %s, thoughts=%s, text_response=%s, enhanced_prompt=%s",
                         msg_id, meta_keys, has_thoughts, has_text_response, has_enhanced_prompt)

        metadata_json = json.dumps(extracted_meta) if extracted_meta else None
        
        if not message:
            # 创建新消息
            message = table_class(
                id=msg_id,
                session_id=session_id,
                user_id=user_id,  # ✅ 添加 user_id
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=timestamp,
                is_error=msg.get("isError", False),
                metadata_json=metadata_json
            )
            db.add(message)
        else:
            # 更新消息
            message.content = msg.get("content", "")
            message.is_error = msg.get("is_error", False)
            message.metadata_json = metadata_json

        # ✅ image-chat-edit: persist enhanced prompt into edit_prompt if available
        if hasattr(message, "edit_prompt"):
            enhanced_prompt_value = msg.get("enhanced_prompt") or msg.get("edit_prompt")
            if enhanced_prompt_value:
                message.edit_prompt = enhanced_prompt_value

        if hasattr(message, "model_name"):
            model_name_value = (
                msg.get("model_name")
                or msg.get("model_id")
                or msg.get("mode_model_id")
            )
            if model_name_value:
                message.model_name = str(model_name_value)
        
        # 5. upsert 附件（云 URL 保护逻辑）
        for att in msg.get("attachments", []):
            att_id = att.get("id")
            if not att_id:
                continue
            
            # ✅ 确定权威 URL（优先级：UploadTask > 旧附件 > 前端）
            authoritative_url = None
            
            # 优先级 1：已完成的上传任务
            task = completed_tasks.get(att_id)
            if task and task.target_url:
                authoritative_url = task.target_url
            
            # 优先级 2：数据库已有的云 URL
            if not authoritative_url:
                existing_att = existing_attachments.get(att_id)
                if existing_att and existing_att.url and is_http_url(existing_att.url):
                    authoritative_url = existing_att.url
            
            # 处理前端发送的 URL（Sprint 2 PR-1: 后端权威清洗）
            frontend_url = att.get("url", "")
            frontend_url_is_temp = (
                not frontend_url or is_blob_url(frontend_url) or is_base64_url(frontend_url)
            )
            if frontend_url_is_temp:
                # 前端 URL 是临时的(blob:/data:);有 authoritative_url 用它,否则强制清空。
                # 不能把 base64 字符串写入 url 字段——会污染 DB 且超长。
                final_url = authoritative_url if authoritative_url else ""
            else:
                # 前端发送的是 HTTP URL,直接使用
                final_url = frontend_url

            # upload_status 权威推导(覆盖前端可能传的 'completed' + blob 这类不一致):
            # - final_url 是 http:// 且有 completed task → 'completed'
            # - final_url 是 http:// 但无 task → 信任前端 status
            # - 否则 → 'pending'
            if (task and task.target_url) and final_url and is_http_url(final_url):
                derived_upload_status = "completed"
            elif final_url and is_http_url(final_url):
                derived_upload_status = att.get("upload_status", "pending")
            else:
                derived_upload_status = "pending"

            # temp_url 权威清洗:仅保留有效的非临时 HTTP URL
            frontend_temp_url = att.get("temp_url") or None
            if frontend_temp_url:
                temp_is_invalid = (
                    not is_http_url(frontend_temp_url)
                    or "/temp/" in frontend_temp_url
                    or "expires=" in frontend_temp_url
                )
                if temp_is_invalid:
                    frontend_temp_url = None

            # upsert 附件表（从预加载字典查找）
            attachment = _preloaded_atts.get((msg_id, att_id))
            if not attachment:
                attachment = MessageAttachment(
                    id=att_id,
                    session_id=session_id,
                    user_id=user_id,
                    message_id=msg_id,
                    mime_type=att.get("mime_type"),
                    name=att.get("name"),
                    url=final_url,
                    temp_url=frontend_temp_url,
                    file_uri=att.get("file_uri"),
                    upload_status=derived_upload_status,
                    upload_task_id=task.id if task else None,
                    google_file_uri=att.get("google_file_uri"),
                    google_file_expiry=att.get("google_file_expiry"),
                    size=att.get("size")
                )
                db.add(attachment)
            else:
                # 更新附件（保护云 URL）
                if final_url and is_http_url(final_url):
                    attachment.url = final_url
                    attachment.upload_status = 'completed'
                    attachment.temp_url = None
                else:
                    # 保持原有 URL 不变
                    pass
                
                # 更新其他字段
                attachment.message_id = msg_id
                attachment.mime_type = att.get("mime_type") or attachment.mime_type
                attachment.name = att.get("name") or attachment.name
                attachment.file_uri = att.get("file_uri") or attachment.file_uri
                attachment.google_file_uri = att.get("google_file_uri") or attachment.google_file_uri
                attachment.google_file_expiry = att.get("google_file_expiry") or attachment.google_file_expiry
                attachment.size = att.get("size") or attachment.size
        
        # ✅ 更新内存记录
        mode_last_msg[mode] = msg_id
    
    db.commit()
    db.refresh(session)
    
    # ✅ 清除会话列表缓存
    try:
        from ...services.common.cache_service import CacheService
        cache_service: CacheService = cache
        # 通配清除该用户下所有 mode 变体的缓存(Sprint 3 per-mode key)
        cache_pattern = cache_service._make_key("sessions", user_id, "*")
        await cache_service.delete(cache_pattern)
        logger.debug(f"[Sessions] 已清除缓存(通配): {cache_pattern}")
    except Exception as e:
        logger.warning(
            "[Sessions] 清除缓存失败: %s",
            summarize_text_for_log(e, label="error"),
        )
    
    # 返回更新后的会话（使用 v3 查询逻辑）
    return await get_session_by_id(session_id, user_id, db)



@router.get(
    "/sessions/{session_id}",
    responses={200: {"model": SessionResponse, "description": "Session detail"}},
)
@case_conversion_options(always_convert_response=True)
async def get_session(
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取单个会话的完整数据（包含消息内容）
    
    用于用户选择会话时按需加载消息（不能分页，必须完整）
    
    返回：
    {
        "id": str,
        "title": str,
        "messages": [...],  # 完整消息列表（不能分页）
        "createdAt": int,
        "personaId": str | null,
        "mode": str | null
    }
    """
    return await get_session_by_id(session_id, user_id, db)


async def get_session_by_id(session_id: str, user_id: str, db: Session) -> Dict[str, Any]:
    """
    获取单个会话的完整数据 (v3 架构)
    
    内部辅助函数，用于按需加载会话的完整消息（不能分页）
    """
    user_query = UserScopedQuery(db, user_id)
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 查询消息索引
    indexes = db.query(MessageIndex).filter(
        MessageIndex.session_id == session_id,
        MessageIndex.user_id == user_id
    ).order_by(MessageIndex.seq.asc()).all()
    
    if indexes:
        # 收集 message_ids 和 table_names
        message_ids = [idx.id for idx in indexes]
        table_message_ids: Dict[str, Set[str]] = defaultdict(set)
        for idx in indexes:
            table_message_ids[idx.table_name].add(idx.id)
        
        # 批量查询模式表
        messages_by_table: Dict[str, Dict[str, Any]] = {}
        for table_name, msg_ids in table_message_ids.items():
            try:
                table_class = get_message_table_class_by_name(table_name)
                messages = db.query(table_class).filter(
                    table_class.id.in_(list(msg_ids))
                ).all()
                messages_by_table[table_name] = {msg.id: msg for msg in messages}
            except ValueError:
                continue
        
        # 批量查询附件
        attachments_by_message: Dict[str, List[MessageAttachment]] = defaultdict(list)
        attachments = db.query(MessageAttachment).filter(
            MessageAttachment.message_id.in_(message_ids),
            MessageAttachment.user_id == user_id
        ).all()
        for att in attachments:
            attachments_by_message[att.message_id].append(att)
        
        # 组装消息
        messages = assemble_messages_v3(
            session_id,
            indexes,
            messages_by_table,
            attachments_by_message
        )
    else:
        # 无消息数据
        messages = []
    
    return {
        "id": session.id,
        "title": session.title,
        "messages": messages,
        "created_at": session.created_at,
        "persona_id": session.persona_id,
        "mode": session.mode
    }




@router.delete(
    "/sessions/{session_id}",
    responses={200: {"model": DeleteSessionResponse, "description": "Session deleted"}},
)
async def delete_session(
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    """
    删除会话 (v3 架构)
    
    级联删除：
    1. 删除会话关联的所有消息索引
    2. 删除各模式表中的消息
    3. 删除附件
    4. 取消关联的上传任务
    5. 删除会话本身
    """
    user_query = UserScopedQuery(db, user_id)
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 1. 查询所有消息索引
    indexes = db.query(MessageIndex).filter(
        MessageIndex.session_id == session_id,
        MessageIndex.user_id == user_id
    ).all()
    
    if indexes:
        message_ids = [idx.id for idx in indexes]
        
        # 按 table_name 分组
        tables_to_delete: Dict[str, List[str]] = defaultdict(list)
        for idx in indexes:
            tables_to_delete[idx.table_name].append(idx.id)
        
        # 2. 查询并取消关联的上传任务
        attachments = db.query(MessageAttachment).filter(
            MessageAttachment.message_id.in_(message_ids),
            MessageAttachment.user_id == user_id
        ).all()
        attachment_ids = [att.id for att in attachments]
        
        if attachment_ids:
            db.query(UploadTask).filter(
                UploadTask.attachment_id.in_(attachment_ids)
            ).update({
                "status": "cancelled",
                "error_message": "会话已被删除"
            }, synchronize_session=False)
        
        # 3. 删除模式表消息
        for table_name, ids in tables_to_delete.items():
            try:
                table_class = get_message_table_class_by_name(table_name)
                db.query(table_class).filter(table_class.id.in_(ids)).delete(synchronize_session=False)
            except ValueError:
                logger.warning(f"[Sessions] 删除时未知表名: {table_name}")
        
        # 4. 删除索引表
        db.query(MessageIndex).filter(MessageIndex.session_id == session_id, MessageIndex.user_id == user_id).delete(synchronize_session=False)
        
        # 5. 删除附件
        db.query(MessageAttachment).filter(MessageAttachment.session_id == session_id, MessageAttachment.user_id == user_id).delete(synchronize_session=False)

    # 删除历史状态（收藏等 UI 状态）
    db.query(MessageHistoryState).filter(
        MessageHistoryState.session_id == session_id,
        MessageHistoryState.user_id == user_id
    ).delete(synchronize_session=False)
    # 删除历史偏好（仅收藏开关等）
    db.query(SessionHistoryPreference).filter(
        SessionHistoryPreference.session_id == session_id,
        SessionHistoryPreference.user_id == user_id
    ).delete(synchronize_session=False)
    
    # 6. 删除会话本身
    db.delete(session)
    db.commit()
    
    # ✅ 清除会话列表缓存
    try:
        from ...services.common.cache_service import CacheService
        cache_service: CacheService = cache
        # 通配清除该用户下所有 mode 变体的缓存(Sprint 3 per-mode key)
        cache_pattern = cache_service._make_key("sessions", user_id, "*")
        await cache_service.delete(cache_pattern)
        logger.debug(f"[Sessions] 已清除缓存(通配): {cache_pattern}")
    except Exception as e:
        logger.warning(
            "[Sessions] 清除缓存失败: %s",
            summarize_text_for_log(e, label="error"),
        )

    return {"success": True}


@router.get(
    "/sessions/{session_id}/history-states",
    responses={
        200: {"model": SessionHistoryStatesResponse, "description": "Session history states"}
    },
)
@case_conversion_options(always_convert_response=True)
async def get_session_history_states(
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取会话历史列表状态（当前包含收藏状态）
    """
    user_query = UserScopedQuery(db, user_id)
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    states = db.query(MessageHistoryState).filter(
        MessageHistoryState.session_id == session_id,
        MessageHistoryState.user_id == user_id,
        MessageHistoryState.is_favorite.is_(True)
    ).all()

    return {
        "states": [
            {
                "message_id": state.message_id,
                "is_favorite": bool(state.is_favorite),
                "updated_at": state.updated_at
            }
            for state in states
        ]
    }


@router.patch(
    "/sessions/{session_id}/history-states/{message_id}",
    responses={
        200: {"model": SessionHistoryStateResponse, "description": "Updated history state"}
    },
)
async def update_session_history_state(
    session_id: str,
    message_id: str,
    payload: HistoryStateUpdateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    更新会话历史项状态（当前支持收藏开关）
    """
    if payload.is_favorite is None:
        raise HTTPException(status_code=400, detail="至少需要提供 is_favorite 字段")

    user_query = UserScopedQuery(db, user_id)
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    message_index = db.query(MessageIndex.id).filter(
        MessageIndex.id == message_id,
        MessageIndex.session_id == session_id,
        MessageIndex.user_id == user_id
    ).first()
    if not message_index:
        raise HTTPException(status_code=404, detail="历史项不存在")

    now_ms = int(datetime.now().timestamp() * 1000)
    if payload.is_favorite:
        state = db.query(MessageHistoryState).filter(
            MessageHistoryState.session_id == session_id,
            MessageHistoryState.user_id == user_id,
            MessageHistoryState.message_id == message_id
        ).first()
        if not state:
            state = MessageHistoryState(
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                is_favorite=True,
                created_at=now_ms,
                updated_at=now_ms
            )
            db.add(state)
        else:
            state.is_favorite = True
            state.updated_at = now_ms
    else:
        db.query(MessageHistoryState).filter(
            MessageHistoryState.session_id == session_id,
            MessageHistoryState.user_id == user_id,
            MessageHistoryState.message_id == message_id
        ).delete(synchronize_session=False)

    db.commit()

    return {
        "message_id": message_id,
        "is_favorite": bool(payload.is_favorite),
        "updated_at": now_ms
    }


@router.get(
    "/sessions/{session_id}/history-preferences",
    responses={
        200: {
            "model": SessionHistoryPreferenceResponse,
            "description": "Session history preferences",
        }
    },
)
async def get_session_history_preferences(
    session_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取会话历史偏好（当前包含“仅收藏”开关）
    """
    user_query = UserScopedQuery(db, user_id)
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    pref = db.query(SessionHistoryPreference).filter(
        SessionHistoryPreference.session_id == session_id,
        SessionHistoryPreference.user_id == user_id
    ).first()

    if not pref:
        return {
            "show_favorites_only": False,
            "updated_at": None
        }

    return {
        "show_favorites_only": bool(pref.show_favorites_only),
        "updated_at": pref.updated_at
    }


@router.patch(
    "/sessions/{session_id}/history-preferences",
    responses={
        200: {
            "model": SessionHistoryPreferenceResponse,
            "description": "Updated session history preferences",
        }
    },
)
async def update_session_history_preferences(
    session_id: str,
    payload: HistoryPreferenceUpdateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    更新会话历史偏好（当前支持“仅收藏”开关）
    """
    if payload.show_favorites_only is None:
        raise HTTPException(status_code=400, detail="至少需要提供 show_favorites_only 字段")

    user_query = UserScopedQuery(db, user_id)
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    now_ms = int(datetime.now().timestamp() * 1000)
    pref = db.query(SessionHistoryPreference).filter(
        SessionHistoryPreference.session_id == session_id,
        SessionHistoryPreference.user_id == user_id
    ).first()

    if not pref:
        pref = SessionHistoryPreference(
            user_id=user_id,
            session_id=session_id,
            show_favorites_only=bool(payload.show_favorites_only),
            created_at=now_ms,
            updated_at=now_ms
        )
        db.add(pref)
    else:
        pref.show_favorites_only = bool(payload.show_favorites_only)
        pref.updated_at = now_ms

    db.commit()

    return {
        "show_favorites_only": bool(payload.show_favorites_only),
        "updated_at": now_ms
    }



@router.get(
    "/sessions/{session_id}/attachments/{attachment_id}",
    responses={
        200: {"model": SessionAttachmentResponse, "description": "Session attachment detail"}
    },
)
async def get_attachment(
    session_id: str,
    attachment_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    查询附件的最新信息 (v3 架构)
    
    从 message_attachments 表直接查询，联查 UploadTask 获取最新云 URL
    
    返回：
    {
        "id": "att-xxx",
        "url": "https://img.dicry.com/xxx.png",
        "upload_status": "completed",
        "mime_type": "image/png",
        "name": "image.png",
        "task_id": "task-xxx",
        "task_status": "completed"
    }
    """
    user_query = UserScopedQuery(db, user_id)
    # 1. 验证会话存在
    session = user_query.get(DBChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 2. 从 message_attachments 表查询附件
    attachment = db.query(MessageAttachment).filter(
        MessageAttachment.session_id == session_id,
        MessageAttachment.id == attachment_id,
        MessageAttachment.user_id == user_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    # 3. 查询关联的上传任务
    if attachment.upload_task_id:
        task = db.query(UploadTask).filter(UploadTask.id == attachment.upload_task_id).first()
    else:
        task = (
            db.query(UploadTask)
            .filter(UploadTask.attachment_id == attachment_id)
            .order_by(UploadTask.created_at.desc())
            .first()
        )
    
    # 4. 构建返回结果
    result = attachment.to_dict()
    
    # 如果有关联的上传任务，添加任务信息
    if task:
        result["task_id"] = task.id
        result["task_status"] = task.status
        logger.debug(
            "[Sessions] 找到上传任务: task_id=%s, status=%s, target_url=%s",
            task.id,
            task.status,
            _summarize_url_for_log(task.target_url),
        )
        
        # 如果任务已完成且有目标 URL，优先使用任务的 URL
        if task.status == 'completed' and task.target_url:
            result["url"] = task.target_url
            result["upload_status"] = 'completed'
            logger.debug("[Sessions] 使用任务的 target_url 作为最终 URL")
    
    logger.debug(
        "[Sessions] 查询附件: %s -> url=%s, upload_status=%s",
        attachment_id,
        _summarize_url_for_log(result.get("url")),
        result.get("upload_status"),
    )
    return result
