"""ADK artifact/session helpers backed by WorkflowRuntimeStore."""

from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .workflow_runtime_store import WorkflowRuntimeStore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_artifact_key(value: Any) -> str:
    return _norm_text(value)


def _coerce_version(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("artifact_version must be >= 1")
    if isinstance(value, (int, float)):
        version = int(value)
    else:
        text = _norm_text(value)
        if not text:
            raise ValueError("artifact_version is required")
        try:
            version = int(float(text))
        except Exception as exc:
            raise ValueError("artifact_version must be >= 1") from exc
    if version <= 0:
        raise ValueError("artifact_version must be >= 1")
    return version


def _copy_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    try:
        return copy.deepcopy(value)
    except Exception:
        return dict(value)


def _copy_list(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return []
    try:
        return copy.deepcopy(value)
    except Exception:
        return list(value)


def _safe_artifact_key_segment(value: str) -> str:
    text = _norm_artifact_key(value).lower()
    if not text:
        return "artifact"
    return text.replace("/", "__")


def _artifact_ref_token(*, artifact_key: str, artifact_version: int) -> str:
    return f"{artifact_key}@{int(artifact_version)}"


class ADKArtifactServiceError(Exception):
    """Base artifact service error."""


class ADKArtifactSessionError(ADKArtifactServiceError):
    """Session resolution/binding error."""


class ADKArtifactBindingError(ADKArtifactServiceError):
    """Artifact binding/authorization error."""


class ADKArtifactNotFoundError(ADKArtifactServiceError):
    """Artifact record is missing."""


class ADKArtifactLineageError(ADKArtifactServiceError):
    """Artifact lineage chain is missing/inconsistent."""


class ADKArtifactService:
    """Persist and query sheet-stage sessions/artifacts on top of runtime store."""

    def __init__(self, *, runtime_store: WorkflowRuntimeStore, namespace: str = "sheet-stage"):
        self._runtime_store = runtime_store
        self._namespace = _norm_text(namespace).rstrip(":") or "sheet-stage"

    def build_session_id(self) -> str:
        return f"sheet-stage-{uuid.uuid4().hex[:16]}"

    def build_session_key(self, session_id: str) -> str:
        normalized_session_id = _norm_text(session_id)
        return f"{self._namespace}:session:{normalized_session_id}"

    def build_invocation_key(self, invocation_id: str) -> str:
        normalized_invocation_id = _norm_text(invocation_id)
        return f"{self._namespace}:invocation:{normalized_invocation_id}"

    def build_artifact_record_key(self, *, session_id: str, artifact_key: str, artifact_version: int) -> str:
        normalized_session_id = _norm_text(session_id)
        normalized_artifact_key = _safe_artifact_key_segment(artifact_key)
        normalized_version = max(1, int(artifact_version))
        return (
            f"{self._namespace}:artifact:"
            f"{normalized_session_id}:{normalized_artifact_key}:{normalized_version}"
        )

    async def load_session(self, *, session_id: str) -> Optional[Dict[str, Any]]:
        payload = await self._runtime_store.get_payload(self.build_session_key(session_id))
        if not isinstance(payload, dict):
            return None
        return _copy_dict(payload)

    async def save_session(self, *, session_id: str, session_state: Dict[str, Any], updated_at_ms: Optional[int] = None) -> Dict[str, Any]:
        payload = _copy_dict(session_state)
        payload["session_id"] = _norm_text(session_id)
        payload["updated_at_ms"] = int(updated_at_ms if updated_at_ms is not None else _now_ms())
        stored = await self._runtime_store.put_payload(
            self.build_session_key(session_id),
            payload,
            updated_at=payload["updated_at_ms"],
        )
        return _copy_dict(stored if isinstance(stored, dict) else payload)

    async def resolve_sheet_stage_session(
        self,
        *,
        requested_session_id: Optional[str],
        user_id: str,
        stage: str,
        invocation_id: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        normalized_stage = _norm_text(stage).lower()
        normalized_user_id = _norm_text(user_id)
        normalized_session_id = _norm_text(requested_session_id)

        if not normalized_session_id:
            if normalized_stage != "ingest":
                raise ADKArtifactSessionError("session_id is required for non-ingest stages")
            normalized_session_id = self.build_session_id()

        session_state = await self.load_session(session_id=normalized_session_id)
        if session_state is None:
            if normalized_stage != "ingest":
                raise ADKArtifactSessionError(f"sheet stage session not found: {normalized_session_id}")
            now_ms = _now_ms()
            session_state = {
                "session_id": normalized_session_id,
                "user_id": normalized_user_id,
                "current_stage": "",
                "artifact_versions": {},
                "artifacts": {},
                "history": [],
                "invocation_ids": [],
                "last_invocation_id": "",
                "created_at_ms": now_ms,
                "updated_at_ms": now_ms,
            }

        owner = _norm_text(session_state.get("user_id"))
        if owner != normalized_user_id:
            raise ADKArtifactBindingError("sheet stage session is bound to another user")

        session_state = await self._validate_invocation_binding(
            session_state=session_state,
            session_id=normalized_session_id,
            user_id=normalized_user_id,
            stage=normalized_stage,
            invocation_id=invocation_id,
        )
        session_state["updated_at_ms"] = _now_ms()
        stored = await self.save_session(session_id=normalized_session_id, session_state=session_state)
        return normalized_session_id, stored

    async def _validate_invocation_binding(
        self,
        *,
        session_state: Dict[str, Any],
        session_id: str,
        user_id: str,
        stage: str,
        invocation_id: Optional[str],
    ) -> Dict[str, Any]:
        normalized_invocation_id = _norm_text(invocation_id)
        if not normalized_invocation_id:
            return session_state

        invocation_key = self.build_invocation_key(normalized_invocation_id)
        binding = await self._runtime_store.get_payload(invocation_key)
        if not isinstance(binding, dict):
            if stage != "ingest":
                raise ADKArtifactSessionError("invocation_id binding not found")
            now_ms = _now_ms()
            binding = {
                "session_id": session_id,
                "user_id": user_id,
                "invocation_id": normalized_invocation_id,
                "created_at_ms": now_ms,
                "updated_at_ms": now_ms,
            }
            await self._runtime_store.put_payload(invocation_key, binding, updated_at=now_ms)
        else:
            bound_session_id = _norm_text(binding.get("session_id"))
            bound_user_id = _norm_text(binding.get("user_id"))
            if bound_session_id != session_id:
                raise ADKArtifactBindingError("invocation_id is bound to another session")
            if bound_user_id != user_id:
                raise ADKArtifactBindingError("invocation_id is bound to another user")

        invocation_ids = _copy_list(session_state.get("invocation_ids"))
        if invocation_ids:
            if normalized_invocation_id not in invocation_ids:
                if stage != "ingest":
                    raise ADKArtifactBindingError("session invocation binding mismatch")
                invocation_ids.append(normalized_invocation_id)
        else:
            invocation_ids.append(normalized_invocation_id)

        session_state["invocation_ids"] = invocation_ids
        session_state["last_invocation_id"] = normalized_invocation_id
        return session_state

    async def store_sheet_stage_artifact(
        self,
        *,
        session_state: Dict[str, Any],
        session_id: str,
        stage: str,
        artifact_key: str,
        payload: Dict[str, Any],
        parent_artifact_ref: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        normalized_session_id = _norm_text(session_id)
        normalized_artifact_key = _norm_artifact_key(artifact_key)
        normalized_stage = _norm_text(stage).lower()
        if not normalized_session_id or not normalized_artifact_key:
            raise ValueError("session_id and artifact_key are required")

        now_ms = _now_ms()
        artifact_versions_raw = _copy_dict(session_state.get("artifact_versions"))
        artifacts_raw = _copy_dict(session_state.get("artifacts"))
        history = _copy_list(session_state.get("history"))

        key_versions = _copy_dict(artifacts_raw.get(normalized_artifact_key))
        next_version = int(artifact_versions_raw.get(normalized_artifact_key) or 0) + 1
        normalized_payload = _copy_dict(payload)

        artifact_ref = {
            "artifact_key": normalized_artifact_key,
            "artifact_version": next_version,
            "artifact_session_id": normalized_session_id,
        }
        parent_ref = self.normalize_artifact_ref(parent_artifact_ref, required=False)
        artifact_record = {
            "tenant_id": _norm_text(session_state.get("user_id")),
            "session_id": normalized_session_id,
            "artifact_key": normalized_artifact_key,
            "artifact_version": next_version,
            "stage": normalized_stage,
            "parent_artifact": parent_ref,
            "payload": normalized_payload,
            "created_at_ms": now_ms,
            "updated_at_ms": now_ms,
        }

        key_versions[str(next_version)] = artifact_record
        artifacts_raw[normalized_artifact_key] = key_versions
        artifact_versions_raw[normalized_artifact_key] = next_version

        history.append(
            {
                "stage": normalized_stage,
                "status": "completed",
                "artifact": _copy_dict(artifact_ref),
                "timestamp_ms": now_ms,
            }
        )
        if len(history) > 100:
            del history[:-100]

        session_state["artifact_versions"] = artifact_versions_raw
        session_state["artifacts"] = artifacts_raw
        session_state["history"] = history
        session_state["current_stage"] = normalized_stage
        session_state["updated_at_ms"] = now_ms

        await self._runtime_store.put_payload(
            self.build_artifact_record_key(
                session_id=normalized_session_id,
                artifact_key=normalized_artifact_key,
                artifact_version=next_version,
            ),
            artifact_record,
            updated_at=now_ms,
        )
        stored_session_state = await self.save_session(
            session_id=normalized_session_id,
            session_state=session_state,
            updated_at_ms=now_ms,
        )
        return artifact_ref, stored_session_state

    async def load_sheet_stage_artifact(
        self,
        *,
        session_id: str,
        user_id: str,
        artifact_ref: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_ref = self.normalize_artifact_ref(artifact_ref, required=True)
        normalized_session_id = _norm_text(session_id)
        if normalized_ref["artifact_session_id"] != normalized_session_id:
            raise ADKArtifactBindingError("artifact record is bound to another session")

        payload_key = self.build_artifact_record_key(
            session_id=normalized_ref["artifact_session_id"],
            artifact_key=normalized_ref["artifact_key"],
            artifact_version=normalized_ref["artifact_version"],
        )
        artifact_record = await self._runtime_store.get_payload(payload_key)
        if not isinstance(artifact_record, dict):
            raise ADKArtifactNotFoundError(
                f"artifact version not found: {normalized_ref['artifact_key']}@{normalized_ref['artifact_version']}"
            )

        record_tenant_id = _norm_text(artifact_record.get("tenant_id"))
        record_session_id = _norm_text(artifact_record.get("session_id"))
        normalized_user_id = _norm_text(user_id)
        if record_session_id != normalized_session_id:
            raise ADKArtifactBindingError("artifact record is bound to another session")
        if record_tenant_id != normalized_user_id:
            raise ADKArtifactBindingError("artifact record is bound to another tenant")

        payload = artifact_record.get("payload")
        if not isinstance(payload, dict):
            raise ADKArtifactBindingError("artifact record missing payload")
        return _copy_dict(payload)

    def normalize_artifact_ref(self, value: Any, *, required: bool = True) -> Dict[str, Any]:
        if value is None:
            if required:
                raise ValueError("artifact reference is required")
            return {}
        if not isinstance(value, dict):
            raise ValueError("artifact reference must be an object")

        if not required:
            has_any_binding_field = any(
                _norm_text(
                    value.get(field_name)
                )
                for field_name in (
                    "artifact_key",
                    "artifactKey",
                    "artifact_version",
                    "artifactVersion",
                    "artifact_session_id",
                    "artifactSessionId",
                )
            )
            if not has_any_binding_field:
                return {}

        artifact_key = _norm_artifact_key(value.get("artifact_key") or value.get("artifactKey"))
        if not artifact_key:
            raise ValueError("artifact_key is required")

        artifact_version = _coerce_version(value.get("artifact_version", value.get("artifactVersion")))
        artifact_session_id = _norm_text(value.get("artifact_session_id") or value.get("artifactSessionId"))
        if not artifact_session_id:
            raise ValueError("artifact_session_id is required")

        return {
            "artifact_key": artifact_key,
            "artifact_version": artifact_version,
            "artifact_session_id": artifact_session_id,
        }

    def get_latest_artifact_version(self, *, session_state: Dict[str, Any], artifact_key: str) -> int:
        versions = _copy_dict(session_state.get("artifact_versions"))
        return int(versions.get(_norm_artifact_key(artifact_key)) or 0)

    async def query_sheet_artifact_lineage(
        self,
        *,
        session_id: str,
        user_id: str,
        artifact_key: str,
        artifact_version: int,
    ) -> Dict[str, Any]:
        normalized_session_id = _norm_text(session_id)
        normalized_artifact_key = _norm_artifact_key(artifact_key)
        normalized_version = _coerce_version(artifact_version)

        session_state = await self.load_session(session_id=normalized_session_id)
        if not isinstance(session_state, dict):
            raise ADKArtifactSessionError(f"sheet stage session not found: {normalized_session_id}")

        owner = _norm_text(session_state.get("user_id"))
        normalized_user_id = _norm_text(user_id)
        if owner != normalized_user_id:
            raise ADKArtifactBindingError("sheet stage session is bound to another user")

        target_ref = {
            "artifact_key": normalized_artifact_key,
            "artifact_version": normalized_version,
            "artifact_session_id": normalized_session_id,
        }
        target_record = await self._load_artifact_record_for_lineage(
            session_id=normalized_session_id,
            user_id=normalized_user_id,
            artifact_ref=target_ref,
        )

        all_records = self._collect_all_session_artifacts(session_state=session_state)
        target_token = _artifact_ref_token(
            artifact_key=normalized_artifact_key,
            artifact_version=normalized_version,
        )
        all_records[target_token] = _copy_dict(target_record)

        parent_refs: List[Dict[str, Any]] = []
        parent_ref = self.normalize_artifact_ref(target_record.get("parent_artifact"), required=False)
        while parent_ref:
            parent_token = _artifact_ref_token(
                artifact_key=parent_ref["artifact_key"],
                artifact_version=parent_ref["artifact_version"],
            )
            parent_record = all_records.get(parent_token)
            if not isinstance(parent_record, dict):
                raise ADKArtifactLineageError(
                    f"missing parent lineage: {parent_ref['artifact_key']}@{parent_ref['artifact_version']}"
                )
            parent_refs.append(parent_ref)
            parent_ref = self.normalize_artifact_ref(parent_record.get("parent_artifact"), required=False)

        child_map: Dict[str, List[Dict[str, Any]]] = {}
        for record in all_records.values():
            parent = self.normalize_artifact_ref(record.get("parent_artifact"), required=False)
            if not parent:
                continue
            parent_token = _artifact_ref_token(
                artifact_key=parent["artifact_key"],
                artifact_version=parent["artifact_version"],
            )
            child_map.setdefault(parent_token, []).append(
                {
                    "artifact_key": _norm_artifact_key(record.get("artifact_key")),
                    "artifact_version": _coerce_version(record.get("artifact_version")),
                    "artifact_session_id": _norm_text(record.get("session_id")),
                }
            )

        for children in child_map.values():
            children.sort(key=lambda item: (item["artifact_key"], int(item["artifact_version"])))

        child_refs: List[Dict[str, Any]] = []
        queue: List[Dict[str, Any]] = list(child_map.get(target_token, []))
        visited: set[str] = set()
        while queue:
            current_ref = queue.pop(0)
            current_token = _artifact_ref_token(
                artifact_key=current_ref["artifact_key"],
                artifact_version=current_ref["artifact_version"],
            )
            if current_token in visited:
                continue
            visited.add(current_token)
            child_refs.append(current_ref)
            queue.extend(child_map.get(current_token, []))

        version_refs: List[Dict[str, Any]] = []
        artifacts_by_key = _copy_dict(_copy_dict(session_state.get("artifacts")).get(normalized_artifact_key))
        if not artifacts_by_key:
            raise ADKArtifactLineageError(
                f"missing version lineage: {normalized_artifact_key}@{normalized_version}"
            )

        for raw_version in sorted(
            (_coerce_version(item) for item in artifacts_by_key.keys()),
        ):
            version_refs.append(
                {
                    "artifact_key": normalized_artifact_key,
                    "artifact_version": raw_version,
                    "artifact_session_id": normalized_session_id,
                }
            )

        return {
            "artifact": target_ref,
            "parent_chain": list(reversed(parent_refs)),
            "child_chain": child_refs,
            "version_chain": version_refs,
        }

    async def _load_artifact_record_for_lineage(
        self,
        *,
        session_id: str,
        user_id: str,
        artifact_ref: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload_key = self.build_artifact_record_key(
            session_id=session_id,
            artifact_key=_norm_artifact_key(artifact_ref.get("artifact_key")),
            artifact_version=_coerce_version(artifact_ref.get("artifact_version")),
        )
        artifact_record = await self._runtime_store.get_payload(payload_key)
        if not isinstance(artifact_record, dict):
            raise ADKArtifactLineageError(
                f"artifact lineage not found: {artifact_ref.get('artifact_key')}@{artifact_ref.get('artifact_version')}"
            )

        record_tenant_id = _norm_text(artifact_record.get("tenant_id"))
        record_session_id = _norm_text(artifact_record.get("session_id"))
        if record_session_id != session_id:
            raise ADKArtifactBindingError("artifact record is bound to another session")
        if record_tenant_id != user_id:
            raise ADKArtifactBindingError("artifact record is bound to another tenant")
        return _copy_dict(artifact_record)

    def _collect_all_session_artifacts(self, *, session_state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        artifacts = _copy_dict(session_state.get("artifacts"))
        for artifact_key, versions_any in artifacts.items():
            if not isinstance(versions_any, dict):
                continue
            normalized_artifact_key = _norm_artifact_key(artifact_key)
            for raw_version, raw_record in versions_any.items():
                if not isinstance(raw_record, dict):
                    continue
                try:
                    version = _coerce_version(raw_version)
                except Exception:
                    continue
                token = _artifact_ref_token(
                    artifact_key=normalized_artifact_key,
                    artifact_version=version,
                )
                normalized = _copy_dict(raw_record)
                normalized.setdefault("artifact_key", normalized_artifact_key)
                normalized["artifact_version"] = version
                result[token] = normalized
        return result
