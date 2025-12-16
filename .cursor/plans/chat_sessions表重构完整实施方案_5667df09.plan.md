---
name: chat_sessions表重构完整实施方案
overview: 提供完整的数据库规范化重构方案，包括优化的数据模型、服务层实现、数据迁移策略和URL处理逻辑（只保留云存储URL）
todos: []
---

# chat_sessions 表重构完整实施方案

## 一、方案概述

### 1.1 核心目标

- 将 `chat_sessions.messages` JSON 字段拆分为独立的关系型表
- **URL 策略**：只保留云存储 URL（http/https），不存储 Base64、Blob URL 等临时数据
- 支持多用户隔离（通过 `user_id`）
- 保持 API 向后兼容
- 优化查询性能（分页、索引）

### 1.2 数据模型优化

#### User 表（优化后）

```python
class User(Base):
    __tablename__ = "users"
    
    # ✅ 优化：使用 UUID 作为主键，移除自增 id
    user_id = Column(String(36), primary_key=True, index=True)  # UUID
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(BigInteger, nullable=False)
    
    # Relationships
    sessions = relationship("ChatSessionV2", back_populates="user", cascade="all, delete-orphan")
```

#### ChatSessionV2 表

```python
class ChatSessionV2(Base):
    __tablename__ = "chat_sessions_v2"
    
    id = Column(String(36), primary_key=True, index=True)  # UUID
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    persona_id = Column(String(36), nullable=True)
    mode = Column(String(50), nullable=True)
    created_at = Column(BigInteger, nullable=False, index=True)
    updated_at = Column(BigInteger, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    messages = relationship("MessageV2", back_populates="session", cascade="all, delete-orphan", order_by="MessageV2.timestamp")
```

#### MessageV2 表

```python
class MessageV2(Base):
    __tablename__ = "messages_v2"
    
    id = Column(String(36), primary_key=True, index=True)  # UUID
    session_id = Column(String(36), ForeignKey("chat_sessions_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, model, system
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False, index=True)
    is_error = Column(Boolean, default=False)
    mode = Column(String(50), nullable=True)
    grounding_metadata = Column(JSON, nullable=True)
    url_context_metadata = Column(JSON, nullable=True)
    browser_operation_id = Column(String(36), nullable=True)
    created_at = Column(BigInteger, nullable=False)  # ✅ 新增：创建时间
    updated_at = Column(BigInteger, nullable=True)  # ✅ 新增：更新时间（支持消息编辑）
    
    # Relationships
    session = relationship("ChatSessionV2", back_populates="messages")
    attachments = relationship("AttachmentV2", back_populates="message", cascade="all, delete-orphan")
```

#### AttachmentV2 表（优化后 - 只保留云存储 URL）

```python
class AttachmentV2(Base):
    __tablename__ = "attachments_v2"
    
    id = Column(String(36), primary_key=True, index=True)  # UUID
    message_id = Column(String(36), ForeignKey("messages_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    
    # ✅ 优化：只保留云存储 URL，移除 temp_url 和 file_uri
    url = Column(String(500), nullable=True)  # 只存储云存储 URL (http/https)
    
    upload_status = Column(String(20), default='pending')  # pending, uploading, completed, failed
    upload_task_id = Column(String(36), nullable=True)  # 关联 UploadTask
    upload_error = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)
    
    # Relationships
    message = relationship("MessageV2", back_populates="attachments")
    
    def to_dict(self):
        """转换为前端 Attachment 格式"""
        return {
            "id": self.id,
            "mimeType": self.mime_type,
            "name": self.name,
            "url": self.url,  # 只返回云存储 URL
            "uploadStatus": self.upload_status,
            "uploadTaskId": self.upload_task_id,
            "uploadError": self.upload_error
        }
```

### 1.3 索引设计（优化后）

```sql
-- User 表
CREATE UNIQUE INDEX ix_users_email ON users(email);

-- ChatSessionV2 表
CREATE INDEX ix_sessions_user_id ON chat_sessions_v2(user_id);
CREATE INDEX ix_sessions_user_created ON chat_sessions_v2(user_id, created_at DESC);  -- ✅ 复合索引

-- MessageV2 表
CREATE INDEX ix_messages_session ON messages_v2(session_id);
CREATE INDEX ix_messages_session_timestamp ON messages_v2(session_id, timestamp DESC);  -- ✅ 复合索引，优化分页
CREATE INDEX ix_messages_timestamp ON messages_v2(timestamp DESC);

-- AttachmentV2 表
CREATE INDEX ix_attachments_message ON attachments_v2(message_id);
CREATE INDEX ix_attachments_status ON attachments_v2(upload_status) WHERE upload_status != 'completed';  -- ✅ 部分索引，优化上传状态查询
```

## 二、服务层实现

### 2.1 SessionService 完整实现

```python

# backend/app/services/session_service.py

from sqlalchemy.orm import Session, joinedload

from sqlalchemy import and_, desc

from typing import List, Optional, Dict

from datetime import datetime

import uuid

from ..models.db_models import (

User, ChatSessionV2, MessageV2, AttachmentV2

)

class SessionService:

"""会话服务 - 处理会话的 CRUD 操作和数据聚合"""

def **init**(self, db: Session):

self.db = db

def _normalize_attachment_url(self, url: Optional[str]) -> Optional[str]:

"""

规范化附件 URL：只保留云存储 URL (http/https)

清空 Base64、Blob URL 等临时数据

"""

if not url:

return None

# 只保留云存储 URL

if url.startswith('http://') or url.startswith('https://'):

return url

# 其他类型（Base64、Blob）返回 None

return None

def _clean_attachment_for_storage(self, att_data: dict) -> dict:

"""

清理附件数据用于存储：

        - 只保留云存储 URL
        - 移除临时字段（file, tempUrl, bas