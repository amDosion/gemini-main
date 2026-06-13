from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import require_current_user
from app.models.db_models import ConfigProfile, UserSettings
from app.routers.user import profiles

USER_ID = "user-profile-contract"


def _add_profile(
    db,
    *,
    profile_id: str = "profile-1",
    provider_id: str = "google",
    api_key: str = "encrypted",
) -> ConfigProfile:
    profile = ConfigProfile(
        id=profile_id,
        user_id=USER_ID,
        name=provider_id.title(),
        provider_id=provider_id,
        api_key=api_key,
        base_url="",
        protocol="google",
        is_proxy=False,
        hidden_models=[],
        cached_model_count=0,
        saved_models=[],
        created_at=1,
        updated_at=1,
    )
    db.add(profile)
    db.commit()
    return profile


def _make_client(db):
    app = FastAPI()
    app.include_router(profiles.router)
    app.dependency_overrides[require_current_user] = lambda: USER_ID
    app.dependency_overrides[get_db] = lambda: db
    return app, TestClient(app)


def test_encrypt_api_key_error_log_is_summarized(monkeypatch, caplog):
    secret = "profile-encrypt-secret"

    def _boom(value):
        raise RuntimeError(f"encrypt failed {secret}")

    monkeypatch.setattr(profiles, "encrypt_data", _boom)
    with caplog.at_level(logging.ERROR, logger=profiles.logger.name):
        try:
            profiles._encrypt_api_key("plain-key")
        except RuntimeError:
            pass

    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_profiles_edit_mode_decrypt_error_log_is_summarized(monkeypatch, caplog):
    secret = "profile-decrypt-secret"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    app, client = _make_client(db)

    def _boom(value, *, silent):
        raise RuntimeError(f"decrypt failed {secret}")

    monkeypatch.setattr(profiles, "decrypt_api_key", _boom)

    try:
        _add_profile(db, api_key="encrypted-value")
        with caplog.at_level(logging.WARNING, logger=profiles.logger.name):
            response = client.get("/api/profiles?edit_mode=true")

        assert response.status_code == 200
        assert secret not in response.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_clear_config_cache_error_log_is_summarized(monkeypatch, caplog):
    secret = "profile-cache-secret"

    def _boom(*args, **kwargs):
        raise RuntimeError(f"cache failed {secret}")

    monkeypatch.setattr(profiles, "clear_config_cache", _boom)

    with caplog.at_level(logging.DEBUG, logger=profiles.logger.name):
        profiles._clear_config_cache_best_effort(user_id=USER_ID)

    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "<redacted error; length=" in caplog.text


def test_active_profile_roundtrip_and_delete_response():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()

    app, client = _make_client(db)

    try:
        profile = _add_profile(db)

        assert client.get("/api/active-profile").json() == {"id": None}

        set_resp = client.post("/api/active-profile", json={"id": profile.id})
        assert set_resp.status_code == 200
        assert set_resp.json() == {"id": profile.id, "success": True}

        assert client.get("/api/active-profile").json() == {"id": profile.id}

        delete_resp = client.delete(f"/api/profiles/{profile.id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json() == {"success": True}
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_active_profile_missing_id_still_uses_route_error():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()

    app, client = _make_client(db)

    try:
        resp = client.post("/api/active-profile", json={})

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Profile ID is required"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_profiles_list_and_full_settings_response_models():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    app, client = _make_client(db)

    try:
        active = _add_profile(db, profile_id="profile-1", provider_id="google")
        _add_profile(db, profile_id="profile-2", provider_id="tongyi", api_key="dashscope-key")
        db.add(UserSettings(user_id=USER_ID, active_profile_id=active.id))
        db.commit()

        list_resp = client.get("/api/profiles")
        assert list_resp.status_code == 200
        assert [item["id"] for item in list_resp.json()] == ["profile-1", "profile-2"]

        full_resp = client.get("/api/settings/full")
        assert full_resp.status_code == 200
        body = full_resp.json()
        assert body["active_profile_id"] == "profile-1"
        assert body["active_profile"]["id"] == "profile-1"
        assert body["dashscope_key"] == "dashscope-key"
        assert len(body["profiles"]) == 2
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_create_profile_response_model_and_request_bounds(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    app, client = _make_client(db)
    monkeypatch.setattr(profiles, "_encrypt_api_key", lambda value: f"enc:{value}")

    try:
        response = client.post(
            "/api/profiles",
            json={
                "id": "profile-new",
                "name": "OpenAI",
                "provider_id": "openai",
                "api_key": "secret",
                "base_url": "https://api.openai.example",
                "protocol": "openai",
                "hidden_models": ["model-hidden"],
                "cached_model_count": 1,
                "saved_models": [{"id": "gpt-test"}],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "profile-new"
        assert body["api_key"] == "enc:secret"
        assert body["cached_model_count"] == 1
        assert body["saved_models"] == [{"id": "gpt-test"}]

        oversized = client.post(
            "/api/profiles",
            json={
                "id": "profile-bad",
                "provider_id": "openai",
                "api_key": "x" * 4097,
            },
        )
        assert oversized.status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_create_profile_internal_error_is_generic(monkeypatch, caplog):
    secret = "profile-create-secret"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    app, client = _make_client(db)

    def _boom():
        raise RuntimeError(f"commit failed {secret}")

    monkeypatch.setattr(profiles, "_encrypt_api_key", lambda value: f"enc:{value}")
    monkeypatch.setattr(db, "commit", _boom)

    try:
        with caplog.at_level(logging.ERROR, logger=profiles.logger.name):
            response = client.post(
                "/api/profiles",
                json={
                    "id": "profile-new",
                    "name": "OpenAI",
                    "provider_id": "openai",
                    "api_key": "secret",
                },
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to save profile"
        assert secret not in response.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_delete_profile_internal_error_is_generic(monkeypatch, caplog):
    secret = "profile-delete-secret"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    app, client = _make_client(db)

    try:
        profile = _add_profile(db)

        def _boom():
            raise RuntimeError(f"delete failed {secret}")

        monkeypatch.setattr(db, "commit", _boom)
        with caplog.at_level(logging.ERROR, logger=profiles.logger.name):
            response = client.delete(f"/api/profiles/{profile.id}")

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to delete profile"
        assert secret not in response.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_set_active_profile_internal_error_is_generic(monkeypatch, caplog):
    secret = "profile-active-secret"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    app, client = _make_client(db)

    try:
        profile = _add_profile(db)

        def _boom():
            raise RuntimeError(f"active failed {secret}")

        monkeypatch.setattr(db, "commit", _boom)
        with caplog.at_level(logging.ERROR, logger=profiles.logger.name):
            response = client.post("/api/active-profile", json={"id": profile.id})

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to set active profile"
        assert secret not in response.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
