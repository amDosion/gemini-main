import logging
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware.case_conversion_middleware import CaseConversionMiddleware
from app.routers.ai import workflows
from app.routers.core import attachments
from app.services.common import attachment_continuity
from app.services.ollama.handlers.openai_compat_handler import OpenAICompatibleHandler
from app.services.ollama.ollama import OllamaService
from app.services.openai.video_generator import VideoGenerator as OpenAIVideoGenerator
from app.services.tongyi.virtual_tryon import TongyiVirtualTryOnService
from app.utils.log_sanitization import summarize_query_for_log, summarize_url_for_log


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row=None):
        self._row = row

    def query(self, _model):
        return _FakeQuery(self._row)

    def commit(self):
        return None


def test_summarize_url_counts_query_params_without_decoding_values():
    secret = "secret-token-" + ("x" * 10000)
    url = f"https://cdn.example.test/private/source.png?token={secret}&empty=&sig=abc#frag"

    summary = summarize_url_for_log(url)

    assert summary == "https://cdn.example.test path_len=19 query_params=3 fragment=yes"
    assert secret not in summary
    assert "token=" not in summary


def test_summarize_query_counts_params_without_decoding_values():
    secret = "secret-token-" + ("x" * 10000)
    query = f"apiKey={secret}&accessToken=abc&empty="

    summary = summarize_query_for_log(query)

    assert summary == f"query_params=3 length={len(query)}"
    assert secret not in summary
    assert "apiKey=" not in summary
    assert "accessToken=" not in summary


@pytest.mark.asyncio
async def test_auth_login_exception_log_summarizes_email(monkeypatch, caplog):
    from fastapi import HTTPException
    from app.routers.auth import auth as auth_router
    from app.services.common.auth_service import LoginRequest
    from starlette.requests import Request
    from starlette.responses import Response

    email = "private-user@example-mail.com"
    secret_error = f"database detail with {email}"

    def fail_login(*_args, **_kwargs):
        raise RuntimeError(secret_error)

    monkeypatch.setattr(auth_router.AuthService, "login", fail_login)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )

    with caplog.at_level(logging.ERROR, logger=auth_router.logger.name):
        with pytest.raises(HTTPException) as exc_info:
            await auth_router.login(
                LoginRequest(email=email, password="secret"),
                request,
                Response(),
                db=object(),
            )

    assert exc_info.value.status_code == 500
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert email not in log_text
    assert secret_error not in log_text
    assert "<redacted email; length=" in log_text
    assert "<redacted error; type=RuntimeError; length=" in log_text


def test_task_decomposer_json_error_logs_response_summary(caplog):
    from app.services.gemini.agent.task_decomposer import SmartTaskDecomposer

    response = "not json with private task text and secret-token"
    decomposer = SmartTaskDecomposer(google_service=object())

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.task_decomposer"):
        with pytest.raises(ValueError):
            decomposer._parse_subtasks(response, max_subtasks=10)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted decomposer_response; length={len(response)}>" in log_text
    assert response not in log_text
    assert "secret-token" not in log_text
    assert "private task text" not in log_text


@pytest.mark.asyncio
async def test_task_decomposer_decompose_logs_task_summary(monkeypatch, caplog):
    from app.services.gemini.agent.task_decomposer import SmartTaskDecomposer

    task = "private user task with secret-token"
    decomposer = SmartTaskDecomposer(google_service=object())

    async def fake_call_llm(_prompt):
        return '{"subtasks":[{"description":"safe","required_capabilities":[]}]}'

    monkeypatch.setattr(decomposer, "_call_llm", fake_call_llm)

    with caplog.at_level(logging.INFO, logger="app.services.gemini.agent.task_decomposer"):
        subtasks = await decomposer.decompose_task(
            task,
            available_agents=[],
            max_subtasks=1,
        )

    assert len(subtasks) == 1
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted task; length={len(task)}>" in log_text
    assert task not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_task_decomposer_llm_error_log_summarizes_without_exc_info(caplog):
    from app.services.gemini.agent.task_decomposer import SmartTaskDecomposer

    class FakeGoogleService:
        async def chat(self, **_kwargs):
            raise RuntimeError("provider echoed secret-token")

    decomposer = SmartTaskDecomposer(google_service=FakeGoogleService())

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.task_decomposer"):
        with pytest.raises(RuntimeError):
            await decomposer._call_llm("private prompt with secret-token")

    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.task_decomposer"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted llm_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_coordinator_agent_logs_task_summary(monkeypatch, caplog):
    from app.services.gemini.agent.coordinator_agent import CoordinatorAgent, Intent

    task = "private coordinator task with secret-token"

    class FakeRegistry:
        async def list_agents(self, *, user_id):
            return []

    coordinator = CoordinatorAgent(
        google_service=object(),
        agent_registry=FakeRegistry(),
    )

    async def fake_analyze_intent(_task, _context):
        return Intent(intent_type="general", confidence=0.5)

    monkeypatch.setattr(coordinator, "_analyze_intent", fake_analyze_intent)

    with caplog.at_level(logging.INFO, logger="app.services.gemini.agent.coordinator_agent"):
        result = await coordinator.coordinate("user-1", task)

    assert result["success"] is False
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted task; length={len(task)}>" in log_text
    assert task not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_orchestrator_no_match_log_summarizes_subtask(caplog):
    from app.services.gemini.agent.orchestrator import Orchestrator
    from app.services.gemini.agent.task_decomposer import SubTask

    subtask_text = "private subtask with secret-token"
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.use_smart_decomposition = True
    orchestrator.agent_matcher = SimpleNamespace(
        match_agent=lambda **_kwargs: None,
    )

    with caplog.at_level(logging.WARNING, logger="app.services.gemini.agent.orchestrator"):
        results = await orchestrator._execute_sequential(
            subtasks=[SubTask(id="s1", description=subtask_text)],
            user_id="user-1",
            selected_agents=[{"id": "agent-1"}],
        )

    assert results[0]["error"] == "No suitable agent found"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted subtask; length={len(subtask_text)}>" in log_text
    assert subtask_text not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_base_agent_executor_llm_error_log_summarizes_without_exc_info(caplog):
    from app.services.gemini.agent.base_agent_executor import BaseAgentExecutor

    class FakeGoogleService:
        async def chat(self, **_kwargs):
            raise RuntimeError("provider echoed secret-token")

    executor = BaseAgentExecutor(
        agent_registry=object(),
        google_service=FakeGoogleService(),
    )

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.base_agent_executor"):
        with pytest.raises(RuntimeError):
            await executor._execute_with_llm(
                agent_name="agent-1",
                agent_id="agent-1",
                task="private task with secret-token",
                agent_info={},
            )

    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.base_agent_executor"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted llm_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_sequential_agent_error_log_summarizes_without_exc_info(caplog):
    from app.services.gemini.agent.sequential_agent import SequentialAgent

    class FakeExecutor:
        async def execute_agent(self, **_kwargs):
            raise RuntimeError("step echoed secret-token")

    agent = SequentialAgent(
        name="seq",
        sub_agents=[{"agent_id": "agent-1", "agent_name": "Agent One"}],
        agent_registry=object(),
    )
    agent._executor = FakeExecutor()

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.sequential_agent"):
        result = await agent.execute("user-1", "private input secret-token")

    assert result["success"] is False
    assert "secret-token" in result["session_state"]["error"]
    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.sequential_agent"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted step_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_parallel_agent_error_log_summarizes_without_exc_info(monkeypatch, caplog):
    from app.services.gemini.agent.parallel_agent import ParallelAgent

    async def fake_execute_task_with_timeout(**_kwargs):
        raise RuntimeError("parallel task echoed secret-token")

    agent = ParallelAgent(
        name="parallel",
        sub_agents=[{"agent_id": "agent-1", "agent_name": "Agent One"}],
        agent_registry=object(),
    )
    monkeypatch.setattr(agent, "_execute_task_with_timeout", fake_execute_task_with_timeout)

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.parallel_agent"):
        result = await agent.execute("user-1", "private input secret-token")

    assert result["success"] is False
    assert "secret-token" in result["errors"]["task_0"]
    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.parallel_agent"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted task_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_case_conversion_debug_log_summarizes_query_without_values(caplog):
    app = FastAPI()
    app.add_middleware(CaseConversionMiddleware)

    @app.get("/echo")
    async def echo(request: Request):
        return {"keys": sorted(request.query_params.keys())}

    client = TestClient(app)
    query = "apiKey=secret-token&accessToken=abc&userId=123"

    with caplog.at_level(logging.DEBUG, logger="app.middleware.case_conversion_middleware"):
        response = client.get(f"/echo?{query}")

    assert response.status_code == 200
    assert response.json()["keys"] == ["access_token", "api_key", "user_id"]
    log_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "app.middleware.case_conversion_middleware"
    )
    assert "[CaseConversion] Query converted" in log_text
    assert "query_params=3" in log_text
    assert "secret-token" not in log_text
    assert "apiKey=" not in log_text
    assert "accessToken=" not in log_text


def test_startup_tasks_do_not_log_raw_exception_text():
    from app.core import startup_tasks

    source = startup_tasks.__loader__.get_source(startup_tasks.__name__)
    assert source is not None
    assert "traceback.print_exc(" not in source
    assert not re.search(r"logger\.(?:warning|error)\(f[\"'].*\{e\}", source)


@pytest.mark.asyncio
async def test_workflow_persistence_log_labels_summarize_urls(monkeypatch):
    image_url = "https://cdn.example.test/private/source.png?token=secret-token#frag"
    video_url = "https://cdn.example.test/private/result.mp4?token=video-secret#frag"
    calls = []

    async def fake_persist(_attachment_service, **kwargs):
        calls.append(kwargs)
        return {
            "display_url": f"/api/temp-images/{len(calls)}",
            "mime_type": kwargs.get("mime_type"),
            "filename": kwargs.get("filename") or "",
        }

    monkeypatch.setattr(workflows, "safe_persist_ai_result", fake_persist)
    monkeypatch.setattr(
        workflows,
        "safe_persist_video_last_frame_derivative",
        lambda *args, **kwargs: None,
    )
    db = _FakeDB(SimpleNamespace(storage_id="storage-1"))

    await workflows._persist_workflow_result_images(
        db,
        execution_id="exec-1",
        user_id="u1",
        result_payload={"images": [image_url]},
    )
    await workflows._persist_workflow_result_media(
        db,
        execution_id="exec-1",
        user_id="u1",
        result_payload={"videoUrl": video_url},
        media_kind="video",
    )

    labels = "\n".join(call["log_label"] for call in calls)
    assert "https://cdn.example.test path_len=19 query_params=1 fragment=yes" in labels
    assert "https://cdn.example.test path_len=19 query_params=1 fragment=yes" in labels
    assert image_url not in labels
    assert video_url not in labels
    assert "secret-token" not in labels
    assert "video-secret" not in labels


@pytest.mark.asyncio
async def test_startup_redis_pool_failure_logs_summary_without_traceback(
    monkeypatch,
    caplog,
    capsys,
):
    from app.core import startup_tasks
    from app.services.common.redis_queue_service import GlobalRedisConnectionPool

    secret = "startup-redis-secret"

    class FailingRedisPool:
        async def initialize(self):
            raise RuntimeError(f"redis init failed {secret}")

    monkeypatch.setattr(
        GlobalRedisConnectionPool,
        "get_instance",
        classmethod(lambda cls: FailingRedisPool()),
    )

    with caplog.at_level(logging.ERROR, logger=startup_tasks.logger.name):
        redis_available = await startup_tasks.initialize_redis_pool(
            {"error": "[ERR]", "success": "[OK]", "warning": "[WARN]", "info": "[INFO]"}
        )

    captured = capsys.readouterr()
    log_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == startup_tasks.logger.name
    )
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert secret not in captured.out
    assert secret not in captured.err
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    assert all(record.exc_info is None for record in caplog.records)
    assert redis_available is False


@pytest.mark.asyncio
async def test_startup_skips_embedded_worker_pool_when_redis_unavailable(
    monkeypatch,
    caplog,
):
    from app.core import config as config_module
    from app.core import startup_tasks

    class WorkerPoolThatMustNotStart:
        async def start(self):
            raise AssertionError("worker pool must not start without Redis")

    monkeypatch.setattr(config_module.settings, "worker_mode", "embedded", raising=False)

    with caplog.at_level(logging.WARNING, logger=startup_tasks.logger.name):
        worker_mode = await startup_tasks.start_worker_pool(
            WorkerPoolThatMustNotStart(),
            True,
            {"error": "[ERR]", "success": "[OK]", "warning": "[WARN]", "info": "[INFO]"},
            redis_available=False,
        )

    assert worker_mode == "unavailable"
    log_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == startup_tasks.logger.name
    )
    assert "Redis is unavailable; skipping embedded upload worker pool startup" in log_text


@pytest.mark.asyncio
async def test_startup_worker_pool_failure_logs_summary_without_traceback(
    monkeypatch,
    caplog,
    capsys,
):
    from app.core import config as config_module
    from app.core import startup_tasks

    secret = "startup-worker-secret"

    class FailingWorkerPool:
        async def start(self):
            raise RuntimeError(f"worker start failed {secret}")

    monkeypatch.setattr(config_module.settings, "worker_mode", "embedded", raising=False)

    with caplog.at_level(logging.ERROR, logger=startup_tasks.logger.name):
        worker_mode = await startup_tasks.start_worker_pool(
            FailingWorkerPool(),
            True,
            {"error": "[ERR]", "success": "[OK]", "warning": "[WARN]", "info": "[INFO]"},
        )

    captured = capsys.readouterr()
    log_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == startup_tasks.logger.name
    )
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert secret not in captured.out
    assert secret not in captured.err
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    assert all(record.exc_info is None for record in caplog.records)
    assert worker_mode == "unavailable"


@pytest.mark.asyncio
async def test_startup_worker_pool_fallback_failure_logs_summary(
    monkeypatch,
    caplog,
):
    from app.core import config as config_module
    from app.core import startup_tasks

    secret = "startup-worker-fallback-secret"

    class FailingWorkerPool:
        async def start(self):
            raise RuntimeError(f"fallback worker start failed {secret}")

    monkeypatch.setattr(config_module.settings, "worker_mode", "unexpected", raising=False)

    with caplog.at_level(logging.ERROR, logger=startup_tasks.logger.name):
        worker_mode = await startup_tasks.start_worker_pool(
            FailingWorkerPool(),
            True,
            {"error": "[ERR]", "success": "[OK]", "warning": "[WARN]", "info": "[INFO]"},
        )

    log_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == startup_tasks.logger.name
    )
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert all(record.exc_info is None for record in caplog.records)
    assert worker_mode == "unavailable"


@pytest.mark.asyncio
async def test_attachment_continuity_logs_summarized_cloud_url(caplog):
    url = "https://cdn.example.test/private/source.png?token=secret-token#frag"
    attachment = SimpleNamespace(
        id="att-1",
        message_id="msg-1",
        session_id="s1",
        user_id="u1",
        name="source.png",
        mime_type="image/png",
        size=123,
        url=url,
        temp_url=None,
        upload_status="completed",
    )
    svc = SimpleNamespace(
        db=_FakeDB(attachment),
        _find_attachment_by_url=lambda _url, _messages: "att-1",
        _find_latest_uploaded_image=lambda _session_id, _user_id: None,
        _is_persistent_storage_url=lambda _url: True,
    )

    with caplog.at_level(logging.INFO, logger=attachment_continuity.logger.name):
        result = await attachment_continuity.resolve_continuity_attachment(
            svc,
            active_image_url=url,
            session_id="s1",
            user_id="u1",
            messages=[],
        )

    assert result is not None
    assert result["url"] == url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://cdn.example.test path_len=19 query_params=1 fragment=yes" in log_text
    assert url not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_openai_video_missing_local_media_error_summarizes_url():
    url = "/api/storage/local-files/private/source.mp4?token=secret-token"
    generator = OpenAIVideoGenerator(api_key="test-key")

    with pytest.raises(ValueError) as exc_info:
        await generator._load_media_bytes({"url": url}, "video/mp4")

    error_text = str(exc_info.value)
    assert f"relative reference; length={len(url)}" in error_text
    assert url not in error_text
    assert "secret-token" not in error_text


class _FakeImageInlineData:
    data = b"edited-image"
    mime_type = "image/png"


class _FakeImagePart:
    inline_data = _FakeImageInlineData()
    text = None
    thought = False
    function_call = None
    function_response = None


class _FakeImageCandidate:
    def __init__(self):
        self.content = SimpleNamespace(parts=[_FakeImagePart()])


class _FakeImageResponse:
    parts = []
    candidates = [_FakeImageCandidate()]


class _FakeImageChat:
    async def send_message(self, *args, **kwargs):
        return _FakeImageResponse()


class _FakeImageChatManager:
    def __init__(self, chat=None):
        self.chat = chat or _FakeImageChat()

    def get_chat_object_from_cache(self, _chat_id):
        return self.chat


@pytest.mark.asyncio
async def test_conversational_image_edit_local_file_log_summarizes_url(
    monkeypatch,
    tmp_path,
    caplog,
):
    from app.services.gemini.geminiapi import conversational_image_edit_service as edit_module
    from app.services.storage import local_provider

    url = "/api/storage/local-files/private/source.png?token=secret-token"
    local_image = tmp_path / "source.png"
    local_image.write_bytes(b"source-image")
    monkeypatch.setattr(
        local_provider,
        "resolve_local_public_file_path",
        lambda _url: local_image,
    )
    service = edit_module.ConversationalImageEditService(
        chat_session_manager=_FakeImageChatManager(),
        file_handler=object(),
    )

    with caplog.at_level(logging.INFO, logger=edit_module.logger.name):
        result = await service._send_edit_message_internal(
            chat_id="chat-1",
            prompt="make it brighter",
            reference_images=[{"url": url, "mime_type": "image/png"}],
            config={},
            chat_session=SimpleNamespace(model_name="gemini-3.1-flash-image-preview", config_json=None),
            model_name="gemini-3.1-flash-image-preview",
            should_include_image=True,
            client=object(),
        )

    assert result["images"][0]["mime_type"] == "image/png"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"relative reference; length={len(url)}" in log_text
    assert url not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_conversational_image_edit_local_file_missing_error_summarizes_url(
    monkeypatch,
    tmp_path,
    caplog,
):
    from app.services.gemini.geminiapi import conversational_image_edit_service as edit_module
    from app.services.storage import local_provider

    url = "/api/storage/local-files/private/missing.png?token=secret-token"
    monkeypatch.setattr(
        local_provider,
        "resolve_local_public_file_path",
        lambda _url: tmp_path / "missing.png",
    )
    service = edit_module.ConversationalImageEditService(
        chat_session_manager=_FakeImageChatManager(),
        file_handler=object(),
    )

    with caplog.at_level(logging.ERROR, logger=edit_module.logger.name):
        with pytest.raises(ValueError) as exc_info:
            await service._send_edit_message_internal(
                chat_id="chat-1",
                prompt="make it brighter",
                reference_images=[{"url": url, "mime_type": "image/png"}],
                config={},
                chat_session=SimpleNamespace(
                    model_name="gemini-3.1-flash-image-preview",
                    config_json=None,
                ),
                model_name="gemini-3.1-flash-image-preview",
                should_include_image=True,
                client=object(),
            )

    error_text = str(exc_info.value)
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"relative reference; length={len(url)}" in error_text
    assert f"relative reference; length={len(url)}" in log_text
    assert url not in error_text
    assert url not in log_text
    assert "secret-token" not in error_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_conversational_image_edit_http_download_error_summarizes_url(
    monkeypatch,
    caplog,
):
    from app.services.gemini.geminiapi import conversational_image_edit_service as edit_module

    url = "https://cdn.example.test/private/source.png?token=secret-token#frag"
    service = edit_module.ConversationalImageEditService(
        chat_session_manager=_FakeImageChatManager(),
        file_handler=object(),
    )

    async def fake_download_http_image_guarded(_url, _fallback_mime):
        raise RuntimeError(f"download failed for {_url}")

    monkeypatch.setattr(
        service,
        "_download_http_image_guarded",
        fake_download_http_image_guarded,
    )

    with caplog.at_level(logging.ERROR, logger=edit_module.logger.name):
        with pytest.raises(ValueError) as exc_info:
            await service._send_edit_message_internal(
                chat_id="chat-1",
                prompt="make it brighter",
                reference_images=[{"url": url, "mime_type": "image/png"}],
                config={},
                chat_session=SimpleNamespace(
                    model_name="gemini-3.1-flash-image-preview",
                    config_json=None,
                ),
                model_name="gemini-3.1-flash-image-preview",
                should_include_image=True,
                client=object(),
            )

    error_text = str(exc_info.value)
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    expected_summary = "https://cdn.example.test path_len=19 query_params=1 fragment=yes"
    assert expected_summary in error_text
    assert expected_summary in log_text
    assert url not in error_text
    assert url not in log_text
    assert "secret-token" not in error_text
    assert "secret-token" not in log_text


def test_ollama_initialization_logs_summarized_base_urls(caplog):
    base_url = "https://ollama.example.test/private-token-path"

    with caplog.at_level(logging.INFO):
        service = OllamaService(api_key="test-key", api_url=base_url)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert service.openai_handler.base_url == "https://ollama.example.test/private-token-path/v1"
    assert service.native_handler.base_url == "https://ollama.example.test/private-token-path"
    assert "private-token-path" not in log_text
    assert "https://ollama.example.test path_len=" in log_text


class _FakeOllamaCompletions:
    def __init__(self, error):
        self.error = error

    async def create(self, **kwargs):
        raise self.error


class _FakeOllamaChat:
    def __init__(self, error):
        self.completions = _FakeOllamaCompletions(error)


class _FakeOllamaChatClient:
    def __init__(self, error):
        self.chat = _FakeOllamaChat(error)


async def _collect_ollama_stream(agen):
    return [chunk async for chunk in agen]


@pytest.mark.asyncio
async def test_ollama_openai_compat_chat_error_log_is_summarized(caplog):
    error_text = "ollama chat failed with secret-token"
    handler = OpenAICompatibleHandler(api_key="test-key", base_url="https://ollama.example.test/v1")
    handler.client = _FakeOllamaChatClient(RuntimeError(error_text))

    with caplog.at_level(logging.ERROR, logger="app.services.ollama.handlers.openai_compat_handler"):
        with pytest.raises(RuntimeError, match="ollama chat failed"):
            await handler.chat([{"role": "user", "content": "private prompt"}], "llama3")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_ollama_openai_compat_stream_error_log_and_chunk_are_summarized(caplog):
    error_text = "ollama stream failed with secret-token"
    handler = OpenAICompatibleHandler(api_key="test-key", base_url="https://ollama.example.test/v1")
    handler.client = _FakeOllamaChatClient(RuntimeError(error_text))

    with caplog.at_level(logging.ERROR, logger="app.services.ollama.handlers.openai_compat_handler"):
        chunks = await _collect_ollama_stream(
            handler.stream_chat([{"role": "user", "content": "private prompt"}], "llama3")
        )

    assert chunks[0]["chunk_type"] == "error"
    assert chunks[0]["error"] == "Ollama stream chat failed"
    assert chunks[1]["chunk_type"] == "done"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted error; length={len(error_text)}>" in log_text
    assert error_text not in log_text
    assert "secret-token" not in log_text
    assert "private prompt" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


class _FailingOllamaNativeHandler:
    async def get_available_models_detailed(self):
        raise RuntimeError("ollama models failed with secret-token")


@pytest.mark.asyncio
async def test_ollama_service_model_failure_log_is_summarized(caplog):
    service = OllamaService(api_key="test-key", api_url="https://ollama.example.test")
    service.native_handler = _FailingOllamaNativeHandler()

    with caplog.at_level(logging.WARNING, logger="app.services.ollama.ollama"):
        models = await service.get_available_models()

    assert models == []
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "<redacted error; length=38>" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_tongyi_tryon_missing_local_image_error_summarizes_url():
    url = "/api/storage/local-files/private/person.png?token=secret-token"
    service = TongyiVirtualTryOnService(api_key="test-key")

    with pytest.raises(RuntimeError) as exc_info:
        await service._ensure_provider_url(url, model="aitryon-plus")

    error_text = str(exc_info.value)
    assert f"relative reference; length={len(url)}" in error_text
    assert url not in error_text
    assert "secret-token" not in error_text


@pytest.mark.asyncio
async def test_temp_image_redirect_logs_summarized_cloud_url(caplog):
    url = "https://cdn.example.test/private/source.png?token=secret-token#frag"
    attachment = SimpleNamespace(
        id="att-1",
        user_id="u1",
        temp_url=None,
        url=url,
        upload_status="completed",
        mime_type="image/png",
        google_file_uri=None,
        file_uri=None,
        gcs_uri=None,
    )
    request = SimpleNamespace(headers={}, cookies={})

    with caplog.at_level(logging.INFO, logger=attachments.logger.name):
        response = await attachments.get_temp_image(
            "att-1",
            request=request,
            no_redirect=False,
            db=_FakeDB(attachment),
            current_user="u1",
        )

    assert response.status_code == 307
    assert response.headers["location"] == url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://cdn.example.test path_len=19 query_params=1 fragment=yes" in log_text
    assert url not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_storage_upload_task_logs_summarized_signed_urls(monkeypatch, tmp_path, caplog):
    from app.routers.storage import storage as storage_router

    source_url = "https://source.example.com/input.png?token=secret-source-token&safe=1"
    final_url = "https://redirect.example.com/final.png?sig=secret-final-sig&safe=1#frag"
    target_url = "https://cdn.example.com/uploaded.png?signature=secret-target-sig&safe=1"

    task = SimpleNamespace(
        id="task-log-router",
        storage_id="storage-1",
        session_id=None,
        message_id=None,
        attachment_id=None,
        filename="source.png",
        source_file_path=None,
        source_url=source_url,
        status="pending",
        error_message=None,
        target_url=None,
        completed_at=None,
    )

    class FakeQuery:
        def filter(self, *_args):
            return self

        def first(self):
            return task

    class FakeSession:
        def query(self, _model):
            return FakeQuery()

        def commit(self):
            return None

        def close(self):
            return None

    class FakeResponse:
        content = b"image"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class FakeStorageManager:
        def __init__(self, *_args, **_kwargs):
            pass

        async def upload_file(self, **_kwargs):
            return {"success": True, "url": target_url}

    async def fake_bump_storage_revision(*_args):
        return 1

    monkeypatch.setattr(storage_router, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(storage_router, "StorageManager", FakeStorageManager)
    monkeypatch.setattr(storage_router, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(storage_router, "get_temp_dir_relative", lambda: "temp")
    monkeypatch.setattr(storage_router, "resolve_upload_task_user_id", lambda *_args: "user-1")
    monkeypatch.setattr(storage_router, "_bump_storage_revision", fake_bump_storage_revision)
    monkeypatch.setattr(storage_router, "_validate_outbound_http_url", lambda url: url)
    monkeypatch.setattr(storage_router, "_ensure_client_pinned", lambda _client: None)
    monkeypatch.setattr(storage_router.httpx, "AsyncClient", FakeAsyncClient)

    async def fake_redirect_guard(_client, url):
        assert url == source_url
        return FakeResponse(), final_url

    monkeypatch.setattr(storage_router, "_safe_get_with_redirect_guard", fake_redirect_guard)

    with caplog.at_level(logging.INFO, logger=storage_router.logger.name):
        await storage_router.process_upload_task("task-log-router")

    assert task.status == "completed"
    assert task.target_url == target_url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-source-token" not in log_text
    assert "secret-final-sig" not in log_text
    assert "secret-target-sig" not in log_text
    assert "下载图片: https://source.example.com path_len=10 query_params=2 fragment=no" in log_text
    assert "下载完成（最终URL）: https://redirect.example.com path_len=10 query_params=2 fragment=yes" in log_text
    assert "上传成功: https://cdn.example.com path_len=13 query_params=2 fragment=no" in log_text


@pytest.mark.asyncio
async def test_storage_attachment_update_logs_summarized_signed_url(caplog):
    from app.routers.storage import storage as storage_router

    signed_url = "https://cdn.example.com/final.png?token=secret-attachment-token&safe=1#frag"
    session = SimpleNamespace(id="session-1", user_id="user-1")
    attachment = SimpleNamespace(
        id="att-1",
        message_id="msg-1",
        session_id="session-1",
        user_id="user-1",
        url=None,
        upload_status="pending",
        temp_url="blob:temp",
    )

    class FakeQuery:
        def __init__(self, row):
            self._row = row

        def filter(self, *_args):
            return self

        def first(self):
            return self._row

    class FakeSession:
        def __init__(self):
            self.commits = 0

        def query(self, model):
            if model.__name__ == "ChatSession":
                return FakeQuery(session)
            if model.__name__ == "MessageAttachment":
                return FakeQuery(attachment)
            return FakeQuery(None)

        def expire_all(self):
            return None

        def commit(self):
            self.commits += 1

    db = FakeSession()

    with caplog.at_level(logging.INFO, logger=storage_router.logger.name):
        await storage_router.update_session_attachment_url(
            db,
            session_id="session-1",
            message_id="msg-1",
            attachment_id="att-1",
            url=signed_url,
            expected_user_id="user-1",
            max_retries=1,
            retry_delay=0,
        )

    assert attachment.url == signed_url
    assert attachment.upload_status == "completed"
    assert attachment.temp_url is None
    assert db.commits == 1
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "附件表已更新: att-1, URL: https://cdn.example.com path_len=10 query_params=2 fragment=yes" in log_text
    assert signed_url not in log_text
    assert "secret-attachment-token" not in log_text


@pytest.mark.asyncio
async def test_storage_attachment_update_error_logs_summary_without_traceback(caplog, capsys):
    from app.routers.storage import storage as storage_router

    secret = "secret-attachment-error-token"
    session = SimpleNamespace(id="session-1", user_id="user-1")
    attachment = SimpleNamespace(
        id="att-1",
        message_id="msg-1",
        session_id="session-1",
        user_id="user-1",
        url=None,
        upload_status="pending",
        temp_url="blob:temp",
    )

    class FakeQuery:
        def __init__(self, row):
            self._row = row

        def filter(self, *_args):
            return self

        def first(self):
            return self._row

    class FakeSession:
        def query(self, model):
            if model.__name__ == "ChatSession":
                return FakeQuery(session)
            if model.__name__ == "MessageAttachment":
                return FakeQuery(attachment)
            return FakeQuery(None)

        def expire_all(self):
            return None

        def commit(self):
            raise RuntimeError(f"attachment update failed {secret}")

    with caplog.at_level(logging.ERROR, logger=storage_router.logger.name):
        await storage_router.update_session_attachment_url(
            FakeSession(),
            session_id="session-1",
            message_id="msg-1",
            attachment_id="att-1",
            url="https://cdn.example.com/final.png?token=secret-url-token",
            expected_user_id="user-1",
            max_retries=1,
            retry_delay=0,
        )

    captured = capsys.readouterr()
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in log_text
    assert "secret-url-token" not in log_text
    assert "Traceback" not in log_text
    assert "<redacted error; length=" in log_text
    assert secret not in captured.err
    assert "Traceback" not in captured.err


def test_tongyi_dashscope_sync_upload_logs_summarized_oss_url(monkeypatch, caplog):
    from app.services.tongyi import file_upload

    oss_url = "oss://dashscope-private/secret/path/object.png?token=secret-oss-token"

    monkeypatch.setattr(
        file_upload,
        "_get_upload_policy",
        lambda *_args, **_kwargs: (True, {"unused": True}, None),
    )
    monkeypatch.setattr(
        file_upload,
        "_upload_to_oss",
        lambda *_args, **_kwargs: (True, oss_url, None),
    )

    with caplog.at_level(logging.INFO, logger=file_upload.logger.name):
        result = file_upload.upload_bytes_to_dashscope(b"image", "image.png", "api-key")

    assert result.success is True
    assert result.oss_url == oss_url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "oss reference; length=" in log_text
    assert oss_url not in log_text
    assert "secret-oss-token" not in log_text


@pytest.mark.asyncio
async def test_tongyi_dashscope_async_upload_logs_summarized_oss_url(monkeypatch, caplog):
    from app.services.tongyi import file_upload

    oss_url = "oss://dashscope-private/secret/path/object.png?token=secret-async-oss-token"

    async def fake_get_upload_policy(*_args, **_kwargs):
        return True, {"unused": True}, None

    async def fake_upload_to_oss(*_args, **_kwargs):
        return True, oss_url, None

    monkeypatch.setattr(file_upload, "_get_upload_policy_async", fake_get_upload_policy)
    monkeypatch.setattr(file_upload, "_upload_to_oss_async", fake_upload_to_oss)

    with caplog.at_level(logging.INFO, logger=file_upload.logger.name):
        result = await file_upload.upload_bytes_to_dashscope_async(b"image", "image.png", "api-key")

    assert result.success is True
    assert result.oss_url == oss_url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "oss reference; length=" in log_text
    assert oss_url not in log_text
    assert "secret-async-oss-token" not in log_text


def test_tongyi_outpainting_sync_poll_logs_summarized_output_url(monkeypatch, caplog):
    from app.services.tongyi import image_expand

    output_url = "https://dashscope.example.com/out.png?token=secret-outpaint-token&safe=1#frag"

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "output": {
                    "task_status": "SUCCEEDED",
                    "output_image_url": output_url,
                }
            }

    monkeypatch.setattr(image_expand.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(image_expand.requests, "get", lambda *_args, **_kwargs: FakeResponse())

    with caplog.at_level(logging.INFO, logger=image_expand.logger.name):
        result = image_expand.ImageExpandService().poll_task("task-1", "api-key", max_retries=1)

    assert result.success is True
    assert result.output_url == output_url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "任务成功: https://dashscope.example.com path_len=8 query_params=2 fragment=yes" in log_text
    assert output_url not in log_text
    assert "secret-outpaint-token" not in log_text


@pytest.mark.asyncio
async def test_tongyi_outpainting_async_poll_logs_summarized_output_url(monkeypatch, caplog):
    from app.services.tongyi import image_expand

    output_url = "https://dashscope.example.com/out.png?token=secret-async-outpaint-token&safe=1#frag"

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "output": {
                    "task_status": "SUCCEEDED",
                    "output_image_url": output_url,
                }
            }

    class FakeClient:
        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    async def fake_sleep(_seconds):
        return None

    async def fake_get_async_http_client():
        return FakeClient()

    monkeypatch.setattr(image_expand.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(image_expand, "_get_async_http_client", fake_get_async_http_client)

    with caplog.at_level(logging.INFO, logger=image_expand.logger.name):
        result = await image_expand.ImageExpandService().poll_task_async(
            "task-1",
            "api-key",
            max_retries=1,
        )

    assert result.success is True
    assert result.output_url == output_url
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "任务成功: https://dashscope.example.com path_len=8 query_params=2 fragment=yes" in log_text
    assert output_url not in log_text
    assert "secret-async-outpaint-token" not in log_text
