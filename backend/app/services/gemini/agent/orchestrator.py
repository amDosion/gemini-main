"""
Orchestrator - 智能体编排器

提供：
- 任务分解和分配
- 智能体选择策略
- 结果聚合
- 错误处理和重试
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from .agent_registry import AgentRegistryService
from .task_decomposer import SmartTaskDecomposer, SubTask
from .agent_matcher import AgentMatcher
from .execution_graph import ExecutionGraph

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    智能体编排器
    
    负责：
    - 任务分解和分配
    - 智能体选择策略
    - 结果聚合
    - 错误处理和重试
    """
    
    def __init__(
        self,
        db: Session,
        google_service: Optional[Any] = None,
        use_smart_decomposition: bool = True
    ):
        """
        初始化编排器
        
        Args:
            db: 数据库会话
            google_service: GoogleService 实例（用于智能任务分解，可选）
            use_smart_decomposition: 是否使用智能任务分解（默认：True）
        """
        self.db = db
        self.agent_registry = AgentRegistryService(db=db)
        self.use_smart_decomposition = use_smart_decomposition
        
        # 初始化智能任务分解器和代理匹配器
        if use_smart_decomposition and google_service:
            self.task_decomposer = SmartTaskDecomposer(google_service=google_service)
            self.agent_matcher = AgentMatcher()
            logger.info("[Orchestrator] Initialized with smart task decomposition")
        else:
            self.task_decomposer = None
            self.agent_matcher = None
            logger.info("[Orchestrator] Initialized with simple task decomposition")
        
        # 初始化工具注册表（用于代理工具执行）
        try:
            from .tool_registry import ToolRegistry
            from ...mcp_manager import get_mcp_manager
            mcp_manager = get_mcp_manager()
            self.tool_registry = ToolRegistry(mcp_manager=mcp_manager)
            logger.info("[Orchestrator] Initialized with tool registry")
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to initialize tool registry: {e}")
            self.tool_registry = None
    
    async def multi_agent(
        self,
        prompt: str,
        model: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一的多智能体编排接口 - 处理模式路由
        
        Args:
            prompt: Task description
            model: Model identifier (not used, but required by interface)
            user_id: 用户 ID
            **kwargs: Additional parameters:
                - agent_ids: List of agent IDs to use
                - mode: Orchestration mode ('coordinator', 'sequential', 'parallel', 'default')
                - workflow_config: Workflow configuration (for sequential/parallel modes)
        
        Returns:
            Orchestration result
        """
        agent_ids = kwargs.get("agent_ids")
        mode = kwargs.get("mode", "default")
        workflow_config = kwargs.get("workflow_config")
        
        # 根据模式选择执行方式
        if mode == "coordinator":
            from .coordinator_agent import CoordinatorAgent
            
            coordinator = CoordinatorAgent(
                google_service=self.google_service,
                agent_registry=self.agent_registry,
                model=model or "gemini-2.0-flash-exp"
            )
            
            result = await coordinator.coordinate(
                user_id=user_id,
                task=prompt,
                context=workflow_config
            )
            return result
        
        elif mode == "sequential":
            if not workflow_config or "sub_agents" not in workflow_config:
                raise ValueError("Sequential mode requires workflow_config with sub_agents")
            
            from .sequential_agent import SequentialAgent
            from .tool_registry import ToolRegistry
            from ...mcp_manager import get_mcp_manager
            
            mcp_manager = get_mcp_manager()
            tool_registry = ToolRegistry(mcp_manager=mcp_manager)
            
            sequential_agent = SequentialAgent(
                name=workflow_config.get("name", "SequentialWorkflow"),
                sub_agents=workflow_config["sub_agents"],
                agent_registry=self.agent_registry,
                google_service=self.google_service,
                tool_registry=tool_registry
            )
            
            result = await sequential_agent.execute(
                user_id=user_id,
                initial_input=prompt,
                context=workflow_config.get("context")
            )
            return result
        
        elif mode == "parallel":
            if not workflow_config or "sub_agents" not in workflow_config:
                raise ValueError("Parallel mode requires workflow_config with sub_agents")
            
            from .parallel_agent import ParallelAgent
            from .tool_registry import ToolRegistry
            from ...mcp_manager import get_mcp_manager
            
            mcp_manager = get_mcp_manager()
            tool_registry = ToolRegistry(mcp_manager=mcp_manager)
            
            parallel_agent = ParallelAgent(
                name=workflow_config.get("name", "ParallelWorkflow"),
                sub_agents=workflow_config["sub_agents"],
                agent_registry=self.agent_registry,
                google_service=self.google_service,
                tool_registry=tool_registry,
                default_timeout=workflow_config.get("timeout", 60.0)
            )
            
            result = await parallel_agent.execute(
                user_id=user_id,
                shared_input=prompt,
                context=workflow_config.get("context")
            )
            return result
        
        else:
            # Default mode: 使用 Orchestrator（智能任务分解 + 执行图）
            result = await self.orchestrate(
                user_id=user_id,
                task=prompt,
                agent_ids=agent_ids
            )
            return result
    
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
            # 使用智能任务分解
            try:
                subtasks = await self.task_decomposer.decompose_task(
                    task=task,
                    available_agents=selected_agents
                )
                logger.info(f"[Orchestrator] Decomposed task into {len(subtasks)} subtasks using smart decomposition")
            except Exception as e:
                logger.error(f"[Orchestrator] Smart decomposition failed: {e}, falling back to simple decomposition")
                subtasks = self._decompose_task_simple(task, len(selected_agents))
        else:
            # 使用简单任务分解
            subtasks = self._decompose_task_simple(task, len(selected_agents))
        
        # 构建执行图（如果使用智能分解且有依赖关系）
        use_execution_graph = (
            self.use_smart_decomposition and
            isinstance(subtasks[0], SubTask) if subtasks else False
        )
        
        if use_execution_graph:
            # 使用执行图管理依赖关系
            try:
                execution_graph = ExecutionGraph(subtasks)
                is_valid, error = execution_graph.validate()
                
                if not is_valid:
                    logger.warning(f"[Orchestrator] Execution graph validation failed: {error}, using sequential execution")
                    use_execution_graph = False
                else:
                    logger.info(f"[Orchestrator] Using execution graph with {len(execution_graph.get_execution_levels())} levels")
            except Exception as e:
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
            # 顺序执行（向后兼容）
            results = await self._execute_sequential(
                subtasks=subtasks,
                user_id=user_id,
                selected_agents=selected_agents
            )
        
        # 聚合结果
        aggregated = self._aggregate_results(results)
        
        return aggregated
    
    def _decompose_task_simple(self, task: str, num_agents: int) -> List[str]:
        """
        简单任务分解（向后兼容）
        
        Args:
            task: 任务描述
            num_agents: 智能体数量
            
        Returns:
            子任务列表（字符串）
        """
        # 简化实现：将任务平均分配
        return [f"{task} (part {i+1}/{num_agents})" for i in range(num_agents)]
    
    async def _execute_with_graph(
        self,
        execution_graph: ExecutionGraph,
        user_id: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        使用执行图执行任务（按层级并行执行）
        
        Args:
            execution_graph: 执行图
            user_id: 用户 ID
            selected_agents: 选中的代理列表
            
        Returns:
            执行结果列表
        """
        import asyncio
        
        levels = execution_graph.get_execution_levels()
        results: Dict[str, Dict[str, Any]] = {}  # task_id -> result
        
        logger.info(f"[Orchestrator] Executing {len(levels)} levels with execution graph")
        
        for level_idx, level in enumerate(levels):
            logger.info(f"[Orchestrator] Executing level {level_idx + 1}/{len(levels)} with {len(level)} tasks")
            
            # 并行执行当前层级的所有任务
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
                    # 轮询分配
                    agent_index = len(results) % len(selected_agents)
                    agent_id = selected_agents[agent_index]["id"]
                
                # 创建执行任务
                task_coro = self._execute_subtask_with_context(
                    user_id=user_id,
                    agent_id=agent_id,
                    subtask=subtask,
                    previous_results=results  # 传递之前的结果，用于依赖注入
                )
                level_tasks.append((subtask.id, task_coro))
            
            # 并行执行当前层级的所有任务
            if level_tasks:
                task_results = await asyncio.gather(
                    *[coro for _, coro in level_tasks],
                    return_exceptions=True
                )
                
                # 收集结果
                for (task_id, _), result in zip(level_tasks, task_results):
                    if isinstance(result, Exception):
                        logger.error(f"[Orchestrator] Error executing subtask {task_id}: {result}")
                        results[task_id] = {
                            "subtask_id": task_id,
                            "error": str(result)
                        }
                    else:
                        results[task_id] = result
            
            # 等待当前层级完成后再执行下一层级
            logger.info(f"[Orchestrator] Level {level_idx + 1} completed")
        
        # 按原始顺序返回结果
        return [results.get(task.id, {"error": "Not executed"}) for task in execution_graph.get_execution_order()]
    
    async def _execute_sequential(
        self,
        subtasks: List[Any],
        user_id: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        顺序执行任务（向后兼容）
        
        Args:
            subtasks: 子任务列表
            user_id: 用户 ID
            selected_agents: 选中的代理列表
            
        Returns:
            执行结果列表
        """
        results = []
        for subtask in subtasks:
            try:
                # 如果是智能分解，使用代理匹配器
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
                    # 简单分配：轮询分配
                    agent_index = len(results) % len(selected_agents)
                    agent_id = selected_agents[agent_index]["id"]
                    subtask_str = subtask if isinstance(subtask, str) else subtask.description
                
                # 执行子任务（传递工具注册表）
                result = await self._execute_subtask(
                    user_id=user_id,
                    agent_id=agent_id,
                    subtask=subtask_str,
                    tool_registry=self.tool_registry
                )
                
                # 添加子任务信息
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
        
        Args:
            user_id: 用户 ID
            agent_id: 代理 ID
            subtask: 子任务
            previous_results: 之前执行的结果（用于依赖注入）
            
        Returns:
            执行结果
        """
        # 构建包含依赖结果的上下文
        context = {}
        for dep_id in subtask.dependencies:
            if dep_id in previous_results:
                context[dep_id] = previous_results[dep_id]
        
                # 执行子任务（传递工具注册表）
                result = await self._execute_subtask(
                    user_id=user_id,
                    agent_id=agent_id,
                    subtask=subtask.description,
                    tool_registry=self.tool_registry
                )
        
        # 添加子任务信息和上下文
        result["subtask_id"] = subtask.id
        result["subtask_description"] = subtask.description
        result["dependencies"] = subtask.dependencies
        result["context"] = context  # 包含依赖结果
        
        return result
    
    async def _execute_subtask(
        self,
        user_id: str,
        agent_id: str,
        subtask: str,
        tools: Optional[List[str]] = None,
        tool_registry: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        执行子任务
        
        Args:
            user_id: 用户 ID
            agent_id: 智能体 ID
            subtask: 子任务
            tools: 工具名称列表（可选）
            tool_registry: 工具注册表（可选）
            
        Returns:
            执行结果
        """
        # 获取代理信息
        agent_info = await self.agent_registry.get_agent(user_id, agent_id)
        
        if not agent_info:
            return {
                "agent_id": agent_id,
                "subtask": subtask,
                "error": f"Agent {agent_id} not found"
            }
        
        # 如果代理配置了工具，使用 AgentWithTools
        agent_tools = tools
        mcp_session_id = None
        
        if agent_info.get("tools"):
            tool_config = agent_info["tools"]
            agent_tools = tool_config.get("tool_names")
            mcp_session_id = tool_config.get("mcp_session_id")
        
        # 如果有工具配置，使用 AgentWithTools 执行
        if agent_tools and tool_registry:
            try:
                # 创建 GoogleService（需要从数据库获取 API key）
                from ..google_service import GoogleService
                from ...provider_factory import ProviderFactory
                from ....models.db_models import UserSettings, ConfigProfile
                from ....core.encryption import decrypt_api_key
                
                # 获取 Google API key
                settings = self.db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
                active_profile_id = settings.active_profile_id if settings else None
                
                matching_profiles = self.db.query(ConfigProfile).filter(
                    ConfigProfile.provider_id == 'google',
                    ConfigProfile.user_id == user_id
                ).all()
                
                api_key = None
                if matching_profiles:
                    if active_profile_id:
                        for profile in matching_profiles:
                            if profile.id == active_profile_id and profile.api_key:
                                api_key = decrypt_api_key(profile.api_key)
                                break
                    
                    if not api_key:
                        for profile in matching_profiles:
                            if profile.api_key:
                                api_key = decrypt_api_key(profile.api_key)
                                break
                
                if api_key:
                    # 加载 MCP 工具（如果有）
                    if mcp_session_id:
                        await tool_registry.load_mcp_tools(mcp_session_id)
                    
                    # 创建 GoogleService
                    google_service = ProviderFactory.create(
                        provider='google',
                        api_key=api_key,
                        user_id=user_id,
                        db=self.db
                    )
                    
                    # 创建 AgentWithTools
                    from .agent_with_tools import AgentWithTools
                    agent_with_tools = AgentWithTools(
                        name=agent_info.get("name", agent_id),
                        google_service=google_service,
                        tool_registry=tool_registry,
                        model="gemini-2.0-flash-exp"
                    )
                    
                    # 执行任务（带工具）
                    result = await agent_with_tools.execute_with_tools(
                        task=subtask,
                        available_tools=agent_tools
                    )
                    
                    return {
                        "agent_id": agent_id,
                        "subtask": subtask,
                        "result": result.get("result"),
                        "tool_calls": result.get("tool_calls", []),
                        "iterations": result.get("iterations", 1)
                    }
            except Exception as e:
                logger.error(f"[Orchestrator] Error executing with tools: {e}", exc_info=True)
                # 回退到简单执行
        
        # 简化实现：直接返回结果
        # 实际应该调用智能体执行逻辑
        return {
            "agent_id": agent_id,
            "subtask": subtask,
            "result": f"Result for: {subtask}"
        }
    
    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        聚合结果
        
        Args:
            results: 结果列表
            
        Returns:
            聚合结果
        """
        return {
            "results": results,
            "summary": f"Aggregated {len(results)} results"
        }
