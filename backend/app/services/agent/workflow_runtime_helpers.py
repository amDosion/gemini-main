"""Helpers for workflow pause/resume checkpoints and runtime event metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RuntimeEventMetrics:
    emitted_event_count: int = 0
    delivered_event_count: int = 0
    dropped_event_count: int = 0
    backpressure_count: int = 0
    last_emitted_at: int = 0
    last_dropped_at: int = 0


def build_runtime_metrics_snapshot(
    metrics: Optional[RuntimeEventMetrics],
    *,
    subscriber_count: int,
) -> Dict[str, Any]:
    if metrics is None:
        return {
            "subscriber_count": int(max(0, subscriber_count)),
            "emitted_event_count": 0,
            "delivered_event_count": 0,
            "dropped_event_count": 0,
            "backpressure_count": 0,
            "last_emitted_at": 0,
            "last_dropped_at": 0,
        }

    return {
        "subscriber_count": int(max(0, subscriber_count)),
        "emitted_event_count": int(metrics.emitted_event_count or 0),
        "delivered_event_count": int(metrics.delivered_event_count or 0),
        "dropped_event_count": int(metrics.dropped_event_count or 0),
        "backpressure_count": int(metrics.backpressure_count or 0),
        "last_emitted_at": int(metrics.last_emitted_at or 0),
        "last_dropped_at": int(metrics.last_dropped_at or 0),
    }


def record_runtime_event_publish(
    metrics: RuntimeEventMetrics,
    *,
    delivered: int,
    dropped: int,
    emitted_at: int,
) -> RuntimeEventMetrics:
    metrics.emitted_event_count += 1
    metrics.last_emitted_at = int(emitted_at or 0)

    safe_delivered = max(0, int(delivered or 0))
    safe_dropped = max(0, int(dropped or 0))
    metrics.delivered_event_count += safe_delivered
    metrics.dropped_event_count += safe_dropped
    metrics.backpressure_count += safe_dropped
    if safe_dropped > 0:
        metrics.last_dropped_at = int(emitted_at or 0)
    return metrics


def build_checkpoint_summary(checkpoint: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(checkpoint, dict):
        return None
    return {
        "version": int(checkpoint.get("version") or 1),
        "strategy": str(checkpoint.get("strategy") or "restart"),
        "captured_at": int(checkpoint.get("captured_at") or 0),
        "reason": str(checkpoint.get("reason") or "pause_requested"),
        "event_count": int(checkpoint.get("event_count") or 0),
        "last_event_type": str(checkpoint.get("last_event_type") or ""),
    }


def create_pause_checkpoint(
    request_payload: Dict[str, Any],
    node_events: List[Dict[str, Any]],
    *,
    paused_at: int,
    reason: str,
) -> Dict[str, Any]:
    workflow_nodes = request_payload.get("nodes")
    workflow_edges = request_payload.get("edges")
    workflow_input = request_payload.get("input")
    workflow_meta = request_payload.get("meta")
    sanitized_payload = {
        "nodes": workflow_nodes if isinstance(workflow_nodes, list) else [],
        "edges": workflow_edges if isinstance(workflow_edges, list) else [],
        "input": workflow_input if isinstance(workflow_input, dict) else {},
        "meta": workflow_meta if isinstance(workflow_meta, dict) else {},
        "async_mode": bool(request_payload.get("async_mode", True)),
    }
    last_event_type = ""
    if node_events:
        last_event_type = str(node_events[-1].get("type") or "").strip()
    return {
        "version": 1,
        "strategy": "restart",
        "reason": str(reason or "pause_requested"),
        "captured_at": int(paused_at),
        "event_count": len(node_events),
        "last_event_type": last_event_type,
        "request_payload": sanitized_payload,
    }


def build_resume_request_payload(
    checkpoint: Optional[Dict[str, Any]],
    *,
    workflow_payload: Optional[Dict[str, Any]],
    input_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(checkpoint, dict):
        payload = checkpoint.get("request_payload")
        if isinstance(payload, dict):
            nodes = payload.get("nodes")
            edges = payload.get("edges")
            workflow_input = payload.get("input")
            workflow_meta = payload.get("meta")
            if isinstance(nodes, list) and isinstance(edges, list):
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "input": workflow_input if isinstance(workflow_input, dict) else {},
                    "meta": workflow_meta if isinstance(workflow_meta, dict) else {},
                    "async_mode": bool(payload.get("async_mode", True)),
                }

    safe_workflow = workflow_payload if isinstance(workflow_payload, dict) else {}
    safe_input = input_payload if isinstance(input_payload, dict) else {}
    return {
        "nodes": safe_workflow.get("nodes") if isinstance(safe_workflow.get("nodes"), list) else [],
        "edges": safe_workflow.get("edges") if isinstance(safe_workflow.get("edges"), list) else [],
        "input": safe_input,
        "meta": safe_workflow.get("meta") if isinstance(safe_workflow.get("meta"), dict) else {},
        "async_mode": True,
    }
