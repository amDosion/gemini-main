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
