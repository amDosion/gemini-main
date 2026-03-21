"""
Memory Bank Service - Memory Bank 服务层

提供：
- VertexAiMemoryBankService：使用 Vertex AI Memory Bank API
- InMemoryMemoryService：内存记忆服务（用于测试）
- 记忆创建、检索、更新、删除
- 会话记忆管理
"""

import inspect
import json
import logging
import time
from typing import Dict, Any, List, Optional, Type
from sqlalchemy.orm import Session

from ....models.db_models import (
    AgentMemoryBank,
    AgentMemory,
    AgentMemorySession,
    MessageIndex,
    MessagesChat,
    MessagesImageGen,
    MessagesVideoGen,
    MessagesGeneric,
    MessagesImageChatEdit,
    MessagesImageMaskEdit,
    MessagesImageInpainting,
    MessagesImageBackgroundEdit,
    MessagesImageRecontext,
)

logger = logging.getLogger(__name__)


MESSAGE_TABLE_MODEL_MAP: Dict[str, Type[Any]] = {
    "messages_chat": MessagesChat,
    "messages_image_gen": MessagesImageGen,
    "messages_video_gen": MessagesVideoGen,
    "messages_generic": MessagesGeneric,
    "messages_image_chat_edit": MessagesImageChatEdit,
    "messages_image_mask_edit": MessagesImageMaskEdit,
    "messages_image_inpainting": MessagesImageInpainting,
    "messages_image_background_edit": MessagesImageBackgroundEdit,
    "messages_image_recontext": MessagesImageRecontext,
}


class BaseMemoryService:
    """
    Memory Service 基类

    定义 Memory Service 的通用接口
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _safe_json_loads(raw: Optional[str], default: Any = None) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default

    @staticmethod
    def _serialize_structured(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, list, dict)):
            return value
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                pass
        if hasattr(value, "dict"):
            try:
                return value.dict()
            except Exception:
                pass
        return str(value)

    def _load_session_messages(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        rows = self.db.query(MessageIndex).filter(
            MessageIndex.user_id == user_id,
            MessageIndex.session_id == session_id,
        ).order_by(MessageIndex.seq.asc()).all()

        messages: List[Dict[str, Any]] = []
        for row in rows:
            table_name = str(getattr(row, "table_name", "") or "").strip()
            model_cls = MESSAGE_TABLE_MODEL_MAP.get(table_name, MessagesGeneric)
            message_row = self.db.query(model_cls).filter(model_cls.id == row.id).first()
            if message_row is None and model_cls is not MessagesGeneric:
                message_row = self.db.query(MessagesGeneric).filter(MessagesGeneric.id == row.id).first()
            if message_row is None:
                continue

            content = str(getattr(message_row, "content", "") or "").strip()
            if not content:
                continue

            timestamp = int(
                getattr(message_row, "timestamp", None)
                or getattr(row, "timestamp", None)
                or int(time.time() * 1000)
            )
            role = str(getattr(message_row, "role", "user") or "user").strip().lower() or "user"
            messages.append(
                {
                    "id": str(getattr(message_row, "id", "") or row.id or ""),
                    "seq": int(getattr(row, "seq", 0) or 0),
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                }
            )

        return messages

    async def add_session_to_memory(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def search_memory(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def create_memory(
        self,
        user_id: str,
        content: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def get_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> bool:
        raise NotImplementedError


class InMemoryMemoryService(BaseMemoryService):
    """
    内存记忆服务 - 用于测试和开发

    将所有记忆存储在内存中，不持久化到 Vertex AI
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self._memories: Dict[str, List[Dict[str, Any]]] = {}
        logger.info("InMemoryMemoryService initialized")

    async def add_session_to_memory(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        _ = memory_bank_id
        messages = self._load_session_messages(user_id=user_id, session_id=session_id)
        if not messages:
            return []

        memory = {
            "id": f"memory_{int(time.time() * 1000)}",
            "user_id": user_id,
            "session_id": session_id,
            "content": "\n".join(f"{item['role']}: {item['content']}" for item in messages),
            "message_count": len(messages),
            "created_at": int(time.time() * 1000),
        }

        self._memories.setdefault(user_id, []).append(memory)
        logger.info("[InMemoryMemoryService] Added session %s to memory for user %s", session_id, user_id)
        return [memory]

    async def search_memory(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        _ = memory_bank_id
        if user_id not in self._memories:
            return []

        query_lower = str(query or "").lower()
        matches = [
            memory for memory in self._memories[user_id]
            if query_lower in str(memory.get("content", "")).lower()
        ]
        matches.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return matches[:limit]

    async def create_memory(
        self,
        user_id: str,
        content: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        memory_id = f"memory_{int(time.time() * 1000)}"
        memory = {
            "id": memory_id,
            "user_id": user_id,
            "memory_bank_id": memory_bank_id,
            "session_id": session_id,
            "content": content,
            "metadata": metadata or {},
            "created_at": int(time.time() * 1000),
        }
        self._memories.setdefault(user_id, []).append(memory)
        logger.info("[InMemoryMemoryService] Created memory %s for user %s", memory_id, user_id)
        return memory

    async def get_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> Optional[Dict[str, Any]]:
        for memory in self._memories.get(user_id, []):
            if memory.get("id") == memory_id:
                return memory
        return None

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> bool:
        memories = self._memories.get(user_id, [])
        for i, memory in enumerate(memories):
            if memory.get("id") == memory_id:
                del memories[i]
                logger.info("[InMemoryMemoryService] Deleted memory %s for user %s", memory_id, user_id)
                return True
        return False


class VertexAiMemoryBankService(BaseMemoryService):
    """
    Vertex AI Memory Bank 服务

    使用 Vertex AI Memory Bank API 进行持久化记忆存储。
    如果 Vertex/ADK 不可用，会自动回退到数据库搜索与存储。
    """

    def __init__(
        self,
        db: Session,
        project: Optional[str] = None,
        location: Optional[str] = None,
        agent_engine_id: Optional[str] = None
    ):
        super().__init__(db)
        self.project = project
        self.location = location or "us-central1"
        self.agent_engine_id = agent_engine_id

        self._vertexai_available = False
        self._ADKMemoryBankServiceClass = None
        self._SessionClass = None
        self._EventClass = None
        self._Content = None
        self._Part = None
        self._adk_service = None
        self._adk_service_engine_id = None

        try:
            import vertexai
            from google.adk.memory import VertexAiMemoryBankService as ADKMemoryBankService
            from google.adk.sessions import Session as ADKSessionModel
            from google.adk.events import Event as ADKEventModel
            from google.genai.types import Content, Part

            self._vertexai_available = True
            self._ADKMemoryBankServiceClass = ADKMemoryBankService
            self._SessionClass = ADKSessionModel
            self._EventClass = ADKEventModel
            self._Content = Content
            self._Part = Part

            if self.project:
                vertexai.init(project=self.project, location=self.location)
        except Exception:
            self._vertexai_available = False
            logger.warning("[VertexAiMemoryBankService] Vertex/ADK memory SDK not available", exc_info=True)

        logger.info(
            "[VertexAiMemoryBankService] Initialized (project=%s, location=%s, vertex_available=%s)",
            self.project,
            self.location,
            self._vertexai_available,
        )

    async def _touch_memory_session(
        self,
        *,
        user_id: str,
        memory_bank_id: str,
        session_id: str,
    ) -> Dict[str, Any]:
        now = int(time.time() * 1000)
        session = self.db.query(AgentMemorySession).filter(
            AgentMemorySession.user_id == user_id,
            AgentMemorySession.memory_bank_id == memory_bank_id,
            AgentMemorySession.session_id == session_id,
        ).first()

        if session:
            session.last_used_at = now
            self.db.commit()
            self.db.refresh(session)
            return session.to_dict()

        session = AgentMemorySession(
            user_id=user_id,
            memory_bank_id=memory_bank_id,
            session_id=session_id,
            created_at=now,
            last_used_at=now,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session.to_dict()

    def _resolve_memory_app_name(self, memory_bank: AgentMemoryBank, user_id: str) -> str:
        config = self._safe_json_loads(memory_bank.config_json, {}) or {}
        if isinstance(config, dict):
            app_name = str(config.get("app_name") or "").strip()
            if app_name:
                return app_name
        return f"gemini-memory-{user_id}"

    def _ensure_adk_service(self, memory_bank: AgentMemoryBank) -> Optional[Any]:
        if not self._vertexai_available or self._ADKMemoryBankServiceClass is None:
            return None

        target_engine_id = str(memory_bank.vertex_memory_bank_id or self.agent_engine_id or "").strip()
        if not target_engine_id:
            return None

        if self._adk_service and self._adk_service_engine_id == target_engine_id:
            return self._adk_service

        try:
            self._adk_service = self._ADKMemoryBankServiceClass(
                project=self.project,
                location=self.location,
                agent_engine_id=target_engine_id,
            )
            self._adk_service_engine_id = target_engine_id
            return self._adk_service
        except Exception:
            logger.warning(
                "[VertexAiMemoryBankService] Failed to initialize ADK memory service (engine_id=%s)",
                target_engine_id,
                exc_info=True,
            )
            self._adk_service = None
            self._adk_service_engine_id = None
            return None

    def _build_adk_session(
        self,
        *,
        user_id: str,
        session_id: str,
        memory_bank: AgentMemoryBank,
        messages: List[Dict[str, Any]],
    ) -> Optional[Any]:
        if not self._SessionClass or not self._EventClass or not self._Content or not self._Part:
            return None

        app_name = self._resolve_memory_app_name(memory_bank, user_id=user_id)
        events: List[Any] = []

        for item in messages:
            role = str(item.get("role") or "user").strip().lower() or "user"
            content_text = str(item.get("content") or "").strip()
            if not content_text:
                continue

            content = self._Content(
                role="user" if role in {"user", "human"} else "model",
                parts=[self._Part(text=content_text)],
            )
            event = self._EventClass(
                author="user" if role in {"user", "human"} else "model",
                invocation_id=f"memory-{session_id}-{int(item.get('seq') or 0)}",
                content=content,
                timestamp=(int(item.get("timestamp") or int(time.time() * 1000)) / 1000.0),
            )
            events.append(event)

        if not events:
            return None

        return self._SessionClass(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            events=events,
            state={},
        )

    async def add_session_to_memory(
        self,
        user_id: str,
        session_id: str,
        memory_bank_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        memory_bank = await self._get_or_create_memory_bank(user_id, memory_bank_id)
        messages = self._load_session_messages(user_id=user_id, session_id=session_id)

        if not messages:
            logger.warning("[VertexAiMemoryBankService] No messages found for session %s", session_id)
            return []

        await self._touch_memory_session(
            user_id=user_id,
            memory_bank_id=memory_bank.id,
            session_id=session_id,
        )

        indexed_by_vertex = False
        adk_service = self._ensure_adk_service(memory_bank)
        if adk_service:
            adk_session = self._build_adk_session(
                user_id=user_id,
                session_id=session_id,
                memory_bank=memory_bank,
                messages=messages,
            )
            if adk_session is not None:
                try:
                    await self._maybe_await(adk_service.add_session_to_memory(adk_session))
                    indexed_by_vertex = True
                    logger.info(
                        "[VertexAiMemoryBankService] Indexed session %s to Vertex Memory Bank %s",
                        session_id,
                        memory_bank.vertex_memory_bank_id,
                    )
                except Exception:
                    logger.error(
                        "[VertexAiMemoryBankService] ADK add_session_to_memory failed; fallback to DB snapshot",
                        exc_info=True,
                    )

        return await self._add_session_to_memory_db(
            user_id=user_id,
            session_id=session_id,
            memory_bank_id=memory_bank.id,
            messages=messages,
            indexed_by_vertex=indexed_by_vertex,
        )

    async def _add_session_to_memory_db(
        self,
        *,
        user_id: str,
        session_id: str,
        memory_bank_id: str,
        messages: List[Dict[str, Any]],
        indexed_by_vertex: bool,
    ) -> List[Dict[str, Any]]:
        now = int(time.time() * 1000)
        content = "\n".join(f"{item['role']}: {item['content']}" for item in messages)

        existing = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.memory_bank_id == memory_bank_id,
            AgentMemory.session_id == session_id,
        ).order_by(AgentMemory.created_at.desc()).first()

        metadata = {
            "source": "vertex+db" if indexed_by_vertex else "db",
            "message_count": len(messages),
            "session_id": session_id,
        }

        if existing:
            existing.content = content
            existing.metadata_json = json.dumps(metadata, ensure_ascii=False)
            existing.updated_at = now
            self.db.commit()
            self.db.refresh(existing)
            return [existing.to_dict()]

        memory = AgentMemory(
            user_id=user_id,
            memory_bank_id=memory_bank_id,
            session_id=session_id,
            content=content,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return [memory.to_dict()]

    def _extract_memory_entry_text(self, entry: Any) -> str:
        payload = self._serialize_structured(entry) or {}
        if not isinstance(payload, dict):
            return str(payload or "").strip()

        content = payload.get("content")
        if isinstance(content, dict):
            parts = content.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict):
                        text = str(part.get("text") or "").strip()
                        if text:
                            return text

        direct_text = str(payload.get("text") or "").strip()
        if direct_text:
            return direct_text

        return ""

    def _parse_adk_search_results(self, raw_response: Any, limit: int) -> List[Dict[str, Any]]:
        payload = self._serialize_structured(raw_response) or {}
        if not isinstance(payload, dict):
            return []

        memories = payload.get("memories")
        if not isinstance(memories, list):
            return []

        results: List[Dict[str, Any]] = []
        for item in memories:
            text = self._extract_memory_entry_text(item)
            if not text:
                continue
            item_payload = self._serialize_structured(item) or {}
            if not isinstance(item_payload, dict):
                item_payload = {"raw": str(item)}
            results.append(
                {
                    "content": text,
                    "source": "vertex",
                    "memory": item_payload,
                }
            )
            if len(results) >= limit:
                break

        return results

    async def search_memory(
        self,
        user_id: str,
        query: str,
        memory_bank_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        memory_bank = await self._get_or_create_memory_bank(user_id, memory_bank_id)

        adk_service = self._ensure_adk_service(memory_bank)
        if adk_service:
            try:
                raw_response = await self._maybe_await(
                    adk_service.search_memory(
                        app_name=self._resolve_memory_app_name(memory_bank, user_id=user_id),
                        user_id=user_id,
                        query=query,
                    )
                )
                parsed = self._parse_adk_search_results(raw_response, limit=limit)
                if parsed:
                    return parsed
            except Exception:
                logger.error("[VertexAiMemoryBankService] Error searching vertex memory", exc_info=True)

        return await self._search_memory_db(user_id, query, memory_bank.id, limit)

    async def _search_memory_db(
        self,
        user_id: str,
        query: str,
        memory_bank_id: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        memories = self.db.query(AgentMemory).filter(
            AgentMemory.user_id == user_id,
            AgentMemory.memory_bank_id == memory_bank_id,
            AgentMemory.content.ilike(f"%{query}%"),
        ).order_by(AgentMemory.created_at.desc()).limit(limit).all()

        return [memory.to_dict() for memory in memories]

    async def create_memory(
        self,
        user_id: str,
        content: str,
        memory_bank_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        memory_bank = await self._get_or_create_memory_bank(user_id, memory_bank_id)

        now = int(time.time() * 1000)
        memory = AgentMemory(
            user_id=user_id,
            memory_bank_id=memory_bank.id,
            session_id=session_id,
            content=content,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False) if metadata is not None else None,
            created_at=now,
            updated_at=now,
        )

        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)

        logger.info("[VertexAiMemoryBankService] Created memory %s for user %s", memory.id, user_id)
        return memory.to_dict()

    async def get_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> Optional[Dict[str, Any]]:
        memory = self.db.query(AgentMemory).filter(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
        ).first()

        if memory:
            return memory.to_dict()
        return None

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str
    ) -> bool:
        memory = self.db.query(AgentMemory).filter(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
        ).first()

        if memory:
            self.db.delete(memory)
            self.db.commit()
            logger.info("[VertexAiMemoryBankService] Deleted memory %s for user %s", memory_id, user_id)
            return True

        return False

    async def _get_or_create_memory_bank(
        self,
        user_id: str,
        memory_bank_id: Optional[str] = None
    ) -> AgentMemoryBank:
        if memory_bank_id:
            memory_bank = self.db.query(AgentMemoryBank).filter(
                AgentMemoryBank.id == memory_bank_id,
                AgentMemoryBank.user_id == user_id,
            ).first()
            if memory_bank:
                return memory_bank

        existing = self.db.query(AgentMemoryBank).filter(
            AgentMemoryBank.user_id == user_id,
        ).order_by(AgentMemoryBank.updated_at.desc()).first()
        if existing:
            return existing

        now = int(time.time() * 1000)
        app_name = f"gemini-memory-{user_id}"
        config = {"app_name": app_name}

        memory_bank = AgentMemoryBank(
            user_id=user_id,
            name=f"Memory Bank {now}",
            vertex_memory_bank_id=self.agent_engine_id,
            config_json=json.dumps(config, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )

        self.db.add(memory_bank)
        self.db.commit()
        self.db.refresh(memory_bank)

        logger.info("[VertexAiMemoryBankService] Created memory bank %s for user %s", memory_bank.id, user_id)
        return memory_bank
