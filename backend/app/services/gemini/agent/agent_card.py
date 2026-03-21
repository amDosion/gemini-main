"""
Agent Card - Agent Card 定义和管理

提供：
- Agent 元数据定义（名称、描述、技能）
- Agent Skill 定义（输入/输出模式、示例）
- Agent Card 注册和发现
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import AgentCard

logger = logging.getLogger(__name__)


class AgentCardManager:
    """
    Agent Card 管理器
    
    负责：
    - Agent Card 创建和更新
    - Agent Skill 定义
    - Agent Card 发现
    """
    
    def __init__(self, db: Session):
        """
        初始化 Agent Card 管理器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[AgentCardManager] Initialized")
    
    def create_agent_card(
        self,
        user_id: str,
        agent_id: str,
        card_data: Dict[str, Any],
        version: str = "1.0.0"
    ) -> Dict[str, Any]:
        """
        创建 Agent Card
        
        Args:
            user_id: 用户 ID
            agent_id: 智能体 ID
            card_data: Agent Card 数据
            version: Agent Card 版本
            
        Returns:
            Agent Card 信息
        """
        now = int(time.time() * 1000)
        
        card = AgentCard(
            user_id=user_id,
            agent_id=agent_id,
            card_json=json.dumps(card_data),
            version=version,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        
        logger.info(f"[AgentCardManager] Created agent card {card.id} for agent {agent_id}")
        return card.to_dict()
    
    def get_agent_card(
        self,
        user_id: str,
        agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Agent Card
        
        Args:
            user_id: 用户 ID
            agent_id: 智能体 ID
            
        Returns:
            Agent Card 信息，如果不存在则返回 None
        """
        card = self.db.query(AgentCard).filter(
            AgentCard.agent_id == agent_id,
            AgentCard.user_id == user_id
        ).order_by(AgentCard.created_at.desc()).first()
        
        if card:
            return card.to_dict()
        return None
    
    def list_agent_cards(
        self,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        列出 Agent Card
        
        Args:
            user_id: 用户 ID（可选，如果提供则只返回该用户的）
            
        Returns:
            Agent Card 列表
        """
        query = self.db.query(AgentCard)
        
        if user_id:
            query = query.filter(AgentCard.user_id == user_id)
        
        cards = query.order_by(AgentCard.created_at.desc()).all()
        
        return [card.to_dict() for card in cards]
    
    def create_agent_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        tags: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        input_modes: Optional[List[str]] = None,
        output_modes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建 Agent Skill
        
        Args:
            skill_id: 技能 ID
            name: 技能名称
            description: 技能描述
            tags: 标签列表（可选）
            examples: 示例列表（可选）
            input_modes: 输入模式列表（可选）
            output_modes: 输出模式列表（可选）
            
        Returns:
            Agent Skill 定义
        """
        return {
            "id": skill_id,
            "name": name,
            "description": description,
            "tags": tags or [],
            "examples": examples or [],
            "input_modes": input_modes or ["text/plain"],
            "output_modes": output_modes or ["text/plain"]
        }
