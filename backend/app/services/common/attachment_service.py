"""
统一附件处理服务

职责:
1. 处理所有来源的附件（用户上传、AI返回、CONTINUITY LOGIC）
2. 统一云URL管理
3. 调度Worker Pool异步上传
4. 管理附件生命周期
"""

from typing import Optional, Dict, Any, List

# 持久化契约与容错 wrapper 已拆分到 attachment_persistence;此处 re-export 以保持
# 既有 ``from ...attachment_service import safe_persist_ai_result, UploadStatus`` 等
# import 路径不变(公共 API 不变)。
from .attachment_persistence import (
    UploadStatus,
    ProcessAIResultDict,
    safe_persist_ai_result,
    safe_persist_ai_result_concurrent,
)

from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging
import time

from ...core.encryption import ConfigDecryptionError, decrypt_config
from ...utils.attachment_handler import is_base64_url
from ...models.db_models import MessageAttachment, UploadTask, StorageConfig, ActiveStorage
from .redis_queue_service import redis_queue
from .upload_worker_pool import worker_pool
from .upload_task_scope import is_upload_task_owned_by_user
from ..storage.storage_service import StorageService
from . import attachment_records
from .attachment_local_writer import record_local_persist_failure
from .attachment_source_resolver import (
    delete_local_source_file,
    load_local_storage_source_bytes,
)
# 两个大编排方法的内部逻辑已拆到独立模块,服务层只保留薄包装(公共 API 不变)。
from .attachment_ai_result import process_ai_result as _process_ai_result_impl
from .attachment_continuity import (
    resolve_continuity_attachment as _resolve_continuity_attachment_impl,
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
            user_id=user_id,
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
    ) -> ProcessAIResultDict:
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
        # 编排实现已迁出到 attachment_ai_result;此处仅薄包装委派。
        # 传 self 让实现按调用点解析协作者(_submit_upload_task /
        # _persist_to_local_storage_if_enabled 等),保持 monkeypatch 契约。
        return await _process_ai_result_impl(
            self,
            ai_url=ai_url,
            mime_type=mime_type,
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            prefix=prefix,
            storage_id=storage_id,
            filename=filename,
            file_uri=file_uri,
            provider_file_name=provider_file_name,
            provider_file_uri=provider_file_uri,
            gcs_uri=gcs_uri,
        )

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
        # 编排实现已迁出到 attachment_continuity;此处仅薄包装委派。
        # 传 self 让实现按调用点解析协作者(_find_attachment_by_url /
        # _submit_upload_task / db 等),保持 monkeypatch 契约。
        return await _resolve_continuity_attachment_impl(
            self,
            active_image_url=active_image_url,
            session_id=session_id,
            user_id=user_id,
            messages=messages,
        )

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
            if task and task.target_url and is_upload_task_owned_by_user(self.db, task, user_id):
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
        except ConfigDecryptionError:
            # fail-closed（B2）：解密失败时绝不把 Fernet 密文配置交给存储 provider，
            # 与 V-S2 / fe394cb 的契约一致。让错误向上抛出而非静默回退到密文。
            logger.error(
                "[AttachmentService] 存储配置解密失败（ENCRYPTION_KEY 不匹配？），"
                "拒绝使用密文配置: storage_id=%s",
                config.id,
            )
            raise

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

        # 复合主键 (id, message_id) —— 在任何可能失败的 I/O 之前抓取,
        # 以便 except 分支即使 session 处于失败事务态也能精确定位该行写诊断。
        attachment_pk_id = attachment.id
        attachment_pk_message_id = attachment.message_id

        try:
            load_start = time.time()
            content = await load_local_storage_source_bytes(
                db=self.db,
                user_id=user_id,
                source_file_path=source_file_path,
                source_ai_url=source_ai_url,
            )
            logger.info(
                "[AttachmentService] 本地存储源数据读取完成 (bytes=%s, 耗时: %.2fms)",
                len(content),
                (time.time() - load_start) * 1000,
            )

            upload_start = time.time()
            upload = await StorageService.upload_file(
                filename=filename,
                content=content,
                content_type=mime_type,
                provider="local",
                config=dict(storage.get("config") or {}),
            )
            logger.info(
                "[AttachmentService] 本地存储写入完成 (耗时: %.2fms)",
                (time.time() - upload_start) * 1000,
            )
            persisted_url = str(upload.get("url") or "").strip()
            if not persisted_url:
                raise RuntimeError("Local storage upload returned an empty URL.")

            db_update_start = time.time()
            attachment.url = persisted_url
            attachment.temp_url = None
            attachment.upload_status = 'completed'
            attachment.upload_task_id = None
            attachment.upload_error = None
            self.db.commit()
            logger.info(
                "[AttachmentService] 本地存储附件状态更新完成 (耗时: %.2fms)",
                (time.time() - db_update_start) * 1000,
            )

            if source_file_path:
                delete_local_source_file(source_file_path)

            return persisted_url
        except Exception as err:
            # guard-over-swallow:本地直写失败时,把失败原因落到该附件行
            # (upload_status='failed' + upload_error),再原样向上抛 ——
            # 绝不吞成 fallback 成功。即便上层 wrapper(safe_persist_*)吞掉异常,
            # DB 行本身也能自证失败原因,根治"故障神秘、查不出 upload_error"。
            self._record_local_persist_failure(
                attachment_pk_id=attachment_pk_id,
                attachment_pk_message_id=attachment_pk_message_id,
                error=err,
            )
            raise

    def _record_local_persist_failure(
        self,
        *,
        attachment_pk_id: Any,
        attachment_pk_message_id: Any,
        error: Exception,
    ) -> None:
        record_local_persist_failure(
            db=self.db,
            attachment_pk_id=attachment_pk_id,
            attachment_pk_message_id=attachment_pk_message_id,
            error=error,
        )

    def _is_persistent_storage_url(self, url: Optional[str]) -> bool:
        return attachment_records.is_persistent_storage_url(url)

    def _is_google_provider_http_file_url(self, url: str) -> bool:
        return attachment_records.is_google_provider_http_file_url(url)

    def _parse_data_url(self, data_url: str) -> tuple[str, str]:
        return attachment_records.parse_data_url(data_url)

    async def _submit_upload_task(
        self,
        user_id: str,
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
            user_id: 用户ID
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
        start_time = time.time()
        
        logger.info(f"[AttachmentService] ========== 开始创建上传任务 ==========")
        logger.info(f"[AttachmentService] 📋 任务参数:")
        logger.info(f"[AttachmentService]     - attachment_id: {attachment_id}")
        logger.info(f"[AttachmentService]     - filename: {filename}")
        logger.info(f"[AttachmentService]     - mime_type: {mime_type}")
        logger.info(f"[AttachmentService]     - user_id: {user_id}")
        logger.info(f"[AttachmentService]     - session_id: {session_id if session_id else 'None'}")
        logger.info(f"[AttachmentService]     - message_id: {message_id if message_id else 'None'}")
        logger.info(f"[AttachmentService]     - priority: {priority}")
        logger.info(f"[AttachmentService]     - storage_id: {storage_id if storage_id else 'None'}")
        
        # ✅ 详细日志：检查source类型
        logger.info(f"[AttachmentService] 🔍 检查源类型:")
        logger.info(f"[AttachmentService]     - source_file_path: {'存在' if source_file_path else 'None'}")
        logger.info(f"[AttachmentService]     - source_url: {'存在 (HTTP URL)' if source_url else 'None'}")
        logger.info(f"[AttachmentService]     - source_ai_url: {'存在 (' + ('Base64' if is_base64_url(source_ai_url) else 'HTTP') + ')' if source_ai_url else 'None'}")
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
        return attachment_records.build_generated_filename(prefix, mime_type)

    def _resolve_provider_asset_metadata(
        self,
        *,
        ai_url: Optional[str],
        file_uri: Optional[str] = None,
        provider_file_name: Optional[str] = None,
        provider_file_uri: Optional[str] = None,
        gcs_uri: Optional[str] = None,
    ) -> tuple[str, str]:
        return attachment_records.resolve_provider_asset_metadata(
            ai_url=ai_url,
            file_uri=file_uri,
            provider_file_name=provider_file_name,
            provider_file_uri=provider_file_uri,
            gcs_uri=gcs_uri,
        )

    def _find_attachment_by_url(
        self,
        target_url: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        return attachment_records.find_attachment_by_url(target_url, messages)

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
