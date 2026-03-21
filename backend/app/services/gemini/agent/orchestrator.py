"""
Orchestrator - Google runtime 智能体编排器

提供：
- 任务分解和分配
- 智能体选择策略
- 结果聚合
- 错误处理和重试
"""

import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from .agent_registry import AgentRegistryService
from .task_decomposer import SmartTaskDecomposer, SubTask
from .agent_matcher import AgentMatcher
from .execution_graph import ExecutionGraph
from .base_agent_executor import BaseAgentExecutor
from .adk_runner import compute_adk_accuracy_signals

logger = logging.getLogger(__name__)


def classify_orchestration_http_exception(exc: HTTPException) -> Dict[str, Any]:
    """
    对官方编排路径的 HTTPException 做机读分类，避免将输入/配置错误误报为 runtime unavailable。
    """
    status_code = int(exc.status_code)
    cause = str(exc.detail or "").strip() or "orchestration request failed"
    if 400 <= status_code < 500:
        return {
            "status_code": status_code,
            "error_code": "ADK_INVALID_REQUEST",
            "message": "Orchestration request/configuration is invalid.",
            "cause": cause,
        }
    return {
        "status_code": status_code if status_code >= 500 else 503,
        "error_code": "ADK_RUNTIME_UNAVAILABLE",
        "message": "Official ADK runtime is unavailable for orchestration.",
        "cause": cause,
    }


class Orchestrator:
    """
    Google runtime 专属的智能体编排器

    负责：
    - 任务分解和分配
    - 智能体选择策略
    - 结果聚合
    - 错误处理和重试

    说明：
    - 该实现依赖 GoogleService / Gemini 路径进行智能分解与工具执行。
    - 不应被视为 provider-neutral workflow runtime；统一入口应使用 `/api/modes/{provider}/multi-agent`。
    """

    def __init__(
        self,
        db: Session,
        google_service: Optional[Any] = None,
        use_smart_decomposition: bool = True,
        strict_runtime: bool = False,
    ):
        self.db = db
        self.google_service = google_service
        self.agent_registry = AgentRegistryService(db=db)
        self.use_smart_decomposition = use_smart_decomposition
        self.strict_runtime = bool(strict_runtime)

        # 初始化智能任务分解器和代理匹配器
        if use_smart_decomposition and google_service:
            self.task_decomposer = SmartTaskDecomposer(google_service=google_service)
            self.agent_matcher = AgentMatcher()
            logger.info("[Orchestrator] Initialized with smart task decomposition")
        else:
            self.task_decomposer = None
            self.agent_matcher = None
            logger.info("[Orchestrator] Initialized with simple task decomposition")

        # 初始化工具注册表
        try:
            from .tool_registry import ToolRegistry
            from ...mcp_manager import get_mcp_manager
            mcp_manager = get_mcp_manager()
            self.tool_registry = ToolRegistry(mcp_manager=mcp_manager)
            logger.info("[Orchestrator] Initialized with tool registry")
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to initialize tool registry: {e}")
            self.tool_registry = None

        # 创建共享的 agent executor
        self._executor = BaseAgentExecutor(
            agent_registry=self.agent_registry,
            google_service=self.google_service,
            tool_registry=self.tool_registry,
        )

    async def orchestrate(
        self,
        user_id: str,
        task: str,
        agent_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        编排多智能体任务

        Args:
            user_id: 用户 ID
            task: 任务描述
            agent_ids: 智能体 ID 列表（可选，如果未提供则自动选择）

        Returns:
            聚合结果
        """
        # 获取可用代理
        available_agents = await self.agent_registry.list_agents(user_id=user_id)

        if not available_agents:
            logger.warning("[Orchestrator] No available agents found")
            return {
                "error": "No available agents",
                "results": []
            }

        # 如果没有指定智能体，使用所有可用代理
        if not agent_ids:
            agent_ids = [agent["id"] for agent in available_agents]

        # 过滤出指定的代理
        selected_agents = [
            agent for agent in available_agents
            if agent["id"] in agent_ids
        ]

        if not selected_agents:
            logger.warning(f"[Orchestrator] No agents found for IDs: {agent_ids}")
            return {
                "error": f"No agents found for IDs: {agent_ids}",
                "results": []
            }

        # 分解任务
        if self.use_smart_decomposition and self.task_decomposer:
            try:
                subtasks = await self.task_decomposer.decompose_task(
                    task=task,
                    available_agents=selected_agents
                )
                logger.info(f"[Orchestrator] Decomposed task into {len(subtasks)} subtasks using smart decomposition")
            except Exception as e:
                if self.strict_runtime:
                    raise RuntimeError(
                        f"ORCHESTRATOR_NO_DEGRADE: smart decomposition failed in strict mode: {e}"
                    ) from e
                logger.error(f"[Orchestrator] Smart decomposition failed: {e}, falling back to simple decomposition")
                subtasks = self._decompose_task_simple(task, len(selected_agents))
        else:
            subtasks = self._decompose_task_simple(task, len(selected_agents))

        # 构建执行图（如果使用智能分解且有依赖关系）
        use_execution_graph = (
            self.use_smart_decomposition and
            isinstance(subtasks[0], SubTask) if subtasks else False
        )

        if use_execution_graph:
            try:
                execution_graph = ExecutionGraph(subtasks)
                is_valid, error = execution_graph.validate()

                if not is_valid:
                    if self.strict_runtime:
                        raise RuntimeError(
                            "ORCHESTRATOR_NO_DEGRADE: execution graph validation failed in strict mode: "
                            f"{error}"
                        )
                    logger.warning(f"[Orchestrator] Execution graph validation failed: {error}, using sequential execution")
                    use_execution_graph = False
                else:
                    logger.info(f"[Orchestrator] Using execution graph with {len(execution_graph.get_execution_levels())} levels")
            except Exception as e:
                if self.strict_runtime:
                    raise RuntimeError(
                        f"ORCHESTRATOR_NO_DEGRADE: execution graph creation failed in strict mode: {e}"
                    ) from e
                logger.warning(f"[Orchestrator] Failed to create execution graph: {e}, using sequential execution")
                use_execution_graph = False

        # 执行任务
        if use_execution_graph:
            results = await self._execute_with_graph(
                execution_graph=execution_graph,
                user_id=user_id,
                selected_agents=selected_agents
            )
        else:
            results = await self._execute_sequential(
                subtasks=subtasks,
                user_id=user_id,
                selected_agents=selected_agents
            )

        # 聚合结果
        aggregated = self._aggregate_results(results)

        return aggregated

    def _decompose_task_simple(self, task: str, num_agents: int) -> List[str]:
        """简单任务分解（向后兼容）"""
        return [f"{task} (part {i+1}/{num_agents})" for i in range(num_agents)]

    async def _execute_with_graph(
        self,
        execution_graph: ExecutionGraph,
        user_id: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """使用执行图执行任务（按层级并行执行）"""
        import asyncio

        levels = execution_graph.get_execution_levels()
        results: Dict[str, Dict[str, Any]] = {}

        logger.info(f"[Orchestrator] Executing {len(levels)} levels with execution graph")

        for level_idx, level in enumerate(levels):
            logger.info(f"[Orchestrator] Executing level {level_idx + 1}/{len(levels)} with {len(level)} tasks")

            level_tasks = []
            for subtask in level:
                # 匹配代理
                if self.agent_matcher:
                    matched_agent = self.agent_matcher.match_agent(
                        subtask=subtask,
                        available_agents=selected_agents,
                        consider_load=True
                    )

                    if not matched_agent:
                        logger.warning(f"[Orchestrator] No agent matched for subtask: {subtask.description}")
                        results[subtask.id] = {
                            "subtask_id": subtask.id,
                            "subtask": subtask.description,
                            "error": "No suitable agent found"
                        }
                        continue

                    agent_id = matched_agent["id"]
                else:
                    agent_index = len(results) % len(selected_agents)
                    agent_id = selected_agents[agent_index]["id"]

                task_coro = self._execute_subtask_with_context(
                    user_id=user_id,
                    agent_id=agent_id,
                    subtask=subtask,
                    previous_results=results
                )
                level_tasks.append((subtask.id, task_coro))

            if level_tasks:
                task_results = await asyncio.gather(
                    *[coro for _, coro in level_tasks],
                    return_exceptions=True
                )

                for (task_id, _), result in zip(level_tasks, task_results):
                    if isinstance(result, Exception):
                        logger.error(f"[Orchestrator] Error executing subtask {task_id}: {result}")
                        results[task_id] = {
                            "subtask_id": task_id,
                            "error": str(result)
                        }
                    else:
                        results[task_id] = result

            logger.info(f"[Orchestrator] Level {level_idx + 1} completed")

        return [results.get(task.id, {"error": "Not executed"}) for task in execution_graph.get_execution_order()]

    async def _execute_sequential(
        self,
        subtasks: List[Any],
        user_id: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """顺序执行任务（向后兼容）"""
        results = []
        for subtask in subtasks:
            try:
                if self.use_smart_decomposition and self.agent_matcher and isinstance(subtask, SubTask):
                    matched_agent = self.agent_matcher.match_agent(
                        subtask=subtask,
                        available_agents=selected_agents,
                        consider_load=True
                    )

                    if not matched_agent:
                        logger.warning(f"[Orchestrator] No agent matched for subtask: {subtask.description}")
                        results.append({
                            "subtask_id": subtask.id,
                            "subtask": subtask.description,
                            "error": "No suitable agent found"
                        })
                        continue

                    agent_id = matched_agent["id"]
                    subtask_str = subtask.description
                else:
                    agent_index = len(results) % len(selected_agents)
                    agent_id = selected_agents[agent_index]["id"]
                    subtask_str = subtask if isinstance(subtask, str) else subtask.description

                # Use shared executor instead of duplicated logic
                result = await self._executor.execute_agent(
                    user_id=user_id,
                    agent_id=agent_id,
                    agent_name=agent_id,
                    input_data=subtask_str,
                )

                if isinstance(subtask, SubTask):
                    result["subtask_id"] = subtask.id
                    result["subtask_description"] = subtask.description
                    result["dependencies"] = subtask.dependencies

                results.append(result)

            except Exception as e:
                logger.error(f"[Orchestrator] Error executing subtask: {e}", exc_info=True)
                error_result = {
                    "error": str(e),
                    "subtask": subtask.description if isinstance(subtask, SubTask) else str(subtask)
                }
                if isinstance(subtask, SubTask):
                    error_result["subtask_id"] = subtask.id
                results.append(error_result)

        return results

    async def _execute_subtask_with_context(
        self,
        user_id: str,
        agent_id: str,
        subtask: SubTask,
        previous_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行子任务（带上下文，用于执行图）

        FIX: The original code had a critical indentation bug where the
        execute call was nested inside the dependency loop, causing it
        to only run if there were dependencies and to run multiple times.
        """
        # Build context from dependency results
        context = {}
        for dep_id in subtask.dependencies:
            if dep_id in previous_results:
                context[dep_id] = previous_results[dep_id]

        # Build task description with context
        task_with_context = subtask.description
        if context:
            context_summary = "; ".join(
                f"[{dep_id}]: {dep_result.get('output', dep_result.get('result', 'N/A'))}"
                for dep_id, dep_result in context.items()
            )
            task_with_context = f"{subtask.description}\n\nContext from dependencies:\n{context_summary}"

        # Execute (OUTSIDE the loop - this was the bug)
        result = await self._executor.execute_agent(
            user_id=user_id,
            agent_id=agent_id,
            agent_name=agent_id,
            input_data=task_with_context,
        )

        # Add subtask metadata
        result["subtask_id"] = subtask.id
        result["subtask_description"] = subtask.description
        result["dependencies"] = subtask.dependencies
        result["context"] = context

        return result

    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """聚合结果"""
        serialized_results = json.dumps(
            results,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        action_items: List[Any] = []
        long_running_tool_ids: List[str] = []
        for item in results:
            if isinstance(item.get("actions"), dict) and item.get("actions"):
                action_items.append(item.get("actions"))
            raw_long_running = item.get("long_running_tool_ids")
            if isinstance(raw_long_running, list) and raw_long_running:
                long_running_tool_ids.extend(str(tool_id).strip() for tool_id in raw_long_running if str(tool_id).strip())

        signals = compute_adk_accuracy_signals(
            content=serialized_results,
            actions={"actions": action_items},
            long_running_tool_ids=sorted(set(long_running_tool_ids)),
        )
        return {
            "results": results,
            "summary": f"Aggregated {len(results)} results",
            "response_signature": signals["response_signature"],
            "action_signature": signals["action_signature"],
        }
