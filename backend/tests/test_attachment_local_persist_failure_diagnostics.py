"""回归:本地直写持久化失败时的可诊断传播(Layer 1 修复)。

证据文档: .investigations/2026-06-02-image-gen-local-persistence-failure.md

被固化的不变式:
1. 本地直写失败时,失败原因必须落到 ``message_attachments`` 行
   (``upload_status='failed'`` + ``upload_error`` 含底层异常类型与消息),
   并向上抛原异常 —— 绝不静默吞成 fallback 成功,也绝不留下无 ``upload_error``
   的 ``pending`` 行(这正是线上"故障神秘、查不出原因"的直接根因)。
2. ``safe_persist_ai_result_concurrent(reraise=True)``:把底层异常暴露给 route
   (image-gen 硬失败路径,details 注入 error_type/error_message)。
3. ``safe_persist_ai_result_concurrent(reraise=False)``:保持"失败返回 None,
   caller 优雅降级"契约(video sidecar 等路径依赖此行为)。

红→绿:修复前 (a) 直写失败不写 ``upload_error`` 且行停留 ``pending`` → 测试 1 红;
(b) ``reraise`` 形参不存在 → 测试 2/3 触发 TypeError 红。修复后三者皆绿。
"""
import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import MessageAttachment
from app.services.common.attachment_service import (
    AttachmentService,
    safe_persist_ai_result_concurrent,
)

# 合法 base64 data URL —— process_ai_result 仅 base64 解码后写盘,不校验 PNG 结构。
_PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"0" * 256
).decode("ascii")


def _sessionmaker():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _force_local_storage(svc: AttachmentService) -> None:
    """绕过 storage_configs 表查询,强制解析为 local provider(走直写分支)。"""
    svc._get_effective_storage_config = lambda **_kw: {  # type: ignore[method-assign]
        "id": "storage-local-1",
        "provider": "local",
        "config": {},
    }


@pytest.mark.asyncio
async def test_local_direct_write_failure_records_upload_error_and_reraises(monkeypatch) -> None:
    session_factory = _sessionmaker()
    db = session_factory()
    svc = AttachmentService(db)
    _force_local_storage(svc)

    async def _boom(**_kwargs):
        raise RuntimeError("disk boom")

    monkeypatch.setattr(
        "app.services.common.attachment_service.StorageService.upload_file",
        _boom,
    )

    # 直写失败必须向上抛(不吞成 None / 不 fallback)。
    with pytest.raises(RuntimeError, match="disk boom"):
        await svc.process_ai_result(
            ai_url=_PNG_DATA_URL,
            mime_type="image/png",
            session_id="sess-diag-1",
            message_id="msg-diag-1",
            user_id="user-diag-1",
            prefix="generated",
            filename=None,
        )

    # 该附件行自证失败:status=failed + upload_error 含底层异常类型与消息;
    # 且绝不是非持久化"成功"(url 仍为空,未写入伪造云地址)。
    row = db.query(MessageAttachment).filter_by(message_id="msg-diag-1").one()
    assert row.upload_status == "failed"
    assert row.upload_error and "RuntimeError" in row.upload_error
    assert "disk boom" in row.upload_error
    assert (row.url or "") == ""
    db.close()


@pytest.mark.asyncio
async def test_concurrent_wrapper_reraise_true_propagates_underlying_cause(monkeypatch) -> None:
    session_factory = _sessionmaker()

    async def _boom(self, **_kwargs):
        raise RuntimeError("persist exploded")

    monkeypatch.setattr(AttachmentService, "process_ai_result", _boom, raising=True)

    with pytest.raises(RuntimeError, match="persist exploded"):
        await safe_persist_ai_result_concurrent(
            session_factory,
            reraise=True,
            ai_url=_PNG_DATA_URL,
            mime_type="image/png",
            session_id="s",
            message_id="m",
            user_id="u",
            prefix="generated",
            filename=None,
        )


@pytest.mark.asyncio
async def test_concurrent_wrapper_reraise_false_returns_none_for_graceful_degradation(monkeypatch) -> None:
    session_factory = _sessionmaker()

    async def _boom(self, **_kwargs):
        raise RuntimeError("persist exploded")

    monkeypatch.setattr(AttachmentService, "process_ai_result", _boom, raising=True)

    result = await safe_persist_ai_result_concurrent(
        session_factory,
        reraise=False,
        ai_url=_PNG_DATA_URL,
        mime_type="image/png",
        session_id="s",
        message_id="m",
        user_id="u",
        prefix="generated",
        filename=None,
    )
    assert result is None
