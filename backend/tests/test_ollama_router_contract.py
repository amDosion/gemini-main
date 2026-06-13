from __future__ import annotations

import logging
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.models import ollama_models


class FakeOllamaService:
    instances = []
    list_error = None
    info_error = None
    delete_error = None
    pull_error = None

    def __init__(self, *, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url
        self.closed = False
        FakeOllamaService.instances.append(self)

    async def get_available_models_detailed(self):
        if FakeOllamaService.list_error is not None:
            raise FakeOllamaService.list_error
        return [
            {
                "name": "llama3:latest",
                "size": 123,
            }
        ]

    async def get_model_info(self, name: str):
        if FakeOllamaService.info_error is not None:
            raise FakeOllamaService.info_error
        assert name == "llama3:latest"
        return SimpleNamespace(
            modelfile=None,
            parameters="",
            template="",
            details={},
            model_info={"general.architecture": "llama"},
            capabilities=SimpleNamespace(
                supports_vision=True,
                supports_tools=False,
                supports_thinking=True,
            ),
        )

    async def pull_model(self, model: str):
        if FakeOllamaService.pull_error is not None:
            raise FakeOllamaService.pull_error
        assert model == "llama3:latest"
        yield {"status": "pulling", "completed": 1}

    async def delete_model(self, name: str):
        if FakeOllamaService.delete_error is not None:
            raise FakeOllamaService.delete_error
        assert name == "llama3:latest"
        return True

    async def close(self):
        self.closed = True


def _client(monkeypatch, *, reject_url: bool = False) -> TestClient:
    FakeOllamaService.instances = []
    FakeOllamaService.list_error = None
    FakeOllamaService.info_error = None
    FakeOllamaService.delete_error = None
    FakeOllamaService.pull_error = None
    app = FastAPI()
    app.include_router(ollama_models.router)
    monkeypatch.setattr(ollama_models, "OllamaService", FakeOllamaService)

    def validate(provider: str, base_url: str) -> str:
        assert provider == "ollama"
        if reject_url:
            raise ollama_models.UnsafeURLError("blocked")
        return base_url

    monkeypatch.setattr(
        ollama_models.ProviderFactory,
        "_validate_provider_api_url",
        staticmethod(validate),
    )
    return TestClient(app)


def test_list_models_uses_header_api_key_and_tolerates_sparse_ollama_items(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get(
            "/api/ollama/models",
            params={"base_url": "https://ollama.example.test"},
            headers={"X-Ollama-Api-Key": "secret"},
        )

    assert response.status_code == 200
    assert FakeOllamaService.instances[0].api_key == "secret"
    assert FakeOllamaService.instances[0].api_url == "https://ollama.example.test"
    assert FakeOllamaService.instances[0].closed is True
    assert response.json()["models"] == [
        {
            "name": "llama3:latest",
            "model": "",
            "size": 123,
            "digest": "",
            "modified_at": "",
            "details": {
                "format": "",
                "family": "",
                "parameter_size": "",
                "quantization_level": "",
            },
        }
    ]


def test_list_models_rejects_unsafe_base_url_before_service_creation(monkeypatch):
    with _client(monkeypatch, reject_url=True) as client:
        response = client.get(
            "/api/ollama/models",
            params={"base_url": "http://169.254.169.254"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ollama_base_url_rejected"
    assert FakeOllamaService.instances == []


def test_model_info_and_delete_response_models(monkeypatch):
    with _client(monkeypatch) as client:
        info = client.get("/api/ollama/models/llama3:latest")
        delete = client.delete("/api/ollama/models/llama3:latest")

    assert info.status_code == 200
    assert info.json()["capabilities"] == ["completion", "vision", "thinking"]
    assert info.json()["model_info"] == {"general.architecture": "llama"}
    assert delete.status_code == 200
    assert delete.json()["message"] == "Model 'llama3:latest' deleted successfully"


def test_pull_rejects_unsafe_base_url_before_streaming(monkeypatch):
    with _client(monkeypatch, reject_url=True) as client:
        response = client.post(
            "/api/ollama/pull",
            json={"model": "llama3:latest", "base_url": "http://169.254.169.254"},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ollama_base_url_rejected"
    assert FakeOllamaService.instances == []


def test_pull_streams_text_event_stream_with_header_api_key(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/ollama/pull",
            json={"model": "llama3:latest", "base_url": "https://ollama.example.test"},
            headers={"X-Ollama-Api-Key": "secret"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert FakeOllamaService.instances[0].api_key == "secret"
    assert 'data: {"status": "pulling", "completed": 1}' in response.text
    assert 'data: {"status": "success"}' in response.text


def test_list_models_error_response_and_log_are_summarized(monkeypatch, caplog):
    error_text = "list models failed with secret-token"
    with _client(monkeypatch) as client:
        FakeOllamaService.list_error = RuntimeError(error_text)
        with caplog.at_level(logging.ERROR, logger=ollama_models.logger.name):
            response = client.get(
                "/api/ollama/models",
                params={"base_url": "https://ollama.example.test"},
            )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "ollama_service_unavailable"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


def test_model_info_error_response_and_log_are_summarized(monkeypatch, caplog):
    error_text = "model info failed with secret-token"
    with _client(monkeypatch) as client:
        FakeOllamaService.info_error = RuntimeError(error_text)
        with caplog.at_level(logging.ERROR, logger=ollama_models.logger.name):
            response = client.get("/api/ollama/models/llama3:latest")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "ollama_service_unavailable"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


def test_delete_model_error_response_and_log_are_summarized(monkeypatch, caplog):
    error_text = "delete model failed with secret-token"
    with _client(monkeypatch) as client:
        FakeOllamaService.delete_error = RuntimeError(error_text)
        with caplog.at_level(logging.ERROR, logger=ollama_models.logger.name):
            response = client.delete("/api/ollama/models/llama3:latest")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "ollama_model_delete_failed"
    assert detail["details"]["error"] == f"<redacted error; length={len(error_text)}>"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert "secret-token" not in str(detail)
    assert all(record.exc_info is None for record in caplog.records)


def test_pull_model_error_event_and_log_are_summarized(monkeypatch, caplog):
    error_text = "pull model failed with secret-token"
    with _client(monkeypatch) as client:
        FakeOllamaService.pull_error = RuntimeError(error_text)
        with caplog.at_level(logging.ERROR, logger=ollama_models.logger.name):
            response = client.post(
                "/api/ollama/pull",
                json={"model": "llama3:latest", "base_url": "https://ollama.example.test"},
            )

    assert response.status_code == 200
    assert f"<redacted error; length={len(error_text)}>" in response.text
    assert "secret-token" not in response.text
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)
