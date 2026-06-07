"""Regression: refresh-token rotation must fail closed.

W02R-001: AuthService.refresh_tokens only rejected an existing-and-revoked DB
row. A valid-signature refresh JWT with NO stored row (rotated away / cleaned
up) still minted fresh tokens, and an inactive account's refresh JWT was never
checked against account status -> server-side revocation/deactivation was
unenforceable at the refresh boundary.

refresh_tokens must require a stored, non-revoked refresh-token row AND an active
account before minting.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.jwt_utils import create_refresh_token
from app.models.db_models import RefreshToken, User
from app.services.common.auth_service import AuthService, InvalidTokenError


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_user(session, *, user_id="u-1", status="active"):
    user = User(id=user_id, email=f"{user_id}@example.com", password_hash="x", status=status)
    session.add(user)
    session.commit()
    return user


def _store_row(session, user_id, token):
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    session.commit()


_SENTINEL = object()


def _service_with_stubbed_minting(db_session, monkeypatch):
    # Isolate the refresh GATE under test from _create_tokens' real rotation
    # (create_refresh_token has no jti, so same-second rotation can collide on the
    # unique token_hash -- unrelated to this fix).
    svc = AuthService(db_session)
    monkeypatch.setattr(svc, "_create_tokens", lambda user_id: _SENTINEL)
    return svc


def test_refresh_with_missing_db_row_is_rejected(db_session, monkeypatch):
    _make_user(db_session)
    token = create_refresh_token("u-1")  # valid JWT, but no stored row
    svc = _service_with_stubbed_minting(db_session, monkeypatch)
    with pytest.raises(InvalidTokenError):
        svc.refresh_tokens(token)


def test_refresh_for_inactive_user_is_rejected(db_session, monkeypatch):
    _make_user(db_session, status="suspended")
    token = create_refresh_token("u-1")
    _store_row(db_session, "u-1", token)
    svc = _service_with_stubbed_minting(db_session, monkeypatch)
    with pytest.raises(InvalidTokenError):
        svc.refresh_tokens(token)


def test_refresh_with_valid_row_and_active_user_succeeds(db_session, monkeypatch):
    _make_user(db_session)
    token = create_refresh_token("u-1")
    _store_row(db_session, "u-1", token)
    svc = _service_with_stubbed_minting(db_session, monkeypatch)
    assert svc.refresh_tokens(token) is _SENTINEL
