from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, Float, func
from ..core.database import Base
from datetime import datetime
import uuid

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

    支持模式：image-outpainting, audio-gen, pdf-extract,
             virtual-try-on, deep-research 等

    注意：image-edit 相关模式已拆分为独立表：
    - image-chat-edit → messages_image_chat_edit
    - image-mask-edit → messages_image_mask_edit
    - image-inpainting → messages_image_inpainting
    - image-background-edit → messages_image_background_edit
    - image-recontext → messages_image_recontext

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


class MessagesImageChatEdit(Base):
    """
    image-chat-edit 模式消息表 - 对话式图片编辑
    
    存储对话式图片编辑消息，使用 Google Chat SDK 进行多轮编辑。
    包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 对话式编辑特定字段：chat_id, model_name, edit_prompt
    - 复杂结构：metadata_json
    """
    __tablename__ = "messages_image_chat_edit"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 对话式编辑特定字段
    chat_id = Column(String(36), nullable=True, index=True)  # Google Chat ID
    model_name = Column(String(100), nullable=True)  # 使用的模型
    edit_prompt = Column(Text, nullable=True)  # 编辑提示词

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
            "chatId": self.chat_id,
            "modelName": self.model_name,
            "editPrompt": self.edit_prompt
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesImageMaskEdit(Base):
    """
    image-mask-edit 模式消息表 - 带 mask 的精确编辑
    
    存储带 mask 的精确图片编辑消息，使用 Vertex AI Imagen。
    包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - Mask 编辑特定字段：edit_mode, mask_mode, guidance_scale, model_name
    - 复杂结构：metadata_json
    """
    __tablename__ = "messages_image_mask_edit"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # Mask 编辑特定字段
    edit_mode = Column(String(50), nullable=True)  # inpainting-insert/inpainting-remove/outpainting
    mask_mode = Column(String(50), nullable=True)  # user-provided/auto-generated
    guidance_scale = Column(String(20), nullable=True)  # 使用 String 存储，支持范围值
    model_name = Column(String(100), nullable=True)  # 使用的模型
    number_of_images = Column(Integer, default=1)  # 生成数量
    aspect_ratio = Column(String(20), nullable=True)  # 图片比例

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
            "editMode": self.edit_mode,
            "maskMode": self.mask_mode,
            "guidanceScale": self.guidance_scale,
            "modelName": self.model_name,
            "numberOfImages": self.number_of_images,
            "aspectRatio": self.aspect_ratio
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesImageInpainting(Base):
    """
    image-inpainting 模式消息表 - 图片修复
    
    存储图片修复消息，用于修复图片中的缺陷或移除不需要的元素。
    包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 修复特定字段：repair_type, model_name
    - 复杂结构：metadata_json
    """
    __tablename__ = "messages_image_inpainting"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 修复特定字段
    repair_type = Column(String(50), nullable=True)  # defect-removal/object-removal/content-fill
    model_name = Column(String(100), nullable=True)  # 使用的模型
    guidance_scale = Column(String(20), nullable=True)

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
            "repairType": self.repair_type,
            "modelName": self.model_name,
            "guidanceScale": self.guidance_scale
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesImageBackgroundEdit(Base):
    """
    image-background-edit 模式消息表 - 背景编辑
    
    存储背景编辑消息，用于替换或修改图片背景。
    包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 背景编辑特定字段：background_type, model_name
    - 复杂结构：metadata_json
    """
    __tablename__ = "messages_image_background_edit"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 背景编辑特定字段
    background_type = Column(String(50), nullable=True)  # replace/remove/blur/enhance
    model_name = Column(String(100), nullable=True)  # 使用的模型
    guidance_scale = Column(String(20), nullable=True)

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
            "backgroundType": self.background_type,
            "modelName": self.model_name,
            "guidanceScale": self.guidance_scale
        }
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
                if isinstance(metadata, dict):
                    result.update(metadata)
            except (json.JSONDecodeError, TypeError):
                pass
        return result


class MessagesImageRecontext(Base):
    """
    image-recontext 模式消息表 - 重新上下文
    
    存储重新上下文消息，用于改变图片的上下文环境或场景。
    包含：
    - 基础字段：id, session_id, role, content, timestamp, is_error
    - 重新上下文特定字段：context_type, model_name
    - 复杂结构：metadata_json
    """
    __tablename__ = "messages_image_recontext"

    id = Column(String(36), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' | 'model' | 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    is_error = Column(Boolean, default=False)

    # 重新上下文特定字段
    context_type = Column(String(50), nullable=True)  # scene-change/environment-swap/style-transfer
    model_name = Column(String(100), nullable=True)  # 使用的模型
    guidance_scale = Column(String(20), nullable=True)

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
            "contextType": self.context_type,
            "modelName": self.model_name,
            "guidanceScale": self.guidance_scale
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


class GoogleChatSession(Base):
    """
    Google Chat 会话表 - 存储对话式图片编辑的 Chat 会话元数据
    
    关联关系：
    - chat_id: Google SDK Chat 对象的标识符（UUID）
    - frontend_session_id: 前端会话 ID（关联 ChatSession.id）
    - user_id: 用户 ID
    
    注意：
    - 实际的消息历史存储在 MessageIndex + MessagesGeneric（mode='image-edit'）
    - 附件存储在 MessageAttachment
    - 此表仅存储 Google Chat SDK 的会话元数据，用于重建 Chat 对象
    """
    __tablename__ = "google_chat_sessions"

    chat_id = Column(String(36), primary_key=True)  # Google Chat ID（UUID）
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    frontend_session_id = Column(String(36), nullable=False, index=True)  # 前端会话ID（ChatSession.id）
    model_name = Column(String(100), nullable=False)  # 使用的模型名称
    config_json = Column(Text, nullable=True)  # Chat 配置（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（ms）
    last_used_at = Column(BigInteger, nullable=False)  # 最后使用时间（ms）
    is_active = Column(Boolean, default=True)  # 是否活跃

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "chatId": self.chat_id,
            "userId": self.user_id,
            "frontendSessionId": self.frontend_session_id,
            "modelName": self.model_name,
            "createdAt": self.created_at,
            "lastUsedAt": self.last_used_at,
            "isActive": self.is_active
        }
        if self.config_json:
            try:
                result["config"] = json.loads(self.config_json)
            except (json.JSONDecodeError, TypeError):
                result["config"] = None
        return result


class Persona(Base):
    """角色表 - 存储AI角色配置"""
    __tablename__ = "user_ai_personas"

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
    source_ai_url = Column(Text, nullable=True)  # 【新增】AI返回URL（Base64或HTTP）
    source_attachment_id = Column(String, nullable=True)  # 【新增】复用已有附件ID
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
            "sourceAiUrl": self.source_ai_url,
            "sourceAttachmentId": self.source_attachment_id,
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


class VertexAIConfig(Base):
    """Vertex AI 配置表 - 存储用户的 Vertex AI 配置"""
    __tablename__ = "vertex_ai_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, unique=True, index=True)  # 关联 users.id，每个用户只有一条配置
    api_mode = Column(String, nullable=False, default='gemini_api')  # 'gemini_api' or 'vertex_ai'
    
    # Vertex AI 配置（仅在 api_mode='vertex_ai' 时使用）
    vertex_ai_project_id = Column(String, nullable=True)
    vertex_ai_location = Column(String, nullable=True, default='us-central1')
    vertex_ai_credentials_json = Column(Text, nullable=True)  # 加密存储的 service account JSON
    
    # 模型配置（参考 config_profiles 的设计）
    hidden_models = Column(JSON, default=list)  # 隐藏的模型ID列表
    saved_models = Column(JSON, default=list)  # 保存的模型配置列表（ModelConfig[]）
    
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
            "hiddenModels": self.hidden_models or [],
            "savedModels": self.saved_models or [],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }


# ============================================
# Agent Engine 模型 (Agent Engine Models)
# ============================================

class AgentMemoryBank(Base):
    """
    Memory Bank 实例表 - 存储 Vertex AI Memory Bank 实例元数据
    
    关联关系：
    - user_id: 用户 ID
    - vertex_memory_bank_id: Vertex AI Memory Bank 资源 ID
    - config_json: Memory Bank 配置（JSON）
    """
    __tablename__ = "agent_memory_banks"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False)  # Memory Bank 名称
    vertex_memory_bank_id = Column(String, nullable=True)  # Vertex AI Memory Bank 资源 ID
    config_json = Column(Text, nullable=True)  # Memory Bank 配置（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "vertexMemoryBankId": self.vertex_memory_bank_id,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        if self.config_json:
            try:
                result["config"] = json.loads(self.config_json)
            except (json.JSONDecodeError, TypeError):
                result["config"] = None
        return result


class AgentMemory(Base):
    """
    记忆数据表 - 存储 Memory Bank 中的记忆内容
    
    关联关系：
    - user_id: 用户 ID
    - memory_bank_id: 关联的 Memory Bank ID
    - session_id: 关联的会话 ID（可选）
    - content: 记忆内容
    - metadata_json: 记忆元数据（JSON）
    """
    __tablename__ = "agent_memories"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    memory_bank_id = Column(String, nullable=False, index=True)  # Memory Bank ID
    session_id = Column(String, nullable=True, index=True)  # 会话 ID（可选）
    vertex_memory_id = Column(String, nullable=True)  # Vertex AI Memory ID
    content = Column(Text, nullable=False)  # 记忆内容
    metadata_json = Column(Text, nullable=True)  # 记忆元数据（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "memoryBankId": self.memory_bank_id,
            "sessionId": self.session_id,
            "vertexMemoryId": self.vertex_memory_id,
            "content": self.content,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        if self.metadata_json:
            try:
                result["metadata"] = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = None
        return result


class AgentMemorySession(Base):
    """
    Memory Bank 会话表 - 存储 Memory Bank 会话元数据
    
    关联关系：
    - user_id: 用户 ID
    - memory_bank_id: 关联的 Memory Bank ID
    - session_id: 会话 ID
    - metadata_json: 会话元数据（JSON）
    """
    __tablename__ = "agent_memory_sessions"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    memory_bank_id = Column(String, nullable=False, index=True)  # Memory Bank ID
    session_id = Column(String, nullable=False, index=True)  # 会话 ID
    vertex_session_id = Column(String, nullable=True)  # Vertex AI Session ID
    metadata_json = Column(Text, nullable=True)  # 会话元数据（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    last_used_at = Column(BigInteger, nullable=False)  # 最后使用时间（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "memoryBankId": self.memory_bank_id,
            "sessionId": self.session_id,
            "vertexSessionId": self.vertex_session_id,
            "createdAt": self.created_at,
            "lastUsedAt": self.last_used_at
        }
        if self.metadata_json:
            try:
                result["metadata"] = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = None
        return result


class AgentCodeSandbox(Base):
    """
    代码执行沙箱表 - 存储 Vertex AI Sandbox 实例元数据
    
    关联关系：
    - user_id: 用户 ID
    - vertex_sandbox_id: Vertex AI Sandbox 资源 ID
    - config_json: 沙箱配置（JSON）
    - status: 沙箱状态
    """
    __tablename__ = "agent_code_sandboxes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    vertex_sandbox_id = Column(String, nullable=True)  # Vertex AI Sandbox 资源 ID
    config_json = Column(Text, nullable=True)  # 沙箱配置（JSON）
    status = Column(String, nullable=False, default='active')  # active/inactive/expired
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "vertexSandboxId": self.vertex_sandbox_id,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        if self.config_json:
            try:
                result["config"] = json.loads(self.config_json)
            except (json.JSONDecodeError, TypeError):
                result["config"] = None
        return result


class AgentArtifact(Base):
    """
    代码执行 Artifact 表 - 存储代码执行产生的 Artifact 元数据
    
    关联关系：
    - user_id: 用户 ID
    - sandbox_id: 关联的沙箱 ID
    - vertex_artifact_id: Vertex AI Artifact ID
    - gcs_uri: Google Cloud Storage URI
    """
    __tablename__ = "agent_artifacts"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    sandbox_id = Column(String, nullable=False, index=True)  # 沙箱 ID
    vertex_artifact_id = Column(String, nullable=True)  # Vertex AI Artifact ID
    gcs_uri = Column(Text, nullable=True)  # Google Cloud Storage URI
    metadata_json = Column(Text, nullable=True)  # Artifact 元数据（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "sandboxId": self.sandbox_id,
            "vertexArtifactId": self.vertex_artifact_id,
            "gcsUri": self.gcs_uri,
            "createdAt": self.created_at
        }
        if self.metadata_json:
            try:
                result["metadata"] = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = None
        return result


class AgentRegistry(Base):
    """
    智能体注册表 - 存储智能体注册信息
    
    关联关系：
    - user_id: 用户 ID
    - agent_type: 智能体类型
    - agent_card_json: Agent Card JSON
    - endpoint_url: 智能体端点 URL
    """
    __tablename__ = "agent_registry"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False)  # 智能体名称
    agent_type = Column(String, nullable=False)  # 智能体类型（adk/interactions/custom）
    agent_card_json = Column(Text, nullable=True)  # Agent Card JSON
    endpoint_url = Column(String, nullable=True)  # 智能体端点 URL
    status = Column(String, nullable=False, default='active')  # active/inactive/error
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "agentType": self.agent_type,
            "endpointUrl": self.endpoint_url,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        if self.agent_card_json:
            try:
                result["agentCard"] = json.loads(self.agent_card_json)
            except (json.JSONDecodeError, TypeError):
                result["agentCard"] = None
        return result


class AgentCard(Base):
    """
    Agent Card 定义表 - 存储 Agent Card 定义
    
    关联关系：
    - user_id: 用户 ID
    - agent_id: 关联的智能体 ID
    - card_json: Agent Card JSON
    - version: Agent Card 版本
    """
    __tablename__ = "agent_cards"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    agent_id = Column(String, nullable=False, index=True)  # 智能体 ID
    card_json = Column(Text, nullable=False)  # Agent Card JSON
    version = Column(String, nullable=False, default='1.0.0')  # Agent Card 版本
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "agentId": self.agent_id,
            "version": self.version,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        if self.card_json:
            try:
                result["card"] = json.loads(self.card_json)
            except (json.JSONDecodeError, TypeError):
                result["card"] = None
        return result


class WorkflowTemplate(Base):
    """工作流模板表 - 存储预定义的工作流模板"""
    __tablename__ = "workflow_templates"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False)  # 模板名称
    description = Column(Text, nullable=True)  # 模板描述
    category = Column(String, nullable=False, index=True)  # 模板分类（image-edit, excel-analysis, general等）
    workflow_type = Column(String, nullable=False)  # 工作流类型（sequential, parallel, coordinator）
    config_json = Column(Text, nullable=False)  # 工作流配置（节点、边、参数等，JSON格式）
    is_public = Column(Boolean, default=False)  # 是否公开（其他用户可见）
    version = Column(Integer, default=1)  # 版本号
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "workflowType": self.workflow_type,
            "isPublic": self.is_public,
            "version": self.version,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        try:
            result["config"] = json.loads(self.config_json)
        except (json.JSONDecodeError, TypeError):
            result["config"] = None
        return result


class A2ATask(Base):
    """
    A2A 协议任务表 - 存储 A2A 协议任务状态
    
    关联关系：
    - user_id: 用户 ID
    - agent_id: 关联的智能体 ID
    - task_id: A2A 任务 ID
    - context_id: A2A 上下文 ID
    - status: 任务状态
    """
    __tablename__ = "a2a_tasks"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    agent_id = Column(String, nullable=False, index=True)  # 智能体 ID
    task_id = Column(String, nullable=False, index=True)  # A2A 任务 ID
    context_id = Column(String, nullable=False, index=True)  # A2A 上下文 ID
    status = Column(String, nullable=False, default='submitted')  # submitted/working/completed/failed
    metadata_json = Column(Text, nullable=True)  # 任务元数据（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "agentId": self.agent_id,
            "taskId": self.task_id,
            "contextId": self.context_id,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
        if self.metadata_json:
            try:
                result["metadata"] = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = None
        return result


class A2AEvent(Base):
    """
    A2A 事件队列表 - 存储 A2A 协议事件
    
    关联关系：
    - task_id: 关联的任务 ID
    - event_type: 事件类型
    - event_data_json: 事件数据（JSON）
    """
    __tablename__ = "a2a_events"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    task_id = Column(String, nullable=False, index=True)  # 任务 ID
    event_type = Column(String, nullable=False)  # 事件类型
    event_data_json = Column(Text, nullable=True)  # 事件数据（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "taskId": self.task_id,
            "eventType": self.event_type,
            "createdAt": self.created_at
        }
        if self.event_data_json:
            try:
                result["eventData"] = json.loads(self.event_data_json)
            except (json.JSONDecodeError, TypeError):
                result["eventData"] = None
        return result


class SystemConfig(Base):
    """系统配置表 - 存储系统级别的配置（单例模式，只有一行数据）"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, default=1)  # 固定为 1，单例模式

    # 注册相关配置
    allow_registration = Column(Boolean, nullable=False, default=False)  # 是否允许用户注册

    # 登录安全配置
    max_login_attempts = Column(Integer, nullable=False, default=5)  # 单个邮箱的最大登录失败次数
    max_login_attempts_per_ip = Column(Integer, nullable=False, default=10)  # 单个IP的最大登录尝试次数
    login_lockout_duration = Column(Integer, nullable=False, default=900)  # 登录失败后锁定时间（秒）

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "allowRegistration": self.allow_registration,
            "maxLoginAttempts": self.max_login_attempts,
            "maxLoginAttemptsPerIp": self.max_login_attempts_per_ip,
            "loginLockoutDuration": self.login_lockout_duration,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }


class LoginAttempt(Base):
    """登录尝试记录表 - 用于防暴力破解"""
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    email = Column(String, nullable=True, index=True)  # 尝试登录的邮箱（可为空，用于IP限制）
    ip_address = Column(String, nullable=False, index=True)  # IP 地址
    success = Column(Boolean, default=False)  # 是否成功
    user_agent = Column(Text, nullable=True)  # 用户代理
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "ipAddress": self.ip_address,
            "success": self.success,
            "userAgent": self.user_agent,
            "createdAt": self.created_at.isoformat() if self.created_at else None
        }


class ADKSession(Base):
    """
    ADK 会话表 - 存储 ADK 会话元数据
    
    关联关系：
    - user_id: 用户 ID
    - agent_id: 关联的智能体 ID
    - session_id: ADK 会话 ID
    - metadata_json: 会话元数据（JSON）
    """
    __tablename__ = "adk_sessions"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    agent_id = Column(String, nullable=False, index=True)  # 智能体 ID
    session_id = Column(String, nullable=False, index=True)  # ADK 会话 ID
    metadata_json = Column(Text, nullable=True)  # 会话元数据（JSON）
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    last_used_at = Column(BigInteger, nullable=False)  # 最后使用时间（毫秒）

    def to_dict(self):
        """转换为字典格式"""
        import json
        result = {
            "id": self.id,
            "userId": self.user_id,
            "agentId": self.agent_id,
            "sessionId": self.session_id,
            "createdAt": self.created_at,
            "lastUsedAt": self.last_used_at
        }
        if self.metadata_json:
            try:
                result["metadata"] = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = None
        return result
