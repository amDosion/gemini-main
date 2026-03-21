"""
消息组装工具 - 统一的 v3 架构消息组装逻辑

避免在多个地方重复实现相同的逻辑。
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def assemble_messages_v3(
    session_id: str,
    indexes: List,  # List[MessageIndex]
    messages_by_table: Dict[str, Dict[str, Any]],
    attachments_by_message: Dict[str, List]  # Dict[str, List[MessageAttachment]]
) -> List[Dict[str, Any]]:
    """
    组装单个会话的消息列表 (v3 架构)

    统一的消息组装逻辑，被以下模块使用：
    - routers/user/sessions.py: GET /sessions/{session_id}/messages
    - services/common/init_service.py: 初始化时加载历史消息

    Args:
        session_id: 会话 ID
        indexes: 该会话的消息索引列表（已按 seq 排序）
        messages_by_table: {table_name: {msg_id: msg_obj}} 消息字典
        attachments_by_message: {message_id: [attachment_obj]} 附件字典

    Returns:
        组装后的消息列表，每条消息包含：
        - 消息基础字段（从模式表）
        - mode 字段（从索引表）
        - attachments 列表（从附件表）
    """
    assembled_messages = []

    for idx in indexes:
        # 从模式表获取消息
        table_messages = messages_by_table.get(idx.table_name, {})
        msg = table_messages.get(idx.id)

        if not msg:
            # 数据不一致：索引存在但消息不存在，跳过
            logger.warning(
                f"[MessageAssembly] 消息不存在: session_id={session_id}, "
                f"message_id={idx.id}, table={idx.table_name}"
            )
            continue

        # 转换为字典
        msg_dict = msg.to_dict()

        # ✅ 关键：从索引表获取 mode 字段并赋值
        # 索引表是权威来源，模式表中可能没有 mode 字段
        msg_dict['mode'] = idx.mode

        # 附加附件
        atts = attachments_by_message.get(idx.id, [])
        if atts:
            msg_dict['attachments'] = [att.to_dict() for att in atts]
        else:
            msg_dict['attachments'] = []

        assembled_messages.append(msg_dict)

    logger.debug(
        f"[MessageAssembly] 组装完成: session_id={session_id}, "
        f"消息数={len(assembled_messages)}"
    )

    return assembled_messages
