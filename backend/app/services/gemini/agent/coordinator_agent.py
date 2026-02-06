"""
Coordinator Agent - 协调代理（Coordinator/Dispatcher Pattern）

参考 Google ADK 的 Coordinator/Dispatcher 模式：
- 分析用户意图
- 选择最合适的子代理
- 路由任务到选定的代理
- 实际执行并返回结果
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .base_agent_executor import BaseAgentExecutor

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """用户意图分析结果"""
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
    - 实际执行并返回结果（不再只返回路由信息）
    """

    def __init__(
        self,
        google_service: Any,
        agent_registry: Any,
        model: str = "gemini-2.0-flash-exp",
        tool_registry: Optional[Any] = None,
    ):
        self.google_service = google_service
        self.agent_registry = agent_registry
        self.model = model

        # Shared executor for actual task execution
        self._executor = BaseAgentExecutor(
            agent_registry=agent_registry,
            google_service=google_service,
            tool_registry=tool_registry,
        )

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
        4. 实际执行任务（不再只返回路由信息）
        5. 返回结果
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

        agent_id = selected_agent.get("id")
        agent_name = selected_agent.get("name", agent_id)
        logger.info(f"[CoordinatorAgent] Selected agent: {agent_name}")

        # 4. Actually execute the task (FIX: old code just returned routing info)
        try:
            result = await self._executor.execute_agent(
                user_id=user_id,
                agent_id=agent_id,
                agent_name=agent_name,
                input_data=task,
            )

            return {
                "success": True,
                "intent": intent.intent_type,
                "selected_agent": {
                    "id": agent_id,
                    "name": agent_name,
                    "type": selected_agent.get("agentType")
                },
                "result": result.get("output", result),
                "tool_calls": result.get("tool_calls", []),
            }

        except Exception as e:
            logger.error(f"[CoordinatorAgent] Execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "intent": intent.intent_type,
                "selected_agent": {
                    "id": agent_id,
                    "name": agent_name,
                },
                "error": str(e),
            }

    async def _analyze_intent(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Intent:
        """分析用户意图（使用 LLM）"""
        if not self.google_service:
            return Intent(intent_type="general", confidence=0.3)

        prompt = f"""分析以下用户任务的意图，并确定需要哪些能力和哪个代理最适合处理。

任务：{task}

{context if context else ''}

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

            text = BaseAgentExecutor._extract_text(response)

            import json
            import re

            json_match = re.search(r'\{[^{}]*"intent_type"[^{}]*\}', text, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group())
            else:
                intent_data = {
                    "intent_type": "general",
                    "confidence": 0.5,
                    "required_capabilities": [],
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
            return Intent(intent_type="general", confidence=0.3)

    def _select_agent(
        self,
        intent: Intent,
        available_agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """选择最合适的代理"""
        if not available_agents:
            return None

        # 1. 优先使用 suggested_agent_id
        if intent.suggested_agent_id:
            for agent in available_agents:
                if agent.get("id") == intent.suggested_agent_id:
                    return agent

        # 2. 根据能力匹配
        if intent.required_capabilities:
            best_match = None
            best_score = 0

            for agent in available_agents:
                agent_card = agent.get("agentCard", {})
                agent_capabilities = agent_card.get("capabilities", [])

                score = self._calculate_capability_score(
                    intent.required_capabilities,
                    agent_capabilities
                )

                if score > best_score:
                    best_score = score
                    best_match = agent

            if best_match and best_score > 0.3:
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
                    return agent

        # 4. 回退：选择第一个可用代理
        logger.warning("[CoordinatorAgent] No specific match found, using first available agent")
        return available_agents[0]

    def _calculate_capability_score(
        self,
        required: List[str],
        available: List[str]
    ) -> float:
        """计算能力匹配分数"""
        if not required:
            return 0.5
        if not available:
            return 0.0

        required_lower = [c.lower() for c in required]
        available_lower = [c.lower() for c in available]

        matches = sum(1 for r in required_lower if any(r in a or a in r for a in available_lower))
        return matches / len(required)
