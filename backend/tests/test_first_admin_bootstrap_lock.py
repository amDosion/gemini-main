"""W02R-002: the first-admin bootstrap must be serialized so two concurrent
registrations on an empty instance cannot both be granted admin (CWE-362).

On PostgreSQL this is enforced with a transaction-scoped advisory lock held
across the count->insert->commit critical section; on SQLite writers are already
serialized so no lock is issued. These tests pin that serialization mechanism.
"""

from types import SimpleNamespace

from app.services.common.auth_service import AuthService


def _service_with_dialect(name, calls):
    svc = AuthService.__new__(AuthService)
    svc.db = SimpleNamespace(
        bind=SimpleNamespace(dialect=SimpleNamespace(name=name)),
        execute=lambda *a, **k: calls.append((a, k)),
    )
    return svc


def test_advisory_lock_acquired_on_postgres():
    calls = []
    svc = _service_with_dialect("postgresql", calls)
    svc._acquire_first_admin_bootstrap_lock()
    assert len(calls) == 1
    assert "pg_advisory_xact_lock" in str(calls[0][0][0])


def test_no_lock_on_sqlite():
    calls = []
    svc = _service_with_dialect("sqlite", calls)
    svc._acquire_first_admin_bootstrap_lock()
    assert calls == []


def test_no_lock_when_bind_missing():
    calls = []
    svc = AuthService.__new__(AuthService)
    svc.db = SimpleNamespace(bind=None, execute=lambda *a, **k: calls.append(1))
    svc._acquire_first_admin_bootstrap_lock()
    assert calls == []
