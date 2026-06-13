from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.system import file_search


class FakeTimestamp:
    def __str__(self) -> str:
        return "2026-06-12T00:00:00Z"


class FakeStore:
    name = "fileSearchStores/deep-research-documents"
    display_name = "deep-research-documents"
    create_time = FakeTimestamp()
    update_time = None


class FakeOperation:
    done = True
    name = "operations/upload-1"


class FakeUploadedFile:
    name = "files/uploaded-1"


class FakeFileSearchStores:
    def get(self, _name=None, *, name=None):
        return FakeStore()

    def list(self):
        return [FakeStore()]

    def upload_to_file_search_store(self, name, file):
        assert name == FakeStore.name
        assert file.name == FakeUploadedFile.name
        return FakeOperation()


class FakeFiles:
    def upload(self, path):
        assert path
        return FakeUploadedFile()


class FakeOperations:
    def get(self, name):
        assert name == FakeOperation.name
        return FakeOperation()


class FakeClient:
    file_search_stores = FakeFileSearchStores()
    files = FakeFiles()
    operations = FakeOperations()


class FakeClientPool:
    def __init__(self):
        self.calls = []

    def get_client(self, **kwargs):
        self.calls.append(kwargs)
        return FakeClient()


def _client(monkeypatch):
    pool = FakeClientPool()
    monkeypatch.setattr(file_search, "get_client_pool", lambda: pool)
    app = FastAPI()
    app.include_router(file_search.router)
    return TestClient(app), pool


def test_file_search_upload_response_model(monkeypatch):
    client, pool = _client(monkeypatch)
    with client:
        response = client.post(
            "/api/file-search/upload",
            files={"file": ("hello.txt", b"hello world", "text/plain")},
            headers={"Authorization": "Bearer fs-test-key"},
        )

    assert response.status_code == 200
    assert pool.calls == [{"api_key": "fs-test-key", "vertexai": False}]
    assert response.json() == {
        "file_search_store_name": "fileSearchStores/deep-research-documents",
        "file_name": "hello.txt",
        "status": "active",
        "operation": "operations/upload-1",
    }


def test_file_search_upload_internal_error_logs_summary(monkeypatch, caplog):
    secret = "file-search-upload-secret"

    class BoomFiles(FakeFiles):
        def upload(self, path):
            raise RuntimeError(f"upload failed {secret}")

    class BoomClient(FakeClient):
        files = BoomFiles()

    class BoomClientPool(FakeClientPool):
        def get_client(self, **kwargs):
            self.calls.append(kwargs)
            return BoomClient()

    pool = BoomClientPool()
    monkeypatch.setattr(file_search, "get_client_pool", lambda: pool)
    app = FastAPI()
    app.include_router(file_search.router)

    with TestClient(app) as client:
        with caplog.at_level(logging.ERROR, logger=file_search.logger.name):
            response = client.post(
                "/api/file-search/upload",
                files={"file": ("hello.txt", b"hello world", "text/plain")},
                headers={"Authorization": "Bearer fs-test-key"},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "File upload failed. Please try again or contact support."
    )
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_file_search_stores_response_model_stringifies_times(monkeypatch):
    client, pool = _client(monkeypatch)
    with client:
        response = client.get(
            "/api/file-search/stores",
            headers={"Authorization": "Bearer fs-test-key"},
        )

    assert response.status_code == 200
    assert pool.calls == [{"api_key": "fs-test-key", "vertexai": False}]
    assert response.json() == {
        "stores": [
            {
                "name": "fileSearchStores/deep-research-documents",
                "display_name": "deep-research-documents",
                "create_time": "2026-06-12T00:00:00Z",
                "update_time": None,
            }
        ]
    }


def test_file_search_stores_internal_error_logs_summary(monkeypatch, caplog):
    secret = "file-search-store-secret"

    class BoomStores(FakeFileSearchStores):
        def list(self):
            raise RuntimeError(f"list stores failed {secret}")

    class BoomClient(FakeClient):
        file_search_stores = BoomStores()

    class BoomClientPool(FakeClientPool):
        def get_client(self, **kwargs):
            self.calls.append(kwargs)
            return BoomClient()

    pool = BoomClientPool()
    monkeypatch.setattr(file_search, "get_client_pool", lambda: pool)
    app = FastAPI()
    app.include_router(file_search.router)

    with TestClient(app) as client:
        with caplog.at_level(logging.ERROR, logger=file_search.logger.name):
            response = client.get(
                "/api/file-search/stores",
                headers={"Authorization": "Bearer fs-test-key"},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Failed to list file search stores. Please try again or contact support."
    )
    assert secret not in response.text
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
