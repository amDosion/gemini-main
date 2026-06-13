import logging

import pytest
from fastapi import HTTPException

from app.services.storage import storage_service as storage_module
from app.services.storage.base import UploadResult
from app.services.storage.storage_service import StorageService


class _UploadFailureProvider:
    def __init__(self, secret: str):
        self.secret = secret

    async def upload(self, *_args):
        return UploadResult(
            success=False,
            error=f"provider leaked signed url token={self.secret}",
            provider="fake",
        )


class _RaisingProvider:
    def __init__(self, secret: str):
        self.secret = secret

    async def upload(self, *_args):
        raise RuntimeError(f"upload leaked token={self.secret}")

    async def browse(self, **_kwargs):
        raise RuntimeError(f"browse leaked token={self.secret}")

    async def count_items(self, **_kwargs):
        raise RuntimeError(f"count leaked token={self.secret}")

    async def delete_path(self, **_kwargs):
        raise RuntimeError(f"delete leaked token={self.secret}")

    async def rename_path(self, **_kwargs):
        raise RuntimeError(f"rename leaked token={self.secret}")


def _install_provider(monkeypatch, provider):
    monkeypatch.setattr(
        storage_module.ProviderFactory,
        "create",
        staticmethod(lambda *_args, **_kwargs: provider),
    )


def _storage_log_records(caplog):
    return [
        record
        for record in caplog.records
        if record.name == "app.services.storage.storage_service"
    ]


def _assert_safe_failure(caplog, exc_info, detail: str, secret: str):
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == detail
    assert secret not in str(exc_info.value.detail)

    records = _storage_log_records(caplog)
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted error; length=" in log_text
    assert secret not in log_text
    assert "Traceback" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_upload_result_error_does_not_leak_to_http_detail(monkeypatch, caplog):
    secret = "secret-upload-result"
    _install_provider(monkeypatch, _UploadFailureProvider(secret))

    with caplog.at_level(logging.ERROR, logger="app.services.storage.storage_service"):
        with pytest.raises(HTTPException) as exc_info:
            await StorageService.upload_file("a.png", b"x", "image/png", "fake", {})

    _assert_safe_failure(caplog, exc_info, "上传失败", secret)


@pytest.mark.parametrize(
    ("operation", "detail"),
    [
        ("upload", "上传失败"),
        ("browse", "浏览目录失败"),
        ("count", "统计目录失败"),
        ("delete", "删除失败"),
        ("rename", "重命名失败"),
    ],
)
@pytest.mark.asyncio
async def test_storage_service_internal_errors_do_not_leak_to_http_detail(
    monkeypatch,
    caplog,
    operation,
    detail,
):
    secret = f"secret-{operation}"
    _install_provider(monkeypatch, _RaisingProvider(secret))

    with caplog.at_level(logging.ERROR, logger="app.services.storage.storage_service"):
        with pytest.raises(HTTPException) as exc_info:
            if operation == "upload":
                await StorageService.upload_file("a.png", b"x", "image/png", "fake", {})
            elif operation == "browse":
                await StorageService.browse_files("fake", {}, path="/")
            elif operation == "count":
                await StorageService.count_files("fake", {}, path="/")
            elif operation == "delete":
                await StorageService.delete_item("fake", {}, path="/a.png")
            elif operation == "rename":
                await StorageService.rename_item("fake", {}, path="/a.png", new_name="b.png")
            else:
                raise AssertionError(operation)

    _assert_safe_failure(caplog, exc_info, detail, secret)
