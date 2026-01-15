"""
MCP 类型定义
定义 MCP 服务使用的数据类型
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class MCPServerType(str, Enum):
    """MCP 服务器类型"""
    STDIO = "stdio"       # 标准输入输出（进程通信）
    SSE = "sse"           # Server-Sent Events（HTTP 流）
    HTTP = "http"         # HTTP（自定义）


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "is_error": self.is_error
        }


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    server_type: MCPServerType
    command: Optional[str] = None           # stdio: 命令（如 "node", "python"）
    args: Optional[List[str]] = None        # stdio: 参数（如 ["server.js"]）
    env: Optional[Dict[str, str]] = None    # stdio: 环境变量
    url: Optional[str] = None               # sse/http: 服务器 URL
    timeout: float = 30.0                   # 超时时间（秒）

    def validate(self) -> None:
        """验证配置"""
        if self.server_type == MCPServerType.STDIO:
            if not self.command:
                raise ValueError("stdio server requires 'command' parameter")
        elif self.server_type in (MCPServerType.SSE, MCPServerType.HTTP):
            if not self.url:
                raise ValueError(f"{self.server_type.value} server requires 'url' parameter")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "server_type": self.server_type.value,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "url": self.url,
            "timeout": self.timeout
        }


@dataclass
class GeminiTool:
    """Gemini 工具定义（用于转换）"""
    name: str
    description: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
