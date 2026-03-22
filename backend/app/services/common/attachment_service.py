"""
统一附件处理服务

职责:
1. 处理所有来源的附件（用户上传、AI返回、CONTINUITY LOGIC）
2. 统一云URL管理
3. 调度Worker Pool异步上传
4. 管理附件生命周期
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
import base64
import os
import mimetypes
import uuid
import logging
import httpx

from ...core.encryption import decrypt_config
from ...models.db_models import MessageAttachment, UploadTask, StorageConfig, ActiveStorage
from .redis_queue_service import redis_queue
from .upload_worker_pool import worker_pool
from ..storage.storage_service import StorageService
from ...utils.url_security import (
    get_with_redirect_guard,
    validate_outbound_http_url,
)

logger = logging.getLogger(__name__)

class AttachmentService:
    """
    统一附件处理服务

    职责:
    1. 处理所有来源的附件（用户上传、AI返回、CONTINUITY LOGIC）
    2. 统一云URL管理
    3. 调度Worker Pool异步上传
    4. 管理附件生命周期
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== 公共接口 ====================

    async def process_user_upload(
        self,
        file_path: str,
        filename: str,
        mime_type: str,
        session_id: str,
        message_id: str,
        user_id: str,
        storage_id: Optional[str] = None,
        priority: str = 'normal'
    ) -> Dict[str, Any]:
        """
        处理用户上传的文件

        流程:
        1. 创建附件记录
        2. 提交Worker Pool任务（source_file_path）
        3. 返回临时附件信息

        参数:
            file_path: 临时文件路径（相对路径）
            filename: 文件名
            mime_type: MIME类型
            session_id: 会话ID
            message_id: 消息ID
            user_id: 用户ID

        返回:
            {
                'attachment_id': str,
                'status': 'pending',
                'task_id': str
            }
        """
        import time
        start_time = time.time()
        
        logger.info(f"[AttachmentService] ========== 开始处理用户上传 ==========")
        logger.info(f"[AttachmentService] 📥 请求参数:")
        logger.info(f"[AttachmentService]     - filename: {filename}")
        logger.info(f"[AttachmentService]     - mime_type: {mime_type}")
        logger.info(f"[AttachmentService]     - file_path: {file_path}")
        logger.info(f"[AttachmentService]     - session_id: {session_id if session_id else 'None'}")
        logger.info(f"[AttachmentService]     - message_id: {message_id if message_id else 'None'}")
        logger.info(f"[AttachmentService]     - user_id: {user_id}")
        logger.info(f"[AttachmentService]     - storage_id: {storage_id if storage_id else 'None'}")
        logger.info(f"[AttachmentService]     - priority: {priority}")
        
        attachment_id = str(uuid.uuid4())
        logger.info(f"[AttachmentService] 🔄 [步骤1] 生成附件ID: {attachment_id}")

        # ✅ 详细日志：步骤1 - 创建附件记录
        logger.info(f"[AttachmentService] 🔄 [步骤1] 创建附件记录...")
        attachment = MessageAttachment(
            id=attachment_id,
            message_id=message_id,
            user_id=user_id,
            session_id=session_id,
            name=filename,
            mime_type=mime_type,
            url='',  # 待上传
            upload_status='pending'
        )
        self.db.add(attachment)
        self.db.commit()
        logger.info(f"[AttachmentService] ✅ [步骤1] 附件记录已创建并保存到数据库")

        local_storage_url = await self._persist_to_local_storage_if_enabled(
            attachment=attachment,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            storage_id=storage_id,
            source_file_path=file_path,
        )
        if local_storage_url:
            logger.info(f"[AttachmentService] ✅ [步骤2] 本地存储已直写完成，跳过 Worker Pool")
            logger.info(f"[AttachmentService] ========== 用户上传处理完成 ==========")
            return {
                'attachment_id': attachment_id,
                'status': 'completed',
                'task_id': None
            }

        # ✅ 详细日志：步骤2 - 提交Worker Pool任务
        logger.info(f"[AttachmentService] 🔄 [步骤2] 提交Worker Pool任务...")
        task_id = await self._submit_upload_task(
            session_id=session_id,
            message_id=message_id,
            attachment_id=attachment_id,
            source_file_path=file_path,
            filename=filename,
            mime_type=mime_type,
            priority=priority,
            storage_id=storage_id
        )
        attachment.upload_task_id = task_id
        self.db.commit()
        
        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ✅ [步骤2] 上传任务已创建: {task_id} (耗时: {elapsed_time:.2f}ms)")
        logger.info(f"[AttachmentService] ========== 用户上传处理完成 ==========")

        return {
            'attachment_id': attachment_id,
            'status': 'pending',
            'task_id': task_id
        }

    async def process_ai_result(
        self,
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
    ) -> Dict[str, Any]:
        """
        处理AI返回的图片URL

        流程:
        1. 判断URL类型（Base64 Data URL 或 HTTP URL）
        2. 创建附件记录
        3. 统一返回后端临时代理 URL（/api/temp-images/{attachment_id}）
        4. 提交Worker Pool任务（source_ai_url）
        5. Worker Pool 上传完成后更新云URL，临时代理自动重定向云URL

        **关键优化**:
        - 前端始终只拿 HTTP URL（不透传 Base64）
        - AI 原图统一进入 Worker Pool 上传链路
        - 上传完成后自动切换到云存储 URL

        参数:
            ai_url: AI返回的URL（Base64或HTTP）
            mime_type: MIME类型
            session_id: 会话ID
            message_id: 消息ID
            user_id: 用户ID
            prefix: 文件名前缀
            storage_id: 指定存储配置ID（可选）

        返回:
            {
                'attachment_id': str,
                'display_url': str,      # 显示URL（HTTP临时代理URL，绝不是Base64）
                'cloud_url': str,        # 云URL（空，待上传完成）
                'status': 'pending',
                'task_id': str
            }
        """
        import time
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
        url_type = "Base64" if ai_url.startswith('data:') else "HTTP" if ai_url.startswith('http') else "未知"
        logger.info(f"[AttachmentService] 🔍 [步骤1] 判断URL类型: {url_type}")
        logger.info(f"[AttachmentService]     - ai_url长度: {len(ai_url)}")
        if url_type == "Base64":
            # 估算Base64图片大小
            try:
                base64_str = ai_url.split(',', 1)[1] if ',' in ai_url else ''
                estimated_size = len(base64_str) * 3 / 4 / 1024  # Base64解码后大小（KB）
                logger.info(f"[AttachmentService]     - 估算图片大小: {estimated_size:.2f} KB")
            except:
                pass
        
        attachment_id = str(uuid.uuid4())
        resolved_filename = filename or self._build_generated_filename(prefix, mime_type)
        resolved_file_uri, resolved_google_file_uri = self._resolve_provider_asset_metadata(
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
        if ai_url.startswith('data:'):
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
        self.db.add(attachment)
        self.db.commit()
        step3_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ✅ [步骤3] 附件记录已创建并保存到数据库 (耗时: {step3_time:.2f}ms)")

        local_storage_url = await self._persist_to_local_storage_if_enabled(
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
        task_id = await self._submit_upload_task(
            session_id=session_id,
            message_id=message_id,
            attachment_id=attachment_id,
            source_ai_url=ai_url,  # ✅ 新增source类型（可以是Base64或HTTP）
            filename=resolved_filename,
            mime_type=mime_type,
            storage_id=storage_id,
        )
        attachment.upload_task_id = task_id
        self.db.commit()
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

    async def resolve_continuity_attachment(
        self,
        active_image_url: str,
        session_id: str,
        user_id: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        解析CONTINUITY LOGIC的附件

        流程:
        1. 在messages中查找active_image_url对应的附件
        2. 查询数据库获取最新云URL
        3. 如果已上传完成 → 直接返回云URL
        4. 如果未上传 → 提交Worker Pool任务

        **关键优化**: 后端负责查找，前端无需findAttachmentByUrl

        参数:
            active_image_url: 画布当前图片URL
            session_id: 会话ID
            user_id: 用户ID
            messages: 历史消息列表

        返回:
            {
                'attachment_id': str,
                'url': str,              # 云URL（如果已上传）或原URL
                'status': 'completed' | 'pending',
                'task_id': str | None
            }
            或 None（未找到）
        """
        import time
        start_time = time.time()
        
        # ✅ 详细日志：步骤1 - 查找匹配的附件ID
        logger.info(f"[AttachmentService] 🔍 [步骤1] 开始查找匹配的附件ID...")
        logger.info(f"[AttachmentService]     - active_image_url类型: {'Blob' if active_image_url.startswith('blob:') else 'Base64' if active_image_url.startswith('data:') else 'HTTP' if active_image_url.startswith('http') else '未知'}")
        logger.info(f"[AttachmentService]     - active_image_url长度: {len(active_image_url)}")
        logger.info(f"[AttachmentService]     - messages数量: {len(messages)}")
        
        attachment_id = self._find_attachment_by_url(active_image_url, messages)
        
        if attachment_id:
            logger.info(f"[AttachmentService] ✅ [步骤1] 在messages中找到附件ID: {attachment_id}")
        else:
            logger.info(f"[AttachmentService] ⚠️ [步骤1] 在messages中未找到匹配的附件ID")

        if not attachment_id:
            # 策略: Blob URL兜底 - 查找最近的已上传图片
            if active_image_url.startswith('blob:'):
                logger.info(f"[AttachmentService] 🔄 [步骤1-兜底] Blob URL，尝试查找最近的已上传图片...")
                attachment_id = self._find_latest_uploaded_image(session_id, user_id)
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
        
        attachment = self.db.query(MessageAttachment).filter_by(
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
        if attachment.url and attachment.url.startswith('data:'):
            logger.info(f"[AttachmentService]     - url: Base64 Data URL (长度: {len(attachment.url)} 字符)")
        else:
            logger.info(f"[AttachmentService]     - url: {attachment.url[:80] + '...' if attachment.url and len(attachment.url) > 80 else attachment.url or 'None'}")
        logger.info(f"[AttachmentService]     - temp_url: {'存在' if attachment.temp_url else 'None'}")
        if attachment.temp_url and attachment.temp_url.startswith('data:'):
            logger.info(f"[AttachmentService]     - temp_url类型: Base64 (长度: {len(attachment.temp_url)} 字符)")
        else:
            logger.info(f"[AttachmentService]     - temp_url类型: {'HTTP' if attachment.temp_url and attachment.temp_url.startswith('http') else 'None' if not attachment.temp_url else '其他'}")

        # ✅ 详细日志：步骤3 - 检查上传状态
        logger.info(f"[AttachmentService] 🔍 [步骤3] 检查上传状态...")
        
        # ✅ 关键修复：如果附件已经上传完成且有 HTTP URL，直接返回，不创建新任务
        if attachment.upload_status == 'completed' and self._is_persistent_storage_url(attachment.url):
            # 已上传到云存储 → 直接返回云URL，不创建新任务
            elapsed_time = (time.time() - start_time) * 1000
            logger.info(f"[AttachmentService] ✅ [步骤3] 附件已上传完成，直接复用 (耗时: {elapsed_time:.2f}ms)")
            logger.info(f"[AttachmentService]     - 跳过上传任务创建")
            # 对于BASE64 URL，只输出类型和长度，不输出内容
            if attachment.url and attachment.url.startswith('data:'):
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
        if self._is_persistent_storage_url(attachment.url) and attachment.upload_status != 'completed':
            logger.warning(f"[AttachmentService] ⚠️ [步骤3] 附件有 HTTP URL 但状态不是 completed，更新状态并直接返回")
            logger.warning(f"[AttachmentService]     - 原状态: {attachment.upload_status}")
            logger.warning(f"[AttachmentService]     - 更新为: completed")
            attachment.upload_status = 'completed'
            self.db.commit()
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
            logger.info(f"[AttachmentService]     - temp_url类型: {'Base64' if attachment.temp_url.startswith('data:') else 'HTTP'}")
        elif attachment.url and not attachment.url.startswith('http'):
            # 有 url 但不是 HTTP URL（可能是Base64），使用 source_ai_url
            source_ai_url = attachment.url
            logger.info(f"[AttachmentService]     - 使用 url (非HTTP) 作为 source_ai_url")
        elif attachment.url and attachment.url.startswith('http'):
            # 有 HTTP URL，使用 source_url
            source_url = attachment.url
            logger.info(f"[AttachmentService]     - 使用 url (HTTP) 作为 source_url")
        elif active_image_url:
            # ✅ 关键修复：附件没有任何 URL，使用请求中的 active_image_url
            logger.info(f"[AttachmentService]     - 附件没有 URL，使用请求中的 active_image_url")
            if active_image_url.startswith('data:') or active_image_url.startswith('blob:'):
                source_ai_url = active_image_url
                logger.info(f"[AttachmentService]     - active_image_url类型: {'Base64' if active_image_url.startswith('data:') else 'Blob'}")
            elif active_image_url.startswith('http'):
                source_url = active_image_url
                logger.info(f"[AttachmentService]     - active_image_url类型: HTTP")
            else:
                logger.warning(f"[AttachmentService]     - ⚠️ active_image_url类型未知: {active_image_url[:50]}...")
        else:
            logger.warning(f"[AttachmentService]     - ⚠️ 没有可用的源URL或文件路径")
        
        logger.info(f"[AttachmentService] 🔄 [步骤4] 调用 _submit_upload_task() 创建上传任务...")
        task_id = await self._submit_upload_task(
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

    async def get_cloud_url(
        self,
        attachment_id: str,
        user_id: str
    ) -> Optional[str]:
        """
        获取附件的云存储URL

        流程:
        1. 查询MessageAttachment
        2. 如果有upload_task_id → 查询UploadTask.target_url（最权威）
        3. 否则返回attachment.url

        **替代**: 前端的tryFetchCloudUrl

        参数:
            attachment_id: 附件ID
            user_id: 用户ID

        返回:
            云URL 或 None
        """
        attachment = self.db.query(MessageAttachment).filter_by(
            id=attachment_id,
            user_id=user_id
        ).first()

        if not attachment:
            return None

        # 优先级1: UploadTask.target_url
        if attachment.upload_task_id:
            task = self.db.query(UploadTask).filter_by(
                id=attachment.upload_task_id,
                status='completed'
            ).first()
            if task and task.target_url:
                return task.target_url

        # 优先级2: attachment.url
        if attachment.url and attachment.upload_status == 'completed':
            return attachment.url

        return None

    # ==================== 私有方法 ====================

    def _get_effective_storage_config(
        self,
        *,
        user_id: str,
        storage_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        config: Optional[StorageConfig] = None

        if storage_id:
            config = self.db.query(StorageConfig).filter(StorageConfig.id == storage_id).first()
        else:
            active = self.db.query(ActiveStorage).filter(ActiveStorage.user_id == user_id).first()
            if not active:
                active = self.db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
            if active and active.storage_id:
                config = self.db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()

        if not config or not config.enabled:
            return None

        raw_config = dict(config.config or {})
        try:
            resolved_config = decrypt_config(raw_config)
        except Exception:
            resolved_config = raw_config

        return {
            "id": config.id,
            "provider": str(config.provider or "").strip().lower(),
            "config": resolved_config,
        }

    async def _persist_to_local_storage_if_enabled(
        self,
        *,
        attachment: MessageAttachment,
        user_id: str,
        filename: str,
        mime_type: str,
        storage_id: Optional[str] = None,
        source_file_path: Optional[str] = None,
        source_ai_url: Optional[str] = None,
    ) -> Optional[str]:
        storage = self._get_effective_storage_config(user_id=user_id, storage_id=storage_id)
        if not storage or storage.get("provider") != "local":
            return None

        content = await self._load_local_storage_source_bytes(
            user_id=user_id,
            source_file_path=source_file_path,
            source_ai_url=source_ai_url,
        )
        upload = await StorageService.upload_file(
            filename=filename,
            content=content,
            content_type=mime_type,
            provider="local",
            config=dict(storage.get("config") or {}),
        )
        persisted_url = str(upload.get("url") or "").strip()
        if not persisted_url:
            raise RuntimeError("Local storage upload returned an empty URL.")

        attachment.url = persisted_url
        attachment.temp_url = None
        attachment.upload_status = 'completed'
        attachment.upload_task_id = None
        attachment.upload_error = None
        self.db.commit()

        if source_file_path:
            self._delete_local_source_file(source_file_path)

        return persisted_url

    async def _load_local_storage_source_bytes(
        self,
        *,
        user_id: str,
        source_file_path: Optional[str] = None,
        source_ai_url: Optional[str] = None,
    ) -> bytes:
        if source_file_path:
            from ...core.path_utils import resolve_relative_path

            file_path = resolve_relative_path(source_file_path)
            with open(file_path, 'rb') as f:
                return f.read()

        normalized_ai_url = str(source_ai_url or "").strip()
        if not normalized_ai_url:
            raise ValueError("Local storage persistence requires a source payload.")

        if normalized_ai_url.startswith('data:'):
            _mime_type, base64_str = self._parse_data_url(normalized_ai_url)
            return base64.b64decode(base64_str)

        if normalized_ai_url.startswith('files/') or normalized_ai_url.startswith('gs://') or self._is_google_provider_http_file_url(normalized_ai_url):
            from ..gemini.base.video_asset_download import download_google_video_asset_for_user
            from ..gemini.base.video_common import normalize_gemini_file_name

            provider_file_name = normalize_gemini_file_name(normalized_ai_url)
            provider_file_uri = normalized_ai_url if normalized_ai_url.startswith('files/') or provider_file_name else None
            gcs_uri = normalized_ai_url if normalized_ai_url.startswith('gs://') else None
            payload, _mime_type = await download_google_video_asset_for_user(
                self.db,
                user_id,
                provider_file_name=provider_file_name,
                provider_file_uri=provider_file_uri,
                gcs_uri=gcs_uri,
            )
            return payload

        safe_url = validate_outbound_http_url(normalized_ai_url)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response, _final_url = await get_with_redirect_guard(client, safe_url, max_redirects=5)
            response.raise_for_status()
            return response.content

    def _delete_local_source_file(self, source_file_path: str) -> None:
        from ...core.path_utils import resolve_relative_path

        try:
            file_path = resolve_relative_path(source_file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.warning(f"[AttachmentService] 本地存储直写后删除临时文件失败: {source_file_path}")

    def _is_persistent_storage_url(self, url: Optional[str]) -> bool:
        from ..gemini.base.video_common import normalize_gemini_file_name

        normalized = str(url or "").strip()
        if not normalized:
            return False
        if normalized.startswith('data:') or normalized.startswith('blob:'):
            return False
        if normalized.startswith('gs://') or normalized.startswith('files/'):
            return False
        if normalize_gemini_file_name(normalized):
            return False
        return True

    def _is_google_provider_http_file_url(self, url: str) -> bool:
        normalized = str(url or "").strip()
        return normalized.startswith("https://") and "/files/" in normalized

    def _parse_data_url(self, data_url: str) -> tuple[str, str]:
        if not data_url.startswith('data:'):
            raise ValueError("Invalid data URL")

        parts = data_url.split(',', 1)
        if len(parts) != 2:
            raise ValueError("Invalid data URL format")

        header = parts[0]
        base64_str = parts[1]
        mime_type = header.split(':', 1)[1].split(';', 1)[0] if ':' in header else ''
        return (mime_type or 'application/octet-stream', base64_str)

    async def _submit_upload_task(
        self,
        session_id: str,
        message_id: str,
        attachment_id: str,
        filename: str,
        mime_type: str,
        source_file_path: Optional[str] = None,
        source_url: Optional[str] = None,
        source_ai_url: Optional[str] = None,
        source_attachment_id: Optional[str] = None,
        priority: str = 'normal',
        storage_id: Optional[str] = None
    ) -> str:
        """
        提交上传任务到Worker Pool

        参数:
            session_id: 会话ID
            message_id: 消息ID
            attachment_id: 附件ID
            filename: 文件名
            mime_type: MIME类型
            source_file_path: 源文件路径（可选）
            source_url: 源URL（可选）
            source_ai_url: AI返回URL（可选，新增）
            source_attachment_id: 复用附件ID（可选，新增）
            priority: 优先级

        返回:
            任务ID
        """
        import time
        start_time = time.time()
        
        logger.info(f"[AttachmentService] ========== 开始创建上传任务 ==========")
        logger.info(f"[AttachmentService] 📋 任务参数:")
        logger.info(f"[AttachmentService]     - attachment_id: {attachment_id}")
        logger.info(f"[AttachmentService]     - filename: {filename}")
        logger.info(f"[AttachmentService]     - mime_type: {mime_type}")
        logger.info(f"[AttachmentService]     - session_id: {session_id if session_id else 'None'}")
        logger.info(f"[AttachmentService]     - message_id: {message_id if message_id else 'None'}")
        logger.info(f"[AttachmentService]     - priority: {priority}")
        logger.info(f"[AttachmentService]     - storage_id: {storage_id if storage_id else 'None'}")
        
        # ✅ 详细日志：检查source类型
        logger.info(f"[AttachmentService] 🔍 检查源类型:")
        logger.info(f"[AttachmentService]     - source_file_path: {'存在' if source_file_path else 'None'}")
        logger.info(f"[AttachmentService]     - source_url: {'存在 (HTTP URL)' if source_url else 'None'}")
        logger.info(f"[AttachmentService]     - source_ai_url: {'存在 (' + ('Base64' if source_ai_url and source_ai_url.startswith('data:') else 'HTTP') + ')' if source_ai_url else 'None'}")
        logger.info(f"[AttachmentService]     - source_attachment_id: {source_attachment_id if source_attachment_id else 'None'}")
        
        # 确保至少有一个source
        if not any([source_file_path, source_url, source_ai_url, source_attachment_id]):
            logger.error(f"[AttachmentService] ❌ 错误: 至少需要提供一个source")
            raise ValueError("至少需要提供一个source（source_file_path, source_url, source_ai_url, source_attachment_id）")

        task_id = str(uuid.uuid4())
        logger.info(f"[AttachmentService] 🔄 [步骤1] 生成任务ID: {task_id}")

        # ✅ 详细日志：步骤1 - 创建UploadTask记录
        logger.info(f"[AttachmentService] 🔄 [步骤1] 创建UploadTask记录...")
        task = UploadTask(
            id=task_id,
            session_id=session_id,
            message_id=message_id,
            attachment_id=attachment_id,
            source_file_path=source_file_path,
            source_url=source_url,
            source_ai_url=source_ai_url,  # ✅ 新增字段（需要数据库迁移）
            source_attachment_id=source_attachment_id,  # ✅ 新增字段（需要数据库迁移）
            filename=filename,
            priority=priority,
            storage_id=storage_id,  # ✅ 存储配置ID（可选）
            retry_count=0,
            status='pending',
            created_at=int(datetime.now().timestamp() * 1000)
        )

        self.db.add(task)
        self.db.commit()
        step1_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ✅ [步骤1] UploadTask记录已创建并保存到数据库 (耗时: {step1_time:.2f}ms)")

        # ✅ 详细日志：步骤2 - 入队任务到 Redis
        logger.info(f"[AttachmentService] 🔄 [步骤2] 入队Redis...")
        try:
            # 确保Redis连接已建立
            if redis_queue._redis is None:
                logger.info(f"[AttachmentService]     - Redis连接未建立，正在连接...")
                await redis_queue.connect()
                logger.info(f"[AttachmentService]     - Redis连接已建立")

            queue_position = await redis_queue.enqueue(task_id, priority)
            step2_time = (time.time() - start_time) * 1000
            logger.info(f"[AttachmentService] ✅ [步骤2] 任务已入队Redis (耗时: {step2_time:.2f}ms)")
            logger.info(f"[AttachmentService]     - queue_position: {queue_position}")

            # ✅ 步骤3: 确保Worker正在运行（按需启动）
            logger.info(f"[AttachmentService] 🔄 [步骤3] 确保Worker正在运行...")
            await worker_pool.ensure_worker_running()
            step3_time = (time.time() - start_time) * 1000
            logger.info(f"[AttachmentService] ✅ [步骤3] Worker已启动/运行中 (耗时: {step3_time:.2f}ms)")
        except Exception as e:
            step2_time = (time.time() - start_time) * 1000
            logger.error(f"[AttachmentService] ❌ [步骤2] Redis入队失败 (耗时: {step2_time:.2f}ms): {e}")
            logger.error(f"[AttachmentService]     - 任务已保存到数据库，Worker Pool会在启动时恢复")
            # 即使Redis入队失败，任务也已保存到数据库
            # Worker Pool会在启动时恢复这些任务

        total_time = (time.time() - start_time) * 1000
        logger.info(f"[AttachmentService] ========== 上传任务创建完成 (总耗时: {total_time:.2f}ms) ==========")
        logger.info(f"[AttachmentService]     - task_id: {task_id}")
        logger.info(f"[AttachmentService]     - attachment_id: {attachment_id}")

        return task_id

    def _build_generated_filename(self, prefix: str, mime_type: Optional[str]) -> str:
        guessed_ext = mimetypes.guess_extension((mime_type or "").split(";")[0].strip()) or ""
        if guessed_ext == ".jpe":
            guessed_ext = ".jpg"
        if not guessed_ext:
            guessed_ext = ".bin"
        return f"{prefix}-{uuid.uuid4()}{guessed_ext}"

    def _resolve_provider_asset_metadata(
        self,
        *,
        ai_url: Optional[str],
        file_uri: Optional[str] = None,
        provider_file_name: Optional[str] = None,
        provider_file_uri: Optional[str] = None,
        gcs_uri: Optional[str] = None,
    ) -> tuple[str, str]:
        from ..gemini.base.video_common import normalize_gemini_file_name

        normalized_ai_url = str(ai_url or "").strip()
        normalized_file_uri = str(file_uri or "").strip()
        normalized_provider_file_name = str(provider_file_name or "").strip()
        normalized_provider_file_uri = str(provider_file_uri or "").strip()
        normalized_gcs_uri = str(gcs_uri or "").strip()

        resolved_file_uri = (
            normalized_file_uri
            or normalized_gcs_uri
            or normalized_provider_file_uri
            or normalized_provider_file_name
        )
        if not resolved_file_uri:
            if normalized_ai_url.startswith("gs://") or normalize_gemini_file_name(normalized_ai_url):
                resolved_file_uri = normalized_ai_url

        resolved_google_file_uri = normalize_gemini_file_name(
            normalized_provider_file_name
            or normalized_provider_file_uri
            or resolved_file_uri
        ) or ""

        return resolved_file_uri, resolved_google_file_uri

    def _find_attachment_by_url(
        self,
        target_url: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        在消息列表中查找附件ID

        策略:
        1. 精确匹配url
        2. 精确匹配tempUrl

        **不再有**: 模糊匹配（原文档错误）
        """
        for msg in reversed(messages):  # 从新到旧
            for att in msg.get('attachments', []):
                # 策略1: 精确匹配url
                if att.get('url') == target_url:
                    return att.get('id')

                # 策略2: 精确匹配tempUrl
                if att.get('tempUrl') == target_url:
                    return att.get('id')

        return None

    def _find_latest_uploaded_image(
        self,
        session_id: str,
        user_id: str
    ) -> Optional[str]:
        """
        Blob URL兜底策略: 查找最近的已上传图片

        策略3: Blob URL兜底
        """
        attachment = self.db.query(MessageAttachment).filter(
            MessageAttachment.session_id == session_id,
            MessageAttachment.user_id == user_id,
            MessageAttachment.mime_type.like('image/%'),
            MessageAttachment.upload_status == 'completed',
            MessageAttachment.url.isnot(None)
        ).order_by(
            MessageAttachment.id.desc()  # 使用id降序（近似时间顺序）
        ).first()

        return attachment.id if attachment else None
