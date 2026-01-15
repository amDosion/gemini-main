"""
MCP 工具适配器
将 MCP 工具转换为不同 AI 模型的格式（Gemini、OpenAI 等）
参考 Google Gemini SDK 的 McpToGenAiToolAdapter 实现
"""

from typing import Dict, Any, List, Optional
import logging

from .types import MCPTool, GeminiTool, MCPToolResult
from .schema_utils import mcp_schema_to_gemini_schema, mcp_schema_to_openai_schema
from .client import MCPClient

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """
    MCP 工具适配器基类

    提供 MCP 工具到其他格式的转换能力
    """

    def __init__(self, client: MCPClient):
        """
        初始化适配器

        Args:
            client: MCP 客户端实例
        """
        self.client = client
        self._tool_map: Dict[str, MCPTool] = {}

    async def load_tools(self) -> List[MCPTool]:
        """
        加载工具列表

        Returns:
            MCP 工具列表
        """
        tools = await self.client.list_tools()
        self._tool_map = {tool.name: tool for tool in tools}
        logger.info(f"Loaded {len(tools)} tools into adapter")
        return tools

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """
        获取指定工具

        Args:
            tool_name: 工具名称

        Returns:
            MCP 工具，如果不存在则返回 None
        """
        return self._tool_map.get(tool_name)

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """
        调用工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具调用结果
        """
        return await self.client.call_tool(tool_name, arguments)


class GeminiToolAdapter(MCPToolAdapter):
    """
    Gemini 工具适配器

    将 MCP 工具转换为 Gemini Function Calling 格式
    参考 Google Gemini SDK 的实现
    """

    def to_gemini_tools(self) -> List[Dict[str, Any]]:
        """
        转换为 Gemini 工具格式

        Returns:
            Gemini 工具列表

        Example:
            >>> adapter = GeminiToolAdapter(client)
            >>> await adapter.load_tools()
            >>> gemini_tools = adapter.to_gemini_tools()
            >>> # 返回格式：
            >>> # [{
            >>> #     "function_declarations": [{
            >>> #         "name": "get_weather",
            >>> #         "description": "Get weather info",
            >>> #         "parameters": {...}
            >>> #     }]
            >>> # }]
        """
        if not self._tool_map:
            logger.warning("No tools loaded. Call load_tools() first.")
            return []

        # Gemini 格式：Tool 包含多个 FunctionDeclaration
        function_declarations = []

        for tool_name, tool in self._tool_map.items():
            # 转换 Schema
            parameters = mcp_schema_to_gemini_schema(tool.input_schema)

            function_declaration = {
                "name": tool.name,
                "description": tool.description,
                "parameters": parameters
            }

            function_declarations.append(function_declaration)

        # Gemini 工具格式
        gemini_tool = {
            "function_declarations": function_declarations
        }

        logger.info(f"Converted {len(function_declarations)} tools to Gemini format")
        return [gemini_tool]

    def to_gemini_tools_list(self) -> List[GeminiTool]:
        """
        转换为 Gemini 工具对象列表

        Returns:
            GeminiTool 对象列表
        """
        gemini_tools = []

        for tool_name, tool in self._tool_map.items():
            parameters = mcp_schema_to_gemini_schema(tool.input_schema)

            gemini_tool = GeminiTool(
                name=tool.name,
                description=tool.description,
                parameters=parameters
            )

            gemini_tools.append(gemini_tool)

        return gemini_tools


class OpenAIToolAdapter(MCPToolAdapter):
    """
    OpenAI 工具适配器

    将 MCP 工具转换为 OpenAI Function Calling 格式
    """

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """
        转换为 OpenAI 工具格式

        Returns:
            OpenAI 工具列表

        Example:
            >>> adapter = OpenAIToolAdapter(client)
            >>> await adapter.load_tools()
            >>> openai_tools = adapter.to_openai_tools()
            >>> # 返回格式：
            >>> # [{
            >>> #     "type": "function",
            >>> #     "function": {
            >>> #         "name": "get_weather",
            >>> #         "description": "Get weather info",
            >>> #         "parameters": {...}
            >>> #     }
            >>> # }]
        """
        if not self._tool_map:
            logger.warning("No tools loaded. Call load_tools() first.")
            return []

        openai_tools = []

        for tool_name, tool in self._tool_map.items():
            # 转换 Schema
            parameters = mcp_schema_to_openai_schema(tool.input_schema)

            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters
                }
            }

            openai_tools.append(openai_tool)

        logger.info(f"Converted {len(openai_tools)} tools to OpenAI format")
        return openai_tools


class UniversalToolAdapter(MCPToolAdapter):
    """
    通用工具适配器

    支持转换为多种格式
    """

    def to_format(self, format_type: str) -> List[Dict[str, Any]]:
        """
        转换为指定格式

        Args:
            format_type: 格式类型（"gemini", "openai", "anthropic"）

        Returns:
            指定格式的工具列表

        Raises:
            ValueError: 不支持的格式类型
        """
        if format_type == "gemini":
            adapter = GeminiToolAdapter(self.client)
            adapter._tool_map = self._tool_map
            return adapter.to_gemini_tools()

        elif format_type == "openai":
            adapter = OpenAIToolAdapter(self.client)
            adapter._tool_map = self._tool_map
            return adapter.to_openai_tools()

        elif format_type == "anthropic":
            # Anthropic Claude 格式（与 OpenAI 类似）
            adapter = OpenAIToolAdapter(self.client)
            adapter._tool_map = self._tool_map
            return adapter.to_openai_tools()

        else:
            raise ValueError(
                f"Unsupported format type: {format_type}. "
                f"Supported: gemini, openai, anthropic"
            )

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        转换为字典格式（工具名 -> 工具定义）

        Returns:
            工具字典
        """
        return {
            tool_name: tool.to_dict()
            for tool_name, tool in self._tool_map.items()
        }
