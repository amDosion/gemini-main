"""Fail-closed storage-config decryption in AttachmentService (B2).

_get_effective_storage_config did `except Exception: resolved_config = raw_config`,
so a ConfigDecryptionError (e.g. ENCRYPTION_KEY mismatch) silently handed the raw
Fernet ciphertext config to the storage provider. This is the same fail-open class
fe394cb closed for storage_manager / storage_router / celery — but the
attachment_service path was not covered. Contract: a decryption failure must
propagate (fail closed), never fall back to ciphertext.
"""

import pytest


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeDB:
    def __init__(self, config_obj):
        self._config = config_obj

    def query(self, _model):
        return _FakeQuery(self._config)


class _FakeStorageConfig:
    id = "cfg-1"
    enabled = True
    provider = "aliyun-oss"
    config = {"access_key_id": "gAAAAA-ciphertext", "bucket": "b1"}


def _make_service(monkeypatch):
    from app.services.common import attachment_service as svc

    service = svc.AttachmentService(db=_FakeDB(_FakeStorageConfig()))
    return svc, service


def test_fails_closed_on_decrypt_error(monkeypatch):
    from app.core.encryption import ConfigDecryptionError

    svc, service = _make_service(monkeypatch)

    def _boom(_config):
        raise ConfigDecryptionError("access_key_id")

    monkeypatch.setattr(svc, "decrypt_config", _boom)

    with pytest.raises(ConfigDecryptionError):
        service._get_effective_storage_config(user_id="u1", storage_id="cfg-1")


def test_returns_decrypted_config_on_success(monkeypatch):
    svc, service = _make_service(monkeypatch)

    def _ok(config):
        return {**config, "access_key_id": "PLAINTEXT-KEY"}

    monkeypatch.setattr(svc, "decrypt_config", _ok)

    result = service._get_effective_storage_config(user_id="u1", storage_id="cfg-1")
    assert result is not None
    assert result["provider"] == "aliyun-oss"
    assert result["config"]["access_key_id"] == "PLAINTEXT-KEY"
    # Never the ciphertext.
    assert not result["config"]["access_key_id"].startswith("gAAAAA")
