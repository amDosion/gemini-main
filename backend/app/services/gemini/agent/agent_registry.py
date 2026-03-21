"""
Agent Registry - 智能体注册表

提供：
- 智能体注册和发现
- 智能体能力匹配
- 负载均衡
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import AgentRegistry as AgentRegistryModel

logger = logging.getLogger(__name__)


class AgentRegistryService:
    """
    智能体注册表
    
    负责：
    - 智能体注册和发现
    - 智能体能力匹配
    - 负载均衡
    """
    
    def __init__(self, db: Session):
        """
        初始化智能体注册表
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[AgentRegistryService] Initialized")
    
    async def register_agent(
        self,
        user_id: str,
        name: str,
        agent_type: str,
        agent_card: Optional[Dict[str, Any]] = None,
        endpoint_url: Optional[str] = None,
        tools: Optional[List[str]] = None,
        mcp_session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        注册智能体
        
        Args:
            user_id: 用户 ID
            name: 智能体名称
            agent_type: 智能体类型（adk/interactions/custom）
            agent_card: Agent Card（可选）
            endpoint_url: 端点 URL（可选）
            tools: 工具名称列表（可选）
            mcp_session_id: MCP 会话 ID（可选，用于加载 MCP 工具）
            
        Returns:
            注册的智能体信息
        """
        now = int(time.time() * 1000)
        
        # 将工具配置添加到 agent_card 中（如果不存在则创建）
        if agent_card is None:
            agent_card = {}
        
        if tools or mcp_session_id:
            agent_card["tools"] = {
                "tool_names": tools or [],
                "mcp_session_id": mcp_session_id
            }
        
        agent = AgentRegistryModel(
            user_id=user_id,
            name=name,
            agent_type=agent_type,
            agent_card_json=json.dumps(agent_card) if agent_card else None,
            endpoint_url=endpoint_url,
            status="active",
            created_at=now,
            updated_at=now
        )
        
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        
        logger.info(f"[AgentRegistryService] Registered agent {agent.id} for user {user_id} (tools: {tools})")
        return agent.to_dict()
    
    async def list_agents(
        self,
        user_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """
        列出智能体
        
        Args:
            user_id: 用户 ID（可选）
            agent_type: 智能体类型（可选）
            status: 状态（默认：active）
            
        Returns:
            智能体列表（包含工具配置信息）
        """
        query = self.db.query(AgentRegistryModel).filter(
            AgentRegistryModel.status == status
        )
        
        if user_id:
            query = query.filter(AgentRegistryModel.user_id == user_id)
        
        if agent_type:
            query = query.filter(AgentRegistryModel.agent_type == agent_type)
        
        agents = query.order_by(AgentRegistryModel.created_at.desc()).all()
        
        # 转换为字典并提取工具信息
        result = []
        for agent in agents:
            agent_dict = agent.to_dict()
            
            # 从 agent_card 中提取工具配置
            if agent.agent_card_json:
                try:
                    agent_card = json.loads(agent.agent_card_json)
                    if "tools" in agent_card:
                        agent_dict["tools"] = agent_card["tools"]
                except json.JSONDecodeError:
                    pass
            
            result.append(agent_dict)
        
        return result
    
    async def get_agent(
        self,
        user_id: str,
        agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取智能体
        
        Args:
            user_id: 用户 ID
            agent_id: 智能体 ID
            
        Returns:
            智能体信息，如果不存在则返回 None
        """
        agent = self.db.query(AgentRegistryModel).filter(
            AgentRegistryModel.id == agent_id,
            AgentRegistryModel.user_id == user_id
        ).first()
        
        if agent:
            return agent.to_dict()
        return None
    
    async def match_agents(
        self,
        capability: str,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        匹配智能体能力
        
        Args:
            capability: 所需能力
            user_id: 用户 ID（可选）
            
        Returns:
            匹配的智能体列表
        """
        # 简化实现：返回所有活跃的智能体
        # 实际应该根据 Agent Card 中的技能进行匹配
        return await self.list_agents(user_id=user_id, status="active")
