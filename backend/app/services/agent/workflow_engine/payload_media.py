"""
Payload, reference, and result-media helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import mimetypes
import re
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from ...gemini.base.video_common import is_google_provider_video_uri
from ..execution_context import ExecutionContext

logger = logging.getLogger(__name__)


def looks_like_excel_binary(engine: Any, mime_type: str = "", file_name: str = "") -> bool:
    _ = engine
    ext = Path(str(file_name or "").split("?", 1)[0]).suffix.lower()
    if ext in {".xlsx", ".xls", ".xlsm", ".xlsb"}:
        return True
    lowered = str(mime_type or "").lower()
    return any(
        token in lowered
        for token in (
            "spreadsheetml",
            "ms-excel",
            "officedocument.spreadsheet",
            "application/vnd.ms-excel",
        )
    )


def parse_reference_ip_host(
    engine: Any,
    hostname: str,
) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    _ = engine
    host = str(hostname or "").strip()
    if not host:
        return None
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        packed = socket.inet_aton(host)
        return ipaddress.IPv4Address(packed)
    except OSError:
        return None


def is_disallowed_reference_ip(
    engine: Any,
    ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    if ip_obj in engine.REFERENCE_METADATA_IPS:
        return True
    return any(
        (
            ip_obj.is_private,
            ip_obj.is_loopback,
            ip_obj.is_link_local,
            ip_obj.is_multicast,
            ip_obj.is_reserved,
            ip_obj.is_unspecified,
        )
    )


def is_disallowed_reference_hostname(engine: Any, hostname: str) -> bool:
    normalized = str(hostname or "").strip().strip(".").lower()
    if not normalized:
        return True
    if normalized in engine.REFERENCE_METADATA_HOSTS:
        return True
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    if normalized.startswith("metadata."):
        return True
    return False


def resolve_generic_path(engine: Any, data: Any, path: str) -> Any:
    _ = engine
    if not path:
        return data
    normalized = re.sub(r"\[(\d+)\]", r".\1", path)
    parts = [part for part in normalized.split(".") if part != ""]
    current = data
    for part in parts:
        if isinstance(current, list):
            if not part.isdigit():
                return None
            idx = int(part)
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
            continue
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        return None
    return current


def normalize_possible_image_url(engine: Any, value: Any, key_hint: str = "") -> Optional[str]:
    _ = engine
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    lower = text.lower()
    if lower.startswith("data:image/"):
        return text
    if lower.startswith("blob:"):
        return text
    if lower.startswith("oss://"):
        return text
    if lower.startswith("file://"):
        return text

    compact = text.replace("\n", "").replace("\r", "")
    if (
        len(compact) >= 128
        and re.fullmatch(r"[A-Za-z0-9+/=]+", compact)
        and " " not in compact
    ):
        return f"data:image/png;base64,{compact}"

    if not (
        lower.startswith("http://")
        or lower.startswith("https://")
        or lower.startswith("/")
        or lower.startswith("file://")
    ):
        return None

    hint = (key_hint or "").lower()
    if "image" in hint:
        return text

    normalized_path = lower.split("?", 1)[0].split("#", 1)[0]
    if re.search(r"\.(png|jpg|jpeg|webp|gif|bmp|svg)$", normalized_path):
        return text
    if any(token in normalized_path for token in ("/image", "/images", "/attachments", "/uploads", "/generated", "/edited", "/expanded")):
        return text
    return None


def normalize_possible_file_url(engine: Any, value: Any) -> Optional[str]:
    _ = engine
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    lower = text.lower()
    if "{{" in text or "}}" in text:
        return None
    if lower.startswith("data:"):
        return text
    if (
        lower.startswith("http://")
        or lower.startswith("https://")
        or lower.startswith("oss://")
        or lower.startswith("file://")
        or lower.startswith("/")
    ):
        return text
    return text


def normalize_possible_result_media_url(engine: Any, value: Any) -> Optional[str]:
    _ = engine
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None

    lower = text.lower()
    if "{{" in text or "}}" in text:
        return None
    if lower.startswith("data:"):
        return text
    if is_google_provider_video_uri(text):
        return text
    if lower.startswith(("http://", "https://", "oss://")):
        return text
    if text.startswith("/api/"):
        return text
    return None


def normalize_reference_image_for_provider(engine: Any, source_image_url: str, provider_id: str) -> str:
    raw_value = str(source_image_url or "").strip()
    if not raw_value:
        return raw_value

    lowered_provider = str(provider_id or "").lower()
    is_google = lowered_provider.startswith("google")
    is_tongyi = lowered_provider.startswith("tongyi") or lowered_provider.startswith("dashscope")
    if not is_google and not is_tongyi:
        return raw_value

    if raw_value.lower().startswith("data:image/"):
        return raw_value

    if is_tongyi and raw_value.lower().startswith(("http://", "https://", "oss://")):
        return raw_value
    parsed = urlparse(raw_value)
    maybe_ref = parsed.scheme in ("http", "https", "file") or raw_value.startswith("/")
    if not maybe_ref:
        candidate = Path(raw_value).expanduser()
        if not candidate.exists() or not candidate.is_file():
            return raw_value

    try:
        binary, mime_type, file_name = engine._load_binary_from_reference(raw_value)
        normalized_mime = str(mime_type or "").strip().lower()
        if not normalized_mime.startswith("image/"):
            guessed, _ = mimetypes.guess_type(file_name or "")
            guessed = str(guessed or "").strip().lower()
            if guessed.startswith("image/"):
                normalized_mime = guessed
        if not normalized_mime.startswith("image/"):
            normalized_mime = "image/png"

        encoded = base64.b64encode(binary).decode("ascii")
        return f"data:{normalized_mime};base64,{encoded}"
    except Exception as exc:
        logger.warning(
            "[WorkflowEngine] Failed to normalize reference image for provider %s: %s",
            provider_id,
            exc,
        )
        return raw_value


def guess_image_mime_type_from_reference(engine: Any, reference: str) -> str:
    _ = engine
    raw = str(reference or "").strip()
    if not raw:
        return "image/png"
    lowered = raw.lower()
    if lowered.startswith("data:image/"):
        header = raw.split(",", 1)[0]
        mime_type = str(header.split(":", 1)[1].split(";", 1)[0] if ":" in header else "").strip().lower()
        if mime_type.startswith("image/"):
            return mime_type
        return "image/png"

    parsed = urlparse(raw)
    if parsed.scheme == "file":
        guessed = str(mimetypes.guess_type(parsed.path)[0] or "").strip().lower()
    else:
        guessed = str(mimetypes.guess_type(raw)[0] or "").strip().lower()
    if guessed.startswith("image/"):
        return guessed
    return "image/png"


def extract_all_image_urls(engine: Any, payload: Any) -> List[str]:
    urls: List[str] = []
    seen: Set[str] = set()

    def walk(value: Any, key_hint: str = ""):
        normalized = engine._normalize_possible_image_url(value, key_hint=key_hint)
        if normalized and normalized not in seen:
            seen.add(normalized)
            urls.append(normalized)

        if isinstance(value, list):
            for item in value:
                walk(item, key_hint=key_hint)
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, key_hint=str(key))

    walk(payload)
    return urls


def extract_result_image_urls(engine: Any, payload: Any) -> List[str]:
    urls: List[str] = []
    seen: Set[str] = set()

    def push(candidate: Any, key_hint: str = ""):
        normalized = engine._normalize_possible_image_url(candidate, key_hint=key_hint)
        if normalized and normalized not in seen:
            seen.add(normalized)
            urls.append(normalized)

    def push_image_items(items: Any):
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    push(item.get("url"), key_hint="imageUrl")
                    push(item.get("imageUrl"), key_hint="imageUrl")
                    push(item.get("image_url"), key_hint="image_url")
                else:
                    push(item, key_hint="imageUrl")
            return
        if items is not None:
            push(items, key_hint="imageUrls")

    if isinstance(payload, dict):
        push(payload.get("imageUrl"), key_hint="imageUrl")
        push(payload.get("image_url"), key_hint="image_url")
        push_image_items(payload.get("imageUrls"))
        push_image_items(payload.get("image_urls"))
        push_image_items(payload.get("images"))
        if urls:
            return urls

    return engine._extract_all_image_urls(payload)


def extract_first_image_url(engine: Any, payload: Any) -> Optional[str]:
    urls = engine._extract_all_image_urls(payload)
    return urls[0] if urls else None


def extract_first_video_url(engine: Any, payload: Any) -> Optional[str]:
    candidates: List[Any] = []

    if isinstance(payload, dict):
        direct_candidates = [
            payload.get("videoUrl"),
            payload.get("video_url"),
        ]
        payload_mime_type = str(payload.get("mimeType") or payload.get("mime_type") or "").strip().lower()
        if payload_mime_type.startswith("video/") and payload.get("url") is not None:
            direct_candidates.append(payload.get("url"))
        for item in direct_candidates:
            if item is not None:
                candidates.append(item)
        for key in ("videoUrls", "video_urls", "videos", "resultPreviewVideoUrls"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif value is not None:
                candidates.append(value)

    if not candidates:
        candidates = [payload]

    for candidate in candidates:
        if isinstance(candidate, dict):
            nested = (
                candidate.get("videoUrl")
                or candidate.get("video_url")
                or candidate.get("url")
            )
            normalized = engine._normalize_possible_result_media_url(nested)
            if normalized:
                return normalized
            continue

        normalized = engine._normalize_possible_result_media_url(candidate)
        if normalized:
            return normalized

    return None


def build_source_video_payload(engine: Any, payload: Any) -> Any:
    def _pack_video_payload(raw_payload: Dict[str, Any]) -> Any:
        video_url = engine._extract_first_video_url(raw_payload)
        provider_file_name = str(
            raw_payload.get("provider_file_name")
            or raw_payload.get("providerFileName")
            or ""
        ).strip()
        provider_file_uri = str(
            raw_payload.get("provider_file_uri")
            or raw_payload.get("providerFileUri")
            or ""
        ).strip()
        gcs_uri = str(raw_payload.get("gcs_uri") or raw_payload.get("gcsUri") or "").strip()
        mime_type = str(raw_payload.get("mime_type") or raw_payload.get("mimeType") or "").strip()

        if not provider_file_name and provider_file_uri.startswith("files/"):
            provider_file_name = provider_file_uri

        if video_url or provider_file_name or provider_file_uri or gcs_uri or mime_type:
            normalized_payload: Dict[str, Any] = {}
            if video_url:
                normalized_payload["url"] = video_url
            if provider_file_name:
                normalized_payload["provider_file_name"] = provider_file_name
            if provider_file_uri:
                normalized_payload["provider_file_uri"] = provider_file_uri
            if gcs_uri:
                normalized_payload["gcs_uri"] = gcs_uri
            if mime_type:
                normalized_payload["mime_type"] = mime_type
            if len(normalized_payload) == 1 and "url" in normalized_payload:
                return normalized_payload["url"]
            return normalized_payload

        for nested_key in ("source_video", "sourceVideo", "input", "raw"):
            nested_value = raw_payload.get(nested_key)
            if nested_value is None:
                continue
            nested_payload = engine._build_source_video_payload(nested_value)
            if nested_payload is not None:
                return nested_payload
        return None

    if payload is None:
        return None

    if isinstance(payload, list):
        for item in payload:
            normalized_item = engine._build_source_video_payload(item)
            if normalized_item is not None:
                return normalized_item
        return None

    if isinstance(payload, dict):
        return _pack_video_payload(payload)

    if not isinstance(payload, str):
        return None

    text = payload.strip()
    if not text or "{{" in text or "}}" in text:
        return None

    normalized = engine._extract_first_video_url(text)
    if normalized:
        return normalized
    return text


def resolve_agent_reference_image_url(
    engine: Any,
    node_data: Dict[str, Any],
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
) -> str:
    raw_ref = (
        node_data.get("agentReferenceImageUrl")
        or node_data.get("agent_reference_image_url")
        or ""
    )
    if str(raw_ref or "").strip():
        resolved = context.resolve_template(raw_ref) if isinstance(raw_ref, str) and "{{" in raw_ref else raw_ref
        normalized = engine._normalize_possible_image_url(resolved, key_hint="imageUrl")
        if normalized:
            return normalized
        if isinstance(resolved, str) and resolved.strip():
            return resolved.strip()

    for packet in reversed(input_packets or []):
        candidate = engine._extract_first_image_url((packet or {}).get("output"))
        if candidate:
            return candidate

    return engine._extract_first_image_url(initial_input) or ""


def resolve_agent_source_video_input(
    engine: Any,
    node_data: Dict[str, Any],
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
) -> Any:
    raw_ref = (
        node_data.get("agentSourceVideoUrl")
        or node_data.get("agent_source_video_url")
        or ""
    )
    if str(raw_ref or "").strip():
        resolved = context.resolve_template(raw_ref) if isinstance(raw_ref, str) and "{{" in raw_ref else raw_ref
        normalized_payload = engine._build_source_video_payload(resolved)
        if normalized_payload is not None:
            return normalized_payload

    continue_from_previous = engine._to_bool(
        node_data.get("agentContinueFromPreviousVideo", node_data.get("agent_continue_from_previous_video")),
        default=False,
    )
    continue_from_previous_last_frame = engine._to_bool(
        node_data.get(
            "agentContinueFromPreviousLastFrame",
            node_data.get("agent_continue_from_previous_last_frame"),
        ),
        default=False,
    )
    if not continue_from_previous and not continue_from_previous_last_frame:
        return None

    for packet in reversed(input_packets or []):
        candidate = engine._build_source_video_payload((packet or {}).get("output"))
        if candidate is not None:
            return candidate

    return engine._build_source_video_payload(initial_input)


def resolve_agent_source_video_url(
    engine: Any,
    node_data: Dict[str, Any],
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
) -> str:
    resolved = engine._resolve_agent_source_video_input(
        node_data=node_data,
        context=context,
        initial_input=initial_input,
        input_packets=input_packets,
    )
    normalized = engine._extract_first_video_url(resolved)
    if normalized:
        return normalized
    if isinstance(resolved, str):
        return resolved
    return ""


def get_tool_arg(engine: Any, tool_args: Dict[str, Any], *keys: str) -> Any:
    _ = engine
    for key in keys:
        if key in tool_args and tool_args.get(key) is not None:
            value = tool_args.get(key)
            if isinstance(value, str):
                value = value.strip()
                if re.fullmatch(r"\{\{[^{}]+\}\}", value):
                    continue
            if value != "":
                return value
    return None


def to_bool(engine: Any, value: Any, default: bool = False) -> bool:
    _ = engine
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on"):
        return True
    if text in ("0", "false", "no", "n", "off"):
        return False
    return default
