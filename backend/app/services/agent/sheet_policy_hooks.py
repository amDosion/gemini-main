"""Row-level sheet policy hooks with deterministic audit-chain evidence."""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional, Tuple

ROW_LEVEL_POLICY_NAME = "row_level"
ROW_LEVEL_BEFORE_AFTER_ALLOWED = {"before_tool", "after_tool"}
ROW_LEVEL_STAGE_ALLOWED = {"ingest", "profile", "query", "export"}
_ROW_LEVEL_DECISIONS_ALLOWED = {"allow", "filter", "deny"}
_ROW_LEVEL_TENANT_FIELDS = (
    "tenant_id",
    "tenantId",
    "tenant",
    "user_id",
    "userId",
)
_ROW_LEVEL_ROW_CONTAINER_FIELDS = ("rows", "records", "items", "data")


class SheetPolicyHookError(ValueError):
    """Base row-level policy hook error."""


class SheetPolicyEvidenceError(SheetPolicyHookError):
    """Policy audit-chain evidence is missing or invalid."""


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


def _coerce_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise SheetPolicyEvidenceError(f"{field} must be a positive integer")
    if isinstance(value, (int, float)):
        numeric = int(value)
    else:
        text = _norm_text(value)
        if not text:
            raise SheetPolicyEvidenceError(f"{field} is required")
        try:
            numeric = int(float(text))
        except Exception as exc:
            raise SheetPolicyEvidenceError(f"{field} must be a positive integer") from exc
    if numeric <= 0:
        raise SheetPolicyEvidenceError(f"{field} must be a positive integer")
    return numeric


def _normalize_stage(value: Any) -> str:
    stage = _norm_text(value).lower()
    if stage not in ROW_LEVEL_STAGE_ALLOWED:
        raise SheetPolicyHookError(
            f"invalid stage: {value!r}; expected one of {sorted(ROW_LEVEL_STAGE_ALLOWED)}"
        )
    return stage


def _normalize_before_after(value: Any) -> str:
    marker = _norm_text(value).lower()
    if marker not in ROW_LEVEL_BEFORE_AFTER_ALLOWED:
        raise SheetPolicyHookError(
            f"invalid before_after: {value!r}; expected one of {sorted(ROW_LEVEL_BEFORE_AFTER_ALLOWED)}"
        )
    return marker


def _extract_row_container(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    for field_name in _ROW_LEVEL_ROW_CONTAINER_FIELDS:
        rows = payload.get(field_name)
        if not isinstance(rows, list):
            continue
        if rows and not all(isinstance(item, dict) for item in rows):
            continue
        return field_name, [_copy_dict(item) for item in rows if isinstance(item, dict)]
    return "", []


def _extract_row_tenant_binding(row: Dict[str, Any]) -> str:
    for field_name in _ROW_LEVEL_TENANT_FIELDS:
        tenant = _norm_text(row.get(field_name))
        if tenant:
            return tenant
    return ""


def _refresh_row_count(payload: Dict[str, Any], *, row_count: int) -> None:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        normalized_summary = _copy_dict(summary)
        normalized_summary["row_count"] = int(max(0, row_count))
        payload["summary"] = normalized_summary
    elif "row_count" in payload:
        payload["row_count"] = int(max(0, row_count))


def validate_row_level_policy_audit_chain(
    *,
    chain: Any,
    require_non_empty: bool = True,
    require_stage_before_after_pair: bool = False,
    stage: Optional[str] = None,
) -> List[Dict[str, Any]]:
    normalized_chain = _copy_list(chain)
    if chain is None:
        normalized_chain = []
    if not isinstance(chain, list) and chain is not None:
        raise SheetPolicyEvidenceError("policy_audit_chain must be a list")
    if require_non_empty and not normalized_chain:
        raise SheetPolicyEvidenceError("policy_audit_chain is required")

    normalized_stage = _normalize_stage(stage) if stage else ""
    result: List[Dict[str, Any]] = []
    for index, raw_event in enumerate(normalized_chain, start=1):
        if not isinstance(raw_event, dict):
            raise SheetPolicyEvidenceError(f"policy_audit_chain[{index - 1}] must be an object")
        event = _copy_dict(raw_event)
        sequence = _coerce_positive_int(event.get("sequence"), field="sequence")
        if sequence != index:
            raise SheetPolicyEvidenceError(
                f"policy_audit_chain[{index - 1}] sequence mismatch ({sequence} != {index})"
            )

        policy = _norm_text(event.get("policy")).lower()
        if not policy:
            raise SheetPolicyEvidenceError(f"policy_audit_chain[{index - 1}] policy is required")

        before_after = _normalize_before_after(event.get("before_after"))
        event_stage = _normalize_stage(event.get("stage"))
        who = _norm_text(event.get("who"))
        what = _norm_text(event.get("what"))
        why = _norm_text(event.get("why"))
        decision = _norm_text(event.get("decision")).lower()
        if not who:
            raise SheetPolicyEvidenceError(f"policy_audit_chain[{index - 1}] who is required")
        if not what:
            raise SheetPolicyEvidenceError(f"policy_audit_chain[{index - 1}] what is required")
        if not why:
            raise SheetPolicyEvidenceError(f"policy_audit_chain[{index - 1}] why is required")
        if decision and decision not in _ROW_LEVEL_DECISIONS_ALLOWED:
            raise SheetPolicyEvidenceError(
                f"policy_audit_chain[{index - 1}] decision must be one of "
                f"{sorted(_ROW_LEVEL_DECISIONS_ALLOWED)}"
            )

        when = _coerce_positive_int(event.get("when"), field="when")
        evidence = event.get("evidence")
        if not isinstance(evidence, dict):
            raise SheetPolicyEvidenceError(f"policy_audit_chain[{index - 1}] evidence is required")

        event["sequence"] = sequence
        event["policy"] = policy
        event["before_after"] = before_after
        event["stage"] = event_stage
        event["who"] = who
        event["what"] = what
        event["why"] = why
        event["when"] = when
        event["decision"] = decision or "allow"
        event["evidence"] = _copy_dict(evidence)
        result.append(event)

    if require_stage_before_after_pair:
        before_present = False
        after_present = False
        for item in result:
            if item.get("policy") != ROW_LEVEL_POLICY_NAME:
                continue
            if normalized_stage and item.get("stage") != normalized_stage:
                continue
            marker = str(item.get("before_after") or "")
            if marker == "before_tool":
                before_present = True
            elif marker == "after_tool":
                after_present = True
        if not before_present or not after_present:
            stage_hint = normalized_stage or "current"
            raise SheetPolicyEvidenceError(
                f"policy_audit_chain missing row_level before_tool/after_tool pair for stage {stage_hint}"
            )

    return result


def assert_stage_row_level_policy_pair(*, chain: Any, stage: str) -> List[Dict[str, Any]]:
    return validate_row_level_policy_audit_chain(
        chain=chain,
        require_non_empty=True,
        require_stage_before_after_pair=True,
        stage=stage,
    )


def apply_row_level_policy_hook(
    *,
    stage: str,
    before_after: str,
    user_id: str,
    session_id: str,
    payload: Any,
    audit_chain: Any = None,
    require_existing_chain: bool = False,
    deny_on_foreign_only: bool = True,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_stage = _normalize_stage(stage)
    normalized_before_after = _normalize_before_after(before_after)
    normalized_user_id = _norm_text(user_id)
    normalized_session_id = _norm_text(session_id)
    if not normalized_user_id:
        raise SheetPolicyHookError("user_id is required")
    if not normalized_session_id:
        raise SheetPolicyHookError("session_id is required")

    normalized_payload = _copy_dict(payload)
    raw_chain = audit_chain
    if raw_chain is None:
        raw_chain = normalized_payload.get("policy_audit_chain")
    normalized_chain = validate_row_level_policy_audit_chain(
        chain=raw_chain,
        require_non_empty=bool(require_existing_chain),
        require_stage_before_after_pair=False,
    )

    row_container, rows = _extract_row_container(normalized_payload)
    rows_seen = len(rows)
    rows_allowed: List[Dict[str, Any]] = []
    rows_filtered = 0
    for row in rows:
        row_tenant_id = _extract_row_tenant_binding(row)
        if row_tenant_id and row_tenant_id != normalized_user_id:
            rows_filtered += 1
            continue
        rows_allowed.append(_copy_dict(row))

    if row_container:
        normalized_payload[row_container] = rows_allowed
        _refresh_row_count(normalized_payload, row_count=len(rows_allowed))

    if rows_seen > 0 and rows_filtered >= rows_seen and bool(deny_on_foreign_only):
        raise PermissionError(
            "row_level policy denied: no rows authorized for tenant "
            f"{normalized_user_id!r} ({normalized_before_after})"
        )

    decision = "allow"
    if rows_filtered > 0:
        decision = "filter"
    if rows_seen > 0 and rows_filtered >= rows_seen:
        decision = "deny"

    normalized_reason = _norm_text(reason)
    if not normalized_reason:
        if normalized_before_after == "before_tool":
            normalized_reason = "apply row-level tenant filter before tool execution"
        else:
            normalized_reason = "verify row-level tenant filter evidence after tool execution"

    audit_event = {
        "sequence": len(normalized_chain) + 1,
        "policy": ROW_LEVEL_POLICY_NAME,
        "before_after": normalized_before_after,
        "stage": normalized_stage,
        "who": normalized_user_id,
        "what": f"sheet_stage:{normalized_stage}",
        "why": normalized_reason,
        "when": _now_ms(),
        "decision": decision,
        "evidence": {
            "session_id": normalized_session_id,
            "required_tenant_id": normalized_user_id,
            "rows_seen": rows_seen,
            "rows_allowed": len(rows_allowed),
            "rows_filtered": rows_filtered,
        },
    }

    next_chain = normalized_chain + [audit_event]
    validated_next_chain = validate_row_level_policy_audit_chain(
        chain=next_chain,
        require_non_empty=True,
        require_stage_before_after_pair=False,
    )

    return {
        "payload": normalized_payload,
        "audit_event": _copy_dict(audit_event),
        "policy_audit_chain": validated_next_chain,
        "row_level": {
            "status": "passed",
            "decision": decision,
            "before_after": normalized_before_after,
            "stage": normalized_stage,
            "rows_seen": rows_seen,
            "rows_allowed": len(rows_allowed),
            "rows_filtered": rows_filtered,
        },
    }


__all__ = [
    "ROW_LEVEL_BEFORE_AFTER_ALLOWED",
    "ROW_LEVEL_POLICY_NAME",
    "ROW_LEVEL_STAGE_ALLOWED",
    "SheetPolicyEvidenceError",
    "SheetPolicyHookError",
    "apply_row_level_policy_hook",
    "assert_stage_row_level_policy_pair",
    "validate_row_level_policy_audit_chain",
]
