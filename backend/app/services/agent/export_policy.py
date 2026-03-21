"""Sheet export constraints and audit-evidence enforcement."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from .sheet_policy_hooks import (
    SheetPolicyEvidenceError,
    assert_stage_row_level_policy_pair,
    validate_row_level_policy_audit_chain,
)

_EXPORT_CONSTRAINT_POLICY_NAME = "export_constraint"
_EXPORT_CONSTRAINT_SENSITIVE_FIELDS = {
    "ssn",
    "social_security",
    "passport",
    "credit_card",
    "card_number",
    "bank_account",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "身份证",
}
_TENANT_BINDING_FIELDS = (
    "tenant_id",
    "tenantId",
    "artifact_tenant_id",
    "artifactTenantId",
    "user_id",
    "userId",
)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


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


def _iter_export_strings(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        chunks: List[str] = []
        for key, nested in value.items():
            chunks.extend(_iter_export_strings(str(key)))
            chunks.extend(_iter_export_strings(nested))
        return chunks
    if isinstance(value, (list, tuple, set)):
        chunks: List[str] = []
        for nested in value:
            chunks.extend(_iter_export_strings(nested))
        return chunks
    return [str(value)]


def _extract_columns(payload: Any) -> List[str]:
    if not isinstance(payload, dict):
        return []
    raw_columns = payload.get("columns")
    if not isinstance(raw_columns, list):
        return []
    columns: List[str] = []
    for item in raw_columns:
        if isinstance(item, str):
            name = _norm_text(item)
        elif isinstance(item, dict):
            name = _norm_text(item.get("name") or item.get("column"))
        else:
            name = ""
        if name:
            columns.append(name)
    return columns


def _scan_sensitive_hits(*, source_payload: Any, output_payload: Any) -> List[str]:
    chunks: List[str] = []
    chunks.extend(_extract_columns(source_payload))
    chunks.extend(_extract_columns(output_payload))
    chunks.extend(_iter_export_strings(source_payload))
    chunks.extend(_iter_export_strings(output_payload))
    haystack = "\n".join(item for item in chunks if item).lower()
    if not haystack:
        return []

    hits: List[str] = []
    for keyword in _EXPORT_CONSTRAINT_SENSITIVE_FIELDS:
        needle = _norm_text(keyword).lower()
        if not needle:
            continue
        if needle in haystack:
            hits.append(keyword)
    return sorted(set(hits))


def _extract_tenant_binding(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in _TENANT_BINDING_FIELDS:
        value = _norm_text(payload.get(key))
        if value:
            return value
    source = payload.get("source")
    if isinstance(source, dict):
        for key in _TENANT_BINDING_FIELDS:
            value = _norm_text(source.get(key))
            if value:
                return value
    return ""


def _normalize_artifact_ref(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("artifact_ref is required")
    artifact_key = _norm_text(value.get("artifact_key") or value.get("artifactKey"))
    artifact_session_id = _norm_text(value.get("artifact_session_id") or value.get("artifactSessionId"))
    if not artifact_key:
        raise ValueError("artifact_ref.artifact_key is required")
    if not artifact_session_id:
        raise ValueError("artifact_ref.artifact_session_id is required")
    raw_version = value.get("artifact_version", value.get("artifactVersion"))
    if isinstance(raw_version, bool):
        raise ValueError("artifact_ref.artifact_version must be a positive integer")
    try:
        artifact_version = int(raw_version)
    except Exception as exc:
        raise ValueError("artifact_ref.artifact_version must be a positive integer") from exc
    if artifact_version <= 0:
        raise ValueError("artifact_ref.artifact_version must be a positive integer")
    return {
        "artifact_key": artifact_key,
        "artifact_version": artifact_version,
        "artifact_session_id": artifact_session_id,
    }


def _build_export_constraint_fingerprint(evidence: Dict[str, Any]) -> str:
    canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enforce_sheet_export_constraint(
    *,
    user_id: str,
    session_id: str,
    artifact_ref: Any,
    source_payload: Any,
    output_payload: Any,
    policy_audit_chain: Any,
    export_format: Optional[str] = None,
    resource_tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_user_id = _norm_text(user_id)
    normalized_session_id = _norm_text(session_id)
    if not normalized_user_id:
        raise ValueError("user_id is required")
    if not normalized_session_id:
        raise ValueError("session_id is required")

    normalized_artifact_ref = _normalize_artifact_ref(artifact_ref)
    if normalized_artifact_ref["artifact_session_id"] != normalized_session_id:
        raise PermissionError(
            "export_constraint failed: artifact session binding mismatch "
            f"({normalized_artifact_ref['artifact_session_id']} != {normalized_session_id})"
        )

    normalized_chain = validate_row_level_policy_audit_chain(
        chain=policy_audit_chain,
        require_non_empty=True,
        require_stage_before_after_pair=False,
    )
    normalized_chain = assert_stage_row_level_policy_pair(
        chain=normalized_chain,
        stage="export",
    )

    for event in normalized_chain:
        event_who = _norm_text(event.get("who"))
        if event_who != normalized_user_id:
            raise PermissionError(
                "export_constraint failed: audit chain user mismatch "
                f"({event_who!r} != {normalized_user_id!r})"
            )
        evidence = event.get("evidence")
        if not isinstance(evidence, dict):
            raise SheetPolicyEvidenceError("policy_audit_chain event evidence is required")
        evidence_session_id = _norm_text(evidence.get("session_id"))
        if evidence_session_id and evidence_session_id != normalized_session_id:
            raise PermissionError(
                "export_constraint failed: audit chain session mismatch "
                f"({evidence_session_id!r} != {normalized_session_id!r})"
            )

    explicit_resource_tenant = _norm_text(resource_tenant_id)
    payload_tenant = _extract_tenant_binding(source_payload) or _extract_tenant_binding(output_payload)
    normalized_resource_tenant = explicit_resource_tenant or payload_tenant or normalized_user_id
    if normalized_resource_tenant != normalized_user_id:
        raise PermissionError(
            "export_constraint failed: tenant binding mismatch "
            f"({normalized_resource_tenant} != {normalized_user_id})"
        )

    sensitive_hits = _scan_sensitive_hits(
        source_payload=source_payload,
        output_payload=output_payload,
    )
    if sensitive_hits:
        raise ValueError(
            "export_constraint failed: sensitive fields detected "
            f"({', '.join(sensitive_hits)})"
        )

    normalized_export_format = _norm_text(export_format).lower() or "markdown"
    if normalized_export_format not in {"json", "markdown"}:
        normalized_export_format = "markdown"

    evidence_base = {
        "tenant_id": normalized_user_id,
        "resource_tenant_id": normalized_resource_tenant,
        "session_id": normalized_session_id,
        "artifact_ref": normalized_artifact_ref,
        "export_format": normalized_export_format,
        "audit_chain_length": len(normalized_chain),
        "sensitive_hits": sensitive_hits,
    }
    evidence_fingerprint = _build_export_constraint_fingerprint(evidence_base)

    constraint_event = {
        "sequence": len(normalized_chain) + 1,
        "policy": _EXPORT_CONSTRAINT_POLICY_NAME,
        "before_after": "after_tool",
        "stage": "export",
        "who": normalized_user_id,
        "what": "sheet_stage:export",
        "why": "enforce export constraints for sensitive fields and tenant/session binding",
        "when": _now_ms(),
        "decision": "allow",
        "evidence": {
            **_copy_dict(evidence_base),
            "export_constraint": "passed",
            "audit_fingerprint": evidence_fingerprint,
        },
    }

    final_chain = _copy_list(normalized_chain)
    final_chain.append(constraint_event)
    validated_chain = validate_row_level_policy_audit_chain(
        chain=final_chain,
        require_non_empty=True,
        require_stage_before_after_pair=True,
        stage="export",
    )

    return {
        "export_constraint": {
            "status": "passed",
            "tenant_id": normalized_user_id,
            "resource_tenant_id": normalized_resource_tenant,
            "session_id": normalized_session_id,
            "artifact_key": normalized_artifact_ref["artifact_key"],
            "artifact_version": normalized_artifact_ref["artifact_version"],
            "artifact_session_id": normalized_artifact_ref["artifact_session_id"],
            "export_format": normalized_export_format,
            "sensitive_hits": sensitive_hits,
            "audit_fingerprint": evidence_fingerprint,
        },
        "policy_audit_chain": validated_chain,
    }


__all__ = [
    "enforce_sheet_export_constraint",
]
