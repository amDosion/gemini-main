import importlib
import sys
import types


class _FakeStorageConfig:
    def __init__(
        self,
        config_id,
        config,
        *,
        provider="aliyun-oss",
        enabled=True,
        name="Storage",
    ):
        self.id = config_id
        self.user_id = "user-1"
        self.name = name
        self.provider = provider
        self.enabled = enabled
        self.config = dict(config)
        self.created_at = 1000
        self.updated_at = 1000

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "provider": self.provider,
            "enabled": self.enabled,
            "config": dict(self.config),
        }


class _FakeUserScopedQuery:
    configs = []
    by_id = {}

    def __init__(self, _db, _user_id):
        pass

    def get_all(self, _model):
        return list(self.configs)

    def get(self, _model, config_id):
        return self.by_id.get(config_id)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _model):
        return _FakeQuery(self._rows)


def _fake_decrypt_config(config):
    from app.core.encryption import ConfigDecryptionError

    if config.get("broken_credentials"):
        raise ConfigDecryptionError("access_key_id")
    return dict(config)


class _FakeCeleryTaskContext:
    def update_state(self, **_kwargs):
        return None


def _import_upload_tasks_with_fake_celery(monkeypatch):
    class FakeCeleryConf:
        def update(self, *_args, **_kwargs):
            return None

    class FakeCelery:
        def __init__(self, *_args, **_kwargs):
            self.conf = FakeCeleryConf()

        def task(self, *_args, **_kwargs):
            def decorator(func):
                return types.SimpleNamespace(run=func)

            return decorator

    celery_module = types.ModuleType("celery")
    celery_module.Celery = FakeCelery
    monkeypatch.setitem(sys.modules, "celery", celery_module)
    sys.modules.pop("app.core.celery_app", None)
    sys.modules.pop("app.tasks.upload_tasks", None)
    tasks_pkg = sys.modules.get("app.tasks")
    if tasks_pkg is not None and hasattr(tasks_pkg, "upload_tasks"):
        delattr(tasks_pkg, "upload_tasks")
    return importlib.import_module("app.tasks.upload_tasks")


def _make_upload_task_session(task, config):
    class FakeModelQuery:
        def __init__(self, model):
            self._model = model

        def filter(self, *_args):
            return self

        def first(self):
            if self._model.__name__ == "UploadTask":
                return task
            if self._model.__name__ == "StorageConfig":
                return config
            return None

    class FakeSession:
        def query(self, model):
            return FakeModelQuery(model)

        def commit(self):
            return None

        def close(self):
            return None

    return FakeSession()


def test_storage_manager_get_all_configs_marks_unreadable_credentials(monkeypatch):
    from app.services.storage import storage_manager

    broken = _FakeStorageConfig(
        "broken",
        {
            "broken_credentials": True,
            "access_key_id": "gAAAAABdummyUnreadableAccessKeyId",
            "access_key_secret": "gAAAAABdummyUnreadableAccessKeySecret",
            "bucket": "broken-bucket",
            "endpoint": "oss-cn.test.aliyuncs.com",
        },
        name="Broken OSS",
    )
    normal = _FakeStorageConfig(
        "normal",
        {
            "access_key_id": "plain-access-key-id",
            "access_key_secret": "plain-access-key-secret",
            "bucket": "normal-bucket",
            "endpoint": "oss-cn.test.aliyuncs.com",
        },
        name="Normal OSS",
    )

    _FakeUserScopedQuery.configs = [broken, normal]
    monkeypatch.setattr(storage_manager, "UserScopedQuery", _FakeUserScopedQuery)
    monkeypatch.setattr(storage_manager, "decrypt_config", _fake_decrypt_config)

    result = storage_manager.StorageManager(object(), "user-1").get_all_configs()

    assert len(result) == 2
    broken_result = result[0]
    assert broken_result["credentials_decryption_failed"] is True
    assert broken_result["requires_reentry"] is True
    assert broken_result["config"]["access_key_id"] == "***"
    assert broken_result["config"]["access_key_secret"] == "***"
    assert broken_result["config"]["bucket"] == "broken-bucket"
    assert result[1]["config"]["access_key_id"] == "plain-access-key-id"
    assert result[1].get("credentials_decryption_failed") is not True


def test_storage_manager_get_config_marks_unreadable_credentials(monkeypatch):
    from app.services.storage import storage_manager

    broken = _FakeStorageConfig(
        "broken",
        {
            "broken_credentials": True,
            "access_key_id": "gAAAAABdummyUnreadableAccessKeyId",
            "access_key_secret": "gAAAAABdummyUnreadableAccessKeySecret",
            "bucket": "broken-bucket",
            "endpoint": "oss-cn.test.aliyuncs.com",
        },
        name="Broken OSS",
    )

    _FakeUserScopedQuery.by_id = {"broken": broken}
    monkeypatch.setattr(storage_manager, "UserScopedQuery", _FakeUserScopedQuery)
    monkeypatch.setattr(storage_manager, "decrypt_config", _fake_decrypt_config)

    result = storage_manager.StorageManager(object(), "user-1").get_config("broken")

    assert result["credentials_decryption_failed"] is True
    assert result["requires_reentry"] is True
    assert result["config"]["access_key_id"] == "***"
    assert result["config"]["endpoint"] == "oss-cn.test.aliyuncs.com"


def test_storage_preview_allowlist_uses_public_fields_when_credentials_unreadable(monkeypatch):
    from app.routers.storage import storage as storage_router

    broken = _FakeStorageConfig(
        "broken",
        {
            "broken_credentials": True,
            "access_key_id": "gAAAAABdummyUnreadableAccessKeyId",
            "access_key_secret": "gAAAAABdummyUnreadableAccessKeySecret",
            "bucket": "preview-bucket",
            "endpoint": "oss-cn.test.aliyuncs.com",
        },
    )

    monkeypatch.setattr(storage_router, "decrypt_config", _fake_decrypt_config)

    allowlist = storage_router._collect_storage_preview_host_allowlist(
        _FakeDB([broken]),
        "user-1",
    )

    assert "oss-cn.test.aliyuncs.com" in allowlist
    assert "preview-bucket.oss-cn.test.aliyuncs.com" in allowlist


def test_celery_upload_task_fails_closed_when_storage_credentials_unreadable(
    monkeypatch,
    tmp_path,
):
    from app.core.encryption import ConfigDecryptionError

    upload_tasks = _import_upload_tasks_with_fake_celery(monkeypatch)

    source_file = tmp_path / "source.png"
    source_file.write_bytes(b"image")
    task = types.SimpleNamespace(
        id="task-1",
        storage_id="storage-1",
        session_id=None,
        message_id=None,
        attachment_id=None,
        filename="source.png",
        source_file_path=str(source_file),
        source_url=None,
        status="pending",
        error_message=None,
        target_url=None,
        completed_at=None,
    )
    config = types.SimpleNamespace(
        id="storage-1",
        provider="lsky",
        enabled=True,
        config={"access_key_id": "gAAAAABdummyUnreadableAccessKeyId"},
    )

    upload_calls = []

    def fake_decrypt_config(_config):
        raise ConfigDecryptionError("access_key_id")

    def fake_upload_to_lsky_sync(*_args, **_kwargs):
        upload_calls.append((_args, _kwargs))
        return {"success": True, "url": "https://example.invalid/uploaded.png"}

    monkeypatch.setattr(upload_tasks, "SessionLocal", lambda: _make_upload_task_session(task, config))
    monkeypatch.setattr("app.core.encryption.decrypt_config", fake_decrypt_config)

    from app.routers import storage as storage_package

    monkeypatch.setattr(
        storage_package,
        "upload_to_lsky_sync",
        fake_upload_to_lsky_sync,
        raising=False,
    )

    result = upload_tasks.process_upload.run(_FakeCeleryTaskContext(), "task-1")

    assert result["success"] is False
    assert "storage_config_credentials_not_decrypted" in result["error"]
    assert task.status == "failed"
    assert upload_calls == []


def test_celery_upload_success_log_summarizes_signed_target_url(
    monkeypatch,
    tmp_path,
    capsys,
):
    upload_tasks = _import_upload_tasks_with_fake_celery(monkeypatch)

    source_file = tmp_path / "source.png"
    source_file.write_bytes(b"image")
    signed_url = (
        "https://cdn.example.invalid/uploaded.png"
        "?X-Amz-Signature=secret-signature&token=secret-token#private-fragment"
    )
    task = types.SimpleNamespace(
        id="task-log",
        storage_id="storage-1",
        session_id=None,
        message_id=None,
        attachment_id=None,
        filename="source.png",
        source_file_path=str(source_file),
        source_url=None,
        status="pending",
        error_message=None,
        target_url=None,
        completed_at=None,
    )
    config = types.SimpleNamespace(
        id="storage-1",
        provider="lsky",
        enabled=True,
        config={"token": "encrypted"},
    )

    def fake_upload_to_lsky_sync(*_args, **_kwargs):
        return {"success": True, "url": signed_url}

    monkeypatch.setattr(upload_tasks, "SessionLocal", lambda: _make_upload_task_session(task, config))
    monkeypatch.setattr("app.core.encryption.decrypt_config", lambda config: dict(config))

    from app.routers import storage as storage_package

    monkeypatch.setattr(
        storage_package,
        "upload_to_lsky_sync",
        fake_upload_to_lsky_sync,
        raising=False,
    )

    result = upload_tasks.process_upload.run(_FakeCeleryTaskContext(), "task-log")
    output = capsys.readouterr().out

    assert result == {"success": True, "url": signed_url, "task_id": "task-log"}
    assert task.target_url == signed_url
    assert "上传成功: https://cdn.example.invalid path_len=13 query_params=2 fragment=yes" in output
    assert signed_url not in output
    assert "secret-signature" not in output
    assert "secret-token" not in output
    assert "private-fragment" not in output


def test_celery_upload_failure_stdout_summarizes_exception(
    monkeypatch,
    tmp_path,
    capsys,
):
    upload_tasks = _import_upload_tasks_with_fake_celery(monkeypatch)

    source_file = tmp_path / "source.png"
    source_file.write_bytes(b"image")
    secret = "provider-secret-token"
    task = types.SimpleNamespace(
        id="task-fail-log",
        storage_id="storage-1",
        session_id=None,
        message_id=None,
        attachment_id=None,
        filename="source.png",
        source_file_path=str(source_file),
        source_url=None,
        status="pending",
        error_message=None,
        target_url=None,
        completed_at=None,
    )
    config = types.SimpleNamespace(
        id="storage-1",
        provider="lsky",
        enabled=True,
        config={"token": "encrypted"},
    )

    def fake_upload_to_lsky_sync(*_args, **_kwargs):
        raise RuntimeError(f"provider failed {secret}")

    monkeypatch.setattr(upload_tasks, "SessionLocal", lambda: _make_upload_task_session(task, config))
    monkeypatch.setattr("app.core.encryption.decrypt_config", lambda config: dict(config))

    from app.routers import storage as storage_package

    monkeypatch.setattr(
        storage_package,
        "upload_to_lsky_sync",
        fake_upload_to_lsky_sync,
        raising=False,
    )

    result = upload_tasks.process_upload.run(_FakeCeleryTaskContext(), "task-fail-log")
    output = capsys.readouterr().out

    assert result["success"] is False
    assert secret in result["error"]
    assert task.status == "failed"
    assert secret not in output
    assert "provider failed" not in output
    assert "Traceback" not in output
    assert "<redacted error; length=" in output


def test_celery_upload_task_rejects_unsafe_source_url_before_upload(monkeypatch):
    from app.utils.url_security import UnsafeURLError

    upload_tasks = _import_upload_tasks_with_fake_celery(monkeypatch)

    task = types.SimpleNamespace(
        id="task-ssrf",
        storage_id="storage-1",
        session_id=None,
        message_id=None,
        attachment_id=None,
        filename="source.png",
        source_file_path=None,
        source_url="http://127.0.0.1/internal.png",
        status="pending",
        error_message=None,
        target_url=None,
        completed_at=None,
    )
    config = types.SimpleNamespace(
        id="storage-1",
        provider="lsky",
        enabled=True,
        config={"token": "encrypted"},
    )

    guarded_urls = []
    upload_calls = []

    def fake_guard(url, **kwargs):
        guarded_urls.append((url, kwargs))
        raise UnsafeURLError("blocked unsafe URL")

    def fake_upload_to_lsky_sync(*_args, **_kwargs):
        upload_calls.append((_args, _kwargs))
        return {"success": True, "url": "https://example.invalid/uploaded.png"}

    monkeypatch.setattr(upload_tasks, "SessionLocal", lambda: _make_upload_task_session(task, config))
    monkeypatch.setattr("app.core.encryption.decrypt_config", lambda config: dict(config))
    monkeypatch.setattr(upload_tasks, "sync_get_with_redirect_guard", fake_guard)

    from app.routers import storage as storage_package

    monkeypatch.setattr(
        storage_package,
        "upload_to_lsky_sync",
        fake_upload_to_lsky_sync,
        raising=False,
    )

    result = upload_tasks.process_upload.run(_FakeCeleryTaskContext(), "task-ssrf")

    assert result["success"] is False
    assert "blocked unsafe URL" in result["error"]
    assert task.status == "failed"
    assert guarded_urls == [
        ("http://127.0.0.1/internal.png", {"timeout": 30.0, "max_redirects": 5})
    ]
    assert upload_calls == []
