from __future__ import annotations

import logging

from fastapi import FastAPI
from starlette.testclient import TestClient

from app.routers.tools import browse
from app.services.gemini.common import browser as gemini_browser
from app.utils.log_sanitization import redact_exact_value_in_log_text, summarize_url_for_log


class _FakeBrowseResponse:
    text = "<html><head><title>Example</title></head><body>Hello</body></html>"

    def raise_for_status(self) -> None:
        return None


class _FakeBrowseClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def get(self, url: str, **kwargs):
        self.urls.append(url)
        return _FakeBrowseResponse()


class _FailingBrowseClient:
    async def get(self, url: str, **kwargs):
        raise RuntimeError(f"internal failure for {url} with secret-token")


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(browse.router)
    app.dependency_overrides[browse.require_current_user] = lambda: "user-browse"
    app.dependency_overrides[browse.require_admin] = lambda: "admin-browse"
    return TestClient(app)


def test_browse_logs_url_summary_without_leaking_signed_query(monkeypatch, caplog):
    raw_url = (
        "https://example.com/private/path"
        "?token=secret-token&X-Amz-Signature=secret-signature#private-fragment"
    )
    fake_client = _FakeBrowseClient()
    test_logger = logging.getLogger("test.browse.url-redaction")

    async def fake_get_client():
        return fake_client

    monkeypatch.setattr(browse, "validate_outbound_http_url", lambda url: None)
    monkeypatch.setattr(browse, "_get_async_http_client", fake_get_client)
    monkeypatch.setattr(browse, "_SELENIUM_AVAILABLE", False)
    monkeypatch.setattr(browse, "_selenium_browse", None)
    monkeypatch.setattr(browse, "_progress_tracker", None)
    monkeypatch.setattr(browse, "_logger", test_logger)
    monkeypatch.setattr(
        browse,
        "_LOG_PREFIXES",
        {
            "request": "[request]",
            "webpage": "[webpage]",
            "success": "[success]",
            "error": "[error]",
            "warning": "[warning]",
            "selenium": "[selenium]",
        },
    )

    with caplog.at_level(logging.INFO, logger=test_logger.name), _build_client() as client:
        resp = client.post("/api/browse", json={"url": raw_url})

    assert resp.status_code == 200
    assert fake_client.urls == [raw_url]
    assert "https://example.com path_len=13 query_params=2 fragment=yes" in caplog.text
    assert raw_url not in caplog.text
    assert "/private/path" not in caplog.text
    assert "secret-token" not in caplog.text
    assert "secret-signature" not in caplog.text
    assert "private-fragment" not in caplog.text


def test_browse_internal_error_log_and_response_are_summarized(monkeypatch, caplog):
    raw_url = (
        "https://example.com/private/path"
        "?token=secret-token&X-Amz-Signature=secret-signature#private-fragment"
    )
    test_logger = logging.getLogger("test.browse.internal-error-redaction")

    async def fake_get_client():
        return _FailingBrowseClient()

    monkeypatch.setattr(browse, "validate_outbound_http_url", lambda url: None)
    monkeypatch.setattr(browse, "_get_async_http_client", fake_get_client)
    monkeypatch.setattr(browse, "_SELENIUM_AVAILABLE", False)
    monkeypatch.setattr(browse, "_selenium_browse", None)
    monkeypatch.setattr(browse, "_progress_tracker", None)
    monkeypatch.setattr(browse, "_logger", test_logger)
    monkeypatch.setattr(
        browse,
        "_LOG_PREFIXES",
        {
            "request": "[request]",
            "webpage": "[webpage]",
            "success": "[success]",
            "error": "[error]",
            "warning": "[warning]",
            "selenium": "[selenium]",
        },
    )

    with caplog.at_level(logging.ERROR, logger=test_logger.name), _build_client() as client:
        resp = client.post("/api/browse", json={"url": raw_url})

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error while browsing"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://example.com path_len=13 query_params=2 fragment=yes" in log_text
    assert "<redacted error; length=" in log_text
    assert raw_url not in log_text
    assert "/private/path" not in log_text
    assert "secret-token" not in log_text
    assert "secret-signature" not in log_text
    assert "private-fragment" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_stop_browser_session_error_log_and_response_are_summarized(monkeypatch, caplog):
    test_logger = logging.getLogger("test.browse.stop-session-redaction")

    def fake_close_driver(*, user_id):
        raise RuntimeError("stop failed with secret-token")

    monkeypatch.setattr(gemini_browser, "close_driver", fake_close_driver)
    monkeypatch.setattr(browse, "_logger", test_logger)

    with caplog.at_level(logging.ERROR, logger=test_logger.name), _build_client() as client:
        resp = client.post("/api/browser/stop")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to stop browser session"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "<redacted error; length=29>" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_browser_sessions_error_log_and_response_are_summarized(monkeypatch, caplog):
    test_logger = logging.getLogger("test.browse.sessions-redaction")

    def fake_get_active_sessions():
        raise RuntimeError("sessions failed with secret-token")

    monkeypatch.setattr(gemini_browser, "get_active_sessions", fake_get_active_sessions)
    monkeypatch.setattr(browse, "_logger", test_logger)

    with caplog.at_level(logging.ERROR, logger=test_logger.name), _build_client() as client:
        resp = client.get("/api/browser/sessions")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to get browser sessions"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "<redacted error; length=33>" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_redact_url_in_log_text_replaces_embedded_raw_url():
    raw_url = "https://example.com/a?token=secret"
    summary = summarize_url_for_log(raw_url)

    assert redact_exact_value_in_log_text(f"failed while fetching {raw_url}", raw_url, summary) == (
        "failed while fetching https://example.com path_len=2 query_params=1 fragment=no"
    )


def test_gemini_browser_web_search_logs_query_summary(monkeypatch, caplog):
    query = "private search query secret-token"

    def fake_get(*_args, **_kwargs):
        raise RuntimeError("search backend echoed secret-token")

    monkeypatch.setattr(gemini_browser.requests, "get", fake_get)

    with caplog.at_level(logging.INFO, logger=gemini_browser.logger.name):
        result = gemini_browser.web_search(query)

    assert "secret-token" in result
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"query_params=1 length={len(query)}" in log_text
    assert query not in log_text
    assert "search backend echoed secret-token" not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_gemini_browser_read_webpage_logs_url_summary(monkeypatch, caplog):
    raw_url = "https://reader.example.test/private/path?token=secret-token#frag"

    def fake_guard(url, **_kwargs):
        raise gemini_browser.requests.exceptions.RequestException(
            f"failed while fetching {url}"
        )

    monkeypatch.setattr(gemini_browser, "_http_get_with_ssrf_guard", fake_guard)

    with caplog.at_level(logging.ERROR, logger=gemini_browser.logger.name):
        result = gemini_browser.read_webpage(raw_url)

    assert raw_url in result
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://reader.example.test path_len=13 query_params=1 fragment=yes" in log_text
    assert raw_url not in log_text
    assert "/private/path" not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)


def test_gemini_browser_selenium_logs_url_and_user_summaries(monkeypatch, caplog):
    raw_url = "https://selenium.example.test/private/path?token=secret-token"
    user_id = "user-secret-token"

    monkeypatch.setattr(gemini_browser, "SELENIUM_AVAILABLE", False)
    monkeypatch.setattr(gemini_browser, "validate_outbound_http_url", lambda url: url)

    with caplog.at_level(logging.INFO, logger=gemini_browser.logger.name):
        result = gemini_browser.selenium_browse(raw_url, user_id=user_id)

    assert result["error"] == (
        "Error: Selenium is not available. Please install selenium and webdriver-manager."
    )
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "https://selenium.example.test path_len=13 query_params=1 fragment=no" in log_text
    assert f"<redacted user_id; length={len(user_id)}>" in log_text
    assert raw_url not in log_text
    assert user_id not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in caplog.records)
