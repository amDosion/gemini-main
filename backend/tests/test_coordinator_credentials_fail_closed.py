"""Fail-closed contract for Gemini coordinator credential-resolution paths.

Regression guard for the residual V-S2 fail-open class living in the provider
credential paths of the Gemini coordinators and the Vertex AI config router.

THE BUG: these paths gated decryption on ``is_encrypted()`` (or returned the
raw value on any failure). ``is_encrypted()`` swallows ``InvalidToken`` on an
ENCRYPTION_KEY mismatch and returns ``False``, so the raw Fernet ciphertext was
forwarded straight to the Vertex AI / Gemini provider SDK as
``vertex_ai_credentials_json`` or as the API key.

CONTRACT under test: on an ENCRYPTION_KEY mismatch, no coordinator / router
credential path may ever return or forward Fernet ciphertext. It must resolve
to an empty / absent credential (fail-closed) so the SDK receives nothing
usable instead of someone else's (undecryptable) ciphertext.

Each test encrypts under KEY_A, rotates ENCRYPTION_KEY to KEY_B, drives the
real resolution path, and asserts the result is NOT the gAAAA... ciphertext.
"""

from __future__ import annotations

import types

import pytest
from cryptography.fernet import Fernet

from app.core.encryption import encrypt_data, looks_like_fernet_token
from app.services.gemini.coordinators import _config_cache

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()

CREDS_PLAINTEXT = '{"type":"service_account","project_id":"p","private_key":"k"}'
API_KEY_PLAINTEXT = "AIzaSyRealPlaintextGoogleKey"


def _assert_no_ciphertext(value) -> None:
    """A provider SDK must never receive Fernet ciphertext."""
    if value is None or value == "":
        return
    assert not str(value).startswith("gAAAAA"), (
        f"fail-open: ciphertext forwarded to SDK: {str(value)[:24]}..."
    )
    assert not looks_like_fernet_token(str(value)), (
        "fail-open: Fernet-shaped token forwarded to SDK"
    )


@pytest.fixture(autouse=True)
def _clear_config_cache():
    _config_cache.clear_config_cache()
    yield
    _config_cache.clear_config_cache()


@pytest.fixture
def creds_cipher_under_key_a(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", KEY_A)
    token = encrypt_data(CREDS_PLAINTEXT)
    assert looks_like_fernet_token(token)
    return token


@pytest.fixture
def api_key_cipher_under_key_a(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", KEY_A)
    token = encrypt_data(API_KEY_PLAINTEXT)
    assert looks_like_fernet_token(token)
    return token


class _Result:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self._row

    def all(self):
        return [self._row] if self._row is not None else []


class _FakeDB:
    """Maps an ORM model class -> the row object its query should return."""

    def __init__(self, rows_by_model):
        self._rows_by_model = rows_by_model

    def query(self, model):
        return _Result(self._rows_by_model.get(model))


def _vertex_row(cipher):
    return types.SimpleNamespace(
        api_mode="vertex_ai",
        vertex_ai_project_id="proj-123",
        vertex_ai_location="us-central1",
        vertex_ai_credentials_json=cipher,
    )


def _google_profile_row(cipher):
    return types.SimpleNamespace(
        provider_id="google",
        api_key=cipher,
        updated_at=0,
        id="profile-1",
    )


# ----------------------- VideoUnderstandingCoordinator -----------------------

def test_video_understanding_vertex_creds_fail_closed(monkeypatch, creds_cipher_under_key_a):
    from app.models.db_models import VertexAIConfig
    from app.services.gemini.coordinators.video_understanding_coordinator import (
        VideoUnderstandingCoordinator,
    )

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB({VertexAIConfig: _vertex_row(creds_cipher_under_key_a)})
    coord = VideoUnderstandingCoordinator(user_id="u1", db=db)
    _assert_no_ciphertext(coord._config.get("vertex_ai_credentials_json"))


def test_video_understanding_api_key_fail_closed(monkeypatch, api_key_cipher_under_key_a):
    from app.models.db_models import ConfigProfile, VertexAIConfig
    from app.services.gemini.coordinators.video_understanding_coordinator import (
        VideoUnderstandingCoordinator,
    )

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB(
        {
            VertexAIConfig: types.SimpleNamespace(
                api_mode="gemini_api",
                vertex_ai_project_id=None,
                vertex_ai_location=None,
                vertex_ai_credentials_json=None,
            ),
            ConfigProfile: _google_profile_row(api_key_cipher_under_key_a),
        }
    )
    coord = VideoUnderstandingCoordinator(user_id="u1", db=db)
    _assert_no_ciphertext(coord._config.get("gemini_api_key"))


# ------------------------ VideoGenerationCoordinator -------------------------

def test_video_generation_vertex_creds_fail_closed(monkeypatch, creds_cipher_under_key_a):
    from app.models.db_models import VertexAIConfig
    from app.services.gemini.coordinators.video_generation_coordinator import (
        VideoGenerationCoordinator,
    )

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB({VertexAIConfig: _vertex_row(creds_cipher_under_key_a)})
    coord = VideoGenerationCoordinator(user_id="u1", db=db)
    _assert_no_ciphertext(coord._config.get("vertex_ai_credentials_json"))


def test_video_generation_api_key_fail_closed(monkeypatch, api_key_cipher_under_key_a):
    from app.models.db_models import ConfigProfile, UserSettings, VertexAIConfig
    from app.services.gemini.coordinators.video_generation_coordinator import (
        VideoGenerationCoordinator,
    )

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB(
        {
            VertexAIConfig: types.SimpleNamespace(
                api_mode="gemini_api",
                vertex_ai_project_id=None,
                vertex_ai_location=None,
                vertex_ai_credentials_json=None,
            ),
            UserSettings: types.SimpleNamespace(active_profile_id=None),
            ConfigProfile: _google_profile_row(api_key_cipher_under_key_a),
        }
    )
    coord = VideoGenerationCoordinator(user_id="u1", db=db)
    _assert_no_ciphertext(coord._config.get("gemini_api_key"))


# ------------------------------ ImagenCoordinator ----------------------------

def test_imagen_api_key_fail_closed(monkeypatch, api_key_cipher_under_key_a):
    from app.models.db_models import ConfigProfile, VertexAIConfig
    from app.services.gemini.coordinators.imagen_coordinator import ImagenCoordinator

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB(
        {
            VertexAIConfig: types.SimpleNamespace(
                api_mode="gemini_api",
                vertex_ai_project_id=None,
                vertex_ai_location=None,
                vertex_ai_credentials_json=None,
            ),
            ConfigProfile: _google_profile_row(api_key_cipher_under_key_a),
        }
    )
    coord = ImagenCoordinator(user_id="u1", db=db)
    _assert_no_ciphertext(coord._config.get("gemini_api_key"))


# ---------------------------- ImageEditCoordinator ---------------------------

def test_image_edit_api_key_fail_closed(monkeypatch, api_key_cipher_under_key_a):
    from app.models.db_models import ConfigProfile, VertexAIConfig
    from app.services.gemini.coordinators.image_edit_coordinator import (
        ImageEditCoordinator,
    )

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB(
        {
            VertexAIConfig: types.SimpleNamespace(
                api_mode="gemini_api",
                vertex_ai_project_id=None,
                vertex_ai_location=None,
                vertex_ai_credentials_json=None,
            ),
            ConfigProfile: _google_profile_row(api_key_cipher_under_key_a),
        }
    )
    coord = ImageEditCoordinator(user_id="u1", db=db)
    _assert_no_ciphertext(coord._config.get("gemini_api_key"))


# ----------------------- google_service tryon vertex path --------------------

def test_google_service_tryon_vertex_creds_fail_closed(monkeypatch, creds_cipher_under_key_a):
    from app.models.db_models import VertexAIConfig
    from app.services.gemini.google_service import GoogleService

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    db = _FakeDB({VertexAIConfig: _vertex_row(creds_cipher_under_key_a)})
    fake_self = types.SimpleNamespace(user_id="u1", db=db)
    project_id, location, credentials_json = (
        GoogleService._resolve_vertex_config_for_tryon(fake_self)
    )
    _assert_no_ciphertext(credentials_json)


# --------------------------- vertex_ai_config router -------------------------

@pytest.mark.asyncio
async def test_router_get_google_api_key_active_profile_fail_closed(
    monkeypatch, api_key_cipher_under_key_a
):
    from app.models.db_models import ConfigProfile, UserSettings
    from app.routers.models.vertex_ai_config import _get_google_api_key

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    profile = _google_profile_row(api_key_cipher_under_key_a)
    db = _FakeDB(
        {
            UserSettings: types.SimpleNamespace(active_profile_id="profile-1"),
            ConfigProfile: profile,
        }
    )
    result = await _get_google_api_key(db, "u1")
    _assert_no_ciphertext(result)


@pytest.mark.asyncio
async def test_router_get_google_api_key_fallback_profile_fail_closed(
    monkeypatch, api_key_cipher_under_key_a
):
    from app.models.db_models import ConfigProfile, UserSettings
    from app.routers.models.vertex_ai_config import _get_google_api_key

    monkeypatch.setenv("ENCRYPTION_KEY", KEY_B)
    profile = _google_profile_row(api_key_cipher_under_key_a)
    db = _FakeDB(
        {
            UserSettings: types.SimpleNamespace(active_profile_id=None),
            ConfigProfile: profile,
        }
    )
    result = await _get_google_api_key(db, "u1")
    _assert_no_ciphertext(result)
