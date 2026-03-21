"""Shared helpers for SSE payload encoding and response creation."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from .case_converter import to_camel_case

SSE_HEADERS: Dict[str, str] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def encode_sse_data(
    payload: Any,
    *,
    camel_case: bool = False,
    event: Optional[str] = None,
    event_id: Optional[str] = None,
) -> str:
    """Serialize a payload into a SSE message string."""
    serializable = jsonable_encoder(payload, exclude_none=False)
    if camel_case:
        serializable = to_camel_case(serializable)

    lines = []
    if event:
        lines.append(f"event: {event}")
    if event_id:
        # SSE id line is used by EventSource for automatic Last-Event-ID resume.
        lines.append(f"id: {str(event_id).replace(chr(10), '').replace(chr(13), '')}")
    lines.append(f"data: {json.dumps(serializable, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def build_safe_error_chunk(
    *,
    code: str = "stream_error",
    message: str = "Stream processing failed",
    details: Optional[Dict[str, Any]] = None,
    retryable: bool = True,
) -> Dict[str, Any]:
    """Build a sanitized SSE error chunk safe for client exposure."""
    safe_message = str(message or "Stream processing failed").strip() or "Stream processing failed"
    return {
        "text": "",
        "chunk_type": "error",
        "error": safe_message,
        "error_info": {
            "code": str(code or "stream_error"),
            "message": safe_message,
            "details": details or {},
            "retryable": bool(retryable),
        },
    }


async def _with_heartbeat(
    stream: AsyncGenerator[str, None],
    heartbeat_interval: float,
) -> AsyncGenerator[str, None]:
    """Wrap SSE stream with comment heartbeats to keep intermediaries alive."""
    queue: "asyncio.Queue[object]" = asyncio.Queue()
    sentinel = object()

    async def _drain_source() -> None:
        try:
            async for chunk in stream:
                await queue.put(chunk)
        finally:
            await queue.put(sentinel)

    drain_task = asyncio.create_task(_drain_source())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue

            if item is sentinel:
                break

            yield str(item)
    finally:
        if not drain_task.done():
            drain_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await drain_task


def create_sse_response(
    stream: AsyncGenerator[str, None],
    *,
    heartbeat_interval: Optional[float] = None,
) -> StreamingResponse:
    """Create a StreamingResponse with standard SSE headers."""
    if heartbeat_interval and heartbeat_interval > 0:
        stream = _with_heartbeat(stream, heartbeat_interval)

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=dict(SSE_HEADERS),
    )
