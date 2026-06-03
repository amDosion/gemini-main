"""AI 返回图片处理编排(从 ``attachment_service.py`` 拆出)。

``AttachmentService.process_ai_result`` 的内部编排逻辑迁出到这里,服务层只保留
薄包装 ``await process_ai_result(self, ...)``。行为必须与拆分前完全一致 —— 所有
``logger.info`` 步骤日志(可观测、已加固)逐字保留。

为保持既有 monkeypatch 契约,本模块不直接持有/调用任何被测试替换的协作者:
- ``self._persist_to_local_storage_if_enabled`` 仍在服务实例上,它内部引用
  ``attachment_service.StorageService``(被 patch 的模块级名)与实例级
  ``self._get_effective_storage_config``。
- ``self._submit_upload_task`` / ``self._build_generated_filename`` /
  ``self._resolve_provider_asset_metadata`` 也都从传入的 ``svc`` 取用,
  在调用点解析,确保实例级 monkeypatch 生效。
URL 判别函数从本模块级 import,与拆分前在 ``attachment_service`` 中的语义一致。
"""

import logging
import time
import uuid
from typing import Optional

from ...models.db_models import MessageAttachment
from ...utils.attachment_handler import is_base64_url, is_http_url
from .attachment_persistence import ProcessAIResultDict

logger = logging.getLogger(__name__)


async def process_ai_result(
    svc,
    *,
    ai_url: str,
    mime_type: str,
    session_id: str,
    message_id: str,
    user_id: str,
    prefix: str = 'generated',
    storage_id: Optional[str] = None,
    filename: Optional[str] = None,
    file_uri: Optional[str] = None,
    provider_file_name: Optional[str] = None,
    provider_file_uri: Optional[str] = None,
    gcs_uri: Optional[str] = None,
) -> ProcessAIResultDict:
    """处理 AI 返回的图片 URL(编排实现)。详见 ``AttachmentService.process_ai_result`` docstring。"""
    start_time = time.time()

    logger.info(f"[AttachmentService] ========== 开始处理AI返回的图片 ==========")
    logger.info(f"[AttachmentService] 📥 请求参数:")
    logger.info(f"[AttachmentService]     - prefix: {prefix}")
    logger.info(f"[AttachmentService]     - mime_type: {mime_type}")
    logger.info(f"[AttachmentService]     - session_id: {session_id if session_id else 'None'}")
    logger.info(f"[AttachmentService]     - message_id: {message_id if message_id else 'None'}")
    logger.info(f"[AttachmentService]     - user_id: {user_id}")
    logger.info(f"[AttachmentService]     - storage_id: {storage_id if storage_id else 'None'}")

    # ✅ 详细日志：步骤1 - 判断URL类型
    url_type = "Base64" if is_base64_url(ai_url) else "HTTP" if is_http_url(ai_url) else "未知"
    logger.info(f"[AttachmentService] 🔍 [步骤1] 判断URL类型: {url_type}")
    logger.info(f"[AttachmentService]     - ai_url长度: {len(ai_url)}")
    if url_type == "Base64":
        # 估算Base64图片大小
        try:
            base64_str = ai_url.split(',', 1)[1] if ',' in ai_url else ''
            estimated_size = len(base64_str) * 3 / 4 / 1024  # Base64解码后大小（KB）
            logger.info(f"[AttachmentService]     - 估算图片大小: {estimated_size:.2f} KB")
        except (IndexError, ValueError):
            # 仅用于日志的体积估算，解析失败可忽略（B4：收窄裸 except）
            pass

    attachment_id = str(uuid.uuid4())
    resolved_filename = filename or svc._build_generated_filename(prefix, mime_type)
    resolved_file_uri, resolved_google_file_uri = svc._resolve_provider_asset_metadata(
        ai_url=ai_url,
        file_uri=file_uri,
        provider_file_name=provider_file_name,
        provider_file_uri=provider_file_uri,
        gcs_uri=gcs_uri,
    )
    logger.info(f"[AttachmentService] 🔄 [步骤1] 生成附件ID: {attachment_id}")
    logger.info(f"[AttachmentService]     - filename: {resolved_filename}")

    # ✅ 步骤2 - 统一返回临时代理 URL，前端不直接接触 base64/第三方临时 URL
    logger.info(f"[AttachmentService] 🔄 [步骤2] 设置显示URL...")
    display_url = f"/api/temp-images/{attachment_id}"
    if is_base64_url(ai_url):
        logger.info(f"[AttachmentService]     - Base64 Data URL，改为代理URL: {display_url}")
    else:
        logger.info(f"[AttachmentService]     - HTTP URL，改为代理URL: {display_url}")
    logger.info(f"[AttachmentService] ✅ [步骤2] 显示URL已设置")

    # ✅ 详细日志：步骤3 - 创建附件记录
    logger.info(f"[AttachmentService] 🔄 [步骤3] 创建附件记录...")
    attachment = MessageAttachment(
        id=attachment_id,
        message_id=message_id,
        user_id=user_id,
        session_id=session_id,
        name=resolved_filename,
        mime_type=mime_type,
        temp_url=ai_url,  # 保存原始URL（可能是Base64）
        url='',           # 云URL（待Worker Pool上传完成后更新）
        upload_status='pending',
        file_uri=resolved_file_uri or None,
        google_file_uri=resolved_google_file_uri or None,
    )
    svc.db.add(attachment)
    svc.db.commit()
    step3_time = (time.time() - start_time) * 1000
    logger.info(f"[AttachmentService] ✅ [步骤3] 附件记录已创建并保存到数据库 (耗时: {step3_time:.2f}ms)")

    local_storage_url = await svc._persist_to_local_storage_if_enabled(
        attachment=attachment,
        user_id=user_id,
        filename=resolved_filename,
        mime_type=mime_type,
        storage_id=storage_id,
        source_ai_url=ai_url,
    )
    if local_storage_url:
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ✅ [步骤4] 本地存储已直写完成，跳过 Worker Pool")
        logger.info(f"[AttachmentService] ========== AI图片处理完成 (总耗时: {total_time:.2f}ms) ==========")
        logger.info(f"[AttachmentService]     - attachment_id: {attachment_id}")
        logger.info(f"[AttachmentService]     - display_url: {local_storage_url} (direct local storage)")
        return {
            'attachment_id': attachment_id,
            'display_url': local_storage_url,
            'cloud_url': local_storage_url,
            'status': 'completed',
            'task_id': None,
            'session_id': session_id,
            'message_id': message_id,
            'user_id': user_id,
            'filename': resolved_filename,
            'mime_type': mime_type,
            'file_uri': resolved_file_uri or '',
            'google_file_uri': resolved_google_file_uri or '',
        }

    # ✅ 详细日志：步骤4 - 提交Worker Pool任务
    logger.info(f"[AttachmentService] 🔄 [步骤4] 提交Worker Pool任务...")
    task_id = await svc._submit_upload_task(
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        source_ai_url=ai_url,  # ✅ 新增source类型（可以是Base64或HTTP）
        filename=resolved_filename,
        mime_type=mime_type,
        storage_id=storage_id,
    )
    attachment.upload_task_id = task_id
    svc.db.commit()
    step4_time = (time.time() - start_time) * 1000
    logger.info(f"[AttachmentService] ✅ [步骤4] 上传任务已创建: {task_id} (耗时: {step4_time:.2f}ms)")

    total_time = (time.time() - start_time) * 1000
    logger.info(f"[AttachmentService] ========== AI图片处理完成 (总耗时: {total_time:.2f}ms) ==========")
    logger.info(f"[AttachmentService]     - attachment_id: {attachment_id}")
    logger.info(f"[AttachmentService]     - display_url: {display_url}")
    logger.info(f"[AttachmentService]     - task_id: {task_id}")

    return {
        'attachment_id': attachment_id,
        'display_url': display_url,  # ✅ 统一临时代理URL（/api/temp-images/{attachment_id}）
        'cloud_url': '',             # ✅ 云URL（空，待上传完成）
        'status': 'pending',
        'task_id': task_id,
        # ✅ 新增：返回完整的元数据，供前端保存和后续 CONTINUITY LOGIC 使用
        'session_id': session_id,
        'message_id': message_id,
        'user_id': user_id,
        'filename': resolved_filename,
        'mime_type': mime_type,
        'file_uri': resolved_file_uri or '',
        'google_file_uri': resolved_google_file_uri or '',
    }
