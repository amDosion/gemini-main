# 数据库重构与用户数据表完整实施方案

## 一、方案概述

### 1.1 核心目标

本次重构旨在解决以下问题：

1. **数据规范化**：将 `chat_sessions.messages` JSON 字段拆分为独立的关系型表，避免数据无限膨胀
2. **多用户支持**：建立完整的用户数据表体系，实现多用户数据隔离
3. **用户认证**：实现真正的用户认证系统，替换当前的模拟登录逻辑
4. **性能优化**：通过索引和分页查询提升系统性能
5. **向后兼容**：保持现有 API 接口兼容，前端无需大规模修改

### 1.2 重构范围

- **数据库层**：新增 `users`、`chat_sessions_v2`、`messages_v2`、`attachments_v2` 表
- **服务层**：实现 `SessionService` 和 `UserService` 处理业务逻辑
- **API 层**：新增用户认证 API，重构会话管理 API
- **前端层**：更新数据库适配层，支持新的数据结构
- **迁移工具**：提供数据迁移脚本，将旧数据迁移到新表结构

## 二、数据模型设计

### 2.1 用户表（User）

```python
class User(Base):
    """用户表 - 存储用户基本信息"""
    __tablename__ = "users"
    
    # ✅ 优化：使用 UUID 作为主键，移除自增 id
    user_id = Column(String(36), primary_key=True, index=True)  # UUID
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)  # bcrypt 哈希
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)
    last_login_at = Column(BigInteger, nullable=True)  # ✅ 新增：最后登录时间
    
    # Relationships
    sessions = relationship("ChatSessionV2", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    
    def to_dict(self):
        """转换为字典格式（不包含敏感信息）"""
        return {
            "userId": self.user_id,
            "email": self.email,
            "name": self.name,
            "createdAt": self.created_at,
            "lastLoginAt": self.last_login_at
        }
```

**设计说明**：
- 使用 `user_id`（UUID）作为主键，避免自增 ID 的安全隐患
- `email` 作为唯一标识，用于登录验证
- `password_hash` 存储 bcrypt 加密后的密码
- 添加 `last_login_at` 字段用于追踪用户活跃度

### 2.2 会话表（ChatSessionV2）

```python
class ChatSessionV2(Base):
    """聊天会话表 V2 - 仅存储元数据"""
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
    
    def to_dict(self):
        """转换为字典格式（与前端 ChatSession 接口兼容）"""
        return {
            "id": self.id,
            "title": self.title,
            "messages": [],  # 消息通过关联查询获取
            "createdAt": self.created_at,
            "personaId": self.persona_id,
            "mode": self.mode
        }
```

**设计说明**：
- 移除 `messages` JSON 字段，仅存储会话元数据
- 通过 `user_id` 外键关联用户，实现数据隔离
- 级联删除确保用户删除时自动清理会话数据

### 2.3 消息表（MessageV2）

```python
class MessageV2(Base):
    """消息表 V2 - 独立存储每条消息"""
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
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=True)  # ✅ 支持消息编辑
    
    # Relationships
    session = relationship("ChatSessionV2", back_populates="messages")
    attachments = relationship("AttachmentV2", back_populates="message", cascade="all, delete-orphan")
    
    def to_dict(self):
        """转换为字典格式（与前端 Message 接口兼容）"""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "isError": self.is_error,
            "mode": self.mode,
            "groundingMetadata": self.grounding_metadata,
            "urlContextMetadata": self.url_context_metadata,
            "browserOperationId": self.browser_operation_id,
            "attachments": [att.to_dict() for att in self.attachments]
        }
```

**设计说明**：
- 每条消息独立存储，支持单条消息的增删改查
- 通过 `session_id` 外键关联会话
- 添加 `created_at` 和 `updated_at` 支持消息编辑功能
- 级联删除确保会话删除时自动清理消息

### 2.4 附件表（AttachmentV2）

```python
class AttachmentV2(Base):
    """附件表 V2 - 独立存储附件元数据"""
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

**设计说明**：
- 只保留云存储 URL（http/https），不存储 Base64、Blob URL 等临时数据
- 通过 `message_id` 外键关联消息
- 级联删除确保消息删除时自动清理附件

### 2.5 数据关系图

```mermaid
erDiagram
    users ||--o{ chat_sessions_v2 : "has"
    users ||--o| user_settings : "has"
    chat_sessions_v2 ||--o{ messages_v2 : "contains"
    messages_v2 ||--o{ attachments_v2 : "has"
    
    users {
        string user_id PK "UUID主键"
        string email UK "邮箱（唯一）"
        string name "用户名称"
        string password_hash "密码哈希"
        bigint created_at "创建时间"
        bigint updated_at "更新时间"
        bigint last_login_at "最后登录时间"
    }
    
    chat_sessions_v2 {
        string id PK "UUID"
        string user_id FK "用户ID"
        string title "会话标题"
        string persona_id "角色ID"
        string mode "会话模式"
        bigint created_at "创建时间"
        bigint updated_at "更新时间"
    }
    
    messages_v2 {
        string id PK "UUID"
        string session_id FK "会话ID"
        string role "角色"
        text content "消息内容"
        bigint timestamp "时间戳"
        boolean is_error "是否错误"
        json grounding_metadata "搜索元数据"
        json url_context_metadata "URL上下文"
    }
    
    attachments_v2 {
        string id PK "UUID"
        string message_id FK "消息ID"
        string mime_type "MIME类型"
        string name "文件名"
        string url "云存储URL"
        string upload_status "上传状态"
    }
```

## 三、索引设计

### 3.1 索引策略

```sql
-- User 表索引
CREATE UNIQUE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_created_at ON users(created_at DESC);

-- ChatSessionV2 表索引
CREATE INDEX ix_sessions_user_id ON chat_sessions_v2(user_id);
CREATE INDEX ix_sessions_user_created ON chat_sessions_v2(user_id, created_at DESC);  -- ✅ 复合索引，优化用户会话列表查询

-- MessageV2 表索引
CREATE INDEX ix_messages_session ON messages_v2(session_id);
CREATE INDEX ix_messages_session_timestamp ON messages_v2(session_id, timestamp DESC);  -- ✅ 复合索引，优化分页查询
CREATE INDEX ix_messages_timestamp ON messages_v2(timestamp DESC);

-- AttachmentV2 表索引
CREATE INDEX ix_attachments_message ON attachments_v2(message_id);
CREATE INDEX ix_attachments_status ON attachments_v2(upload_status) WHERE upload_status != 'completed';  -- ✅ 部分索引，优化上传状态查询
```

**索引优化说明**：
- **复合索引**：`(user_id, created_at)` 和 `(session_id, timestamp)` 优化常见查询场景
- **部分索引**：附件上传状态索引只包含未完成的记录，减少索引大小
- **唯一索引**：`email` 字段确保用户邮箱唯一性

## 四、服务层实现

### 4.1 UserService - 用户服务

```python
# backend/app/services/user_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, Dict
import uuid
import bcrypt
from datetime import datetime

from ..models.db_models import User

class UserService:
    """用户服务 - 处理用户认证和用户数据管理"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, email: str, password: str, name: str) -> User:
        """创建新用户"""
        # 检查邮箱是否已存在
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError(f"邮箱 {email} 已被使用")
        
        # 生成密码哈希
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # 创建用户
        user = User(
            user_id=str(uuid.uuid4()),
            email=email,
            name=name,
            password_hash=password_hash,
            created_at=int(datetime.now().timestamp() * 1000)
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """验证用户登录"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return None
        
        # 验证密码
        if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            # 更新最后登录时间
            user.last_login_at = int(datetime.now().timestamp() * 1000)
            self.db.commit()
            return user
        
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据 user_id 获取用户"""
        return self.db.query(User).filter(User.user_id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()
    
    def update_user(self, user_id: str, name: Optional[str] = None, password: Optional[str] = None) -> User:
        """更新用户信息"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"用户 {user_id} 不存在")
        
        if name:
            user.name = name
        if password:
            user.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        user.updated_at = int(datetime.now().timestamp() * 1000)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_or_create_default_user(self) -> User:
        """获取或创建默认用户（用于向后兼容）"""
        default_email = "default@system.local"
        user = self.get_user_by_email(default_email)
        
        if not user:
            user = self.create_user(
                email=default_email,
                password="default",
                name="默认用户"
            )
        
        return user
```

### 4.2 SessionService - 会话服务

```python
# backend/app/services/session_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc
from typing import List, Optional, Dict
from datetime import datetime
import uuid

from ..models.db_models import ChatSessionV2, MessageV2, AttachmentV2

class SessionService:
    """会话服务 - 处理会话的 CRUD 操作和数据聚合"""
    
    def __init__(self, db: Session):
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
    
    def get_sessions_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取用户的会话列表（仅元数据）"""
        sessions = self.db.query(ChatSessionV2)\
            .filter(ChatSessionV2.user_id == user_id)\
            .order_by(desc(ChatSessionV2.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return [self._session_to_dict(session) for session in sessions]
    
    def get_session_with_messages(self, session_id: str, user_id: str) -> Optional[Dict]:
        """获取完整会话（包含消息和附件）"""
        session = self.db.query(ChatSessionV2)\
            .filter(
                and_(
                    ChatSessionV2.id == session_id,
                    ChatSessionV2.user_id == user_id
                )
            )\
            .options(
                joinedload(ChatSessionV2.messages).joinedload(MessageV2.attachments)
            )\
            .first()
        
        if not session:
            return None
        
        return self._session_to_dict_with_messages(session)
    
    def save_session(self, session_data: dict, user_id: str) -> Dict:
        """保存会话（拆分存储消息和附件）"""
        session_id = session_data.get("id")
        messages_data = session_data.get("messages", [])
        
        # 查找或创建会话
        session = self.db.query(ChatSessionV2).filter(ChatSessionV2.id == session_id).first()
        
        if session:
            # 更新现有会话
            session.title = session_data.get("title", session.title)
            session.persona_id = session_data.get("personaId", session.persona_id)
            session.mode = session_data.get("mode", session.mode)
            session.updated_at = int(datetime.now().timestamp() * 1000)
        else:
            # 创建新会话
            session = ChatSessionV2(
                id=session_id,
                user_id=user_id,
                title=session_data.get("title", "新对话"),
                persona_id=session_data.get("personaId"),
                mode=session_data.get("mode"),
                created_at=session_data.get("createdAt", int(datetime.now().timestamp() * 1000)),
                updated_at=int(datetime.now().timestamp() * 1000)
            )
            self.db.add(session)
        
        # 保存消息和附件
        self._save_messages(session_id, messages_data)
        
        self.db.commit()
        self.db.refresh(session)
        return self._session_to_dict_with_messages(session)
    
    def _save_messages(self, session_id: str, messages_data: List[Dict]):
        """保存消息列表"""
        for msg_data in messages_data:
            message_id = msg_data.get("id")
            
            # 查找或创建消息
            message = self.db.query(MessageV2).filter(MessageV2.id == message_id).first()
            
            if message:
                # 更新现有消息
                message.content = msg_data.get("content", message.content)
                message.role = msg_data.get("role", message.role)
                message.timestamp = msg_data.get("timestamp", message.timestamp)
                message.is_error = msg_data.get("isError", message.is_error)
                message.mode = msg_data.get("mode", message.mode)
                message.grounding_metadata = msg_data.get("groundingMetadata")
                message.url_context_metadata = msg_data.get("urlContextMetadata")
                message.browser_operation_id = msg_data.get("browserOperationId")
                message.updated_at = int(datetime.now().timestamp() * 1000)
            else:
                # 创建新消息
                message = MessageV2(
                    id=message_id,
                    session_id=session_id,
                    role=msg_data.get("role", "user"),
                    content=msg_data.get("content", ""),
                    timestamp=msg_data.get("timestamp", int(datetime.now().timestamp() * 1000)),
                    is_error=msg_data.get("isError", False),
                    mode=msg_data.get("mode"),
                    grounding_metadata=msg_data.get("groundingMetadata"),
                    url_context_metadata=msg_data.get("urlContextMetadata"),
                    browser_operation_id=msg_data.get("browserOperationId"),
                    created_at=int(datetime.now().timestamp() * 1000)
                )
                self.db.add(message)
            
            # 保存附件
            attachments_data = msg_data.get("attachments", [])
            self._save_attachments(message_id, attachments_data)
    
    def _save_attachments(self, message_id: str, attachments_data: List[Dict]):
        """保存附件列表"""
        for att_data in attachments_data:
            attachment_id = att_data.get("id")
            
            # 规范化 URL
            url = self._normalize_attachment_url(att_data.get("url"))
            
            # 查找或创建附件
            attachment = self.db.query(AttachmentV2).filter(AttachmentV2.id == attachment_id).first()
            
            if attachment:
                # 更新现有附件
                attachment.mime_type = att_data.get("mimeType", attachment.mime_type)
                attachment.name = att_data.get("name", attachment.name)
                attachment.url = url or attachment.url  # 只更新有效的 URL
                attachment.upload_status = att_data.get("uploadStatus", attachment.upload_status)
                attachment.upload_task_id = att_data.get("uploadTaskId", attachment.upload_task_id)
                attachment.upload_error = att_data.get("uploadError", attachment.upload_error)
                attachment.updated_at = int(datetime.now().timestamp() * 1000)
            else:
                # 创建新附件
                attachment = AttachmentV2(
                    id=attachment_id,
                    message_id=message_id,
                    mime_type=att_data.get("mimeType", "application/octet-stream"),
                    name=att_data.get("name", "unknown"),
                    url=url,
                    upload_status=att_data.get("uploadStatus", "pending"),
                    upload_task_id=att_data.get("uploadTaskId"),
                    upload_error=att_data.get("uploadError"),
                    created_at=int(datetime.now().timestamp() * 1000)
                )
                self.db.add(attachment)
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """删除会话（级联删除消息和附件）"""
        session = self.db.query(ChatSessionV2)\
            .filter(
                and_(
                    ChatSessionV2.id == session_id,
                    ChatSessionV2.user_id == user_id
                )
            )\
            .first()
        
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True
    
    def get_messages_paginated(self, session_id: str, limit: int = 50, before_timestamp: int = None) -> List[Dict]:
        """分页获取消息"""
        query = self.db.query(MessageV2)\
            .filter(MessageV2.session_id == session_id)\
            .options(joinedload(MessageV2.attachments))
        
        if before_timestamp:
            query = query.filter(MessageV2.timestamp < before_timestamp)
        
        messages = query\
            .order_by(desc(MessageV2.timestamp))\
            .limit(limit)\
            .all()
        
        return [self._message_to_dict(msg) for msg in messages]
    
    def get_recent_messages(self, session_id: str, count: int = 20) -> List[Dict]:
        """获取最近 N 条消息（用于 AI 上下文）"""
        messages = self.db.query(MessageV2)\
            .filter(MessageV2.session_id == session_id)\
            .options(joinedload(MessageV2.attachments))\
            .order_by(MessageV2.timestamp)\
            .limit(count)\
            .all()
        
        return [self._message_to_dict(msg) for msg in messages]
    
    def _session_to_dict(self, session: ChatSessionV2) -> Dict:
        """会话转字典（不含消息）"""
        return {
            "id": session.id,
            "title": session.title,
            "messages": [],  # 空数组，保持 API 兼容
            "createdAt": session.created_at,
            "personaId": session.persona_id,
            "mode": session.mode
        }
    
    def _session_to_dict_with_messages(self, session: ChatSessionV2) -> Dict:
        """会话转字典（包含消息）"""
        return {
            "id": session.id,
            "title": session.title,
            "messages": [self._message_to_dict(msg) for msg in session.messages],
            "createdAt": session.created_at,
            "personaId": session.persona_id,
            "mode": session.mode
        }
    
    def _message_to_dict(self, message: MessageV2) -> Dict:
        """消息转字典"""
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp,
            "isError": message.is_error,
            "mode": message.mode,
            "groundingMetadata": message.grounding_metadata,
            "urlContextMetadata": message.url_context_metadata,
            "browserOperationId": message.browser_operation_id,
            "attachments": [att.to_dict() for att in message.attachments]
        }
```

## 五、API 路由层

### 5.1 用户认证 API

```python
# backend/app/routers/auth.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from ..core.database import SessionLocal
from ..services.user_service import UserService

router = APIRouter(prefix="/api/auth", tags=["authentication"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserResponse(BaseModel):
    userId: str
    email: str
    name: str
    createdAt: int
    lastLoginAt: Optional[int] = None

@router.post("/login", response_model=UserResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user_service = UserService(db)
    user = user_service.authenticate_user(request.email, request.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="无效的邮箱或密码")
    
    return user.to_dict()

@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    user_service = UserService(db)
    
    try:
        user = user_service.create_user(
            email=request.email,
            password=request.password,
            name=request.name
        )
        return user.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def get_current_user(user_id: str = "default", db: Session = Depends(get_db)):
    """获取当前用户信息"""
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user.to_dict()
```

### 5.2 会话管理 API（重构后）

```python
# backend/app/routers/sessions.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from ..core.database import SessionLocal
from ..services.session_service import SessionService

router = APIRouter(prefix="/api", tags=["sessions"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/sessions")
async def get_sessions(user_id: str = "default", db: Session = Depends(get_db)):
    """获取会话列表 - 返回聚合后的完整格式（保持向后兼容）"""
    session_service = SessionService(db)
    sessions = session_service.get_sessions_by_user(user_id)
    
    # 为了保持向后兼容，需要为每个会话加载消息
    result = []
    for session_meta in sessions:
        full_session = session_service.get_session_with_messages(session_meta["id"], user_id)
        if full_session:
            result.append(full_session)
    
    return result

@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: str = "default", db: Session = Depends(get_db)):
    """获取单个会话 - 包含所有消息和附件"""
    session_service = SessionService(db)
    session = session_service.get_session_with_messages(session_id, user_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return session

@router.post("/sessions")
async def save_session(session_data: dict, user_id: str = "default", db: Session = Depends(get_db)):
    """保存会话 - 接受完整格式，拆分存储"""
    session_service = SessionService(db)
    return session_service.save_session(session_data, user_id)

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = "default", db: Session = Depends(get_db)):
    """删除会话 - 级联删除"""
    session_service = SessionService(db)
    success = session_service.delete_session(session_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return {"success": True}

# 新增的细粒度 API（可选）
@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    before: Optional[int] = None,
    user_id: str = "default",
    db: Session = Depends(get_db)
):
    """分页获取消息"""
    session_service = SessionService(db)
    # 验证会话属于当前用户
    session = session_service.get_session_with_messages(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return session_service.get_messages_paginated(session_id, limit, before)
```

## 六、数据迁移策略

### 6.1 迁移脚本

```python
# backend/app/migrations/migrate_to_v2.py

"""
数据库迁移脚本：将旧版 chat_sessions 表数据迁移到新表结构

运行方式：
python -m backend.app.migrations.migrate_to_v2
"""

from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import List, Dict

from ..core.database import SessionLocal
from ..models.db_models import ChatSession as OldChatSession
from ..models.db_models import User, ChatSessionV2, MessageV2, AttachmentV2
from ..services.user_service import UserService
from ..services.session_service import SessionService

def migrate_sessions():
    """执行数据迁移"""
    db = SessionLocal()
    user_service = UserService(db)
    session_service = SessionService(db)
    
    # 1. 获取或创建默认用户
    default_user = user_service.get_or_create_default_user()
    print(f"[迁移] 使用默认用户: {default_user.user_id}")
    
    # 2. 获取所有旧会话
    old_sessions = db.query(OldChatSession).all()
    print(f"[迁移] 找到 {len(old_sessions)} 个旧会话")
    
    success_count = 0
    failed_sessions = []
    
    for old_session in old_sessions:
        try:
            # 3. 创建新会话
            new_session = ChatSessionV2(
                id=old_session.id,
                user_id=default_user.user_id,
                title=old_session.title,
                persona_id=old_session.persona_id,
                mode=old_session.mode,
                created_at=old_session.created_at,
                updated_at=old_session.created_at
            )
            db.add(new_session)
            
            # 4. 迁移消息
            messages = old_session.messages or []
            for msg_data in messages:
                message = MessageV2(
                    id=msg_data.get("id", str(uuid.uuid4())),
                    session_id=old_session.id,
                    role=msg_data.get("role", "user"),
                    content=msg_data.get("content", ""),
                    timestamp=msg_data.get("timestamp", int(datetime.now().timestamp() * 1000)),
                    is_error=msg_data.get("isError", False),
                    mode=msg_data.get("mode"),
                    grounding_metadata=msg_data.get("groundingMetadata"),
                    url_context_metadata=msg_data.get("urlContextMetadata"),
                    browser_operation_id=msg_data.get("browserOperationId"),
                    created_at=msg_data.get("timestamp", int(datetime.now().timestamp() * 1000))
                )
                db.add(message)
                
                # 5. 迁移附件
                attachments = msg_data.get("attachments", [])
                for att_data in attachments:
                    # 规范化 URL：只保留云存储 URL
                    url = att_data.get("url", "")
                    if url and not (url.startswith("http://") or url.startswith("https://")):
                        url = None
                    
                    attachment = AttachmentV2(
                        id=att_data.get("id", str(uuid.uuid4())),
                        message_id=message.id,
                        mime_type=att_data.get("mimeType", "application/octet-stream"),
                        name=att_data.get("name", "unknown"),
                        url=url,
                        upload_status=att_data.get("uploadStatus", "completed"),
                        upload_task_id=att_data.get("uploadTaskId"),
                        upload_error=att_data.get("uploadError"),
                        created_at=int(datetime.now().timestamp() * 1000)
                    )
                    db.add(attachment)
            
            db.commit()
            success_count += 1
            print(f"[迁移] ✓ 会话 {old_session.id[:8]}... 迁移成功")
            
        except Exception as e:
            db.rollback()
            failed_sessions.append({
                "session_id": old_session.id,
                "error": str(e)
            })
            print(f"[迁移] ✗ 会话 {old_session.id[:8]}... 迁移失败: {e}")
    
    # 6. 输出统计
    print("\n" + "="*50)
    print(f"[迁移完成]")
    print(f"  成功: {success_count}")
    print(f"  失败: {len(failed_sessions)}")
    if failed_sessions:
        print(f"\n失败的会话:")
        for failed in failed_sessions:
            print(f"  - {failed['session_id']}: {failed['error']}")
    
    db.close()
    return {
        "success": success_count,
        "failed": len(failed_sessions),
        "failed_sessions": failed_sessions
    }

if __name__ == "__main__":
    migrate_sessions()
```

### 6.2 迁移执行步骤

1. **备份数据库**
   ```bash
   # SQLite
   cp database.db database.db.backup
   
   # PostgreSQL
   pg_dump -U user -d database > backup.sql
   ```

2. **创建新表**
   ```python
   # 在 main.py 中导入新模型
   from .models.db_models import User, ChatSessionV2, MessageV2, AttachmentV2
   Base.metadata.create_all(bind=engine)
   ```

3. **执行迁移**
   ```bash
   python -m backend.app.migrations.migrate_to_v2
   ```

4. **验证数据**
   - 检查新表中的数据量是否与旧表一致
   - 随机抽样验证数据完整性
   - 测试 API 接口是否正常工作

5. **切换使用新表**
   - 更新路由使用新的服务层
   - 保留旧表作为备份（可选）

## 七、前端适配层更新

### 7.1 更新 LocalStorageDB

```typescript
// frontend/services/db.ts

class LocalStorageDB {
    // 会话元数据
    async getSessions(): Promise<ChatSession[]> {
        const sessions = this.get<SessionMetadata[]>('flux_sessions_v2', []);
        // 聚合消息数据返回完整格式
        return sessions.map(s => this.aggregateSession(s));
    }
    
    // 消息独立存储
    async getMessages(sessionId: string): Promise<Message[]> {
        const allMessages = this.get<StoredMessage[]>('flux_messages', []);
        return allMessages
            .filter(m => m.sessionId === sessionId)
            .sort((a, b) => a.timestamp - b.timestamp);
    }
    
    async saveMessage(sessionId: string, message: Message): Promise<void> {
        const messages = this.get<StoredMessage[]>('flux_messages', []);
        const existingIndex = messages.findIndex(m => m.id === message.id);
        if (existingIndex >= 0) {
            messages[existingIndex] = { ...message, sessionId };
        } else {
            messages.push({ ...message, sessionId });
        }
        this.set('flux_messages', messages);
    }
    
    // 附件独立存储
    async getAttachments(messageId: string): Promise<Attachment[]> {
        const allAttachments = this.get<StoredAttachment[]>('flux_attachments', []);
        return allAttachments.filter(a => a.messageId === messageId);
    }
    
    async saveAttachment(messageId: string, attachment: Attachment): Promise<void> {
        const attachments = this.get<StoredAttachment[]>('flux_attachments', []);
        const existingIndex = attachments.findIndex(a => a.id === attachment.id);
        if (existingIndex >= 0) {
            attachments[existingIndex] = { ...attachment, messageId };
        } else {
            attachments.push({ ...attachment, messageId });
        }
        this.set('flux_attachments', attachments);
    }
    
    // 聚合会话数据
    private aggregateSession(metadata: SessionMetadata): ChatSession {
        const messages = this.getMessages(metadata.id);
        return {
            ...metadata,
            messages: messages.map(msg => ({
                ...msg,
                attachments: this.getAttachments(msg.id)
            }))
        };
    }
}
```

### 7.2 更新用户认证

```typescript
// frontend/services/auth.ts

export interface User {
    userId: string;
    email: string;
    name: string;
    createdAt: number;
    lastLoginAt?: number;
}

export class AuthService {
    private static readonly AUTH_TOKEN_KEY = 'flux_auth_token';
    private static readonly USER_KEY = 'flux_user';
    
    static async login(email: string, password: string): Promise<User> {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        if (!response.ok) {
            throw new Error('登录失败');
        }
        
        const user = await response.json();
        localStorage.setItem(this.AUTH_TOKEN_KEY, user.userId);
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        return user;
    }
    
    static async register(email: string, password: string, name: string): Promise<User> {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, name })
        });
        
        if (!response.ok) {
            throw new Error('注册失败');
        }
        
        const user = await response.json();
        localStorage.setItem(this.AUTH_TOKEN_KEY, user.userId);
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        return user;
    }
    
    static getCurrentUser(): User | null {
        const userStr = localStorage.getItem(this.USER_KEY);
        return userStr ? JSON.parse(userStr) : null;
    }
    
    static getUserId(): string {
        return localStorage.getItem(this.AUTH_TOKEN_KEY) || 'default';
    }
    
    static logout(): void {
        localStorage.removeItem(this.AUTH_TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
    }
}
```

## 八、实施步骤

### 阶段一：数据库模型创建（1-2天）

1. ✅ 创建新的数据库模型文件
   - `User` 模型
   - `ChatSessionV2` 模型
   - `MessageV2` 模型
   - `AttachmentV2` 模型

2. ✅ 创建数据库迁移脚本
   - 创建新表
   - 创建索引

3. ✅ 测试数据库模型
   - 验证表结构
   - 验证外键约束
   - 验证级联删除

### 阶段二：服务层实现（2-3天）

1. ✅ 实现 `UserService`
   - 用户创建、认证、查询
   - 密码加密（bcrypt）

2. ✅ 实现 `SessionService`
   - 会话 CRUD
   - 消息聚合逻辑
   - 附件 URL 规范化

3. ✅ 单元测试
   - 服务层功能测试
   - 边界情况测试

### 阶段三：API 层重构（2-3天）

1. ✅ 创建用户认证 API
   - `/api/auth/login`
   - `/api/auth/register`
   - `/api/auth/me`

2. ✅ 重构会话管理 API
   - 更新路由使用新服务层
   - 保持 API 向后兼容

3. ✅ API 测试
   - 接口功能测试
   - 错误处理测试

### 阶段四：数据迁移（1-2天）

1. ✅ 开发迁移脚本
   - 数据提取
   - 数据转换
   - 数据导入

2. ✅ 执行迁移
   - 备份数据库
   - 执行迁移
   - 验证数据完整性

3. ✅ 回滚方案
   - 准备回滚脚本
   - 测试回滚流程

### 阶段五：前端适配（2-3天）

1. ✅ 更新数据库适配层
   - 更新 `LocalStorageDB`
   - 支持新的数据结构

2. ✅ 更新用户认证
   - 替换模拟登录
   - 集成真实认证 API

3. ✅ 前端测试
   - 功能测试
   - 兼容性测试

### 阶段六：测试与优化（2-3天）

1. ✅ 集成测试
   - 端到端测试
   - 性能测试

2. ✅ 优化
   - 查询性能优化
   - 索引优化

3. ✅ 文档更新
   - API 文档
   - 部署文档

## 九、测试策略

### 9.1 单元测试

```python
# backend/tests/test_user_service.py

import pytest
from backend.app.services.user_service import UserService
from backend.app.models.db_models import User

def test_create_user():
    """测试用户创建"""
    # 测试代码
    pass

def test_authenticate_user():
    """测试用户认证"""
    # 测试代码
    pass

def test_get_user_by_email():
    """测试根据邮箱获取用户"""
    # 测试代码
    pass
```

### 9.2 集成测试

```python
# backend/tests/test_session_api.py

import pytest
from fastapi.testclient import TestClient

def test_get_sessions():
    """测试获取会话列表"""
    # 测试代码
    pass

def test_save_session():
    """测试保存会话"""
    # 测试代码
    pass
```

### 9.3 属性测试（Property-Based Testing）

```python
# backend/tests/test_properties.py

from hypothesis import given, strategies as st

@given(
    session_id=st.uuids().map(str),
    messages=st.lists(st.builds(Message, content=st.text(min_size=1)), min_size=1, max_size=100)
)
def test_message_count_accuracy(session_id, messages):
    """Property 8: 消息计数准确性"""
    # 测试代码
    pass
```

## 十、依赖与配置

### 10.1 Python 依赖

```txt
# requirements.txt 新增依赖

bcrypt>=4.0.0  # 密码加密
```

### 10.2 环境变量

```env
# .env 文件（无需新增，使用现有配置）

DATABASE_URL=sqlite:///./database.db
# 或
DATABASE_URL=postgresql://user:password@localhost/dbname
```

## 十一、风险评估与应对

### 11.1 风险点

1. **数据迁移风险**
   - 风险：迁移过程中数据丢失或损坏
   - 应对：完整备份、分批次迁移、回滚方案

2. **API 兼容性风险**
   - 风险：前端调用失败
   - 应对：保持 API 格式兼容、充分测试

3. **性能风险**
   - 风险：查询性能下降
   - 应对：优化索引、分页查询、性能测试

### 11.2 回滚方案

1. **数据库回滚**
   - 恢复备份数据库
   - 切换回旧表结构

2. **代码回滚**
   - Git 回退到重构前版本
   - 重新部署

## 十二、总结

本方案提供了完整的数据库重构和用户数据表优化实施方案，包括：

1. ✅ **完整的数据模型设计**：规范化表结构，支持多用户隔离
2. ✅ **服务层实现**：`UserService` 和 `SessionService` 处理业务逻辑
3. ✅ **API 层重构**：用户认证 API 和会话管理 API
4. ✅ **数据迁移策略**：完整的迁移脚本和验证流程
5. ✅ **前端适配**：更新数据库适配层和用户认证
6. ✅ **测试策略**：单元测试、集成测试、属性测试
7. ✅ **实施步骤**：分阶段实施，降低风险

通过本方案的实施，系统将实现：
- 数据规范化存储，避免 JSON 字段无限膨胀
- 多用户数据隔离，支持真正的用户认证
- 高效的查询性能，支持分页和索引优化
- 向后兼容的 API，前端无需大规模修改
