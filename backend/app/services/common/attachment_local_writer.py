"""本地直写失败诊断写回

从 ``attachment_service.py`` 拆出的"把本地直写失败原因写回 ``message_attachments``
行"逻辑。直写主流程(读取源字节 → StorageService.upload_file → 更新附件状态)仍留在
``AttachmentService._persist_to_local_storage_if_enabled`` 中,因为它依赖被测试
monkeypatch 的模块级 ``StorageService`` / 实例级 ``_get_effective_storage_config``;
而本失败诊断写回只用 ``db`` 与 ORM 模型,不触碰这些被 patch 的名字,可安全迁出。
"""

import logging
from typing import Any

from ...models.db_models import MessageAttachment

logger = logging.getLogger(__name__)


def record_local_persist_failure(
    *,
    db: Any,
    attachment_pk_id: Any,
    attachment_pk_message_id: Any,
    error: Exception,
) -> None:
    """best-effort 把本地直写失败原因写回 ``message_attachments`` 行。

    直写过程若在 commit 阶段抛错,session 可能处于失败事务态 —— 先 ``rollback``
    再以复合主键定向 ``UPDATE``,确保诊断写入不被原异常事务连累。任何二次失败
    只记日志,不掩盖原始异常(原始异常由 caller ``raise`` 继续上抛)。
    """
    detail = f"{type(error).__name__}: {error}"[:1000]
    try:
        db.rollback()
        db.query(MessageAttachment).filter(
            MessageAttachment.id == attachment_pk_id,
            MessageAttachment.message_id == attachment_pk_message_id,
        ).update(
            {
                MessageAttachment.upload_status: 'failed',
                MessageAttachment.upload_error: detail,
            },
            synchronize_session=False,
        )
        db.commit()
        logger.error(
            "[AttachmentService] 本地直写失败,已标记附件 %s 为 failed: %s",
            attachment_pk_id,
            detail,
            exc_info=True,
        )
    except Exception:
        logger.error(
            "[AttachmentService] 记录本地直写失败诊断时二次失败 (attachment_id=%s)",
            attachment_pk_id,
            exc_info=True,
        )
