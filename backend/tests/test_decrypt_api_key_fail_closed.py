"""Fail-closed contract for decrypt_api_key (LLM-provider credential path).

Regression guard for verified finding V-S2: on an ENCRYPTION_KEY mismatch,
``is_encrypted()`` swallows the ``InvalidToken`` and returns ``False`` so the
old ``decrypt_api_key`` returned the raw Fernet ciphertext, which callers then
forwarded as a live API key to OpenAI/Tongyi/Google/Ollama SDKs.

The contract under test: decrypt_api_key MUST NEVER return Fernet ciphertext.
It either returns plaintext (matching key / plaintext input) or fails closed
(empty string in silent mode, ConfigDecryptionError otherwise).
"""

import pytest
from cryptography.fernet import Fernet

from app.core.encryption import (
    ConfigDecryptionError,
    decrypt_api_key,
    encrypt_data,
    looks_like_fernet_token,
)

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()
PLAINTEXT = "sk-super-secret-provider-key-123"


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
