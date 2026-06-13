"""Regression: MCP debug logs must not expose credentials."""

import logging
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.gemini.agent.agent_with_tools import AgentWithTools
from app.services.gemini.agent.tool_registry import MCPToolExecutor, Tool, ToolExecutor, ToolRegistry
from app.services.mcp.client import _redact_log_value


MCP_CLIENT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "mcp"
    / "client.py"
)


class _FailingToolExecutor(ToolExecutor):
    async def execute(self, name, arguments):
        raise RuntimeError("tool echoed secret-token")


class _FailingMcpManager:
    async def call_tool(self, **_kwargs):
        raise RuntimeError("mcp echoed secret-token")


class _FakeToolRegistry:
    def get_tool(self, _name):
        return Tool(
            name="danger",
            description="danger",
            parameters={"type": "object"},
        )

    def to_gemini_tools(self):
        return []

    async def execute_tool(self, name, arguments):
        raise RuntimeError("tool args echoed secret-token")


class _FakeGoogleServiceForTools:
    def __init__(self):
        self.calls = 0

    async def chat(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "function_calls": [
                    {
                        "name": "danger",
                        "args": {"query": "private query secret-token"},
                        "id": "call-1",
                    }
                ]
            }
        return {"text": "done"}


def test_mcp_log_redaction_masks_cli_secret_arguments():
    args = [
        "server.js",
        "--api-key",
        "plain-secret-value-1234567890",
        "--authorization=Bearer abcdefghijklmnopqrstuvwxyz",
        "--model",
        "gemini-flash",
    ]

    redacted = _redact_log_value(args)

    assert redacted == [
        "server.js",
        "--api-key",
        "[REDACTED]",
        "--authorization=[REDACTED]",
        "--model",
        "gemini-flash",
    ]
    assert "plain-secret-value-1234567890" not in str(redacted)
    assert "abcdefghijklmnopqrstuvwxyz" not in str(redacted)


def test_mcp_log_redaction_masks_nested_tool_arguments_without_mutating_input():
    arguments = {
        "query": "list projects",
        "apiKey": "plain-secret-value-1234567890",
        "max_tokens": 128,
        "headers": {
            "Authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
            "X-Trace": "trace-1",
        },
        "items": [
            {"refresh_token": "refresh-secret-value-1234567890"},
            "sk-testSECRETSECRET",
        ],
    }
    original = deepcopy(arguments)

    redacted = _redact_log_value(arguments)

    assert arguments == original
    assert redacted["query"] == "list projects"
    assert redacted["max_tokens"] == 128
    assert redacted["headers"]["X-Trace"] == "trace-1"
    assert redacted["apiKey"] == "[REDACTED]"
    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["items"][0]["refresh_token"] == "[REDACTED]"
    assert "plain-secret-value-1234567890" not in str(redacted)
    assert "abcdefghijklmnopqrstuvwxyz" not in str(redacted)
    assert "refresh-secret-value-1234567890" not in str(redacted)
    assert "sk-testSECRETSECRET" not in str(redacted)


def test_mcp_client_source_uses_summarized_error_logs():
    source = MCP_CLIENT_SOURCE.read_text(encoding="utf-8")

    assert 'f"Failed to connect to MCP server: {e}"' not in source
    assert 'f"MCP connection failed: {e}"' not in source
    assert 'f"Failed to list tools: {e}"' not in source
    assert 'f"MCP tool call failed: {result}"' not in source
    assert 'f"Error calling MCP tool {tool_name}: {e}"' not in source
    assert 'f"Error closing session context: {e}"' not in source
    assert 'f"Error closing stdio context: {e}"' not in source
    assert 'f"Error closing streamable HTTP context: {e}"' not in source
    assert "logger.info(f" not in source
    assert "logger.debug(f" not in source
    assert "logger.warning(f" not in source
    assert "logger.error(f" not in source
    assert 'summarize_text_for_log(e, label="mcp_tool_error")' in source
    assert 'summarize_text_for_log(result, label="tool_result")' in source
    assert 'summarize_text_for_log(tool_name, label="tool_name")' in source


@pytest.mark.asyncio
async def test_tool_registry_execute_error_log_summarizes_without_exc_info(caplog):
    registry = ToolRegistry()
    registry.register(
        Tool(name="danger", description="danger", parameters={"type": "object"}),
        _FailingToolExecutor(),
    )

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.tool_registry"):
        result = await registry.execute_tool("danger", {"query": "private query secret-token"})

    assert result["success"] is False
    assert "secret-token" in result["error"]
    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.tool_registry"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted tool_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_mcp_tool_executor_error_log_summarizes_without_exc_info(caplog):
    executor = MCPToolExecutor(_FailingMcpManager(), session_id="session-1")

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.tool_registry"):
        result = await executor.execute("danger", {"apiKey": "secret-token"})

    assert result["success"] is False
    assert "secret-token" in result["error"]
    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.tool_registry"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted tool_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


@pytest.mark.asyncio
async def test_google_search_log_summarizes_query(monkeypatch, caplog):
    from app.services.gemini.common import browser

    query = "private search query secret-token"
    monkeypatch.setattr(browser, "web_search", lambda _query: '{"results":[]}')

    registry = ToolRegistry()
    with caplog.at_level(logging.INFO, logger="app.services.gemini.agent.tool_registry"):
        result = await registry._execute_google_search(query, num_results=3)

    assert result["success"] is True
    assert result["query"] == query
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert f"<redacted query; length={len(query)}>" in log_text
    assert query not in log_text
    assert "secret-token" not in log_text


@pytest.mark.asyncio
async def test_agent_with_tools_error_log_summarizes_without_exc_info(caplog):
    agent = AgentWithTools(
        name="agent-1",
        google_service=_FakeGoogleServiceForTools(),
        tool_registry=_FakeToolRegistry(),
        max_tool_iterations=2,
    )

    with caplog.at_level(logging.ERROR, logger="app.services.gemini.agent.agent_with_tools"):
        result = await agent.execute_with_tools(
            task="private task secret-token",
            available_tools=["danger"],
        )

    assert result["result"] == "done"
    records = [
        record
        for record in caplog.records
        if record.name == "app.services.gemini.agent.agent_with_tools"
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted tool_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)
