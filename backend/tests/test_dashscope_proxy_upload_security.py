import json
import logging

import pytest
from fastapi import HTTPException

from app.routers.system import dashscope_proxy
from app.utils.url_security import UnsafeURLError


class _FakeUploadFile:
    filename = "source.png"
    content_type = "image/png"
    file = object()

    def __init__(self, content: bytes = b"image-bytes") -> None:
        self._content = content
        self.seek_calls = []

    async def seek(self, offset: int) -> None:
        self.seek_calls.append(offset)

    async def read(self) -> bytes:
        return self._content


class _FakeRequest:
    headers = {"authorization": "Bearer test-api-key"}

    def __init__(self, upload_file: _FakeUploadFile | None = None) -> None:
        self.upload_file = upload_file or _FakeUploadFile()

    async def form(self):
        return {
            "file": self.upload_file,
            "purpose": "image-edit",
            "model": "wanx-v1",
        }


class _FakeProxyRequest:
    method = "GET"
    headers = {"authorization": "Bearer test-api-key"}
    query_params = {}

    async def body(self) -> bytes:
        return b""


class _PolicyResponse:
    status_code = 200
    text = "ok"

    def __init__(self, upload_host: str) -> None:
        self.upload_host = upload_host

    def json(self):
        return {
            "data": {
                "upload_host": self.upload_host,
                "upload_dir": "dashscope/uploads",
                "oss_access_key_id": "oss-key",
                "signature": "sig",
                "policy": "policy",
                "x_oss_object_acl": "private",
                "x_oss_forbid_overwrite": "true",
                "request_id": "req-1",
            }
        }


class _UploadResponse:
    status_code = 200
    text = "ok"


@pytest.mark.asyncio
async def test_dashscope_upload_pins_validated_upload_host(monkeypatch):
    upload_host = "https://oss.example.test/upload"
    calls = {"validated": [], "pinned": [], "posts": []}

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, headers=None, params=None):
            assert url == f"{dashscope_proxy.DASHSCOPE_BASE_URL}/api/v1/uploads"
            assert headers == {"Authorization": "Bearer test-api-key"}
            assert params == {"action": "getPolicy", "model": "wanx-v1"}
            return _PolicyResponse(upload_host)

        async def post(self, url, *, files=None, follow_redirects=None):
            calls["posts"].append(
                {
                    "url": url,
                    "files": files,
                    "follow_redirects": follow_redirects,
                }
            )
            return _UploadResponse()

    def _validate(url: str) -> str:
        calls["validated"].append(url)
        return url

    def _pin(client) -> None:
        calls["pinned"].append(client)

    monkeypatch.setattr(dashscope_proxy.httpx, "AsyncClient", _AsyncClient)
    monkeypatch.setattr(dashscope_proxy, "validate_outbound_http_url", _validate)
    monkeypatch.setattr(dashscope_proxy, "_ensure_client_pinned", _pin)

    response = await dashscope_proxy.upload_file_to_dashscope(_FakeRequest())

    assert response.status_code == 200
    assert json.loads(response.body) == {
        "data": {
            "url": "oss://dashscope/uploads/source.png",
            "file_id": "dashscope/uploads/source.png",
        },
        "request_id": "req-1",
    }
    assert calls["validated"] == [upload_host]
    assert len(calls["pinned"]) == 1
    assert calls["posts"][0]["url"] == upload_host
    assert calls["posts"][0]["follow_redirects"] is False


@pytest.mark.asyncio
async def test_dashscope_upload_rejects_unsafe_upload_host_before_post(monkeypatch):
    calls = {"posts": 0}

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return _PolicyResponse("http://127.0.0.1:9000/upload")

        async def post(self, *args, **kwargs):
            calls["posts"] += 1
            raise AssertionError("OSS upload POST must not run for unsafe upload_host")

    def _reject(_url: str) -> str:
        raise UnsafeURLError("URL 指向受限地址")

    monkeypatch.setattr(dashscope_proxy.httpx, "AsyncClient", _AsyncClient)
    monkeypatch.setattr(dashscope_proxy, "validate_outbound_http_url", _reject)

    with pytest.raises(HTTPException) as excinfo:
        await dashscope_proxy.upload_file_to_dashscope(_FakeRequest())

    assert excinfo.value.status_code == 400
    assert "URL 指向受限地址" in str(excinfo.value.detail)
    assert calls["posts"] == 0


@pytest.mark.asyncio
async def test_dashscope_upload_internal_error_is_generic(monkeypatch, caplog):
    secret = "dashscope-upload-secret"

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError(f"policy failed {secret}")

    monkeypatch.setattr(dashscope_proxy.httpx, "AsyncClient", _AsyncClient)

    with caplog.at_level(logging.ERROR, logger=dashscope_proxy.logger.name):
        with pytest.raises(HTTPException) as excinfo:
            await dashscope_proxy.upload_file_to_dashscope(_FakeRequest())

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Upload failed"
    assert secret not in str(excinfo.value.detail)
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


@pytest.mark.asyncio
async def test_dashscope_proxy_request_error_is_generic(monkeypatch, caplog):
    secret = "dashscope-request-secret"

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise dashscope_proxy.httpx.RequestError(f"network failed {secret}")

    monkeypatch.setattr(dashscope_proxy.httpx, "AsyncClient", _AsyncClient)

    with caplog.at_level(logging.ERROR, logger=dashscope_proxy.logger.name):
        with pytest.raises(HTTPException) as excinfo:
            await dashscope_proxy.proxy_dashscope("api/v1/services", _FakeProxyRequest())

    assert excinfo.value.status_code == 502
    assert excinfo.value.detail == "无法连接到 DashScope API"
    assert secret not in str(excinfo.value.detail)
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


@pytest.mark.asyncio
async def test_dashscope_proxy_unexpected_error_is_generic(monkeypatch, caplog):
    secret = "dashscope-proxy-secret"

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise RuntimeError(f"proxy failed {secret}")

    monkeypatch.setattr(dashscope_proxy.httpx, "AsyncClient", _AsyncClient)

    with caplog.at_level(logging.ERROR, logger=dashscope_proxy.logger.name):
        with pytest.raises(HTTPException) as excinfo:
            await dashscope_proxy.proxy_dashscope("api/v1/services", _FakeProxyRequest())

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "代理请求失败"
    assert secret not in str(excinfo.value.detail)
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
