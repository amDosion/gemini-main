"""
MCP Manager - 高层 MCP 管理服务

职责：
- MCP 会话池管理
- 配置管理
- 生命周期管理
- 工具缓存

类似于 storage_manager.py 的架构设计
"""

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
from .adapter import (
    GeminiToolAdapter,
    OpenAIToolAdapter,
    UniversalToolAdapter
)

logger = logging.getLogger(__name__)


class MCPSessionPool:
    """
    MCP 会话池

    管理多个 MCP 客户端会话，支持：
    - 会话复用
    - 自动重连
    - 资源清理
    """

    def __init__(self):
        self._sessions: Dict[str, MCPClient] = {}
        self._configs: Dict[str, MCPServerConfig] = {}

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
        # 检查是否已存在
        if session_id in self._sessions:
            client = self._sessions[session_id]
            if client.is_connected:
                logger.debug(f"Reusing existing session: {session_id}")
                return client
            else:
                # 会话已断开，移除
                logger.info(f"Session {session_id} disconnected, creating new one")
                await self.remove(session_id)

        # 创建新会话
        logger.info(f"Creating new MCP session: {session_id}")
        client = MCPClient(config)
        await client.connect()

        self._sessions[session_id] = client
        self._configs[session_id] = config

        return client

    async def remove(self, session_id: str) -> None:
        """
        移除会话

        Args:
            session_id: 会话 ID
        """
        if session_id in self._sessions:
            client = self._sessions[session_id]
            await client.close()
            del self._sessions[session_id]
            del self._configs[session_id]
            logger.info(f"Removed session: {session_id}")

    async def close_all(self) -> None:
        """关闭所有会话"""
        logger.info(f"Closing {len(self._sessions)} MCP sessions...")

        for session_id in list(self._sessions.keys()):
            await self.remove(session_id)

        logger.info("All MCP sessions closed")

    def get_session(self, session_id: str) -> Optional[MCPClient]:
        """获取会话（不创建）"""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return list(self._sessions.keys())


class MCPManager:
    """
    MCP 高层管理服务

    提供：
    - 会话管理
    - 工具列表获取
    - 工具调用
    - 格式转换
    """

    def __init__(self):
        """初始化 MCP 管理器"""
        self._session_pool = MCPSessionPool()
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
        client = self._session_pool.get_session(session_id)
        if not client:
            raise ValueError(f"Session not found: {session_id}")

        adapter = GeminiToolAdapter(client)
        await adapter.load_tools()
        return adapter.to_gemini_tools()

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
        client = self._session_pool.get_session(session_id)
        if not client:
            raise ValueError(f"Session not found: {session_id}")

        adapter = OpenAIToolAdapter(client)
        await adapter.load_tools()
        return adapter.to_openai_tools()

    async def get_tools_by_format(
        self,
        session_id: str,
        format_type: str
    ) -> List[Dict[str, Any]]:
        """
        获取指定格式的工具列表

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
        """关闭所有会话"""
        await self._session_pool.close_all()

    def list_sessions(self) -> List[str]:
        """列出所有会话 ID"""
        return self._session_pool.list_sessions()


# 全局单例（可选）
_global_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """
    获取全局 MCP 管理器实例

    Returns:
        MCPManager 单例
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = MCPManager()
    return _global_manager
