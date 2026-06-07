"""Unit tests for the canonical synchronous SSRF egress guard.

`sync_get_with_redirect_guard` is the sync counterpart of get_with_redirect_guard:
it re-validates the initial URL AND every redirect hop, and (W02R-016) connects
to the validated IP at connect time via a pinned httpx sync transport — fully
scoped to its own client, no global socket state. This closes the "validate
initial URL, then the client re-resolves and follows a 302 to 169.254.169.254"
bypass (CANON-012/013) and the DNS-rebinding window.
"""

import httpx
import pytest

from app.utils.url_security import UnsafeURLError, sync_get_with_redirect_guard


class _Resp:
    def __init__(self, status_code, headers=None, content=b"ok"):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content


def test_rejects_loopback_initial_url_without_fetch(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(httpx.Client, "get", lambda self, u, **k: calls.__setitem__("n", calls["n"] + 1))
    with pytest.raises(UnsafeURLError):
        sync_get_with_redirect_guard("http://127.0.0.1:9/x")
    assert calls["n"] == 0


def test_rejects_metadata_ip_initial(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda self, u, **k: _Resp(200))
    with pytest.raises(UnsafeURLError):
        sync_get_with_redirect_guard("http://169.254.169.254/latest/")


def test_rejects_redirect_to_internal(monkeypatch):
    seq = [_Resp(302, {"location": "http://127.0.0.1/secret"})]
    monkeypatch.setattr(httpx.Client, "get", lambda self, u, **k: seq.pop(0))
    with pytest.raises(UnsafeURLError):
        sync_get_with_redirect_guard("http://1.1.1.1/start")


def test_follows_safe_redirect_then_returns(monkeypatch):
    seq = [_Resp(302, {"location": "http://8.8.8.8/next"}), _Resp(200, {}, b"final")]
    monkeypatch.setattr(httpx.Client, "get", lambda self, u, **k: seq.pop(0))
    resp = sync_get_with_redirect_guard("http://1.1.1.1/start")
    assert resp.status_code == 200
    assert resp.content == b"final"


def test_returns_response_on_direct_200(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda self, u, **k: _Resp(200, {}, b"hello"))
    resp = sync_get_with_redirect_guard("http://1.1.1.1/ok")
    assert resp.status_code == 200
    assert resp.content == b"hello"


def test_redirect_without_location_is_rejected(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda self, u, **k: _Resp(302, {}))
    with pytest.raises(UnsafeURLError):
        sync_get_with_redirect_guard("http://1.1.1.1/start")
