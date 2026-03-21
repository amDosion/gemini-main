"""
Reference/file/table helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
import socket
import ipaddress
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ....core.config import settings

logger = logging.getLogger(__name__)

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore


def validate_remote_reference_url(engine: Any, ref_text: str) -> str:
    raw_url = str(ref_text or "").strip()
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("文件引用仅支持 http/https 协议")

    host = parsed.hostname
    if not host:
        raise ValueError("文件引用缺少主机名")
    if engine._is_disallowed_reference_hostname(host):
        raise ValueError("文件引用主机不被允许")

    ip_literal = engine._parse_reference_ip_host(host)
    if ip_literal is not None:
        if engine._is_disallowed_reference_ip(ip_literal):
            raise ValueError("文件引用指向受限地址")
        return raw_url

    try:
        addr_infos = socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise ValueError(f"文件引用主机解析失败: {host}") from exc

    resolved_ips = {
        ipaddress.ip_address(info[4][0])
        for info in addr_infos
        if info and len(info) >= 5 and info[4]
    }
    if not resolved_ips:
        raise ValueError(f"文件引用主机解析失败: {host}")
    if any(engine._is_disallowed_reference_ip(ip_obj) for ip_obj in resolved_ips):
        raise ValueError("文件引用指向受限网络地址")

    return raw_url


def load_binary_from_reference(
    engine: Any,
    ref: str,
    max_bytes: int = 8 * 1024 * 1024,
) -> Tuple[bytes, str, str]:
    ref_text = str(ref or "").strip()
    if not ref_text:
        raise ValueError("文件引用为空")

    if ref_text.startswith("data:"):
        mime_type, raw = engine._decode_data_url(ref_text)
        return raw, mime_type, "inline-data"

    parsed = urlparse(ref_text)
    if parsed.scheme in ("http", "https"):
        safe_ref = validate_remote_reference_url(engine, ref_text)
        request = Request(
            url=safe_ref,
            headers={
                "User-Agent": "WorkflowEngine/1.0",
                "Accept": "*/*",
            },
        )
        with urlopen(request, timeout=10) as response:  # nosec B310
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"文件过大，超过 {max_bytes // (1024 * 1024)}MB 上限")
        file_name = Path(parsed.path).name or "remote-file"
        return raw, content_type, file_name

    if parsed.scheme in ("", "file"):
        if not settings.workflow_allow_local_file_reference:
            raise ValueError("本地文件引用已禁用，请使用 data URL 或可访问的 http/https URL")
        path_value = parsed.path if parsed.scheme == "file" else ref_text
        candidate = Path(path_value).expanduser()
        if not candidate.exists() or not candidate.is_file():
            raise ValueError(f"本地文件不存在: {candidate}")
        raw = candidate.read_bytes()
        if len(raw) > max_bytes:
            raise ValueError(f"文件过大，超过 {max_bytes // (1024 * 1024)}MB 上限")
        mime_type = str(mimetypes.guess_type(str(candidate))[0] or "").lower()
        return raw, mime_type, str(candidate.name)

    raise ValueError(f"暂不支持的文件引用协议: {parsed.scheme}")


def normalize_dataframe(engine: Any, frame: Any) -> Any:
    if pd is None:
        return frame
    df = frame.copy()
    df.columns = [str(col or "").strip() or f"column_{idx + 1}" for idx, col in enumerate(df.columns)]
    normalized_columns: List[str] = []
    name_counter: Dict[str, int] = {}
    for col in df.columns:
        count = name_counter.get(col, 0) + 1
        name_counter[col] = count
        normalized_columns.append(col if count == 1 else f"{col}_{count}")
    df.columns = normalized_columns
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return df


def text_to_dataframe(engine: Any, text: str, source_hint: str = "") -> Any:
    if pd is None:
        raise ValueError("pandas 未安装，无法解析结构化表格")

    content = str(text or "").strip()
    if not content:
        return pd.DataFrame()

    if content[:1] in ("{", "["):
        try:
            parsed_json = json.loads(content)
            if isinstance(parsed_json, list):
                if all(isinstance(item, dict) for item in parsed_json):
                    return normalize_dataframe(engine, pd.DataFrame(parsed_json))
                return normalize_dataframe(engine, pd.DataFrame({"value": parsed_json}))
            if isinstance(parsed_json, dict):
                for key in ("rows", "data", "items", "sample_data", "cleaned_data"):
                    if key in parsed_json and isinstance(parsed_json[key], list):
                        rows = parsed_json[key]
                        if rows and all(isinstance(item, dict) for item in rows):
                            return normalize_dataframe(engine, pd.DataFrame(rows))
                return normalize_dataframe(engine, pd.DataFrame([parsed_json]))
        except Exception:
            pass

    delimiter = ","
    if "\t" in content:
        delimiter = "\t"
    else:
        try:
            sniffed = csv.Sniffer().sniff(content[:2048], delimiters=",\t;|")
            delimiter = sniffed.delimiter
        except Exception:
            if source_hint.lower().endswith(".tsv"):
                delimiter = "\t"

    try:
        frame = pd.read_csv(io.StringIO(content), sep=delimiter, engine="python")
        return normalize_dataframe(engine, frame)
    except Exception:
        try:
            frame = pd.read_csv(io.StringIO(content), engine="python")
            return normalize_dataframe(engine, frame)
        except Exception:
            lines = [line for line in content.splitlines() if line.strip()]
            if not lines:
                return pd.DataFrame()
            return normalize_dataframe(engine, pd.DataFrame({"text": lines}))


def bytes_to_dataframe(engine: Any, raw: bytes, mime_type: str = "", file_name: str = "") -> Any:
    if pd is None:
        raise ValueError("pandas 未安装，无法解析 Excel/CSV")
    if not raw:
        return pd.DataFrame()

    if engine._looks_like_excel_binary(mime_type=mime_type, file_name=file_name):
        try:
            frame = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
        except Exception:
            frame = pd.read_excel(io.BytesIO(raw))
        return normalize_dataframe(engine, frame)

    text = engine._decode_bytes_to_text(raw)
    return text_to_dataframe(engine, text=text, source_hint=file_name or mime_type or "")


def table_payload_to_dataframe(engine: Any, payload: Any) -> Tuple[Any, str]:
    if pd is None:
        raise ValueError("pandas 未安装，无法解析表格输入")

    if payload is None:
        return pd.DataFrame(), "empty"

    if isinstance(payload, list):
        if not payload:
            return pd.DataFrame(), "empty_list"
        if all(isinstance(item, dict) for item in payload):
            return normalize_dataframe(engine, pd.DataFrame(payload)), "list_of_dict"
        return normalize_dataframe(engine, pd.DataFrame({"value": payload})), "list"

    if isinstance(payload, dict):
        for key in (
            "sample_data",
            "cleaned_data",
            "rows",
            "data",
            "items",
            "table",
            "csv",
            "content",
            "fileUrl",
            "file_url",
        ):
            if key in payload:
                frame, source = table_payload_to_dataframe(engine, payload.get(key))
                if len(frame.index) > 0 or len(frame.columns) > 0:
                    return frame, f"dict.{key}:{source}"
        return normalize_dataframe(engine, pd.DataFrame([payload])), "dict"

    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return pd.DataFrame(), "empty_string"

        maybe_ref = False
        parsed = urlparse(text)
        if text.startswith("data:") or parsed.scheme in ("http", "https", "file"):
            maybe_ref = True
        elif parsed.scheme == "" and (text.startswith("/") or Path(text).expanduser().exists()):
            maybe_ref = True

        if maybe_ref:
            raw, mime_type, file_name = load_binary_from_reference(engine, text)
            frame = bytes_to_dataframe(engine, raw=raw, mime_type=mime_type, file_name=file_name)
            source = "data-url" if text.startswith("data:") else f"ref:{file_name or mime_type or 'unknown'}"
            return frame, source

        frame = text_to_dataframe(engine, text=text, source_hint="")
        return frame, "string"

    extracted = engine._extract_text_from_value(payload)
    frame = text_to_dataframe(engine, text=extracted, source_hint="generic")
    return frame, "generic"


def table_payload_to_text(engine: Any, payload: Any) -> Tuple[str, str]:
    if pd is not None:
        try:
            frame, source = table_payload_to_dataframe(engine, payload)
            if len(frame.columns) == 0:
                return "", source
            preview_rows = min(len(frame.index), 400)
            csv_text = frame.head(preview_rows).to_csv(index=False)
            source_with_count = f"{source}:rows={len(frame.index)},cols={len(frame.columns)}"
            return csv_text, source_with_count
        except Exception as exc:
            logger.info(f"[WorkflowEngine] table payload dataframe parse fallback: {exc}")

    if payload is None:
        return "", "empty"

    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return "", "empty_string"
        if text.startswith("data:"):
            mime_type, raw = engine._decode_data_url(text)
            textual_mime = (
                mime_type.startswith("text/")
                or any(token in mime_type for token in ("json", "csv", "xml", "yaml", "markdown"))
            )
            if not textual_mime:
                raise ValueError(f"table payload data URL 为二进制类型：{mime_type}")
            return engine._decode_bytes_to_text(raw), f"data-url:{mime_type}"
        return text, "string"

    if isinstance(payload, list):
        if not payload:
            return "", "empty_list"
        if all(isinstance(item, dict) for item in payload):
            return engine._dict_rows_to_csv(payload), "list_of_dict"
        return "\n".join(engine._extract_text_from_value(item) for item in payload if item is not None), "list"

    if isinstance(payload, dict):
        for key in (
            "sample_data",
            "cleaned_data",
            "rows",
            "data",
            "items",
            "table",
            "csv",
            "content",
            "fileUrl",
            "file_url",
        ):
            if key in payload:
                text, source = table_payload_to_text(engine, payload.get(key))
                if text:
                    return text, f"dict.{key}:{source}"
        return json.dumps(payload, ensure_ascii=False, indent=2), "dict_json"

    text = engine._extract_text_from_value(payload)
    return text, "generic"


def build_file_reference_context(engine: Any, file_ref: str) -> str:
    ref = str(file_ref or "").strip()
    if not ref:
        return "未提供文件引用。"
    try:
        raw, mime_type, file_name = load_binary_from_reference(engine, ref, max_bytes=2 * 1024 * 1024)
    except Exception as exc:
        return (
            f"用户提供了文件引用: {ref}\n"
            f"读取失败: {exc}\n"
            "请检查文件路径/URL 是否可访问。"
        )

    normalized_mime = str(mime_type or "").lower()
    normalized_name = str(file_name or "").strip() or "unknown"
    ext = Path(normalized_name).suffix.lower()
    is_data_url = ref.startswith("data:")
    source_label = "data-url" if is_data_url else ref

    table_like = (
        engine._looks_like_excel_binary(mime_type=normalized_mime, file_name=normalized_name)
        or ext in {".csv", ".tsv"}
        or "csv" in normalized_mime
        or "tab-separated-values" in normalized_mime
    )
    if table_like and pd is not None:
        try:
            frame = bytes_to_dataframe(engine, raw=raw, mime_type=normalized_mime, file_name=normalized_name)
            if len(frame.columns) > 0:
                preview_rows = min(len(frame.index), 200)
                preview_csv = frame.head(preview_rows).to_csv(index=False)
                column_preview = ", ".join(str(col) for col in list(frame.columns)[:30]) or "(无列名)"
                row_count = len(frame.index)
                col_count = len(frame.columns)
                row_note = "（样例已截断）" if row_count > preview_rows else ""
                return (
                    f"以下是文件结构化预览 {row_note}:\n"
                    f"来源: {source_label}\n"
                    f"文件名: {normalized_name}\n"
                    f"类型: {normalized_mime or 'application/octet-stream'}\n"
                    f"表格规模: {row_count} 行 x {col_count} 列\n"
                    f"列名: {column_preview}\n"
                    f"样例数据(CSV):\n{engine._truncate_text(preview_csv, max_chars=12000)}"
                )
        except Exception as exc:
            logger.info(f"[WorkflowEngine] file reference table preview parse failed: {exc}")

    textual_mime = (
        normalized_mime.startswith("text/")
        or any(token in normalized_mime for token in ("json", "csv", "xml", "yaml", "markdown"))
        or ext in {".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".log"}
    )
    if textual_mime:
        text = engine._decode_bytes_to_text(raw)
        preview = engine._build_text_preview(
            text,
            mime_type=normalized_mime or ext.lstrip("."),
            max_chars=10000,
        )
        return (
            "以下是用户提供的文件内容预览（可能已截断）：\n"
            f"来源: {source_label}\n"
            f"文件名: {normalized_name}\n"
            f"MIME: {normalized_mime or 'text/plain'}\n"
            f"内容:\n{preview}"
        )

    return (
        "用户提供了二进制文件：\n"
        f"来源: {source_label}\n"
        f"文件名: {normalized_name}\n"
        f"MIME: {normalized_mime or 'application/octet-stream'}\n"
        f"大小: {len(raw)} 字节\n"
        "该文件不属于可直接文本解析格式。"
    )
