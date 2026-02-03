"""
会话管理路由 (v3 架构)

v3 架构采用"按模式分表 + 消息索引表"设计：
- message_index: 消息索引表，存储消息路由信息
- messages_chat/messages_image_gen/messages_video_gen/messages_generic: 模式表
- message_attachments: 附件表
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Set
from datetime import datetime
from collections import defaultdict
import json
import copy
import logging

logger = logging.getLogger(__name__)

from ...core.database import SessionLocal, get_db
from ...models.db_models import (
    ChatSession as DBChatSession,
    MessageIndex,
    MessageAttachment,
    UploadTask
)
from ...utils.message_utils import (
    get_table_name_for_mode,
    get_message_table_class_by_name,
    extract_metadata
)
from ...core.dependencies import require_current_user, get_cache
from ...core.user_scoped_query import UserScopedQuery
from ...utils.message_assembly import assemble_messages_v3


router = APIRouter(prefix="/api", tags=["sessions"])


# ==================== v3 辅助函数（已移至 utils/message_assembly.py）====================

# 已删除重复的 assemble_messages_v3 函数
# 现在使用统一的实现：utils/message_assembly.py


# ==================== 会话管理 ====================

@router.get("/sessions")
async def get_sessions(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    """
    获取所有会话 (v3 架构，带 Redis 缓存)
    
    查询逻辑：
    1. 查询所有 ChatSession
    2. 批量查询 MessageIndex（按 session_id, seq 排序）
    3. 按 table_name 分组批量查询各模式表
    4. 批量查询 MessageAttachment
    5. 按 seq 顺序组装 messages 数组
    
    缓存策略：
    - 缓存键：cache:sessions:{user_id}
    - TTL：5 分钟（300 秒）
    - 失效时机：创建/更新/删除会话时
    """
    from ...services.common.cache_service import CacheService
    cache_service: CacheService = cache
    
    # 生成缓存键
    cache_key = cache_service._make_key("sessions", user_id)
    
    # 定义数据获取函数
    async def fetch_sessions():
        user_query = UserScopedQuery(db, user_id)

        # 1. 查询所有会话
        sessions = user_query.get_all(DBChatSession)
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
                print(f"[Sessions] ⚠️ 未知表名: {table_name}, 错误: {e}")
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
        logger.warning(f"[Sessions] 缓存获取失败，使用直接查询: {e}")
        # 缓存失败时，直接查询数据库
        return await fetch_sessions()



@router.post("/sessions")
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
    
    # 1. upsert ChatSession
    session = user_query.get(DBChatSession, session_id)
    
    if session:
        # 更新现有会话元数据
        session.title = session_data.get("title", session.title)
        session.persona_id = session_data.get("persona_id", session.persona_id)
        session.mode = session_data.get("mode", session.mode)
    else:
        # 创建新会话
        session = DBChatSession(
            id=session_id,
            user_id=user_id,
            title=session_data.get("title", "新对话"),
            created_at=session_data.get("created_at", int(datetime.now().timestamp() * 1000)),
            persona_id=session_data.get("persona_id"),
            mode=session_data.get("mode")
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
                print(f"[Sessions] ⚠️ 删除时未知表名: {table_name}")
        
        # 删除索引表
        db.query(MessageIndex).filter(MessageIndex.id.in_(list(deleted_ids)), MessageIndex.user_id == user_id).delete(synchronize_session=False)
        
        # 删除附件
        db.query(MessageAttachment).filter(MessageAttachment.message_id.in_(list(deleted_ids)), MessageAttachment.user_id == user_id).delete(synchronize_session=False)
        
        print(f"[Sessions] 收敛删除: 删除了 {len(deleted_ids)} 条消息")
    
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
    if current_attachment_ids:
        tasks = db.query(UploadTask).filter(
            UploadTask.attachment_id.in_(current_attachment_ids),
            UploadTask.status == 'completed',
            UploadTask.target_url.isnot(None)
        ).all()
        completed_tasks = {task.attachment_id: task for task in tasks}
    
    # 4. 增量 upsert 消息（使用内存构建 parent_id）
    mode_last_msg: Dict[str, str] = {}  # ✅ 内存追踪每个模式的最后一条消息 ID
    
    for seq, msg in enumerate(new_messages):
        msg_id = msg["id"]
        mode = msg.get("mode", "chat")
        timestamp = msg.get("timestamp", int(datetime.now().timestamp() * 1000))
        
        # 确定 table_name
        table_name = get_table_name_for_mode(mode)
        
        # ✅ 从内存获取 parent_id（而非查询 DB）
        parent_id = mode_last_msg.get(mode)
        
        # upsert message_index
        index = db.query(MessageIndex).filter(MessageIndex.id == msg_id, MessageIndex.user_id == user_id).first()
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
        
        # upsert 模式表
        table_class = get_message_table_class_by_name(table_name)
        message = db.query(table_class).get(msg_id)

        # ✅ 调试：检查 thoughts/text_response/enhanced_prompt 是否存在于消息中
        extracted_meta = extract_metadata(msg)
        if extracted_meta:
            # 只记录关键字段，不记录完整内容
            meta_keys = list(extracted_meta.keys())
            has_thoughts = 'thoughts' in extracted_meta
            has_text_response = 'text_response' in extracted_meta
            has_enhanced_prompt = 'enhanced_prompt' in extracted_meta
            logger.info(f"[Sessions] 📝 消息 {msg_id} 的 metadata 字段: {meta_keys}, thoughts={has_thoughts}, text_response={has_text_response}, enhanced_prompt={has_enhanced_prompt}")

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
                if existing_att and existing_att.url and existing_att.url.startswith('http'):
                    authoritative_url = existing_att.url
            
            # 处理前端发送的 URL
            frontend_url = att.get("url", "")
            if not frontend_url or frontend_url.startswith("blob:") or frontend_url.startswith("data:"):
                # 前端 URL 是临时的，使用权威 URL
                final_url = authoritative_url or frontend_url
            else:
                # 前端发送的是永久 URL，直接使用
                final_url = frontend_url
            
            # upsert 附件表（复合主键：id + message_id）
            # 先查询是否存在该附件（可能在其他消息中）
            attachment = db.query(MessageAttachment).filter(
                MessageAttachment.id == att_id,
                MessageAttachment.message_id == msg_id,
                MessageAttachment.user_id == user_id
            ).first()
            if not attachment:
                attachment = MessageAttachment(
                    id=att_id,
                    session_id=session_id,
                    user_id=user_id,
                    message_id=msg_id,
                    mime_type=att.get("mime_type"),
                    name=att.get("name"),
                    url=final_url,
                    temp_url=att.get("temp_url"),
                    file_uri=att.get("file_uri"),
                    upload_status=att.get("upload_status", "pending"),
                    upload_task_id=task.id if task else None,
                    google_file_uri=att.get("google_file_uri"),
                    google_file_expiry=att.get("google_file_expiry"),
                    size=att.get("size")
                )
                db.add(attachment)
            else:
                # 更新附件（保护云 URL）
                if final_url and final_url.startswith('http'):
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
        cache_key = cache_service._make_key("sessions", user_id)
        await cache_service.delete(cache_key)
        logger.debug(f"[Sessions] 已清除缓存: {cache_key}")
    except Exception as e:
        logger.warning(f"[Sessions] 清除缓存失败: {e}")
    
    # 返回更新后的会话（使用 v3 查询逻辑）
    return await get_session_by_id(session_id, user_id, db)



@router.get("/sessions/{session_id}")
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




@router.delete("/sessions/{session_id}")
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
                print(f"[Sessions] ⚠️ 删除时未知表名: {table_name}")
        
        # 4. 删除索引表
        db.query(MessageIndex).filter(MessageIndex.session_id == session_id, MessageIndex.user_id == user_id).delete(synchronize_session=False)
        
        # 5. 删除附件
        db.query(MessageAttachment).filter(MessageAttachment.session_id == session_id, MessageAttachment.user_id == user_id).delete(synchronize_session=False)
    
    # 6. 删除会话本身
    db.delete(session)
    db.commit()
    
    # ✅ 清除会话列表缓存
    try:
        from ...services.common.cache_service import CacheService
        cache_service: CacheService = cache
        cache_key = cache_service._make_key("sessions", user_id)
        await cache_service.delete(cache_key)
        logger.debug(f"[Sessions] 已清除缓存: {cache_key}")
    except Exception as e:
        logger.warning(f"[Sessions] 清除缓存失败: {e}")

    return {"success": True}



@router.get("/sessions/{session_id}/attachments/{attachment_id}")
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
    task = db.query(UploadTask).filter(
        UploadTask.attachment_id == attachment_id
    ).first()
    
    # 4. 构建返回结果
    result = attachment.to_dict()
    
    # 如果有关联的上传任务，添加任务信息
    if task:
        result["task_id"] = task.id
        result["task_status"] = task.status
        print(f"[Sessions] 找到上传任务: task_id={task.id}, status={task.status}, target_url={task.target_url if task.target_url else 'None'}")
        
        # 如果任务已完成且有目标 URL，优先使用任务的 URL
        if task.status == 'completed' and task.target_url:
            result["url"] = task.target_url
            result["upload_status"] = 'completed'
            print(f"[Sessions] ✅ 使用任务的 target_url 作为最终 URL")
    
    print(f"[Sessions] 查询附件: {attachment_id} -> url: {result.get('url') if result.get('url') else 'None'}, upload_status: {result.get('upload_status')}")
    return result
