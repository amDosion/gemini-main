import httpx
import pytest

from app.services.common.attachment_source_resolver import load_local_storage_source_bytes
from app.utils.url_security import UnsafeURLError


@pytest.mark.asyncio
async def test_load_local_storage_source_blocks_loopback_before_fetch(monkeypatch):
    calls = {"get": 0}

    async def _must_not_get(*args, **kwargs):
        calls["get"] += 1
        raise AssertionError("httpx.AsyncClient.get must not run for blocked SSRF URL")

    monkeypatch.setattr(httpx.AsyncClient, "get", _must_not_get)

    with pytest.raises(UnsafeURLError):
        await load_local_storage_source_bytes(
            db=None,
            user_id="user-1",
            source_ai_url="http://127.0.0.1:9/private.png",
        )

    assert calls["get"] == 0
