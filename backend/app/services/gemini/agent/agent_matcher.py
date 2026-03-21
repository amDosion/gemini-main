"""
Agent Matcher - 代理匹配器

为子任务匹配合适的代理，考虑：
- 能力匹配
- 专业领域匹配
- 负载均衡
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .task_decomposer import SubTask

logger = logging.getLogger(__name__)


@dataclass
class AgentLoad:
    """
    代理负载信息
    
    Attributes:
        agent_id: 代理 ID
        current_tasks: 当前任务数量
        max_capacity: 最大容量
        last_used: 最后使用时间戳
    """
    agent_id: str
    current_tasks: int = 0
    max_capacity: int = 10
    last_used: float = 0.0
    
    @property
    def load_ratio(self) -> float:
        """负载比率（0.0-1.0）"""
        if self.max_capacity == 0:
            return 1.0
        return min(self.current_tasks / self.max_capacity, 1.0)
    
    @property
    def available_capacity(self) -> int:
        """可用容量"""
        return max(0, self.max_capacity - self.current_tasks)


class AgentMatcher:
    """
    代理匹配器
    
    为子任务匹配合适的代理，考虑：
    1. 能力匹配（capabilities）
    2. 专业领域匹配（specialization）
    3. 负载均衡（load balancing）
    """
    
    def __init__(self):
        """初始化代理匹配器"""
        self.agent_loads: Dict[str, AgentLoad] = {}
        logger.info("[AgentMatcher] Initialized")
    
    def match_agent(
        self,
        subtask: SubTask,
        available_agents: List[Dict[str, Any]],
        consider_load: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        为子任务匹配合适的代理
        
        Args:
            subtask: 子任务
            available_agents: 可用代理列表
            consider_load: 是否考虑负载均衡（默认：True）
            
        Returns:
            匹配的代理信息，如果没有匹配则返回 None
        """
        if not available_agents:
            logger.warning("[AgentMatcher] No available agents")
            return None
        
        if not subtask.required_capabilities:
            # 如果没有指定能力要求，选择负载最低的代理
            return self._select_by_load(available_agents) if consider_load else available_agents[0]
        
        # 计算每个代理的匹配分数
        scores: List[Tuple[Dict[str, Any], float]] = []
        for agent in available_agents:
            score = self._calculate_match_score(subtask, agent, consider_load)
            scores.append((agent, score))
        
        # 按分数排序（降序）
        scores.sort(key=lambda x: x[1], reverse=True)
        
        if not scores or scores[0][1] == 0.0:
            logger.warning(
                f"[AgentMatcher] No suitable agent found for subtask: {subtask.description}"
            )
            return None
        
        best_agent = scores[0][0]
        logger.info(
            f"[AgentMatcher] Matched agent {best_agent.get('id')} "
            f"(score: {scores[0][1]:.2f}) for subtask: {subtask.description[:50]}"
        )
        
        return best_agent
    
    def _calculate_match_score(
        self,
        subtask: SubTask,
        agent: Dict[str, Any],
        consider_load: bool
    ) -> float:
        """
        计算代理匹配分数
        
        Args:
            subtask: 子任务
            agent: 代理信息
            consider_load: 是否考虑负载
            
        Returns:
            匹配分数（0.0-1.0）
        """
        # 1. 能力匹配分数（权重：0.6）
        capability_score = self._calculate_capability_score(
            subtask.required_capabilities,
            agent.get("capabilities", [])
        )
        
        # 2. 专业领域匹配分数（权重：0.2）
        specialization_score = self._calculate_specialization_score(
            subtask,
            agent
        )
        
        # 3. 建议代理匹配（如果子任务有建议的代理 ID）
        suggested_score = 0.0
        if subtask.suggested_agent_id and agent.get("id") == subtask.suggested_agent_id:
            suggested_score = 0.2
        
        # 4. 负载分数（权重：0.2，如果启用）
        load_score = 0.0
        if consider_load:
            load_score = self._calculate_load_score(agent.get("id"))
        
        # 综合分数
        total_score = (
            capability_score * 0.6 +
            specialization_score * 0.2 +
            suggested_score +
            load_score * (0.2 if consider_load else 0.0)
        )
        
        return min(total_score, 1.0)
    
    def _calculate_capability_score(
        self,
        required_capabilities: List[str],
        agent_capabilities: List[str]
    ) -> float:
        """
        计算能力匹配分数
        
        Args:
            required_capabilities: 所需能力列表
            agent_capabilities: 代理能力列表
            
        Returns:
            匹配分数（0.0-1.0）
        """
        if not required_capabilities:
            return 1.0  # 如果没有要求，所有代理都匹配
        
        if not agent_capabilities:
            return 0.0  # 如果代理没有能力，不匹配
        
        # 计算匹配的能力数量
        required_lower = [cap.lower() for cap in required_capabilities]
        agent_lower = [cap.lower() for cap in agent_capabilities]
        
        matched = sum(1 for req in required_lower if req in agent_lower)
        
        # 分数 = 匹配数 / 要求数
        return matched / len(required_capabilities)
    
    def _calculate_specialization_score(
        self,
        subtask: SubTask,
        agent: Dict[str, Any]
    ) -> float:
        """
        计算专业领域匹配分数
        
        Args:
            subtask: 子任务
            agent: 代理信息
            
        Returns:
            匹配分数（0.0-1.0）
        """
        # 从代理信息中获取专业领域
        specialization = agent.get("specialization", "")
        agent_type = agent.get("agent_type", "")
        name = agent.get("name", "")
        
        # 从子任务描述中提取关键词
        description_lower = subtask.description.lower()
        
        # 简单的关键词匹配
        score = 0.0
        
        # 检查专业领域
        if specialization and specialization.lower() in description_lower:
            score += 0.5
        
        # 检查代理类型
        if agent_type:
            # 根据代理类型判断是否匹配
            if agent_type == "data" and any(kw in description_lower for kw in ["数据", "分析", "excel", "csv"]):
                score += 0.3
            elif agent_type == "image" and any(kw in description_lower for kw in ["图像", "图片", "编辑", "生成"]):
                score += 0.3
            elif agent_type == "text" and any(kw in description_lower for kw in ["文本", "写作", "生成", "总结"]):
                score += 0.3
        
        # 检查名称关键词
        if name:
            name_lower = name.lower()
            if any(kw in description_lower for kw in name_lower.split()):
                score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_load_score(self, agent_id: Optional[str]) -> float:
        """
        计算负载分数（负载越低，分数越高）
        
        Args:
            agent_id: 代理 ID
            
        Returns:
            负载分数（0.0-1.0）
        """
        if not agent_id:
            return 0.5  # 如果没有 ID，返回中等分数
        
        load_info = self.agent_loads.get(agent_id)
        if not load_info:
            return 1.0  # 如果没有负载信息，假设负载为 0
        
        # 负载分数 = 1.0 - 负载比率
        return 1.0 - load_info.load_ratio
    
    def _select_by_load(self, agents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        根据负载选择代理
        
        Args:
            agents: 代理列表
            
        Returns:
            负载最低的代理
        """
        if not agents:
            return None
        
        best_agent = None
        best_score = -1.0
        
        for agent in agents:
            agent_id = agent.get("id")
            load_score = self._calculate_load_score(agent_id)
            
            if load_score > best_score:
                best_score = load_score
                best_agent = agent
        
        return best_agent
    
    def update_agent_load(
        self,
        agent_id: str,
        current_tasks: int,
        max_capacity: int = 10
    ) -> None:
        """
        更新代理负载信息
        
        Args:
            agent_id: 代理 ID
            current_tasks: 当前任务数量
            max_capacity: 最大容量
        """
        import time
        
        if agent_id not in self.agent_loads:
            self.agent_loads[agent_id] = AgentLoad(
                agent_id=agent_id,
                max_capacity=max_capacity
            )
        
        self.agent_loads[agent_id].current_tasks = current_tasks
        self.agent_loads[agent_id].max_capacity = max_capacity
        self.agent_loads[agent_id].last_used = time.time()
        
        logger.debug(
            f"[AgentMatcher] Updated load for agent {agent_id}: "
            f"{current_tasks}/{max_capacity} (ratio: {self.agent_loads[agent_id].load_ratio:.2f})"
        )
    
    def get_agent_load(self, agent_id: str) -> Optional[AgentLoad]:
        """
        获取代理负载信息
        
        Args:
            agent_id: 代理 ID
            
        Returns:
            负载信息，如果不存在则返回 None
        """
        return self.agent_loads.get(agent_id)
    
    def reset_agent_load(self, agent_id: str) -> None:
        """
        重置代理负载（将当前任务数设为 0）
        
        Args:
            agent_id: 代理 ID
        """
        if agent_id in self.agent_loads:
            self.agent_loads[agent_id].current_tasks = 0
            logger.debug(f"[AgentMatcher] Reset load for agent {agent_id}")
