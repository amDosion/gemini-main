"""
Base Agent Executor - 共享的智能体执行逻辑

Eliminates the duplicated `_execute_agent` methods across:
- orchestrator.py
- sequential_agent.py
- parallel_agent.py
- coordinator_agent.py

Each of those had an identical pattern:
  1. Look up agent info from registry
  2. Check if agent has tools configured
  3. Create AgentWithTools and execute (or fall back to a stub)

This module provides a single, correct implementation.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BaseAgentExecutor:
    """
    Shared agent execution logic.

    Usage:
        executor = BaseAgentExecutor(
            agent_registry=registry,
            google_service=service,
            tool_registry=tool_registry
        )
        result = await executor.execute_agent(
            user_id="user1",
            agent_id="agent1",
            agent_name="MyAgent",
            input_data="Analyze this data"
        )
    """

    def __init__(
        self,
        agent_registry: Any,
        google_service: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        model: str = "gemini-2.0-flash-exp"
    ):
        self.agent_registry = agent_registry
        self.google_service = google_service
        self.tool_registry = tool_registry
        self.model = model

    async def execute_agent(
        self,
        user_id: str,
        agent_id: str,
        agent_name: str,
        input_data: Any,
        available_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an agent with proper LLM integration.

        Unlike the old stub implementations, this method:
        - Always attempts real LLM execution when google_service is available
        - Returns structured results with agent_id, input, and output
        - Only falls back to LLM-only execution (no tools) when tool_registry is unavailable

        Args:
            user_id: User ID
            agent_id: Agent ID
            agent_name: Agent display name
            input_data: Input data (task description or structured data)
            available_tools: Tool names to use (overrides agent config)

        Returns:
            Execution result dict

        Raises:
            ValueError: If agent not found
            RuntimeError: If no google_service and no fallback available
        """
        # Look up agent info
        agent_info = await self.agent_registry.get_agent(user_id, agent_id)
        if not agent_info:
            raise ValueError(f"Agent not found: {agent_id}")

        # Determine tools to use
        agent_tools = available_tools
        mcp_session_id = None

        if not agent_tools and agent_info.get("tools"):
            tool_config = agent_info["tools"]
            agent_tools = tool_config.get("tool_names")
            mcp_session_id = tool_config.get("mcp_session_id")

        task_str = str(input_data)

        # Path 1: Agent with tools (full capability)
        if agent_tools and self.tool_registry and self.google_service:
            return await self._execute_with_tools(
                agent_name=agent_name,
                agent_id=agent_id,
                task=task_str,
                agent_tools=agent_tools,
                mcp_session_id=mcp_session_id,
            )

        # Path 2: Agent with LLM only (no tools)
        if self.google_service:
            return await self._execute_with_llm(
                agent_name=agent_name,
                agent_id=agent_id,
                task=task_str,
                agent_info=agent_info,
            )

        # Path 3: No LLM available - cannot execute
        raise RuntimeError(
            f"Cannot execute agent '{agent_name}': no LLM service available. "
            "Ensure a Google API key is configured."
        )

    async def _execute_with_tools(
        self,
        agent_name: str,
        agent_id: str,
        task: str,
        agent_tools: List[str],
        mcp_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute agent with tool-calling loop."""
        try:
            # Load MCP tools if needed
            if mcp_session_id:
                await self.tool_registry.load_mcp_tools(mcp_session_id)

            from .agent_with_tools import AgentWithTools

            agent_with_tools = AgentWithTools(
                name=agent_name,
                google_service=self.google_service,
                tool_registry=self.tool_registry,
                model=self.model,
            )

            result = await agent_with_tools.execute_with_tools(
                task=task,
                available_tools=agent_tools,
            )

            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "input": task,
                "output": result.get("result"),
                "tool_calls": result.get("tool_calls", []),
                "iterations": result.get("iterations", 1),
            }

        except Exception as e:
            logger.error(
                f"[BaseAgentExecutor] Tool execution failed for {agent_name}: {e}",
                exc_info=True,
            )
            # Fall back to LLM-only
            return await self._execute_with_llm(
                agent_name=agent_name,
                agent_id=agent_id,
                task=task,
                agent_info={},
            )

    async def _execute_with_llm(
        self,
        agent_name: str,
        agent_id: str,
        task: str,
        agent_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute agent using LLM directly (no tools)."""
        try:
            system_prompt = agent_info.get("systemPrompt") or agent_info.get("system_prompt", "")
            prompt = task
            if system_prompt:
                prompt = f"System: {system_prompt}\n\nTask: {task}"

            response = await self.google_service.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
            )

            # Extract text from response
            output = self._extract_text(response)

            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "input": task,
                "output": output,
            }

        except Exception as e:
            logger.error(
                f"[BaseAgentExecutor] LLM execution failed for {agent_name}: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Agent '{agent_name}' execution failed: {e}")

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text content from various LLM response formats."""
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            if "text" in response:
                return response["text"]
            if "content" in response:
                return response["content"]
            if "message" in response and "content" in response["message"]:
                return response["message"]["content"]
            if "candidates" in response and len(response["candidates"]) > 0:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    texts = [
                        part.get("text", "")
                        for part in candidate["content"]["parts"]
                        if "text" in part
                    ]
                    if texts:
                        return " ".join(texts)

        return str(response)
