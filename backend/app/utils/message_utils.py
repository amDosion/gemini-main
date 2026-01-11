"""
v3 消息存储工具函数

提供消息模式映射、表类获取、元数据提取等核心功能
"""
import json
from typing import Dict, Any, Optional, Type

from ..models.db_models import (
    MessagesChat,
    MessagesImageGen,
    MessagesVideoGen,
    MessagesGeneric,
    MessageAttachment,
    MessageIndex
)


# 模式到表名的映射
MODE_TABLE_MAP: Dict[str, str] = {
    'chat': 'messages_chat',
    'image-gen': 'messages_image_gen',
    'video-gen': 'messages_video_gen',
    # 其他模式使用兜底表
}

# 表名到模型类的映射
TABLE_CLASS_MAP: Dict[str, Type] = {
    'messages_chat': MessagesChat,
    'messages_image_gen': MessagesImageGen,
    'messages_video_gen': MessagesVideoGen,
    'messages_generic': MessagesGeneric,
}


def get_table_name_for_mode(mode: str) -> str:
    """
    根据消息模式获取对应的表名
    
    Args:
        mode: 消息模式（chat/image-gen/video-gen/...）
    
    Returns:
        表名（messages_chat/messages_image_gen/messages_video_gen/messages_generic）
    
    示例:
        >>> get_table_name_for_mode('chat')
        'messages_chat'
        >>> get_table_name_for_mode('image-gen')
        'messages_image_gen'
        >>> get_table_name_for_mode('pdf-extract')
        'messages_generic'
    """
    return MODE_TABLE_MAP.get(mode, 'messages_generic')


def get_message_table_class_by_name(table_name: str) -> Type:
    """
    根据表名获取对应的 SQLAlchemy 模型类
    
    Args:
        table_name: 表名
    
    Returns:
        SQLAlchemy 模型类
    
    Raises:
        ValueError: 未知的表名
    
    示例:
        >>> get_message_table_class_by_name('messages_chat')
        <class 'MessagesChat'>
    """
    if table_name not in TABLE_CLASS_MAP:
        raise ValueError(f"未知的表名: {table_name}")
    return TABLE_CLASS_MAP[table_name]


def extract_metadata(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    从前端消息对象提取复杂元数据
    
    提取的字段包括：
    - groundingMetadata: 搜索增强元数据
    - urlContextMetadata: URL 上下文元数据
    - toolCalls: 工具调用信息
    - toolResults: 工具调用结果
    - thinkingContent: 思考内容
    - 其他扩展字段
    
    Args:
        msg: 前端消息对象
    
    Returns:
        包含元数据的字典（可直接 json.dumps）
    
    示例:
        >>> msg = {'id': '123', 'content': 'hello', 'groundingMetadata': {...}}
        >>> extract_metadata(msg)
        {'groundingMetadata': {...}}
    """
    # 需要提取的元数据字段列表
    metadata_fields = [
        'groundingMetadata',
        'urlContextMetadata',
        'toolCalls',
        'toolResults',
        'thinkingContent',
        'searchResults',
        'citations',
        'safetyRatings',
        'finishReason',
        # 图像生成相关（可能在 metadata 中）
        'generatedImages',
        'imagePrompt',
        # 视频生成相关
        'generatedVideos',
        'videoPrompt',
        # 其他扩展字段
        'customData',
    ]
    
    metadata = {}
    for field in metadata_fields:
        if field in msg and msg[field] is not None:
            metadata[field] = msg[field]
    
    return metadata


def extract_image_gen_fields(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    从消息中提取图像生成特定字段
    
    Args:
        msg: 前端消息对象
    
    Returns:
        图像生成特定字段字典
    """
    return {
        'image_size': msg.get('imageSize'),
        'image_style': msg.get('imageStyle'),
        'image_quality': msg.get('imageQuality'),
        'image_count': msg.get('imageCount', 1),
        'model_name': msg.get('modelName'),
    }


def extract_video_gen_fields(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    从消息中提取视频生成特定字段
    
    Args:
        msg: 前端消息对象
    
    Returns:
        视频生成特定字段字典
    """
    return {
        'video_duration': msg.get('videoDuration'),
        'video_resolution': msg.get('videoResolution'),
        'video_fps': msg.get('videoFps'),
        'model_name': msg.get('modelName'),
    }


def build_message_for_table(
    msg: Dict[str, Any],
    session_id: str,
    table_name: str
) -> Dict[str, Any]:
    """
    构建用于插入模式表的消息数据
    
    Args:
        msg: 前端消息对象
        session_id: 会话 ID
        table_name: 目标表名
    
    Returns:
        适合插入对应表的数据字典
    """
    # 基础字段（所有表共有）
    base_data = {
        'id': msg['id'],
        'session_id': session_id,
        'role': msg['role'],
        'content': msg['content'],
        'timestamp': msg['timestamp'],
        'is_error': msg.get('isError', False),
        'metadata_json': json.dumps(extract_metadata(msg)) if extract_metadata(msg) else None,
    }
    
    # 根据表名添加特定字段
    if table_name == 'messages_image_gen':
        base_data.update(extract_image_gen_fields(msg))
    elif table_name == 'messages_video_gen':
        base_data.update(extract_video_gen_fields(msg))
    
    return base_data
