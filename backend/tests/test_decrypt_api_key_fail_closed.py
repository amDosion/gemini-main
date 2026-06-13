"""Fail-closed contract for decrypt_api_key (LLM-provider credential path).

Regression guard for verified finding V-S2: on an ENCRYPTION_KEY mismatch,
``is_encrypted()`` swallows the ``InvalidToken`` and returns ``False`` so the
old ``decrypt_api_key`` returned the raw Fernet ciphertext, which callers then
forwarded as a live API key to OpenAI/Tongyi/Google/Ollama SDKs.

The contract under test: decrypt_api_key MUST NEVER return Fernet ciphertext.
It either returns plaintext (matching key / plaintext input) or fails closed
(empty string in silent mode, ConfigDecryptionError otherwise).
"""

import logging

import pytest
from cryptography.fernet import Fernet

from app.core import encryption
from app.core.encryption import (
    ConfigDecryptionError,
    EncryptionKeyManager,
    decrypt_api_key,
    encrypt_data,
    looks_like_fernet_token,
)

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()
PLAINTEXT = "sk-super-secret-provider-key-123"


def _raise_runtime(message: str):
    raise RuntimeError(message)


@pytest.fixture
def ciphertext_under_key_a(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", KEY_A)
    token = encrypt_data(PLAINTEXT)
    assert looks_like_fernet_token(token), "fixture must produce a Fernet token"
    return token


def test_key_mismatch_silent_never_returns_ciphertext(monkeypatch, ciphertext_under_key_a):
    # Rotate to a non-matching key (e.g. operator changed ENCRYPTION_KEY).
    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    result = decrypt_api_key(ciphertext_under_key_a, silent=True)
    # The cardinal rule: a provider SDK must never receive Fernet ciphertext.
    assert result != ciphertext_under_key_a
    assert not result.startswith("gAAAAA")
    assert not looks_like_fernet_token(result)


def test_key_mismatch_non_silent_raises(monkeypatch, ciphertext_under_key_a):
    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    with pytest.raises(ConfigDecryptionError):
        decrypt_api_key(ciphertext_under_key_a, silent=False)


def test_round_trip_with_matching_key(ciphertext_under_key_a):
    # Key stays KEY_A (set by the fixture) -> genuine decryption.
    assert decrypt_api_key(ciphertext_under_key_a, silent=True) == PLAINTEXT


def test_plaintext_key_passthrough(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", KEY_A)
    assert decrypt_api_key(PLAINTEXT, silent=True) == PLAINTEXT
    assert decrypt_api_key("AIzaSyExamplePlaintextGoogleKey", silent=True) == (
        "AIzaSyExamplePlaintextGoogleKey"
    )
    assert decrypt_api_key("", silent=True) == ""


def test_encrypt_data_error_log_is_summarized(monkeypatch, caplog):
    secret = "encrypt-log-secret"
    monkeypatch.setattr(
        encryption,
        "_get_encryption_key_bytes",
        lambda: _raise_runtime(f"key load failed {secret}"),
    )

    with caplog.at_level(logging.ERROR, logger=encryption.logger.name):
        with pytest.raises(RuntimeError):
            encryption.encrypt_data("plain-secret")

    assert secret not in caplog.text
    assert "plain-secret" not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_decrypt_data_key_error_log_is_summarized(monkeypatch, caplog):
    secret = "decrypt-log-secret"
    monkeypatch.setattr(
        encryption,
        "_get_encryption_key_bytes",
        lambda: (_ for _ in ()).throw(ValueError(f"missing key {secret}")),
    )

    with caplog.at_level(logging.ERROR, logger=encryption.logger.name):
        with pytest.raises(ValueError):
            encryption.decrypt_data("ciphertext-secret", silent=False)

    assert secret not in caplog.text
    assert "ciphertext-secret" not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_encrypt_config_error_log_is_summarized(monkeypatch, caplog):
    secret = "config-encrypt-log-secret"
    monkeypatch.setattr(
        encryption,
        "_get_encryption_key_bytes",
        lambda: _raise_runtime(f"config key failed {secret}"),
    )

    with caplog.at_level(logging.ERROR, logger=encryption.logger.name):
        with pytest.raises(RuntimeError):
            encryption.encrypt_config({"api_key": "plain-api-key-secret"})

    assert secret not in caplog.text
    assert "plain-api-key-secret" not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_dead_file_key_persistence_methods_are_removed():
    """File-based ENCRYPTION_KEY persistence was unreferenced dead code.

    The key is sourced only from the environment (``get_or_create_key``); the
    old ``save_key`` / ``load_key_from_file`` helpers had zero callers and are
    removed. Guard against their reintroduction to keep the key off disk.
    """
    assert not hasattr(EncryptionKeyManager, "save_key")
    assert not hasattr(EncryptionKeyManager, "load_key_from_file")
    # The intentionally-retained surface stays available.
    assert hasattr(EncryptionKeyManager, "generate_key")
    assert hasattr(EncryptionKeyManager, "get_or_create_key")
