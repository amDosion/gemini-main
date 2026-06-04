"""always_convert_response: app-owned large endpoints stay camelCase past 2 MiB.

The middleware passes responses larger than MAX_RESPONSE_CONVERSION_BYTES through
UNCONVERTED (snake_case) as a memory safety valve. For app-owned unpaginated
endpoints (/sessions, /api/agents, /api/agents/available-models) that can exceed
the threshold, that means the frontend would receive snake_case and break.

case_conversion_options(always_convert_response=True) opts an endpoint out of the
oversized passthrough so it is ALWAYS converted -> the frontend never converts.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import case_conversion_middleware as ccm
from app.middleware.case_conversion_middleware import (
    CaseConversionMiddleware,
    CaseConversionOptions,
    case_conversion_options,
)


def _make_app():
    app = FastAPI()
    app.add_middleware(CaseConversionMiddleware)

    @app.get("/big-default")
    async def big_default():
        return {"some_snake_key": "x" * 200, "another_key": 1}

    @app.get("/big-forced")
    @case_conversion_options(always_convert_response=True)
    async def big_forced():
        return {"some_snake_key": "x" * 200, "another_key": 1}

    return app


def test_default_endpoint_passes_through_oversized_as_snake(monkeypatch):
    monkeypatch.setattr(ccm, "MAX_RESPONSE_CONVERSION_BYTES", 50)
    client = TestClient(_make_app())
    data = client.get("/big-default").json()
    # > threshold and not opted-in -> passthrough -> stays snake_case
    assert "some_snake_key" in data
    assert "someSnakeKey" not in data


def test_forced_endpoint_converts_even_when_oversized(monkeypatch):
    monkeypatch.setattr(ccm, "MAX_RESPONSE_CONVERSION_BYTES", 50)
    client = TestClient(_make_app())
    data = client.get("/big-forced").json()
    # > threshold but opted-in -> still converted -> camelCase
    assert "someSnakeKey" in data
    assert "some_snake_key" not in data


def test_forced_endpoint_still_converts_when_small(monkeypatch):
    # below threshold: normal conversion path, must also be camelCase
    client = TestClient(_make_app())
    data = client.get("/big-forced").json()
    assert "someSnakeKey" in data


# --- Regression guard: the real app-owned endpoints MUST carry the flag ---------
# The frontend now reads camelCase ONLY (snake fallbacks removed), so these
# unpaginated app-owned endpoints must stay opted into always_convert_response.
# If someone drops the decorator, the >2 MiB snake passthrough bug silently
# returns -- these tests fail loudly instead.


def test_sessions_endpoints_opt_into_always_convert():
    from app.routers.user import sessions

    assert CaseConversionOptions.from_endpoint(sessions.get_sessions).always_convert_response
    assert CaseConversionOptions.from_endpoint(sessions.get_session).always_convert_response


def test_agents_endpoints_opt_into_always_convert():
    from app.routers.ai import workflows

    assert CaseConversionOptions.from_endpoint(workflows.list_agents).always_convert_response
    assert CaseConversionOptions.from_endpoint(
        workflows.get_available_models_for_agents
    ).always_convert_response
