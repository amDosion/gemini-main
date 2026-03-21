"""
ADK Agent - ADK 智能体封装

提供：
- LlmAgent 封装
- Agent 初始化（__init__、set_up）
- 查询方法（query、stream_query、bidi_stream_query）
- 操作注册（register_operations）
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Iterator, AsyncIterator
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ADKAgent:
    """
    ADK 智能体封装
    
    负责：
    - Agent 初始化和配置
    - 查询方法实现
    - 操作注册
    """
    
    def __init__(
        self,
        db: Session,
        model: str = "gemini-2.5-flash",
        name: str = "ADK Agent",
        instruction: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ):
        """
        初始化 ADK 智能体
        
        Args:
            db: 数据库会话
            model: 模型名称
            name: 智能体名称
            instruction: 系统指令（可选）
            tools: 工具列表（可选）
        """
        self.db = db
        self.model = model
        self.name = name
        self.instruction = instruction
        self.tools = tools or []
        self._adk_agent = None
        self._adk_app = None
        
        try:
            from google.adk.agents import LlmAgent as ADKLlmAgent
            from google.adk.apps import App as ADKApp

            self._adk_available = True
            self._adk_agent = ADKLlmAgent(
                model=model,
                name=name,
                instruction=instruction or "You are a helpful assistant.",
                tools=self._convert_tools(self.tools),
            )
            self._adk_app = ADKApp(
                name=name,
                root_agent=self._adk_agent,
            )
        except Exception:
            self._adk_available = False
            logger.warning("[ADKAgent] ADK SDK not available, strict fail-closed mode enabled", exc_info=True)
        
        logger.info("[ADKAgent] Initialized name=%s model=%s adk=%s", name, model, self._adk_available)

    @property
    def is_available(self) -> bool:
        return bool(self._adk_available and self._adk_agent is not None)

    def get_adk_agent(self) -> Any:
        return self._adk_agent

    def get_adk_app(self) -> Any:
        return self._adk_app
    
    def _convert_tools(self, tools: List[Any]) -> List[Any]:
        """
        转换工具格式
        
        Args:
            tools: 工具列表（字典格式）
            
        Returns:
            ADK 工具列表
        """
        converted: List[Any] = []
        for tool in tools or []:
            if callable(tool):
                converted.append(tool)
                continue
            if isinstance(tool, dict):
                fn = tool.get("callable") or tool.get("function")
                if callable(fn):
                    converted.append(fn)
                    continue
            logger.warning("[ADKAgent] Skip unsupported tool definition: %s", type(tool).__name__)
        return converted
    
    def set_up(self):
        """
        设置智能体（重初始化）
        
        在部署时调用，用于加载模型、数据库连接等
        """
        logger.info(f"[ADKAgent] Setting up agent: {self.name}")
        # 实际应该在这里进行重初始化

    @staticmethod
    def _runtime_unavailable_error() -> Dict[str, Any]:
        return {
            "type": "error",
            "error_code": "ADK_RUNTIME_UNAVAILABLE",
            "error": "ADK runtime is unavailable for this agent.",
            "stage": "agent_query",
            "hint": "Install and configure google.adk SDK before running ADKAgent.",
            "retryable": False,
            "is_final": True,
        }
    
    def query(self, input_data: str) -> Dict[str, Any]:
        """
        标准查询（同步）
        
        Args:
            input_data: 输入数据
            
        Returns:
            完整响应
        """
        if not self.is_available:
            raise RuntimeError(self._runtime_unavailable_error()["error"])

        async def _run_query() -> Dict[str, Any]:
            from .adk_runner import ADKRunner

            runner = ADKRunner(
                db=self.db,
                agent_id=f"inline-{self.name}",
                app_name="adk-agent-inline",
                adk_agent=self._adk_agent,
            )
            response = await runner.run_once(
                user_id="inline-user",
                session_id=f"inline-{uuid.uuid4().hex[:12]}",
                input_data=str(input_data or ""),
            )
            return {
                "output": str(response.get("text") or ""),
                "usage": response.get("usage") or {},
                "event_count": int(response.get("event_count") or 0),
                "response_signature": str(response.get("response_signature") or ""),
                "action_signature": str(response.get("action_signature") or ""),
            }

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            logger.warning("[ADKAgent] query() called inside running loop; fail-closed")
            raise RuntimeError("ADKAgent.query cannot run inside an active event loop; use async runner path.")
        return asyncio.run(_run_query())
    
    def stream_query(self, input_data: str) -> Iterator[Dict[str, Any]]:
        """
        服务器端流式查询
        
        Args:
            input_data: 输入数据
            
        Yields:
            增量响应块
        """
        if not self.is_available:
            yield self._runtime_unavailable_error()
            return

        try:
            response = self.query(input_data)
        except Exception as exc:
            yield {
                "type": "error",
                "error_code": "ADK_RUN_FAILED",
                "error": str(exc),
                "stage": "stream_query",
                "retryable": False,
                "is_final": True,
            }
            return
        text = str(response.get("output") or "").strip()
        if text:
            yield {
                "type": "chunk",
                "chunk": text,
                "response_signature": str(response.get("response_signature") or ""),
                "action_signature": str(response.get("action_signature") or ""),
            }
        yield {
            "status": "completed",
            "response_signature": str(response.get("response_signature") or ""),
            "action_signature": str(response.get("action_signature") or ""),
        }
    
    async def bidi_stream_query(
        self,
        queue: asyncio.Queue
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        双向流式查询
        
        Args:
            queue: 消息队列
            
        Yields:
            响应块
        """
        logger.info(f"[ADKAgent] Bidi stream started for agent: {self.name}")
        
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                user_input = message.get("input", "")
                
                if user_input.lower() in ("exit", "quit"):
                    yield {"output": "Goodbye!"}
                    break

                if self.is_available:
                    yield {"output": self.query(user_input).get("output", "")}
                else:
                    yield self._runtime_unavailable_error()
                    break

            except asyncio.TimeoutError:
                yield {"type": "heartbeat"}
            except Exception as e:
                logger.error(f"[ADKAgent] Error in bidi stream: {e}", exc_info=True)
                yield {"error": str(e)}
                break
    
    def register_operations(self):
        """
        注册操作
        
        定义智能体支持的操作（query、stream_query、bidi_stream_query）
        """
        logger.info(f"[ADKAgent] Registering operations for agent: {self.name}")
        # 实际应该注册操作到 Agent Engine
