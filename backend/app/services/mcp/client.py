"""
MCP 客户端实现
基于官方 MCP SDK，支持 stdio / streamable HTTP 协议
"""

from typing import Dict, Any, Optional, List
import logging
import time

from ...core.config import settings
from ...utils.error_handler import _mask_keys_in_text
from ...utils.log_sanitization import summarize_text_for_log
from ...utils.url_security import UnsafeURLError, validate_outbound_http_url_async
from .types import (
    MCPServerConfig,
    MCPServerType,
    MCPTool,
    MCPToolResult,
    MCPStdioPolicyError,
    MCPUrlPolicyError,
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

# svc-mcp-5: how long (seconds) list_tools() results are considered fresh
_TOOLS_CACHE_TTL_SECONDS: float = 60.0
_REDACTED_LOG_VALUE = "[REDACTED]"
_SENSITIVE_KEY_MARKERS = (
    "apikey",
    "accesskey",
    "accesstoken",
    "refreshtoken",
    "authtoken",
    "authorization",
    "credential",
    "password",
    "privatekey",
    "secret",
)
_SENSITIVE_ARG_NAMES = {
    "--api-key",
    "--apikey",
    "--access-key",
    "--access-token",
    "--auth-token",
    "--authorization",
    "--credential",
    "--password",
    "--refresh-token",
    "--secret",
    "--token",
}
_SAFE_TOKEN_COUNT_KEYS = {
    "maxtokens",
    "prompttokens",
    "completiontokens",
    "totaltokens",
}


def _is_sensitive_log_key(key: object) -> bool:
    normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
    if not normalized or normalized in _SAFE_TOKEN_COUNT_KEYS:
        return False
    if normalized == "token" or normalized.endswith("token"):
        return True
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _redact_cli_arg(arg: str) -> str:
    stripped = arg.strip()
    lowered = stripped.lower()
    for name in _SENSITIVE_ARG_NAMES:
        if lowered == name:
            return arg
        for separator in ("=", ":"):
            prefix = f"{name}{separator}"
            if lowered.startswith(prefix):
                visible_prefix = arg[: len(prefix)]
                return f"{visible_prefix}{_REDACTED_LOG_VALUE}"
    return _mask_keys_in_text(arg)


def _redact_sequence_for_log(values: list[Any] | tuple[Any, ...]) -> list[Any]:
    redacted: list[Any] = []
    redact_next = False
    for value in values:
        if redact_next:
            redacted.append(_REDACTED_LOG_VALUE)
            redact_next = False
            continue

        if isinstance(value, str):
            lowered = value.strip().lower()
            redacted.append(_redact_cli_arg(value))
            if lowered in _SENSITIVE_ARG_NAMES:
                redact_next = True
            continue

        redacted.append(_redact_log_value(value))
    return redacted


def _redact_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return _mask_keys_in_text(value)
    if isinstance(value, dict):
        return {
            key: _REDACTED_LOG_VALUE if _is_sensitive_log_key(key) else _redact_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return _redact_sequence_for_log(value)
    return value


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
        self._tools_cache_time: float = 0.0  # epoch seconds when cache was filled
        self._stdio_context = None  # 保存 stdio 上下文管理器
        self._streamable_http_context = None  # 保存 streamable HTTP 上下文管理器

        # svc-mcp-4: log command name only at INFO; args may contain credential-style flags
        logger.info(
            "MCPClient initialized: type=%s, command=%s",
            config.server_type.value,
            config.command,
        )
        logger.debug("MCPClient args: %s", _redact_log_value(config.args))

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

        # CANON-001 / W02R-005: HTTP/SSE MCP server URLs are user-controlled and must
        # pass the same outbound-egress SSRF policy as any other backend fetch.
        # Validated before the connection attempt so a restricted (loopback/private/
        # metadata) target is rejected rather than reached.
        if self.config.server_type in (
            MCPServerType.HTTP,
            MCPServerType.STREAMABLE_HTTP,
            MCPServerType.SSE,
        ):
            try:
                # Event-loop-safe variant: bounds DNS resolution so a hostile/slow
                # resolver on a user-supplied MCP URL cannot stall the event loop.
                await validate_outbound_http_url_async(self.config.url or "")
            except UnsafeURLError as exc:
                raise MCPUrlPolicyError(
                    f"MCP server URL rejected by outbound policy: {exc}"
                ) from exc

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
            await self.close()
            raise
        except Exception as e:
            logger.error(
                "Failed to connect to MCP server: error=%s",
                summarize_text_for_log(e, label="mcp_connect_error"),
            )
            await self.close()
            raise RuntimeError("MCP connection failed") from e

    async def list_tools(self, force_refresh: bool = False) -> List[MCPTool]:
        """
        获取可用工具列表

        Returns:
            MCP 工具列表

        Raises:
            RuntimeError: 未连接
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first or use context manager.")

        # svc-mcp-5: return cached list if within TTL; use force_refresh=True to bypass
        if self._tools_cache is not None and not force_refresh:
            age = time.monotonic() - self._tools_cache_time
            if age < _TOOLS_CACHE_TTL_SECONDS:
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

            self._tools_cache_time = time.monotonic()
            logger.info("Found %d tools", len(self._tools_cache))
            return self._tools_cache

        except Exception as e:
            logger.error(
                "Failed to list MCP tools: error=%s",
                summarize_text_for_log(e, label="mcp_list_tools_error"),
            )
            raise RuntimeError("Failed to list tools") from e

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

        # svc-mcp-3: avoid logging argument values at INFO to prevent credential leakage
        logger.info(
            "Calling MCP tool: %s with %d args",
            summarize_text_for_log(tool_name, label="tool_name"),
            len(arguments),
        )
        logger.debug(
            "MCP tool %s args: %s",
            summarize_text_for_log(tool_name, label="tool_name"),
            _redact_log_value(arguments),
        )

        try:
            # 调用 MCP SDK 的 call_tool
            result: CallToolResult = await self._session.call_tool(
                name=tool_name,
                arguments=arguments
            )

            # 转换为内部类型
            if result.isError:
                logger.error(
                    "MCP tool call failed: tool=%s result=%s",
                    summarize_text_for_log(tool_name, label="tool_name"),
                    summarize_text_for_log(result, label="tool_result"),
                )
                return MCPToolResult(
                    success=False,
                    error=str(result.content) if result.content else "Unknown error",
                    is_error=True
                )

            logger.info(
                "MCP tool call succeeded: %s",
                summarize_text_for_log(tool_name, label="tool_name"),
            )
            return MCPToolResult(
                success=True,
                result=result.content,
                is_error=False
            )

        except Exception as e:
            logger.error(
                "Error calling MCP tool: tool=%s error=%s",
                summarize_text_for_log(tool_name, label="tool_name"),
                summarize_text_for_log(e, label="mcp_tool_error"),
            )
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
                    logger.warning(
                        "Error closing session context: error=%s",
                        summarize_text_for_log(e, label="mcp_close_error"),
                    )
                self._session_context = None

            # 再退出 stdio 上下文
            if self._stdio_context:
                try:
                    await self._stdio_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(
                        "Error closing stdio context: error=%s",
                        summarize_text_for_log(e, label="mcp_close_error"),
                    )
                self._stdio_context = None

            # 再退出 streamable HTTP 上下文
            if self._streamable_http_context:
                try:
                    await self._streamable_http_context.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(
                        "Error closing streamable HTTP context: error=%s",
                        summarize_text_for_log(e, label="mcp_close_error"),
                    )
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
