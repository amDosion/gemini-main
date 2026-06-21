from __future__ import annotations

import pytest
import sqlalchemy
from sqlalchemy.engine import Engine

_ORIGINAL_CREATE_ENGINE = sqlalchemy.create_engine
_TRACKED_SQLITE_ENGINES: set[Engine] = set()


def _tracking_create_engine(*args, **kwargs):
    engine = _ORIGINAL_CREATE_ENGINE(*args, **kwargs)
    if isinstance(engine, Engine) and engine.url.get_backend_name() == "sqlite":
        _TRACKED_SQLITE_ENGINES.add(engine)
    return engine


sqlalchemy.create_engine = _tracking_create_engine


@pytest.fixture(autouse=True)
def _dispose_sqlite_engines_created_by_tests():
    yield
    while _TRACKED_SQLITE_ENGINES:
        engine = _TRACKED_SQLITE_ENGINES.pop()
        engine.dispose()
