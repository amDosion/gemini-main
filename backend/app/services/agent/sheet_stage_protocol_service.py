"""Shared sheet-stage protocol execution helpers for routes and workflow tools."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .adk_artifact_service import (
    ADKArtifactBindingError,
    ADKArtifactNotFoundError,
    ADKArtifactService,
    ADKArtifactSessionError,
)
from .adk_builtin_tools import (
    SHEET_STAGE_PROTOCOL_VERSION,
    build_adk_builtin_tools,
    build_sheet_stage_envelope,
    normalize_sheet_artifact_ref,
    normalize_sheet_stage,
    validate_sheet_artifact_binding,
    validate_sheet_export_precheck,
)
from .export_policy import enforce_sheet_export_constraint
from .sheet_policy_hooks import (
    apply_row_level_policy_hook,
    assert_stage_row_level_policy_pair,
)
from .workflow_runtime_store import create_workflow_runtime_store

_SHEET_STAGE_ALLOWED_PREVIOUS: Dict[str, set[str]] = {
    "ingest": {"", "ingest"},
    "profile": {"ingest", "profile"},
    "query": {"profile", "query"},
    "export": {"query", "export"},
}
_SHEET_STAGE_INPUT_ARTIFACT_KEY: Dict[str, str] = {
    "profile": "sheet/ingest",
    "query": "sheet/profile",
    "export": "sheet/query",
}
_SHEET_STAGE_OUTPUT_ARTIFACT_KEY: Dict[str, str] = {
    "ingest": "sheet/ingest",
    "profile": "sheet/profile",
    "query": "sheet/query",
    "export": "sheet/export",
}

_default_sheet_stage_runtime_store = create_workflow_runtime_store()
_default_sheet_stage_artifact_service = ADKArtifactService(
    runtime_store=_default_sheet_stage_runtime_store,
    namespace="sheet-stage",
)

SheetStageFileResolver = Callable[[Optional[str], Optional[str], Optional[str]], str]


class SheetStageProtocolError(Exception):
    """Structured protocol error surfaced to HTTP routes and workflow tools."""

    def __init__(self, *, status_code: int, detail: Dict[str, Any]):
        self.status_code = int(status_code)
        self.detail = detail
        message = ""
        if isinstance(detail, dict):
            error = detail.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or "").strip()
        super().__init__(message or "sheet stage protocol failed")


def get_default_sheet_stage_runtime_store():
    return _default_sheet_stage_runtime_store


def get_default_sheet_stage_artifact_service() -> ADKArtifactService:
    return _default_sheet_stage_artifact_service


def _request_to_payload(request_body: Any) -> Dict[str, Any]:
    if isinstance(request_body, dict):
        return dict(request_body)
    model_dump = getattr(request_body, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(by_alias=False)
        if isinstance(payload, dict):
            return payload
    return {}


def _pick_first_value(payload: Dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload:
            value = payload.get(key)
            if value is not None:
                return value
    return None


def _pick_first_text(payload: Dict[str, Any], keys: list[str]) -> str:
    value = _pick_first_value(payload, keys)
    return str(value or "").strip()


def _to_int(value: Any, *, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        parsed = int(float(value))
    except Exception:
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def build_sheet_stage_failure_detail(
    *,
    stage: str,
    session_id: str,
    message: str,
    error_code: str = "SHEET_STAGE_FAILED",
) -> Dict[str, Any]:
    normalized_stage = str(stage or "").strip().lower()
    if normalized_stage not in _SHEET_STAGE_OUTPUT_ARTIFACT_KEY:
        normalized_stage = "ingest"
    normalized_session_id = str(session_id or "").strip() or "pending"
    return build_sheet_stage_envelope(
        stage=normalized_stage,
        status="failed",
        session_id=normalized_session_id,
        protocol_version=SHEET_STAGE_PROTOCOL_VERSION,
        error={
            "code": str(error_code or "SHEET_STAGE_FAILED"),
            "message": str(message or "sheet stage failed"),
        },
    )


def extract_sheet_stage_summary_text(envelope: Dict[str, Any]) -> str:
    if not isinstance(envelope, dict):
        return ""
    error = envelope.get("error")
    if isinstance(error, dict):
        error_message = str(error.get("message") or "").strip()
        if error_message:
            return error_message

    data = envelope.get("data")
    if isinstance(data, dict):
        payload = data.get("payload")
        if isinstance(payload, dict):
            for key in ("rendered", "answer", "summaryText", "summary_text", "text"):
                value = payload.get(key)
                text = str(value or "").strip()
                if text:
                    return text
            summary = payload.get("summary")
            if isinstance(summary, dict):
                row_count = int(summary.get("row_count") or 0)
                column_count = int(summary.get("column_count") or 0)
                if row_count > 0 or column_count > 0:
                    return f"{row_count} rows, {column_count} columns"

    stage = str(envelope.get("stage") or "").strip()
    status = str(envelope.get("status") or "").strip()
    if stage and status:
        return f"sheet-stage {stage}: {status}"
    return ""


def _raise_sheet_stage_protocol_error(
    *,
    status_code: int,
    stage: str,
    session_id: str,
    message: str,
    error_code: str = "SHEET_STAGE_FAILED",
) -> None:
    raise SheetStageProtocolError(
        status_code=status_code,
        detail=build_sheet_stage_failure_detail(
            stage=stage,
            session_id=session_id,
            message=message,
            error_code=error_code,
        ),
    )


def _extract_sheet_artifact_tenant_binding(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _pick_first_text(
        value,
        [
            "artifact_tenant_id",
            "artifactTenantId",
            "tenant_id",
            "tenantId",
            "tenant",
            "user_id",
            "userId",
        ],
    )


def _authorize_sheet_artifact_ref_or_raise(
    *,
    stage: str,
    session_id: str,
    user_id: str,
    raw_artifact_ref: Any,
    normalized_artifact_ref: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_session_id = str(session_id or "").strip()
    artifact_session_id = str(normalized_artifact_ref.get("artifact_session_id") or "").strip()
    if artifact_session_id != normalized_session_id:
        _raise_sheet_stage_protocol_error(
            status_code=400,
            stage=stage,
            session_id=normalized_session_id,
            message="artifact reference is bound to another session",
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )

    expected_tenant_id = str(user_id or "").strip()
    artifact_tenant_id = _extract_sheet_artifact_tenant_binding(raw_artifact_ref)
    if artifact_tenant_id and artifact_tenant_id != expected_tenant_id:
        _raise_sheet_stage_protocol_error(
            status_code=403,
            stage=stage,
            session_id=normalized_session_id,
            message="artifact reference is bound to another tenant",
            error_code="SHEET_STAGE_ARTIFACT_FORBIDDEN",
        )

    return normalized_artifact_ref


def _ensure_sheet_stage_artifact_fresh_or_raise(
    *,
    session_state: Dict[str, Any],
    stage: str,
    session_id: str,
    artifact_ref: Dict[str, Any],
) -> None:
    artifact_key = str(artifact_ref.get("artifact_key") or "").strip()
    artifact_version = int(artifact_ref.get("artifact_version") or 0)
    artifact_versions = session_state.get("artifact_versions")
    latest_version = int((artifact_versions or {}).get(artifact_key) or 0) if isinstance(artifact_versions, dict) else 0

    if latest_version <= 0:
        _raise_sheet_stage_protocol_error(
            status_code=404,
            stage=stage,
            session_id=session_id,
            message=f"artifact key not found: {artifact_key}",
            error_code="SHEET_STAGE_ARTIFACT_NOT_FOUND",
        )

    if artifact_version != latest_version:
        _raise_sheet_stage_protocol_error(
            status_code=409,
            stage=stage,
            session_id=session_id,
            message=f"stale artifact reference ({artifact_key}@{artifact_version}; latest={latest_version})",
            error_code="SHEET_STAGE_ARTIFACT_STALE",
        )


async def _resolve_sheet_stage_session_or_raise(
    *,
    requested_session_id: Optional[str],
    user_id: str,
    stage: str,
    invocation_id: Optional[str],
    artifact_service: ADKArtifactService,
) -> tuple[str, Dict[str, Any]]:
    normalized_stage = str(stage or "").strip().lower()
    normalized_session_id = str(requested_session_id or "").strip()
    try:
        return await artifact_service.resolve_sheet_stage_session(
            requested_session_id=normalized_session_id,
            user_id=user_id,
            stage=normalized_stage,
            invocation_id=invocation_id,
        )
    except ADKArtifactBindingError as exc:
        message = str(exc)
        if "another user" in message:
            _raise_sheet_stage_protocol_error(
                status_code=403,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_FORBIDDEN",
            )
        _raise_sheet_stage_protocol_error(
            status_code=409,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=message,
            error_code="SHEET_STAGE_SESSION_BINDING_MISMATCH",
        )
    except ADKArtifactSessionError as exc:
        message = str(exc)
        if "invocation_id binding not found" in message:
            _raise_sheet_stage_protocol_error(
                status_code=409,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_BINDING_MISMATCH",
            )
        if "required for non-ingest" in message:
            _raise_sheet_stage_protocol_error(
                status_code=400,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_REQUIRED",
            )
        if "not found" in message:
            _raise_sheet_stage_protocol_error(
                status_code=404,
                stage=normalized_stage,
                session_id=normalized_session_id,
                message=message,
                error_code="SHEET_STAGE_SESSION_NOT_FOUND",
            )
        _raise_sheet_stage_protocol_error(
            status_code=409,
            stage=normalized_stage,
            session_id=normalized_session_id,
            message=message,
            error_code="SHEET_STAGE_SESSION_BINDING_MISMATCH",
        )


def _ensure_sheet_stage_transition_or_raise(
    *,
    session_state: Dict[str, Any],
    stage: str,
    session_id: str,
) -> None:
    current_stage = str(session_state.get("current_stage") or "").strip().lower()
    allowed_previous = _SHEET_STAGE_ALLOWED_PREVIOUS.get(stage, set())
    if current_stage not in allowed_previous:
        _raise_sheet_stage_protocol_error(
            status_code=409,
            stage=stage,
            session_id=session_id,
            message=f"invalid stage transition ({current_stage or '<empty>'} -> {stage})",
            error_code="SHEET_STAGE_TRANSITION_INVALID",
        )


async def _store_sheet_stage_artifact_or_raise(
    *,
    session_state: Dict[str, Any],
    session_id: str,
    stage: str,
    artifact_key: str,
    payload: Dict[str, Any],
    parent_artifact_ref: Optional[Dict[str, Any]],
    artifact_service: ADKArtifactService,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        return await artifact_service.store_sheet_stage_artifact(
            session_state=session_state,
            session_id=session_id,
            stage=stage,
            artifact_key=artifact_key,
            payload=payload,
            parent_artifact_ref=parent_artifact_ref,
        )
    except ValueError as exc:
        _raise_sheet_stage_protocol_error(
            status_code=400,
            stage=stage,
            session_id=session_id,
            message=str(exc),
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )


async def _load_sheet_stage_artifact_or_raise(
    *,
    stage: str,
    session_id: str,
    user_id: str,
    artifact_ref: Dict[str, Any],
    artifact_service: ADKArtifactService,
) -> Dict[str, Any]:
    try:
        return await artifact_service.load_sheet_stage_artifact(
            session_id=session_id,
            user_id=user_id,
            artifact_ref=artifact_ref,
        )
    except ADKArtifactNotFoundError as exc:
        _raise_sheet_stage_protocol_error(
            status_code=404,
            stage=stage,
            session_id=session_id,
            message=str(exc),
            error_code="SHEET_STAGE_ARTIFACT_VERSION_NOT_FOUND",
        )
    except ADKArtifactBindingError as exc:
        _raise_sheet_stage_protocol_error(
            status_code=403,
            stage=stage,
            session_id=session_id,
            message=str(exc),
            error_code="SHEET_STAGE_ARTIFACT_FORBIDDEN",
        )


def _resolve_sheet_analyze_tool() -> Callable[..., Dict[str, Any]]:
    for tool in build_adk_builtin_tools():
        if getattr(tool, "__name__", "") == "sheet_analyze":
            return tool
    raise RuntimeError("sheet_analyze tool is unavailable")


def build_sheet_ingest_kwargs_from_request(
    *,
    request_body: Any,
    user_id: str,
    resolve_file_reference: Optional[SheetStageFileResolver] = None,
) -> Dict[str, Any]:
    payload = _request_to_payload(request_body)
    kwargs: Dict[str, Any] = {
        "file_name": _pick_first_text(payload, ["file_name", "fileName"]) or "sheet.csv",
        "file_format": _pick_first_value(payload, ["file_format", "fileFormat"]),
        "csv_encoding": _pick_first_text(payload, ["csv_encoding", "csvEncoding"]) or "utf-8",
        "sheet_name": _pick_first_value(payload, ["sheet_name", "sheetName", "sheet"]),
        "sample_rows": _to_int(
            _pick_first_value(payload, ["sample_rows", "sampleRows"]),
            default=5,
            minimum=1,
            maximum=100,
        ),
        "export_format": "json",
        "tenant_id": str(user_id or ""),
        "resource_tenant_id": str(user_id or ""),
    }

    content = _pick_first_text(payload, ["content"])
    if content:
        kwargs["content"] = content
        kwargs["content_encoding"] = _pick_first_text(payload, ["content_encoding", "contentEncoding"]) or "plain"
        return kwargs

    data_url = _pick_first_text(payload, ["data_url", "dataUrl"])
    if data_url:
        kwargs["data_url"] = data_url
        return kwargs

    file_url = _pick_first_text(payload, ["file_url", "fileUrl"])
    if file_url:
        normalized_file_url = str(file_url or "").strip()
        lowered = normalized_file_url.lower()
        if lowered.startswith("data:"):
            kwargs["data_url"] = normalized_file_url
            return kwargs
        if lowered.startswith(("http://", "https://")):
            kwargs["file_url"] = normalized_file_url
            return kwargs
        local_path = Path(normalized_file_url)
        if local_path.exists() and local_path.is_file():
            payload_bytes = local_path.read_bytes()
            kwargs["content"] = base64.b64encode(payload_bytes).decode("ascii")
            kwargs["content_encoding"] = "base64"
            if not _pick_first_text(payload, ["file_name", "fileName"]):
                kwargs["file_name"] = local_path.name or kwargs["file_name"]
            return kwargs
        kwargs["file_url"] = normalized_file_url
        return kwargs

    if not callable(resolve_file_reference):
        raise ValueError("one of content, data_url, file_url is required")

    file_reference = resolve_file_reference(
        _pick_first_text(payload, ["attachment_id", "attachmentId"]) or None,
        _pick_first_text(payload, ["file_url", "fileUrl"]) or None,
        _pick_first_text(payload, ["file_path", "filePath"]) or None,
    )
    normalized_reference = str(file_reference or "").strip()
    lower_reference = normalized_reference.lower()
    if lower_reference.startswith("data:"):
        kwargs["data_url"] = normalized_reference
    elif lower_reference.startswith(("http://", "https://")):
        kwargs["file_url"] = normalized_reference
    else:
        local_path = Path(normalized_reference)
        payload_bytes = local_path.read_bytes()
        kwargs["content"] = base64.b64encode(payload_bytes).decode("ascii")
        kwargs["content_encoding"] = "base64"
        if not _pick_first_text(payload, ["file_name", "fileName"]):
            kwargs["file_name"] = local_path.name or kwargs["file_name"]
    return kwargs


def build_profile_payload_from_ingest(ingest_payload: Dict[str, Any]) -> Dict[str, Any]:
    analysis = ingest_payload.get("analysis")
    normalized_analysis = analysis if isinstance(analysis, dict) else {}
    summary = normalized_analysis.get("summary")
    normalized_summary = summary if isinstance(summary, dict) else {}

    columns = normalized_analysis.get("columns")
    normalized_columns = columns if isinstance(columns, list) else []
    column_names = []
    for item in normalized_columns:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("column") or "").strip()
            if name:
                column_names.append(name)

    row_count = int(normalized_summary.get("row_count") or 0)
    column_count = int(normalized_summary.get("column_count") or len(column_names))
    return {
        "summary": {
            "row_count": row_count,
            "column_count": column_count,
        },
        "columns": column_names,
        "source": {
            "file_name": str(ingest_payload.get("file_name") or ""),
            "file_format": str(ingest_payload.get("file_format") or ""),
            "source_type": str(ingest_payload.get("source_type") or ""),
        },
    }


def build_query_payload(
    *,
    profile_payload: Dict[str, Any],
    query_text: str,
) -> Dict[str, Any]:
    summary = profile_payload.get("summary")
    normalized_summary = summary if isinstance(summary, dict) else {}
    row_count = int(normalized_summary.get("row_count") or 0)
    column_count = int(normalized_summary.get("column_count") or 0)
    answer = (
        f"Query '{query_text}' executed on profiled sheet "
        f"({row_count} rows, {column_count} columns)."
    )
    return {
        "query": query_text,
        "answer": answer,
        "summary": {
            "row_count": row_count,
            "column_count": column_count,
        },
        "columns": profile_payload.get("columns") if isinstance(profile_payload.get("columns"), list) else [],
    }


def build_export_payload(
    *,
    query_payload: Dict[str, Any],
    user_id: str,
    export_format: str,
) -> Dict[str, Any]:
    normalized_export_format = str(export_format or "markdown").strip().lower()
    if normalized_export_format not in {"json", "markdown"}:
        normalized_export_format = "markdown"

    summary = query_payload.get("summary")
    normalized_summary = summary if isinstance(summary, dict) else {}
    precheck = validate_sheet_export_precheck(
        tenant_id=str(user_id or "").strip(),
        resource_tenant_id=str(user_id or "").strip(),
        payload_bytes=b"",
        analysis={
            "summary": normalized_summary,
            "columns": query_payload.get("columns") if isinstance(query_payload.get("columns"), list) else [],
            "query": query_payload.get("query"),
            "answer": query_payload.get("answer"),
        },
    )

    if normalized_export_format == "json":
        rendered = json.dumps(query_payload, ensure_ascii=False, sort_keys=True)
    else:
        rendered = (
            "# Sheet Query Result\n\n"
            f"- Query: {query_payload.get('query')}\n"
            f"- Answer: {query_payload.get('answer')}\n"
            f"- Rows: {normalized_summary.get('row_count')}\n"
            f"- Columns: {normalized_summary.get('column_count')}\n"
        )
    return {
        "export_format": normalized_export_format,
        "rendered": rendered,
        "export_precheck": precheck,
    }


async def execute_sheet_stage_protocol_request(
    *,
    request_body: Any,
    user_id: str,
    artifact_service: Optional[ADKArtifactService] = None,
    resolve_file_reference: Optional[SheetStageFileResolver] = None,
) -> Dict[str, Any]:
    payload = _request_to_payload(request_body)
    normalized_user_id = str(user_id or "").strip()
    requested_stage = _pick_first_text(payload, ["stage"]).lower()
    requested_session_id = _pick_first_text(payload, ["session_id", "sessionId"])
    protocol_version = _pick_first_text(payload, ["protocol_version", "protocolVersion"]) or SHEET_STAGE_PROTOCOL_VERSION
    active_artifact_service = artifact_service or get_default_sheet_stage_artifact_service()

    if protocol_version != SHEET_STAGE_PROTOCOL_VERSION:
        _raise_sheet_stage_protocol_error(
            status_code=400,
            stage=requested_stage,
            session_id=requested_session_id,
            message=(
                "unsupported protocol_version: "
                f"{protocol_version} (expected {SHEET_STAGE_PROTOCOL_VERSION})"
            ),
            error_code="SHEET_STAGE_PROTOCOL_UNSUPPORTED",
        )

    stage = normalize_sheet_stage(requested_stage)
    session_id, session_state = await _resolve_sheet_stage_session_or_raise(
        requested_session_id=requested_session_id,
        user_id=normalized_user_id,
        stage=stage,
        invocation_id=_pick_first_text(payload, ["invocation_id", "invocationId"]) or None,
        artifact_service=active_artifact_service,
    )

    if stage == "ingest":
        if _pick_first_value(payload, ["artifact"]) is not None:
            _raise_sheet_stage_protocol_error(
                status_code=400,
                stage=stage,
                session_id=session_id,
                message="artifact must not be provided for ingest stage",
                error_code="SHEET_STAGE_ARTIFACT_UNEXPECTED",
            )
        _ensure_sheet_stage_transition_or_raise(
            session_state=session_state,
            stage=stage,
            session_id=session_id,
        )
        ingest_policy_before = apply_row_level_policy_hook(
            stage=stage,
            before_after="before_tool",
            user_id=normalized_user_id,
            session_id=session_id,
            payload={
                "stage": stage,
                "file_name": _pick_first_text(payload, ["file_name", "fileName"]) or "sheet.csv",
                "tenant_id": normalized_user_id,
            },
            require_existing_chain=False,
        )
        sheet_analyze_tool = _resolve_sheet_analyze_tool()
        ingest_kwargs = build_sheet_ingest_kwargs_from_request(
            request_body=payload,
            user_id=normalized_user_id,
            resolve_file_reference=resolve_file_reference,
        )
        ingest_result = sheet_analyze_tool(**ingest_kwargs)
        if str(ingest_result.get("status") or "").strip().lower() != "success":
            _raise_sheet_stage_protocol_error(
                status_code=422,
                stage=stage,
                session_id=session_id,
                message=str(ingest_result.get("error") or "sheet ingest failed"),
                error_code="SHEET_STAGE_INGEST_FAILED",
            )
        ingest_payload = {
            "file_name": ingest_result.get("file_name"),
            "file_format": ingest_result.get("file_format"),
            "source_type": ingest_result.get("source_type"),
            "source_ref": ingest_result.get("source_ref"),
            "analysis": ingest_result.get("analysis") if isinstance(ingest_result.get("analysis"), dict) else {},
            "rendered": str(ingest_result.get("rendered") or ""),
            "export_precheck": ingest_result.get("export_precheck")
            if isinstance(ingest_result.get("export_precheck"), dict)
            else {},
        }
        ingest_policy_after = apply_row_level_policy_hook(
            stage=stage,
            before_after="after_tool",
            user_id=normalized_user_id,
            session_id=session_id,
            payload=ingest_payload,
            audit_chain=ingest_policy_before.get("policy_audit_chain"),
            require_existing_chain=True,
        )
        ingest_audit_chain = assert_stage_row_level_policy_pair(
            chain=ingest_policy_after.get("policy_audit_chain"),
            stage=stage,
        )
        ingest_payload = ingest_policy_after.get("payload") if isinstance(ingest_policy_after.get("payload"), dict) else ingest_payload
        ingest_payload["row_level_policy"] = ingest_policy_after.get("row_level")
        ingest_payload["policy_audit_chain"] = ingest_audit_chain
        artifact_ref, session_state = await _store_sheet_stage_artifact_or_raise(
            session_state=session_state,
            session_id=session_id,
            stage=stage,
            artifact_key=_SHEET_STAGE_OUTPUT_ARTIFACT_KEY[stage],
            payload=ingest_payload,
            parent_artifact_ref=None,
            artifact_service=active_artifact_service,
        )
        return build_sheet_stage_envelope(
            stage=stage,
            status="completed",
            session_id=session_id,
            protocol_version=SHEET_STAGE_PROTOCOL_VERSION,
            artifact=artifact_ref,
            data={
                "next_stage": "profile",
                "resume": {
                    "session_id": session_id,
                    "invocation_id": _pick_first_text(payload, ["invocation_id", "invocationId"]),
                },
                "payload": ingest_payload,
                "history": list(session_state.get("history") or []),
            },
        )

    input_artifact_key = _SHEET_STAGE_INPUT_ARTIFACT_KEY.get(stage, "")
    raw_artifact = _pick_first_value(payload, ["artifact"])
    normalized_input_artifact_ref = normalize_sheet_artifact_ref(raw_artifact, required=True)
    authorized_artifact_ref = _authorize_sheet_artifact_ref_or_raise(
        stage=stage,
        session_id=session_id,
        user_id=normalized_user_id,
        raw_artifact_ref=raw_artifact,
        normalized_artifact_ref=normalized_input_artifact_ref or {},
    )
    input_artifact_ref = validate_sheet_artifact_binding(
        artifact_ref=authorized_artifact_ref,
        expected_session_id=session_id,
        expected_artifact_key=input_artifact_key,
    )
    _ensure_sheet_stage_transition_or_raise(
        session_state=session_state,
        stage=stage,
        session_id=session_id,
    )
    _ensure_sheet_stage_artifact_fresh_or_raise(
        session_state=session_state,
        stage=stage,
        session_id=session_id,
        artifact_ref=input_artifact_ref,
    )
    source_payload = await _load_sheet_stage_artifact_or_raise(
        stage=stage,
        session_id=session_id,
        user_id=normalized_user_id,
        artifact_ref=input_artifact_ref,
        artifact_service=active_artifact_service,
    )
    row_level_before = apply_row_level_policy_hook(
        stage=stage,
        before_after="before_tool",
        user_id=normalized_user_id,
        session_id=session_id,
        payload=source_payload,
        audit_chain=source_payload.get("policy_audit_chain") if isinstance(source_payload, dict) else None,
        require_existing_chain=True,
    )
    source_payload = row_level_before.get("payload") if isinstance(row_level_before.get("payload"), dict) else source_payload

    if stage == "profile":
        stage_payload = build_profile_payload_from_ingest(source_payload)
        next_stage = "query"
    elif stage == "query":
        query_text = _pick_first_text(payload, ["query"])
        if not query_text:
            _raise_sheet_stage_protocol_error(
                status_code=400,
                stage=stage,
                session_id=session_id,
                message="query is required for query stage",
                error_code="SHEET_STAGE_QUERY_REQUIRED",
            )
        stage_payload = build_query_payload(
            profile_payload=source_payload,
            query_text=query_text,
        )
        next_stage = "export"
    elif stage == "export":
        stage_payload = build_export_payload(
            query_payload=source_payload,
            user_id=normalized_user_id,
            export_format=_pick_first_text(payload, ["export_format", "exportFormat"]) or "markdown",
        )
        next_stage = "export"
    else:
        _raise_sheet_stage_protocol_error(
            status_code=400,
            stage=stage,
            session_id=session_id,
            message=f"unsupported stage: {stage}",
            error_code="SHEET_STAGE_UNSUPPORTED",
        )

    row_level_after = apply_row_level_policy_hook(
        stage=stage,
        before_after="after_tool",
        user_id=normalized_user_id,
        session_id=session_id,
        payload=stage_payload,
        audit_chain=row_level_before.get("policy_audit_chain"),
        require_existing_chain=True,
    )
    stage_policy_chain = assert_stage_row_level_policy_pair(
        chain=row_level_after.get("policy_audit_chain"),
        stage=stage,
    )
    stage_payload = row_level_after.get("payload") if isinstance(row_level_after.get("payload"), dict) else stage_payload
    stage_payload["row_level_policy"] = row_level_after.get("row_level")
    stage_payload["policy_audit_chain"] = stage_policy_chain

    if stage == "export":
        export_constraint = enforce_sheet_export_constraint(
            user_id=normalized_user_id,
            session_id=session_id,
            artifact_ref=input_artifact_ref,
            source_payload=source_payload,
            output_payload=stage_payload,
            policy_audit_chain=stage_payload.get("policy_audit_chain"),
            export_format=str(stage_payload.get("export_format") or _pick_first_text(payload, ["export_format", "exportFormat"]) or "markdown"),
            resource_tenant_id=normalized_user_id,
        )
        stage_payload["export_constraint"] = export_constraint.get("export_constraint")
        stage_payload["policy_audit_chain"] = export_constraint.get("policy_audit_chain")

    output_artifact_ref, session_state = await _store_sheet_stage_artifact_or_raise(
        session_state=session_state,
        session_id=session_id,
        stage=stage,
        artifact_key=_SHEET_STAGE_OUTPUT_ARTIFACT_KEY[stage],
        payload=stage_payload,
        parent_artifact_ref=input_artifact_ref,
        artifact_service=active_artifact_service,
    )
    return build_sheet_stage_envelope(
        stage=stage,
        status="completed",
        session_id=session_id,
        protocol_version=SHEET_STAGE_PROTOCOL_VERSION,
        artifact=output_artifact_ref,
        data={
            "input_artifact": input_artifact_ref,
            "next_stage": next_stage,
            "resume": {
                "session_id": session_id,
                "invocation_id": _pick_first_text(payload, ["invocation_id", "invocationId"]),
            },
            "payload": stage_payload,
            "history": list(session_state.get("history") or []),
        },
    )


__all__ = [
    "SHEET_STAGE_PROTOCOL_VERSION",
    "SheetStageProtocolError",
    "build_export_payload",
    "build_profile_payload_from_ingest",
    "build_query_payload",
    "build_sheet_ingest_kwargs_from_request",
    "build_sheet_stage_failure_detail",
    "execute_sheet_stage_protocol_request",
    "extract_sheet_stage_summary_text",
    "get_default_sheet_stage_artifact_service",
    "get_default_sheet_stage_runtime_store",
]
