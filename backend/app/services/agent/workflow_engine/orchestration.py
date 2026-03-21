"""
Workflow execution orchestration extracted from WorkflowEngine.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ..execution_context import ExecutionContext

logger = logging.getLogger(__name__)


def record_trace_event(engine: Any, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    event_payload = payload if isinstance(payload, dict) else {}
    engine._trace_events.append({
        "event": str(event_type or "").strip() or "unknown",
        "timestamp": int(time.time() * 1000),
        "payload": event_payload,
    })
    if len(engine._trace_events) > 500:
        engine._trace_events = engine._trace_events[-500:]


async def emit_callback(engine: Any, hook_name: str, payload: Dict[str, Any]) -> None:
    if not engine.callback_plugins:
        return
    for plugin in engine.callback_plugins:
        callback = getattr(plugin, hook_name, None)
        if not callable(callback):
            continue
        try:
            result = callback(payload)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.warning(
                "[WorkflowEngine] callback plugin hook failed: hook=%s plugin=%s",
                hook_name,
                type(plugin).__name__,
                exc_info=True,
            )


def resolve_agent_timeout_seconds(engine: Any, node_data: Dict[str, Any]) -> int:
    raw_timeout = (
        node_data.get("agent_timeout_seconds")
        or node_data.get("agentTimeoutSeconds")
        or node_data.get("timeout_seconds")
        or node_data.get("timeoutSeconds")
    )
    if raw_timeout is not None and str(raw_timeout).strip():
        try:
            parsed = int(float(raw_timeout))
        except Exception:
            parsed = engine.DEFAULT_AGENT_TIMEOUT_SECONDS
        return max(1, min(parsed, 7200))

    task_type = str(
        node_data.get("agent_task_type")
        or node_data.get("agentTaskType")
        or ""
    ).strip().lower().replace("_", "-")
    if task_type in {
        "image-edit",
        "image-gen",
        "vision-understand",
        "image-understand",
        "vision-analyze",
        "image-analyze",
    }:
        return engine.DEFAULT_IMAGE_AGENT_TIMEOUT_SECONDS
    if task_type == "video-gen":
        return engine.DEFAULT_VIDEO_AGENT_TIMEOUT_SECONDS
    if task_type in {"data-analysis", "table-analysis"}:
        return engine.DEFAULT_DATA_AGENT_TIMEOUT_SECONDS
    return engine.DEFAULT_AGENT_TIMEOUT_SECONDS


async def execute(
    engine: Any,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    initial_input: Dict[str, Any],
    on_event: Optional[Callable] = None,
) -> Dict[str, Any]:
    context = ExecutionContext(initial_input or {})
    engine._trace_events = []
    workflow_started_at = int(time.time() * 1000)
    engine._record_trace_event(
        "workflow_start",
        {
            "node_count": len(nodes or []),
            "edge_count": len(edges or []),
        },
    )
    node_map = {n.get("id"): n for n in nodes if n.get("id")}
    if not node_map:
        raise ValueError("工作流为空，缺少可执行节点")

    outgoing_edges: Dict[str, List[Dict[str, Any]]] = {node_id: [] for node_id in node_map}
    incoming_edges: Dict[str, List[Dict[str, Any]]] = {node_id: [] for node_id in node_map}

    for edge in edges:
        source_id = edge.get("source")
        target_id = edge.get("target")
        if source_id not in node_map or target_id not in node_map:
            continue
        outgoing_edges[source_id].append(edge)
        incoming_edges[target_id].append(edge)

    start_node_ids = [
        node_id
        for node_id, node in node_map.items()
        if engine._get_node_type(node) == "start"
    ]
    if len(start_node_ids) == 0:
        raise ValueError("工作流必须包含一个开始节点")
    if len(start_node_ids) > 1:
        raise ValueError("工作流只能包含一个开始节点")

    end_node_ids = [
        node_id
        for node_id, node in node_map.items()
        if engine._get_node_type(node) == "end"
    ]
    if len(end_node_ids) == 0:
        raise ValueError("工作流必须包含一个结束节点")
    if len(end_node_ids) > 1:
        raise ValueError("工作流只能包含一个结束节点")

    start_node_id = start_node_ids[0]
    end_node_id = end_node_ids[0]

    if incoming_edges.get(start_node_id):
        raise ValueError("开始节点不能有输入连接")
    if not outgoing_edges.get(start_node_id):
        raise ValueError("开始节点至少需要一条输出连接")
    if not incoming_edges.get(end_node_id):
        raise ValueError("结束节点至少需要一条输入连接")
    if outgoing_edges.get(end_node_id):
        raise ValueError("结束节点不能有输出连接")

    def _bfs(seed: str, graph: Dict[str, List[Dict[str, Any]]], direction: str) -> Set[str]:
        visited: Set[str] = set()
        queue: List[str] = [seed]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in graph.get(current, []):
                nxt = edge.get("target") if direction == "forward" else edge.get("source")
                if nxt in node_map and nxt not in visited:
                    queue.append(nxt)
        return visited

    reachable_from_start = _bfs(start_node_id, outgoing_edges, "forward")
    if end_node_id not in reachable_from_start:
        raise ValueError("工作流必须存在从开始节点到结束节点的执行路径")

    unreachable_nodes = [node_id for node_id in node_map if node_id not in reachable_from_start]
    if unreachable_nodes:
        raise ValueError(f"存在未从开始节点连通的节点: {', '.join(unreachable_nodes[:3])}")

    can_reach_end = _bfs(end_node_id, incoming_edges, "reverse")
    no_end_path_nodes = [node_id for node_id in node_map if node_id not in can_reach_end]
    if no_end_path_nodes:
        raise ValueError(f"存在无法流向结束节点的节点: {', '.join(no_end_path_nodes[:3])}")

    pending_inputs: Dict[str, List[Dict[str, Any]]] = {node_id: [] for node_id in node_map}
    execution_queue: List[str] = []
    queued: Set[str] = set()
    in_flight: Set[str] = set()
    node_states: Dict[str, str] = {node_id: "pending" for node_id in node_map}
    node_visit_counts: Dict[str, int] = {}

    def should_defer_node_enqueue(node_id: str, trigger_source_id: Optional[str] = None) -> bool:
        node = node_map.get(node_id)
        if not node:
            return False

        node_type = engine._get_node_type(node)
        if node_type not in {"merge", "end"}:
            return False

        node_data = node.get("data", {}) or {}
        wait_for_all_raw = node_data.get("wait_for_all")
        if wait_for_all_raw is None:
            wait_for_all_raw = node_data.get("waitForAll")
        wait_for_all = engine._to_bool(wait_for_all_raw, default=True)
        if not wait_for_all:
            return False

        incoming_list = incoming_edges.get(node_id, [])
        if len(incoming_list) <= 1:
            return False

        if len(pending_inputs.get(node_id, [])) == 0:
            return True

        upstream_ids = {
            str(edge.get("source") or "").strip()
            for edge in incoming_list
            if str(edge.get("source") or "").strip() in node_map
        }

        for upstream_id in upstream_ids:
            if not upstream_id:
                continue
            if trigger_source_id and upstream_id == trigger_source_id:
                continue
            if upstream_id in queued or upstream_id in in_flight:
                return True
            upstream_state = node_states.get(upstream_id, "pending")
            if upstream_state == "running":
                return True
            if upstream_state == "pending" and len(pending_inputs.get(upstream_id, [])) > 0:
                return True

        return False

    def enqueue(node_id: str, trigger_source_id: Optional[str] = None):
        if node_id not in node_map:
            return
        if node_id in queued or node_id in in_flight:
            return
        if should_defer_node_enqueue(node_id, trigger_source_id=trigger_source_id):
            return
        execution_queue.append(node_id)
        queued.add(node_id)

    pending_inputs[start_node_id].append({
        "sourceNodeId": "__input__",
        "viaEdgeId": "__start__",
        "output": initial_input,
    })
    enqueue(start_node_id)

    logger.info(f"[WorkflowEngine] Start node: {start_node_id}, end node: {end_node_id}")

    max_parallel_nodes = engine._resolve_max_parallel_nodes(initial_input=initial_input)
    node_semaphore = asyncio.Semaphore(max_parallel_nodes)
    state_lock = asyncio.Lock()
    total_steps = 0

    async def run_single_node(node_id: str):
        nonlocal total_steps

        node = node_map.get(node_id)
        if not node:
            async with state_lock:
                in_flight.discard(node_id)
            return

        node_type = engine._get_node_type(node)
        node_data = node.get("data", {}) or {}
        progress_task: Optional[asyncio.Task] = None
        progress_stopped = asyncio.Event()
        progress_seed = 12

        async with state_lock:
            max_visits = engine._resolve_max_visits(node_type, node_data)
            node_visit_counts[node_id] = node_visit_counts.get(node_id, 0) + 1
            current_visit = node_visit_counts[node_id]
            if current_visit > max_visits:
                in_flight.discard(node_id)
                raise RuntimeError(f"节点 {node_id} ({node_type}) 执行次数超过上限 {max_visits}")

            total_steps += 1
            if total_steps > engine.MAX_TOTAL_STEPS:
                in_flight.discard(node_id)
                raise RuntimeError(f"工作流执行步数超过上限 {engine.MAX_TOTAL_STEPS}，请检查循环配置")

            input_packets = pending_inputs.get(node_id, [])
            pending_inputs[node_id] = []

        async def emit_node_progress(progress: int, stage: str):
            if not on_event:
                return
            safe_progress = max(0, min(int(progress), 100))
            await on_event("node_progress", {
                "nodeId": node_id,
                "timestamp": int(time.time() * 1000),
                "visit": current_visit,
                "progress": safe_progress,
                "stage": stage,
            })

        async def stop_progress_task():
            nonlocal progress_task
            progress_stopped.set()
            if progress_task:
                if not progress_task.done():
                    progress_task.cancel()
                await asyncio.gather(progress_task, return_exceptions=True)
            progress_task = None

        if on_event:
            await on_event("node_start", {
                "nodeId": node_id,
                "timestamp": int(time.time() * 1000),
                "visit": current_visit,
                "input": engine._build_node_input_snapshot(input_packets=input_packets),
            })
            await emit_node_progress(progress_seed, "started")

            async def progress_heartbeat():
                progress_value = progress_seed
                while not progress_stopped.is_set():
                    await asyncio.sleep(1.5)
                    if progress_stopped.is_set():
                        break
                    progress_value = min(92, progress_value + 6)
                    await emit_node_progress(progress_value, "running")

            progress_task = asyncio.create_task(progress_heartbeat())

        async def run_node_operation() -> Tuple[Any, Dict[str, Any]]:
            node_task = asyncio.create_task(
                engine._execute_node(
                    node=node,
                    context=context,
                    initial_input=initial_input,
                    input_packets=input_packets,
                    outgoing_edges=outgoing_edges.get(node_id, []),
                    incoming_edge_count=len(incoming_edges.get(node_id, [])),
                )
            )
            if progress_task is None:
                return await node_task
            try:
                while True:
                    done, _ = await asyncio.wait(
                        {node_task, progress_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if progress_task in done:
                        progress_exc = progress_task.exception()
                        if progress_exc is not None:
                            if not node_task.done():
                                node_task.cancel()
                                await asyncio.gather(node_task, return_exceptions=True)
                            raise progress_exc
                    if node_task in done:
                        return node_task.result()
            finally:
                if not node_task.done():
                    node_task.cancel()
                    await asyncio.gather(node_task, return_exceptions=True)

        engine._record_trace_event(
            "node_start",
            {
                "node_id": node_id,
                "node_type": node_type,
                "visit": current_visit,
            },
        )
        await engine._emit_callback(
            "before_node",
            {
                "node_id": node_id,
                "node_type": node_type,
                "visit": current_visit,
                "input_packets": input_packets,
            },
        )

        try:
            output, routing = await run_node_operation()
            context.set_output(node_id, output)
            node_states[node_id] = "completed"

            if on_event:
                await stop_progress_task()
                await emit_node_progress(100, "completed")
                await on_event("node_complete", {
                    "nodeId": node_id,
                    "status": "completed",
                    "timestamp": int(time.time() * 1000),
                    "visit": current_visit,
                    "output": output,
                })

            engine._record_trace_event(
                "node_complete",
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "visit": current_visit,
                },
            )
            await engine._emit_callback(
                "after_node",
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "visit": current_visit,
                    "output": output,
                    "routing": routing,
                },
            )

            selected_edges = engine._select_outgoing_edges(
                node=node,
                outgoing_edges=outgoing_edges.get(node_id, []),
                routing=routing,
            )

            async with state_lock:
                for edge in selected_edges:
                    target_id = edge.get("target")
                    if target_id not in node_map:
                        continue
                    pending_inputs[target_id].append({
                        "sourceNodeId": node_id,
                        "viaEdgeId": edge.get("id"),
                        "output": output,
                        "sourceHandle": engine._get_source_handle(edge),
                    })
                    enqueue(target_id, trigger_source_id=node_id)

        except Exception as exc:
            error_msg = str(exc)
            context.set_error(node_id, error_msg)
            node_states[node_id] = "failed"
            logger.error(f"[WorkflowEngine] Node {node_id} ({node_type}) failed: {error_msg}", exc_info=True)
            continue_on_error = engine._to_bool(
                node_data.get("continue_on_error", node_data.get("continueOnError", False)),
                default=False,
            )

            if on_event:
                await stop_progress_task()
                await emit_node_progress(100, "failed")
                await on_event("node_error", {
                    "nodeId": node_id,
                    "timestamp": int(time.time() * 1000),
                    "error": error_msg,
                    "continueOnError": continue_on_error,
                })
            engine._record_trace_event(
                "node_error",
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "visit": current_visit,
                    "error": error_msg,
                    "continue_on_error": continue_on_error,
                },
            )
            await engine._emit_callback(
                "on_node_error",
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "visit": current_visit,
                    "error": error_msg,
                    "continue_on_error": continue_on_error,
                },
            )
            if continue_on_error:
                fallback_output = {
                    "status": "failed",
                    "nodeId": node_id,
                    "nodeType": node_type,
                    "error": error_msg,
                    "text": f"[FAILED:{node_id}] {error_msg}",
                }
                context.set_output(node_id, fallback_output)

                selected_edges = engine._select_outgoing_edges(
                    node=node,
                    outgoing_edges=outgoing_edges.get(node_id, []),
                    routing={"mode": "all"},
                )
                async with state_lock:
                    for edge in selected_edges:
                        target_id = edge.get("target")
                        if target_id not in node_map:
                            continue
                        pending_inputs[target_id].append({
                            "sourceNodeId": node_id,
                            "viaEdgeId": edge.get("id"),
                            "output": fallback_output,
                            "sourceHandle": engine._get_source_handle(edge),
                        })
                        enqueue(target_id, trigger_source_id=node_id)
                return
            raise
        finally:
            await stop_progress_task()
            async with state_lock:
                in_flight.discard(node_id)
                if pending_inputs.get(node_id):
                    enqueue(node_id)

    async def run_node_with_limit(node_id: str):
        async with node_semaphore:
            await run_single_node(node_id)

    running_tasks: Set[asyncio.Task] = set()
    try:
        while True:
            ready_batch: List[str] = []
            async with state_lock:
                if execution_queue:
                    ready_batch = list(execution_queue)
                    execution_queue.clear()
                    for node_id in ready_batch:
                        queued.discard(node_id)
                        in_flight.add(node_id)

            for node_id in ready_batch:
                running_tasks.add(asyncio.create_task(run_node_with_limit(node_id)))

            if not running_tasks:
                async with state_lock:
                    if not execution_queue:
                        break
                await asyncio.sleep(0)
                continue

            done, pending = await asyncio.wait(
                running_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            running_tasks = set(pending)
            for task in done:
                try:
                    task.result()
                except Exception:
                    for pending_task in running_tasks:
                        pending_task.cancel()
                    await asyncio.gather(*running_tasks, return_exceptions=True)
                    raise

        for node_id, state in list(node_states.items()):
            if state != "pending":
                continue
            node_states[node_id] = "skipped"
            engine._record_trace_event(
                "node_skipped",
                {
                    "node_id": node_id,
                    "reason": "unreachable_or_not_routed",
                },
            )
            if on_event:
                await on_event("node_skipped", {
                    "nodeId": node_id,
                    "timestamp": int(time.time() * 1000),
                    "reason": "unreachable_or_not_routed",
                })

        result = context.get_final_result()
        result["node_states"] = node_states
        result["visit_counts"] = node_visit_counts
        workflow_completed_at = int(time.time() * 1000)
        engine._record_trace_event(
            "workflow_complete",
            {
                "status": "completed",
                "duration_ms": max(0, workflow_completed_at - workflow_started_at),
            },
        )
        await engine._emit_callback(
            "after_workflow",
            {
                "status": "completed",
                "started_at": workflow_started_at,
                "completed_at": workflow_completed_at,
                "duration_ms": max(0, workflow_completed_at - workflow_started_at),
                "node_states": node_states,
                "visit_counts": node_visit_counts,
            },
        )
        result["trace"] = {
            "started_at": workflow_started_at,
            "completed_at": workflow_completed_at,
            "duration_ms": max(0, workflow_completed_at - workflow_started_at),
            "events": engine._trace_events[-200:],
            "event_count": len(engine._trace_events),
        }
        return result
    except Exception as exc:
        workflow_failed_at = int(time.time() * 1000)
        engine._record_trace_event(
            "workflow_failed",
            {
                "status": "failed",
                "error": str(exc),
                "duration_ms": max(0, workflow_failed_at - workflow_started_at),
            },
        )
        await engine._emit_callback(
            "on_workflow_error",
            {
                "status": "failed",
                "error": str(exc),
                "started_at": workflow_started_at,
                "completed_at": workflow_failed_at,
                "duration_ms": max(0, workflow_failed_at - workflow_started_at),
                "node_states": node_states,
                "visit_counts": node_visit_counts,
            },
        )
        raise


async def execute_node(
    engine: Any,
    node: Dict[str, Any],
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
    outgoing_edges: List[Dict[str, Any]],
    incoming_edge_count: Optional[int] = None,
) -> Tuple[Any, Dict[str, Any]]:
    _ = incoming_edge_count
    node_id = node.get("id", "")
    node_data = node.get("data", {}) or {}
    node_type = engine._get_node_type(node)

    if node_type == "start":
        output = initial_input.get("task") or initial_input.get("input") or initial_input.get("text")
        if output is None:
            output = json.dumps(initial_input, ensure_ascii=False)
        return {
            "text": str(output),
            "input": initial_input,
        }, {"mode": "all"}

    if node_type in {"input_text", "input_image", "input_video", "input_file"}:
        latest_value = input_packets[-1].get("output") if input_packets else context.get_latest_output()
        if isinstance(latest_value, dict):
            output_payload: Dict[str, Any] = dict(latest_value)
        else:
            output_payload = {}
            if latest_value is not None:
                output_payload["text"] = engine._extract_text_from_value(latest_value)

        if "text" not in output_payload:
            output_payload["text"] = engine._derive_node_input_text(context, initial_input, input_packets)
        if "input" not in output_payload and isinstance(initial_input, dict):
            output_payload["input"] = initial_input

        def resolve_config_value(*keys: str) -> Any:
            for key in keys:
                value = node_data.get(key)
                if value is None:
                    continue
                if isinstance(value, str):
                    if not value.strip():
                        continue
                    if "{{" in value:
                        return context.resolve_template(value)
                    return value
                return value
            return None

        if node_type == "input_text":
            configured_text = resolve_config_value("start_task", "startTask", "input_text", "inputText", "text")
            if configured_text is not None:
                text_value = engine._extract_text_from_value(configured_text).strip()
                if text_value:
                    output_payload["text"] = text_value
                    output_payload["task"] = text_value

        if node_type == "input_image":
            def resolve_config_values(*keys: str) -> List[Any]:
                values: List[Any] = []
                for key in keys:
                    raw_value = node_data.get(key)
                    if raw_value is None:
                        continue
                    if isinstance(raw_value, str):
                        text = raw_value.strip()
                        if not text:
                            continue
                        if "{{" in text:
                            resolved = context.resolve_template(raw_value)
                            if isinstance(resolved, list):
                                values.extend(resolved)
                            elif resolved is not None:
                                values.append(resolved)
                            continue
                        values.append(text)
                        continue
                    if isinstance(raw_value, list):
                        values.extend(raw_value)
                        continue
                    values.append(raw_value)
                return values

            candidate_images: List[Any] = []
            if isinstance(initial_input, dict):
                candidate_images.extend([
                    initial_input.get("imageUrl"),
                    initial_input.get("image_url"),
                    initial_input.get("sourceImageUrl"),
                    initial_input.get("source_image_url"),
                ])
                input_image_urls = initial_input.get("imageUrls")
                if isinstance(input_image_urls, list):
                    candidate_images.extend(input_image_urls)
                input_image_urls_snake = initial_input.get("image_urls")
                if isinstance(input_image_urls_snake, list):
                    candidate_images.extend(input_image_urls_snake)
            candidate_images.extend(resolve_config_values(
                "start_image_url",
                "startImageUrl",
                "start_image_urls",
                "startImageUrls",
                "input_image_url",
                "inputImageUrl",
                "input_image_urls",
                "inputImageUrls",
                "image_url",
                "imageUrl",
                "image_urls",
                "imageUrls",
                "url",
                "urls",
            ))

            normalized_images: List[str] = []
            seen_images: Set[str] = set()

            def collect_image(candidate: Any):
                if isinstance(candidate, list):
                    for item in candidate:
                        collect_image(item)
                    return
                normalized_candidate = engine._normalize_possible_image_url(candidate, key_hint="image_url")
                if normalized_candidate and normalized_candidate not in seen_images:
                    seen_images.add(normalized_candidate)
                    normalized_images.append(normalized_candidate)

            for candidate in candidate_images:
                collect_image(candidate)

            if not normalized_images:
                raise ValueError("图片输入节点缺少有效 imageUrl，请上传图片或填写可访问 URL")
            output_payload["imageUrl"] = normalized_images[0]
            output_payload["imageUrls"] = normalized_images

        if node_type == "input_video":
            def resolve_config_values(*keys: str) -> List[Any]:
                values: List[Any] = []
                for key in keys:
                    raw_value = node_data.get(key)
                    if raw_value is None:
                        continue
                    if isinstance(raw_value, str):
                        text = raw_value.strip()
                        if not text:
                            continue
                        if "{{" in text:
                            resolved = context.resolve_template(raw_value)
                            if isinstance(resolved, list):
                                values.extend(resolved)
                            elif resolved is not None:
                                values.append(resolved)
                            continue
                        values.append(text)
                        continue
                    if isinstance(raw_value, list):
                        values.extend(raw_value)
                        continue
                    values.append(raw_value)
                return values

            candidate_videos: List[Any] = []
            if isinstance(initial_input, dict):
                candidate_videos.append(initial_input)
                candidate_videos.extend(
                    [
                        initial_input.get("videoUrl"),
                        initial_input.get("video_url"),
                        initial_input.get("sourceVideoUrl"),
                        initial_input.get("source_video_url"),
                        initial_input.get("sourceVideo"),
                        initial_input.get("source_video"),
                        initial_input.get("provider_file_uri"),
                        initial_input.get("providerFileUri"),
                        initial_input.get("gcs_uri"),
                        initial_input.get("gcsUri"),
                    ]
                )
                input_video_urls = initial_input.get("videoUrls")
                if isinstance(input_video_urls, list):
                    candidate_videos.extend(input_video_urls)
                input_video_urls_snake = initial_input.get("video_urls")
                if isinstance(input_video_urls_snake, list):
                    candidate_videos.extend(input_video_urls_snake)

            candidate_videos.extend(
                resolve_config_values(
                    "start_video_url",
                    "startVideoUrl",
                    "start_video_urls",
                    "startVideoUrls",
                    "input_video_url",
                    "inputVideoUrl",
                    "input_video_urls",
                    "inputVideoUrls",
                    "video_url",
                    "videoUrl",
                    "video_urls",
                    "videoUrls",
                    "source_video",
                    "sourceVideo",
                    "provider_file_uri",
                    "providerFileUri",
                    "gcs_uri",
                    "gcsUri",
                    "url",
                    "urls",
                )
            )

            normalized_video_payloads: List[Any] = []
            normalized_video_urls: List[str] = []
            seen_video_urls: Set[str] = set()

            def collect_video(candidate: Any):
                if isinstance(candidate, list):
                    for item in candidate:
                        collect_video(item)
                    return
                normalized_candidate = engine._build_source_video_payload(candidate)
                if normalized_candidate is None:
                    return
                normalized_video_payloads.append(normalized_candidate)
                normalized_video_url = engine._extract_first_video_url(normalized_candidate)
                if normalized_video_url and normalized_video_url not in seen_video_urls:
                    seen_video_urls.add(normalized_video_url)
                    normalized_video_urls.append(normalized_video_url)

            for candidate in candidate_videos:
                collect_video(candidate)

            if not normalized_video_payloads:
                raise ValueError("视频输入节点缺少有效 videoUrl / providerFileUri / gcsUri")

            primary_video = normalized_video_payloads[0]
            output_payload["sourceVideo"] = primary_video
            if isinstance(primary_video, dict):
                primary_video_url = engine._extract_first_video_url(primary_video)
                if primary_video_url:
                    output_payload["videoUrl"] = primary_video_url
                if normalized_video_urls:
                    output_payload["videoUrls"] = normalized_video_urls
                provider_file_name = primary_video.get("provider_file_name")
                provider_file_uri = primary_video.get("provider_file_uri")
                gcs_uri = primary_video.get("gcs_uri")
                mime_type = primary_video.get("mime_type")
                if provider_file_name:
                    output_payload["provider_file_name"] = provider_file_name
                    output_payload["providerFileName"] = provider_file_name
                if provider_file_uri:
                    output_payload["provider_file_uri"] = provider_file_uri
                    output_payload["providerFileUri"] = provider_file_uri
                if gcs_uri:
                    output_payload["gcs_uri"] = gcs_uri
                    output_payload["gcsUri"] = gcs_uri
                if mime_type:
                    output_payload["mime_type"] = mime_type
                    output_payload["mimeType"] = mime_type
            else:
                primary_video_url = engine._extract_first_video_url(primary_video)
                if primary_video_url:
                    output_payload["videoUrl"] = primary_video_url
                if normalized_video_urls:
                    output_payload["videoUrls"] = normalized_video_urls
                primary_text = str(primary_video or "").strip()
                if primary_text.startswith("files/"):
                    output_payload["provider_file_name"] = primary_text
                    output_payload["providerFileName"] = primary_text
                    output_payload["provider_file_uri"] = primary_text
                    output_payload["providerFileUri"] = primary_text
                if primary_text.startswith("gs://"):
                    output_payload["gcs_uri"] = primary_text
                    output_payload["gcsUri"] = primary_text

        if node_type == "input_file":
            def resolve_config_values(*keys: str) -> List[Any]:
                values: List[Any] = []
                for key in keys:
                    raw_value = node_data.get(key)
                    if raw_value is None:
                        continue
                    if isinstance(raw_value, str):
                        text = raw_value.strip()
                        if not text:
                            continue
                        if "{{" in text:
                            resolved = context.resolve_template(raw_value)
                            if isinstance(resolved, list):
                                values.extend(resolved)
                            elif resolved is not None:
                                values.append(resolved)
                            continue
                        values.append(text)
                        continue
                    if isinstance(raw_value, list):
                        values.extend(raw_value)
                        continue
                    values.append(raw_value)
                return values

            candidate_files: List[Any] = []
            if isinstance(initial_input, dict):
                candidate_files.extend([
                    initial_input.get("fileUrl"),
                    initial_input.get("file_url"),
                    initial_input.get("table"),
                    initial_input.get("csv"),
                ])
                input_file_urls = initial_input.get("fileUrls")
                if isinstance(input_file_urls, list):
                    candidate_files.extend(input_file_urls)
                input_file_urls_snake = initial_input.get("file_urls")
                if isinstance(input_file_urls_snake, list):
                    candidate_files.extend(input_file_urls_snake)
                input_files = initial_input.get("files")
                if isinstance(input_files, list):
                    candidate_files.extend(input_files)

            candidate_files.extend(resolve_config_values(
                "start_file_url",
                "startFileUrl",
                "start_file_urls",
                "startFileUrls",
                "input_file_url",
                "inputFileUrl",
                "input_file_urls",
                "inputFileUrls",
                "file_url",
                "fileUrl",
                "file_urls",
                "fileUrls",
                "url",
                "urls",
            ))

            normalized_files: List[str] = []
            seen_files: Set[str] = set()

            def collect_file(candidate: Any):
                if isinstance(candidate, list):
                    for item in candidate:
                        collect_file(item)
                    return
                normalized_candidate = engine._normalize_possible_file_url(candidate)
                if normalized_candidate and normalized_candidate not in seen_files:
                    seen_files.add(normalized_candidate)
                    normalized_files.append(normalized_candidate)

            for candidate in candidate_files:
                collect_file(candidate)

            if not normalized_files:
                raise ValueError("文件输入节点缺少 fileUrl，请上传文件或填写可访问 URL")
            output_payload["fileUrl"] = normalized_files[0]
            output_payload["fileUrls"] = normalized_files

        return output_payload, {"mode": "all"}

    if node_type == "end":
        inputs = [packet.get("output") for packet in input_packets if "output" in packet]
        if len(inputs) == 0:
            latest = context.get_latest_output()
            return latest or {"text": "工作流执行完成"}, {"mode": "none"}
        if len(inputs) == 1:
            return inputs[0], {"mode": "none"}
        return {
            "results": inputs,
            "count": len(inputs),
            "text": "工作流已汇总完成",
        }, {"mode": "none"}

    if node_type == "agent":
        timeout_seconds = engine._resolve_agent_timeout_seconds(node_data)
        try:
            output = await asyncio.wait_for(
                engine._execute_agent_node(
                    node_id=node_id,
                    node_data=node_data,
                    context=context,
                    initial_input=initial_input,
                    input_packets=input_packets,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            task_type = str(
                node_data.get("agent_task_type")
                or node_data.get("agentTaskType")
                or "chat"
            ).strip().lower() or "chat"
            raise TimeoutError(
                f"Agent node '{node_id}' timed out after {timeout_seconds}s (taskType={task_type})"
            ) from exc
        return output, {"mode": "all"}

    if node_type == "condition":
        expression = node_data.get("expression") or "{{prev.output.text}}"
        condition_result, resolved_expression = engine._evaluate_expression(
            expression=expression,
            context=context,
            initial_input=initial_input,
            input_packets=input_packets,
        )
        branch = "true" if condition_result else "false"
        return {
            "condition": condition_result,
            "branch": branch,
            "expression": expression,
            "resolvedExpression": resolved_expression,
        }, {
            "mode": "branch",
            "branch": branch,
        }

    if node_type == "router":
        strategy = (node_data.get("router_strategy") or node_data.get("routerStrategy") or "intent").strip()
        router_prompt = node_data.get("router_prompt") or node_data.get("routerPrompt") or ""
        input_text = engine._derive_node_input_text(context, initial_input, input_packets)
        selected_index, route_reason = await engine._select_router_branch(
            strategy=strategy,
            router_prompt=router_prompt,
            input_text=input_text,
            outgoing_count=len(outgoing_edges),
        )
        return {
            "strategy": strategy,
            "selectedIndex": selected_index,
            "selectedHandle": f"output-{selected_index}",
            "routerPrompt": router_prompt,
            "text": input_text,
            "routeReason": route_reason,
        }, {
            "mode": "branch_index",
            "branchIndex": selected_index,
        }

    if node_type == "parallel":
        inputs = [packet.get("output") for packet in input_packets if "output" in packet]
        latest_input_payload = inputs[-1] if inputs else None
        output_payload: Dict[str, Any] = {
            "mode": "parallel",
            "joinMode": node_data.get("join_mode") or node_data.get("joinMode") or "wait_all",
            "timeoutSeconds": node_data.get("timeout_seconds") or node_data.get("timeoutSeconds") or 60,
            "branchCount": len(outgoing_edges),
        }
        if latest_input_payload is not None:
            output_payload["input"] = latest_input_payload
            output_payload["text"] = engine._extract_text_from_value(latest_input_payload)
            if isinstance(latest_input_payload, dict):
                for passthrough_key in ("fileUrl", "fileUrls", "imageUrl", "imageUrls"):
                    if passthrough_key in latest_input_payload:
                        output_payload[passthrough_key] = latest_input_payload.get(passthrough_key)
        return {
            **output_payload,
        }, {"mode": "all"}

    if node_type == "merge":
        inputs = [packet.get("output") for packet in input_packets if "output" in packet]
        merge_strategy = (node_data.get("merge_strategy") or node_data.get("mergeStrategy") or "append").strip()
        merged = engine._merge_outputs(inputs, merge_strategy)
        return {
            "mergeStrategy": merge_strategy,
            "inputsCount": len(inputs),
            "merged": merged,
            "text": engine._extract_text_from_value(merged),
        }, {"mode": "all"}

    if node_type == "loop":
        max_iterations = int(node_data.get("max_iterations") or node_data.get("maxIterations") or 3)
        loop_condition = node_data.get("loop_condition") or node_data.get("loopCondition") or "false"
        iteration = context.increment_loop_iteration(node_id)
        condition_result, resolved_expression = engine._evaluate_expression(
            expression=loop_condition,
            context=context,
            initial_input=initial_input,
            input_packets=input_packets,
        )
        should_continue = condition_result and iteration < max_iterations
        return {
            "iteration": iteration,
            "maxIterations": max_iterations,
            "condition": loop_condition,
            "resolvedExpression": resolved_expression,
            "shouldContinue": should_continue,
        }, {
            "mode": "loop",
            "continue": should_continue,
        }

    if node_type == "tool":
        tool_name = (node_data.get("tool_name") or node_data.get("toolName") or "").strip()
        if not tool_name:
            tool_name = "mock_tool"
        tool_args_template = node_data.get("tool_args_template") or node_data.get("toolArgsTemplate") or ""
        tool_args_raw = engine._resolve_tool_args_template(
            template=tool_args_template,
            context=context,
        )
        tool_args = engine._parse_tool_args(tool_args_raw)

        structured_field_map = {
            "toolProviderId": "provider_id",
            "toolModelId": "model_id",
            "toolNumberOfImages": "number_of_images",
            "toolAspectRatio": "aspect_ratio",
            "toolImageSize": "image_size",
            "toolResolutionTier": "resolution",
            "toolImageStyle": "image_style",
            "toolOutputMimeType": "output_mime_type",
            "toolNegativePrompt": "negative_prompt",
            "toolPromptExtend": "prompt_extend",
            "toolAddMagicSuffix": "add_magic_suffix",
            "toolVideoDurationSeconds": "duration_seconds",
            "toolVideoExtensionCount": "video_extension_count",
            "toolSourceVideoUrl": "source_video",
            "toolLastFrameImageUrl": "last_frame_image",
            "toolVideoMaskImageUrl": "video_mask_image",
            "toolVideoMaskMode": "video_mask_mode",
            "toolGenerateAudio": "generate_audio",
            "toolPersonGeneration": "person_generation",
            "toolSubtitleMode": "subtitle_mode",
            "toolSubtitleLanguage": "subtitle_language",
            "toolSubtitleScript": "subtitle_script",
            "toolStoryboardPrompt": "storyboard_prompt",
            "toolEditMode": "mode",
            "toolEditPrompt": "editPrompt",
            "toolReferenceImageUrl": "image_url",
            "toolAnalysisType": "analysisType",
            "tool_provider_id": "provider_id",
            "tool_model_id": "model_id",
            "tool_number_of_images": "number_of_images",
            "tool_aspect_ratio": "aspect_ratio",
            "tool_image_size": "image_size",
            "tool_resolution_tier": "resolution",
            "tool_image_style": "image_style",
            "tool_output_mime_type": "output_mime_type",
            "tool_negative_prompt": "negative_prompt",
            "tool_prompt_extend": "prompt_extend",
            "tool_add_magic_suffix": "add_magic_suffix",
            "tool_video_duration_seconds": "duration_seconds",
            "tool_video_extension_count": "video_extension_count",
            "tool_source_video_url": "source_video",
            "tool_last_frame_image_url": "last_frame_image",
            "tool_video_mask_image_url": "video_mask_image",
            "tool_video_mask_mode": "video_mask_mode",
            "tool_generate_audio": "generate_audio",
            "tool_person_generation": "person_generation",
            "tool_subtitle_mode": "subtitle_mode",
            "tool_subtitle_language": "subtitle_language",
            "tool_subtitle_script": "subtitle_script",
            "tool_storyboard_prompt": "storyboard_prompt",
            "tool_edit_mode": "mode",
            "tool_edit_prompt": "editPrompt",
            "tool_reference_image_url": "image_url",
            "tool_analysis_type": "analysisType",
        }
        for src_key, dst_key in structured_field_map.items():
            val = node_data.get(src_key)
            if val is not None and str(val).strip() and dst_key not in tool_args:
                tool_args[dst_key] = val

        tool_result = await engine._execute_builtin_tool(
            tool_name=tool_name,
            tool_args=tool_args,
            context=context,
            input_packets=input_packets,
        )
        output = {
            "toolName": tool_name,
            "args": tool_args,
            "result": tool_result,
            "text": engine._extract_text_from_value(tool_result),
        }
        image_urls = engine._extract_result_image_urls(tool_result)
        if image_urls:
            output["imageUrl"] = image_urls[0]
            output["imageUrls"] = image_urls
        video_url = engine._extract_first_video_url(tool_result)
        if video_url:
            output["videoUrl"] = video_url
            output["videoUrls"] = [video_url]
        if isinstance(tool_result, dict):
            audio_url = tool_result.get("audioUrl") or tool_result.get("audio_url")
            if not audio_url:
                raw_url = tool_result.get("url")
                raw_mime_type = str(tool_result.get("mime_type") or tool_result.get("mimeType") or "").strip().lower()
                if isinstance(raw_url, str) and raw_url.strip() and raw_mime_type.startswith("audio/"):
                    audio_url = raw_url
            if isinstance(audio_url, str) and audio_url.strip():
                output["audioUrl"] = audio_url.strip()
                output["audioUrls"] = [audio_url.strip()]
            for key in ("provider_file_name", "providerFileName", "provider_file_uri", "providerFileUri", "gcs_uri", "gcsUri", "mime_type", "mimeType"):
                if tool_result.get(key) is not None:
                    output[key] = tool_result.get(key)
        return output, {"mode": "all"}

    if node_type == "human":
        approval_prompt = node_data.get("approval_prompt") or node_data.get("approvalPrompt") or "请人工确认是否继续执行"
        auto_approve = engine._to_bool(
            node_data.get("auto_approve", node_data.get("autoApprove", True)),
            default=True,
        )
        input_text = engine._derive_node_input_text(context, initial_input, input_packets)
        return {
            "approved": auto_approve,
            "approvalPrompt": approval_prompt,
            "note": "Phase 3 默认自动通过（可在后续版本接入真实人工确认）",
            "text": input_text,
        }, {"mode": "all" if auto_approve else "none"}

    logger.warning(f"[WorkflowEngine] Unknown node type: {node_type}, fallback to passthrough")
    passthrough_text = engine._derive_node_input_text(context, initial_input, input_packets)
    return {
        "text": passthrough_text or f"节点类型 {node_type} 暂不支持，已跳过执行",
        "nodeType": node_type,
    }, {"mode": "all"}
