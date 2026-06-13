"""W02R-016: close the DNS-rebinding TOCTOU in the outbound egress guard.

The previous guard resolved+validated the host, then httpx/requests RE-RESOLVED
at connect time — a window for a short-TTL record to flip public->internal. The
fix resolves+validates AND connects to the SAME pinned IP at connect time (a
custom httpcore network backend), so there is no second resolution to exploit.
httpcore still performs TLS SNI/cert verification against the original hostname.
"""

import httpx
import pytest

from app.utils import url_security as us


def test_resolve_single_allowed_ip_returns_public(monkeypatch):
    monkeypatch.setattr(us, "_getaddrinfo", lambda h, p: [(2, 1, 6, "", ("1.2.3.4", p))])
    assert us._resolve_single_allowed_ip("ok.example", 443) == "1.2.3.4"


def test_resolve_single_allowed_ip_rejects_internal_resolution(monkeypatch):
    monkeypatch.setattr(us, "_getaddrinfo", lambda h, p: [(2, 1, 6, "", ("127.0.0.1", p))])
    with pytest.raises(us.UnsafeURLError):
        us._resolve_single_allowed_ip("evil.example", 443)


def test_resolve_single_allowed_ip_rejects_internal_literal():
    with pytest.raises(us.UnsafeURLError):
        us._resolve_single_allowed_ip("169.254.169.254", 80)


@pytest.mark.asyncio
async def test_pinning_backend_blocks_connect_to_internal(monkeypatch):
    # Connect-time resolution returns an internal IP -> rejected before connecting,
    # so a rebinding flip cannot reach the internal target.
    monkeypatch.setattr(us, "_getaddrinfo", lambda h, p: [(2, 1, 6, "", ("10.0.0.5", p))])
    backend = us._PinningAsyncBackend()
    with pytest.raises(us.UnsafeURLError):
        await backend.connect_tcp("rebind.example", 443)


def test_guard_injects_pinning_backend_into_client():
    client = httpx.AsyncClient()
    try:
        us._ensure_client_pinned(client)
        assert isinstance(client._transport._pool._network_backend, us._PinningAsyncBackend)
    finally:
        pass


def test_sync_pinning_backend_blocks_connect_to_internal(monkeypatch):
    monkeypatch.setattr(us, "_getaddrinfo", lambda h, p: [(2, 1, 6, "", ("10.0.0.5", p))])
    backend = us._PinningSyncBackend()
    with pytest.raises(us.UnsafeURLError):
        backend.connect_tcp("rebind.example", 443)


def test_sync_guard_injects_pinning_backend_into_client():
    client = httpx.Client()
    try:
        us._ensure_sync_client_pinned(client)
        assert isinstance(client._transport._pool._network_backend, us._PinningSyncBackend)
    finally:
        client.close()


# --- M1: async pinning backend must not block the event loop on DNS resolution ---
# _PinningAsyncBackend.connect_tcp runs the blocking getaddrinfo; it must offload to
# an executor under a bounded asyncio.wait_for (like validate_outbound_http_url_async),
# not call socket.getaddrinfo synchronously on the event loop.


@pytest.mark.asyncio
async def test_pinning_async_backend_bounds_slow_resolution(monkeypatch):
    import time

    # Tight timeout + a resolver that blocks far longer than it.
    monkeypatch.setattr(us, "_DEFAULT_DNS_TIMEOUT_SECONDS", 0.1)

    def slow_getaddrinfo(host, port):
        time.sleep(1.0)
        return [(2, 1, 6, "", ("1.2.3.4", port))]

    monkeypatch.setattr(us, "_getaddrinfo", slow_getaddrinfo)

    backend = us._PinningAsyncBackend()

    async def fake_inner(ip, port, **kwargs):  # would only run if resolution returned
        return "CONN"

    monkeypatch.setattr(backend._inner, "connect_tcp", fake_inner)

    # With offload+timeout the slow resolution is bounded -> UnsafeURLError.
    # (Without the fix, the sync resolve blocks then returns, and connect_tcp
    # would resolve successfully instead of timing out.)
    with pytest.raises(us.UnsafeURLError):
        await backend.connect_tcp("slow.example", 443)


@pytest.mark.asyncio
async def test_pinning_async_backend_connects_to_pinned_ip(monkeypatch):
    monkeypatch.setattr(us, "_getaddrinfo", lambda h, p: [(2, 1, 6, "", ("1.2.3.4", p))])
    backend = us._PinningAsyncBackend()
    captured = {}

    async def fake_inner(ip, port, **kwargs):
        captured["ip"] = ip
        captured["port"] = port
        return "CONN"

    monkeypatch.setattr(backend._inner, "connect_tcp", fake_inner)
    result = await backend.connect_tcp("ok.example", 443)
    assert result == "CONN"
    assert captured["ip"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_async_redirect_guard_bounds_initial_slow_resolution(monkeypatch):
    import time

    monkeypatch.setattr(us, "_DEFAULT_DNS_TIMEOUT_SECONDS", 0.1)

    def slow_getaddrinfo(host, port):
        time.sleep(1.0)
        return [(2, 1, 6, "", ("1.2.3.4", port))]

    monkeypatch.setattr(us, "_getaddrinfo", slow_getaddrinfo)

    client = httpx.AsyncClient()
    try:
        with pytest.raises(us.UnsafeURLError):
            await us.get_with_redirect_guard(client, "https://slow.example/image.png")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_redirect_guard_bounds_redirect_slow_resolution(monkeypatch):
    import time

    monkeypatch.setattr(us, "_DEFAULT_DNS_TIMEOUT_SECONDS", 0.1)

    def selective_getaddrinfo(host, port):
        if host == "ok.example":
            return [(2, 1, 6, "", ("1.2.3.4", port))]
        time.sleep(1.0)
        return [(2, 1, 6, "", ("1.2.3.5", port))]

    monkeypatch.setattr(us, "_getaddrinfo", selective_getaddrinfo)

    client = httpx.AsyncClient()

    async def fake_get(url, *, follow_redirects=False):
        return httpx.Response(
            302,
            headers={"location": "https://slow.example/next.png"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(client, "get", fake_get)

    try:
        with pytest.raises(us.UnsafeURLError):
            await us.get_with_redirect_guard(client, "https://ok.example/start.png")
    finally:
        await client.aclose()
