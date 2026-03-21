from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, Float, func, UniqueConstraint
from ..core.database import Base
from datetime import datetime
import uuid

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

    # 使用基类 to_dict()，None 字段替换为默认值
    _field_defaults = {
        'base_url': '',
        'hidden_models': [],
        'cached_model_count': 0,
        'saved_models': [],
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
    # 使用基类的统一 to_dict() 方法


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

    # 使用基类的统一 to_dict() 方法


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类 to_dict()：排除 user_id/session_id，metadata_json 合并到顶层
    _exclude_fields = {'user_id', 'session_id'}
    _json_merge_fields = {'metadata_json'}


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

    # 使用基类的统一 to_dict() 方法


class MessageHistoryState(Base):
    """
    历史消息状态表 - 存储历史列表 UI 状态（收藏）

    说明：
    - 使用 (user_id, message_id) 复合主键，保证用户维度隔离。
    - is_favorite=true 表示该消息在历史列表中被收藏。
    - 删除消息时会在 sessions 路由中同步清理对应状态记录。
    """
    __tablename__ = "message_history_states"

    user_id = Column(String, primary_key=True)  # 用户ID（复合主键）
    message_id = Column(String(36), primary_key=True)  # Message.id（复合主键）
    session_id = Column(String(36), nullable=False, index=True)  # 所属会话ID
    is_favorite = Column(Boolean, nullable=False, default=False)  # 是否收藏
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（ms）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（ms）

    # 使用基类的统一 to_dict() 方法


class SessionHistoryPreference(Base):
    """
    会话历史偏好表 - 存储历史列表 UI 偏好（如“仅收藏”开关）

    说明：
    - 复合主键 (user_id, session_id)，按用户+会话维度隔离。
    - show_favorites_only=true 表示历史面板默认仅显示收藏项。
    """
    __tablename__ = "session_history_preferences"

    user_id = Column(String, primary_key=True)  # 用户ID（复合主键）
    session_id = Column(String(36), primary_key=True)  # 会话ID（复合主键）
    show_favorites_only = Column(Boolean, nullable=False, default=False)  # 是否仅收藏
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（ms）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（ms）

    # 使用基类的统一 to_dict() 方法


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

    # 使用基类 to_dict()：auto-parse config_json → config


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

    # 使用基类 to_dict()：排除时间戳，None 替换为空字符串
    _exclude_fields = {'created_at', 'updated_at'}
    _field_defaults = {'description': '', 'category': ''}


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

    # 使用基类的统一 to_dict() 方法


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

    # 使用基类的统一 to_dict() 方法


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
    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    status_reason = Column(Text, nullable=True)
    access_token = Column(Text, nullable=True)  # ✅ 存储 access_token（不使用 cookie）
    token_expires_at = Column(DateTime(timezone=True), nullable=True)  # token 过期时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 使用基类 to_dict()：排除敏感字段，DateTime → isoformat
    _exclude_fields = {'password_hash', 'access_token', 'token_expires_at', 'status_reason'}
    _datetime_format = 'isoformat'


class RefreshToken(Base):
    """刷新令牌表 - 存储用户的刷新令牌"""
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)  # 关联 users.id
    token_hash = Column(Text, nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # 使用基类 to_dict()：排除敏感字段，DateTime → isoformat
    _exclude_fields = {'token_hash'}
    _datetime_format = 'isoformat'


class IPLoginHistory(Base):
    """IP 登录历史表 - 记录用户登录的 IP 地址"""
    __tablename__ = "ip_login_history"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)  # 关联 users.id
    ip_address = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # login, logout, failed_login, token_refresh
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 使用基类 to_dict()：DateTime → isoformat
    _datetime_format = 'isoformat'


class IPBlocklist(Base):
    """IP 黑名单表 - 存储被封禁的 IP 地址"""
    __tablename__ = "ip_blocklist"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    ip_address = Column(String, unique=True, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    blocked_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)  # 管理员用户 ID

    # 使用基类 to_dict()：DateTime → isoformat
    _datetime_format = 'isoformat'


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
            "user_id": self.user_id,
            "api_mode": self.api_mode,
            "vertex_ai_project_id": self.vertex_ai_project_id,
            "vertex_ai_location": self.vertex_ai_location or 'us-central1',
            "vertex_ai_credentials_json": self.vertex_ai_credentials_json,
            "hidden_models": self.hidden_models or [],
            "saved_models": self.saved_models or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
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

    # 使用基类 to_dict()：auto-parse config_json → config


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

    # 使用基类 to_dict()：auto-parse metadata_json → metadata


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

    # 使用基类 to_dict()：auto-parse metadata_json → metadata


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

    # 使用基类 to_dict()：auto-parse config_json → config


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

    # 使用基类 to_dict()：auto-parse metadata_json → metadata


class AgentRegistry(Base):
    """
    智能体注册表 - 存储智能体注册信息（Phase 1 扩展）
    
    扩展字段：provider_id, model_id, system_prompt, temperature, max_tokens, description, icon, color
    """
    __tablename__ = "agent_registry"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)  # Agent 描述
    agent_type = Column(String, nullable=False, default='custom')  # adk/interactions/custom
    agent_card_json = Column(Text, nullable=True)
    endpoint_url = Column(String, nullable=True)
    # Phase 1 新增：LLM 配置
    provider_id = Column(String, nullable=True)  # google / openai / tongyi / ollama
    model_id = Column(String, nullable=True)  # gemini-2.0-flash / gpt-4o / ...
    system_prompt = Column(Text, nullable=True)  # System Prompt
    temperature = Column(Float, nullable=True, default=0.7)  # 温度
    max_tokens = Column(Integer, nullable=True, default=4096)  # 最大输出 Token
    icon = Column(String, nullable=True, default='🤖')  # 图标
    color = Column(String, nullable=True, default='#14b8a6')  # 颜色
    status = Column(String, nullable=False, default='active')
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    # 使用基类 to_dict()：auto-parse agent_card_json → agent_card，None 替换为默认值
    _field_defaults = {
        'description': '',
        'system_prompt': '',
        'icon': '🤖',
        'color': '#14b8a6',
    }

    def build_runtime_metadata(self):
        agent_type = str(self.agent_type or '').strip().lower()
        provider_id = str(self.provider_id or '').strip().lower()

        supports_google_adk_runtime = (
            agent_type in {'adk', 'google-adk'}
            and provider_id.startswith('google')
        )

        if supports_google_adk_runtime:
            return {
                'kind': 'google-adk',
                'label': 'Google ADK',
                'supports_run': True,
                'supports_live_run': True,
                'supports_sessions': True,
                'supports_memory': True,
                'supports_official_orchestration': True,
            }

        return {
            'kind': '',
            'label': '',
            'supports_run': False,
            'supports_live_run': False,
            'supports_sessions': False,
            'supports_memory': False,
            'supports_official_orchestration': False,
        }

    def build_source_metadata(self):
        agent_type = str(self.agent_type or '').strip().lower()
        provider_id = str(self.provider_id or '').strip().lower()

        if agent_type == "seed":
            return {
                "kind": "seed",
                "label": "官方 Seed",
                "is_system": True,
            }

        if agent_type in {"adk", "google-adk"} and provider_id.startswith("google"):
            return {
                "kind": "google-runtime",
                "label": "Google runtime",
                "is_system": False,
            }

        if agent_type == "interactions":
            return {
                "kind": "vertex-interactions",
                "label": "Vertex Interactions",
                "is_system": False,
            }

        return {
            "kind": "user",
            "label": "用户创建",
            "is_system": False,
        }

    def to_dict(self):
        payload = super().to_dict()
        runtime = self.build_runtime_metadata()
        source = self.build_source_metadata()
        payload['runtime'] = runtime
        payload['source'] = source
        payload['supports_runtime_sessions'] = bool(runtime.get('supports_sessions'))
        payload['supports_runtime_live_run'] = bool(runtime.get('supports_live_run'))
        payload['supports_runtime_memory'] = bool(runtime.get('supports_memory'))
        payload['supports_official_orchestration'] = bool(
            runtime.get('supports_official_orchestration')
        )
        return payload


class WorkflowExecution(Base):
    """工作流执行记录表"""
    __tablename__ = "workflow_executions"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)
    workflow_json = Column(Text, nullable=False)  # 工作流快照 (nodes + edges JSON)
    idempotency_key = Column(String(128), nullable=True, index=True)  # 跨实例幂等键
    status = Column(String, nullable=False, default='pending')  # pending/running/completed/failed/cancelled
    input_json = Column(Text, nullable=True)  # 用户输入
    result_json = Column(Text, nullable=True)  # 最终结果
    error = Column(Text, nullable=True)
    started_at = Column(BigInteger, nullable=False)
    completed_at = Column(BigInteger, nullable=True)

    # 使用基类 to_dict()：auto-parse workflow_json/input_json/result_json


class NodeExecution(Base):
    """节点执行记录表"""
    __tablename__ = "node_executions"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    execution_id = Column(String, nullable=False, index=True)  # 关联 WorkflowExecution
    node_id = Column(String, nullable=False)  # 工作流中的节点 ID
    node_type = Column(String, nullable=False)  # agent / start / end / ...
    status = Column(String, nullable=False, default='pending')  # pending/running/completed/failed/skipped
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(BigInteger, nullable=True)
    completed_at = Column(BigInteger, nullable=True)

    # 使用基类 to_dict()：auto-parse input_json/output_json


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

    # 使用基类 to_dict()：auto-parse card_json → card


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

    # 使用基类 to_dict()：auto-parse config_json → config


class WorkflowTemplateCategory(Base):
    """工作流模板分类表 - 存储用户可复用的模板分类"""
    __tablename__ = "workflow_template_categories"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))  # UUID字符串
    user_id = Column(String, nullable=False, index=True)  # 用户ID
    name = Column(String, nullable=False, index=True)  # 分类名称
    created_at = Column(BigInteger, nullable=False)  # 创建时间戳（毫秒）
    updated_at = Column(BigInteger, nullable=False)  # 更新时间戳（毫秒）

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_workflow_template_category_user_name'),
    )


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

    # 使用基类 to_dict()：auto-parse metadata_json → metadata


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

    # 使用基类 to_dict()：auto-parse event_data_json → event_data


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

    # 日志配置
    enable_logging = Column(Boolean, nullable=False, default=True)  # 是否启用日志显示（True=显示，False=不显示）

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 使用基类 to_dict()：DateTime → isoformat
    _datetime_format = 'isoformat'


class UserMcpConfig(Base):
    """用户 MCP 配置表 - 存储用户自定义 MCP JSON 配置"""
    __tablename__ = "user_mcp_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, unique=True, index=True)  # 关联 users.id，每个用户一条
    config_json = Column(Text, nullable=False, default="{}")  # MCP JSON 配置
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 使用基类 to_dict()：DateTime → isoformat，config_json 自动映射为 config
    _datetime_format = 'isoformat'


class LoginAttempt(Base):
    """登录尝试记录表 - 用于防暴力破解"""
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    email = Column(String, nullable=True, index=True)  # 尝试登录的邮箱（可为空，用于IP限制）
    ip_address = Column(String, nullable=False, index=True)  # IP 地址
    success = Column(Boolean, default=False)  # 是否成功
    user_agent = Column(Text, nullable=True)  # 用户代理
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # 使用基类 to_dict()：DateTime → isoformat
    _datetime_format = 'isoformat'


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

    # 使用基类 to_dict()：auto-parse metadata_json → metadata
