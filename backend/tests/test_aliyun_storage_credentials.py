import types

import pytest
from cryptography.fernet import Fernet


_UNDECRYPTED_ACCESS_KEY_ID = (
    "gAAAAABdummyStorageStateAccessKeyIdCiphertextValueForRegressionOnly"
)
_UNDECRYPTED_ACCESS_KEY_SECRET = (
    "gAAAAABdummyStorageStateAccessKeySecretCiphertextValueForRegressionOnly"
)


@pytest.mark.asyncio
async def test_aliyun_upload_rejects_storage_state_credentials_before_oss_auth(monkeypatch):
    from app.services.storage import aliyun_provider

    auth_calls = []

    def fake_auth(access_key_id, access_key_secret):
        auth_calls.append((access_key_id, access_key_secret))
        return object()

    class Bucket:
        def put_object(self, *_args, **_kwargs):
            return types.SimpleNamespace(status=200)

    monkeypatch.setattr(aliyun_provider.oss2, "Auth", fake_auth)
    monkeypatch.setattr(
        aliyun_provider.oss2,
        "Bucket",
        lambda *_args, **_kwargs: Bucket(),
    )

    provider = aliyun_provider.AliyunProvider(
        {
            "access_key_id": _UNDECRYPTED_ACCESS_KEY_ID,
            "access_key_secret": _UNDECRYPTED_ACCESS_KEY_SECRET,
            "bucket": "bucket",
            "endpoint": "oss-cn.test.aliyuncs.com",
        }
    )

    result = await provider.upload("a.png", b"data", "image/png")

    assert result.success is False
    assert "storage_config_credentials_not_decrypted" in (result.error or "")
    assert auth_calls == []


def test_decrypt_config_fails_closed_for_fernet_storage_credentials_with_wrong_key(monkeypatch):
    from app.core import encryption

    stored_with_other_key = Fernet.generate_key()
    runtime_key = Fernet.generate_key()
    encrypted_access_key_id = (
        Fernet(stored_with_other_key).encrypt(b"dummy-access-key-id").decode("utf-8")
    )

    monkeypatch.setattr(encryption, "_get_encryption_key_bytes", lambda: runtime_key)

    with pytest.raises(ValueError) as exc_info:
        encryption.decrypt_config(
            {
                "access_key_id": encrypted_access_key_id,
                "access_key_secret": "dummy-access-key-secret",
                "bucket": "bucket",
                "endpoint": "oss-cn.test.aliyuncs.com",
            }
        )

    assert (
        getattr(exc_info.value, "code", None)
        == "storage_config_credentials_not_decrypted"
    )
    assert "access_key_id" in str(exc_info.value)
