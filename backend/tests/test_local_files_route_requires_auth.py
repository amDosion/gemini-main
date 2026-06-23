"""Regression: the local-files media route must require authentication.

CANON-024 / W02R-011: GET /api/storage/local-files/{relative_path} served files
from the default local storage root with NO auth dependency and no per-object
ownership, so (with the optional global auth boundary off) anyone could read
other users' generated/uploaded media by path.

This round adds authentication (require_current_user) to the route. Same-origin
<img> requests still authenticate via the httpOnly access_token cookie, so media
display is unaffected; unauthenticated callers are rejected.

The route also rejects paths whose first segment is not the authenticated
user's normalized owner id, so sibling-user media is not resolved.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.storage import storage as storage_mod


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(storage_mod.router)
    return TestClient(app, raise_server_exceptions=False)


def test_local_files_route_requires_authentication():
    resp = _client().get("/api/storage/local-files/2026/05/31/some.png")
    assert resp.status_code == 401


def test_local_files_route_rejects_other_user_prefix(monkeypatch):
    client = _client()
    client.app.dependency_overrides[storage_mod.require_current_user] = lambda: "user-b"

    def _must_not_resolve(*args, **kwargs):
        raise AssertionError("other-user local URL must be rejected before path resolution")

    monkeypatch.setattr(storage_mod, "resolve_local_public_file_path", _must_not_resolve)

    resp = client.get("/api/storage/local-files/user-a/2026/05/31/some.png")
    assert resp.status_code == 404
