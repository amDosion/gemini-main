"""SSRF guard for the Lsky (兰空图床) provider: a user-configured ``domain``
pointing at a private/loopback/metadata host must be rejected BEFORE any outbound
request, on all three egress paths (upload / browse / count_items).
"""

import pytest

from app.services.storage import lsky_provider
from app.services.storage.lsky_provider import LskyProvider

PRIVATE_DOMAIN = "http://169.254.169.254"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    async def _boom():
        raise AssertionError("network client must not be created when SSRF guard rejects")

    monkeypatch.setattr(lsky_provider, "_get_async_http_client", _boom)


@pytest.mark.asyncio
async def test_upload_rejects_private_domain_without_network():
    provider = LskyProvider({"domain": PRIVATE_DOMAIN, "token": "t"})
    result = await provider.upload("f.png", b"x", "image/png")
    assert result.success is False
    assert result.error


@pytest.mark.asyncio
async def test_browse_rejects_private_domain_without_network():
    provider = LskyProvider({"domain": PRIVATE_DOMAIN, "token": "t"})
    result = await provider.browse()
    assert isinstance(result, dict)
    assert result.get("supported") is False


@pytest.mark.asyncio
async def test_count_items_rejects_private_domain_without_network():
    provider = LskyProvider({"domain": PRIVATE_DOMAIN, "token": "t"})
    result = await provider.count_items()
    assert isinstance(result, dict)
    assert result.get("supported") is False


@pytest.mark.asyncio
async def test_public_domain_is_allowed_to_proceed_to_network():
    # A public destination must pass the guard and then hit the (boom) client —
    # proving the guard did NOT reject a legitimate public endpoint. A public IP
    # literal avoids any DNS dependency in the unit test.
    provider = LskyProvider({"domain": "https://1.1.1.1", "token": "t"})
    with pytest.raises(AssertionError):
        await provider.upload("f.png", b"x", "image/png")


@pytest.mark.asyncio
async def test_module_http_client_is_ip_pinned():
    # W02R-016: the reused module-level client must carry the connect-time
    # IP-pinning backend so a DNS-rebinding flip after validation cannot reach an
    # internal host (consistent with the committed get_with_redirect_guard).
    import importlib

    from app.utils.url_security import _PinningAsyncBackend

    mod = importlib.reload(lsky_provider)
    client = await mod._get_async_http_client()
    try:
        backend = client._transport._pool._network_backend
        assert isinstance(backend, _PinningAsyncBackend)
    finally:
        await client.aclose()
        mod._http_client = None
