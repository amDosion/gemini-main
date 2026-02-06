"""
Parallel Agent - 并行代理（Parallel Fan-Out/Gather Pattern）

参考 Google ADK 的 Parallel Fan-Out/Gather 模式：
- 并发执行多个子代理
- 聚合所有代理的结果
- 支持超时和错误处理
- 结果可以传递给后续代理
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass

from .base_agent_executor import BaseAgentExecutor

logger = logging.getLogger(__name__)


@dataclass
class ParallelTask:
    """并行任务"""
    agent_id: str
    agent_name: str
    input_data: Any
    output_key: Optional[str] = None
    timeout: Optional[float] = None


class ParallelAgent:
    """
    并行代理（Parallel Fan-Out/Gather Pattern）

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
        self.name = name
        self.sub_agents = sub_agents
        self.agent_registry = agent_registry
        self.google_service = google_service
        self.tool_registry = tool_registry
        self.default_timeout = default_timeout

        # Shared executor
        self._executor = BaseAgentExecutor(
            agent_registry=agent_registry,
            google_service=google_service,
            tool_registry=tool_registry,
        )

        # Build task list
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
        1. 准备每个任务的输入
        2. 并发执行所有任务
        3. 等待所有任务完成（或超时）
        4. 聚合结果
        """
        logger.info(f"[ParallelAgent] Starting parallel execution: {self.name}")

        try:
            results = await asyncio.gather(
                *[
                    self._execute_task_with_timeout(
                        user_id=user_id,
                        task=task,
                        input_data=task.input_data if task.input_data is not None else shared_input,
                    )
                    for task in self.tasks
                ],
                return_exceptions=True
            )

            aggregated_results = {}
            errors = {}

            for idx, (task, result) in enumerate(zip(self.tasks, results)):
                output_key = task.output_key or f"task_{idx}"
                if isinstance(result, Exception):
                    logger.error(f"[ParallelAgent] Task {idx + 1} failed: {result}")
                    errors[output_key] = str(result)
                    aggregated_results[output_key] = None
                else:
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
    ) -> Any:
        """执行单个任务（带超时）"""
        timeout = task.timeout or self.default_timeout

        try:
            result = await asyncio.wait_for(
                self._executor.execute_agent(
                    user_id=user_id,
                    agent_id=task.agent_id,
                    agent_name=task.agent_name,
                    input_data=input_data,
                ),
                timeout=timeout
            )
            return result.get("output", result)
        except asyncio.TimeoutError:
            logger.warning(f"[ParallelAgent] Task {task.agent_name} timed out after {timeout}s")
            raise TimeoutError(f"Task {task.agent_name} timed out after {timeout}s")

    async def stream_execute(
        self,
        user_id: str,
        shared_input: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行并行任务"""
        logger.info(f"[ParallelAgent] Starting stream parallel execution: {self.name}")

        for idx, task in enumerate(self.tasks):
            yield {
                "event_type": "task_start",
                "task_index": idx,
                "total_tasks": len(self.tasks),
                "agent_id": task.agent_id,
                "agent_name": task.agent_name
            }

        try:
            results = await asyncio.gather(
                *[
                    self._execute_task_with_timeout(
                        user_id=user_id,
                        task=task,
                        input_data=task.input_data if task.input_data is not None else shared_input,
                    )
                    for task in self.tasks
                ],
                return_exceptions=True
            )

            aggregated_results = {}
            errors = {}

            for idx, (task, result) in enumerate(zip(self.tasks, results)):
                output_key = task.output_key or f"task_{idx}"
                if isinstance(result, Exception):
                    errors[output_key] = str(result)
                    aggregated_results[output_key] = None
                    yield {
                        "event_type": "task_error",
                        "task_index": idx,
                        "agent_id": task.agent_id,
                        "agent_name": task.agent_name,
                        "error": str(result)
                    }
                else:
                    aggregated_results[output_key] = result
                    yield {
                        "event_type": "task_complete",
                        "task_index": idx,
                        "agent_id": task.agent_id,
                        "agent_name": task.agent_name,
                        "result": result,
                        "output_key": task.output_key
                    }

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
