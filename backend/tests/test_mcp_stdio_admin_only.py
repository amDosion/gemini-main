"""Regression: only admins may configure stdio MCP servers.

CANON-001 / W02R-004: stdio MCP servers spawn local processes on the backend
host (npx/uvx/node/python are in the default allowlist and package/script args
are not inspected), so an authenticated non-admin user who could save a stdio
MCP server config gained backend code execution. Per product decision, stdio MCP
configuration is restricted to administrators; other users may use HTTP/SSE
transports only.

These tests pin the config-save gate (the env-sensitive stdio command policy is
neutralised with allow_all so we test the admin gate in isolation).
"""

import pytest
from fastapi import HTTPException

from app.routers.user import mcp_config

STDIO_ROOT = {"mcpServers": {"x": {"command": "npx", "args": ["-y", "some-pkg"]}}}
HTTP_ROOT = {"mcpServers": {"x": {"type": "http", "url": "https://mcp.example.com/sse"}}}


@pytest.fixture(autouse=True)
def _allow_all_stdio_policy(monkeypatch):
    monkeypatch.setattr(mcp_config.settings, "mcp_stdio_command_policy", "allow_all")


def test_stdio_config_rejected_for_non_admin():
    with pytest.raises(HTTPException) as exc_info:
        mcp_config._validate_config_root_or_raise(STDIO_ROOT, context="t", allow_stdio=False)
    assert exc_info.value.status_code == 403


def test_stdio_config_allowed_for_admin():
    # Admin may configure stdio servers (no exception).
    mcp_config._validate_config_root_or_raise(STDIO_ROOT, context="t", allow_stdio=True)


def test_http_config_allowed_for_non_admin():
    # HTTP/SSE transports remain available to all authenticated users.
    mcp_config._validate_config_root_or_raise(HTTP_ROOT, context="t", allow_stdio=False)
