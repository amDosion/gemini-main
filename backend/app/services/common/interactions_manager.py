"""
Interactions Manager - 高层智能体交互管理服务

职责：
- 客户端池管理（复用客户端实例）
- 交互创建和管理
- 状态轮询
- 流式响应处理
- MCP 工具集成

类似于 mcp_manager.py 和 storage_manager.py 的架构设计
"""

from typing import Dict, Any, Optional, List, Union, AsyncGenerator
import logging
import asyncio
import os
import time
from sqlalchemy.orm import Session

from ..gemini.agent import Client, AsyncClient
from ..gemini.agent.types import HttpOptions, HttpOptionsDict
from ..mcp.mcp_manager import MCPManager, get_mcp_manager
from ..gemini.client_pool import get_client_pool
from .interactions_event_utils import (
    build_interaction_stream_event,
    serialize_usage,
)

logger = logging.getLogger(__name__)


def _is_retryable_stream_exception(error: Exception) -> bool:
    """Determine whether an interactions stream error is safe to resume."""
    message = str(error).lower()
    timeout_markers = (
        "timed out",
        "readtimeout",
        "read timeout",
        "timeout error",
        "the read operation timed out",
    )
    transient_markers = (
        "connection reset",
        "connection aborted",
        "connection closed",
        "broken pipe",
        "temporarily unavailable",
    )
    return any(marker in message for marker in timeout_markers + transient_markers)


def _get_interactions_stream_timeout_ms() -> int:
    """Read dedicated timeout for interactions streaming requests."""
    raw = os.getenv("GEMINI_INTERACTIONS_STREAM_TIMEOUT_MS")
    if raw is None:
        # Deep Research streams are long-running; keep timeout higher than generic requests.
        return 300000
    try:
        value = int(raw)
        return value if value > 0 else 300000
    except (TypeError, ValueError):
        return 300000


def _get_interactions_stream_max_resume() -> int:
    raw = os.getenv("GEMINI_INTERACTIONS_STREAM_MAX_RESUME")
    if raw is None:
        return 8
    try:
        value = int(raw)
        return value if value >= 0 else 8
    except (TypeError, ValueError):
        return 8


def _get_interactions_stream_resume_backoff_sec() -> float:
    raw = os.getenv("GEMINI_INTERACTIONS_STREAM_RESUME_BACKOFF_SEC")
    if raw is None:
        return 1.0
    try:
        value = float(raw)
        return value if value > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


class InteractionsManager:
    """
    智能体交互高层管理服务

    提供：
    - 客户端管理
    - 交互创建
    - 状态查询
    - 流式处理
    - MCP 工具集成
    """

    def __init__(
        self,
        mcp_manager: Optional[MCPManager] = None,
        db: Optional[Session] = None,
        default_vertexai: bool = True  # 默认使用 Vertex AI
    ):
        """
        初始化 Interactions 管理器

        注意：不再持有客户端实例，从统一池获取

        Args:
            mcp_manager: MCP 管理器实例（可选，用于工具集成）
            db: 数据库会话（可选，用于获取 Vertex AI 配置）
            default_vertexai: 默认是否使用 Vertex AI（企业级功能）
        """
        self._mcp_manager = mcp_manager
        self._db = db
        self._default_vertexai = default_vertexai
        self._vertexai_interactions_service = None  # 延迟初始化
        logger.info(f"InteractionsManager initialized (using unified client pool, default_vertexai={default_vertexai})")

    def get_client(
        self,
        api_key: Optional[str] = None,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None,
        credentials = None,  # Service account credentials (for Vertex AI)
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> Client:
        """
        获取同步客户端（从统一池）

        Args:
            api_key: Google API 密钥（可选，如果有 credentials）
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            credentials: Service account credentials (for Vertex AI ADC mode)
            http_options: HTTP 选项

        Returns:
            Client 实例
        """
        pool = get_client_pool()
        return pool.get_client(
            api_key=api_key,
            vertexai=vertexai,
            project=project,
            location=location,
            credentials=credentials,
            http_options=http_options
        )

    def get_async_client(
        self,
        api_key: Optional[str] = None,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None,
        credentials = None,  # Service account credentials (for Vertex AI)
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> AsyncClient:
        """
        获取异步客户端（从统一池）

        Args:
            api_key: Google API 密钥（Gemini API 模式必需，Vertex AI 模式可选）
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            credentials: Service account credentials (for Vertex AI)
            http_options: HTTP 选项

        Returns:
            AsyncClient 实例
        """
        # 从统一池获取同步客户端，然后获取其异步版本
        pool = get_client_pool()
        sync_client = pool.get_client(
            api_key=api_key,
            vertexai=vertexai,
            project=project,
            location=location,
            credentials=credentials,
            http_options=http_options
        )
        return sync_client.aio

    async def create_interaction(
        self,
        input: Union[str, List[Dict[str, Any]]],
        api_key: Optional[str] = None,
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_session_id: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        store: Optional[bool] = None,
        vertexai: Optional[bool] = None,  # None 表示使用默认值
        project: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None,  # 用户 ID（用于从数据库获取配置）
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> Dict[str, Any]:
        """
        创建智能体交互

        Args:
            api_key: Google API 密钥
            input: 输入内容（字符串或内容列表）
            agent: 智能体名称
            background: 是否在后台运行
            agent_config: 智能体配置
            system_instruction: 系统指令
            tools: 工具列表
            mcp_session_id: MCP 会话 ID（如果提供，将从 MCP 获取工具）
            vertexai: 是否使用 Vertex AI（None 表示使用默认值，默认 True）
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            http_options: HTTP 选项

        Returns:
            交互结果字典
        """
        # 默认使用 Vertex AI（企业级功能）
        use_vertexai = vertexai if vertexai is not None else self._default_vertexai
        
        # ✅ 如果使用 Vertex AI 但缺少 project/location 或 credentials，尝试从数据库获取
        # ✅ 如果使用 Gemini API 模式（vertexai=False），使用标准 API Key
        vertex_credentials = None
        if use_vertexai and self._db and user_id:
            from ..gemini.agent.client import get_vertex_ai_credentials_from_db
            
            db_project, db_location, db_credentials = get_vertex_ai_credentials_from_db(
                user_id=user_id,
                db=self._db,
                project=project,
                location=location
            )
            
            # 使用从数据库获取的值（如果提供了参数，优先使用参数）
            if db_project:
                project = project or db_project
            if db_location:
                location = location or db_location
            if db_credentials:
                vertex_credentials = db_credentials
        
        # 获取客户端
        # ✅ Gemini API 模式（vertexai=False）：使用标准 API Key
        # ✅ Vertex AI 模式（vertexai=True）：使用 ADC 或 credentials，不传递 api_key
        client = self.get_client(
            api_key=api_key if not use_vertexai else None,  # ✅ Gemini API 模式使用 API Key，Vertex AI 模式不使用
            vertexai=use_vertexai,
            project=project,
            location=location,
            credentials=vertex_credentials,  # 传递 credentials（如果从数据库获取），否则使用 ADC
            http_options=http_options
        )

        # 如果提供了 MCP 会话 ID，获取 MCP 工具
        if mcp_session_id and self._mcp_manager:
            try:
                mcp_tools = await self._mcp_manager.get_gemini_tools(mcp_session_id)
                if mcp_tools:
                    if tools is None:
                        tools = []
                    tools.extend(mcp_tools)
                    logger.info(f"Added {len(mcp_tools)} MCP tools to interaction")
            except Exception as e:
                logger.warning(f"Failed to get MCP tools: {e}")

        # 集成 Code Execution 工具（如果启用）
        # 检查工具列表中是否包含 code_execution
        code_execution_enabled = any(
            tool.get("type") == "code_execution" 
            for tool in (tools or [])
        )
        
        # 创建交互（使用官方 SDK）
        try:
            logger.info(f"[create_interaction] Creating interaction with agent: {agent}, vertexai={use_vertexai}, project={project}, location={location}")
            logger.debug(f"[create_interaction] Input: {input[:100] if isinstance(input, str) else str(input)[:100]}...")
            if agent_config:
                logger.debug(f"[create_interaction] Agent config: {agent_config}")
            if tools:
                logger.debug(f"[create_interaction] Tools count: {len(tools)}")

            # Official Interactions contract:
            # background=True requires store=True.
            if background and store is not True:
                raise ValueError("Interactions requires store=True when background=True")

            create_params = {
                "input": input,
                "agent": agent,
                "background": background,
            }
            if agent_config is not None:
                create_params["agent_config"] = agent_config
            if system_instruction is not None:
                create_params["system_instruction"] = system_instruction
            if tools is not None:
                create_params["tools"] = tools
            if previous_interaction_id:
                create_params["previous_interaction_id"] = previous_interaction_id
            if store is not None:
                create_params["store"] = store

            interaction = client.interactions.create(**create_params)
            
            logger.info(f"[create_interaction] Successfully created interaction: id={interaction.id}, status={interaction.status}")
            
        except Exception as e:
            logger.error(f"[create_interaction] Failed to create interaction: {type(e).__name__}: {str(e)}", exc_info=True)
            raise

        return {
            'id': interaction.id,
            'status': interaction.status,
            'outputs': getattr(interaction, 'outputs', None) or [],
            'error': getattr(interaction, 'error', None)
        }

    async def deep_research(
        self,
        prompt: str,
        model: str,
        api_key: str,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一的 Deep Research 接口 - 处理参数映射
        
        Args:
            prompt: Research query
            model: Model identifier (not used, but required by interface)
            api_key: Google API key
            user_id: User ID (for database configuration lookup)
            **kwargs: Additional parameters:
                - agent: Agent name (default: 'deep-research-pro-preview-12-2025')
                - background: Whether to run in background mode (default: True)
                - agent_config: Optional agent configuration
                - system_instruction: Optional system instruction
                - tools: Optional list of tools
                - mcp_session_id: Optional MCP session ID
                - memory_bank_id: Optional Memory Bank ID
                - session_id: Optional session ID
        
        Returns:
            Interaction result with ID and status
        """
        agent = kwargs.get("agent", "deep-research-pro-preview-12-2025")
        background = kwargs.get("background", True)
        agent_config = kwargs.get("agent_config")
        system_instruction = kwargs.get("system_instruction")
        tools = kwargs.get("tools")
        mcp_session_id = kwargs.get("mcp_session_id")
        
        # 如果提供了 memory_bank_id，可以在这里加载相关记忆
        # （这个逻辑已经在 GoogleService.create_deep_research 中实现）
        
        result = await self.create_interaction(
            input=prompt,
            api_key=api_key,
            agent=agent,
            background=background,
            agent_config=agent_config,
            system_instruction=system_instruction,
            tools=tools,
            mcp_session_id=mcp_session_id,
            store=True,
            vertexai=False,  # Deep Research 强制使用 Gemini API Interactions
            user_id=user_id
        )
        
        return result
    
    async def create_interaction_async(
        self,
        api_key: str,
        input: Union[str, List[Dict[str, Any]]],
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True,
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_session_id: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        store: Optional[bool] = None,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None,
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> Dict[str, Any]:
        """
        异步创建智能体交互

        Args:
            api_key: Google API 密钥
            input: 输入内容
            agent: 智能体名称
            background: 是否在后台运行
            agent_config: 智能体配置
            system_instruction: 系统指令
            tools: 工具列表
            mcp_session_id: MCP 会话 ID
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            http_options: HTTP 选项

        Returns:
            交互结果字典
        """
        # 获取异步客户端
        async_client = self.get_async_client(
            api_key=api_key if not vertexai else None,
            vertexai=vertexai,
            project=project,
            location=location,
            http_options=http_options
        )

        # 如果提供了 MCP 会话 ID，获取 MCP 工具
        if mcp_session_id and self._mcp_manager:
            try:
                mcp_tools = await self._mcp_manager.get_gemini_tools(mcp_session_id)
                if mcp_tools:
                    if tools is None:
                        tools = []
                    tools.extend(mcp_tools)
                    logger.info(f"Added {len(mcp_tools)} MCP tools to interaction")
            except Exception as e:
                logger.warning(f"Failed to get MCP tools: {e}")

        # Official Interactions contract:
        # background=True requires store=True.
        if background and store is not True:
            raise ValueError("Interactions requires store=True when background=True")

        create_params = {
            "input": input,
            "agent": agent,
            "background": background,
        }
        if agent_config is not None:
            create_params["agent_config"] = agent_config
        if system_instruction is not None:
            create_params["system_instruction"] = system_instruction
        if tools is not None:
            create_params["tools"] = tools
        if previous_interaction_id:
            create_params["previous_interaction_id"] = previous_interaction_id
        if store is not None:
            create_params["store"] = store

        # 创建交互
        interaction = await async_client.interactions.create(**create_params)

        return {
            'id': interaction.id,
            'status': interaction.status,
            'outputs': getattr(interaction, 'outputs', None) or [],
            'error': getattr(interaction, 'error', None)
        }

    async def get_interaction_status(
        self,
        api_key: str,
        interaction_id: str,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取交互状态

        Args:
            api_key: Google API 密钥
            interaction_id: 交互 ID
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置

        Returns:
            交互状态字典
        """
        client = self.get_client(
            api_key=api_key,
            vertexai=vertexai,
            project=project,
            location=location
        )

        interaction = client.interactions.get(interaction_id)

        return {
            'id': interaction.id,
            'status': interaction.status,
            'outputs': getattr(interaction, 'outputs', None) or [],
            'error': getattr(interaction, 'error', None)
        }

    async def get_interaction_status_async(
        self,
        api_key: str,
        interaction_id: str,
        vertexai: Optional[bool] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None  # 用户 ID（用于从数据库获取配置）
    ) -> Dict[str, Any]:
        """
        异步获取交互状态

        Args:
            api_key: Google API 密钥
            interaction_id: 交互 ID
            vertexai: 是否使用 Vertex AI（None 表示使用默认值）
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            user_id: 用户 ID（用于从数据库获取配置）

        Returns:
            交互状态字典
        """
        # 默认使用 Vertex AI
        use_vertexai = vertexai if vertexai is not None else self._default_vertexai
        vertex_credentials = None
        
        # 如果使用 Vertex AI 但缺少 project/location，尝试从数据库获取
        # 使用统一的辅助函数
        if use_vertexai and (not project or not location) and self._db and user_id:
            from ..gemini.agent.client import get_vertex_ai_credentials_from_db
            
            db_project, db_location, db_credentials = get_vertex_ai_credentials_from_db(
                user_id=user_id,
                db=self._db,
                project=project,
                location=location
            )
            
            # 使用从数据库获取的值（如果提供了参数，优先使用参数）
            if db_project:
                project = project or db_project
            if db_location:
                location = location or db_location
            if db_credentials:
                vertex_credentials = db_credentials
        
        async_client = self.get_async_client(
            api_key=api_key if not use_vertexai else None,
            vertexai=use_vertexai,
            project=project,
            location=location,
            credentials=vertex_credentials
        )

        interaction = await async_client.interactions.get(interaction_id)

        return {
            'id': interaction.id,
            'status': interaction.status,
            'outputs': getattr(interaction, 'outputs', None) or [],
            'error': getattr(interaction, 'error', None)
        }

    async def wait_for_completion(
        self,
        api_key: str,
        interaction_id: str,
        timeout: int = 300,
        poll_interval: int = 2,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        等待交互完成

        Args:
            api_key: Google API 密钥
            interaction_id: 交互 ID
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置

        Returns:
            完成的交互结果

        Raises:
            TimeoutError: 超时
            Exception: 交互失败或取消
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.get_interaction_status_async(
                api_key=api_key,
                interaction_id=interaction_id,
                vertexai=vertexai,
                project=project,
                location=location
            )

            if status['status'] == 'completed':
                return status
            elif status['status'] == 'failed':
                raise Exception(f"交互失败: {interaction_id}")
            elif status['status'] == 'cancelled':
                raise Exception(f"交互已取消: {interaction_id}")

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"交互超时: {interaction_id}")

    async def stream_interaction(
        self,
        input: Union[str, List[Dict[str, Any]]],
        api_key: Optional[str] = None,
        agent: str = 'deep-research-pro-preview-12-2025',
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        mcp_session_id: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        vertexai: Optional[bool] = None,  # None 表示使用默认值
        project: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None,  # 用户 ID（用于从数据库获取配置）
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式创建交互

        Args:
            api_key: Google API 密钥
            input: 输入内容
            agent: 智能体名称
            agent_config: 智能体配置
            system_instruction: 系统指令
            tools: 工具列表
            mcp_session_id: MCP 会话 ID
            vertexai: 是否使用 Vertex AI（None 表示使用默认值，默认 True）
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            http_options: HTTP 选项

        Yields:
            流式事件字典
        """
        # 默认使用 Vertex AI（企业级功能）
        use_vertexai = vertexai if vertexai is not None else self._default_vertexai
        
        # ✅ 如果使用 Vertex AI 但缺少 project/location 或 credentials，尝试从数据库获取
        # ✅ 如果使用 Gemini API 模式（vertexai=False），使用标准 API Key
        vertex_credentials = None
        if use_vertexai and self._db and user_id:
            from ..gemini.agent.client import get_vertex_ai_credentials_from_db
            
            db_project, db_location, db_credentials = get_vertex_ai_credentials_from_db(
                user_id=user_id,
                db=self._db,
                project=project,
                location=location
            )
            
            # 使用从数据库获取的值（如果提供了参数，优先使用参数）
            if db_project:
                project = project or db_project
            if db_location:
                location = location or db_location
            if db_credentials:
                vertex_credentials = db_credentials
        
        # ✅ 获取客户端（根据模式选择不同的实现）
        # - Gemini API 模式: 使用 genai_agent/client.py，返回原生 google.genai.Client
        # - Vertex AI 模式: 使用 agent/client.py，返回包装的 Client 类
        client = self.get_client(
            api_key=api_key if not use_vertexai else None,  # ✅ Gemini API 模式使用 API Key，Vertex AI 模式不使用
            vertexai=use_vertexai,
            project=project,
            location=location,
            credentials=vertex_credentials,  # 传递 credentials（如果从数据库获取），否则使用 ADC
            http_options=http_options
        )
        
        # ✅ 根据客户端类型选择 interactions 访问方式
        # Gemini API 模式: 原生 google.genai.Client，直接使用 client.interactions
        # Vertex AI 模式: 包装的 Client，使用 client.aio.interactions
        if use_vertexai:
            # Vertex AI 模式：使用包装器的异步 interactions
            interactions = client.aio.interactions
        else:
            # Gemini API 模式：直接使用原生 client.interactions（同步）
            # 注意：原生 SDK 的 interactions.create(stream=True) 返回同步 Stream 对象
            interactions = client.interactions

        # 如果提供了 MCP 会话 ID，获取 MCP 工具
        if mcp_session_id and self._mcp_manager:
            try:
                mcp_tools = await self._mcp_manager.get_gemini_tools(mcp_session_id)
                if mcp_tools:
                    if tools is None:
                        tools = []
                    tools.extend(mcp_tools)
                    logger.info(f"Added {len(mcp_tools)} MCP tools to stream interaction")
            except Exception as e:
                logger.warning(f"Failed to get MCP tools: {e}")

        # 集成 Code Execution 工具（如果启用）
        code_execution_enabled = any(
            (isinstance(tool, dict) and tool.get("type") == "code_execution") or
            (hasattr(tool, "type") and tool.type == "code_execution")
            for tool in (tools or [])
        )
        
        if code_execution_enabled:
            logger.info("[InteractionsManager] Code execution enabled for stream interaction")
        
        # 创建流式交互（流式模式下也需要 background=True）
        logger.info(f"Starting stream interaction with agent: {agent}")
        logger.info(f"Input: {input[:100] if isinstance(input, str) else str(input)[:100]}...")
        if agent_config:
            logger.info(f"Agent config: {agent_config}")
        
        # ✅ 根据模式调用 interactions.create()
        # Gemini API 模式: client.interactions.create() 是同步方法，返回 Stream 对象
        # Vertex AI 模式: client.aio.interactions.create() 是异步方法，返回协程，await 后得到 Stream 对象
        
        # 构建 create 参数（只传递非 None 的参数）
        create_params = {
            'input': input,
            'agent': agent,
            'stream': True,
            'background': True,
            'store': True,
        }
        if agent_config is not None:
            create_params['agent_config'] = agent_config
        if system_instruction is not None:
            create_params['system_instruction'] = system_instruction
        if tools is not None:
            create_params['tools'] = tools
        if previous_interaction_id:
            create_params['previous_interaction_id'] = previous_interaction_id
        
        if use_vertexai:
            # Vertex AI 模式：使用异步方法
            stream_coro = interactions.create(**create_params)
            # await 协程得到 Stream 对象（同步迭代器）
            stream = await stream_coro
        else:
            # Gemini API 模式：直接调用同步方法，得到 Stream 对象
            stream = interactions.create(**create_params)

        # 处理流式事件
        event_count = 0
        total_delta_length = 0
        interaction_id = None
        
        # ✅ Stream对象是同步迭代器，需要在事件循环中迭代
        # 使用asyncio.to_thread()在后台线程中迭代，或直接使用for循环（如果Stream支持）
        # 根据官方SDK，Stream对象应该可以直接迭代
        import asyncio
        loop = asyncio.get_event_loop()
        
        # 创建一个队列来在后台线程中迭代Stream
        queue = asyncio.Queue()
        
        def iterate_stream():
            """在后台线程中迭代Stream"""
            try:
                for event in stream:
                    # 将事件放入队列（阻塞直到队列有空间）
                    loop.call_soon_threadsafe(queue.put_nowait, event)
                # 发送结束标记
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as e:
                # 发送错误标记
                loop.call_soon_threadsafe(queue.put_nowait, {"__error__": e})
        
        # 在后台线程中启动迭代
        import threading
        thread = threading.Thread(target=iterate_stream, daemon=True)
        thread.start()
        
        # 从队列中异步获取事件
        while True:
            event = await queue.get()
            if event is None:
                # 结束标记
                break
            if isinstance(event, dict) and "__error__" in event:
                # 错误标记
                raise event["__error__"]
            event_count += 1
            
            # ✅ 提取事件类型（Interactions API 使用 event_type 属性）
            event_type = getattr(event, 'event_type', None)
            if not event_type:
                # 如果没有 event_type，尝试从类名推断
                event_type = type(event).__name__
                # 转换为小写并替换下划线（例如：InteractionStartEvent -> interaction.start）
                event_type = event_type.lower().replace('event', '').replace('_', '.')
            
            # 转换事件为字典格式（兼容 _interactions API 格式）
            event_dict = {
                'event_type': event_type,
            }
            
            # ✅ 提取 event_id（支持不同 SDK 事件字段）
            event_id = (
                getattr(event, "event_id", None)
                or getattr(event, "eventId", None)
                or getattr(event, "id", None)
            )
            if event_id:
                event_dict['event_id'] = event_id
            
            # ✅ 根据事件类型提取数据并记录日志
            # Interactions API 的事件格式：event.interaction, event.delta, event.status, event.error
            if hasattr(event, 'interaction'):
                interaction = event.interaction
                interaction_id = getattr(interaction, 'id', None)
                interaction_status = getattr(interaction, 'status', None)
                
                event_dict['interaction'] = {
                    'id': interaction_id,
                    'status': interaction_status,
                    'outputs': getattr(interaction, 'outputs', None)
                }
                
                # 记录交互事件
                if interaction_id:
                    logger.info(f"[Stream Event #{event_count}] {event_type} - ID: {interaction_id}, Status: {interaction_status}")
                else:
                    logger.info(f"[Stream Event #{event_count}] {event_type} - Status: {interaction_status}")
            
            # ✅ 处理 content 事件（如果存在，但 Interactions API 主要使用 delta）
            if hasattr(event, 'content'):
                content = event.content
                if hasattr(content, 'text'):
                    text = content.text
                    if text:  # 只处理非空文本
                        event_dict['text'] = text
                        content_type = getattr(content, 'type', 'unknown')
                        event_dict['content_type'] = content_type
                        
                        # 记录内容事件
                        text_preview = text[:100] if text else ""
                        logger.info(f"[Stream Event #{event_count}] {event_type} - Type: {content_type}, Length: {len(text)} chars")
                        if text_preview:
                            logger.debug(f"Content preview: {text_preview}...")
                elif hasattr(content, 'type'):
                    # 即使没有文本，也记录内容类型
                    content_type = getattr(content, 'type', 'unknown')
                    event_dict['content_type'] = content_type
                    logger.info(f"[Stream Event #{event_count}] {event_type} - Type: {content_type} (no text)")
            
            if hasattr(event, 'delta'):
                delta = event.delta
                # ✅ 处理 Interactions API 的 delta 格式
                # delta 可能有 type 属性：'text' 或 'thought_summary'
                delta_type = getattr(delta, 'type', None) if hasattr(delta, 'type') else None
                
                # 提取文本内容
                delta_text = None
                if hasattr(delta, 'text') and delta.text:
                    delta_text = delta.text
                elif hasattr(delta, 'content') and hasattr(delta.content, 'text'):
                    # thought_summary 格式：delta.content.text
                    delta_text = delta.content.text
                
                if delta_text:
                    # ✅ 转换为兼容格式（与 _interactions API 格式一致）
                    event_dict['delta'] = {
                        'type': delta_type or 'text',
                        'text': delta_text
                    }
                    # 如果是 thought_summary，添加 content 字段
                    if delta_type == 'thought_summary':
                        event_dict['delta']['content'] = {
                            'text': delta_text
                        }
                    
                    total_delta_length += len(delta_text)
                    
                    # 记录增量内容（研究过程的实时输出）
                    logger.info(f"[Stream Event #{event_count}] ContentDelta - Type: {delta_type or 'text'}, Length: {len(delta_text)} chars, Total: {total_delta_length} chars")
                    # 记录增量内容的前100个字符
                    if len(delta_text) > 0:
                        preview = delta_text[:100].replace('\n', '\\n')
                        logger.debug(f"Delta preview: {preview}...")
                else:
                    event_dict['delta'] = None
            
            if hasattr(event, 'status'):
                status = event.status
                event_dict['status'] = status
                logger.info(f"[Stream Event #{event_count}] {event_type} - Status: {status}")
            
            if hasattr(event, 'error'):
                error = event.error
                # ✅ 处理错误格式（可能是字符串或对象）
                if isinstance(error, dict):
                    event_dict['error'] = error
                    error_str = error.get('message', str(error))
                elif isinstance(error, str):
                    event_dict['error'] = {
                        'type': 'Error',
                        'message': error
                    }
                    error_str = error
                else:
                    error_str = str(error) if error else None
                    event_dict['error'] = {
                        'type': type(error).__name__ if error else 'Error',
                        'message': error_str
                    }
                if error_str:
                    logger.error(f"[Stream Event #{event_count}] {event_type} - Error: {error_str}")
            
            # ✅ 提取 usage（如果存在）
            if hasattr(event, 'usage'):
                usage = event.usage
                if usage:
                    event_dict['usage'] = serialize_usage(usage)
            
            # 不再添加原始事件对象（避免序列化问题）
            # event_dict['_raw_event'] = event
            
            yield event_dict
        
        # 流式结束日志
        logger.info(f"Stream interaction completed - Total events: {event_count}, Total delta length: {total_delta_length} chars")
        if interaction_id:
            logger.info(f"Final interaction ID: {interaction_id}")

    async def stream_existing_interaction(
        self,
        api_key: Optional[str] = None,
        interaction_id: str = None,
        last_event_id: Optional[str] = None,
        include_input: bool = False,
        vertexai: Optional[bool] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None,  # 用户 ID（用于从数据库获取配置）
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式获取已有交互的事件（用于 SSE）
        
        Args:
            api_key: Google API 密钥
            interaction_id: 交互 ID
            last_event_id: 上次事件 ID（用于断点续传）
            include_input: 是否包含输入事件（官方高级用法）
            vertexai: 是否使用 Vertex AI（None 表示使用默认值）
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            http_options: HTTP 选项
            
        Yields:
            流式事件字典
        """
        import asyncio
        from queue import Queue
        from threading import Thread
        
        # 默认使用 Vertex AI
        use_vertexai = vertexai if vertexai is not None else self._default_vertexai
        vertex_credentials = None
        
        # 如果使用 Vertex AI 但缺少 project/location，尝试从数据库获取
        # 使用统一的辅助函数
        if use_vertexai and (not project or not location) and self._db and user_id:
            from ..gemini.agent.client import get_vertex_ai_credentials_from_db
            
            db_project, db_location, db_credentials = get_vertex_ai_credentials_from_db(
                user_id=user_id,
                db=self._db,
                project=project,
                location=location
            )
            
            # 使用从数据库获取的值（如果提供了参数，优先使用参数）
            if db_project:
                project = project or db_project
            if db_location:
                location = location or db_location
            if db_credentials:
                vertex_credentials = db_credentials
        
        try:
            logger.info(
                "Streaming existing interaction: %s, last_event_id=%s, include_input=%s",
                interaction_id,
                last_event_id,
                include_input,
            )

            # Deep Research 流使用更长的读超时，避免无增量阶段被过早切断。
            effective_http_options = http_options
            if effective_http_options is None:
                effective_http_options = HttpOptions(
                    timeout=_get_interactions_stream_timeout_ms()
                )

            # 使用队列在线程和异步代码之间传递数据
            queue = Queue()

            def sync_stream_worker():
                """在独立线程中运行同步的流式代码"""
                current_last_event_id = last_event_id if last_event_id else None
                resume_attempt = 0
                max_resume = _get_interactions_stream_max_resume()
                backoff_sec = _get_interactions_stream_resume_backoff_sec()

                while True:
                    try:
                        # ✅ 获取客户端
                        # Gemini API 模式（vertexai=False）：使用标准 API Key
                        # Vertex AI 模式（vertexai=True）：使用 ADC 或 credentials，不传递 api_key
                        client = self.get_client(
                            api_key=api_key if not use_vertexai else None,  # ✅ Gemini API 模式使用 API Key，Vertex AI 模式不使用
                            vertexai=use_vertexai,
                            project=project,
                            location=location,
                            credentials=vertex_credentials,  # 传递 credentials（如果从数据库获取），否则使用 ADC
                            http_options=effective_http_options
                        )

                        # 调用 SDK 的流式接口（同步）
                        stream = client.interactions.get(
                            id=interaction_id,
                            stream=True,
                            last_event_id=current_last_event_id,
                            include_input=include_input,
                        )

                        # 遍历流式事件（同步）
                        for chunk in stream:
                            event_data = build_interaction_stream_event(chunk)
                            event_id = event_data.get("event_id")
                            if isinstance(event_id, str) and event_id:
                                current_last_event_id = event_id

                            queue.put(("data", event_data))
                            event_type = event_data.get("event_type")
                            if event_type in {"interaction.complete", "error"}:
                                if event_type == "interaction.complete":
                                    logger.info(f"Stream completed for interaction: {interaction_id}")
                                else:
                                    logger.warning(
                                        "Stream returned error event for interaction %s: %s",
                                        interaction_id,
                                        event_data.get("error"),
                                    )
                                queue.put(("done", None))
                                return

                        # SDK 流对象自然结束（无 complete），尝试基于 last_event_id 续流。
                        resume_attempt += 1
                        if resume_attempt > max_resume:
                            queue.put(("data", {
                                "event_type": "error",
                                "error": (
                                    "Interaction stream closed before completion and "
                                    f"resume exceeded max attempts ({max_resume})"
                                ),
                            }))
                            queue.put(("done", None))
                            return

                        logger.warning(
                            "Interaction stream ended unexpectedly, resuming (%s/%s), interaction=%s, last_event_id=%s",
                            resume_attempt,
                            max_resume,
                            interaction_id,
                            current_last_event_id,
                        )
                        time.sleep(backoff_sec * resume_attempt)

                    except Exception as e:
                        if _is_retryable_stream_exception(e) and resume_attempt < max_resume:
                            resume_attempt += 1
                            logger.warning(
                                "Retryable stream error, resuming (%s/%s), interaction=%s, last_event_id=%s, error=%s",
                                resume_attempt,
                                max_resume,
                                interaction_id,
                                current_last_event_id,
                                e,
                            )
                            time.sleep(backoff_sec * resume_attempt)
                            continue

                        logger.error(f"Failed to stream interaction {interaction_id}: {e}")
                        queue.put(("data", {
                            "event_type": "error",
                            "error": str(e)
                        }))
                        queue.put(("done", None))
                        return

            # 启动工作线程
            thread = Thread(target=sync_stream_worker, daemon=True)
            thread.start()
            
            # 从队列中读取事件并 yield
            while True:
                msg_type, data = await asyncio.to_thread(queue.get)
                
                if msg_type == "done":
                    break
                elif msg_type == "data":
                    yield data
                    
        except Exception as e:
            logger.error(f"Failed to stream interaction {interaction_id}: {e}")
            yield {
                "event_type": "error",
                "error": str(e)
            }

    async def delete_interaction(
        self,
        api_key: str,
        interaction_id: str,
        vertexai: Optional[bool] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None  # 用户 ID（用于从数据库获取配置）
    ) -> None:
        """
        删除交互

        Args:
            api_key: Google API 密钥
            interaction_id: 交互 ID
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
        """
        client = self.get_client(
            api_key=api_key,
            vertexai=vertexai,
            project=project,
            location=location
        )

        # 删除交互
        client.interactions.delete(id=interaction_id)
        logger.info(f"Deleted interaction: {interaction_id}")

    async def cancel_interaction(
        self,
        api_key: str,
        interaction_id: str,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        取消正在运行的交互

        只适用于后台模式中仍在运行的交互。

        Args:
            api_key: Google API 密钥
            interaction_id: 交互 ID
            vertexai: 是否使用 Vertex AI
            project: Google Cloud 项目 ID
            location: Google Cloud 位置

        Returns:
            取消后的交互状态
        """
        async_client = self.get_async_client(
            api_key=api_key,
            vertexai=vertexai,
            project=project,
            location=location
        )

        # 取消交互
        official_interaction = await async_client.interactions.cancel(id=interaction_id)
        logger.info(f"Cancelled interaction: {interaction_id}, status: {official_interaction.status}")

        # 转换为字典格式
        from ..gemini.agent.interactions import Interaction
        interaction = Interaction.from_official(official_interaction)

        return {
            'id': interaction.id,
            'status': interaction.status,
            'outputs': getattr(interaction, 'outputs', None) or [],
            'error': getattr(interaction, 'error', None)
        }

    async def close_all(self) -> None:
        """关闭所有客户端（从统一池）"""
        pool = get_client_pool()
        pool.close_all()

    def list_clients(self) -> Dict[str, Dict[str, Any]]:
        """列出所有客户端缓存键（从统一池）"""
        pool = get_client_pool()
        return pool.list_clients()


# 全局单例（可选）
_global_manager: Optional[InteractionsManager] = None


def get_interactions_manager(
    mcp_manager: Optional[MCPManager] = None,
    db: Optional[Session] = None,
    default_vertexai: bool = True
) -> InteractionsManager:
    """
    获取全局 Interactions 管理器实例

    Args:
        mcp_manager: MCP 管理器实例（可选）
        db: 数据库会话（可选，用于获取 Vertex AI 配置）
        default_vertexai: 默认是否使用 Vertex AI（企业级功能）

    Returns:
        InteractionsManager 单例
    """
    global _global_manager
    if _global_manager is None:
        if mcp_manager is None:
            mcp_manager = get_mcp_manager()
        _global_manager = InteractionsManager(
            mcp_manager=mcp_manager,
            db=db,
            default_vertexai=default_vertexai
        )
    return _global_manager
