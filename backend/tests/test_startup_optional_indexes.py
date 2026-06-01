import asyncio
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_optional_index_helper_skips_when_table_schema_is_not_manageable(monkeypatch):
    from app.core import startup_tasks

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sample_table (id INTEGER PRIMARY KEY, user_id TEXT)"))

    monkeypatch.setattr(startup_tasks, "_table_schema_is_manageable", lambda conn, table: False)

    created = startup_tasks._ensure_optional_index(
        engine=engine,
        table_names={"sample_table"},
        table="sample_table",
        index_name="ix_sample_table_user_id",
        sql="CREATE INDEX ix_sample_table_user_id ON sample_table (user_id)",
        log_prefixes={"success": "[OK]", "info": "[INFO]", "warning": "[WARN]"},
    )

    assert created is False
    assert inspect(engine).get_indexes("sample_table") == []


def test_optional_index_helper_creates_index_when_table_schema_is_manageable(monkeypatch):
    from app.core import startup_tasks

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sample_table (id INTEGER PRIMARY KEY, user_id TEXT)"))

    monkeypatch.setattr(startup_tasks, "_table_schema_is_manageable", lambda conn, table: True)

    created = startup_tasks._ensure_optional_index(
        engine=engine,
        table_names={"sample_table"},
        table="sample_table",
        index_name="ix_sample_table_user_id",
        sql="CREATE INDEX ix_sample_table_user_id ON sample_table (user_id)",
        log_prefixes={"success": "[OK]", "info": "[INFO]", "warning": "[WARN]"},
    )

    indexes = inspect(engine).get_indexes("sample_table")
    assert created is True
    assert [index["name"] for index in indexes] == ["ix_sample_table_user_id"]


def test_workflow_idempotency_schema_migration_uses_sql_text(monkeypatch):
    from app.core import database, startup_tasks

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE workflow_executions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    idempotency_key TEXT
                )
                """
            )
        )

    monkeypatch.setattr(database, "engine", engine)

    asyncio.run(
        startup_tasks.migrate_workflow_idempotency_schema(
            {"success": "[OK]", "info": "[INFO]", "warning": "[WARN]"}
        )
    )

    index_names = [index["name"] for index in inspect(engine).get_indexes("workflow_executions")]
    assert "uq_workflow_execution_user_idempotency_key" in index_names
