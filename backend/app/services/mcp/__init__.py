"""
MCP (Model Context Protocol) 服务模块

提供 MCP 客户端、工具适配器、Schema 转换等功能
"""

from .types import (
    MCPServerType,
    MCPServerConfig,
    MCPTool,
    MCPToolResult,
    GeminiTool
)

from .client import MCPClient

from .adapter import (
    MCPToolAdapter,
    GeminiToolAdapter,
    OpenAIToolAdapter,
    UniversalToolAdapter
)

from .schema_utils import (
    filter_supported_schema,
    mcp_schema_to_gemini_schema,
    mcp_schema_to_openai_schema,
    validate_schema
)

__all__ = [
    # Types
    "MCPServerType",
    "MCPServerConfig",
    "MCPTool",
    "MCPToolResult",
    "GeminiTool",

    # Client
    "MCPClient",

    # Adapters
    "MCPToolAdapter",
    "GeminiToolAdapter",
    "OpenAIToolAdapter",
    "UniversalToolAdapter",

    # Utils
    "filter_supported_schema",
    "mcp_schema_to_gemini_schema",
    "mcp_schema_to_openai_schema",
    "validate_schema",
]
