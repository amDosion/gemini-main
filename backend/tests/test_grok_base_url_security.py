import logging

import pytest

from app.services.grok import grok_service as grok_service_mod
from app.services.grok.grok_service import GrokService
from app.services.grok.image_editor import ImageEditor
from app.services.grok.image_generator import ImageGenerator
from app.services.grok.video_generator import VideoGenerator
from app.utils.url_security import UnsafeURLError


def test_grok_service_preserves_default_local_base_url():
    service = GrokService(api_key="test-key")

    assert service.base_url == "http://localhost:8000/v1"


def test_grok_service_validates_non_default_base_url(monkeypatch):
    calls = []

    def fake_validate(url):
        calls.append(url)
        return url

    monkeypatch.setattr(grok_service_mod, "validate_storage_egress_url", fake_validate)

    service = GrokService(api_key="test-key", api_url="https://grok.example.test/v1/")

    assert service.base_url == "https://grok.example.test/v1"
    assert calls == ["https://grok.example.test/v1"]


def test_grok_service_rejects_non_default_loopback_base_url():
    with pytest.raises(UnsafeURLError):
        GrokService(api_key="test-key", api_url="http://127.0.0.1:8001/v1")


def test_grok_service_logs_summarized_base_url(monkeypatch, caplog):
    def fake_validate(url):
        return url

    monkeypatch.setattr(grok_service_mod, "validate_storage_egress_url", fake_validate)

    with caplog.at_level(logging.INFO, logger=grok_service_mod.logger.name):
        GrokService(
            api_key="test-key",
            api_url="https://grok.example.test/private-token-path/v1",
        )

    assert "private-token-path" not in caplog.text
    assert "https://grok.example.test path_len=" in caplog.text


def test_grok_subservices_log_summarized_base_url(caplog):
    base_url = "https://grok.example.test/private-token-path/v1"

    with caplog.at_level(logging.INFO):
        ImageGenerator(api_key="test-key", base_url=base_url)
        ImageEditor(api_key="test-key", base_url=base_url)
        VideoGenerator(api_key="test-key", base_url=base_url)

    assert "private-token-path" not in caplog.text
    assert caplog.text.count("https://grok.example.test path_len=") == 3
