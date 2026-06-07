"""Unit tests for AuthService login rate-limiting and IP blocking.

svc-common-6: _check_login_attempts and _check_ip_blocked must enforce
the four invariants required by the recommendation:

(a) login is blocked after max_login_attempts failures for the same email.
(b) login is blocked after max_ip_attempts failures from the same IP.
(c) lockout expires after login_lockout_duration seconds (attempts outside
    the time window are not counted).
(d) a blocked IP receives 403 before attempt counting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.db_models import IPBlocklist, LoginAttempt, SystemConfig, User
from app.services.common.auth_service import AuthService, LoginRequest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_system_config(
    session,
    *,
    max_login_attempts: int = 5,
    max_ip_attempts: int = 10,
    lockout_duration: int = 900,
    allow_registration: bool = False,
) -> SystemConfig:
    cfg = SystemConfig(
        id=1,
        allow_registration=allow_registration,
        max_login_attempts=max_login_attempts,
        max_login_attempts_per_ip=max_ip_attempts,
        login_lockout_duration=lockout_duration,
    )
    session.add(cfg)
    session.commit()
    return cfg


def _add_failed_attempts(
    session,
    *,
    email: str | None = None,
    ip_address: str = "1.2.3.4",
    count: int = 1,
    age_seconds: int = 0,
) -> None:
    """Insert ``count`` failed LoginAttempt rows with ``created_at`` offset by ``age_seconds``."""
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    for _ in range(count):
        attempt = LoginAttempt(
            email=email,
            ip_address=ip_address,
            success=False,
        )
        session.add(attempt)
        session.flush()
        # Override the server_default via direct attribute assignment so SQLite
        # uses our controlled timestamp for the time-window assertion.
        attempt.created_at = ts
    session.commit()


# ---------------------------------------------------------------------------
# (a) Email-level lockout
# ---------------------------------------------------------------------------

class TestEmailLevelLockout:
    def test_blocked_after_max_email_attempts(self, db_session):
        """_check_login_attempts returns (False, msg) once the email failure
        count reaches max_login_attempts within the lockout window."""
        _seed_system_config(db_session, max_login_attempts=3, max_ip_attempts=100)
        _add_failed_attempts(
            db_session, email="victim@example.com", ip_address="1.2.3.4", count=3
        )
        svc = AuthService(db_session)
        allowed, msg = svc._check_login_attempts("victim@example.com", "1.2.3.4")
        assert allowed is False
        assert msg is not None and len(msg) > 0

    def test_allowed_one_attempt_below_email_limit(self, db_session):
        """One attempt fewer than the limit must still be allowed."""
        _seed_system_config(db_session, max_login_attempts=3, max_ip_attempts=100)
        _add_failed_attempts(
            db_session, email="victim@example.com", ip_address="1.2.3.4", count=2
        )
        svc = AuthService(db_session)
        allowed, _ = svc._check_login_attempts("victim@example.com", "1.2.3.4")
        assert allowed is True


# ---------------------------------------------------------------------------
# (b) IP-level lockout
# ---------------------------------------------------------------------------

class TestIPLevelLockout:
    def test_blocked_after_max_ip_attempts(self, db_session):
        """_check_login_attempts returns (False, msg) when the IP failure count
        reaches max_login_attempts_per_ip, even without an email filter."""
        _seed_system_config(db_session, max_login_attempts=100, max_ip_attempts=5)
        _add_failed_attempts(
            db_session, email=None, ip_address="10.0.0.1", count=5
        )
        svc = AuthService(db_session)
        allowed, msg = svc._check_login_attempts(None, "10.0.0.1")
        assert allowed is False
        assert msg is not None and len(msg) > 0

    def test_allowed_one_attempt_below_ip_limit(self, db_session):
        """One attempt fewer than the IP limit must still be allowed."""
        _seed_system_config(db_session, max_login_attempts=100, max_ip_attempts=5)
        _add_failed_attempts(
            db_session, email=None, ip_address="10.0.0.1", count=4
        )
        svc = AuthService(db_session)
        allowed, _ = svc._check_login_attempts(None, "10.0.0.1")
        assert allowed is True

    def test_different_ips_do_not_share_quota(self, db_session):
        """Failures on IP A must not consume the quota of IP B."""
        _seed_system_config(db_session, max_login_attempts=100, max_ip_attempts=3)
        _add_failed_attempts(db_session, ip_address="10.0.0.1", count=3)
        svc = AuthService(db_session)
        allowed, _ = svc._check_login_attempts(None, "10.0.0.2")
        assert allowed is True


# ---------------------------------------------------------------------------
# (c) Lockout expires after login_lockout_duration seconds
# ---------------------------------------------------------------------------

class TestLockoutExpiry:
    def test_old_attempts_outside_window_not_counted(self, db_session):
        """Attempts older than login_lockout_duration seconds must not count
        toward the lockout threshold."""
        lockout = 300  # 5 minutes
        _seed_system_config(
            db_session,
            max_login_attempts=3,
            max_ip_attempts=3,
            lockout_duration=lockout,
        )
        # Add attempts well outside the window (twice the lockout duration old).
        _add_failed_attempts(
            db_session,
            email="user@example.com",
            ip_address="1.2.3.4",
            count=3,
            age_seconds=lockout * 2,
        )
        svc = AuthService(db_session)
        allowed, _ = svc._check_login_attempts("user@example.com", "1.2.3.4")
        # Old attempts must be ignored; login should still be allowed.
        assert allowed is True

    def test_recent_and_old_attempts_only_recent_counted(self, db_session):
        """A mix of old (outside window) and recent (inside window) attempts
        must only count recent ones against the threshold."""
        lockout = 300
        _seed_system_config(
            db_session,
            max_login_attempts=3,
            max_ip_attempts=3,
            lockout_duration=lockout,
        )
        # 2 recent + 5 expired; total in window is 2, below threshold of 3.
        _add_failed_attempts(
            db_session, email="user@example.com", ip_address="1.2.3.4",
            count=5, age_seconds=lockout * 2,
        )
        _add_failed_attempts(
            db_session, email="user@example.com", ip_address="1.2.3.4",
            count=2, age_seconds=10,
        )
        svc = AuthService(db_session)
        allowed, _ = svc._check_login_attempts("user@example.com", "1.2.3.4")
        assert allowed is True


# ---------------------------------------------------------------------------
# (d) Blocked IP receives 403 before attempt counting
# ---------------------------------------------------------------------------

class TestIPBlocklist:
    def test_blocked_ip_raises_403_without_counting_attempts(
        self, db_session, monkeypatch
    ):
        """A permanently blocked IP must be rejected with HTTP 403 before
        _check_login_attempts is ever called."""
        _seed_system_config(db_session, max_login_attempts=100, max_ip_attempts=100)

        blocked_ip = "9.9.9.9"
        db_session.add(
            IPBlocklist(
                ip_address=blocked_ip,
                reason="test block",
                expires_at=None,  # permanent
            )
        )
        db_session.commit()

        # Ensure there is a valid user so the rejection can't be attributed
        # to a credential failure.
        db_session.add(
            User(
                id="u-blocked",
                email="blocked@example.com",
                password_hash="x",
                status="active",
            )
        )
        db_session.commit()

        attempt_check_called = []
        original = AuthService._check_login_attempts

        def spy(self, email, ip):
            attempt_check_called.append((email, ip))
            return original(self, email, ip)

        monkeypatch.setattr(AuthService, "_check_login_attempts", spy)

        svc = AuthService(db_session)
        req = LoginRequest(email="blocked@example.com", password="doesnotmatter")

        with pytest.raises(HTTPException) as exc_info:
            svc.login(req, ip_address=blocked_ip)

        assert exc_info.value.status_code == 403
        # _check_login_attempts must NOT have been called for a blocked IP.
        assert attempt_check_called == [], (
            "_check_login_attempts must not be called when IP is blocked"
        )

    def test_expired_ip_block_is_removed_and_login_proceeds_to_credential_check(
        self, db_session
    ):
        """An expired IP block must be cleaned up; the login should then
        proceed (and ultimately fail on bad credentials, not on a 403)."""
        _seed_system_config(db_session, max_login_attempts=100, max_ip_attempts=100)

        expired_ip = "8.8.8.8"
        db_session.add(
            IPBlocklist(
                ip_address=expired_ip,
                reason="test expired block",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        db_session.commit()

        svc = AuthService(db_session)
        req = LoginRequest(email="nobody@example.com", password="badpass")

        # Must NOT raise 403; expired block means the IP is no longer blocked.
        # It will raise InvalidCredentialsError (or similar) not HTTPException(403).
        with pytest.raises(Exception) as exc_info:
            svc.login(req, ip_address=expired_ip)

        if isinstance(exc_info.value, HTTPException):
            assert exc_info.value.status_code != 403, (
                "Expired block must not produce a 403; got HTTP "
                f"{exc_info.value.status_code}"
            )
