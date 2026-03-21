"""
MCP 客户端实现
基于官方 MCP SDK，支持 stdio / streamable HTTP 协议
"""

from typing import Dict, Any, Optional, List
import logging
from contextlib import asynccontextmanager

from ...core.config import settings
from .types import (
    MCPServerConfig,
    MCPServerType,
    MCPTool,
    MCPToolResult,
    MCPStdioPolicyError,
    validate_mcp_stdio_command_policy,
)

# 尝试导入官方 MCP SDK
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.types import Tool as McpSdkTool, CallToolResult
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None
    McpSdkTool = None
    CallToolResult = None

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 客户端（基于官方 SDK）

    功能：
    - 连接 MCP 服务器（stdio/streamable HTTP）
    - 获取工具列表
    - 调用工具
    - 会话管理
    - 自动资源清理

    示例：
        >>> config = MCPServerConfig(
        ...     server_type=MCPServerType.STDIO,
        ...     command="node",
        ...     args=["server.js"]
        ... )
        >>> async with MCPClient(config) as client:
        ...     tools = await client.list_tools()
        ...     result = await client.call_tool("get_weather", {"city": "Beijing"})
    """

    def __init__(self, config: MCPServerConfig):
        """
        初始化 MCP 客户端

        Args:
            config: MCP 服务器配置

        Raises:
            ImportError: MCP SDK 未安装
            ValueError: 配置无效
        """
        if not MCP_SDK_AVAILABLE:
            raise ImportError(
                "MCP SDK is required but not installed. "
                "Install it with: pip install mcp"
            )

        # 验证配置
        config.validate()

        self.config = config
        self._session: Optional[ClientSession] = None
        self._session_context = None  # 保存 ClientSession 上下文管理器
        self._tools_cache: Optional[List[MCPTool]] = None
        self._stdio_context = None  # 保存 stdio 上下文管理器
        self._streamable_http_context = None  # 保存 streamable HTTP 上下文管理器

        logger.info(
            f"MCPClient initialized: type={config.server_type.value}, "
            f"command={config.command}, args={config.args}"
        )

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def connect(self) -> None:
        """
        建立 MCP 连接

        Raises:
            RuntimeError: 连接失败
        """
        if self._session:
            logger.warning("Session already connected")
            return

        # 防御性校验（双保险）：即使上游已校验，这里仍再次阻止任意 stdio 命令执行
        validate_mcp_stdio_command_policy(
            self.config,
            policy=settings.mcp_stdio_command_policy,
            allowed_commands=settings.mcp_stdio_allowed_commands,
            context="mcp-client-connect",
        )

        try:
            logger.info("Connecting to MCP server...")

            if self.config.server_type == MCPServerType.STDIO:
                # stdio 协议（进程通信）
                server_params = StdioServerParameters(
                    command=self.config.command,
                    args=self.config.args or [],
                    env=self.config.env
                )

                # 注意：stdio_client 返回异步上下文管理器
                # 根据 MCP SDK 文档，应该使用嵌套的 async with
                from mcp.client.stdio import stdio_client

                # stdio_client 返回异步上下文管理器，需要进入上下文获取流
                # 但我们不能在这里使用 async with，因为需要保持连接
                # 所以手动进入上下文
                stdio_context = stdio_client(server_params)
                read_stream, write_stream = await stdio_context.__aenter__()
                
                # 保存上下文管理器以便后续清理
                self._stdio_context = stdio_context

                # 创建 ClientSession（它也是一个异步上下文管理器）
                session_context = ClientSession(read_stream, write_stream)
                self._session = await session_context.__aenter__()
                self._session_context = session_context
                
                await self._session.initialize()

                logger.info("MCP session initialized (stdio)")

            elif self.config.server_type == MCPServerType.SSE:
                # SSE 协议（HTTP 流）
                # TODO: 实现 SSE 连接
                raise NotImplementedError("SSE protocol is not yet implemented")

            elif self.config.server_type in (MCPServerType.HTTP, MCPServerType.STREAMABLE_HTTP):
                # HTTP / Streamable HTTP（MCP over HTTP）
                from mcp.client.streamable_http import streamable_http_client

                streamable_http_context = streamable_http_client(
                    self.config.url or "",
                    terminate_on_close=True,
                )
                read_stream, write_stream, _ = await streamable_http_context.__aenter__()

                # 保存上下文管理器以便后续清理
                self._streamable_http_context = streamable_http_context

                # 创建 ClientSession（它也是一个异步上下文管理器）
                session_context = ClientSession(read_stream, write_stream)
                self._session = await session_context.__aenter__()
                self._session_context = session_context

                await self._session.initialize()

                logger.info("MCP session initialized (streamable HTTP)")

            else:
                raise ValueError(f"Unsupported server type: {self.config.server_type}")

        except MCPStdioPolicyError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise RuntimeError(f"MCP connection failed: {e}")

    async def list_tools(self) -> List[MCPTool]:
        """
        获取可用工具列表

        Returns:
            MCP 工具列表

        Raises:
            RuntimeError: 未连接
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        # 返回缓存的工具列表
        if self._tools_cache is not None:
            return self._tools_cache

        try:
            logger.info("Fetching tool list from MCP server...")

            # 调用 MCP SDK 的 list_tools
            result = await self._session.list_tools()

            # 转换为内部类型
            self._tools_cache = [
                MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema or {}
                )
                for tool in result.tools
            ]

            logger.info(f"Found {len(self._tools_cache)} tools")
            return self._tools_cache

        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            raise RuntimeError(f"Failed to list tools: {e}")

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """
        调用远程工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果

        Raises:
            RuntimeError: 未连接
            ValueError: 参数无效
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        if not tool_name:
            raise ValueError("tool_name cannot be empty")

        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a dictionary")

        logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")

        try:
            # 调用 MCP SDK 的 call_tool
            result: CallToolResult = await self._session.call_tool(
                name=tool_name,
                arguments=arguments
            )

            # 转换为内部类型
            if result.isError:
                logger.error(f"MCP tool call failed: {result}")
                return MCPToolResult(
                    success=False,
                    error=str(result.content) if result.content else "Unknown error",
                    is_error=True
                )

            logger.info(f"MCP tool call succeeded: {tool_name}")
            return MCPToolResult(
                success=True,
                result=result.content,
                is_error=False
            )

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return MCPToolResult(
                success=False,
                error=str(e),
                is_error=True
            )

    async def close(self) -> None:
        """
        关闭 MCP 连接

        清理资源，关闭会话
        """
        if self._session or self._session_context or self._stdio_context or self._streamable_http_context:
            logger.info("Closing MCP session...")

            # 先退出 ClientSession 上下文
            if self._session_context:
                try:
                    await self._session_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing session context: {e}")
                self._session_context = None

            # 再退出 stdio 上下文
            if self._stdio_context:
                try:
                    await self._stdio_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing stdio context: {e}")
                self._stdio_context = None

            # 再退出 streamable HTTP 上下文
            if self._streamable_http_context:
                try:
                    await self._streamable_http_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing streamable HTTP context: {e}")
                self._streamable_http_context = None

            # 清空引用
            self._session = None
            self._tools_cache = None

            logger.info("MCP session closed")

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._session is not None

    @property
    def tools(self) -> Optional[List[MCPTool]]:
        """获取缓存的工具列表（如果已加载）"""
        return self._tools_cache
