import pytest

from app.services.common import cache_service as cache_module
from app.services.common.cache_service import _CACHE_MISS, CacheService


class _ConnectTimeoutRedis:
    def __init__(self):
        self.close_calls = 0

    async def ping(self):
        raise TimeoutError("redis connect timeout")

    async def close(self):
        self.close_calls += 1


class _OperationTimeoutRedis:
    def __init__(self):
        self.close_calls = 0

    async def get(self, _key):
        raise TimeoutError("redis read timeout")

    async def close(self):
        self.close_calls += 1


@pytest.mark.asyncio
async def test_cache_service_connect_timeout_degrades_without_raising(monkeypatch):
    clients = []

    def fake_from_url(*_args, **_kwargs):
        client = _ConnectTimeoutRedis()
        clients.append(client)
        return client

    monkeypatch.setattr(cache_module.redis, "from_url", fake_from_url)
    service = CacheService()

    assert await service.connect() is False
    assert service._redis is None
    assert clients[0].close_calls == 1

    fetch_calls = 0

    async def fetch_value():
        nonlocal fetch_calls
        fetch_calls += 1
        return {"fresh": True}

    assert await service.get_or_set("cache:models:profile", fetch_value) == {"fresh": True}
    assert fetch_calls == 1
    assert len(clients) == 1


@pytest.mark.asyncio
async def test_cache_service_operation_timeout_drops_client_and_uses_miss():
    client = _OperationTimeoutRedis()
    service = CacheService(redis_client=client)

    assert await service._get_raw("cache:models:profile") is _CACHE_MISS
    assert client.close_calls == 1
    assert service._redis is None

    fetch_calls = 0

    async def fetch_value():
        nonlocal fetch_calls
        fetch_calls += 1
        return ["model-a"]

    assert await service.get_or_set("cache:models:profile", fetch_value) == ["model-a"]
    assert fetch_calls == 1
