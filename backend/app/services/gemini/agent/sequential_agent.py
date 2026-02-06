"""
Sequential Agent - 顺序代理（Sequential Pipeline Pattern）

参考 Google ADK 的 Sequential Pipeline 模式：
- 按顺序执行子代理链
- 会话状态在代理间传递
- 支持输出键（output_key）机制
- 每个代理的输出作为下一个代理的输入
"""

import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass

from .base_agent_executor import BaseAgentExecutor

logger = logging.getLogger(__name__)


@dataclass
class SequentialStep:
    """顺序执行步骤"""
    agent_id: str
    agent_name: str
    output_key: Optional[str] = None
    input_key: Optional[str] = None


class SequentialAgent:
    """
    顺序代理（Sequential Pipeline Pattern）

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
        self.name = name
        self.sub_agents = sub_agents
        self.agent_registry = agent_registry
        self.google_service = google_service
        self.tool_registry = tool_registry

        # Shared executor - eliminates duplicated _execute_agent logic
        self._executor = BaseAgentExecutor(
            agent_registry=agent_registry,
            google_service=google_service,
            tool_registry=tool_registry,
        )

        # Build step list
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
        """
        logger.info(f"[SequentialAgent] Starting execution: {self.name}")

        session_state: Dict[str, Any] = {
            "input": initial_input,
            "context": context or {},
            "steps": []
        }

        for idx, step in enumerate(self.steps):
            logger.info(f"[SequentialAgent] Executing step {idx + 1}/{len(self.steps)}: {step.agent_name}")

            try:
                step_input = self._prepare_step_input(step, session_state)

                # Use shared executor
                step_result = await self._executor.execute_agent(
                    user_id=user_id,
                    agent_id=step.agent_id,
                    agent_name=step.agent_name,
                    input_data=step_input,
                )

                # Extract output from result
                output = step_result.get("output", step_result)

                if step.output_key:
                    session_state[step.output_key] = output
                else:
                    session_state[f"step_{idx}_output"] = output

                session_state["steps"].append({
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "input": step_input,
                    "output": output,
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
                session_state["error"] = f"Step {idx + 1} failed: {str(e)}"
                break

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
        """准备步骤输入"""
        if step.input_key:
            return session_state.get(step.input_key, session_state.get("input"))
        else:
            if session_state["steps"]:
                last_step = session_state["steps"][-1]
                return last_step.get("output", session_state.get("input"))
            else:
                return session_state.get("input")

    async def stream_execute(
        self,
        user_id: str,
        initial_input: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行顺序管道"""
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

                step_result = await self._executor.execute_agent(
                    user_id=user_id,
                    agent_id=step.agent_id,
                    agent_name=step.agent_name,
                    input_data=step_input,
                )

                output = step_result.get("output", step_result)

                if step.output_key:
                    session_state[step.output_key] = output
                else:
                    session_state[f"step_{idx}_output"] = output

                session_state["steps"].append({
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "output": output
                })

                yield {
                    "event_type": "step_complete",
                    "step": idx + 1,
                    "agent_id": step.agent_id,
                    "agent_name": step.agent_name,
                    "result": output
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
