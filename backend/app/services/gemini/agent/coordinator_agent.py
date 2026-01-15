"""
Coordinator Agent - 协调代理（Coordinator/Dispatcher Pattern）

参考 Google ADK 的 Coordinator/Dispatcher 模式：
- 分析用户意图
- 选择最合适的子代理
- 路由任务到选定的代理
- 聚合结果

参考：
- https://github.com/google/adk-samples
- https://github.com/google/adk-python
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """
    用户意图分析结果
    
    Attributes:
        intent_type: 意图类型（如：数据分析、图像处理、文本生成等）
        confidence: 置信度（0-1）
        required_capabilities: 所需能力列表
        suggested_agent_id: 建议的代理 ID
        context: 额外上下文信息
    """
    intent_type: str
    confidence: float
    required_capabilities: List[str] = field(default_factory=list)
    suggested_agent_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class CoordinatorAgent:
    """
    协调代理（Coordinator/Dispatcher Pattern）
    
    功能：
    - 分析用户意图（使用 LLM）
    - 选择最合适的子代理
    - 路由任务到选定的代理
    - 聚合结果
    
    使用场景：
    - 用户请求不明确，需要智能路由
    - 多个专业代理可用，需要选择最合适的
    - 需要根据上下文动态选择代理
    """
    
    def __init__(
        self,
        google_service: Any,
        agent_registry: Any,
        model: str = "gemini-2.0-flash-exp"
    ):
        """
        初始化协调代理
        
        Args:
            google_service: GoogleService 实例（用于 LLM 调用）
            agent_registry: AgentRegistryService 实例
            model: 使用的模型
        """
        self.google_service = google_service
        self.agent_registry = agent_registry
        self.model = model
        
        logger.info(f"[CoordinatorAgent] Initialized (model: {model})")
    
    async def coordinate(
        self,
        user_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        协调任务执行
        
        流程：
        1. 分析用户意图
        2. 获取可用代理列表
        3. 选择最合适的代理
        4. 路由任务到选定的代理
        5. 返回结果
        
        Args:
            user_id: 用户 ID
            task: 任务描述
            context: 上下文信息（可选）
            
        Returns:
            执行结果
        """
        logger.info(f"[CoordinatorAgent] Coordinating task: {task[:50]}...")
        
        # 1. 分析用户意图
        intent = await self._analyze_intent(task, context)
        logger.info(f"[CoordinatorAgent] Intent analyzed: {intent.intent_type} (confidence: {intent.confidence:.2f})")
        
        # 2. 获取可用代理列表
        available_agents = await self.agent_registry.list_agents(user_id=user_id)
        logger.info(f"[CoordinatorAgent] Found {len(available_agents)} available agents")
        
        # 3. 选择最合适的代理
        selected_agent = self._select_agent(intent, available_agents)
        
        if not selected_agent:
            return {
                "success": False,
                "error": "No suitable agent found for the task",
                "intent": intent.intent_type,
                "required_capabilities": intent.required_capabilities
            }
        
        logger.info(f"[CoordinatorAgent] Selected agent: {selected_agent.get('name', selected_agent.get('id'))}")
        
        # 4. 路由任务到选定的代理
        # 注意：这里需要调用实际的代理执行逻辑
        # 简化实现：返回路由信息
        return {
            "success": True,
            "intent": intent.intent_type,
            "selected_agent": {
                "id": selected_agent.get("id"),
                "name": selected_agent.get("name"),
                "type": selected_agent.get("agentType")
            },
            "task": task,
            "context": context,
            "message": f"Task routed to agent: {selected_agent.get('name')}"
        }
    
    async def _analyze_intent(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Intent:
        """
        分析用户意图（使用 LLM）
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            意图分析结果
        """
        prompt = f"""分析以下用户任务的意图，并确定需要哪些能力和哪个代理最适合处理。

任务：{task}

{context if context else ''}

请分析：
1. 任务的主要意图类型（如：数据分析、图像处理、文本生成、代码执行等）
2. 完成任务所需的能力列表
3. 建议使用的代理类型或 ID

请以 JSON 格式返回：
{{
    "intent_type": "意图类型",
    "confidence": 0.0-1.0,
    "required_capabilities": ["能力1", "能力2"],
    "suggested_agent_id": "代理ID（如果有）",
    "context": {{"额外信息": "值"}}
}}
"""
        
        try:
            response = await self.google_service.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model
            )
            
            # 提取文本响应
            text = response.get("text", "")
            if not text:
                # 尝试从 candidates 中提取
                if "candidates" in response and len(response["candidates"]) > 0:
                    candidate = response["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        texts = [
                            part.get("text", "")
                            for part in candidate["content"]["parts"]
                            if "text" in part
                        ]
                        text = " ".join(texts)
            
            # 解析 JSON
            import json
            import re
            
            # 尝试提取 JSON 块
            json_match = re.search(r'\{[^{}]*"intent_type"[^{}]*\}', text, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group())
            else:
                # 回退：手动解析
                intent_data = {
                    "intent_type": "general",
                    "confidence": 0.5,
                    "required_capabilities": [],
                    "suggested_agent_id": None,
                    "context": {}
                }
            
            return Intent(
                intent_type=intent_data.get("intent_type", "general"),
                confidence=float(intent_data.get("confidence", 0.5)),
                required_capabilities=intent_data.get("required_capabilities", []),
                suggested_agent_id=intent_data.get("suggested_agent_id"),
                context=intent_data.get("context", {})
            )
            
        except Exception as e:
            logger.error(f"[CoordinatorAgent] Error analyzing intent: {e}", exc_info=True)
            # 回退：返回默认意图
            return Intent(
                intent_type="general",
                confidence=0.3,
                required_capabilities=[],
                suggested_agent_id=None,
                context={}
            )
    
    def _select_agent(
        self,
        intent: Intent,
        available_agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        选择最合适的代理
        
        策略：
        1. 如果 intent 中有 suggested_agent_id，优先使用
        2. 根据 required_capabilities 匹配
        3. 根据 agent_type 匹配
        4. 选择第一个可用代理（回退）
        
        Args:
            intent: 意图分析结果
            available_agents: 可用代理列表
            
        Returns:
            选定的代理，如果未找到则返回 None
        """
        if not available_agents:
            return None
        
        # 1. 优先使用 suggested_agent_id
        if intent.suggested_agent_id:
            for agent in available_agents:
                if agent.get("id") == intent.suggested_agent_id:
                    logger.info(f"[CoordinatorAgent] Using suggested agent: {intent.suggested_agent_id}")
                    return agent
        
        # 2. 根据能力匹配
        if intent.required_capabilities:
            best_match = None
            best_score = 0
            
            for agent in available_agents:
                # 从 agent_card 中提取能力
                agent_card = agent.get("agentCard", {})
                agent_capabilities = agent_card.get("capabilities", [])
                
                # 计算匹配分数
                score = self._calculate_capability_score(
                    intent.required_capabilities,
                    agent_capabilities
                )
                
                if score > best_score:
                    best_score = score
                    best_match = agent
            
            if best_match and best_score > 0.3:  # 阈值
                logger.info(f"[CoordinatorAgent] Selected agent by capability match (score: {best_score:.2f})")
                return best_match
        
        # 3. 根据意图类型匹配代理类型
        intent_to_type = {
            "数据分析": "data-analysis",
            "图像处理": "image-processing",
            "文本生成": "text-generation",
            "代码执行": "code-execution"
        }
        
        agent_type = intent_to_type.get(intent.intent_type)
        if agent_type:
            for agent in available_agents:
                if agent.get("agentType") == agent_type:
                    logger.info(f"[CoordinatorAgent] Selected agent by type: {agent_type}")
                    return agent
        
        # 4. 回退：选择第一个可用代理
        logger.warning("[CoordinatorAgent] No specific match found, using first available agent")
        return available_agents[0] if available_agents else None
    
    def _calculate_capability_score(
        self,
        required: List[str],
        available: List[str]
    ) -> float:
        """
        计算能力匹配分数
        
        Args:
            required: 所需能力列表
            available: 可用能力列表
            
        Returns:
            匹配分数（0-1）
        """
        if not required:
            return 0.5  # 如果没有要求，给中等分数
        
        if not available:
            return 0.0
        
        # 计算交集
        required_lower = [c.lower() for c in required]
        available_lower = [c.lower() for c in available]
        
        matches = sum(1 for r in required_lower if any(r in a or a in r for a in available_lower))
        
        return matches / len(required) if required else 0.0
