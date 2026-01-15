"""
Agent With Tools - 带工具的代理

提供：
- 工具调用循环
- LLM 与工具交互
- 工具结果处理
- 多轮工具调用支持
"""

import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass

from .tool_registry import ToolRegistry, Tool

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """
    工具调用请求
    
    Attributes:
        name: 工具名称
        arguments: 工具参数
        call_id: 调用 ID（用于匹配结果）
    """
    name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None


@dataclass
class ToolCallResult:
    """
    工具调用结果
    
    Attributes:
        call_id: 调用 ID
        name: 工具名称
        result: 执行结果
        success: 是否成功
        error: 错误信息（如果有）
    """
    call_id: Optional[str]
    name: str
    result: Any
    success: bool
    error: Optional[str] = None


class AgentWithTools:
    """
    带工具的代理
    
    支持：
    - 工具调用循环（LLM 决定调用工具 → 执行工具 → 反馈结果 → 继续）
    - 多轮工具调用
    - 工具结果处理
    """
    
    def __init__(
        self,
        name: str,
        google_service: Any,
        tool_registry: ToolRegistry,
        model: str = "gemini-2.0-flash-exp",
        max_tool_iterations: int = 10
    ):
        """
        初始化带工具的代理
        
        Args:
            name: 代理名称
            google_service: GoogleService 实例（用于 LLM 调用）
            tool_registry: 工具注册表
            model: 使用的模型
            max_tool_iterations: 最大工具调用迭代次数（防止无限循环）
        """
        self.name = name
        self.google_service = google_service
        self.tool_registry = tool_registry
        self.model = model
        self.max_tool_iterations = max_tool_iterations
        
        logger.info(f"[AgentWithTools] Initialized: {name} (model: {model})")
    
    async def execute_with_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        使用工具执行任务
        
        流程：
        1. LLM 决定需要哪些工具
        2. 调用工具
        3. 将工具结果反馈给 LLM
        4. 生成最终结果
        
        Args:
            task: 任务描述
            context: 上下文信息（可选）
            available_tools: 可用工具名称列表（可选，如果不提供则使用所有工具）
            
        Returns:
            执行结果
        """
        # 获取可用工具
        if available_tools:
            tools = [self.tool_registry.get_tool(name) for name in available_tools]
            tools = [t for t in tools if t is not None]
        else:
            tools = self.tool_registry.list_tools()
        
        # 转换为 Gemini 格式
        gemini_tools = self._prepare_gemini_tools(tools)
        
        # 构建初始消息
        messages = self._build_initial_messages(task, context)
        
        # 工具调用循环
        iteration = 0
        tool_call_history: List[Dict[str, Any]] = []
        
        while iteration < self.max_tool_iterations:
            iteration += 1
            logger.info(f"[AgentWithTools] Iteration {iteration}/{self.max_tool_iterations}")
            
            # 调用 LLM（带工具）
            # 使用 tools 参数传递工具（如果 GoogleService 支持）
            chat_kwargs = {}
            if gemini_tools:
                chat_kwargs["tools"] = gemini_tools
            
            response = await self.google_service.chat(
                messages=messages,
                model=self.model,
                **chat_kwargs
            )
            
            # 检查是否有工具调用
            tool_calls = self._extract_tool_calls(response)
            
            if not tool_calls:
                # 没有工具调用，返回最终结果
                final_result = self._extract_final_result(response)
                logger.info(f"[AgentWithTools] Task completed after {iteration} iterations")
                return {
                    "result": final_result,
                    "tool_calls": tool_call_history,
                    "iterations": iteration
                }
            
            # 执行工具调用
            tool_results = []
            for tool_call in tool_calls:
                logger.info(f"[AgentWithTools] Calling tool: {tool_call.name}")
                
                try:
                    result = await self.tool_registry.execute_tool(
                        name=tool_call.name,
                        arguments=tool_call.arguments
                    )
                    
                    tool_result = ToolCallResult(
                        call_id=tool_call.call_id,
                        name=tool_call.name,
                        result=result,
                        success=result.get("success", False),
                        error=result.get("error") if not result.get("success") else None
                    )
                    tool_results.append(tool_result)
                    tool_call_history.append({
                        "iteration": iteration,
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "result": result
                    })
                    
                except Exception as e:
                    logger.error(f"[AgentWithTools] Tool execution failed: {e}", exc_info=True)
                    tool_result = ToolCallResult(
                        call_id=tool_call.call_id,
                        name=tool_call.name,
                        result=None,
                        success=False,
                        error=str(e)
                    )
                    tool_results.append(tool_result)
            
            # 将工具结果添加到消息中，继续循环
            messages = self._add_tool_results_to_messages(messages, response, tool_results)
        
        # 达到最大迭代次数
        logger.warning(f"[AgentWithTools] Reached max iterations ({self.max_tool_iterations})")
        return {
            "result": "Task execution reached maximum iterations",
            "tool_calls": tool_call_history,
            "iterations": iteration,
            "warning": "Maximum tool call iterations reached"
        }
    
    def _prepare_gemini_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """
        准备 Gemini 格式的工具列表
        
        Args:
            tools: 工具列表
            
        Returns:
            Gemini 工具列表
        """
        if not tools:
            return []
        
        # 使用 ToolRegistry 的转换方法
        return self.tool_registry.to_gemini_tools()
    
    def _build_initial_messages(
        self,
        task: str,
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        构建初始消息
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            消息列表
        """
        system_instruction = f"""你是一个智能代理，可以使用工具来完成任务。

任务：{task}

你可以使用提供的工具来获取信息、执行操作等。如果需要使用工具，请明确调用工具。
"""
        
        if context:
            system_instruction += f"\n上下文信息：{context}"
        
        messages = [
            {
                "role": "user",
                "content": task
            }
        ]
        
        return messages
    
    def _extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        从 LLM 响应中提取工具调用
        
        Args:
            response: LLM 响应
            
        Returns:
            工具调用列表
        """
        tool_calls = []
        
        # 处理不同的响应格式
        if isinstance(response, dict):
            # 检查 function_calls 字段（Gemini Function Calling 格式）
            if "function_calls" in response:
                for fc in response["function_calls"]:
                    # 处理不同的格式
                    if hasattr(fc, 'name'):
                        # 对象格式
                        tool_calls.append(ToolCall(
                            name=fc.name,
                            arguments=dict(fc.args) if hasattr(fc, 'args') and fc.args else {},
                            call_id=getattr(fc, 'id', None)
                        ))
                    elif isinstance(fc, dict):
                        # 字典格式
                        tool_calls.append(ToolCall(
                            name=fc.get("name", ""),
                            arguments=fc.get("args", {}),
                            call_id=fc.get("id")
                        ))
            
            # 检查 candidates[0].content.parts 中的 functionCall
            elif "candidates" in response and len(response["candidates"]) > 0:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            # 处理不同的格式
                            if hasattr(fc, 'name'):
                                tool_calls.append(ToolCall(
                                    name=fc.name,
                                    arguments=dict(fc.args) if hasattr(fc, 'args') and fc.args else {},
                                    call_id=getattr(fc, 'id', None)
                                ))
                            elif isinstance(fc, dict):
                                tool_calls.append(ToolCall(
                                    name=fc.get("name", ""),
                                    arguments=fc.get("args", {}),
                                    call_id=fc.get("id")
                                ))
            
            # 检查是否有 function_calls 属性（对象格式）
            elif hasattr(response, 'function_calls') and response.function_calls:
                for fc in response.function_calls:
                    tool_calls.append(ToolCall(
                        name=fc.name if hasattr(fc, 'name') else "",
                        arguments=dict(fc.args) if hasattr(fc, 'args') and fc.args else {},
                        call_id=getattr(fc, 'id', None)
                    ))
        
        return tool_calls
    
    def _extract_final_result(self, response: Dict[str, Any]) -> str:
        """
        提取最终结果（文本响应）
        
        Args:
            response: LLM 响应
            
        Returns:
            文本结果
        """
        if isinstance(response, dict):
            # 检查 text 字段
            if "text" in response:
                return response["text"]
            
            # 检查 candidates[0].content.parts 中的 text
            if "candidates" in response and len(response["candidates"]) > 0:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    texts = [
                        part.get("text", "")
                        for part in candidate["content"]["parts"]
                        if "text" in part
                    ]
                    if texts:
                        return " ".join(texts)
            
            # 检查 message.content
            if "message" in response and "content" in response["message"]:
                return response["message"]["content"]
        
        return str(response)
    
    def _add_tool_results_to_messages(
        self,
        messages: List[Dict[str, Any]],
        previous_response: Dict[str, Any],
        tool_results: List[ToolCallResult]
    ) -> List[Dict[str, Any]]:
        """
        将工具结果添加到消息中
        
        Args:
            messages: 当前消息列表
            previous_response: 上一次 LLM 响应
            tool_results: 工具执行结果列表
            
        Returns:
            更新后的消息列表
        """
        # 添加上一次的响应（包含工具调用）
        new_messages = messages.copy()
        
        # 添加助手响应（包含工具调用）
        assistant_message = {
            "role": "model",
            "parts": []
        }
        
        # 添加工具调用部分
        for tool_result in tool_results:
            assistant_message["parts"].append({
                "functionCall": {
                    "name": tool_result.name,
                    "args": {}  # 参数已经在之前的消息中
                }
            })
        
        new_messages.append(assistant_message)
        
        # 添加工具结果
        function_response = {
            "role": "user",
            "parts": []
        }
        
        for tool_result in tool_results:
            function_response["parts"].append({
                "functionResponse": {
                    "name": tool_result.name,
                    "response": {
                        "result": tool_result.result if tool_result.success else None,
                        "error": tool_result.error
                    }
                }
            })
        
        new_messages.append(function_response)
        
        return new_messages
    
    async def stream_execute_with_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行（带工具）
        
        Args:
            task: 任务描述
            context: 上下文信息
            available_tools: 可用工具列表
            
        Yields:
            执行事件（text/tool_call/tool_result/final）
        """
        # 获取可用工具
        if available_tools:
            tools = [self.tool_registry.get_tool(name) for name in available_tools]
            tools = [t for t in tools if t is not None]
        else:
            tools = self.tool_registry.list_tools()
        
        gemini_tools = self._prepare_gemini_tools(tools)
        messages = self._build_initial_messages(task, context)
        
        iteration = 0
        
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # 流式调用 LLM
            async for chunk in self.google_service.stream_chat(
                messages=messages,
                model=self.model,
                tools=gemini_tools if gemini_tools else None
            ):
                # 检查是否是工具调用
                tool_calls = self._extract_tool_calls(chunk)
                
                if tool_calls:
                    # 执行工具调用
                    for tool_call in tool_calls:
                        yield {
                            "event_type": "tool_call",
                            "tool": tool_call.name,
                            "arguments": tool_call.arguments
                        }
                        
                        result = await self.tool_registry.execute_tool(
                            name=tool_call.name,
                            arguments=tool_call.arguments
                        )
                        
                        yield {
                            "event_type": "tool_result",
                            "tool": tool_call.name,
                            "result": result
                        }
                else:
                    # 文本输出
                    text = self._extract_final_result(chunk)
                    if text:
                        yield {
                            "event_type": "text",
                            "text": text
                        }
            
            # 检查是否需要继续（简化实现，实际需要更复杂的逻辑）
            break
        
        yield {
            "event_type": "complete"
        }
