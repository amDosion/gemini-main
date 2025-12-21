"""
会话管理路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..core.database import SessionLocal
from ..models.db_models import ChatSession as DBChatSession

router = APIRouter(prefix="/api", tags=["sessions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 会话管理 ====================

@router.get("/sessions")
async def get_sessions(db: Session = Depends(get_db)):
    """获取所有会话"""
    sessions = db.query(DBChatSession).all()
    return [session.to_dict() for session in sessions]


@router.post("/sessions")
async def create_or_update_session(session_data: dict, db: Session = Depends(get_db)):
    """创建或更新会话
    
    注意：更新消息时会保留已上传完成的附件 URL，避免前端覆盖后端的上传结果
    """
    from sqlalchemy.orm.attributes import flag_modified
    from ..models.db_models import UploadTask
    import copy
    
    session_id = session_data.get("id")
    
    # 查找现有会话
    session = db.query(DBChatSession).filter(DBChatSession.id == session_id).first()
    
    if session:
        # 更新现有会话
        session.title = session_data.get("title", session.title)
        session.persona_id = session_data.get("personaId", session.persona_id)
        session.mode = session_data.get("mode", session.mode)
        
        # ✅ 智能合并消息：只处理当前活动的附件，保留已上传完成的 URL
        new_messages = session_data.get("messages", [])
        old_messages = session.messages or []
        
        # 1. 收集当前消息中需要处理的附件 ID（只关注当前活动的附件）
        current_attachment_keys = set()  # (msg_id, att_id)
        for msg in new_messages:
            msg_id = msg.get('id')
            for att in msg.get('attachments', []):
                att_id = att.get('id')
                if att_id:
                    current_attachment_keys.add((msg_id, att_id))
        
        # 2. 只从旧消息中提取当前活动附件的 URL（而不是所有历史附件）
        old_attachment_urls = {}
        for msg in old_messages:
            msg_id = msg.get('id')
            for att in msg.get('attachments', []):
                att_id = att.get('id')
                key = (msg_id, att_id)
                # ✅ 只处理当前消息中存在的附件
                if key in current_attachment_keys:
                    att_url = att.get('url', '')
                    if att_url and att_url.startswith('http'):
                        old_attachment_urls[key] = {
                            'url': att_url,
                            'status': att.get('uploadStatus', 'completed')
                        }
        
        # 3. 从 UploadTask 补充新上传的 URL（只查询当前活动的附件）
        current_attachment_ids = [key[1] for key in current_attachment_keys]
        if current_attachment_ids:
            completed_tasks = db.query(UploadTask).filter(
                UploadTask.session_id == session_id,
                UploadTask.attachment_id.in_(current_attachment_ids),
                UploadTask.status == 'completed',
                UploadTask.target_url.isnot(None)
            ).all()
            
            for task in completed_tasks:
                key = (task.message_id, task.attachment_id)
                if key not in old_attachment_urls:
                    old_attachment_urls[key] = {
                        'url': task.target_url,
                        'status': 'completed'
                    }
        
        # 4. 合并新消息，保留已上传的 URL
        merged_messages = []
        merge_count = 0
        for msg in new_messages:
            msg_copy = copy.deepcopy(msg)
            msg_id = msg_copy.get('id')
            
            for att in msg_copy.get('attachments', []):
                att_id = att.get('id')
                key = (msg_id, att_id)
                
                if key in old_attachment_urls:
                    new_url = att.get('url', '')
                    old_data = old_attachment_urls[key]
                    # 新 URL 为空、Blob URL 或 Base64 时，使用旧的永久 URL
                    if not new_url or new_url.startswith('blob:') or new_url.startswith('data:'):
                        att['url'] = old_data['url']
                        att['uploadStatus'] = 'completed'
                        merge_count += 1
            
            merged_messages.append(msg_copy)
        
        if merge_count > 0:
            print(f"[Sessions] 合并完成，保留了 {merge_count} 个已上传的附件 URL")
        
        session.messages = merged_messages
        flag_modified(session, 'messages')
    else:
        # 创建新会话
        session = DBChatSession(
            id=session_id,
            title=session_data.get("title", "新对话"),
            messages=session_data.get("messages", []),
            created_at=session_data.get("createdAt", int(datetime.now().timestamp() * 1000)),
            persona_id=session_data.get("personaId"),
            mode=session_data.get("mode")
        )
        db.add(session)
    
    db.commit()
    db.refresh(session)
    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    """删除会话"""
    session = db.query(DBChatSession).filter(DBChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    db.delete(session)
    db.commit()
    return {"success": True}


@router.get("/sessions/{session_id}/attachments/{attachment_id}")
async def get_attachment(session_id: str, attachment_id: str, db: Session = Depends(get_db)):
    """
    查询附件的最新信息
    
    从数据库中查询附件的最新 URL 和上传状态，用于：
    1. CONTINUITY LOGIC 中获取 Base64 对应的云存储 URL
    2. 后期扩展：上传进度页面、任务管理等
    
    返回：
    {
        "id": "att-xxx",
        "url": "https://img.dicry.com/xxx.png",
        "uploadStatus": "completed",
        "mimeType": "image/png",
        "name": "image.png",
        "taskId": "task-xxx",  // 关联的上传任务 ID（如果有）
        "taskStatus": "completed"  // 任务状态（如果有）
    }
    """
    from ..models.db_models import UploadTask
    
    # 1. 查询会话
    session = db.query(DBChatSession).filter(DBChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 2. 在消息中查找附件
    attachment = None
    message_id = None
    for msg in session.messages or []:
        for att in msg.get('attachments', []):
            if att.get('id') == attachment_id:
                attachment = att
                message_id = msg.get('id')
                break
        if attachment:
            break
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    # 3. 查询关联的上传任务
    task = db.query(UploadTask).filter(
        UploadTask.session_id == session_id,
        UploadTask.attachment_id == attachment_id
    ).first()
    
    # 4. 构建返回结果
    result = {
        "id": attachment.get('id'),
        "url": attachment.get('url'),
        "uploadStatus": attachment.get('uploadStatus', 'unknown'),
        "mimeType": attachment.get('mimeType'),
        "name": attachment.get('name'),
        "messageId": message_id
    }
    
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
        else:
            print(f"[Sessions] ⚠️ 任务未完成或无 target_url, 使用附件原始 URL")
    else:
        print(f"[Sessions] ⚠️ 未找到关联的上传任务")
    
    print(f"[Sessions] 查询附件: {attachment_id[:8]}... -> url: {result['url'][:50] if result['url'] else 'None'}..., uploadStatus: {result['uploadStatus']}")
    return result
