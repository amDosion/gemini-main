"""
Sequential Agent - 顺序代理（Sequential Pipeline Pattern）

参考 Google ADK 的 Sequential Pipeline 模式：
- 按顺序执行子代理链
- 会话状态在代理间传递
- 支持输出键（output_key）机制
- 每个代理的输出作为下一个代理的输入

参考：
- https://github.com/google/adk-samples
- https://github.com/google/adk-python
- https://google.github.io/adk-docs/agents/multi-agents/
"""

import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SequentialStep:
    """
    顺序执行步骤
    
    Attributes:
        agent_id: 代理 ID
        agent_name: 代理名称
        output_key: 输出键（用于在会话状态中存储结果）
        input_key: 输入键（从会话状态中读取输入，可选）
    """
    agent_id: str
    agent_name: str
    output_key: Optional[str] = None
    input_key: Optional[str] = None


class SequentialAgent:
    """
    顺序代理（Sequential Pipeline Pattern）
    
    功能：
    - 按顺序执行子代理链
    - 会话状态在代理间传递
    - 支持输出键（output_key）机制
    - 每个代理的输出作为下一个代理的输入
    
    使用场景：
    - 数据预处理管道（读取 -> 清理 -> 分析 -> 报告）
    - 图像处理管道（分析 -> 编辑 -> 验证）
    - 多步骤任务，每个步骤依赖前一步的结果
    """
    
    def __init__(
        self,
        name: str,
        sub_agents: List[Dict[str, Any]],
        agent_registry: Any,
        google_service: Optional[Any] = None,
        tool_registry: Optional[Any] = None
    ):
        """
        初始化顺序代理
        
        Args:
            name: 代理名称
            sub_agents: 子代理列表（每个包含 agent_id, output_key, input_key 等）
            agent_registry: AgentRegistryService 实例
            google_service: GoogleService 实例（用于代理执行，可选）
            tool_registry: ToolRegistry 实例（用于代理工具执行，可选）
        """
        self.name = name
        self.sub_agents = sub_agents
        self.agent_registry = agent_registry
        self.google_service = google_service
        self.tool_registry = tool_registry
        
        # 构建步骤列表
        self.steps: List[SequentialStep] = []
        for agent_config in sub_agents:
            self.steps.append(SequentialStep(
                agent_id=agent_config.get("agent_id", ""),
                agent_name=agent_config.get("agent_name", ""),
                output_key=agent_config.get("output_key"),
                input_key=agent_config.get("input_key")
            ))
        
        logger.info(f"[SequentialAgent] Initialized: {name} with {len(self.steps)} steps")
    
    async def execute(
        self,
        user_id: str,
        initial_input: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行顺序管道
        
        流程：
        1. 初始化会话状态（包含初始输入）
        2. 按顺序执行每个子代理
        3. 将每个代理的输出存储到会话状态（使用 output_key）
        4. 下一个代理从会话状态读取输入（使用 input_key）
        5. 返回最终结果
        
        Args:
            user_id: 用户 ID
            initial_input: 初始输入
            context: 上下文信息（可选）
            
        Returns:
            执行结果（包含所有步骤的输出）
        """
        logger.info(f"[SequentialAgent] Starting execution: {self.name}")
        
        # 初始化会话状态
        session_state: Dict[str, Any] = {
            "input": initial_input,
            "context": context or {},
            "steps": []
        }
        
        # 按顺序执行每个步骤
        for idx, step in enumerate(self.steps):
            logger.info(f"[SequentialAgent] Executing step {idx + 1}/{len(self.steps)}: {step.agent_name}")
            
            try:
                # 准备输入
                step_input = self._prepare_step_input(step, session_state)
                
                # 执行代理
                step_result = await self._execute_agent(
                    user_id=user_id,
                    agent_id=step.agent_id,
                    agent_name=step.agent_name,
                    input_data=step_input
                )
                
                # 存储结果到会话状态
                if step.output_key:
                    session_state[step.output_key] = step_result
                else:
                    # 如果没有指定 output_key，使用默认键
                    session_state[f"step_{idx}_output"] = step_result
                
                # 记录步骤信息
                session_state["steps"].append({
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "input": step_input,
                    "output": step_result,
                    "output_key": step.output_key
                })
                
                logger.info(f"[SequentialAgent] Step {idx + 1} completed: {step.agent_name}")
                
            except Exception as e:
                logger.error(f"[SequentialAgent] Step {idx + 1} failed: {e}", exc_info=True)
                session_state["steps"].append({
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "error": str(e)
                })
                # 可以选择继续执行或停止
                # 这里选择停止，返回部分结果
                session_state["error"] = f"Step {idx + 1} failed: {str(e)}"
                break
        
        # 返回最终结果
        return {
            "success": "error" not in session_state,
            "final_output": session_state.get(self.steps[-1].output_key) if self.steps else None,
            "session_state": session_state,
            "steps_count": len(session_state["steps"])
        }
    
    def _prepare_step_input(
        self,
        step: SequentialStep,
        session_state: Dict[str, Any]
    ) -> Any:
        """
        准备步骤输入
        
        如果指定了 input_key，从会话状态中读取
        否则使用初始输入或上一个步骤的输出
        
        Args:
            step: 执行步骤
            session_state: 会话状态
            
        Returns:
            步骤输入
        """
        if step.input_key:
            # 从会话状态中读取指定键的值
            return session_state.get(step.input_key, session_state.get("input"))
        else:
            # 使用上一个步骤的输出，如果没有则使用初始输入
            if session_state["steps"]:
                last_step = session_state["steps"][-1]
                return last_step.get("output", session_state.get("input"))
            else:
                return session_state.get("input")
    
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
                logger.error(f"[SequentialAgent] Error executing agent with tools: {e}", exc_info=True)
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
        initial_input: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行顺序管道
        
        Args:
            user_id: 用户 ID
            initial_input: 初始输入
            context: 上下文信息
            
        Yields:
            执行事件（step_start, step_progress, step_complete, final）
        """
        logger.info(f"[SequentialAgent] Starting stream execution: {self.name}")
        
        session_state: Dict[str, Any] = {
            "input": initial_input,
            "context": context or {},
            "steps": []
        }
        
        for idx, step in enumerate(self.steps):
            yield {
                "event_type": "step_start",
                "step": idx + 1,
                "total_steps": len(self.steps),
                "agent_id": step.agent_id,
                "agent_name": step.agent_name
            }
            
            try:
                step_input = self._prepare_step_input(step, session_state)
                
                step_result = await self._execute_agent(
                    user_id=user_id,
                    agent_id=step.agent_id,
                    agent_name=step.agent_name,
                    input_data=step_input
                )
                
                if step.output_key:
                    session_state[step.output_key] = step_result
                else:
                    session_state[f"step_{idx}_output"] = step_result
                
                session_state["steps"].append({
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "output": step_result
                })
                
                yield {
                    "event_type": "step_complete",
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "result": step_result
                }
                
            except Exception as e:
                logger.error(f"[SequentialAgent] Step {idx + 1} failed: {e}", exc_info=True)
                yield {
                    "event_type": "step_error",
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "error": str(e)
                }
                break
        
        yield {
            "event_type": "final",
            "success": "error" not in str(session_state.get("error", "")),
            "session_state": session_state
        }
