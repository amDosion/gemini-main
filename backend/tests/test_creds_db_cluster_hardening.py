"""Hardening contracts for the credential / DB-session cluster (creds-db).

Covers three verified findings:

A2 (HIGH) — ``ProviderCredentialsResolver.resolve`` is ``async`` but runs SYNC
SQLAlchemy ORM calls inline, blocking the event loop. The blocking ORM work
must run off the event-loop thread (via ``run_in_executor`` / ``to_thread``),
while the public async signature and return shape stay identical.

V-S7 (MEDIUM) — ``user_context._is_access_token_active_in_db`` swallowed *any*
exception (including transient DB errors) as a plain ``False`` with no signal,
turning a DB blip into a silent 401; and ``database.py`` set no connect timeout.
A ``SQLAlchemyError`` must be logged (distinguished from an invalid token) and
the sync engine must carry ``connect_args={"connect_timeout": ...}``.

V-S3 (LOW) — ``credential_manager.get_provider_credentials`` logged a
request-supplied api_key override at INFO with no user scoping or redaction.
The override must be logged at WARNING with user_id + provider + last-4 only,
never the full key.
"""

import asyncio
import logging
import threading
from types import SimpleNamespace
from typing import Optional

import pytest
from sqlalchemy.exc import OperationalError

from app.core import credential_manager, database, user_context
from app.services.llm.credentials_resolver import ProviderCredentialsResolver


# ---------------------------------------------------------------------------
# A2 — async resolve() must not block the event loop with sync ORM calls
# ---------------------------------------------------------------------------


class _RecordingQuery:
    """Minimal stand-in for an ORM query chain that records its thread.

    ``first_result`` is returned by ``.first()`` and ``all_result`` by ``.all()``
    so a single fake can model both the scalar lookups used by
    ``get_provider_credentials`` and the list lookups used by the fallback path.
    """

    def __init__(self, recorder, first_result=None, all_result=None):
        self._recorder = recorder
        self._first_result = first_result
        self._all_result = all_result if all_result is not None else []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        self._recorder.append(threading.current_thread())
        return self._first_result

    def all(self):
        self._recorder.append(threading.current_thread())
        return self._all_result


class _FakeProfile:
    def __init__(self, provider_id: str, api_key: str, base_url: Optional[str]):
        self.id = "profile-1"
        self.provider_id = provider_id
        self.user_id = "user-1"
        self.api_key = api_key
        self.base_url = base_url
        self.name = "test-profile"


class _FakeDB:
    """Records the executing thread of every ORM query call."""

    def __init__(self, query_thread_recorder, profile):
        self._recorder = query_thread_recorder
        self._profile = profile

    def query(self, model):
        return _RecordingQuery(self._recorder, first_result=self._profile)


def test_resolve_explicit_profile_runs_orm_off_event_loop():
    """The sync ORM ``.first()`` must execute on a worker thread, not the loop."""
    # Plaintext key path: decrypt_api_key returns it unchanged in silent mode.
    profile = _FakeProfile(provider_id="openai", api_key="sk-plaintext", base_url="https://x")
    recorder: list = []
    fake_db = _FakeDB(recorder, profile)

    resolver = ProviderCredentialsResolver()

    async def _run():
        loop_thread = threading.current_thread()
        api_key, base_url = await resolver.resolve(
            provider_id="openai",
            db=fake_db,
            user_id="user-1",
            profile_id="profile-1",
        )
        return loop_thread, api_key, base_url

    loop_thread, api_key, base_url = asyncio.run(_run())

    assert recorder, "ORM query was never executed"
    assert all(t is not loop_thread for t in recorder), (
        "blocking ORM call ran on the event-loop thread; it must be offloaded "
        "via run_in_executor/to_thread"
    )
    # Return shape must be preserved.
    assert api_key == "sk-plaintext"
    assert base_url == "https://x"


def test_resolve_base_provider_fallback_runs_orm_off_event_loop():
    """The HTTPException fallback path also offloads its sync ORM work."""
    profile = _FakeProfile(provider_id="openai", api_key="sk-fallback", base_url=None)
    recorder: list = []

    class _FallbackDB:
        def query(self, model):
            # get_provider_credentials uses .first() and must find NOTHING so it
            # raises HTTPException and the resolver enters the fallback path,
            # which uses .all() to collect matching profiles.
            from app.models.db_models import UserSettings

            if model is UserSettings:
                return _RecordingQuery(recorder, first_result=None)
            # ConfigProfile: .first() -> None (no active/any match in cred-manager),
            # .all() -> [profile] (fallback prefix lookup succeeds).
            return _RecordingQuery(recorder, first_result=None, all_result=[profile])

    resolver = ProviderCredentialsResolver()

    async def _run():
        return threading.current_thread(), await resolver.resolve(
            provider_id="openai",
            db=_FallbackDB(),
            user_id="user-1",
            profile_id=None,
        )

    loop_thread, (api_key, base_url) = asyncio.run(_run())

    assert recorder, "fallback ORM query was never executed"
    assert all(t is not loop_thread for t in recorder), (
        "fallback blocking ORM call ran on the event-loop thread"
    )
    assert api_key == "sk-fallback"


# ---------------------------------------------------------------------------
# V-S7 — DB errors must not be silently swallowed as a plain False
# ---------------------------------------------------------------------------


def test_db_engine_has_connect_timeout():
    """The sync engine must configure a bounded connect timeout."""
    connect_args = database.engine_kwargs.get("connect_args")
    assert isinstance(connect_args, dict), "engine_kwargs must carry connect_args"
    assert "connect_timeout" in connect_args, "connect_args must set connect_timeout"
    assert isinstance(connect_args["connect_timeout"], int)
    assert connect_args["connect_timeout"] > 0


def test_transient_db_error_is_logged_not_silently_false(monkeypatch, caplog):
    """A SQLAlchemyError during token validation must be logged (not swallowed)."""

    class _BoomDB:
        def query(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self):
            pass

    monkeypatch.setattr(user_context, "SessionLocal", lambda: _BoomDB())

    with caplog.at_level(logging.ERROR, logger=user_context.logger.name):
        result = user_context._is_access_token_active_in_db("user-1", "tok")

    # Fail-closed is preserved (still returns False) ...
    assert result is False
    # ... but the transient DB error must be surfaced in logs, not silenced.
    db_error_logged = any(
        record.levelno >= logging.ERROR
        and (
            "SQLAlchemy" in record.getMessage()
            or "数据库" in record.getMessage()
            or "database" in record.getMessage().lower()
        )
        for record in caplog.records
    )
    assert db_error_logged, "a transient DB error must be logged at ERROR level"


def test_invalid_token_returns_false_without_db_error_log(monkeypatch, caplog):
    """A genuinely invalid token (user missing) is a normal False, not an error."""

    class _NoUserQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class _NoUserDB:
        def query(self, *args, **kwargs):
            return _NoUserQuery()

        def close(self):
            pass

    monkeypatch.setattr(user_context, "SessionLocal", lambda: _NoUserDB())

    with caplog.at_level(logging.ERROR, logger=user_context.logger.name):
        result = user_context._is_access_token_active_in_db("ghost", "tok")

    assert result is False
    # No ERROR-level DB failure should be logged for an ordinary invalid token.
    assert not any(record.levelno >= logging.ERROR for record in caplog.records)


def test_user_context_narrows_to_sqlalchemy_error(monkeypatch):
    """A non-DB bug must NOT be swallowed as False (bare except removed)."""

    class _ValueErrorDB:
        def query(self, *args, **kwargs):
            raise ValueError("programming bug, not a DB outage")

        def close(self):
            pass

    monkeypatch.setattr(user_context, "SessionLocal", lambda: _ValueErrorDB())

    with pytest.raises(ValueError):
        user_context._is_access_token_active_in_db("user-1", "tok")


# ---------------------------------------------------------------------------
# V-S3 — request api_key override must be logged at WARNING, redacted
# ---------------------------------------------------------------------------


def test_request_api_key_override_logged_warning_redacted(caplog):
    full_key = "sk-ABCDEFGHIJKLMNOP1234WXYZ"
    last4 = full_key[-4:]

    with caplog.at_level(logging.WARNING, logger=credential_manager.logger.name):
        api_key, base_url = asyncio.run(
            credential_manager.get_provider_credentials(
                provider="openai",
                db=None,
                user_id="user-42",
                request_api_key=full_key,
                request_base_url="https://override",
            )
        )

    assert api_key == full_key  # behavior preserved
    assert base_url == "https://override"

    override_records = [
        r
        for r in caplog.records
        if "request" in r.getMessage().lower() or "override" in r.getMessage().lower()
    ]
    assert override_records, "override must be logged"
    rec = override_records[0]
    # WARNING level, with user scope + provider + redacted last-4, never full key.
    assert rec.levelno == logging.WARNING
    msg = rec.getMessage()
    assert "user-42" in msg
    assert "openai" in msg
    assert full_key not in msg, "the full api_key must never be logged"
    assert last4 in msg, "the last-4 of the key should be logged for traceability"
