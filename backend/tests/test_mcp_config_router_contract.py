from __future__ import annotations

import json
import logging
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.user import mcp_config


class FakeRecord:
    def __init__(self, config_json: str, updated_at=None):
        self.user_id = "user-1"
        self.config_json = config_json
        self.updated_at = updated_at


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.db.record

    def scalar(self):
        return self.db.is_admin


class FakeDb:
    def __init__(self, record=None, *, is_admin: bool = False):
        self.record = record
        self.is_admin = is_admin
        self.committed = False

    def query(self, *args, **kwargs):
        return FakeQuery(self)

    def add(self, record):
        self.record = record

    def commit(self):
        self.committed = True

    def rollback(self):
        self.committed = False

    def refresh(self, record):
        return None


class FakeTool:
    name = "lookup"
    description = "Lookup data"


class FakeToolResult:
    def to_dict(self):
        return {
            "success": True,
            "result": {"items": [1, None, {"ok": True}]},
            "error": None,
            "is_error": False,
        }


class FakeMcpManager:
    def __init__(self):
        self.created_sessions = []

    async def create_session(self, session_id, config, **kwargs):
        self.created_sessions.append((session_id, config.url))

    async def list_tools(self, session_id, **kwargs):
        assert session_id.startswith("chat:user-1:remote:")
        return [FakeTool()]

    async def call_tool(self, session_id, tool_name, arguments, **kwargs):
        assert session_id.startswith("chat:user-1:remote:")
        assert tool_name == "lookup"
        assert arguments == {"q": "abc"}
        return FakeToolResult()

    def list_sessions(self):
        return []


class FailingCommitDb(FakeDb):
    def commit(self):
        raise RuntimeError("database echoed secret-token")


class FailingToolsMcpManager(FakeMcpManager):
    async def list_tools(self, session_id, **kwargs):
        raise RuntimeError("tool list echoed secret-token")


class FailingInvokeMcpManager(FakeMcpManager):
    async def call_tool(self, session_id, tool_name, arguments, **kwargs):
        raise RuntimeError("tool invoke echoed secret-token")


class FailingCloseMcpManager(FakeMcpManager):
    def list_sessions(self):
        return ["chat:user-1:remote:session-secret-token"]

    async def close_session(self, session_id):
        raise RuntimeError("close echoed secret-token")


def _client(db, monkeypatch, manager=None):
    app = FastAPI()
    app.include_router(mcp_config.router)
    app.dependency_overrides[mcp_config.require_current_user] = lambda: "user-1"
    app.dependency_overrides[mcp_config.get_db] = lambda: db
    monkeypatch.setattr(
        mcp_config.settings,
        "mcp_http_allowed_hosts_raw",
        "mcp.example.test",
        raising=False,
    )
    if manager is not None:
        monkeypatch.setattr(mcp_config, "get_mcp_manager", lambda: manager)
    return TestClient(app)


def _http_config_json() -> str:
    return json.dumps(
        {
            "mcpServers": {
                "remote": {
                    "type": "http",
                    "url": "https://mcp.example.test/rpc",
                }
            }
        }
    )


def _stdio_config_json() -> str:
    return json.dumps(
        {
            "mcpServers": {
                "local": {
                    "type": "stdio",
                    "command": sys.executable,
                    "args": [],
                }
            }
        }
    )


def test_mcp_config_get_response_model_without_record(monkeypatch):
    with _client(FakeDb(), monkeypatch) as client:
        response = client.get("/api/mcp/config")

    assert response.status_code == 200
    assert response.json() == {"config_json": "{}", "updated_at": None}


def test_mcp_config_update_response_model(monkeypatch):
    db = FakeDb()

    with _client(db, monkeypatch) as client:
        response = client.put(
            "/api/mcp/config",
            json={
                "config": {
                    "mcpServers": {
                        "remote": {
                            "type": "http",
                            "url": "https://mcp.example.test/rpc",
                        }
                    }
                }
            },
        )

    assert response.status_code == 200
    assert db.committed is True
    body = response.json()
    assert json.loads(body["config_json"])["mcpServers"]["remote"]["type"] == "http"
    assert body["updated_at"] is None


def test_mcp_config_rejects_stdio_save_for_non_admin(monkeypatch):
    monkeypatch.setattr(mcp_config.settings, "mcp_stdio_command_policy", "allow_all", raising=False)
    db = FakeDb(is_admin=False)

    with _client(db, monkeypatch) as client:
        response = client.put(
            "/api/mcp/config",
            json={"config_json": _stdio_config_json()},
        )

    assert response.status_code == 403
    assert "stdio MCP server" in response.json()["detail"]
    assert db.committed is False


def test_mcp_config_allows_stdio_save_for_admin(monkeypatch):
    monkeypatch.setattr(mcp_config.settings, "mcp_stdio_command_policy", "allow_all", raising=False)
    db = FakeDb(is_admin=True)

    with _client(db, monkeypatch) as client:
        response = client.put(
            "/api/mcp/config",
            json={"config_json": _stdio_config_json()},
        )

    assert response.status_code == 200
    assert db.committed is True


def test_mcp_tools_response_model(monkeypatch):
    db = FakeDb(record=FakeRecord(_http_config_json()))
    manager = FakeMcpManager()

    with _client(db, monkeypatch, manager=manager) as client:
        response = client.get("/api/mcp/config/tools/remote")

    assert response.status_code == 200
    assert response.json() == {
        "server_key": "remote",
        "tool_count": 1,
        "tools": [{"name": "lookup", "description": "Lookup data"}],
    }
    assert manager.created_sessions


def test_mcp_tools_rejects_stale_stdio_config_for_non_admin(monkeypatch):
    monkeypatch.setattr(mcp_config.settings, "mcp_stdio_command_policy", "allow_all", raising=False)
    db = FakeDb(record=FakeRecord(_stdio_config_json()), is_admin=False)
    manager = FakeMcpManager()

    with _client(db, monkeypatch, manager=manager) as client:
        response = client.get("/api/mcp/config/tools/local")

    assert response.status_code == 403
    assert "stdio MCP server" in response.json()["detail"]
    assert manager.created_sessions == []


def test_mcp_tool_invoke_response_model_preserves_json_result(monkeypatch):
    db = FakeDb(record=FakeRecord(_http_config_json()))
    manager = FakeMcpManager()

    with _client(db, monkeypatch, manager=manager) as client:
        response = client.post(
            "/api/mcp/config/tools/remote/invoke",
            json={"toolName": "lookup", "arguments": {"q": "abc"}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["server_key"] == "remote"
    assert body["tool_name"] == "lookup"
    assert body["success"] is True
    assert body["result"] == {"items": [1, None, {"ok": True}]}
    assert body["error"] is None
    assert body["is_error"] is False


def test_mcp_tool_invoke_rejects_stale_stdio_config_for_non_admin(monkeypatch):
    monkeypatch.setattr(mcp_config.settings, "mcp_stdio_command_policy", "allow_all", raising=False)
    db = FakeDb(record=FakeRecord(_stdio_config_json()), is_admin=False)
    manager = FakeMcpManager()

    with _client(db, monkeypatch, manager=manager) as client:
        response = client.post(
            "/api/mcp/config/tools/local/invoke",
            json={"toolName": "lookup", "arguments": {"q": "abc"}},
        )

    assert response.status_code == 403
    assert "stdio MCP server" in response.json()["detail"]
    assert manager.created_sessions == []


def test_mcp_config_save_error_log_is_summarized(monkeypatch, caplog):
    db = FailingCommitDb()

    with caplog.at_level(logging.ERROR, logger="app.routers.user.mcp_config"):
        with _client(db, monkeypatch) as client:
            response = client.put(
                "/api/mcp/config",
                json={
                    "config": {
                        "mcpServers": {
                            "remote": {
                                "type": "http",
                                "url": "https://mcp.example.test/rpc",
                            }
                        }
                    }
                },
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to save MCP config"
    records = [
        record for record in caplog.records if record.name == "app.routers.user.mcp_config"
    ]
    assert records
    assert all(record.exc_info is None for record in records)
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted mcp_config_error; length=" in log_text
    assert "secret-token" not in log_text
    assert "user-1" not in log_text


def test_mcp_tools_error_log_and_response_are_summarized(monkeypatch, caplog):
    db = FakeDb(record=FakeRecord(_http_config_json()))
    manager = FailingToolsMcpManager()

    with caplog.at_level(logging.ERROR, logger="app.routers.user.mcp_config"):
        with _client(db, monkeypatch, manager=manager) as client:
            response = client.get("/api/mcp/config/tools/remote")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to fetch MCP tools"
    records = [
        record for record in caplog.records if record.name == "app.routers.user.mcp_config"
    ]
    assert records
    assert all(record.exc_info is None for record in records)
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted mcp_tools_error; length=" in log_text
    assert "secret-token" not in log_text
    assert "remote" not in log_text


def test_mcp_tool_invoke_error_log_and_response_are_summarized(monkeypatch, caplog):
    db = FakeDb(record=FakeRecord(_http_config_json()))
    manager = FailingInvokeMcpManager()

    with caplog.at_level(logging.ERROR, logger="app.routers.user.mcp_config"):
        with _client(db, monkeypatch, manager=manager) as client:
            response = client.post(
                "/api/mcp/config/tools/remote/invoke",
                json={"toolName": "lookup", "arguments": {"apiKey": "secret-token"}},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to invoke MCP tool"
    records = [
        record for record in caplog.records if record.name == "app.routers.user.mcp_config"
    ]
    assert records
    assert all(record.exc_info is None for record in records)
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted mcp_tool_error; length=" in log_text
    assert "secret-token" not in log_text
    assert "lookup" not in log_text


def test_mcp_stop_session_error_response_and_log_are_summarized(monkeypatch, caplog):
    manager = FailingCloseMcpManager()

    with caplog.at_level(logging.WARNING, logger="app.routers.user.mcp_config"):
        with _client(FakeDb(), monkeypatch, manager=manager) as client:
            response = client.post(
                "/api/mcp/session/stop",
                json={"mcpServerKey": "remote"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["closed_count"] == 0
    assert body["closed_sessions"] == []
    assert body["errors"]
    assert "secret-token" not in json.dumps(body)
    assert "<redacted session_id; length=" in body["errors"][0]
    assert "<redacted mcp_session_close_error; length=" in body["errors"][0]

    records = [
        record for record in caplog.records if record.name == "app.routers.user.mcp_config"
    ]
    assert records
    assert all(record.exc_info is None for record in records)
    log_text = "\n".join(record.getMessage() for record in records)
    assert "secret-token" not in log_text
