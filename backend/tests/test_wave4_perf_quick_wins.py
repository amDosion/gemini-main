import types

import pytest


class _ImmediateCache:
    def _make_key(self, *parts):
        return ":".join(str(part) for part in parts)

    async def get_or_set(self, _key, factory, ttl):
        return await factory()


class _FakeStorageResponse(dict):
    def __init__(self):
        super().__init__({"ResponseMetadata": {"HTTPStatusCode": 200}, "ETag": '"etag"'})


@pytest.mark.asyncio
async def test_s3_upload_runs_blocking_sdk_call_in_worker_thread(monkeypatch):
    from app.services.storage import s3_provider

    calls = []

    async def fake_to_thread(func, /, *args, **kwargs):
        calls.append((func.__name__, kwargs))
        return func(*args, **kwargs)

    class Client:
        def put_object(self, **kwargs):
            return _FakeStorageResponse()

    monkeypatch.setattr(s3_provider.asyncio, "to_thread", fake_to_thread)
    provider = s3_provider.S3Provider({
        "access_key_id": "ak",
        "secret_access_key": "sk",
        "bucket": "bucket",
    })
    monkeypatch.setattr(provider, "_create_client", lambda: Client())

    result = await provider.upload("a.png", b"data", "image/png")

    assert result.success is True
    assert calls == [("put_object", {
        "Bucket": "bucket",
        "Key": result.metadata["object_key"],
        "Body": b"data",
        "ContentType": "image/png",
    })]


@pytest.mark.asyncio
async def test_tencent_upload_runs_blocking_sdk_call_in_worker_thread(monkeypatch):
    from app.services.storage import tencent_provider

    calls = []

    async def fake_to_thread(func, /, *args, **kwargs):
        calls.append((func.__name__, kwargs))
        return func(*args, **kwargs)

    class Client:
        def put_object(self, **kwargs):
            return _FakeStorageResponse()

    monkeypatch.setattr(tencent_provider.asyncio, "to_thread", fake_to_thread)
    provider = tencent_provider.TencentProvider({
        "secret_id": "sid",
        "secret_key": "sk",
        "bucket": "bucket",
        "region": "ap-guangzhou",
    })
    monkeypatch.setattr(provider, "_create_client", lambda: Client())

    result = await provider.upload("a.png", b"data", "image/png")

    assert result.success is True
    assert calls == [("put_object", {
        "Bucket": "bucket",
        "Key": result.metadata["object_name"],
        "Body": b"data",
        "ContentType": "image/png",
    })]


@pytest.mark.asyncio
async def test_aliyun_upload_runs_blocking_sdk_call_in_worker_thread(monkeypatch):
    from app.services.storage import aliyun_provider

    calls = []

    async def fake_to_thread(func, /, *args, **kwargs):
        calls.append((func.__name__, args, kwargs))
        return func(*args, **kwargs)

    class Bucket:
        def put_object(self, *args, **kwargs):
            return types.SimpleNamespace(status=200)

    monkeypatch.setattr(aliyun_provider.asyncio, "to_thread", fake_to_thread)
    provider = aliyun_provider.AliyunProvider({
        "access_key_id": "ak",
        "access_key_secret": "sk",
        "bucket": "bucket",
        "endpoint": "oss-cn.test.aliyuncs.com",
    })
    monkeypatch.setattr(provider, "_create_bucket_client", lambda: Bucket())

    result = await provider.upload("a.png", b"data", "image/png")

    assert result.success is True
    assert len(calls) == 1
    assert calls[0][0] == "put_object"
    assert calls[0][1] == (result.metadata["object_name"], b"data")
    assert calls[0][2] == {"headers": {"Content-Type": "image/png"}}


def test_database_logging_filter_uses_in_memory_value_without_db_lookup(monkeypatch):
    from app.core.logger import DatabaseLoggingFilter

    logging_filter = DatabaseLoggingFilter()
    logging_filter.set_enable_logging(False)
    monkeypatch.setattr(
        logging_filter,
        "_get_enable_logging_from_db",
        lambda: pytest.fail("filter hot path must not query the database"),
    )

    assert logging_filter.filter(types.SimpleNamespace()) is False


@pytest.mark.asyncio
async def test_get_sessions_pushes_mode_filter_into_user_scoped_query(monkeypatch):
    from app.routers.user import sessions as sessions_router

    class FakeQuery:
        def __init__(self):
            self.filters = []

        def filter(self, *criteria):
            self.filters.extend(criteria)
            return self

        def all(self):
            return []

    fake_query = FakeQuery()

    class FakeUserScopedQuery:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def query(self, model):
            assert model is sessions_router.DBChatSession
            return fake_query

        def get_all(self, model):
            raise AssertionError("mode-filtered sessions must not load all rows first")

    monkeypatch.setattr(sessions_router, "UserScopedQuery", FakeUserScopedQuery)

    result = await sessions_router.get_sessions(
        mode="image-gen",
        user_id="user-1",
        db=object(),
        cache=_ImmediateCache(),
    )

    assert result == []
    assert fake_query.filters, "expected DBChatSession.mode filter to be pushed into SQL query"
