"""Regression: HTTP/SSE MCP server URLs must pass the outbound SSRF policy.

CANON-001 / W02R-005: validate_mcp_stdio_command_policy only guards stdio
commands; the HTTP / streamableHttp transport passed the user-configured URL
straight to streamable_http_client with no outbound URL validation, so an
authenticated user's MCP config could point the backend at loopback / private /
metadata addresses (authenticated SSRF / internal probing).

connect() must reject restricted URLs via the shared url_security guard before
attempting any connection.
"""

import pytest

from app.services.mcp.client import MCPClient
from app.services.mcp.types import MCPServerConfig, MCPServerType


@pytest.mark.asyncio
async def test_streamable_http_mcp_requires_operator_host_allowlist(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "mcp_http_allowed_hosts_raw", "", raising=False)
    client = MCPClient(
        MCPServerConfig(server_type=MCPServerType.STREAMABLE_HTTP, url="http://127.0.0.1:9/mcp")
    )
    with pytest.raises(Exception) as exc_info:
        await client.connect()
    assert "allowlisted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_http_mcp_rejects_loopback_url_even_when_allowlisted(monkeypatch):
    import app.core.config as config_mod

    monkeypatch.setattr(
        config_mod.settings,
        "mcp_http_allowed_hosts_raw",
        "127.0.0.1",
        raising=False,
    )
    client = MCPClient(
        MCPServerConfig(server_type=MCPServerType.HTTP, url="http://127.0.0.1:1/mcp")
    )
    with pytest.raises(Exception) as exc_info:
        await client.connect()
    assert "rejected by outbound policy" in str(exc_info.value)
