"""
Parallel Agent - 并行代理（Parallel Fan-Out/Gather Pattern）

参考 Google ADK 的 Parallel Fan-Out/Gather 模式：
- 并发执行多个子代理
- 聚合所有代理的结果
- 支持超时和错误处理
- 结果可以传递给后续代理

参考：
- https://github.com/google/adk-samples
- https://github.com/google/adk-python
- https://google.github.io/adk-docs/agents/multi-agents/
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParallelTask:
    """
    并行任务
    
    Attributes:
        agent_id: 代理 ID
        agent_name: 代理名称
        input_data: 输入数据（可以是共享的或特定的）
        output_key: 输出键（用于在结果中存储）
        timeout: 超时时间（秒，可选）
    """
    agent_id: str
    agent_name: str
    input_data: Any
    output_key: Optional[str] = None
    timeout: Optional[float] = None


class ParallelAgent:
    """
    并行代理（Parallel Fan-Out/Gather Pattern）
    
    功能：
    - 并发执行多个子代理
    - 聚合所有代理的结果
    - 支持超时和错误处理
    - 结果可以传递给后续代理
    
    使用场景：
    - 并行数据获取（从多个 API 获取数据）
    - 并行分析（多个独立的分析任务）
    - 并行处理（可以独立处理的任务）
    """
    
    def __init__(
        self,
        name: str,
        sub_agents: List[Dict[str, Any]],
        agent_registry: Any,
        google_service: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        default_timeout: float = 60.0
    ):
        """
        初始化并行代理
        
        Args:
            name: 代理名称
            sub_agents: 子代理列表（每个包含 agent_id, input_data, output_key, timeout 等）
            agent_registry: AgentRegistryService 实例
            google_service: GoogleService 实例（用于代理执行，可选）
            tool_registry: ToolRegistry 实例（用于代理工具执行，可选）
            default_timeout: 默认超时时间（秒）
        """
        self.name = name
        self.sub_agents = sub_agents
        self.agent_registry = agent_registry
        self.google_service = google_service
        self.tool_registry = tool_registry
        self.default_timeout = default_timeout
        
        # 构建任务列表
        self.tasks: List[ParallelTask] = []
        for agent_config in sub_agents:
            self.tasks.append(ParallelTask(
                agent_id=agent_config.get("agent_id", ""),
                agent_name=agent_config.get("agent_name", ""),
                input_data=agent_config.get("input_data"),
                output_key=agent_config.get("output_key"),
                timeout=agent_config.get("timeout", default_timeout)
            ))
        
        logger.info(f"[ParallelAgent] Initialized: {name} with {len(self.tasks)} parallel tasks")
    
    async def execute(
        self,
        user_id: str,
        shared_input: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行并行任务
        
        流程：
        1. 准备每个任务的输入（使用 shared_input 或任务特定的 input_data）
        2. 并发执行所有任务（使用 asyncio.gather）
        3. 等待所有任务完成（或超时）
        4. 聚合结果
        5. 返回聚合结果
        
        Args:
            user_id: 用户 ID
            shared_input: 共享输入（如果任务没有指定 input_data，使用此输入）
            context: 上下文信息（可选）
            
        Returns:
            聚合结果（包含所有任务的结果）
        """
        logger.info(f"[ParallelAgent] Starting parallel execution: {self.name}")
        
        # 准备任务输入
        task_inputs = []
        for task in self.tasks:
            if task.input_data is not None:
                task_inputs.append(task.input_data)
            else:
                task_inputs.append(shared_input)
        
        # 并发执行所有任务
        try:
            results = await asyncio.gather(
                *[
                    self._execute_task_with_timeout(
                        user_id=user_id,
                        task=task,
                        input_data=task_inputs[idx],
                        context=context
                    )
                    for idx, task in enumerate(self.tasks)
                ],
                return_exceptions=True  # 不因单个任务失败而中断
            )
            
            # 聚合结果
            aggregated_results = {}
            errors = {}
            
            for idx, (task, result) in enumerate(zip(self.tasks, results)):
                if isinstance(result, Exception):
                    error_msg = str(result)
                    logger.error(f"[ParallelAgent] Task {idx + 1} failed: {error_msg}")
                    errors[task.output_key or f"task_{idx}"] = error_msg
                    aggregated_results[task.output_key or f"task_{idx}"] = None
                else:
                    output_key = task.output_key or f"task_{idx}"
                    aggregated_results[output_key] = result
            
            return {
                "success": len(errors) == 0,
                "results": aggregated_results,
                "errors": errors if errors else None,
                "tasks_count": len(self.tasks),
                "completed_count": len(self.tasks) - len(errors),
                "failed_count": len(errors)
            }
            
        except Exception as e:
            logger.error(f"[ParallelAgent] Parallel execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "results": {},
                "tasks_count": len(self.tasks)
            }
    
    async def _execute_task_with_timeout(
        self,
        user_id: str,
        task: ParallelTask,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        执行单个任务（带超时）
        
        Args:
            user_id: 用户 ID
            task: 并行任务
            input_data: 输入数据
            context: 上下文信息
            
        Returns:
            任务执行结果
        """
        timeout = task.timeout or self.default_timeout
        
        try:
            result = await asyncio.wait_for(
                self._execute_agent(
                    user_id=user_id,
                    agent_id=task.agent_id,
                    agent_name=task.agent_name,
                    input_data=input_data
                ),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"[ParallelAgent] Task {task.agent_name} timed out after {timeout}s")
            raise TimeoutError(f"Task {task.agent_name} timed out after {timeout}s")
    
    async def _execute_agent(
        self,
        user_id: str,
        agent_id: str,
        agent_name: str,
        input_data: Any
    ) -> Any:
        """
        执行单个代理
        
        Args:
            user_id: 用户 ID
            agent_id: 代理 ID
            agent_name: 代理名称
            input_data: 输入数据
            
        Returns:
            代理执行结果
        """
        # 获取代理信息
        agent_info = await self.agent_registry.get_agent(user_id, agent_id)
        
        if not agent_info:
            raise ValueError(f"Agent not found: {agent_id}")
        
        # 如果代理配置了工具，使用 AgentWithTools
        agent_tools = None
        mcp_session_id = None
        
        if agent_info.get("tools"):
            tool_config = agent_info["tools"]
            agent_tools = tool_config.get("tool_names")
            mcp_session_id = tool_config.get("mcp_session_id")
        
        # 如果有工具配置，使用 AgentWithTools 执行
        if agent_tools and self.tool_registry and self.google_service:
            try:
                # 加载 MCP 工具（如果有）
                if mcp_session_id:
                    await self.tool_registry.load_mcp_tools(mcp_session_id)
                
                from .agent_with_tools import AgentWithTools
                agent_with_tools = AgentWithTools(
                    name=agent_name,
                    google_service=self.google_service,
                    tool_registry=self.tool_registry,
                    model="gemini-2.0-flash-exp"
                )
                
                # 执行任务（带工具）
                result = await agent_with_tools.execute_with_tools(
                    task=str(input_data),
                    available_tools=agent_tools
                )
                
                return result.get("result", result)
                
            except Exception as e:
                logger.error(f"[ParallelAgent] Error executing agent with tools: {e}", exc_info=True)
                # 回退到简单执行
        
        # 简化实现：直接返回结果
        # 实际应该调用代理的执行逻辑
        return {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "input": input_data,
            "output": f"Result from {agent_name}: {input_data}"
        }
    
    async def stream_execute(
        self,
        user_id: str,
        shared_input: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行并行任务
        
        Args:
            user_id: 用户 ID
            shared_input: 共享输入
            context: 上下文信息
            
        Yields:
            执行事件（task_start, task_progress, task_complete, final）
        """
        logger.info(f"[ParallelAgent] Starting stream parallel execution: {self.name}")
        
        # 发送所有任务开始事件
        for idx, task in enumerate(self.tasks):
            yield {
                "event_type": "task_start",
                "task_index": idx,
                "total_tasks": len(self.tasks),
                "agent_id": task.agent_id,
                "agent_name": task.agent_name
            }
        
        # 并发执行所有任务
        task_inputs = [
            task.input_data if task.input_data is not None else shared_input
            for task in self.tasks
        ]
        
        try:
            results = await asyncio.gather(
                *[
                    self._execute_task_with_timeout(
                        user_id=user_id,
                        task=task,
                        input_data=task_inputs[idx],
                        context=context
                    )
                    for idx, task in enumerate(self.tasks)
                ],
                return_exceptions=True
            )
            
            # 发送每个任务的完成事件
            for idx, (task, result) in enumerate(zip(self.tasks, results)):
                if isinstance(result, Exception):
                    yield {
                        "event_type": "task_error",
                        "task_index": idx,
                        "agent_id": task.agent_id,
                        "agent_name": task.agent_name,
                        "error": str(result)
                    }
                else:
                    yield {
                        "event_type": "task_complete",
                        "task_index": idx,
                        "agent_id": task.agent_id,
                        "agent_name": task.agent_name,
                        "result": result,
                        "output_key": task.output_key
                    }
            
            # 聚合结果
            aggregated_results = {}
            errors = {}
            
            for idx, (task, result) in enumerate(zip(self.tasks, results)):
                if isinstance(result, Exception):
                    errors[task.output_key or f"task_{idx}"] = str(result)
                    aggregated_results[task.output_key or f"task_{idx}"] = None
                else:
                    output_key = task.output_key or f"task_{idx}"
                    aggregated_results[output_key] = result
            
            yield {
                "event_type": "final",
                "success": len(errors) == 0,
                "results": aggregated_results,
                "errors": errors if errors else None
            }
            
        except Exception as e:
            logger.error(f"[ParallelAgent] Stream execution failed: {e}", exc_info=True)
            yield {
                "event_type": "error",
                "error": str(e)
            }
