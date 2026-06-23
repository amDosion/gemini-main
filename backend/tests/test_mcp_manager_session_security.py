import asyncio

import pytest

from app.services.mcp import mcp_manager as mcp_manager_mod
from app.services.mcp.mcp_manager import MCPManager, MCPSessionPool
from app.services.mcp.types import MCPServerConfig, MCPServerType


class _FakeMCPClient:
    slow_started: asyncio.Event
    release_slow: asyncio.Event

    def __init__(self, config):
        self.config = config
        self.is_connected = False
        self.closed = False

    async def connect(self):
        if self.config.command == "slow":
            self.__class__.slow_started.set()
            await self.__class__.release_slow.wait()
        self.is_connected = True

    async def close(self):
        if self.config.command == "slow-close":
            self.__class__.close_started.set()
            await self.__class__.release_close.wait()
        self.closed = True


@pytest.mark.asyncio
async def test_mcp_session_connect_does_not_hold_global_pool_lock(monkeypatch):
    _FakeMCPClient.slow_started = asyncio.Event()
    _FakeMCPClient.release_slow = asyncio.Event()
    monkeypatch.setattr(mcp_manager_mod, "MCPClient", _FakeMCPClient)

    pool = MCPSessionPool(max_sessions=10)
    slow_config = MCPServerConfig(server_type=MCPServerType.STDIO, command="slow", timeout=1)
    fast_config = MCPServerConfig(server_type=MCPServerType.STDIO, command="fast", timeout=1)

    slow_task = asyncio.create_task(pool.get_or_create("slow-session", slow_config, owner_id="u1"))
    await asyncio.wait_for(_FakeMCPClient.slow_started.wait(), timeout=0.2)

    fast_client = await asyncio.wait_for(
        pool.get_or_create("fast-session", fast_config, owner_id="u1"),
        timeout=0.2,
    )

    assert fast_client.is_connected is True
    _FakeMCPClient.release_slow.set()
    await slow_task


@pytest.mark.asyncio
async def test_mcp_session_owner_is_enforced(monkeypatch):
    _FakeMCPClient.slow_started = asyncio.Event()
    _FakeMCPClient.release_slow = asyncio.Event()
    monkeypatch.setattr(mcp_manager_mod, "MCPClient", _FakeMCPClient)

    pool = MCPSessionPool(max_sessions=10)
    config = MCPServerConfig(server_type=MCPServerType.STDIO, command="fast", timeout=1)

    await pool.get_or_create("shared-session", config, owner_id="owner-a")

    assert pool.get_session("shared-session", owner_id="owner-b") is None
    with pytest.raises(PermissionError):
        await pool.get_or_create("shared-session", config, owner_id="owner-b")


@pytest.mark.asyncio
async def test_mcp_formatted_tool_access_enforces_owner(monkeypatch):
    _FakeMCPClient.slow_started = asyncio.Event()
    _FakeMCPClient.release_slow = asyncio.Event()
    monkeypatch.setattr(mcp_manager_mod, "MCPClient", _FakeMCPClient)

    manager = MCPManager()
    config = MCPServerConfig(server_type=MCPServerType.STDIO, command="fast", timeout=1)
    await manager.create_session("shared-session", config, owner_id="owner-a")

    with pytest.raises(ValueError, match="Session not found"):
        await manager.get_gemini_tools("shared-session", owner_id="owner-b")


@pytest.mark.asyncio
async def test_mcp_session_remove_does_not_hold_global_lock_while_closing(monkeypatch):
    _FakeMCPClient.slow_started = asyncio.Event()
    _FakeMCPClient.release_slow = asyncio.Event()
    _FakeMCPClient.close_started = asyncio.Event()
    _FakeMCPClient.release_close = asyncio.Event()
    monkeypatch.setattr(mcp_manager_mod, "MCPClient", _FakeMCPClient)

    pool = MCPSessionPool(max_sessions=10)
    slow_close_config = MCPServerConfig(
        server_type=MCPServerType.STDIO,
        command="slow-close",
        timeout=1,
    )
    fast_config = MCPServerConfig(server_type=MCPServerType.STDIO, command="fast", timeout=1)

    await pool.get_or_create("slow-close-session", slow_close_config, owner_id="u1")
    remove_task = asyncio.create_task(pool.remove("slow-close-session"))
    await asyncio.wait_for(_FakeMCPClient.close_started.wait(), timeout=0.2)

    fast_client = await asyncio.wait_for(
        pool.get_or_create("fast-session", fast_config, owner_id="u1"),
        timeout=0.2,
    )

    assert fast_client.is_connected is True
    _FakeMCPClient.release_close.set()
    await remove_task
