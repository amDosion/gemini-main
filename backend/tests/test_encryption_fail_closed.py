"""Audit finding core-4: encrypt_config must FAIL CLOSED.

Previously, if field encryption (or key retrieval) failed, encrypt_config silently
kept/returned the PLAINTEXT value — so a transient crypto/config error would store
provider credentials unencrypted in the DB. It must raise instead, so the caller
fails the save rather than persisting secrets in the clear.
"""

import pytest

from app.core import encryption


class _BoomFernet:
    def __init__(self, *args, **kwargs):
        pass

    def encrypt(self, data):  # field encryption fails
        raise RuntimeError("encrypt boom")

    def decrypt(self, data, *args, **kwargs):  # is_encrypted() -> False (plaintext)
        raise RuntimeError("decrypt boom")


def test_encrypt_config_raises_when_field_encryption_fails(monkeypatch):
    monkeypatch.setattr(encryption, "Fernet", _BoomFernet)
    with pytest.raises(Exception):
        encryption.encrypt_config({"token": "secret-plaintext-123"})


def test_encrypt_config_never_returns_plaintext_secret_on_failure(monkeypatch):
    monkeypatch.setattr(encryption, "Fernet", _BoomFernet)
    try:
        out = encryption.encrypt_config({"token": "secret-plaintext-123"})
    except Exception:
        return  # raised => fail-closed => correct
    assert out.get("token") != "secret-plaintext-123", "must not persist plaintext secret"


def test_encrypt_config_raises_on_key_retrieval_error(monkeypatch):
    def boom():
        raise RuntimeError("no key available")

    monkeypatch.setattr(encryption, "_get_encryption_key_bytes", boom)
    with pytest.raises(Exception):
        encryption.encrypt_config({"token": "secret-plaintext-123"})


def test_encrypt_config_encrypts_sensitive_field_on_happy_path():
    out = encryption.encrypt_config({"token": "secret-plaintext-123", "domain": "example.com"})
    assert out["domain"] == "example.com"  # non-sensitive unchanged
    assert out["token"] != "secret-plaintext-123"  # sensitive encrypted
    assert encryption.is_encrypted(out["token"])
