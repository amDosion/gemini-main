"""
MCP (Model Context Protocol) 客户端

用于调用远程 MCP 服务器的工具
"""

from typing import Dict, Any, Optional
import logging
import httpx


logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 客户端
    
    通过 HTTP 连接到远程 MCP 服务器并调用工具
    """
    
    def __init__(
        self,
        server_url: str,
        timeout: float = 30.0
    ):
        """
        初始化 MCP 客户端
        
        Args:
            server_url: MCP 服务器 URL（HTTP 端点）
            timeout: 请求超时时间（秒）
            
        Raises:
            ValueError: URL 格式无效
        """
        # 验证 URL
        if not server_url or not isinstance(server_url, str):
            raise ValueError("server_url must be a non-empty string")
        
        if not server_url.startswith(('http://', 'https://')):
            raise ValueError("server_url must start with http:// or https://")
        
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        
        # 创建 HTTP 客户端
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True
        )
        
        logger.info(f"MCPClient initialized for {self.server_url}")
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        调用远程工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
            
        Raises:
            ValueError: 参数验证失败
            httpx.HTTPError: HTTP 请求失败
            RuntimeError: 工具执行失败
        """
        # 验证参数
        if not tool_name or not isinstance(tool_name, str):
            raise ValueError("tool_name must be a non-empty string")
        
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a dictionary")
        
        logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")
        
        # 构建 JSON-RPC 请求
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            # 发送 POST 请求
            response = await self.client.post(
                f"{self.server_url}/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            # 检查 HTTP 状态码
            response.raise_for_status()
            
            # 解析 JSON 响应
            response_data = response.json()
            
            # 检查 JSON-RPC 错误
            if "error" in response_data:
                error = response_data["error"]
                error_message = error.get("message", "Unknown error")
                logger.error(f"MCP tool call failed: {error_message}")
                raise RuntimeError(f"MCP tool call failed: {error_message}")
            
            # 提取结果
            result = response_data.get("result")
            logger.info(f"MCP tool call succeeded: {tool_name}")
            logger.debug(f"MCP tool result: {result}")
            
            return result
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling MCP tool {tool_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
        logger.info("MCPClient closed")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
