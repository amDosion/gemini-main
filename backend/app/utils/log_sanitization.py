"""Helpers for logging user-controlled text and URLs without leaking content."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit


def summarize_text_for_log(value: Any, *, label: str = "text") -> str:
    if value is None:
        return f"<none {label}>"
    text = str(value)
    if not text:
        return f"<empty {label}>"
    return f"<redacted {label}; length={len(text)}>"


def _count_query_params_for_log(query: str) -> int:
    if not query:
        return 0
    return query.count("&") + 1


def summarize_query_for_log(value: Any) -> str:
    if value is None:
        return "<none query>"
    if isinstance(value, (bytes, bytearray)):
        query = bytes(value).decode("utf-8", errors="replace")
    else:
        query = str(value)
    if not query:
        return "<empty query>"
    return f"query_params={_count_query_params_for_log(query)} length={len(query)}"


def summarize_url_for_log(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "None"

    lowered = text.lower()
    if lowered.startswith("data:"):
        media_type = text[5:].split(";", 1)[0] or "unknown"
        return f"data:{media_type}; length={len(text)}"
    if lowered.startswith("blob:"):
        return f"blob URL; length={len(text)}"

    try:
        parsed = urlsplit(text)
    except Exception:
        return f"invalid-url(len={len(text)})"

    if parsed.scheme in {"http", "https"}:
        query_count = _count_query_params_for_log(parsed.query)
        fragment = "yes" if parsed.fragment else "no"
        return (
            f"{parsed.scheme}://{parsed.netloc or 'unknown-host'} "
            f"path_len={len(parsed.path)} "
            f"query_params={query_count} "
            f"fragment={fragment}"
        )

    scheme = parsed.scheme or "relative"
    return f"{scheme} reference; length={len(text)}"


def redact_exact_value_in_log_text(text: Any, value: Any, replacement: str) -> str:
    return str(text).replace(str(value), replacement)
