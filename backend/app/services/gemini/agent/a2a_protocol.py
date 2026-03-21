"""
A2A Protocol Handler - A2A 协议处理器

提供：
- 消息格式解析（A2A JSON Schema）
- 任务生命周期管理（submitted -> working -> completed）
- 事件队列处理
- 协议转换（A2A <-> Agent 格式）
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ValidationError, model_validator

from ....models.db_models import A2ATask, A2AEvent

logger = logging.getLogger(__name__)


VALID_TASK_STATUSES = {
    "submitted",
    "working",
    "completed",
    "failed",
    "cancelled",
}


class A2AMessagePart(BaseModel):
    """A2A 消息片段。"""

    text: Optional[str] = None
    mime_type: Optional[str] = None
    data: Optional[Any] = None

    @model_validator(mode="after")
    def validate_payload(self) -> "A2AMessagePart":
        if not str(self.text or "").strip() and self.data is None:
            raise ValueError("message part requires text or data")
        return self


class A2AInputMessage(BaseModel):
    """A2A 输入消息结构。"""

    role: str = "user"
    text: Optional[str] = None
    parts: List[A2AMessagePart] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_input_message(self) -> "A2AInputMessage":
        has_text = bool(str(self.text or "").strip())
        has_parts = len(self.parts) > 0
        if not has_text and not has_parts:
            raise ValueError("message requires text or parts")
        return self


class A2ATaskRef(BaseModel):
    """A2A 任务引用。"""

    id: str = Field(min_length=1)
    context_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class A2AEnvelope(BaseModel):
    """A2A 消息信封（兼容简化字段）。"""

    task: Optional[A2ATaskRef] = None
    task_id: Optional[str] = None
    context_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    input: Optional[str] = None
    message: Optional[A2AInputMessage] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_envelope(self) -> "A2AEnvelope":
        task_id = str((self.task.id if self.task else self.task_id) or "").strip()
        if not task_id:
            raise ValueError("task_id is required")

        if self.task and self.task.context_id and not self.context_id:
            self.context_id = self.task.context_id

        has_input = bool(str(self.input or "").strip())
        has_message = self.message is not None
        if not has_input and not has_message:
            raise ValueError("either input or message is required")
        return self


class A2AProtocolHandler:
    """
    A2A 协议处理器

    负责：
    - 消息格式解析
    - 任务生命周期管理
    - 事件队列处理
    - 协议转换
    """

    def __init__(self, db: Session):
        """
        初始化 A2A 协议处理器

        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[A2AProtocolHandler] Initialized")

    async def create_task(
        self,
        user_id: str,
        agent_id: str,
        task_id: str,
        context_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建 A2A 任务

        Args:
            user_id: 用户 ID
            agent_id: 智能体 ID
            task_id: A2A 任务 ID
            context_id: A2A 上下文 ID
            metadata: 任务元数据（可选）

        Returns:
            任务信息
        """
        now = int(time.time() * 1000)

        task = A2ATask(
            user_id=user_id,
            agent_id=agent_id,
            task_id=task_id,
            context_id=context_id,
            status="submitted",
            metadata_json=json.dumps(metadata) if metadata else None,
            created_at=now,
            updated_at=now
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        logger.info("[A2AProtocolHandler] Created task %s for user %s", task_id, user_id)
        return task.to_dict()

    async def update_task_status(
        self,
        user_id: str,
        task_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新任务状态

        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            status: 新状态（submitted/working/completed/failed/cancelled）
            metadata: 任务元数据（可选）

        Returns:
            是否更新成功
        """
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in VALID_TASK_STATUSES:
            raise ValueError(f"invalid A2A status: {status}")

        task = self.db.query(A2ATask).filter(
            A2ATask.task_id == task_id,
            A2ATask.user_id == user_id
        ).first()

        if task:
            task.status = normalized_status
            task.updated_at = int(time.time() * 1000)
            if metadata:
                task.metadata_json = json.dumps(metadata)
            self.db.commit()
            logger.info("[A2AProtocolHandler] Updated task %s status to %s", task_id, normalized_status)
            return True

        return False

    async def add_event(
        self,
        task_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加事件到事件队列

        Args:
            task_id: 任务 ID
            event_type: 事件类型
            event_data: 事件数据（可选）

        Returns:
            事件信息
        """
        now = int(time.time() * 1000)

        event = A2AEvent(
            task_id=task_id,
            event_type=event_type,
            event_data_json=json.dumps(event_data) if event_data else None,
            created_at=now
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        logger.info("[A2AProtocolHandler] Added event %s of type %s to task %s", event.id, event_type, task_id)
        return event.to_dict()

    async def get_task(
        self,
        user_id: str,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取任务

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            任务信息，如果不存在则返回 None
        """
        task = self.db.query(A2ATask).filter(
            A2ATask.task_id == task_id,
            A2ATask.user_id == user_id
        ).first()

        if task:
            return task.to_dict()
        return None

    async def get_events(
        self,
        task_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取任务的事件列表

        Args:
            task_id: 任务 ID
            limit: 返回结果数量限制

        Returns:
            事件列表
        """
        events = self.db.query(A2AEvent).filter(
            A2AEvent.task_id == task_id
        ).order_by(A2AEvent.created_at.asc()).limit(limit).all()

        return [event.to_dict() for event in events]

    def parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 A2A 消息格式并执行 schema 校验。

        Args:
            message: A2A 消息（JSON）

        Returns:
            规范化后的消息
        """
        if not isinstance(message, dict):
            raise ValueError("A2A message must be an object")

        try:
            envelope = A2AEnvelope.model_validate(message)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(item) for item in err.get('loc', []))}: {err.get('msg')}"
                for err in exc.errors()
            )
            raise ValueError(f"Invalid A2A message schema: {details}") from exc

        message_text = ""
        message_obj: Dict[str, Any] = {}
        if envelope.message is not None:
            message_obj = envelope.message.model_dump(exclude_none=True)
            message_text = str(envelope.message.text or "").strip()
            if not message_text:
                for part in envelope.message.parts:
                    if str(part.text or "").strip():
                        message_text = str(part.text or "").strip()
                        break

        if not message_text:
            message_text = str(envelope.input or "").strip()

        normalized_task_id = str((envelope.task.id if envelope.task else envelope.task_id) or "").strip()
        normalized_context_id = str(
            (
                envelope.context_id
                or (envelope.task.context_id if envelope.task else "")
                or ""
            )
        ).strip()

        task_payload = envelope.task.model_dump(exclude_none=True) if envelope.task else {
            "id": normalized_task_id,
            "context_id": normalized_context_id,
            "metadata": {},
        }

        return {
            "task": task_payload,
            "task_id": normalized_task_id,
            "context_id": normalized_context_id,
            "input": message_text,
            "context": envelope.context if isinstance(envelope.context, dict) else {},
            "message": message_obj or {"role": "user", "text": message_text},
            "metadata": envelope.metadata if isinstance(envelope.metadata, dict) else {},
        }

    def convert_to_agent_format(self, a2a_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 A2A 消息格式转换为 Agent 格式

        Args:
            a2a_message: A2A 消息

        Returns:
            Agent 格式消息
        """
        normalized = self.parse_message(a2a_message)
        return {
            "input": normalized.get("input", ""),
            "context": normalized.get("context", {}),
            "metadata": normalized.get("metadata", {}),
            "task_id": normalized.get("task_id", ""),
            "context_id": normalized.get("context_id", ""),
        }

    def convert_to_a2a_format(self, agent_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 Agent 响应格式转换为 A2A 格式

        Args:
            agent_response: Agent 响应

        Returns:
            A2A 格式响应
        """
        response_text = str(agent_response.get("output") or agent_response.get("text") or "").strip()
        return {
            "status": str(agent_response.get("status") or "completed"),
            "message": {
                "role": "agent",
                "text": response_text,
            },
            "output": response_text,
            "artifacts": agent_response.get("artifacts", []),
            "metadata": agent_response.get("metadata", {}),
        }
