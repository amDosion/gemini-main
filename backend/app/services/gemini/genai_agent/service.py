"""
GenAI Agent Service - 主服务类

提供基于 Gemini API 的研究智能体服务
"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from ..client_pool import get_client_pool
from .research_agent import ResearchAgent
from .advanced_features import AdvancedResearchAgent
from .types import ResearchConfig, ResearchResult
from .tools import is_url

logger = logging.getLogger(__name__)


class GenAIAgentService:
    """GenAI Agent Service - 使用 Gemini API 实现研究智能体"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp"
    ):
        """
        初始化 GenAI Agent Service
        
        Args:
            api_key: Google API Key
            model: 模型名称
        """
        self.api_key = api_key
        self.model = model
        logger.info(f"[GenAIAgentService] Initialized with model: {model}")
    
    async def create_research(
        self,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建研究任务（非流式）
        
        Args:
            prompt: 研究提示
            tools: 工具列表
            agent_config: 智能体配置
            
        Returns:
            研究结果字典
        """
        try:
            client = get_client_pool().get_client(api_key=self.api_key)
            
            # 解析配置
            config = ResearchConfig()
            if agent_config:
                config.thinking_summaries = agent_config.get('thinking_summaries', 'auto')
                config.max_iterations = agent_config.get('max_iterations', 5)
                config.enable_search = agent_config.get('enable_search', True)
                config.enable_code_execution = agent_config.get('enable_code_execution', False)
                config.enable_file_search = agent_config.get('enable_file_search', False)
            
            # 创建研究智能体
            research_agent = ResearchAgent(
                client=client,
                model=self.model,
                tools=tools or [],
                config=config
            )
            
            # 执行研究
            result = await research_agent.execute(prompt)
            
            return {
                'id': result.session_id,
                'status': result.status,
                'outputs': result.outputs,
                'error': result.error
            }
            
        except Exception as e:
            logger.error(f"[GenAIAgentService] Failed to create research: {e}", exc_info=True)
            raise
    
    async def stream_research(
        self,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_config: Optional[Dict[str, Any]] = None,
        use_advanced: bool = True  # 是否使用高级功能
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行研究任务
        
        Args:
            prompt: 研究提示
            tools: 工具列表
            agent_config: 智能体配置
            use_advanced: 是否使用高级功能（多轮对话、思考过程等）
            
        Yields:
            流式事件字典（兼容 _interactions API 格式）
        """
        try:
            client = get_client_pool().get_client(api_key=self.api_key)
            
            # 解析配置
            config = ResearchConfig()
            if agent_config:
                config.thinking_summaries = agent_config.get('thinking_summaries', 'auto')
                config.max_iterations = agent_config.get('max_iterations', 5)
                config.enable_search = agent_config.get('enable_search', True)
                config.enable_code_execution = agent_config.get('enable_code_execution', False)
                config.enable_file_search = agent_config.get('enable_file_search', False)
            
            # ✅ 自动检测 URL 并启用 Browser 工具
            enable_browser = agent_config.get('enable_browser', False) if agent_config else False
            if not enable_browser and is_url(prompt):
                logger.info(f"[GenAIAgentService] Detected URL in prompt, enabling Browser tools")
                enable_browser = True
                if agent_config is None:
                    agent_config = {}
                agent_config['enable_browser'] = True
            
            # 如果启用 Browser 工具，添加到工具列表
            if enable_browser:
                if tools is None:
                    tools = []
                # 检查是否已包含 browser 工具
                has_browser_tool = any(
                    tool.get('type') == 'browser' or tool.get('type') == 'enable_browser'
                    for tool in tools
                )
                if not has_browser_tool:
                    tools.append({'type': 'browser'})
                    logger.info(f"[GenAIAgentService] Added Browser tools to research agent")
            
            # 根据配置选择使用基础或高级智能体
            if use_advanced:
                # 使用高级研究智能体（支持多轮对话、思考过程等）
                advanced_agent = AdvancedResearchAgent(
                    client=client,
                    model=self.model,
                    tools=tools or [],
                    config=config
                )
                
                # 获取对话历史（如果存在）
                conversation_history = agent_config.get('conversation_history') if agent_config else None
                
                # 流式执行（高级模式）
                async for event in advanced_agent.stream_research_advanced(
                    prompt=prompt,
                    conversation_history=conversation_history
                ):
                    yield event
            else:
                # 使用基础研究智能体
                research_agent = ResearchAgent(
                    client=client,
                    model=self.model,
                    tools=tools or [],
                    config=config
                )
                
                # 流式执行（基础模式）
                async for event in research_agent.stream_execute(prompt):
                    yield event
                
        except Exception as e:
            logger.error(f"[GenAIAgentService] Failed to stream research: {e}", exc_info=True)
            yield {
                'event_type': 'error',
                'error': {
                    'type': type(e).__name__,
                    'message': str(e)
                }
            }
