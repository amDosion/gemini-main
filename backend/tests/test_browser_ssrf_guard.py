"""SSRF guard for the workflow browser tools (S2).

read_webpage() and selenium_browse() forwarded user-supplied URLs straight to
requests.get / Selenium with no validation and (for requests) automatic redirect
following, so an attacker could reach cloud metadata (169.254.169.254), loopback,
or RFC-1918 hosts. The url_security.validate_outbound_http_url guard already
existed; these tests pin that it is now wired in BEFORE any network/driver call.
"""

import logging

from app.services.gemini.common import browser

INTERNAL_URLS = [
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://127.0.0.1:8080/admin",               # loopback
    "http://10.0.0.5/internal",                  # RFC-1918
]


def test_read_webpage_rejects_internal_targets_before_any_request(monkeypatch):
    calls = []

    def _record(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("requests.get must not be reached for a blocked URL")

    monkeypatch.setattr(browser.requests, "get", _record)

    for url in INTERNAL_URLS:
        result = browser.read_webpage(url)
        assert isinstance(result, str)
        # Returns an error string, never page content.
        assert "Error" in result or "受限" in result or "不被允许" in result
    # The SSRF guard must short-circuit before any outbound request.
    assert calls == []


def test_selenium_browse_rejects_internal_targets_before_driver(monkeypatch):
    def _no_driver(*args, **kwargs):
        raise AssertionError("get_driver must not be reached for a blocked URL")

    monkeypatch.setattr(browser, "get_driver", _no_driver)

    result = browser.selenium_browse("http://169.254.169.254/latest/meta-data/")
    assert isinstance(result, dict)
    assert result.get("error")


def test_read_webpage_allows_public_target(monkeypatch):
    class _FakeResponse:
        status_code = 200
        text = "<html><body><h1>hello-public</h1></body></html>"
        headers: dict = {}

        def raise_for_status(self):
            return None

    captured = {}

    def _fake_get(self, url, **kwargs):
        captured["url"] = url
        return _FakeResponse()

    # The guard now uses a pinned httpx sync client (redirects disabled on the
    # client itself); mock its GET instead of requests.
    import httpx

    monkeypatch.setattr(httpx.Client, "get", _fake_get)

    # 8.8.8.8 is a public IP literal -> passes the SSRF guard with no DNS lookup.
    result = browser.read_webpage("http://8.8.8.8/")
    assert "hello-public" in result.lower()
    assert captured.get("url") == "http://8.8.8.8/"


def test_read_webpage_logs_url_summary_without_signed_query(monkeypatch, caplog):
    class _FakeResponse:
        status_code = 200
        text = "<html><body><h1>hello-private</h1></body></html>"
        headers: dict = {}

        def raise_for_status(self):
            return None

    captured = {}

    def _fake_get(self, url, **kwargs):
        captured["url"] = url
        return _FakeResponse()

    import httpx

    monkeypatch.setattr(httpx.Client, "get", _fake_get)

    raw_url = (
        "http://8.8.8.8/private/path"
        "?token=secret-token&X-Amz-Signature=secret-signature"
        "#private-fragment"
    )

    with caplog.at_level(logging.INFO, logger=browser.logger.name):
        result = browser.read_webpage(raw_url)

    assert "hello-private" in result.lower()
    assert captured.get("url") == raw_url

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "http://8.8.8.8 path_len=13 query_params=2 fragment=yes" in log_text
    assert raw_url not in log_text
    assert "/private/path" not in log_text
    assert "secret-token" not in log_text
    assert "secret-signature" not in log_text
    assert "private-fragment" not in log_text


def test_selenium_browse_logs_url_summary_and_not_step_payload(monkeypatch, caplog):
    captured = {"driver_get": [], "guard_url": None, "documents": []}

    class _FakeResponse:
        text = "<html><body><h1>selenium-private</h1><script>fetch('http://127.0.0.1/')</script></body></html>"
        url = "http://8.8.8.8/private/path?token=secret-token&X-Amz-Signature=secret-signature#private-fragment"

        def raise_for_status(self):
            return None

    def _fake_guard(url, *, headers, timeout, max_redirects=5):
        captured["guard_url"] = url
        return _FakeResponse()

    class _FakeDriver:
        page_source = "<html><body><h1>selenium-private</h1></body></html>"

        def set_window_size(self, width, height):
            return None

        def get(self, url):
            captured["driver_get"].append(url)

        def execute_script(self, script, *args):
            if "document.write" in script:
                captured["documents"].append(args[0])
                return None
            if "scrollHeight" in script:
                return 100
            if "pageYOffset" in script:
                return 100
            return None

        def get_window_size(self):
            return {"width": 1024, "height": 2048}

        def get_screenshot_as_base64(self):
            return "screenshot"

    class _FakeWait:
        def __init__(self, driver, timeout):
            self.driver = driver
            self.timeout = timeout

        def until(self, condition):
            return object()

    monkeypatch.setattr(browser, "SELENIUM_AVAILABLE", True)
    monkeypatch.setattr(browser, "_http_get_with_ssrf_guard", _fake_guard)
    monkeypatch.setattr(browser, "get_driver", lambda user_id="default": _FakeDriver())
    monkeypatch.setattr(browser, "WebDriverWait", _FakeWait)
    monkeypatch.setattr(browser.time, "sleep", lambda seconds: None)

    raw_url = (
        "http://8.8.8.8/private/path"
        "?token=secret-token&X-Amz-Signature=secret-signature"
        "#private-fragment"
    )

    with caplog.at_level(logging.DEBUG, logger=browser.logger.name):
        result = browser.selenium_browse(
            raw_url,
            steps=[{"action": "wait", "seconds": 0, "keys": "super-secret-password"}],
            capture_screenshot=False,
            auto_scroll=False,
        )

    assert result["error"] is None
    assert "selenium-private" in result["content"].lower()
    assert captured["guard_url"] == raw_url
    assert captured["driver_get"] == ["about:blank"]
    assert captured["documents"]
    assert "<script" not in captured["documents"][0].lower()
    assert "script-src 'none'" in captured["documents"][0]
    assert "127.0.0.1" not in captured["documents"][0]

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "http://8.8.8.8 path_len=13 query_params=2 fragment=yes" in log_text
    assert "Steps to perform: 1" in log_text
    assert raw_url not in log_text
    assert "/private/path" not in log_text
    assert "secret-token" not in log_text
    assert "secret-signature" not in log_text
    assert "private-fragment" not in log_text
    assert "super-secret-password" not in log_text


def test_selenium_browse_rejects_redirect_to_internal_before_driver(monkeypatch):
    def _blocked_redirect(url, *, headers, timeout, max_redirects=5):
        raise browser.UnsafeURLError("redirect target is restricted")

    def _no_driver(*args, **kwargs):
        raise AssertionError("get_driver must not be reached when guarded fetch blocks")

    monkeypatch.setattr(browser, "SELENIUM_AVAILABLE", True)
    monkeypatch.setattr(browser, "_http_get_with_ssrf_guard", _blocked_redirect)
    monkeypatch.setattr(browser, "get_driver", _no_driver)

    result = browser.selenium_browse(
        "http://8.8.8.8/",
        capture_screenshot=False,
        auto_scroll=False,
    )

    assert result["error"]
    assert "SSRF" in result["error"] or "防护" in result["error"]
