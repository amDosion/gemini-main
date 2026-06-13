from __future__ import annotations

import asyncio
import logging
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.ai import interactions as interactions_router
from app.routers.tools import batch_jobs
from app.routers.tools import live_api as live_router
from app.routers.tools import table_analysis
from app.services.agent import adk_builtin_tools as adk_builtin_tools_module
from app.services.gemini.agent import adk_runner as adk_runner_module
from app.services.gemini.agent.adk_agent import ADKAgent
from app.services.gemini.agent.adk_runner import ADKRunner
from app.services.gemini.agent.interactions import InteractionsResource
from app.services.gemini.agent.live_api import LiveAPIHandler
from app.services.gemini.agent.memory_bank_service import VertexAiMemoryBankService
from app.services.gemini.agent.workflows import image_edit_workflow as image_workflow_module


def _log_text(records) -> str:
    return "\n".join(record.getMessage() for record in records)


async def _collect_async_generator(generator) -> list[dict]:
    return [item async for item in generator]


def test_adk_runner_run_errors_are_logged_as_summaries(monkeypatch, caplog) -> None:
    class FailingRunner:
        async def run_async(self, **kwargs):
            raise RuntimeError("run failed with secret-token")
            yield

    runner = object.__new__(ADKRunner)
    runner._adk_runner = FailingRunner()
    runner._ensure_adk_session = lambda **kwargs: asyncio.sleep(0)
    runner._build_new_message = lambda **kwargs: object()
    runner._build_run_config = lambda _run_config: None
    runner._temporary_google_api_key = lambda _google_api_key: nullcontext()

    session_id = "session-secret-token"
    with caplog.at_level(logging.ERROR, logger=adk_runner_module.logger.name):
        events = asyncio.run(
            _collect_async_generator(
                runner._run_adk_stream(
                    user_id="user-secret-token",
                    session_id=session_id,
                    input_data="prompt-secret-token",
                    input_message=None,
                    google_api_key=None,
                    run_config=None,
                    state_delta=None,
                    invocation_id=None,
                )
            )
        )

    assert events[0]["error"] == "run failed with secret-token"
    records = [record for record in caplog.records if record.name == adk_runner_module.logger.name]
    assert records
    log_text = _log_text(records)
    assert f"<redacted session_id; length={len(session_id)}>" in log_text
    assert "<redacted adk_run_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_adk_runner_live_errors_are_logged_as_summaries(monkeypatch, caplog) -> None:
    class FailingRunner:
        async def run_live(self, **kwargs):
            raise RuntimeError("live failed with secret-token")
            yield

    runner = object.__new__(ADKRunner)
    runner._adk_runner = FailingRunner()
    runner._LiveRequestQueueClass = lambda: object()
    runner._ensure_adk_session = lambda **kwargs: asyncio.sleep(0)
    runner._enqueue_live_requests = lambda **kwargs: None
    runner._build_run_config = lambda _run_config: None
    runner._temporary_google_api_key = lambda _google_api_key: nullcontext()

    session_id = "live-session-secret-token"
    with caplog.at_level(logging.ERROR, logger=adk_runner_module.logger.name):
        events = asyncio.run(
            _collect_async_generator(
                runner._run_adk_live_stream(
                    user_id="user-secret-token",
                    session_id=session_id,
                    input_data="prompt-secret-token",
                    live_requests=[],
                    google_api_key=None,
                    run_config=None,
                    close_queue=True,
                    max_events=None,
                )
            )
        )

    assert events[0]["error"] == "live failed with secret-token"
    records = [record for record in caplog.records if record.name == adk_runner_module.logger.name]
    assert records
    log_text = _log_text(records)
    assert f"<redacted session_id; length={len(session_id)}>" in log_text
    assert "<redacted adk_live_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_adk_agent_bidi_stream_logs_agent_and_error_as_summaries(monkeypatch, caplog) -> None:
    agent = object.__new__(ADKAgent)
    agent.name = "agent-secret-token"
    agent._adk_available = True
    agent._adk_agent = object()
    agent.query = lambda _input: (_ for _ in ()).throw(RuntimeError("bidi failed with secret-token"))

    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait({"input": "hello"})

    with caplog.at_level(logging.INFO, logger="app.services.gemini.agent.adk_agent"):
        event = asyncio.run(anext(agent.bidi_stream_query(queue)))

    assert event["error"] == "bidi failed with secret-token"
    records = [record for record in caplog.records if record.name == "app.services.gemini.agent.adk_agent"]
    assert records
    log_text = _log_text(records)
    assert "<redacted agent_name; length=" in log_text
    assert "<redacted bidi_stream_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_image_edit_workflow_errors_are_logged_as_summaries(monkeypatch, caplog) -> None:
    class FakeAgentLLMService:
        def __init__(self, *args, **kwargs):
            pass

    class FakeWorkflowEngine:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, *args, **kwargs):
            raise RuntimeError("image workflow failed with secret-token")

    image_url = "https://cdn.example.test/private/image.png?token=secret-token"
    edit_prompt = "replace background with secret-token"

    monkeypatch.setattr(image_workflow_module, "AgentLLMService", FakeAgentLLMService)
    monkeypatch.setattr(image_workflow_module, "WorkflowEngine", FakeWorkflowEngine)

    workflow = image_workflow_module.ImageEditWorkflow(db=object(), user_id="user-1")
    with caplog.at_level(logging.INFO, logger=image_workflow_module.logger.name):
        result = asyncio.run(
            workflow.execute(
                image_url=image_url,
                edit_prompt=edit_prompt,
                edit_mode="image-chat-edit",
            )
        )

    assert result["success"] is False
    assert result["input"]["image_url"] == image_url
    assert "secret-token" in result["error"]

    records = [record for record in caplog.records if record.name == image_workflow_module.logger.name]
    assert records
    log_text = _log_text(records)
    assert f"<redacted image_url; length={len(image_url)}>" in log_text
    assert f"<redacted edit_prompt; length={len(edit_prompt)}>" in log_text
    assert "<redacted workflow_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_live_api_handler_bidi_logs_user_agent_and_error_as_summaries(caplog) -> None:
    async def failing_stream_query(**kwargs):
        raise RuntimeError("live handler failed with secret-token")
        yield

    handler = object.__new__(LiveAPIHandler)
    handler.stream_query = failing_stream_query

    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait({"input": "hello", "agent_id": "agent-secret-token"})

    logger_name = "app.services.gemini.agent.live_api"
    with caplog.at_level(logging.INFO, logger=logger_name):
        event = asyncio.run(anext(handler.bidi_stream_query("user-secret-token", queue)))

    assert event["error"] == "live handler failed with secret-token"
    records = [record for record in caplog.records if record.name == logger_name]
    assert records
    log_text = _log_text(records)
    assert "<redacted user_id; length=" in log_text
    assert "<redacted agent_id; length=" in log_text
    assert "<redacted bidi_stream_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_live_api_router_query_logs_user_agent_and_error_as_summaries(monkeypatch, caplog) -> None:
    class FailingHandler:
        def __init__(self, db):
            pass

        async def query(self, **kwargs):
            raise RuntimeError("live router failed with secret-token")

    monkeypatch.setattr(live_router, "LiveAPIHandler", FailingHandler)

    with caplog.at_level(logging.ERROR, logger=live_router.logger.name):
        with pytest.raises(HTTPException):
            asyncio.run(
                live_router.query(
                    live_router.QueryRequest(input="hello", agent_id="agent-secret-token"),
                    user_id="user-secret-token",
                    db=object(),
                )
            )

    records = [record for record in caplog.records if record.name == live_router.logger.name]
    assert records
    log_text = _log_text(records)
    assert "<redacted user_id; length=" in log_text
    assert "<redacted agent_id; length=" in log_text
    assert "<redacted query_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_interactions_resource_create_logs_error_as_summary(caplog) -> None:
    class FailingInteractions:
        def create(self, **kwargs):
            raise RuntimeError("interaction create failed with secret-token")

    resource = InteractionsResource(client=SimpleNamespace(interactions=FailingInteractions()))

    logger_name = "app.services.gemini.agent.interactions"
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        with pytest.raises(RuntimeError):
            resource.create(input="prompt-secret-token", agent="agent-secret-token")

    records = [record for record in caplog.records if record.name == logger_name]
    assert records
    log_text = _log_text(records)
    assert "<redacted agent; length=" in log_text
    assert "<redacted create_interaction_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_interactions_router_get_logs_user_interaction_and_error_as_summaries(monkeypatch, caplog) -> None:
    class FailingCredentialsResolver:
        async def resolve(self, **kwargs):
            raise RuntimeError("credentials failed with secret-token")

    monkeypatch.setattr(interactions_router, "credentials_resolver", FailingCredentialsResolver())

    with caplog.at_level(logging.ERROR, logger=interactions_router.logger.name):
        with pytest.raises(HTTPException):
            asyncio.run(
                interactions_router.get_interaction(
                    interaction_id="interaction-secret-token",
                    user_id="user-secret-token",
                    db=object(),
                )
            )

    records = [record for record in caplog.records if record.name == interactions_router.logger.name]
    assert records
    log_text = _log_text(records)
    assert "<redacted user_id; length=" in log_text
    assert "<redacted interaction_id; length=" in log_text
    assert "<redacted get_interaction_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_memory_bank_vertex_search_logs_query_and_error_as_summaries(caplog) -> None:
    class FailingAdkService:
        async def search_memory(self, **kwargs):
            raise RuntimeError("memory search failed with secret-token")

    service = object.__new__(VertexAiMemoryBankService)
    service._get_or_create_memory_bank = (
        lambda _user_id, _memory_bank_id=None: asyncio.sleep(
            0,
            result=SimpleNamespace(id="bank-secret-token"),
        )
    )
    service._ensure_adk_service = lambda _memory_bank: FailingAdkService()
    service._resolve_memory_app_name = lambda _memory_bank, user_id: "app-secret-token"
    service._search_memory_db = lambda _user_id, _query, _memory_bank_id, _limit: asyncio.sleep(0, result=[])

    logger_name = "app.services.gemini.agent.memory_bank_service"
    with caplog.at_level(logging.ERROR, logger=logger_name):
        result = asyncio.run(
            service.search_memory(
                user_id="user-secret-token",
                query="query-secret-token",
                limit=3,
            )
        )

    assert result == []
    records = [record for record in caplog.records if record.name == logger_name]
    assert records
    log_text = _log_text(records)
    assert "<redacted user_id; length=" in log_text
    assert "<redacted memory_bank_id; length=" in log_text
    assert "<redacted query; length=" in log_text
    assert "<redacted vertex_memory_search_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_table_analysis_inline_logs_user_file_and_error_as_summaries(monkeypatch, caplog) -> None:
    def failing_analyze_inline_table_content(**kwargs):
        raise RuntimeError("table failed with secret-token")

    monkeypatch.setattr(
        table_analysis,
        "analyze_inline_table_content",
        failing_analyze_inline_table_content,
    )

    with caplog.at_level(logging.ERROR, logger=table_analysis.logger.name):
        with pytest.raises(HTTPException):
            asyncio.run(
                table_analysis.analyze_table_inline(
                    table_analysis.InlineTableAnalysisRequest(
                        file_name="table-secret-token.csv",
                        content="a,b\n1,2",
                    ),
                    user_id="user-secret-token",
                )
            )

    records = [record for record in caplog.records if record.name == table_analysis.logger.name]
    assert records
    log_text = _log_text(records)
    assert "<redacted user_id; length=" in log_text
    assert "<redacted file_name; length=" in log_text
    assert "<redacted inline_table_analysis_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_batch_job_progress_logs_user_job_and_error_as_summaries(monkeypatch, caplog) -> None:
    class FailingBatchJobOrchestrator:
        async def get_progress(self, **kwargs):
            raise RuntimeError("batch failed with secret-token")

    monkeypatch.setattr(batch_jobs, "_batch_job_orchestrator", FailingBatchJobOrchestrator())

    with caplog.at_level(logging.ERROR, logger=batch_jobs.logger.name):
        with pytest.raises(HTTPException):
            asyncio.run(
                batch_jobs.get_batch_job_progress(
                    job_id="job-secret-token",
                    user_id="user-secret-token",
                )
            )

    records = [record for record in caplog.records if record.name == batch_jobs.logger.name]
    assert records
    log_text = _log_text(records)
    assert "<redacted user_id; length=" in log_text
    assert "<redacted job_id; length=" in log_text
    assert "<redacted batch_progress_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_sheet_analyze_unexpected_error_logs_source_and_error_as_summaries(monkeypatch, caplog) -> None:
    class FakeTableAnalysisError(Exception):
        pass

    class FakeTableAnalysisModule:
        TableAnalysisError = FakeTableAnalysisError

        @staticmethod
        def analyze_table_bytes(*args, **kwargs):
            raise RuntimeError("sheet failed with secret-token")

        @staticmethod
        def export_table_analysis(**kwargs):
            return "# unused"

    monkeypatch.setattr(
        adk_builtin_tools_module,
        "_load_table_analysis_module",
        lambda: FakeTableAnalysisModule,
    )

    sheet_analyze = adk_builtin_tools_module.build_adk_builtin_tools()[0]
    with caplog.at_level(logging.WARNING, logger=adk_builtin_tools_module.logger.name):
        result = sheet_analyze(
            file_name="sheet-secret-token.csv",
            content="a,b\n1,2",
        )

    assert result["status"] == "failed"
    assert "secret-token" in result["error"]
    records = [record for record in caplog.records if record.name == adk_builtin_tools_module.logger.name]
    assert records
    log_text = _log_text(records)
    assert "<redacted source_type; length=" in log_text
    assert "<redacted source_ref; length=" in log_text
    assert "<redacted file_name; length=" in log_text
    assert "<redacted sheet_analyze_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)
