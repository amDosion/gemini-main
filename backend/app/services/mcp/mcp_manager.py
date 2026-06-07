"""
MCP Manager - 高层 MCP 管理服务

职责：
- MCP 会话池管理
- 配置管理
- 生命周期管理
- 工具缓存

类似于 storage_manager.py 的架构设计

Singleton / multi-worker note
------------------------------
``get_mcp_manager()`` returns a **process-local** singleton.  In a
multi-worker (multi-process) Uvicorn deployment each worker holds its own
independent pool; session metadata is NOT shared across workers.  If
cross-worker session sharing is required, store session metadata in a shared
backend (e.g. Redis) and reconstruct ``MCPClient`` on demand.

``MCPManager.close_all()`` MUST be called during application shutdown.
Register it in ``backend/app/core/shutdown_tasks.py`` via
``close_mcp_sessions()`` (parallel to ``close_gemini_client_pool``).
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
import logging
from contextlib import asynccontextmanager

from .client import (
    MCPClient,
    MCPServerConfig,
    MCPServerType,
    MCPTool,
    MCPToolResult
)
from .adapter import UniversalToolAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pool configuration constants
# ---------------------------------------------------------------------------

# Hard upper bound on concurrent sessions in a single pool.  When the pool is
# full, the least-recently-used idle session is evicted before a new one is
# created.  Override via MCPSessionPool(max_sessions=N) if needed.
_DEFAULT_MAX_SESSIONS: int = 50

# Sessions not accessed within this window (seconds) are eligible for eviction
# during the next ``get_or_create`` call or an explicit ``evict_idle_sessions``
# sweep.  Default: 30 minutes.
_DEFAULT_IDLE_TIMEOUT_SECONDS: float = 1800.0


class MCPSessionPool:
    """
    MCP 会话池

    管理多个 MCP 客户端会话，支持：
    - 会话复用
    - 自动重连
    - 资源清理
    - 容量上限 + 空闲超时淘汰
    """

    def __init__(
        self,
        max_sessions: int = _DEFAULT_MAX_SESSIONS,
        idle_timeout_seconds: float = _DEFAULT_IDLE_TIMEOUT_SECONDS,
    ) -> None:
        self._sessions: Dict[str, MCPClient] = {}
        self._configs: Dict[str, MCPServerConfig] = {}
        # Monotonic timestamp of last access per session (seconds).
        self._last_used: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._max_sessions = max_sessions
        self._idle_timeout = idle_timeout_seconds

    # ------------------------------------------------------------------
    # Internal helpers (must be called with self._lock already held)
    # ------------------------------------------------------------------

    def _touch(self, session_id: str) -> None:
        """Update the last-used timestamp for a session (lock must be held)."""
        self._last_used[session_id] = time.monotonic()

    def _find_lru_idle_session(self) -> Optional[str]:
        """
        Return the session_id of the least-recently-used session, or None if
        the pool is empty.  Lock must be held by caller.
        """
        if not self._last_used:
            return None
        return min(self._last_used, key=lambda sid: self._last_used[sid])

    async def _evict_one_for_capacity(self) -> None:
        """
        Evict the LRU session to free a slot.  Called when the pool is at
        capacity before creating a new session.  Lock must be held.
        """
        lru = self._find_lru_idle_session()
        if lru is not None:
            logger.warning(
                "[MCPSessionPool] Pool at capacity (%d). Evicting LRU session: %s",
                self._max_sessions,
                lru,
            )
            await self._remove_locked(lru)

    async def _remove_locked(self, session_id: str) -> None:
        """Remove a session; lock must already be held by the caller."""
        if session_id in self._sessions:
            client = self._sessions.pop(session_id)
            self._configs.pop(session_id, None)
            self._last_used.pop(session_id, None)
            try:
                await client.close()
            except Exception:
                logger.warning(
                    "[MCPSessionPool] Error closing session %s during removal",
                    session_id,
                    exc_info=True,
                )
            logger.info("[MCPSessionPool] Removed session: %s", session_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create(
        self,
        session_id: str,
        config: MCPServerConfig
    ) -> MCPClient:
        """
        获取或创建会话

        Args:
            session_id: 会话 ID
            config: MCP 服务器配置

        Returns:
            MCP 客户端实例
        """
        async with self._lock:
            # Reuse an existing connected session.
            if session_id in self._sessions:
                client = self._sessions[session_id]
                if client.is_connected:
                    logger.debug("Reusing existing session: %s", session_id)
                    self._touch(session_id)
                    return client
                else:
                    # Session disconnected; evict it and create a fresh one.
                    logger.info(
                        "Session %s disconnected, creating new one", session_id
                    )
                    await self._remove_locked(session_id)

            # Enforce capacity limit before allocating a new slot.
            if len(self._sessions) >= self._max_sessions:
                await self._evict_one_for_capacity()

            # Create a new session.
            logger.info("Creating new MCP session: %s", session_id)
            client = MCPClient(config)
            await client.connect()

            self._sessions[session_id] = client
            self._configs[session_id] = config
            self._touch(session_id)

            return client

    async def remove(self, session_id: str) -> None:
        """
        移除会话

        Args:
            session_id: 会话 ID
        """
        async with self._lock:
            await self._remove_locked(session_id)

    async def evict_idle_sessions(self) -> int:
        """
        Evict all sessions that have not been accessed within the idle-timeout
        window.  Safe to call from a background sweep task.

        Returns:
            Number of sessions evicted.
        """
        now = time.monotonic()
        async with self._lock:
            idle: List[str] = [
                sid
                for sid, ts in self._last_used.items()
                if now - ts >= self._idle_timeout
            ]
            for sid in idle:
                logger.info(
                    "[MCPSessionPool] Evicting idle session %s (idle %.0fs)",
                    sid,
                    now - self._last_used.get(sid, now),
                )
                await self._remove_locked(sid)
        return len(idle)

    async def close_all(self) -> None:
        """关闭所有会话"""
        async with self._lock:
            count = len(self._sessions)
            logger.info("[MCPSessionPool] Closing %d MCP sessions...", count)
            for session_id in list(self._sessions.keys()):
                await self._remove_locked(session_id)
        logger.info("[MCPSessionPool] All MCP sessions closed")

    def get_session(self, session_id: str) -> Optional[MCPClient]:
        """获取会话（不创建），并更新最近访问时间。"""
        client = self._sessions.get(session_id)
        if client is not None:
            # Update last-used without acquiring the async lock; monotonic write
            # races are benign here (worst case: slightly stale eviction order).
            self._last_used[session_id] = time.monotonic()
        return client

    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return list(self._sessions.keys())

    def session_count(self) -> int:
        """Return the current number of pooled sessions."""
        return len(self._sessions)


class MCPManager:
    """
    MCP 高层管理服务

    提供：
    - 会话管理
    - 工具列表获取
    - 工具调用
    - 格式转换

    Lifecycle
    ---------
    ``close_all()`` should be called during application shutdown.  The global
    singleton returned by ``get_mcp_manager()`` is registered in
    ``backend/app/core/shutdown_tasks.close_mcp_sessions()``.
    """

    def __init__(
        self,
        max_sessions: int = _DEFAULT_MAX_SESSIONS,
        idle_timeout_seconds: float = _DEFAULT_IDLE_TIMEOUT_SECONDS,
    ) -> None:
        """初始化 MCP 管理器"""
        self._session_pool = MCPSessionPool(
            max_sessions=max_sessions,
            idle_timeout_seconds=idle_timeout_seconds,
        )
        logger.info("MCPManager initialized")

    async def create_session(
        self,
        session_id: str,
        config: MCPServerConfig
    ) -> MCPClient:
        """
        创建 MCP 会话

        Args:
            session_id: 会话 ID
            config: 服务器配置

        Returns:
            MCP 客户端

        Example:
            >>> manager = MCPManager()
            >>> config = MCPServerConfig(
            ...     server_type=MCPServerType.STDIO,
            ...     command="node",
            ...     args=["server.js"]
            ... )
            >>> client = await manager.create_session("my-session", config)
        """
        return await self._session_pool.get_or_create(session_id, config)

    async def get_session(self, session_id: str) -> Optional[MCPClient]:
        """
        获取会话

        Args:
            session_id: 会话 ID

        Returns:
            MCP 客户端，如果不存在则返回 None
        """
        return self._session_pool.get_session(session_id)

    async def close_session(self, session_id: str) -> None:
        """
        关闭会话

        Args:
            session_id: 会话 ID
        """
        await self._session_pool.remove(session_id)

    async def list_tools(
        self,
        session_id: str
    ) -> List[MCPTool]:
        """
        获取工具列表

        Args:
            session_id: 会话 ID

        Returns:
            工具列表

        Raises:
            ValueError: 会话不存在
        """
        client = self._session_pool.get_session(session_id)
        if not client:
            raise ValueError(f"Session not found: {session_id}")

        return await client.list_tools()

    async def call_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """
        调用工具

        Args:
            session_id: 会话 ID
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具调用结果

        Raises:
            ValueError: 会话不存在
        """
        client = self._session_pool.get_session(session_id)
        if not client:
            raise ValueError(f"Session not found: {session_id}")

        return await client.call_tool(tool_name, arguments)

    async def get_gemini_tools(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取 Gemini 格式的工具列表

        Args:
            session_id: 会话 ID

        Returns:
            Gemini 工具列表

        Raises:
            ValueError: 会话不存在
        """
        return await self.get_tools_by_format(session_id, "gemini")

    async def get_openai_tools(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取 OpenAI 格式的工具列表

        Args:
            session_id: 会话 ID

        Returns:
            OpenAI 工具列表

        Raises:
            ValueError: 会话不存在
        """
        return await self.get_tools_by_format(session_id, "openai")

    async def get_tools_by_format(
        self,
        session_id: str,
        format_type: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定格式的工具列表

        svc-mcp-11: single load path — every format request loads the tools once
        via UniversalToolAdapter and converts, so the gemini/openai/anthropic
        paths no longer each allocate a separate adapter and re-fetch the list.

        Args:
            session_id: 会话 ID
            format_type: 格式类型（"gemini", "openai", "anthropic"）

        Returns:
            指定格式的工具列表

        Raises:
            ValueError: 会话不存在或格式不支持
        """
        client = self._session_pool.get_session(session_id)
        if not client:
            raise ValueError(f"Session not found: {session_id}")

        adapter = UniversalToolAdapter(client)
        await adapter.load_tools()
        return adapter.to_format(format_type)

    @asynccontextmanager
    async def session(
        self,
        session_id: str,
        config: MCPServerConfig
    ):
        """
        会话上下文管理器

        自动创建和清理会话

        Example:
            >>> manager = MCPManager()
            >>> config = MCPServerConfig(...)
            >>> async with manager.session("my-session", config) as client:
            ...     tools = await client.list_tools()
            ...     result = await client.call_tool("tool", {})
        """
        client = await self.create_session(session_id, config)
        try:
            yield client
        finally:
            await self.close_session(session_id)

    async def close_all(self) -> None:
        """关闭所有会话。在应用关闭时应通过 shutdown_tasks 调用。"""
        await self._session_pool.close_all()

    async def evict_idle_sessions(self) -> int:
        """
        Evict sessions idle longer than the configured timeout.
        Delegates to the underlying pool; returns eviction count.
        """
        return await self._session_pool.evict_idle_sessions()

    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return self._session_pool.list_sessions()

    def session_count(self) -> int:
        """Return the current number of pooled sessions."""
        return self._session_pool.session_count()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
# NOTE: This is a single-process singleton.  In a multi-worker Uvicorn
# deployment each worker process has its own independent instance; session
# metadata is NOT shared across workers.  ``close_all()`` is registered in
# ``backend/app/core/shutdown_tasks.close_mcp_sessions()`` so that the
# FastAPI lifespan tears it down cleanly on shutdown.

_global_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """
    获取全局 MCP 管理器实例

    Returns:
        MCPManager 单例 (process-local; not shared across Uvicorn workers)
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = MCPManager()
    return _global_manager
