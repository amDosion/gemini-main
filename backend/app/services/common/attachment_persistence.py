"""AI 媒体持久化契约与容错 wrapper

从 ``attachment_service.py`` 拆出的"持久化结果 shape + 容错调用"层:
- ``UploadStatus``:与 ``message_attachments.upload_status`` 列对齐的字面量契约。
- ``ProcessAIResultDict``:``AttachmentService.process_ai_result(...)`` 的返回 shape。
- ``safe_persist_ai_result`` / ``safe_persist_ai_result_concurrent``:把
  "调用 process_ai_result + try/except + log"模式集中到一处。

为保持公共 API 不变,``attachment_service`` 仍 re-export 这些符号,既有
``from ...attachment_service import safe_persist_ai_result, UploadStatus`` 等
import 路径完全不受影响。

``AttachmentService`` 在 wrapper 内 *延迟* import,避免 ``attachment_service`` ↔
``attachment_persistence`` 顶层循环 import;同时保证 monkeypatch
``AttachmentService.process_ai_result`` 命中的是同一个类对象。
"""

import logging
from typing import Any, Optional, Literal, TypedDict

logger = logging.getLogger(__name__)


# 附件上传状态契约 —— 与 message_attachments.upload_status 列对齐。
# 其他模块(modes.py / workflows.py / handlers)从此处 import,确保 typo
# 在 IDE / mypy 静态检查阶段被发现。
UploadStatus = Literal["pending", "uploading", "completed", "failed"]


class ProcessAIResultDict(TypedDict, total=False):
    """``AttachmentService.process_ai_result(...)`` 的返回 shape。

    total=False:所有字段 optional —— 不同 provider 路径 / 降级路径返回的 keyset 不同。
    ``status`` 是 ``UploadStatus`` 字面量四选一,IDE 会针对赋值字面量 typo 报错。
    """
    attachment_id: str
    display_url: str
    cloud_url: str
    status: UploadStatus
    task_id: Optional[str]
    file_uri: Optional[str]
    google_file_uri: Optional[str]
    mime_type: str
    filename: str
    session_id: str
    message_id: str
    user_id: str


async def safe_persist_ai_result(
    attachment_service: Any,
    *,
    log_label: str = "媒体",
    log_with_traceback: bool = True,
    **kwargs: Any,
) -> Optional["ProcessAIResultDict"]:
    """``process_ai_result`` 的容错 wrapper —— 把"调用 + try/except + log"模式
    集中到一处,modes.py / workflows.py / template_sample / google_service 共用。

    成功:返回 ``ProcessAIResultDict``。失败:log 后返回 ``None``,caller 自定义降级。

    持久化失败属罕见且高价值事件 —— 始终带 traceback 记 ERROR(不再因
    ``log_with_traceback=False`` 丢 traceback),避免出现"故障神秘、查不出原因"。
    ``log_with_traceback`` 形参保留以兼容既有 caller 签名,但失败日志恒带堆栈。
    """
    try:
        return await attachment_service.process_ai_result(**kwargs)
    except Exception as err:
        logger.error("[Persist] %s 失败: %r", log_label, err, exc_info=True)
        return None


async def safe_persist_ai_result_concurrent(
    sessionmaker: Any,
    *,
    log_label: str = "媒体",
    log_with_traceback: bool = False,
    reraise: bool = False,
    **kwargs: Any,
) -> Optional["ProcessAIResultDict"]:
    """并发安全版 —— 每次调用打开一个 *fresh* SQLAlchemy ``Session``,内部构造
    临时 ``AttachmentService`` 实例,跑完即关。

    用于 ``asyncio.gather(...)`` 同时持久化 N 个 AI 媒体 (image batch / video sidecars)。
    SQLAlchemy ``Session`` non-task-safe — 共享实例并发会破坏 identity map / pending
    changes / transaction boundary,本 wrapper 保证 session-per-task。

    ``sessionmaker``:无参可调用对象(典型为 ``app.core.database.SessionLocal``),
    ``with sessionmaker() as fresh_session:`` 自动 close。

    成功:返回 ``ProcessAIResultDict``。

    失败处理(始终先带 traceback 记 ERROR,杜绝静默吞错):
    - ``reraise=False``(默认):返回 ``None``,caller 自行降级(video sidecar 等
      优雅降级路径依赖此契约)。
    - ``reraise=True``:向上抛原异常 —— 用于硬失败路径(image-gen 必须把底层
      原因暴露给 route,绝不接受非持久化"成功"或静默 ``None``)。

    ``log_with_traceback`` 形参保留以兼容既有 caller 签名,但失败日志恒带堆栈。
    """
    # local import 避免顶层循环 import(AttachmentService 定义在 attachment_service)
    from .attachment_service import AttachmentService

    try:
        with sessionmaker() as fresh_session:
            service = AttachmentService(fresh_session)
            return await service.process_ai_result(**kwargs)
    except Exception as err:
        logger.error("[Persist] %s 失败: %r", log_label, err, exc_info=True)
        if reraise:
            raise
        return None
