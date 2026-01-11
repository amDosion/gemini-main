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

from ..core.database import SessionLocal
from ..models.db_models import (
    ChatSession as DBChatSession,
    MessageIndex,
    MessageAttachment,
    UploadTask
)
from ..utils.message_utils import (
    get_table_name_for_mode,
    get_message_table_class_by_name,
    extract_metadata
)
from ..core.user_context import require_user_id
from ..core.user_scoped_query import UserScopedQuery


router = APIRouter(prefix="/api", tags=["sessions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== v3 辅助函数 ====================

def assemble_messages_v3(
    session_id: str,
    indexes: List[MessageIndex],
    messages_by_table: Dict[str, Dict[str, Any]],
    attachments_by_message: Dict[str, List[MessageAttachment]]
) -> List[Dict[str, Any]]:
    """
    组装单个会话的消息列表 (v3 架构)
    
    Args:
        session_id: 会话 ID
        indexes: 该会话的消息索引列表（已按 seq 排序）
        messages_by_table: {table_name: {msg_id: msg_obj}} 消息字典
        attachments_by_message: {message_id: [attachment_obj]} 附件字典
    
    Returns:
        组装后的消息列表
    """
    assembled_messages = []
    
    for idx in indexes:
        # 从模式表获取消息
        table_messages = messages_by_table.get(idx.table_name, {})
        msg = table_messages.get(idx.id)
        
        if not msg:
            # 数据不一致：索引存在但消息不存在，跳过
            print(f"[Sessions] ⚠️ 消息不存在: id={idx.id}, table={idx.table_name}")
            continue
        
        # 转换为字典
        msg_dict = msg.to_dict()
        
        # ✅ 关键：从索引表获取 mode 字段并赋值
        msg_dict['mode'] = idx.mode
        
        # 附加附件
        atts = attachments_by_message.get(idx.id, [])
        if atts:
            msg_dict['attachments'] = [att.to_dict() for att in atts]
        else:
            msg_dict['attachments'] = []
        
        assembled_messages.append(msg_dict)
    
    return assembled_messages


# ==================== 会话管理 ====================

@router.get("/sessions")
async def get_sessions(request: Request, db: Session = Depends(get_db)):
    """
    获取所有会话 (v3 架构)
    
    查询逻辑：
    1. 查询所有 ChatSession
    2. 批量查询 MessageIndex（按 session_id, seq 排序）
    3. 按 table_name 分组批量查询各模式表
    4. 批量查询 MessageAttachment
    5. 按 seq 顺序组装 messages 数组
    """
    user_id = require_user_id(request)
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
            "createdAt": session.created_at,
            "personaId": session.persona_id,
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



@router.post("/sessions")
async def create_or_update_session(session_data: dict, request: Request, db: Session = Depends(get_db)):
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
    user_id = require_user_id(request)
    user_query = UserScopedQuery(db, user_id)
    session_id = session_data.get("id")
    new_messages = session_data.get("messages", [])
    
    # 1. upsert ChatSession
    session = user_query.get(DBChatSession, session_id)
    
    if session:
        # 更新现有会话元数据
        session.title = session_data.get("title", session.title)
        session.persona_id = session_data.get("personaId", session.persona_id)
        session.mode = session_data.get("mode", session.mode)
    else:
        # 创建新会话
        session = DBChatSession(
            id=session_id,
            user_id=user_id,
            title=session_data.get("title", "新对话"),
            created_at=session_data.get("createdAt", int(datetime.now().timestamp() * 1000)),
            persona_id=session_data.get("personaId"),
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
        
        metadata_json = json.dumps(extract_metadata(msg)) if extract_metadata(msg) else None
        
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
            message.is_error = msg.get("isError", False)
            message.metadata_json = metadata_json
        
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
                    mime_type=att.get("mimeType"),
                    name=att.get("name"),
                    url=final_url,
                    temp_url=att.get("tempUrl"),
                    file_uri=att.get("fileUri"),
                    upload_status=att.get("uploadStatus", "pending"),
                    upload_task_id=task.id if task else None,
                    google_file_uri=att.get("googleFileUri"),
                    google_file_expiry=att.get("googleFileExpiry"),
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
                attachment.mime_type = att.get("mimeType") or attachment.mime_type
                attachment.name = att.get("name") or attachment.name
                attachment.file_uri = att.get("fileUri") or attachment.file_uri
                attachment.google_file_uri = att.get("googleFileUri") or attachment.google_file_uri
                attachment.google_file_expiry = att.get("googleFileExpiry") or attachment.google_file_expiry
                attachment.size = att.get("size") or attachment.size
        
        # ✅ 更新内存记录
        mode_last_msg[mode] = msg_id
    
    db.commit()
    db.refresh(session)
    
    # 返回更新后的会话（使用 v3 查询逻辑）
    return await get_session_by_id(session_id, request, db)



async def get_session_by_id(session_id: str, request: Request, db: Session) -> Dict[str, Any]:
    """
    获取单个会话的完整数据 (v3 架构)
    """
    user_id = require_user_id(request)
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
        "createdAt": session.created_at,
        "personaId": session.persona_id,
        "mode": session.mode
    }




@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, db: Session = Depends(get_db)):
    """
    删除会话 (v3 架构)
    
    级联删除：
    1. 删除会话关联的所有消息索引
    2. 删除各模式表中的消息
    3. 删除附件
    4. 取消关联的上传任务
    5. 删除会话本身
    """
    user_id = require_user_id(request)
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
    
    return {"success": True}



@router.get("/sessions/{session_id}/attachments/{attachment_id}")
async def get_attachment(session_id: str, attachment_id: str, request: Request, db: Session = Depends(get_db)):
    """
    查询附件的最新信息 (v3 架构)
    
    从 message_attachments 表直接查询，联查 UploadTask 获取最新云 URL
    
    返回：
    {
        "id": "att-xxx",
        "url": "https://img.dicry.com/xxx.png",
        "uploadStatus": "completed",
        "mimeType": "image/png",
        "name": "image.png",
        "taskId": "task-xxx",
        "taskStatus": "completed"
    }
    """
    user_id = require_user_id(request)
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
        result["taskId"] = task.id
        result["taskStatus"] = task.status
        print(f"[Sessions] 找到上传任务: task_id={task.id[:8]}..., status={task.status}, target_url={task.target_url[:60] if task.target_url else 'None'}")
        
        # 如果任务已完成且有目标 URL，优先使用任务的 URL
        if task.status == 'completed' and task.target_url:
            result["url"] = task.target_url
            result["uploadStatus"] = 'completed'
            print(f"[Sessions] ✅ 使用任务的 target_url 作为最终 URL")
    
    print(f"[Sessions] 查询附件: {attachment_id[:8]}... -> url: {result.get('url', 'None')[:50] if result.get('url') else 'None'}..., uploadStatus: {result.get('uploadStatus')}")
    return result
