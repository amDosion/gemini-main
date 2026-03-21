"""
Vertex AI Interactions Service - 企业级 Interactions 服务

基于 Vertex AI 客户端，提供完整的 Interactions API 支持：
- 基础交互创建和查询
- Agent Engine 集成（Memory Bank、Code Execution）
- 流式响应处理
- 工具编排

与 official/_interactions 的区别：
- 专门针对 Vertex AI 优化
- 集成 Agent Engine 高级功能
- 使用统一的客户端池管理
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List, Union, AsyncIterator
from sqlalchemy.orm import Session

# 延迟导入以避免循环导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .client import Client, AsyncClient
    from .types import HttpOptions, HttpOptionsDict
from ...common.interactions_event_utils import build_interaction_stream_event
from .memory_manager import MemoryManager
from .code_executor import AgentEngineSandboxCodeExecutor

logger = logging.getLogger(__name__)


class VertexAiInteractionsService:
    """
    Vertex AI Interactions 服务（企业级）
    
    基于 Vertex AI 客户端，提供完整的 Interactions API 支持。
    充分利用 Vertex AI 的企业级特性，包括 Agent Engine 高级功能。
    """
    
    def __init__(
        self,
        db: Session,
        project: str,
        location: str,
        agent_engine_id: Optional[str] = None,
        api_key: Optional[str] = None,
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None
    ):
        """
        初始化 Vertex AI Interactions 服务
        
        Args:
            db: 数据库会话
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
            agent_engine_id: Agent Engine ID（可选）
            api_key: API 密钥（可选，Vertex AI 也可以使用 credentials）
            http_options: HTTP 选项
        """
        self.db = db
        self.project = project
        self.location = location
        self.agent_engine_id = agent_engine_id
        self.api_key = api_key
        self.http_options = http_options
        
        # 初始化 Memory Manager（用于 Agent Engine Memory Bank）
        self.memory_manager = MemoryManager(
            db=db,
            use_vertex_ai=True,
            project=project,
            location=location
        )
        
        # 初始化 Code Executor（用于 Agent Engine Code Execution）
        self.code_executor = AgentEngineSandboxCodeExecutor(
            db=db,
            project=project,
            location=location,
            agent_engine_id=agent_engine_id
        )
        
        logger.info(
            f"[VertexAiInteractionsService] Initialized "
            f"(project={project}, location={location}, agent_engine_id={agent_engine_id})"
        )
    
    def get_client(self):
        """
        获取 Vertex AI 客户端（从统一池）
        
        Returns:
            Client 实例（Vertex AI 模式）
        """
        # 延迟导入以避免循环导入
        from ..client_pool import get_client_pool
        from .client import Client
        
        pool = get_client_pool()
        return pool.get_client(
            api_key=self.api_key,
            vertexai=True,  # 强制使用 Vertex AI
            project=self.project,
            location=self.location,
            http_options=self.http_options
        )
    
    def get_async_client(self):
        """
        获取异步 Vertex AI 客户端（从统一池）
        
        Returns:
            AsyncClient 实例（Vertex AI 模式）
        """
        from .client import AsyncClient
        
        client = self.get_client()
        return client.aio
    
    async def create_interaction(
        self,
        input: Union[str, List[Dict[str, Any]]],
        agent: str = 'deep-research-pro-preview-12-2025',
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        background: bool = True,
        stream: bool = False,
        previous_interaction_id: Optional[str] = None,
        memory_bank_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        创建交互（Vertex AI）
        
        Args:
            input: 输入内容
            agent: 智能体名称
            agent_config: 智能体配置
            system_instruction: 系统指令
            tools: 工具列表
            background: 是否后台执行
            stream: 是否流式响应
            previous_interaction_id: 上一个交互 ID
            memory_bank_id: Memory Bank ID（自动集成）
            **kwargs: 其他参数
            
        Returns:
            Interaction 对象
        """
        client = self.get_client()
        
        # 集成 Memory Bank（如果提供）
        # 注意：Memory Bank 的集成应该在 agent_config 中配置，而不是在这里手动加载
        # 这里只是记录日志，实际的 Memory Bank 集成由 Vertex AI Agent Engine 处理
        if memory_bank_id:
            logger.info(f"[VertexAiInteractionsService] Memory Bank enabled: {memory_bank_id}")
            # Memory Bank 会通过 agent_config 传递给 Vertex AI，由 Agent Engine 自动处理
        
        # 集成 Code Execution 工具（如果启用）
        code_execution_enabled = any(
            (isinstance(tool, dict) and tool.get("type") == "code_execution") or
            (hasattr(tool, "type") and tool.type == "code_execution")
            for tool in (tools or [])
        )
        
        if code_execution_enabled:
            logger.info("[VertexAiInteractionsService] Code execution enabled for this interaction")
        
        # 构建 agent_config（如果未提供）
        if agent_config is None:
            agent_config = {}
        
        # 添加 Memory Bank 配置（如果提供）
        if memory_bank_id:
            agent_config["memory_bank_id"] = memory_bank_id
        
        # 调用 Vertex AI Interactions API（使用官方 SDK）
        # 注意：新的 client.interactions.create() 使用 agent_config 参数
        create_params = {
            "agent": agent,
            "input": input,
            "background": background,
        }
        
        if agent_config:
            create_params["agent_config"] = agent_config  # 使用 agent_config 参数
        if system_instruction:
            create_params["system_instruction"] = system_instruction
        if tools:
            create_params["tools"] = tools
        if previous_interaction_id:
            create_params["previous_interaction_id"] = previous_interaction_id
        
        create_params.update(kwargs)
        
        if stream:
            # 流式模式：返回流对象
            async_client = self.get_async_client()
            create_params["stream"] = True
            return await async_client.interactions.create(**create_params)
        else:
            # 同步模式：返回 Interaction 对象
            return client.interactions.create(**create_params)
    
    async def get_interaction(
        self,
        interaction_id: str
    ) -> Any:
        """
        获取交互状态（Vertex AI）
        
        Args:
            interaction_id: 交互 ID
            
        Returns:
            Interaction 对象
        """
        client = self.get_client()
        return client.interactions.get(id=interaction_id)
    
    async def stream_interaction(
        self,
        interaction_id: str,
        last_event_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式获取交互（Vertex AI）
        
        Args:
            interaction_id: 交互 ID
            last_event_id: 上次事件 ID（用于断点续传）
            
        Yields:
            流式事件字典
        """
        client = self.get_client()
        
        # 使用同步客户端获取流（SDK 内部会处理）
        stream = client.interactions.get(
            id=interaction_id,
            stream=True,
            last_event_id=last_event_id if last_event_id else None
        )
        
        # 转换流式事件为字典格式
        for chunk in stream:
            event_data = build_interaction_stream_event(chunk)
            if event_data.get("grounding_metadata"):
                logger.info(
                    "[VertexAiInteractionsService] Extracted grounding metadata: %s chunks",
                    len(event_data["grounding_metadata"].get("grounding_chunks", [])),
                )
            yield event_data
    
    async def delete_interaction(
        self,
        interaction_id: str
    ) -> None:
        """
        删除交互（Vertex AI）
        
        Args:
            interaction_id: 交互 ID
        """
        client = self.get_client()
        client.interactions.delete(id=interaction_id)
        logger.info(f"[VertexAiInteractionsService] Deleted interaction: {interaction_id}")
