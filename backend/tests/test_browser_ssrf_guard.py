"""SSRF guard for the workflow browser tools (S2).

read_webpage() and selenium_browse() forwarded user-supplied URLs straight to
requests.get / Selenium with no validation and (for requests) automatic redirect
following, so an attacker could reach cloud metadata (169.254.169.254), loopback,
or RFC-1918 hosts. The url_security.validate_outbound_http_url guard already
existed; these tests pin that it is now wired in BEFORE any network/driver call.
"""

import pytest

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
