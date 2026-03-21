"""
Text and payload helper utilities extracted from WorkflowEngine.
"""

from __future__ import annotations

import base64
import binascii
import csv
import io
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import unquote_to_bytes


def build_node_input_snapshot(engine: Any, input_packets: List[Dict[str, Any]]) -> Dict[str, Any]:
    packets = [packet for packet in input_packets if isinstance(packet, dict)]
    latest_output = packets[-1].get("output") if packets else None
    image_urls = engine._extract_result_image_urls(latest_output)

    source_nodes: List[str] = []
    for packet in packets:
        source_node_id = str(packet.get("sourceNodeId") or "").strip()
        if source_node_id and source_node_id not in source_nodes:
            source_nodes.append(source_node_id)

    return {
        "packetCount": len(packets),
        "sourceNodeIds": source_nodes,
        "latestText": engine._extract_text_from_value(latest_output),
        "latestImageUrls": image_urls[:4],
        "hasImage": bool(image_urls),
        "latestValueType": type(latest_output).__name__ if latest_output is not None else "none",
    }


def extract_text_from_value(engine: Any, value: Any) -> str:
    def sanitize_inline_text(text: str) -> str:
        lowered = str(text or "").lower()
        if lowered.startswith("data:image/"):
            mime = str(text).split(";", 1)[0].replace("data:", "", 1) or "image/*"
            return f"[{mime} data-url omitted]"

        compact = str(text or "").replace("\n", "").replace("\r", "").strip()
        if (
            len(compact) >= 512
            and re.fullmatch(r"[A-Za-z0-9+/=]+", compact)
            and " " not in compact
        ):
            return f"[base64 payload omitted, len={len(compact)}]"
        return str(text or "")

    def sanitize_payload(payload: Any, depth: int = 0) -> Any:
        if depth >= 4:
            return "[truncated]"

        if isinstance(payload, str):
            return sanitize_inline_text(payload)
        if isinstance(payload, (int, float, bool)) or payload is None:
            return payload
        if isinstance(payload, list):
            limit = 8
            sanitized_items = [sanitize_payload(item, depth + 1) for item in payload[:limit]]
            if len(payload) > limit:
                sanitized_items.append(f"... ({len(payload) - limit} more items)")
            return sanitized_items
        if isinstance(payload, dict):
            sanitized: Dict[str, Any] = {}
            keys = list(payload.keys())
            limit = 24
            for key in keys[:limit]:
                key_text = str(key)
                value_item = payload.get(key)
                if key_text.lower() in {
                    "imageurl", "image_url", "imageurls", "image_urls",
                    "data", "inline_data", "base64", "base64_data",
                } and isinstance(value_item, str):
                    sanitized[key_text] = sanitize_inline_text(value_item)
                else:
                    sanitized[key_text] = sanitize_payload(value_item, depth + 1)
            if len(keys) > limit:
                sanitized["_truncated_keys"] = len(keys) - limit
            return sanitized
        return str(payload)

    if value is None:
        return ""
    if isinstance(value, str):
        return sanitize_inline_text(value)
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return ""
        return "\n".join(engine._extract_text_from_value(item) for item in value if item is not None).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "message", "merged", "summaryText", "summary_text"):
            if key in value:
                return engine._extract_text_from_value(value[key])

        image_urls = engine._extract_result_image_urls(value)
        if image_urls:
            return f"已生成 {len(image_urls)} 张图片。"

        summary_payload = value.get("summary")
        summary_parts: List[str] = []
        if isinstance(summary_payload, dict):
            impressions = summary_payload.get("impressions")
            clicks = summary_payload.get("clicks")
            orders = summary_payload.get("orders")
            spend = summary_payload.get("spend")
            sales = summary_payload.get("sales")
            acos = summary_payload.get("acos")
            target_acos = summary_payload.get("targetAcos")
            if impressions is not None:
                summary_parts.append(f"曝光 {int(engine._to_int(impressions, default=0) or 0):,}")
            if clicks is not None:
                summary_parts.append(f"点击 {int(engine._to_int(clicks, default=0) or 0):,}")
            if orders is not None:
                summary_parts.append(f"订单 {int(engine._to_int(orders, default=0) or 0):,}")
            if spend is not None:
                summary_parts.append(f"花费 {engine._format_money(engine._to_float(spend, default=0.0) or 0.0)}")
            if sales is not None:
                summary_parts.append(f"销售 {engine._format_money(engine._to_float(sales, default=0.0) or 0.0)}")
            if acos is not None:
                summary_parts.append(f"ACoS {engine._format_ratio(engine._to_float(acos, default=None))}")
            if target_acos is not None:
                summary_parts.append(f"目标 ACoS {engine._format_ratio(engine._to_float(target_acos, default=None))}")

        validation_payload = value.get("validation")
        if isinstance(validation_payload, dict):
            status = str(validation_payload.get("status") or "").strip()
            confidence = validation_payload.get("confidence")
            if status:
                if confidence is None:
                    summary_parts.append(f"校验 {status}")
                else:
                    summary_parts.append(f"校验 {status}（{confidence}）")

        actions_payload = value.get("actions")
        action_lines: List[str] = []
        if isinstance(actions_payload, list):
            for action in actions_payload[:3]:
                action_text = str(action or "").strip()
                if action_text:
                    action_lines.append(action_text)

        if summary_parts or action_lines:
            segments: List[str] = []
            if summary_parts:
                segments.append(" | ".join(summary_parts))
            if action_lines:
                segments.append("；".join(action_lines))
            return "\n".join(segments).strip()

        visible_keys = [
            str(key) for key in value.keys()
            if str(key).lower() not in {
                "data", "inline_data", "base64", "base64_data",
                "imageurl", "image_url", "imageurls", "image_urls",
            }
        ]
        if visible_keys:
            key_preview = "、".join(visible_keys[:10])
            if len(visible_keys) > 10:
                key_preview = f"{key_preview} 等 {len(visible_keys)} 个字段"
            return f"结构化结果：{key_preview}"

        serialized = json.dumps(sanitize_payload(value), ensure_ascii=False)
        if len(serialized) > 8000:
            return f"{serialized[:8000]}\n...[内容已截断，共 {len(serialized)} 字符]"
        return serialized
    return str(value)


def strip_markdown_code_fence(engine: Any, text: str) -> str:
    _ = engine
    content = str(text or "").strip()
    if not content.startswith("```"):
        return content
    pattern = r"^```(?:json|markdown|md|text)?\s*([\s\S]*?)\s*```$"
    matched = re.match(pattern, content, flags=re.IGNORECASE)
    if matched:
        return matched.group(1).strip()
    return content


def normalize_agent_response_text(engine: Any, text: Any, expected_format: str = "") -> str:
    normalized = engine._strip_markdown_code_fence(str(text or ""))
    fmt = str(expected_format or "").strip().lower()
    if fmt != "json":
        return normalized
    try:
        parsed = json.loads(normalized)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except Exception:
        return normalized


def to_int(
    engine: Any,
    value: Any,
    default: Optional[int] = None,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> Optional[int]:
    _ = engine
    if value is None:
        return default
    try:
        parsed = int(float(str(value).strip()))
    except Exception:
        return default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def to_float(
    engine: Any,
    value: Any,
    default: Optional[float] = None,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> Optional[float]:
    _ = engine
    if value is None:
        return default
    try:
        parsed = float(str(value).strip())
    except Exception:
        return default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def truncate_text(engine: Any, text: str, max_chars: int = 8000) -> str:
    _ = engine
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n...[内容已截断，共 {len(text)} 字符]..."


def decode_data_url(engine: Any, data_url: str) -> Tuple[str, bytes]:
    _ = engine
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise ValueError("不是合法的 data URL")

    header, payload = data_url.split(",", 1) if "," in data_url else ("", "")
    if not header:
        raise ValueError("data URL 缺少头部")

    mime_and_flags = header[5:]
    mime_type = "application/octet-stream"
    if mime_and_flags:
        mime_type = mime_and_flags.split(";", 1)[0] or mime_type

    if ";base64" in header.lower():
        try:
            data = base64.b64decode(payload, validate=False)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("data URL base64 解码失败") from exc
        return mime_type.lower(), data

    try:
        return mime_type.lower(), unquote_to_bytes(payload)
    except Exception as exc:
        raise ValueError("data URL URL 编码解码失败") from exc


def decode_bytes_to_text(engine: Any, content: bytes) -> str:
    _ = engine
    if not content:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def dict_rows_to_csv(engine: Any, rows: List[Dict[str, Any]]) -> str:
    _ = engine
    if not rows:
        return ""
    fieldnames: List[str] = []
    seen: Set[str] = set()
    for row in rows:
        for key in row.keys():
            key_text = str(key)
            if key_text not in seen:
                seen.add(key_text)
                fieldnames.append(key_text)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in fieldnames})
    return stream.getvalue()


def build_text_preview(engine: Any, text: str, mime_type: str, max_chars: int = 8000) -> str:
    content = (text or "").strip()
    if not content:
        return "(空内容)"

    lowered = (mime_type or "").lower()
    if "json" in lowered:
        try:
            parsed = json.loads(content)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            return engine._truncate_text(pretty, max_chars=max_chars)
        except Exception:
            pass

    if "csv" in lowered or "tsv" in lowered:
        stream = io.StringIO(content)
        try:
            dialect = csv.Sniffer().sniff(content[:2048], delimiters=",\t;|")
        except Exception:
            dialect = csv.excel
        reader = csv.reader(stream, dialect=dialect)
        rows: List[str] = []
        for idx, row in enumerate(reader):
            if idx >= 40:
                break
            rows.append(" | ".join(str(cell).strip() for cell in row))
        if rows:
            return engine._truncate_text("\n".join(rows), max_chars=max_chars)

    return engine._truncate_text(content, max_chars=max_chars)
