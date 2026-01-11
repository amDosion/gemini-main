"""
工具编排器

统一处理 Function Calling、Built-in Tools、Remote MCP
"""

from typing import Dict, Callable, Any, List, Optional
import logging

from google import genai

from .mcp_client import MCPClient


logger = logging.getLogger(__name__)


class FunctionCall:
    """工具调用对象"""
    def __init__(self, name: str, arguments: Dict[str, Any], id: str):
        self.name = name
        self.arguments = arguments
        self.id = id


class FunctionResult:
    """工具执行结果"""
    def __init__(self, name: str, call_id: str, result: Any):
        self.name = name
        self.call_id = call_id
        self.result = result


class ToolOrchestrator:
    """
    工具编排器
    
    统一处理 Function Calling、Built-in Tools、Remote MCP
    """
    
    def __init__(self):
        """初始化工具编排器"""
        self.function_registry: Dict[str, Callable] = {}
        self.mcp_clients: Dict[str, MCPClient] = {}
        logger.info("ToolOrchestrator initialized")
    
    def register_mcp_server(
        self,
        server_name: str,
        server_url: str,
        timeout: float = 30.0
    ) -> None:
        """
        注册 MCP 服务器
        
        Args:
            server_name: 服务器名称
            server_url: 服务器 URL
            timeout: 请求超时时间
            
        Raises:
            ValueError: 参数验证失败
        """
        if not server_name or not isinstance(server_name, str):
            raise ValueError("server_name must be a non-empty string")
        
        # 创建 MCP 客户端
        mcp_client = MCPClient(server_url=server_url, timeout=timeout)
        self.mcp_clients[server_name] = mcp_client
        
        logger.info(f"MCP server registered: {server_name} at {server_url}")
    
    def register_function(
        self,
        name: str,
        func: Callable,
        schema: dict
    ) -> None:
        """
        注册自定义函数
        
        Args:
            name: 函数名称
            func: 函数对象
            schema: JSON Schema 定义
            
        Raises:
            ValueError: 参数验证失败
        """
        # 验证参数
        if not name or not isinstance(name, str):
            raise ValueError("Function name must be a non-empty string")
        
        if not callable(func):
            raise ValueError(f"Function {name} must be callable")
        
        if not isinstance(schema, dict):
            raise ValueError(f"Schema for function {name} must be a dictionary")
        
        # 注册函数
        self.function_registry[name] = {
            "function": func,
            "schema": schema
        }
        
        logger.info(f"Function registered: {name}")
        logger.debug(f"Function schema: {schema}")
    
    async def execute_tool_call(
        self,
        tool_call: FunctionCall
    ) -> FunctionResult:
        """
        执行工具调用
        
        支持：
        - 自定义函数（注册在 function_registry）
        - MCP 远程工具（格式：server_name.tool_name）
        
        Args:
            tool_call: 模型返回的工具调用对象
            
        Returns:
            工具执行结果
            
        Raises:
            KeyError: 工具不存在
            Exception: 工具执行失败
        """
        try:
            # 检查是否是 MCP 工具（格式：server_name.tool_name）
            if '.' in tool_call.name:
                server_name, tool_name = tool_call.name.split('.', 1)
                
                # 查找 MCP 客户端
                if server_name not in self.mcp_clients:
                    raise KeyError(f"MCP server {server_name} not found in registry")
                
                mcp_client = self.mcp_clients[server_name]
                
                logger.info(f"Executing MCP tool call: {server_name}.{tool_name} with args: {tool_call.arguments}")
                
                # 调用远程工具
                result = await mcp_client.call_tool(
                    tool_name=tool_name,
                    arguments=tool_call.arguments
                )
                
                logger.info(f"MCP tool call {tool_call.name} executed successfully")
                logger.debug(f"MCP tool result: {result}")
                
                return FunctionResult(
                    name=tool_call.name,
                    call_id=tool_call.id,
                    result=result
                )
            
            # 否则，查找本地注册的函数
            if tool_call.name not in self.function_registry:
                raise KeyError(f"Function {tool_call.name} not found in registry")
            
            func_info = self.function_registry[tool_call.name]
            func = func_info["function"]
            
            logger.info(f"Executing tool call: {tool_call.name} with args: {tool_call.arguments}")
            
            # 执行函数
            # 检查函数是否是异步的
            import inspect
            if inspect.iscoroutinefunction(func):
                result = await func(**tool_call.arguments)
            else:
                result = func(**tool_call.arguments)
            
            logger.info(f"Tool call {tool_call.name} executed successfully")
            logger.debug(f"Tool call result: {result}")
            
            # 返回结果
            return FunctionResult(
                name=tool_call.name,
                call_id=tool_call.id,
                result=result
            )
            
        except KeyError as e:
            logger.error(f"Tool not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_call.name}: {e}")
            # 返回错误结果而不是抛出异常，让模型知道工具执行失败
            return FunctionResult(
                name=tool_call.name,
                call_id=tool_call.id,
                result={"error": str(e)}
            )
    
    def detect_tool_calls(
        self,
        interaction: Any
    ) -> List[FunctionCall]:
        """
        检测交互输出中的工具调用
        
        Args:
            interaction: Interaction 对象（google.genai SDK 返回的动态对象）
            
        Returns:
            工具调用列表
        """
        tool_calls = []
        
        # 检查 outputs 是否存在
        if not interaction.outputs:
            logger.debug("No outputs in interaction")
            return tool_calls
        
        # 遍历 outputs 数组
        for output in interaction.outputs:
            try:
                # 检查 type 字段
                output_type = getattr(output, 'type', None)
                if output_type != 'function_call':
                    continue
                
                # 提取必需字段
                name = getattr(output, 'name', None)
                arguments = getattr(output, 'arguments', None)
                call_id = getattr(output, 'id', None)
                
                # 验证字段
                if not name or not isinstance(name, str):
                    logger.warning(f"Invalid function_call: missing or invalid name")
                    continue
                
                if not call_id or not isinstance(call_id, str):
                    logger.warning(f"Invalid function_call: missing or invalid id")
                    continue
                
                if arguments is None or not isinstance(arguments, dict):
                    logger.warning(f"Invalid function_call: missing or invalid arguments")
                    continue
                
                # 创建 FunctionCall 对象
                tool_call = FunctionCall(
                    name=name,
                    arguments=arguments,
                    id=call_id
                )
                tool_calls.append(tool_call)
                
                logger.info(f"Detected tool call: {name} (id={call_id})")
                
            except Exception as e:
                logger.error(f"Error processing output: {e}")
                continue
        
        logger.info(f"Detected {len(tool_calls)} tool calls")
        return tool_calls
    
    async def handle_tool_loop(
        self,
        interaction: Any,
        client: genai.Client,
        max_iterations: int = 10
    ) -> Any:
        """
        处理工具调用循环
        
        持续检测和执行工具调用，直到模型返回最终响应
        
        Args:
            interaction: 初始 Interaction 对象（google.genai SDK 返回的动态对象）
            client: GenAI Client
            max_iterations: 最大迭代次数（防止无限循环）
            
        Returns:
            最终的 Interaction 对象（google.genai SDK 返回的动态对象）
            
        Raises:
            RuntimeError: 工具调用循环超过最大迭代次数
            ValueError: 参数验证失败
        """
        # 参数验证
        if not interaction:
            raise ValueError("interaction cannot be None")
        if not client:
            raise ValueError("client cannot be None")
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        
        logger.info(f"Starting tool loop for interaction {interaction.id}")
        
        iteration = 0
        current_interaction = interaction
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Tool loop iteration {iteration}/{max_iterations}")
            
            # 1. 检测工具调用
            tool_calls = self.detect_tool_calls(current_interaction)
            
            # 如果没有工具调用，返回最终结果
            if not tool_calls:
                logger.info(f"No tool calls detected, tool loop completed after {iteration} iterations")
                return current_interaction
            
            # 2. 并行执行所有工具调用
            logger.info(f"Executing {len(tool_calls)} tool calls in parallel")
            import asyncio
            tool_results = await asyncio.gather(
                *[self.execute_tool_call(tool_call) for tool_call in tool_calls],
                return_exceptions=True
            )
            
            # 3. 构建 function_result Content 列表
            function_results = []
            for result in tool_results:
                # 处理执行异常
                if isinstance(result, Exception):
                    logger.error(f"Tool execution failed: {result}")
                    continue
                
                # 构建 function_result Content
                function_result_content = {
                    "type": "function_result",
                    "name": result.name,
                    "call_id": result.call_id,
                    "result": result.result
                }
                function_results.append(function_result_content)
            
            if not function_results:
                logger.error("All tool executions failed")
                raise RuntimeError("All tool executions failed")
            
            logger.info(f"Sending {len(function_results)} function results back to model")
            
            # 4. 发送工具结果回模型
            try:
                new_interaction = client.interactions.create(
                    model=current_interaction.model if hasattr(current_interaction, 'model') else None,
                    agent=current_interaction.agent if hasattr(current_interaction, 'agent') else None,
                    input=function_results,
                    previous_interaction_id=current_interaction.id
                )
                
                logger.info(f"Received new interaction: {new_interaction.id}")
                current_interaction = new_interaction
                
            except Exception as e:
                logger.error(f"Failed to send function results to model: {e}")
                raise
        
        # 超过最大迭代次数
        logger.error(f"Tool loop exceeded max iterations ({max_iterations})")
        raise RuntimeError(f"Tool loop exceeded max iterations ({max_iterations})")
