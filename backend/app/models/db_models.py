from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, func
from ..core.database import Base
from datetime import datetime

class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    from_user = Column(String, nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class ConfigProfile(Base):
    """配置档案表 - 存储AI提供商的配置信息"""
    __tablename__ = "config_profiles"

    id = Column(String, primary_key=True, index=True)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False)  # 配置名称
    provider_id = Column(String, nullable=False)  # 提供商ID (google, openai, tongyi等)
    api_key = Column(Text, nullable=False)  # API密钥（加密存储）
    base_url = Column(String, nullable=True)  # 基础URL
    protocol = Column(String, nullable=False)  # 协议类型 (google, openai)
    is_proxy = Column(Boolean, default=False)  # 是否为代理/自定义URL
    hidden_models = Column(JSON, default=list)  # 隐藏的模型ID列表
    cached_model_count = Column(Integer, default=0)  # 缓存的模型数量
    saved_models = Column(JSON, default=list)  # 保存的模型配置列表（ModelConfig[]）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式（与前端ConfigProfile接口兼容）"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "providerId": self.provider_id,
            "apiKey": self.api_key,
            "baseUrl": self.base_url or "",
            "protocol": self.protocol,
            "isProxy": self.is_proxy,
            "hiddenModels": self.hidden_models or [],
            "cachedModelCount": self.cached_model_count or 0,
            "savedModels": self.saved_models or [],
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }


class UserSettings(Base):
    """用户设置表 - 存储用户级别的设置（如活动配置ID）"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False, default="default")  # 用户ID，默认"default"支持单用户
    active_profile_id = Column(String, nullable=True)  # 当前活动的配置ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatSession(Base):
    """聊天会话表 - 存储聊天会话元数据"""
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    title = Column(String, nullable=False)  # 会话标题
    persona_id = Column(String, nullable=True)  # 使用的角色ID
    mode = Column(String, nullable=True)  # 会话模式 (chat, image-gen等)
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    # v3 架构：消息数据存储在 message_index + 各模式表，附件存储在 message_attachments

    def to_dict(self):
        """转换为字典格式（与前端ChatSession接口兼容）"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "title": self.title,
            "createdAt": self.created_at,
            "personaId": self.persona_id,
            "mode": self.mode
        }


# ============================================
# v3 聊天存储优化模型 (Chat Storage Optimization v3)
# ============================================

class MessageIndex(Base):
    """
    消息索引表 - 核心路由层
    
    作用：
    - 快速定位：通过 id 查询，直接获取 table_name，O(1) 定位到具体模式表
    - 跨模式查询：通过 session_id 查询，获取所有模式的消息索引
    - 链式关系：保存 parent_id，支持对话分支管理
    - 顺序稳定性：seq 字段确保消息顺序唯一稳定
    """
    __tablename__ = "message_index"

    id = Column(String(36), primary_key=True)  # 消息 ID（对应前端 Message.id）
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)  # 会话 ID
    mode = Column(String(50), nullable=False)  # 消息模式（chat/image-gen/video-gen...）
    table_name = Column(String(50), nullable=False)  # 物理表名（messages_chat/messages_image_gen/messages_generic）
    seq = Column(Integer, nullable=False)  # 全局顺序：按前端 messages[] 数组下标赋值
    timestamp = Column(BigInteger, nullable=False)  # 消息时间戳（ms）
    parent_id = Column(String(36), nullable=True)  # 链式关联（同模式内）

    # 复合索引在 __table_args__ 中定义
    __table_args__ = (
        # 主排序索引：按会话+顺序查询
        # CREATE INDEX idx_message_index_session_seq ON message_index(session_id, seq)
        # 模式过滤索引：按会话+模式+顺序查询
        # CREATE INDEX idx_message_index_session_mode_seq ON message_index(session_id, mode, seq)
    )

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "sessionId": self.session_id,
            "mode": self.mode,
            "tableName": self.table_name,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "parentId": self.parent_id
        }


class MessagesChat(Base):
    """
    chat 模式消息表

    存储普通聊天消息，包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 复杂结构：metadata_json（grounding/tool/urlContext 等）
    """
    __tablename__ = "messages_chat"

    id = Column(String(36), primary_key=True)  # Message.id（前端生成 UUIDv4）
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)  # 会话 ID
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)  # 纯文本消息内容
    timestamp = Column(BigInteger, nullable=False)  # 时间戳（ms）
    is_error = Column(Boolean, default=False)  # Message.isError
    metadata_json = Column(Text, nullable=True)  # groundingMetadata/urlContextMetadata/toolCalls/toolResults 等

    def to_dict(self):
        """转换为字典格式（兼容前端 Message 结构）"""
        import json
        result = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "isError": self.is_error
        }
        # 解析 metadata_json 并合并到结果中
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesImageGen(Base):
    """
    image-gen 模式消息表

    存储图像生成消息，包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 图像特定字段：image_size, image_style, image_quality, image_count, model_name
    - 复杂结构：metadata_json（与 messages_chat 保持一致）
    """
    __tablename__ = "messages_image_gen"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)  # 提示词或生成结果描述
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 图像生成特定字段
    image_size = Column(String(20), nullable=True)  # 图片尺寸（1024x1024）
    image_style = Column(String(50), nullable=True)  # 风格（vivid/natural）
    image_quality = Column(String(20), nullable=True)  # 质量（standard/hd）
    image_count = Column(Integer, default=1)  # 生成数量
    model_name = Column(String(100), nullable=True)  # 使用的模型

    # 复杂结构使用 JSON 存储
    metadata_json = Column(Text, nullable=True)

    def to_dict(self):
        """转换为字典格式（兼容前端 Message 结构）"""
        import json
        result = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "isError": self.is_error,
            "imageSize": self.image_size,
            "imageStyle": self.image_style,
            "imageQuality": self.image_quality,
            "imageCount": self.image_count,
            "modelName": self.model_name
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesVideoGen(Base):
    """
    video-gen 模式消息表

    存储视频生成消息，包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 视频特定字段：video_duration, video_resolution, video_fps, model_name
    - 复杂结构：metadata_json（与 messages_chat 保持一致）
    """
    __tablename__ = "messages_video_gen"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)  # 提示词或生成结果描述
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 视频生成特定字段
    video_duration = Column(Integer, nullable=True)  # 视频时长（秒）
    video_resolution = Column(String(20), nullable=True)  # 分辨率（1920x1080）
    video_fps = Column(Integer, nullable=True)  # 帧率
    model_name = Column(String(100), nullable=True)  # 使用的模型

    # 复杂结构使用 JSON 存储
    metadata_json = Column(Text, nullable=True)

    def to_dict(self):
        """转换为字典格式（兼容前端 Message 结构）"""
        import json
        result = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "isError": self.is_error,
            "videoDuration": self.video_duration,
            "videoResolution": self.video_resolution,
            "videoFps": self.video_fps,
            "modelName": self.model_name
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesGeneric(Base):
    """
    兜底表 - 覆盖所有未做专表优化的模式

    支持模式：image-edit, image-outpainting, audio-gen, pdf-extract,
             virtual-try-on, deep-research 等

    使用 metadata_json 存储模式特定数据
    """
    __tablename__ = "messages_generic"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 使用 JSON 存储模式特定数据
    metadata_json = Column(Text, nullable=True)

    def to_dict(self):
        """转换为字典格式（兼容前端 Message 结构）"""
        import json
        result = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "isError": self.is_error
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessageAttachment(Base):
    """
    消息附件表 - 所有模式共享

    存储消息的附件信息，包含：
    - 基础字段：id, session_id, message_id, mime_type, name, size
    - URL 字段：url（云端永久）, temp_url（临时）, file_uri（通用文件 URI）
    - 上传状态：upload_status, upload_task_id, upload_error
    - Google Files API：google_file_uri, google_file_expiry

    注意：同一个附件 ID 可以关联到多条消息，因此使用复合主键 (id, message_id)
    """
    __tablename__ = "message_attachments"

    id = Column(String(36), primary_key=True)  # Attachment.id
    message_id = Column(String(36), primary_key=True, index=True)  # 所属消息（复合主键）
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)  # 冗余字段，方便按会话查询
    mime_type = Column(String(100), nullable=True)  # Attachment.mimeType
    name = Column(String(255), nullable=True)  # Attachment.name
    url = Column(Text, nullable=True)  # 云端/持久 URL（权威来源）
    temp_url = Column(Text, nullable=True)  # Attachment.tempUrl（blob/data/临时链接）
    file_uri = Column(Text, nullable=True)  # 通用文件 URI（Google Files API 等）
    upload_status = Column(String(20), default='pending')  # pending/uploading/completed/failed
    upload_task_id = Column(String(36), nullable=True)  # 关联 UploadTask.id
    upload_error = Column(Text, nullable=True)  # 上传失败原因
    google_file_uri = Column(String(500), nullable=True)  # Google Files API URI
    google_file_expiry = Column(BigInteger, nullable=True)  # 过期时间（ms）
    size = Column(BigInteger, nullable=True)  # 文件大小

    def to_dict(self):
        """转换为字典格式（兼容前端 Attachment 结构）"""
        return {
            "id": self.id,
            "messageId": self.message_id,
            "mimeType": self.mime_type,
            "name": self.name,
            "url": self.url,
            "tempUrl": self.temp_url,
            "fileUri": self.file_uri,
            "uploadStatus": self.upload_status,
            "uploadTaskId": self.upload_task_id,
            "uploadError": self.upload_error,
            "googleFileUri": self.google_file_uri,
            "googleFileExpiry": self.google_file_expiry,
            "size": self.size
        }


class Persona(Base):
    """角色表 - 存储AI角色配置"""
    __tablename__ = "personas"

    id = Column(String, primary_key=True, index=True)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False)  # 角色名称
    description = Column(String, nullable=True)  # 角色描述
    system_prompt = Column(Text, nullable=False)  # 系统提示词
    icon = Column(String, nullable=False)  # 图标标识符
    category = Column(String, nullable=True)  # 分类
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式（与前端Persona接口兼容）"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "description": self.description or "",
            "systemPrompt": self.system_prompt,
            "icon": self.icon,
            "category": self.category or ""
        }


class StorageConfig(Base):
    """云存储配置表 - 存储图床配置信息"""
    __tablename__ = "storage_configs"

    id = Column(String, primary_key=True, index=True)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False)  # 配置名称
    provider = Column(String, nullable=False)  # 提供商类型 (lsky, aliyun-oss, local)
    enabled = Column(Boolean, default=True)  # 是否启用
    config = Column(JSON, nullable=False)  # 配置详情（JSON格式）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式（与前端StorageConfig接口兼容）"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "provider": self.provider,
            "enabled": self.enabled,
            "config": self.config,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }


class ActiveStorage(Base):
    """当前激活的存储配置"""
    __tablename__ = "active_storage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False, default="default")  # 用户ID
    storage_id = Column(String, nullable=True)  # 当前激活的存储配置ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UploadTask(Base):
    """上传任务表 - 记录图片上传到云存储的任务"""
    __tablename__ = "upload_tasks"

    id = Column(String, primary_key=True, index=True)  # 任务ID（UUID）
    session_id = Column(String, nullable=True)  # 关联的会话ID（用于更新数据库）
    message_id = Column(String, nullable=True)  # 关联的消息ID
    attachment_id = Column(String, nullable=True)  # 关联的附件ID
    source_url = Column(String, nullable=True)  # 源URL（DashScope临时URL，可选）
    source_file_path = Column(String, nullable=True)  # 源文件路径（本地临时文件）
    target_url = Column(String, nullable=True)  # 目标URL（云存储永久URL）
    filename = Column(String, nullable=False)  # 文件名
    storage_id = Column(String, nullable=True)  # 使用的存储配置ID
    priority = Column(String, nullable=True, default='normal')  # 优先级：high/normal/low
    retry_count = Column(Integer, nullable=True, default=0)  # 重试次数
    status = Column(String, nullable=False, default='pending')  # pending/uploading/completed/failed
    error_message = Column(String, nullable=True)  # 错误信息
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    completed_at = Column(BigInteger, nullable=True)  # 完成时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "messageId": self.message_id,
            "attachmentId": self.attachment_id,
            "sourceUrl": self.source_url,
            "sourceFilePath": self.source_file_path,
            "targetUrl": self.target_url,
            "filename": self.filename,
            "storageId": self.storage_id,
            "priority": self.priority,
            "retryCount": self.retry_count,
            "status": self.status,
            "errorMessage": self.error_message,
            "createdAt": self.created_at,
            "completedAt": self.completed_at
        }


# ============================================
# 认证系统模型 (Authentication System Models)
# ============================================

import secrets
import string


def generate_user_id() -> str:
    """
    生成 gemini2026_ 格式的唯一用户 ID
    格式: gemini2026_ + 8位随机字母数字
    示例: gemini2026_a1b2c3d4
    """
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(8))
    return f"gemini2026_{suffix}"


def generate_uuid() -> str:
    """生成通用 UUID 字符串"""
    import uuid
    return str(uuid.uuid4())


class User(Base):
    """用户表 - 存储用户认证信息"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=generate_user_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    name = Column(String, nullable=True)
    status = Column(String, nullable=False, default='active')  # active, suspended, banned, pending_verification
    status_reason = Column(Text, nullable=True)
    access_token = Column(Text, nullable=True)  # ✅ 存储 access_token（不使用 cookie）
    token_expires_at = Column(DateTime(timezone=True), nullable=True)  # token 过期时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """转换为字典格式（不包含敏感信息）"""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }


class RefreshToken(Base):
    """刷新令牌表 - 存储用户的刷新令牌"""
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)  # 关联 users.id
    token_hash = Column(Text, nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "revokedAt": self.revoked_at.isoformat() if self.revoked_at else None
        }



class IPLoginHistory(Base):
    """IP 登录历史表 - 记录用户登录的 IP 地址"""
    __tablename__ = "ip_login_history"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)  # 关联 users.id
    ip_address = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # login, logout, failed_login, token_refresh
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "ipAddress": self.ip_address,
            "action": self.action,
            "userAgent": self.user_agent,
            "createdAt": self.created_at.isoformat() if self.created_at else None
        }


class IPBlocklist(Base):
    """IP 黑名单表 - 存储被封禁的 IP 地址"""
    __tablename__ = "ip_blocklist"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    ip_address = Column(String, unique=True, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    blocked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)  # 管理员用户 ID

    def to_dict(self):
        return {
            "id": self.id,
            "ipAddress": self.ip_address,
            "reason": self.reason,
            "blockedAt": self.blocked_at.isoformat() if self.blocked_at else None,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
            "createdBy": self.created_by
        }


class AccountStatusHistory(Base):
    """账户状态历史表 - 记录账户状态变更"""
    __tablename__ = "account_status_history"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)  # 关联 users.id
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    changed_by = Column(String, nullable=True)  # 管理员用户 ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "oldStatus": self.old_status,
            "newStatus": self.new_status,
            "reason": self.reason,
            "changedBy": self.changed_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None
        }


class UserOnlineStatus(Base):
    """用户在线状态表 - 记录用户的在线状态"""
    __tablename__ = "user_online_status"

    user_id = Column(String, primary_key=True, index=True)  # 关联 users.id
    is_online = Column(Boolean, default=False)
    last_active = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "userId": self.user_id,
            "isOnline": self.is_online,
            "lastActive": self.last_active.isoformat() if self.last_active else None,
            "lastLoginIp": self.last_login_ip,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }


class ImagenConfig(Base):
    """Imagen 配置表 - 存储用户的图像生成 API 配置"""
    __tablename__ = "imagen_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, unique=True, index=True)  # 关联 users.id，每个用户只有一条配置
    api_mode = Column(String, nullable=False, default='gemini_api')  # 'gemini_api' or 'vertex_ai'
    
    # Vertex AI 配置（仅在 api_mode='vertex_ai' 时使用）
    vertex_ai_project_id = Column(String, nullable=True)
    vertex_ai_location = Column(String, nullable=True, default='us-central1')
    vertex_ai_credentials_json = Column(Text, nullable=True)  # 加密存储的 service account JSON
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """转换为字典格式（与前端 ImagenConfig 接口兼容）"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "apiMode": self.api_mode,
            "vertexAiProjectId": self.vertex_ai_project_id,
            "vertexAiLocation": self.vertex_ai_location or 'us-central1',
            "vertexAiCredentialsJson": self.vertex_ai_credentials_json,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }
