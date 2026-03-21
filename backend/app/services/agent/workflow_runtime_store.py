"""
Workflow runtime state store abstraction.

目标：
- 统一管理工作流执行期状态（done/updated_at）与取消标记（cancel_requested）
- Redis 优先；Redis 不可用时自动回退到进程内本地存储
- 对调用方暴露一致 async 接口
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..common.redis_queue_service import GlobalRedisConnectionPool

logger = logging.getLogger(__name__)
_RUNTIME_PAYLOAD_UPDATED_AT_FIELD = "_runtime_updated_at_ms"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _decode_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if value is None:
        return ""
    return str(value)


def _decode_bool(value: Any) -> bool:
    text = _decode_text(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _lookup(raw: Dict[Any, Any], key: str) -> Any:
    if key in raw:
        return raw[key]
    key_bytes = key.encode("utf-8")
    if key_bytes in raw:
        return raw[key_bytes]
    return None


def _decode_int(value: Any) -> int:
    text = _decode_text(value).strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _decode_json_dict(value: Any) -> Optional[Dict[str, Any]]:
    text = _decode_text(value).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _clone_payload(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    try:
        return copy.deepcopy(value)
    except Exception:
        return dict(value)


def _extract_payload_updated_at(value: Optional[Dict[str, Any]]) -> int:
    if not isinstance(value, dict):
        return 0
    return max(0, _decode_int(value.get(_RUNTIME_PAYLOAD_UPDATED_AT_FIELD)))


@dataclass(frozen=True)
class WorkflowRuntimeState:
    done: bool = False
    cancel_requested: bool = False
    pause_requested: bool = False
    paused: bool = False
    checkpoint: Optional[Dict[str, Any]] = None
    updated_at: int = 0


def _is_empty_state(state: WorkflowRuntimeState) -> bool:
    return (
        not state.done
        and not state.cancel_requested
        and not state.pause_requested
        and not state.paused
        and state.checkpoint is None
        and int(state.updated_at or 0) <= 0
    )


def _merge_runtime_states(local_state: WorkflowRuntimeState, redis_state: WorkflowRuntimeState) -> WorkflowRuntimeState:
    local_updated = int(local_state.updated_at or 0)
    redis_updated = int(redis_state.updated_at or 0)

    # Redis key missing/抖动时，优先保留已有本地状态，避免 pause/cancel 被空状态覆盖。
    if _is_empty_state(redis_state) and not _is_empty_state(local_state):
        return local_state
    if _is_empty_state(local_state) and not _is_empty_state(redis_state):
        return redis_state

    if local_updated > redis_updated:
        return local_state
    if redis_updated > local_updated:
        return redis_state

    checkpoint = redis_state.checkpoint if redis_state.checkpoint is not None else local_state.checkpoint
    return WorkflowRuntimeState(
        done=bool(local_state.done or redis_state.done),
        cancel_requested=bool(local_state.cancel_requested or redis_state.cancel_requested),
        pause_requested=bool(local_state.pause_requested or redis_state.pause_requested),
        paused=bool(local_state.paused or redis_state.paused),
        checkpoint=checkpoint,
        updated_at=max(local_updated, redis_updated),
    )


class LocalWorkflowRuntimeStore:
    """进程内 fallback store。"""

    def __init__(
        self,
        shared_state: Optional[Dict[str, WorkflowRuntimeState]] = None,
        shared_payload_state: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self._state: Dict[str, WorkflowRuntimeState] = shared_state if shared_state is not None else {}
        self._payload_state: Dict[str, Dict[str, Any]] = (
            shared_payload_state if shared_payload_state is not None else {}
        )
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        lock = self._lock
        if lock is None:
            lock = asyncio.Lock()
            self._lock = lock
        return lock

    async def get_state(self, execution_id: str) -> WorkflowRuntimeState:
        async with self._get_lock():
            return self._state.get(execution_id, WorkflowRuntimeState())

    async def initialize_execution(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        state = WorkflowRuntimeState(
            done=False,
            cancel_requested=False,
            pause_requested=False,
            paused=False,
            checkpoint=None,
            updated_at=updated_at if updated_at is not None else _now_ms(),
        )
        async with self._get_lock():
            self._state[execution_id] = state
        return state

    async def touch(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        now_ms = updated_at if updated_at is not None else _now_ms()
        async with self._get_lock():
            current = self._state.get(execution_id, WorkflowRuntimeState())
            next_state = WorkflowRuntimeState(
                done=current.done,
                cancel_requested=current.cancel_requested,
                pause_requested=current.pause_requested,
                paused=current.paused,
                checkpoint=current.checkpoint,
                updated_at=now_ms,
            )
            self._state[execution_id] = next_state
            return next_state

    async def request_cancel(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        now_ms = updated_at if updated_at is not None else _now_ms()
        async with self._get_lock():
            current = self._state.get(execution_id, WorkflowRuntimeState())
            next_state = WorkflowRuntimeState(
                done=current.done,
                cancel_requested=True,
                pause_requested=current.pause_requested,
                paused=current.paused,
                checkpoint=current.checkpoint,
                updated_at=now_ms,
            )
            self._state[execution_id] = next_state
            return next_state

    async def request_pause(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        now_ms = updated_at if updated_at is not None else _now_ms()
        async with self._get_lock():
            current = self._state.get(execution_id, WorkflowRuntimeState())
            next_state = WorkflowRuntimeState(
                done=False,
                cancel_requested=current.cancel_requested,
                pause_requested=True,
                paused=current.paused,
                checkpoint=current.checkpoint,
                updated_at=now_ms,
            )
            self._state[execution_id] = next_state
            return next_state

    async def mark_paused(
        self,
        execution_id: str,
        *,
        paused: bool = True,
        checkpoint: Optional[Dict[str, Any]] = None,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        now_ms = updated_at if updated_at is not None else _now_ms()
        async with self._get_lock():
            current = self._state.get(execution_id, WorkflowRuntimeState())
            checkpoint_payload: Optional[Dict[str, Any]]
            if isinstance(checkpoint, dict):
                checkpoint_payload = dict(checkpoint)
            else:
                checkpoint_payload = current.checkpoint
            next_state = WorkflowRuntimeState(
                done=False,
                cancel_requested=current.cancel_requested,
                pause_requested=False,
                paused=bool(paused),
                checkpoint=checkpoint_payload,
                updated_at=now_ms,
            )
            self._state[execution_id] = next_state
            return next_state

    async def mark_running(
        self,
        execution_id: str,
        *,
        clear_checkpoint: bool = True,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        now_ms = updated_at if updated_at is not None else _now_ms()
        async with self._get_lock():
            current = self._state.get(execution_id, WorkflowRuntimeState())
            next_state = WorkflowRuntimeState(
                done=False,
                cancel_requested=False,
                pause_requested=False,
                paused=False,
                checkpoint=None if clear_checkpoint else current.checkpoint,
                updated_at=now_ms,
            )
            self._state[execution_id] = next_state
            return next_state

    async def mark_done(
        self,
        execution_id: str,
        *,
        done: bool = True,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        now_ms = updated_at if updated_at is not None else _now_ms()
        async with self._get_lock():
            current = self._state.get(execution_id, WorkflowRuntimeState())
            next_state = WorkflowRuntimeState(
                done=bool(done),
                cancel_requested=current.cancel_requested,
                pause_requested=current.pause_requested,
                paused=current.paused,
                checkpoint=current.checkpoint,
                updated_at=now_ms,
            )
            self._state[execution_id] = next_state
            return next_state

    async def clear(self, execution_id: str) -> None:
        async with self._get_lock():
            self._state.pop(execution_id, None)

    async def get_payload(self, payload_key: str) -> Optional[Dict[str, Any]]:
        normalized_key = str(payload_key or "").strip()
        if not normalized_key:
            return None
        async with self._get_lock():
            return _clone_payload(self._payload_state.get(normalized_key))

    async def put_payload(
        self,
        payload_key: str,
        payload: Dict[str, Any],
        *,
        updated_at: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_key = str(payload_key or "").strip()
        if not normalized_key:
            raise ValueError("payload_key is required")
        normalized_payload = _clone_payload(payload) or {}
        normalized_payload[_RUNTIME_PAYLOAD_UPDATED_AT_FIELD] = (
            updated_at if updated_at is not None else _now_ms()
        )
        async with self._get_lock():
            self._payload_state[normalized_key] = normalized_payload
            return _clone_payload(normalized_payload)

    async def delete_payload(self, payload_key: str) -> None:
        normalized_key = str(payload_key or "").strip()
        if not normalized_key:
            return
        async with self._get_lock():
            self._payload_state.pop(normalized_key, None)


class RedisWorkflowRuntimeStore:
    """
    Redis runtime store。

    说明：
    - 若 Redis 不可用，方法返回 None（由上层决定 fallback）
    - 通过 GlobalRedisConnectionPool 获取连接，避免额外独立连接池
    """

    def __init__(
        self,
        *,
        redis_client: Optional[Any] = None,
        redis_pool: Optional["GlobalRedisConnectionPool"] = None,
        key_prefix: str = "workflow:runtime",
        ttl_seconds: int = 24 * 60 * 60,
        connect_retry_seconds: float = 5.0,
    ):
        self._redis = redis_client
        self._pool = redis_pool
        if self._pool is None and redis_client is None:
            try:
                from ..common.redis_queue_service import GlobalRedisConnectionPool
                self._pool = GlobalRedisConnectionPool.get_instance()
            except Exception:
                logger.debug(
                    "[WorkflowRuntimeStore] GlobalRedisConnectionPool unavailable; redis store disabled.",
                    exc_info=True,
                )
                self._pool = None
        self._key_prefix = key_prefix.rstrip(":")
        self._ttl_seconds = max(60, int(ttl_seconds))
        self._connect_retry_seconds = max(0.5, float(connect_retry_seconds))
        self._connect_lock: Optional[asyncio.Lock] = None
        self._last_connect_attempt = 0.0

    def _key(self, execution_id: str) -> str:
        return f"{self._key_prefix}:{execution_id}"

    def _payload_key(self, payload_key: str) -> str:
        return f"{self._key_prefix}:payload:{payload_key}"

    def _decode_state(self, raw: Dict[Any, Any]) -> WorkflowRuntimeState:
        if not raw:
            return WorkflowRuntimeState()
        updated_at = _decode_int(_lookup(raw, "updated_at"))
        return WorkflowRuntimeState(
            done=_decode_bool(_lookup(raw, "done")),
            cancel_requested=_decode_bool(_lookup(raw, "cancel_requested")),
            pause_requested=_decode_bool(_lookup(raw, "pause_requested")),
            paused=_decode_bool(_lookup(raw, "paused")),
            checkpoint=_decode_json_dict(_lookup(raw, "checkpoint_json")),
            updated_at=max(0, updated_at),
        )

    async def _ensure_redis(self) -> Optional[Any]:
        if self._redis is not None:
            return self._redis
        if self._pool is None:
            return None

        now_mono = time.monotonic()
        if self._last_connect_attempt > 0 and (now_mono - self._last_connect_attempt) < self._connect_retry_seconds:
            return None

        connect_lock = self._connect_lock
        if connect_lock is None:
            connect_lock = asyncio.Lock()
            self._connect_lock = connect_lock

        async with connect_lock:
            if self._redis is not None:
                return self._redis
            now_mono = time.monotonic()
            if self._last_connect_attempt > 0 and (now_mono - self._last_connect_attempt) < self._connect_retry_seconds:
                return None
            self._last_connect_attempt = now_mono

            try:
                if not self._pool.is_initialized():
                    await self._pool.initialize()
                candidate = self._pool.get_connection()
                if candidate is None:
                    return None
                await candidate.ping()
                self._redis = candidate
                return self._redis
            except Exception as exc:
                logger.warning("[WorkflowRuntimeStore] Redis unavailable, fallback to local store: %s", exc)
                self._redis = None
                return None

    async def _hset(self, execution_id: str, mapping: Dict[str, Any]) -> Optional[WorkflowRuntimeState]:
        redis_conn = await self._ensure_redis()
        if redis_conn is None:
            return None

        key = self._key(execution_id)
        normalized_mapping = {k: _decode_text(v) for k, v in mapping.items()}
        try:
            await redis_conn.hset(key, mapping=normalized_mapping)
            await redis_conn.expire(key, self._ttl_seconds)
            raw = await redis_conn.hgetall(key)
            if not isinstance(raw, dict):
                return WorkflowRuntimeState()
            return self._decode_state(raw)
        except Exception as exc:
            logger.warning("[WorkflowRuntimeStore] Redis write failed for %s: %s", execution_id, exc)
            self._redis = None
            return None

    async def get_state(self, execution_id: str) -> Optional[WorkflowRuntimeState]:
        redis_conn = await self._ensure_redis()
        if redis_conn is None:
            return None
        try:
            raw = await redis_conn.hgetall(self._key(execution_id))
            if not isinstance(raw, dict):
                return WorkflowRuntimeState()
            return self._decode_state(raw)
        except Exception as exc:
            logger.warning("[WorkflowRuntimeStore] Redis read failed for %s: %s", execution_id, exc)
            self._redis = None
            return None

    async def initialize_execution(self, execution_id: str, *, updated_at: Optional[int] = None) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        return await self._hset(
            execution_id,
            {
                "done": "0",
                "cancel_requested": "0",
                "pause_requested": "0",
                "paused": "0",
                "checkpoint_json": "",
                "updated_at": str(now_ms),
            },
        )

    async def touch(self, execution_id: str, *, updated_at: Optional[int] = None) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        return await self._hset(execution_id, {"updated_at": str(now_ms)})

    async def request_cancel(self, execution_id: str, *, updated_at: Optional[int] = None) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        return await self._hset(
            execution_id,
            {
                "cancel_requested": "1",
                "updated_at": str(now_ms),
            },
        )

    async def request_pause(self, execution_id: str, *, updated_at: Optional[int] = None) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        return await self._hset(
            execution_id,
            {
                "pause_requested": "1",
                "updated_at": str(now_ms),
            },
        )

    async def mark_paused(
        self,
        execution_id: str,
        *,
        paused: bool = True,
        checkpoint: Optional[Dict[str, Any]] = None,
        updated_at: Optional[int] = None,
    ) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        checkpoint_json = ""
        if isinstance(checkpoint, dict):
            try:
                checkpoint_json = json.dumps(checkpoint, ensure_ascii=False)
            except Exception:
                checkpoint_json = ""
        return await self._hset(
            execution_id,
            {
                "done": "0",
                "pause_requested": "0",
                "paused": "1" if paused else "0",
                "checkpoint_json": checkpoint_json,
                "updated_at": str(now_ms),
            },
        )

    async def mark_running(
        self,
        execution_id: str,
        *,
        clear_checkpoint: bool = True,
        updated_at: Optional[int] = None,
    ) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        mapping = {
            "done": "0",
            "cancel_requested": "0",
            "pause_requested": "0",
            "paused": "0",
            "updated_at": str(now_ms),
        }
        if clear_checkpoint:
            mapping["checkpoint_json"] = ""
        return await self._hset(execution_id, mapping)

    async def mark_done(
        self,
        execution_id: str,
        *,
        done: bool = True,
        updated_at: Optional[int] = None,
    ) -> Optional[WorkflowRuntimeState]:
        now_ms = updated_at if updated_at is not None else _now_ms()
        return await self._hset(
            execution_id,
            {
                "done": "1" if done else "0",
                "updated_at": str(now_ms),
            },
        )

    async def clear(self, execution_id: str) -> bool:
        redis_conn = await self._ensure_redis()
        if redis_conn is None:
            return False
        try:
            await redis_conn.delete(self._key(execution_id))
            return True
        except Exception as exc:
            logger.warning("[WorkflowRuntimeStore] Redis clear failed for %s: %s", execution_id, exc)
            self._redis = None
            return False

    async def get_payload(self, payload_key: str) -> Optional[Dict[str, Any]]:
        normalized_key = str(payload_key or "").strip()
        if not normalized_key:
            return None
        redis_conn = await self._ensure_redis()
        if redis_conn is None:
            return None
        try:
            raw = await redis_conn.get(self._payload_key(normalized_key))
            payload = _decode_json_dict(raw)
            return _clone_payload(payload)
        except Exception as exc:
            logger.warning("[WorkflowRuntimeStore] Redis payload read failed for %s: %s", normalized_key, exc)
            self._redis = None
            return None

    async def put_payload(
        self,
        payload_key: str,
        payload: Dict[str, Any],
        *,
        updated_at: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_key = str(payload_key or "").strip()
        if not normalized_key:
            raise ValueError("payload_key is required")

        redis_conn = await self._ensure_redis()
        if redis_conn is None:
            return None

        normalized_payload = _clone_payload(payload) or {}
        normalized_payload[_RUNTIME_PAYLOAD_UPDATED_AT_FIELD] = (
            updated_at if updated_at is not None else _now_ms()
        )
        try:
            serialized = json.dumps(normalized_payload, ensure_ascii=False)
        except Exception as exc:
            raise ValueError(f"payload is not json serializable: {exc}") from exc

        redis_key = self._payload_key(normalized_key)
        try:
            await redis_conn.set(redis_key, serialized, ex=self._ttl_seconds)
            raw = await redis_conn.get(redis_key)
            decoded = _decode_json_dict(raw)
            if isinstance(decoded, dict):
                return _clone_payload(decoded)
            return _clone_payload(normalized_payload)
        except Exception as exc:
            logger.warning("[WorkflowRuntimeStore] Redis payload write failed for %s: %s", normalized_key, exc)
            self._redis = None
            return None

    async def delete_payload(self, payload_key: str) -> bool:
        normalized_key = str(payload_key or "").strip()
        if not normalized_key:
            return False
        redis_conn = await self._ensure_redis()
        if redis_conn is None:
            return False
        try:
            await redis_conn.delete(self._payload_key(normalized_key))
            return True
        except Exception as exc:
            logger.warning("[WorkflowRuntimeStore] Redis payload clear failed for %s: %s", normalized_key, exc)
            self._redis = None
            return False


class WorkflowRuntimeStore:
    """统一对外 store（Redis 优先 + Local fallback）。"""

    def __init__(
        self,
        *,
        redis_store: Optional[RedisWorkflowRuntimeStore] = None,
        local_store: Optional[LocalWorkflowRuntimeStore] = None,
    ):
        self._redis_store = redis_store if redis_store is not None else RedisWorkflowRuntimeStore()
        self._local_store = local_store if local_store is not None else LocalWorkflowRuntimeStore()

    async def get_state(self, execution_id: str) -> WorkflowRuntimeState:
        local_state = await self._local_store.get_state(execution_id)
        redis_state = await self._redis_store.get_state(execution_id)
        if redis_state is None:
            return local_state
        return _merge_runtime_states(local_state, redis_state)

    async def initialize_execution_local(
        self,
        execution_id: str,
        *,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        return await self._local_store.initialize_execution(execution_id, updated_at=updated_at)

    async def initialize_execution(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        local_state = await self._local_store.initialize_execution(execution_id, updated_at=updated_at)
        redis_state = await self._redis_store.initialize_execution(execution_id, updated_at=updated_at)
        return redis_state if redis_state is not None else local_state

    async def touch_local(
        self,
        execution_id: str,
        *,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        return await self._local_store.touch(execution_id, updated_at=updated_at)

    async def touch(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        local_state = await self._local_store.touch(execution_id, updated_at=updated_at)
        redis_state = await self._redis_store.touch(execution_id, updated_at=updated_at)
        return redis_state if redis_state is not None else local_state

    async def request_cancel(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        local_state = await self._local_store.request_cancel(execution_id, updated_at=updated_at)
        redis_state = await self._redis_store.request_cancel(execution_id, updated_at=updated_at)
        return redis_state if redis_state is not None else local_state

    async def request_pause(self, execution_id: str, *, updated_at: Optional[int] = None) -> WorkflowRuntimeState:
        local_state = await self._local_store.request_pause(execution_id, updated_at=updated_at)
        redis_state = await self._redis_store.request_pause(execution_id, updated_at=updated_at)
        return redis_state if redis_state is not None else local_state

    async def mark_paused(
        self,
        execution_id: str,
        *,
        paused: bool = True,
        checkpoint: Optional[Dict[str, Any]] = None,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        local_state = await self._local_store.mark_paused(
            execution_id,
            paused=paused,
            checkpoint=checkpoint,
            updated_at=updated_at,
        )
        redis_state = await self._redis_store.mark_paused(
            execution_id,
            paused=paused,
            checkpoint=checkpoint,
            updated_at=updated_at,
        )
        return redis_state if redis_state is not None else local_state

    async def mark_running(
        self,
        execution_id: str,
        *,
        clear_checkpoint: bool = True,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        local_state = await self._local_store.mark_running(
            execution_id,
            clear_checkpoint=clear_checkpoint,
            updated_at=updated_at,
        )
        redis_state = await self._redis_store.mark_running(
            execution_id,
            clear_checkpoint=clear_checkpoint,
            updated_at=updated_at,
        )
        return redis_state if redis_state is not None else local_state

    async def mark_done(
        self,
        execution_id: str,
        *,
        done: bool = True,
        updated_at: Optional[int] = None,
    ) -> WorkflowRuntimeState:
        local_state = await self._local_store.mark_done(execution_id, done=done, updated_at=updated_at)
        redis_state = await self._redis_store.mark_done(execution_id, done=done, updated_at=updated_at)
        return redis_state if redis_state is not None else local_state

    async def clear(self, execution_id: str) -> None:
        await self._local_store.clear(execution_id)
        await self._redis_store.clear(execution_id)

    async def is_cancel_requested(self, execution_id: str) -> bool:
        state = await self.get_state(execution_id)
        return bool(state.cancel_requested)

    async def is_done(self, execution_id: str) -> bool:
        state = await self.get_state(execution_id)
        return bool(state.done)

    async def is_pause_requested(self, execution_id: str) -> bool:
        state = await self.get_state(execution_id)
        return bool(state.pause_requested)

    async def get_checkpoint(self, execution_id: str) -> Optional[Dict[str, Any]]:
        state = await self.get_state(execution_id)
        return state.checkpoint if isinstance(state.checkpoint, dict) else None

    async def get_payload(self, payload_key: str) -> Optional[Dict[str, Any]]:
        local_payload = await self._local_store.get_payload(payload_key)
        redis_payload = await self._redis_store.get_payload(payload_key)
        if redis_payload is None:
            return local_payload
        if local_payload is None:
            return redis_payload

        local_updated_at = _extract_payload_updated_at(local_payload)
        redis_updated_at = _extract_payload_updated_at(redis_payload)
        if local_updated_at > redis_updated_at:
            return local_payload
        if redis_updated_at > local_updated_at:
            return redis_payload
        return redis_payload

    async def put_payload(
        self,
        payload_key: str,
        payload: Dict[str, Any],
        *,
        updated_at: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        local_payload = await self._local_store.put_payload(payload_key, payload, updated_at=updated_at)
        redis_payload = await self._redis_store.put_payload(payload_key, payload, updated_at=updated_at)
        return redis_payload if redis_payload is not None else local_payload

    async def delete_payload(self, payload_key: str) -> None:
        await self._local_store.delete_payload(payload_key)
        await self._redis_store.delete_payload(payload_key)


def create_workflow_runtime_store() -> WorkflowRuntimeStore:
    return WorkflowRuntimeStore()
