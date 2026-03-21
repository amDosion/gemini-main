"""Built-in tools for ADK agents."""

from __future__ import annotations

import base64
import binascii
import importlib.util
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote_to_bytes, urlparse

import httpx

from ...utils.url_security import UnsafeURLError, resolve_safe_redirect_url, validate_outbound_http_url

logger = logging.getLogger(__name__)

_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 20.0
_TABLE_ANALYSIS_MODULE_CACHE: Any = None
SHEET_STAGE_PROTOCOL_VERSION = "sheet-stage/v1"
_SHEET_STAGE_ALLOWED = {"ingest", "profile", "query", "export"}
_SHEET_STAGE_STATUS_ALLOWED = {"completed", "failed"}
_SHEET_ALLOWED_HOSTS_ENV = "ADK_SHEET_ALLOWED_HOSTS"
_SHEET_EXPORT_SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "ssn",
    "social_security",
    "credit_card",
    "bank_account",
    "身份证",
    "护照",
    "银行卡",
)


def _load_table_analysis_module() -> Any:
    global _TABLE_ANALYSIS_MODULE_CACHE
    if _TABLE_ANALYSIS_MODULE_CACHE is not None:
        return _TABLE_ANALYSIS_MODULE_CACHE

    module_path = Path(__file__).resolve().parents[1] / "common" / "table_analysis_service.py"
    spec = importlib.util.spec_from_file_location("adk_table_analysis_service", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load table_analysis_service module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _TABLE_ANALYSIS_MODULE_CACHE = module
    return module


def _clamp_sample_rows(value: Any, default: int = 5) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(1, min(parsed, 100))


def _normalize_sheet_name(value: Any) -> str | int | None:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return text


def _guess_file_name(url_or_name: str, fallback: str = "sheet.csv") -> str:
    raw = str(url_or_name or "").strip()
    if not raw:
        return fallback
    parsed = urlparse(raw)
    candidate = Path(parsed.path if parsed.scheme else raw).name
    return candidate or fallback


def _guess_file_format(*, file_name: str, explicit_file_format: Optional[str], mime_type: Optional[str]) -> Optional[str]:
    if explicit_file_format:
        normalized = str(explicit_file_format).strip().lower()
        if normalized in {"csv", "xlsx"}:
            return normalized

    suffix = Path(str(file_name or "")).suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm", ".xlsb"}:
        return "xlsx"
    if suffix in {".csv", ".tsv"}:
        return "csv"

    normalized_mime = str(mime_type or "").strip().lower()
    if "spreadsheetml" in normalized_mime or "application/vnd.ms-excel" in normalized_mime:
        return "xlsx"
    if "text/csv" in normalized_mime or "text/plain" in normalized_mime:
        return "csv"
    return None


def _decode_data_url(data_url: str) -> Tuple[bytes, str]:
    raw = str(data_url or "").strip()
    if not raw.startswith("data:") or "," not in raw:
        raise ValueError("invalid data URL")
    header, payload = raw.split(",", 1)
    mime_type = str(header[5:].split(";", 1)[0] or "").strip().lower()
    if ";base64" in header.lower():
        try:
            return base64.b64decode(payload, validate=False), mime_type
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid base64 data URL payload") from exc
    return unquote_to_bytes(payload), mime_type


def _resolve_allowed_sheet_hosts() -> List[str]:
    raw = str(os.getenv(_SHEET_ALLOWED_HOSTS_ENV, "") or "").strip()
    if not raw:
        return []

    normalized_hosts: List[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        raw_item = str(item or "").strip()
        candidate = raw_item.lower()
        if not candidate:
            continue
        if "://" in candidate:
            parsed = urlparse(candidate)
            candidate = str(parsed.hostname or "").strip().lower()
        if candidate.startswith("*."):
            candidate = f".{candidate[2:]}"
        candidate = candidate.strip(".")
        if not candidate:
            continue
        if raw_item.startswith("*.") or raw_item.startswith("."):
            candidate = f".{candidate}"
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized_hosts.append(candidate)
    return normalized_hosts


def _is_allowed_sheet_host(hostname: str, allowed_hosts: List[str]) -> bool:
    normalized_host = str(hostname or "").strip().strip(".").lower()
    if not normalized_host:
        return False
    for allowed in allowed_hosts:
        rule = str(allowed or "").strip().lower()
        if not rule:
            continue
        if rule.startswith("."):
            suffix = rule[1:]
            if normalized_host == suffix or normalized_host.endswith(f".{suffix}"):
                return True
            continue
        if normalized_host == rule:
            return True
    return False


def _validate_sheet_file_url_allowlist(url: str, allowed_hosts: List[str]) -> None:
    host = str(urlparse(str(url or "").strip()).hostname or "").strip().lower()
    if not allowed_hosts:
        raise UnsafeURLError(
            f"remote file_url host allowlist is empty; set {_SHEET_ALLOWED_HOSTS_ENV}"
        )
    if not _is_allowed_sheet_host(host, allowed_hosts):
        raise UnsafeURLError(
            f"host '{host}' is not in {_SHEET_ALLOWED_HOSTS_ENV} allowlist"
        )


def _iter_sheet_security_strings(value: Any) -> List[str]:
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
            chunks.extend(_iter_sheet_security_strings(str(key)))
            chunks.extend(_iter_sheet_security_strings(nested))
        return chunks
    if isinstance(value, (list, tuple, set)):
        chunks: List[str] = []
        for nested in value:
            chunks.extend(_iter_sheet_security_strings(nested))
        return chunks
    return [str(value)]


def _scan_sheet_sensitive_keywords(*, payload_bytes: bytes, analysis: Any) -> List[str]:
    chunks: List[str] = []
    if payload_bytes:
        try:
            decoded = payload_bytes.decode("utf-8", errors="ignore")
        except Exception:
            decoded = ""
        if decoded.strip():
            chunks.append(decoded)

    chunks.extend(_iter_sheet_security_strings(analysis))
    normalized_haystack = "\n".join(chunk for chunk in chunks if chunk).lower()
    if not normalized_haystack:
        return []

    hits: List[str] = []
    for keyword in _SHEET_EXPORT_SENSITIVE_KEYWORDS:
        needle = str(keyword or "").strip()
        if not needle:
            continue
        if re.search(re.escape(needle.lower()), normalized_haystack):
            hits.append(needle)
    return sorted(set(hits))


def _normalize_sheet_protocol_version(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return SHEET_STAGE_PROTOCOL_VERSION
    if normalized != SHEET_STAGE_PROTOCOL_VERSION:
        raise ValueError(
            f"unsupported protocol_version: {normalized} (expected {SHEET_STAGE_PROTOCOL_VERSION})"
        )
    return normalized


def normalize_sheet_stage(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _SHEET_STAGE_ALLOWED:
        raise ValueError(
            f"invalid stage: {value!r}; expected one of {sorted(_SHEET_STAGE_ALLOWED)}"
        )
    return normalized


def _coerce_sheet_artifact_version(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("artifact_version must be a positive integer")
    if isinstance(value, (int, float)):
        version = int(value)
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("artifact_version is required")
        try:
            version = int(float(text))
        except Exception as exc:
            raise ValueError("artifact_version must be a positive integer") from exc
    if version <= 0:
        raise ValueError("artifact_version must be >= 1")
    return version


def normalize_sheet_artifact_ref(
    value: Any,
    *,
    required: bool = False,
) -> Optional[Dict[str, Any]]:
    if value is None:
        if required:
            raise ValueError("artifact reference is required")
        return None
    if not isinstance(value, dict):
        raise ValueError("artifact reference must be an object")

    artifact_key = str(
        value.get("artifact_key")
        or value.get("artifactKey")
        or ""
    ).strip()
    if not artifact_key:
        raise ValueError("artifact_key is required")

    artifact_version = _coerce_sheet_artifact_version(
        value.get("artifact_version", value.get("artifactVersion"))
    )
    artifact_session_id = str(
        value.get("artifact_session_id")
        or value.get("artifactSessionId")
        or ""
    ).strip()
    if not artifact_session_id:
        raise ValueError("artifact_session_id is required")

    return {
        "artifact_key": artifact_key,
        "artifact_version": artifact_version,
        "artifact_session_id": artifact_session_id,
    }


def validate_sheet_artifact_binding(
    *,
    artifact_ref: Any,
    expected_session_id: str,
    expected_artifact_key: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_ref = normalize_sheet_artifact_ref(artifact_ref, required=True) or {}
    normalized_expected_session_id = str(expected_session_id or "").strip()
    if not normalized_expected_session_id:
        raise ValueError("expected_session_id is required")

    if normalized_ref.get("artifact_session_id") != normalized_expected_session_id:
        raise ValueError(
            "artifact_session_id binding mismatch "
            f"({normalized_ref.get('artifact_session_id')} != {normalized_expected_session_id})"
        )

    normalized_expected_key = str(expected_artifact_key or "").strip()
    if normalized_expected_key:
        current_key = str(normalized_ref.get("artifact_key") or "")
        if current_key != normalized_expected_key:
            raise ValueError(
                "artifact_key binding mismatch "
                f"({current_key} != {normalized_expected_key})"
            )

    return normalized_ref


def build_sheet_stage_envelope(
    *,
    stage: Any,
    status: Any,
    session_id: Any,
    protocol_version: Any = SHEET_STAGE_PROTOCOL_VERSION,
    artifact: Any = None,
    data: Any = None,
    error: Any = None,
) -> Dict[str, Any]:
    normalized_protocol_version = _normalize_sheet_protocol_version(protocol_version)
    normalized_stage = normalize_sheet_stage(stage)
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in _SHEET_STAGE_STATUS_ALLOWED:
        raise ValueError(
            f"invalid status: {status!r}; expected one of {sorted(_SHEET_STAGE_STATUS_ALLOWED)}"
        )
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("session_id is required")

    normalized_artifact = normalize_sheet_artifact_ref(artifact, required=False)
    envelope: Dict[str, Any] = {
        "protocol_version": normalized_protocol_version,
        "stage": normalized_stage,
        "status": normalized_status,
        "session_id": normalized_session_id,
        "artifact": normalized_artifact,
    }
    if data is not None:
        envelope["data"] = data
    if error is not None:
        if isinstance(error, dict):
            envelope["error"] = error
        else:
            envelope["error"] = {"message": str(error)}
    return envelope


def validate_sheet_export_precheck(
    *,
    tenant_id: Optional[str],
    resource_tenant_id: Optional[str],
    payload_bytes: bytes,
    analysis: Any,
) -> Dict[str, Any]:
    normalized_tenant_id = str(tenant_id or "").strip()
    normalized_resource_tenant_id = str(resource_tenant_id or "").strip()

    if normalized_tenant_id and normalized_resource_tenant_id and normalized_tenant_id != normalized_resource_tenant_id:
        raise PermissionError(
            "sheet export precheck failed: tenant binding mismatch "
            f"({normalized_tenant_id} != {normalized_resource_tenant_id})"
        )

    sensitive_hits = _scan_sheet_sensitive_keywords(payload_bytes=payload_bytes, analysis=analysis)
    if sensitive_hits:
        raise ValueError(
            "sheet export precheck failed: sensitive fields detected "
            f"({', '.join(sensitive_hits)})"
        )

    return {
        "status": "passed",
        "tenant_id": normalized_tenant_id or normalized_resource_tenant_id or "",
        "sensitive_hits": sensitive_hits,
    }


def _download_remote_file(file_url: str) -> Tuple[bytes, str, str]:
    allowed_hosts = _resolve_allowed_sheet_hosts()
    current_url = validate_outbound_http_url(str(file_url or "").strip())
    _validate_sheet_file_url_allowlist(current_url, allowed_hosts)
    redirect_count = 0
    with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
        while True:
            response = client.get(
                current_url,
                headers={
                    "User-Agent": "ADKSheetAnalyzeTool/1.0",
                    "Accept": "text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
                },
            )
            if response.status_code in _REDIRECT_STATUS_CODES:
                if redirect_count >= _MAX_REDIRECTS:
                    raise ValueError(f"redirects exceeded limit ({_MAX_REDIRECTS})")
                current_url = resolve_safe_redirect_url(current_url, response.headers.get("location", ""))
                _validate_sheet_file_url_allowlist(current_url, allowed_hosts)
                redirect_count += 1
                continue
            response.raise_for_status()
            payload = response.content
            if len(payload) > _MAX_DOWNLOAD_BYTES:
                raise ValueError(f"remote file too large (> {_MAX_DOWNLOAD_BYTES} bytes)")
            content_type = str(response.headers.get("content-type") or "application/octet-stream")
            return payload, current_url, content_type


def build_adk_builtin_tools() -> List[Callable[..., Dict[str, Any]]]:
    """
    Build default tool list for ADK agents.

    当前包含：
    - sheet_analyze: CSV/XLSX 表格分析（inline/data_url/remote_url）
    """

    def sheet_analyze(
        *,
        file_name: str = "sheet.csv",
        file_format: Optional[str] = None,
        file_url: Optional[str] = None,
        data_url: Optional[str] = None,
        content: Optional[str] = None,
        content_encoding: str = "plain",
        csv_encoding: str = "utf-8",
        sheet_name: Optional[Any] = 0,
        sample_rows: int = 5,
        export_format: str = "markdown",
        tenant_id: Optional[str] = None,
        resource_tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a spreadsheet (CSV/XLSX) and return structured insights.

        Usage priority:
        1) `content` (inline CSV text or base64 payload)
        2) `data_url` (data:* URL)
        3) `file_url` (http/https remote file)
        """
        table_analysis_error_cls: Any = Exception
        try:
            table_analysis_module = _load_table_analysis_module()
            table_analysis_error_cls = getattr(table_analysis_module, "TableAnalysisError", Exception)
            analyze_table_bytes_fn = getattr(table_analysis_module, "analyze_table_bytes", None)
            export_table_analysis_fn = getattr(table_analysis_module, "export_table_analysis", None)
            if not callable(analyze_table_bytes_fn) or not callable(export_table_analysis_fn):
                raise RuntimeError("table analysis module does not expose required functions")

            normalized_file_name = _guess_file_name(file_name)
            normalized_sample_rows = _clamp_sample_rows(sample_rows)
            normalized_sheet_name = _normalize_sheet_name(sheet_name)
            normalized_content_encoding = str(content_encoding or "plain").strip().lower()
            if normalized_content_encoding not in {"plain", "base64"}:
                normalized_content_encoding = "plain"

            payload_bytes: Optional[bytes] = None
            source_type = "inline"
            source_ref = ""
            mime_type = ""

            if str(content or "").strip():
                source_type = "inline"
                source_ref = "content"
                if normalized_content_encoding == "base64":
                    payload_bytes = base64.b64decode(str(content).strip(), validate=False)
                else:
                    payload_bytes = str(content).encode(str(csv_encoding or "utf-8"))
            elif str(data_url or "").strip():
                source_type = "data_url"
                source_ref = "data_url"
                payload_bytes, mime_type = _decode_data_url(str(data_url))
                if not normalized_file_name or normalized_file_name == "sheet.csv":
                    normalized_file_name = "sheet.xlsx" if "excel" in mime_type or "spreadsheet" in mime_type else "sheet.csv"
            elif str(file_url or "").strip():
                source_type = "remote_url"
                payload_bytes, source_ref, mime_type = _download_remote_file(str(file_url))
                if not normalized_file_name or normalized_file_name == "sheet.csv":
                    normalized_file_name = _guess_file_name(source_ref, fallback=normalized_file_name)
            else:
                raise ValueError("one of content, data_url, file_url is required")

            inferred_format = _guess_file_format(
                file_name=normalized_file_name,
                explicit_file_format=file_format,
                mime_type=mime_type,
            )
            if inferred_format is None:
                raise ValueError("unable to infer table format; provide file_format=csv|xlsx")

            analysis = analyze_table_bytes_fn(
                payload_bytes or b"",
                file_name=normalized_file_name,
                file_format=inferred_format,
                sample_rows=normalized_sample_rows,
                csv_encoding=str(csv_encoding or "utf-8"),
                sheet_name=normalized_sheet_name,
            )
            precheck = validate_sheet_export_precheck(
                tenant_id=tenant_id,
                resource_tenant_id=resource_tenant_id,
                payload_bytes=payload_bytes or b"",
                analysis=analysis,
            )
            normalized_export_format = str(export_format or "markdown").strip().lower()
            if normalized_export_format not in {"json", "markdown"}:
                normalized_export_format = "markdown"
            rendered = export_table_analysis_fn(analysis=analysis, export_format=normalized_export_format)
            if isinstance(rendered, str):
                rendered_text = rendered
            else:
                rendered_text = json.dumps(rendered, ensure_ascii=False, indent=2)

            return {
                "status": "success",
                "tool": "sheet_analyze",
                "source_type": source_type,
                "source_ref": source_ref or source_type,
                "file_name": normalized_file_name,
                "file_format": inferred_format,
                "export_precheck": precheck,
                "analysis": analysis,
                "rendered": rendered,
                "summaryText": rendered_text,
                "text": rendered_text,
            }
        except UnsafeURLError as exc:
            return {
                "status": "failed",
                "tool": "sheet_analyze",
                "error": f"unsafe file_url: {exc}",
            }
        except table_analysis_error_cls as exc:
            return {
                "status": "failed",
                "tool": "sheet_analyze",
                "error": str(exc),
            }
        except httpx.HTTPStatusError as exc:
            return {
                "status": "failed",
                "tool": "sheet_analyze",
                "error": f"http status {exc.response.status_code}",
            }
        except httpx.RequestError as exc:
            return {
                "status": "failed",
                "tool": "sheet_analyze",
                "error": f"http request failed: {exc}",
            }
        except PermissionError as exc:
            return {
                "status": "failed",
                "tool": "sheet_analyze",
                "error": str(exc),
            }
        except Exception as exc:
            logger.warning("[ADKBuiltInTools] sheet_analyze failed: %s", exc, exc_info=True)
            return {
                "status": "failed",
                "tool": "sheet_analyze",
                "error": str(exc),
            }

    return [sheet_analyze]


__all__ = [
    "SHEET_STAGE_PROTOCOL_VERSION",
    "build_adk_builtin_tools",
    "build_sheet_stage_envelope",
    "normalize_sheet_artifact_ref",
    "normalize_sheet_stage",
    "validate_sheet_artifact_binding",
    "validate_sheet_export_precheck",
]
