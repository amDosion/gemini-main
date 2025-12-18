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
    """聊天会话表 - 存储聊天会话信息"""
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True)  # UUID字符串
    title = Column(String, nullable=False)  # 会话标题
    persona_id = Column(String, nullable=True)  # 使用的角色ID
    mode = Column(String, nullable=True)  # 会话模式 (chat, image-gen等)
    messages = Column(JSON, default=list)  # 消息列表（Message[]）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式（与前端ChatSession接口兼容）"""
        return {
            "id": self.id,
            "title": self.title,
            "messages": self.messages or [],
            "createdAt": self.created_at,
            "personaId": self.persona_id,
            "mode": self.mode
        }


class Persona(Base):
    """角色表 - 存储AI角色配置"""
    __tablename__ = "personas"

    id = Column(String, primary_key=True, index=True)  # UUID字符串
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
