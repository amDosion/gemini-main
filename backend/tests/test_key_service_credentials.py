"""Fail-closed credential handling for the standalone Key Service (S1 + S3).

S1 (HIGH): KEY_SERVICE_CLIENT_TOKEN / ADMIN_VIEW_KEY_PASSWORD defaulted to
well-known values ('default_token_change_me' / 'default_password_change_me'),
letting any local process read ENCRYPTION_KEY / JWT_SECRET_KEY off the socket.
S3 (MEDIUM): the admin password was verified with bare unsalted SHA-256.

Contract: credential resolution must fail closed when the env vars are unset,
empty, the insecure defaults, or too short; and the admin password must be
verified with a salted adaptive hash (bcrypt), not SHA-256.
"""

import pytest

from app.key.key_service import (
    KeyServiceConfigError,
    hash_admin_password,
    resolve_key_service_credentials,
    verify_admin_password,
)

STRONG_TOKEN = "k7f3Q9zR2pL8wX1vB4nM6tH0"  # 24 chars
STRONG_PASSWORD = "S0me-Str0ng-Admin-Pass!"


def test_missing_credentials_fail_closed():
    with pytest.raises(KeyServiceConfigError):
        resolve_key_service_credentials({})


def test_insecure_defaults_are_rejected():
    env = {
        "KEY_SERVICE_CLIENT_TOKEN": "default_token_change_me",
        "ADMIN_VIEW_KEY_PASSWORD": "default_password_change_me",
    }
    with pytest.raises(KeyServiceConfigError):
        resolve_key_service_credentials(env)


def test_too_short_credentials_rejected():
    env = {
        "KEY_SERVICE_CLIENT_TOKEN": "short",
        "ADMIN_VIEW_KEY_PASSWORD": "short",
    }
    with pytest.raises(KeyServiceConfigError):
        resolve_key_service_credentials(env)


def test_strong_credentials_resolve_to_bcrypt_hash():
    env = {
        "KEY_SERVICE_CLIENT_TOKEN": STRONG_TOKEN,
        "ADMIN_VIEW_KEY_PASSWORD": STRONG_PASSWORD,
    }
    client_token, admin_hash = resolve_key_service_credentials(env)
    assert client_token == STRONG_TOKEN
    # S3: must be a salted bcrypt hash, NOT a 64-hex SHA-256 digest.
    assert admin_hash.startswith("$2")
    assert len(admin_hash) != 64


def test_admin_password_verification_roundtrip():
    admin_hash = hash_admin_password(STRONG_PASSWORD)
    assert verify_admin_password(STRONG_PASSWORD, admin_hash) is True
    assert verify_admin_password("wrong-password", admin_hash) is False
    # The old insecure default must never authenticate.
    assert verify_admin_password("default_password_change_me", admin_hash) is False
