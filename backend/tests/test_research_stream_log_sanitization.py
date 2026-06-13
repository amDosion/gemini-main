from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException

from app.routers.ai import research_stream


class _Resolver:
    def __init__(self, error: Exception | None = None):
        self.error = error

    async def resolve(self, **_kwargs):
        if self.error is not None:
            raise self.error
        return "api-key", None


class _FailingManager:
    def __init__(self, error: Exception):
        self.error = error

    async def create_interaction(self, **_kwargs):
        raise self.error

    async def get_interaction_status_async(self, **_kwargs):
        raise self.error

    async def cancel_interaction(self, **_kwargs):
        raise self.error

    async def stream_existing_interaction(self, **_kwargs):
        raise self.error
        yield  # pragma: no cover


async def _collect_streaming_response(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    return "".join(chunks)


def _patch_research_dependencies(monkeypatch, *, resolver=None, manager=None):
    monkeypatch.setattr(
        research_stream,
        "credentials_resolver",
        resolver or _Resolver(),
    )
    if manager is not None:
        monkeypatch.setattr(research_stream, "get_interactions_manager", lambda **_kwargs: manager)
    monkeypatch.setattr(research_stream, "is_deep_research_model", lambda *_args, **_kwargs: True)


@pytest.mark.asyncio
async def test_research_stream_credentials_error_is_summarized(monkeypatch, caplog):
    error_text = "credentials failed with secret-token"
    _patch_research_dependencies(monkeypatch, resolver=_Resolver(RuntimeError(error_text)))
    request = research_stream.StreamStartRequest(
        prompt="private prompt secret-token",
        agent="gemini-deep-research",
        background=True,
        stream=False,
    )

    with caplog.at_level(logging.ERROR, logger=research_stream.logger.name):
        with pytest.raises(HTTPException) as exc_info:
            await research_stream.start_streaming_research(request, user_id="user-1", db=object())

    detail = exc_info.value.detail
    assert detail["code"] == "CREDENTIALS_RESOLVE_FAILED"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert "private prompt" not in str(detail)
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_research_stream_create_error_is_summarized(monkeypatch, caplog):
    error_text = "create interaction failed with secret-token"
    _patch_research_dependencies(monkeypatch, manager=_FailingManager(RuntimeError(error_text)))
    request = research_stream.StreamStartRequest(
        prompt="private prompt secret-token",
        agent="gemini-deep-research",
        background=True,
        stream=False,
    )

    with caplog.at_level(logging.ERROR, logger=research_stream.logger.name):
        with pytest.raises(HTTPException) as exc_info:
            await research_stream.start_streaming_research(request, user_id="user-1", db=object())

    detail = exc_info.value.detail
    assert detail["code"] == "INTERACTION_CREATE_FAILED"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    assert "secret-token" not in "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_research_stream_action_error_is_summarized(monkeypatch, caplog):
    error_text = "action continuation failed with secret-token"
    _patch_research_dependencies(monkeypatch, manager=_FailingManager(RuntimeError(error_text)))
    request = research_stream.StreamActionRequest(
        agent="gemini-deep-research",
        previous_interaction_id="previous-id",
        call_id="call-1",
        result={"ok": True},
    )

    with caplog.at_level(logging.ERROR, logger=research_stream.logger.name):
        with pytest.raises(HTTPException) as exc_info:
            await research_stream.submit_required_action(request, user_id="user-1", db=object())

    detail = exc_info.value.detail
    assert detail["code"] == "REQUIRED_ACTION_SUBMIT_FAILED"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    assert "secret-token" not in "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_research_stream_status_error_summarizes_exception_and_interaction_id(monkeypatch, caplog):
    error_text = "status failed with secret-token"
    interaction_id = "interaction-secret-token"
    _patch_research_dependencies(monkeypatch, manager=_FailingManager(RuntimeError(error_text)))

    with caplog.at_level(logging.ERROR, logger=research_stream.logger.name):
        with pytest.raises(HTTPException) as exc_info:
            await research_stream.get_streaming_research_status(
                interaction_id=interaction_id,
                user_id="user-1",
                db=object(),
            )

    detail = exc_info.value.detail
    assert detail["code"] == "INTERACTION_STATUS_FAILED"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    assert detail["details"]["interaction_id"] == f"<redacted interaction_id; length={len(interaction_id)}>"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_research_stream_cancel_error_summarizes_exception_and_interaction_id(monkeypatch, caplog):
    error_text = "cancel failed with secret-token"
    interaction_id = "interaction-secret-token"
    _patch_research_dependencies(monkeypatch, manager=_FailingManager(RuntimeError(error_text)))

    with caplog.at_level(logging.ERROR, logger=research_stream.logger.name):
        with pytest.raises(HTTPException) as exc_info:
            await research_stream.cancel_streaming_research(
                interaction_id=interaction_id,
                user_id="user-1",
                db=object(),
            )

    detail = exc_info.value.detail
    assert detail["code"] == "INTERACTION_CANCEL_FAILED"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    assert detail["details"]["interaction_id"] == f"<redacted interaction_id; length={len(interaction_id)}>"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_research_stream_sse_error_event_is_summarized(monkeypatch, caplog):
    error_text = "stream existing failed with secret-token"
    _patch_research_dependencies(monkeypatch, manager=_FailingManager(RuntimeError(error_text)))

    with caplog.at_level(logging.ERROR, logger=research_stream.logger.name):
        response = await research_stream.stream_research_events(
            interaction_id="interaction-secret-token",
            last_event_id_header=None,
            last_event_id_query=None,
            include_input=False,
            user_id="user-1",
            db=object(),
        )
        payload = await _collect_streaming_response(response)

    assert "INTERACTION_STREAM_FAILED" in payload
    assert "Stream failed" in payload
    assert f"<redacted error; length={len(error_text)}>" in payload
    assert "secret-token" not in payload
    assert "secret-token" not in "\n".join(record.getMessage() for record in caplog.records)
    assert all(record.exc_info is None for record in caplog.records)
