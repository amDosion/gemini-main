"""Shared pure helpers for workflow result summaries."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def extract_text_preview(
    payload: Any,
    max_length: int = 200,
    strip_markdown_fence: bool = True,
) -> str:
    def _strip_markdown_fence(text: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""

        wrapped = re.match(
            r"^```(?:json|markdown|md|text)?\s*([\s\S]*?)\s*```$",
            normalized,
            flags=re.IGNORECASE,
        )
        if wrapped:
            normalized = wrapped.group(1).strip()
        else:
            normalized = re.sub(r"```(?:json|markdown|md|text)?", "", normalized, flags=re.IGNORECASE)
            normalized = normalized.replace("```", "").strip()
        return normalized

    def cleanup(text: str) -> str:
        candidate = _strip_markdown_fence(text) if strip_markdown_fence else str(text or "")
        normalized = " ".join(candidate.split()).strip()
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[:max_length]}..."

    if payload is None:
        return ""
    if isinstance(payload, str):
        return cleanup(payload)
    if isinstance(payload, (int, float, bool)):
        return cleanup(str(payload))
    if isinstance(payload, list):
        for item in payload:
            preview = extract_text_preview(item, max_length=max_length, strip_markdown_fence=strip_markdown_fence)
            if preview:
                return preview
        return ""
    if isinstance(payload, dict):
        for key in ("finalOutput", "final_output", "text", "message", "summary", "content", "result", "merged"):
            if key in payload:
                preview = extract_text_preview(
                    payload.get(key),
                    max_length=max_length,
                    strip_markdown_fence=strip_markdown_fence,
                )
                if preview:
                    return preview
        for value in payload.values():
            preview = extract_text_preview(value, max_length=max_length, strip_markdown_fence=strip_markdown_fence)
            if preview:
                return preview
        return ""
    return ""


def normalize_runtime_hint(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None

    runtime = str(value).strip().lower().replace("_", "-")
    if not runtime:
        return None

    aliases = {
        "official-adk": "adk-official",
        "google-adk-official": "adk-official",
        "adkofficial": "adk-official",
        "google-adk": "adk",
        "legacy-adapter": "adapter",
        "llm-adapter": "adapter",
    }
    runtime = aliases.get(runtime, runtime)
    return runtime


def extract_runtime_hints(
    payload: Any,
    _seen: Optional[set] = None,
    _depth: int = 0,
    _allow_scalar: bool = False,
) -> List[str]:
    if _depth > 24:
        return []

    seen = _seen if _seen is not None else set()
    hints: List[str] = []

    def append_hint(candidate: Any):
        normalized = normalize_runtime_hint(candidate)
        if not normalized:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        hints.append(normalized)

    if payload is None:
        return hints

    if isinstance(payload, str):
        if _allow_scalar:
            append_hint(payload)
        return hints

    if isinstance(payload, list):
        for item in payload:
            hints.extend(extract_runtime_hints(item, seen, _depth + 1, _allow_scalar=_allow_scalar))
        return hints

    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key or "").strip().lower().replace("_", "")
            if normalized_key in {"runtime", "primaryruntime", "runtimehints", "runtimehint"}:
                hints.extend(extract_runtime_hints(value, seen, _depth + 1, _allow_scalar=True))
                continue
            hints.extend(extract_runtime_hints(value, seen, _depth + 1, _allow_scalar=False))
        return hints

    return hints


def pick_primary_runtime(runtime_hints: List[str]) -> str:
    if not runtime_hints:
        return ""

    priority = {
        "adk-official": 400,
        "adk": 300,
        "multimodal": 200,
        "adapter": 100,
    }
    sorted_hints = sorted(
        runtime_hints,
        key=lambda runtime: (priority.get(runtime, 0), -runtime_hints.index(runtime)),
        reverse=True,
    )
    return str(sorted_hints[0] or "")


def extract_trace_summary(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    trace_payload = payload.get("trace")
    if not isinstance(trace_payload, dict):
        return {}
    return {
        "duration_ms": int(trace_payload.get("duration_ms") or 0) if trace_payload.get("duration_ms") is not None else None,
        "event_count": int(trace_payload.get("event_count") or 0) if trace_payload.get("event_count") is not None else None,
        "started_at": trace_payload.get("started_at"),
        "completed_at": trace_payload.get("completed_at"),
    }


def extract_cost_summary(payload: Any) -> Dict[str, Any]:
    token_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    visited = set()

    def walk(value: Any, depth: int = 0):
        if depth > 14:
            return
        marker = id(value)
        if marker in visited:
            return
        if isinstance(value, (dict, list)):
            visited.add(marker)

        if isinstance(value, dict):
            usage = value.get("usage")
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens") if usage.get("input_tokens") is not None else usage.get("prompt_tokens")
                output_tokens = usage.get("output_tokens") if usage.get("output_tokens") is not None else usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")
                try:
                    if input_tokens is not None:
                        token_totals["input_tokens"] += int(float(str(input_tokens)))
                except Exception:
                    pass
                try:
                    if output_tokens is not None:
                        token_totals["output_tokens"] += int(float(str(output_tokens)))
                except Exception:
                    pass
                try:
                    if total_tokens is not None:
                        token_totals["total_tokens"] += int(float(str(total_tokens)))
                except Exception:
                    pass
            for nested in value.values():
                walk(nested, depth + 1)
            return

        if isinstance(value, list):
            for nested in value:
                walk(nested, depth + 1)

    walk(payload, 0)
    if token_totals["total_tokens"] <= 0:
        token_totals["total_tokens"] = token_totals["input_tokens"] + token_totals["output_tokens"]
    has_any = any(v > 0 for v in token_totals.values())
    if not has_any:
        return {}
    return token_totals
