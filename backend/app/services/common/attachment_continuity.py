"""CONTINUITY LOGIC 附件解析编排(从 ``attachment_service.py`` 拆出)。

``AttachmentService.resolve_continuity_attachment`` 的内部编排逻辑迁出到这里,
服务层只保留薄包装 ``await resolve_continuity_attachment(self, ...)``。行为必须与
拆分前完全一致 —— 所有 ``logger`` 步骤日志(可观测、已加固)逐字保留。

协作者(``svc._find_attachment_by_url`` / ``svc._find_latest_uploaded_image`` /
``svc._is_persistent_storage_url`` / ``svc._submit_upload_task`` / ``svc.db``)
均在调用点从传入的 ``svc`` 取用,保证实例级 monkeypatch 生效;URL 判别函数从本
模块级 import,与拆分前在 ``attachment_service`` 中的语义一致。
"""

import logging
import time
from typing import Any, Dict, List, Optional

from ...models.db_models import MessageAttachment
from ...utils.attachment_handler import is_base64_url, is_blob_url, is_http_url

logger = logging.getLogger(__name__)


async def resolve_continuity_attachment(
    svc,
    *,
    active_image_url: str,
    session_id: str,
    user_id: str,
    messages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """解析 CONTINUITY LOGIC 的附件(编排实现)。详见 ``AttachmentService.resolve_continuity_attachment`` docstring。"""
    start_time = time.time()

    # ✅ 详细日志：步骤1 - 查找匹配的附件ID
    logger.info(f"[AttachmentService] 🔍 [步骤1] 开始查找匹配的附件ID...")
    logger.info(f"[AttachmentService]     - active_image_url类型: {'Blob' if is_blob_url(active_image_url) else 'Base64' if is_base64_url(active_image_url) else 'HTTP' if is_http_url(active_image_url) else '未知'}")
    logger.info(f"[AttachmentService]     - active_image_url长度: {len(active_image_url)}")
    logger.info(f"[AttachmentService]     - messages数量: {len(messages)}")

    attachment_id = svc._find_attachment_by_url(active_image_url, messages)

    if attachment_id:
        logger.info(f"[AttachmentService] ✅ [步骤1] 在messages中找到附件ID: {attachment_id}")
    else:
        logger.info(f"[AttachmentService] ⚠️ [步骤1] 在messages中未找到匹配的附件ID")

    if not attachment_id:
        # 策略: Blob URL兜底 - 查找最近的已上传图片
        if is_blob_url(active_image_url):
            logger.info(f"[AttachmentService] 🔄 [步骤1-兜底] Blob URL，尝试查找最近的已上传图片...")
            attachment_id = svc._find_latest_uploaded_image(session_id, user_id)
            if attachment_id:
                logger.info(f"[AttachmentService] ✅ [步骤1-兜底] 找到最近的已上传图片: {attachment_id}")
            else:
                logger.warning(f"[AttachmentService] ❌ [步骤1-兜底] 未找到最近的已上传图片")

    if not attachment_id:
        elapsed_time = (time.time() - start_time) * 1000
        logger.warning(f"[AttachmentService] ❌ 未找到匹配的附件 (耗时: {elapsed_time:.2f}ms)")
        return None

    # ✅ 详细日志：步骤2 - 查询数据库
    logger.info(f"[AttachmentService] 🔍 [步骤2] 查询数据库获取附件详情...")
    logger.info(f"[AttachmentService]     - attachment_id: {attachment_id}")
    logger.info(f"[AttachmentService]     - user_id: {user_id}")

    attachment = svc.db.query(MessageAttachment).filter_by(
        id=attachment_id,
        user_id=user_id
    ).first()

    if not attachment:
        elapsed_time = (time.time() - start_time) * 1000
        logger.warning(f"[AttachmentService] ❌ [步骤2] 数据库中未找到附件记录 (耗时: {elapsed_time:.2f}ms)")
        return None

    logger.info(f"[AttachmentService] ✅ [步骤2] 找到附件记录:")
    logger.info(f"[AttachmentService]     - upload_status: {attachment.upload_status}")
    # 对于BASE64 URL，只输出类型和长度，不输出内容
    if is_base64_url(attachment.url):
        logger.info(f"[AttachmentService]     - url: Base64 Data URL (长度: {len(attachment.url)} 字符)")
    else:
        logger.info(f"[AttachmentService]     - url: {attachment.url[:80] + '...' if attachment.url and len(attachment.url) > 80 else attachment.url or 'None'}")
    logger.info(f"[AttachmentService]     - temp_url: {'存在' if attachment.temp_url else 'None'}")
    if is_base64_url(attachment.temp_url):
        logger.info(f"[AttachmentService]     - temp_url类型: Base64 (长度: {len(attachment.temp_url)} 字符)")
    else:
        logger.info(f"[AttachmentService]     - temp_url类型: {'HTTP' if is_http_url(attachment.temp_url) else 'None' if not attachment.temp_url else '其他'}")

    # ✅ 详细日志：步骤3 - 检查上传状态
    logger.info(f"[AttachmentService] 🔍 [步骤3] 检查上传状态...")

    # ✅ 关键修复：如果附件已经上传完成且有 HTTP URL，直接返回，不创建新任务
    if attachment.upload_status == 'completed' and svc._is_persistent_storage_url(attachment.url):
        # 已上传到云存储 → 直接返回云URL，不创建新任务
        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ✅ [步骤3] 附件已上传完成，直接复用 (耗时: {elapsed_time:.2f}ms)")
        logger.info(f"[AttachmentService]     - 跳过上传任务创建")
        # 对于BASE64 URL，只输出类型和长度，不输出内容
        if is_base64_url(attachment.url):
            logger.info(f"[AttachmentService]     - 返回云URL: Base64 Data URL (长度: {len(attachment.url)} 字符)")
        else:
            logger.info(f"[AttachmentService]     - 返回云URL: {attachment.url[:80] + '...' if len(attachment.url) > 80 else attachment.url}")
        return {
            'attachment_id': attachment_id,
            'url': attachment.url,
            'status': 'completed',
            'task_id': None,
            # ✅ 新增：返回完整的附件元数据
            'message_id': attachment.message_id,
            'session_id': attachment.session_id,
            'user_id': attachment.user_id,
            'filename': attachment.name,
            'mime_type': attachment.mime_type,
            'size': attachment.size,
            'cloud_url': attachment.url,  # 已上传完成，url 就是 cloud_url
            'created_at': None  # MessageAttachment 模型没有 created_at 字段
        }

    # ✅ 如果附件有 HTTP URL 但状态不是 completed，可能是数据不一致，也直接返回
    if svc._is_persistent_storage_url(attachment.url) and attachment.upload_status != 'completed':
        logger.warning(f"[AttachmentService] ⚠️ [步骤3] 附件有 HTTP URL 但状态不是 completed，更新状态并直接返回")
        logger.warning(f"[AttachmentService]     - 原状态: {attachment.upload_status}")
        logger.warning(f"[AttachmentService]     - 更新为: completed")
        attachment.upload_status = 'completed'
        svc.db.commit()
        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ✅ [步骤3] 状态已更新，直接返回 (耗时: {elapsed_time:.2f}ms)")
        return {
            'attachment_id': attachment_id,
            'url': attachment.url,
            'status': 'completed',
            'task_id': None,
            # ✅ 新增：返回完整的附件元数据
            'message_id': attachment.message_id,
            'session_id': attachment.session_id,
            'user_id': attachment.user_id,
            'filename': attachment.name,
            'mime_type': attachment.mime_type,
            'size': attachment.size,
            'cloud_url': attachment.url,  # 已上传完成，url 就是 cloud_url
            'created_at': None  # MessageAttachment 模型没有 created_at 字段
        }

    # ✅ 详细日志：步骤4 - 未上传，准备创建上传任务
    logger.info(f"[AttachmentService] 🔄 [步骤4] 附件未上传完成，准备创建上传任务...")

    # ✅ 修复：如果附件有 temp_url（Base64或HTTP URL），使用 source_ai_url
    # 如果附件有 url（但未上传），使用 source_url
    # 只有在附件已上传的情况下才使用 source_attachment_id 复用
    # ✅ 关键修复：如果附件没有任何 URL，使用请求中的 active_image_url
    source_ai_url = None
    source_url = None

    if attachment.temp_url:
        # 有 temp_url（Base64或HTTP URL），使用 source_ai_url
        source_ai_url = attachment.temp_url
        logger.info(f"[AttachmentService]     - 使用 temp_url 作为 source_ai_url")
        logger.info(f"[AttachmentService]     - temp_url类型: {'Base64' if is_base64_url(attachment.temp_url) else 'HTTP'}")
    elif attachment.url and not is_http_url(attachment.url):
        # 有 url 但不是 HTTP URL（可能是Base64），使用 source_ai_url
        source_ai_url = attachment.url
        logger.info(f"[AttachmentService]     - 使用 url (非HTTP) 作为 source_ai_url")
    elif attachment.url and is_http_url(attachment.url):
        # 有 HTTP URL，使用 source_url
        source_url = attachment.url
        logger.info(f"[AttachmentService]     - 使用 url (HTTP) 作为 source_url")
    elif active_image_url:
        # ✅ 关键修复：附件没有任何 URL，使用请求中的 active_image_url
        logger.info(f"[AttachmentService]     - 附件没有 URL，使用请求中的 active_image_url")
        if is_base64_url(active_image_url) or is_blob_url(active_image_url):
            source_ai_url = active_image_url
            logger.info(f"[AttachmentService]     - active_image_url类型: {'Base64' if is_base64_url(active_image_url) else 'Blob'}")
        elif is_http_url(active_image_url):
            source_url = active_image_url
            logger.info(f"[AttachmentService]     - active_image_url类型: HTTP")
        else:
            logger.warning(f"[AttachmentService]     - ⚠️ active_image_url类型未知: {active_image_url[:50]}...")
    else:
        logger.warning(f"[AttachmentService]     - ⚠️ 没有可用的源URL或文件路径")

    logger.info(f"[AttachmentService] 🔄 [步骤4] 调用 _submit_upload_task() 创建上传任务...")
    task_id = await svc._submit_upload_task(
        user_id=user_id,
        session_id=session_id,
        message_id=attachment.message_id,
        attachment_id=attachment_id,
        source_ai_url=source_ai_url,  # ✅ 使用 temp_url 或 url（Base64/HTTP）
        source_url=source_url,  # ✅ 使用 HTTP URL（如果有）
        filename=attachment.name or 'continuity-image.png',
        mime_type=attachment.mime_type or 'image/png'
    )

    elapsed_time = (time.time() - start_time) * 1000
    logger.info(f"[AttachmentService] ✅ [步骤4] 上传任务已创建: {task_id} (耗时: {elapsed_time:.2f}ms)")

    # ✅ 关键修复：当数据库中没有保存 URL 时，使用前端传入的 active_image_url
    # 这样 Base64 URL 可以正确传递给 AI 服务处理
    final_url = attachment.temp_url or attachment.url or active_image_url or ''

    # 日志记录最终使用的 URL 来源
    if attachment.temp_url:
        url_source = 'temp_url'
    elif attachment.url:
        url_source = 'url'
    elif active_image_url:
        url_source = 'active_image_url (前端传入)'
    else:
        url_source = '无可用 URL'
    logger.info(f"[AttachmentService]     - 返回 URL 来源: {url_source}")

    return {
        'attachment_id': attachment_id,
        'url': final_url,
        'status': 'pending',
        'task_id': task_id,
        # ✅ 新增：返回完整的附件元数据
        'message_id': attachment.message_id,
        'session_id': attachment.session_id,
        'user_id': attachment.user_id,
        'filename': attachment.name,
        'mime_type': attachment.mime_type,
        'size': attachment.size,
        'cloud_url': None,  # 尚未上传完成
        'created_at': None  # MessageAttachment 模型没有 created_at 字段
    }
