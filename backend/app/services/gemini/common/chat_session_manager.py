"""
Chat Session Manager - 管理 Google Chat SDK 会话生命周期

负责：
1. 数据库持久化：存储 Google Chat 会话元数据（GoogleChatSession 表）
2. 内存缓存：缓存活跃的 Chat 对象（避免重复创建）
3. 历史重建：从数据库消息历史重建 Chat 对象（用于恢复会话）
"""

import logging
import json
import re
import time
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ....models.db_models import (
    GoogleChatSession, 
    MessageIndex, 
    MessagesGeneric, 
    MessagesImageChatEdit,
    MessageAttachment
)
from ....utils.message_utils import get_message_table_class_by_name

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """
    管理 Google Chat SDK 会话的生命周期
    
    策略：
    - 数据库持久化：会话元数据存储在 GoogleChatSession 表
    - 内存缓存：活跃的 Chat 对象缓存在内存中（性能优化）
    - 历史重建：从 MessageIndex + MessagesGeneric 重建 Chat 对象（恢复会话）
    """
    
    def __init__(self, db: Session):
        """
        初始化会话管理器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self._chat_cache: Dict[str, Any] = {}  # {chat_id: Chat对象}
    
    def create_chat_session(
        self,
        chat_id: str,
        user_id: str,
        frontend_session_id: str,
        model_name: str,
        config: Optional[Dict[str, Any]] = None,
        chat_object: Optional[Any] = None
    ) -> GoogleChatSession:
        """
        创建新的 Google Chat 会话记录
        
        Args:
            chat_id: Google Chat ID（UUID）
            user_id: 用户 ID
            frontend_session_id: 前端会话 ID（ChatSession.id）
            model_name: 使用的模型名称
            config: Chat 配置（可选）
            chat_object: Google SDK Chat 对象（可选，如果提供则缓存）
        
        Returns:
            GoogleChatSession 数据库记录
        """
        now = int(time.time() * 1000)
        
        # 创建数据库记录
        chat_session = GoogleChatSession(
            chat_id=chat_id,
            user_id=user_id,
            frontend_session_id=frontend_session_id,
            model_name=model_name,
            config_json=json.dumps(config) if config else None,
            created_at=now,
            last_used_at=now,
            is_active=True
        )
        
        self.db.add(chat_session)
        self.db.commit()
        self.db.refresh(chat_session)
        
        # 如果提供了 Chat 对象，缓存它
        if chat_object:
            self._chat_cache[chat_id] = chat_object
        
        logger.info(
            f"[ChatSessionManager] Created chat session: "
            f"chat_id={chat_id}, user_id={user_id}, frontend_session_id={frontend_session_id}"
        )
        
        return chat_session
    
    def get_chat_session(
        self,
        chat_id: str,
        chat_object: Optional[Any] = None
    ) -> Optional[GoogleChatSession]:
        """
        获取 Google Chat 会话记录
        
        Args:
            chat_id: Google Chat ID
            chat_object: Google SDK Chat 对象（可选，如果提供则缓存）
        
        Returns:
            GoogleChatSession 数据库记录，如果不存在则返回 None
        """
        chat_session = self.db.query(GoogleChatSession).filter(
            GoogleChatSession.chat_id == chat_id
        ).first()
        
        if chat_session:
            # 更新最后使用时间
            chat_session.last_used_at = int(time.time() * 1000)
            self.db.commit()
            
            # 如果提供了 Chat 对象，缓存它
            if chat_object:
                self._chat_cache[chat_id] = chat_object
        
        return chat_session
    
    def get_chat_object_from_cache(self, chat_id: str) -> Optional[Any]:
        """
        从内存缓存获取 Chat 对象
        
        Args:
            chat_id: Google Chat ID
        
        Returns:
            Google SDK Chat 对象，如果不存在则返回 None
        """
        return self._chat_cache.get(chat_id)
    
    def cache_chat_object(self, chat_id: str, chat_object: Any) -> None:
        """
        缓存 Chat 对象到内存
        
        Args:
            chat_id: Google Chat ID
            chat_object: Google SDK Chat 对象
        """
        self._chat_cache[chat_id] = chat_object
        logger.debug(f"[ChatSessionManager] Cached chat object: chat_id={chat_id}")
    
    def get_chat_history_for_rebuild(
        self,
        frontend_session_id: str,
        mode: str = 'image-chat-edit'
    ) -> List[Dict[str, Any]]:
        """
        获取会话历史，用于重建 Chat 对象
        
        从 MessageIndex + 对应的模式表 + MessageAttachment 获取历史消息
        
        Args:
            frontend_session_id: 前端会话 ID
            mode: 消息模式（默认 'image-chat-edit'）
        
        Returns:
            消息列表，格式：[
                {
                    'role': 'user' | 'model',
                    'parts': [...],  # Google SDK Part 格式
                    'timestamp': int
                },
                ...
            ]
        """
        # 1. 获取消息索引
        message_indices = self.db.query(MessageIndex).filter(
            and_(
                MessageIndex.session_id == frontend_session_id,
                MessageIndex.mode == mode
            )
        ).order_by(MessageIndex.seq).all()
        
        if not message_indices:
            return []
        
        # 2. 获取消息内容（从对应的模式表）
        messages = []
        for idx in message_indices:
            # 根据 table_name 获取对应的模型类
            try:
                table_class = get_message_table_class_by_name(idx.table_name)
                msg = self.db.query(table_class).filter(
                    table_class.id == idx.id
                ).first()
            except ValueError:
                # 如果表名未知，回退到 MessagesGeneric
                logger.warning(
                    f"[ChatSessionManager] Unknown table_name: {idx.table_name}, "
                    f"falling back to MessagesGeneric"
                )
                msg = self.db.query(MessagesGeneric).filter(
                    MessagesGeneric.id == idx.id
                ).first()
            
            if not msg:
                continue
            
            # 3. 获取附件（从 MessageAttachment）
            attachments = self.db.query(MessageAttachment).filter(
                MessageAttachment.message_id == msg.id
            ).all()
            
            # 4. 构建 parts（Google SDK 格式）
            parts = []
            
            # 文本内容
            if msg.content:
                parts.append({'text': msg.content})
            
            # 附件（图片）
            for att in attachments:
                if att.google_file_uri:
                    # 使用 Google File URI
                    parts.append({
                        'file_data': {
                            'file_uri': att.google_file_uri,
                            'mime_type': att.mime_type or 'image/png'
                        }
                    })
                elif att.url and att.url.startswith('data:'):
                    # Base64 Data URL
                    match = re.match(r'^data:(.*?);base64,(.*)$', att.url)
                    if match:
                        parts.append({
                            'inline_data': {
                                'mime_type': match.group(1),
                                'data': match.group(2)
                            }
                        })
            
            messages.append({
                'role': msg.role,
                'parts': parts,
                'timestamp': msg.timestamp
            })
        
        logger.info(
            f"[ChatSessionManager] Retrieved chat history: "
            f"frontend_session_id={frontend_session_id}, count={len(messages)}"
        )
        
        return messages
    
    def delete_chat_session(self, chat_id: str) -> bool:
        """
        删除 Google Chat 会话
        
        Args:
            chat_id: Google Chat ID
        
        Returns:
            是否删除成功
        """
        # 从数据库删除
        chat_session = self.db.query(GoogleChatSession).filter(
            GoogleChatSession.chat_id == chat_id
        ).first()
        
        if chat_session:
            chat_session.is_active = False
            self.db.commit()
            
            # 从缓存删除
            if chat_id in self._chat_cache:
                del self._chat_cache[chat_id]
            
            logger.info(f"[ChatSessionManager] Deleted chat session: chat_id={chat_id}")
            return True
        
        return False
    
    def list_user_chat_sessions(
        self,
        user_id: str,
        frontend_session_id: Optional[str] = None
    ) -> List[GoogleChatSession]:
        """
        列出用户的所有 Google Chat 会话
        
        Args:
            user_id: 用户 ID
            frontend_session_id: 前端会话 ID（可选，用于过滤）
        
        Returns:
            GoogleChatSession 列表
        """
        query = self.db.query(GoogleChatSession).filter(
            and_(
                GoogleChatSession.user_id == user_id,
                GoogleChatSession.is_active == True
            )
        )
        
        if frontend_session_id:
            query = query.filter(
                GoogleChatSession.frontend_session_id == frontend_session_id
            )
        
        return query.order_by(GoogleChatSession.last_used_at.desc()).all()
