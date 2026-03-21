"""Shared serialization helpers for Interactions stream events."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi.encoders import jsonable_encoder


def serialize_usage(usage: Any) -> Dict[str, Any]:
    """Serialize usage object to a JSON-safe dict without dropping extended fields."""
    payload = jsonable_encoder(usage, exclude_none=True)
    if not isinstance(payload, dict):
        payload = {}

    # Normalize core counters while preserving all original fields.
    total_tokens = payload.get("total_tokens") or payload.get("total_token_count")
    prompt_tokens = payload.get("prompt_tokens") or payload.get("prompt_token_count")
    completion_tokens = payload.get("completion_tokens") or payload.get("candidates_token_count")

    if total_tokens is not None:
        payload["total_tokens"] = total_tokens
    if prompt_tokens is not None:
        payload["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        payload["completion_tokens"] = completion_tokens

    return payload


def _serialize_object(value: Any) -> Optional[Dict[str, Any]]:
    payload = jsonable_encoder(value, exclude_none=True)
    if isinstance(payload, dict):
        return payload
    return None


def _serialize_interaction(interaction: Any) -> Optional[Dict[str, Any]]:
    payload = _serialize_object(interaction)
    if not payload:
        return None

    normalized: Dict[str, Any] = {}
    for field in ("id", "status", "outputs", "output", "error", "usage"):
        if field in payload:
            normalized[field] = payload[field]

    # Keep both names for compatibility with different SDK revisions.
    if "requires_action" in payload:
        normalized["requires_action"] = payload["requires_action"]
        normalized["required_action"] = payload["requires_action"]
    if "required_action" in payload:
        normalized["required_action"] = payload["required_action"]
        normalized["requires_action"] = payload["required_action"]

    return normalized or payload


def _extract_delta_payload(delta: Any) -> Optional[Dict[str, Any]]:
    if not delta:
        return None

    serialized = _serialize_object(delta)
    if serialized is not None:
        delta_type = serialized.get("type")

        # Normalize thought_summary payload so frontend can always read content.text.
        if delta_type == "thought_summary":
            content = serialized.get("content")
            if not isinstance(content, dict):
                if isinstance(serialized.get("text"), str):
                    serialized["content"] = {"text": serialized["text"]}
            elif "text" not in content and isinstance(serialized.get("text"), str):
                content["text"] = serialized["text"]

        # Normalize text payload fallback when only content.text exists.
        if delta_type == "text" and not serialized.get("text"):
            content = serialized.get("content")
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                serialized["text"] = content["text"]

        # Return full payload to preserve official structured delta fields
        # such as function_call/google_search_call/... and corresponding results.
        return serialized

    delta_type = getattr(delta, "type", None)
    if delta_type == "text":
        return {
            "type": "text",
            "text": getattr(delta, "text", "") or "",
        }

    if delta_type == "thought_summary":
        content = getattr(delta, "content", None)
        return {
            "type": "thought_summary",
            "content": {
                "text": getattr(content, "text", "") if content else "",
            },
        }

    if delta_type == "thought":
        return {
            "type": "thought",
            "thought": getattr(delta, "thought", "") or "",
        }

    # Keep compatibility for any future/unknown delta shape.
    delta_text = getattr(delta, "text", None)
    if delta_text:
        return {
            "type": delta_type or "text",
            "text": delta_text,
        }

    content = getattr(delta, "content", None)
    content_text = getattr(content, "text", None) if content else None
    if content_text:
        return {
            "type": delta_type or "text",
            "content": {"text": content_text},
        }

    return None


def _extract_event_id(chunk: Any) -> Optional[str]:
    for attr in ("event_id", "eventId", "id"):
        value = getattr(chunk, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for method_name in ("model_dump", "to_dict", "dict"):
        method = getattr(chunk, method_name, None)
        if not callable(method):
            continue
        try:
            payload = method()
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("event_id", "eventId", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def extract_grounding_metadata(interaction: Any) -> Optional[Dict[str, Any]]:
    output = getattr(interaction, "output", None)
    if not output or not hasattr(output, "parts") or not output.parts:
        return None

    for part in output.parts:
        grounding_metadata = getattr(part, "grounding_metadata", None)
        if not grounding_metadata:
            continue

        grounding_dict: Dict[str, Any] = {}

        grounding_chunks = getattr(grounding_metadata, "grounding_chunks", None)
        if grounding_chunks:
            grounding_dict["grounding_chunks"] = []
            for grounding_chunk in grounding_chunks:
                chunk_dict: Dict[str, Any] = {}
                chunk_obj = getattr(grounding_chunk, "chunk", None)
                if chunk_obj:
                    chunk_dict["chunk"] = {}
                    chunk_text = getattr(chunk_obj, "text", None)
                    if chunk_text:
                        chunk_dict["chunk"]["text"] = chunk_text

                    chunk_web = getattr(chunk_obj, "web", None)
                    if chunk_web:
                        chunk_dict["chunk"]["web"] = {
                            "uri": getattr(chunk_web, "uri", None),
                            "title": getattr(chunk_web, "title", None),
                        }
                grounding_dict["grounding_chunks"].append(chunk_dict)

        web_search_queries = getattr(grounding_metadata, "web_search_queries", None)
        if web_search_queries:
            grounding_dict["web_search_queries"] = [
                query.query if hasattr(query, "query") else str(query)
                for query in web_search_queries
            ]

        search_entry_point = getattr(grounding_metadata, "search_entry_point", None)
        rendered_content = getattr(search_entry_point, "rendered_content", None) if search_entry_point else None
        if rendered_content:
            grounding_dict["search_entry_point"] = {
                "rendered_content": rendered_content
            }

        if grounding_dict:
            return grounding_dict

    return None


def build_interaction_stream_event(chunk: Any) -> Dict[str, Any]:
    """Convert a raw SDK stream chunk into a JSON-serializable event payload."""
    event_type = getattr(chunk, "event_type", None)
    if not event_type:
        event_type = type(chunk).__name__.lower().replace("event", "").replace("_", ".")

    event_data: Dict[str, Any] = {
        "event_type": event_type,
        "event_id": _extract_event_id(chunk),
    }

    interaction_payload = _serialize_interaction(getattr(chunk, "interaction", None))
    if interaction_payload:
        event_data["interaction"] = interaction_payload

    if event_type == "interaction.start":
        return event_data

    if event_type == "content.delta":
        delta_payload = _extract_delta_payload(getattr(chunk, "delta", None))
        if delta_payload is not None:
            event_data["delta"] = delta_payload
        return event_data

    if event_type == "interaction.status_update":
        status_payload = getattr(chunk, "status", None)
        if status_payload is not None:
            serialized_status = jsonable_encoder(status_payload, exclude_none=True)
            event_data["status"] = serialized_status
        return event_data

    if event_type == "interaction.complete":
        interaction = getattr(chunk, "interaction", None)
        if interaction:
            if event_data.get("interaction"):
                # Keep official terminal status (completed/failed/cancelled) from SDK;
                # never overwrite with a hard-coded fallback.
                interaction_status = event_data["interaction"].get("status")
                if interaction_status is None:
                    sdk_status = getattr(interaction, "status", None)
                    if sdk_status is not None:
                        event_data["interaction"]["status"] = sdk_status

            usage = getattr(interaction, "usage", None)
            if usage:
                event_data["usage"] = serialize_usage(usage)

            grounding_metadata = extract_grounding_metadata(interaction)
            if grounding_metadata:
                event_data["grounding_metadata"] = grounding_metadata
        return event_data

    # Keep compatibility for generic status/error events.
    status = getattr(chunk, "status", None)
    if status is not None:
        event_data["status"] = jsonable_encoder(status, exclude_none=True)

    error = getattr(chunk, "error", None)
    if error is not None:
        event_data["error"] = jsonable_encoder(error, exclude_none=True)

    usage = getattr(chunk, "usage", None)
    if usage:
        event_data["usage"] = serialize_usage(usage)

    return event_data
