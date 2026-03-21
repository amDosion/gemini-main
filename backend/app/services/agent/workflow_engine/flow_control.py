"""
Flow control and routing helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..execution_context import ExecutionContext
from ....utils.safe_expression_eval import safe_eval_expression

logger = logging.getLogger(__name__)


def resolve_max_visits(engine: Any, node_type: str, node_data: Dict[str, Any]) -> int:
    if node_type == "loop":
        max_iterations = int(node_data.get("max_iterations") or node_data.get("maxIterations") or 3)
        return max(2, max_iterations + 2)
    return engine.DEFAULT_MAX_NODE_VISITS


def resolve_max_parallel_nodes(engine: Any, initial_input: Dict[str, Any]) -> int:
    raw = None
    if isinstance(initial_input, dict):
        raw = (
            initial_input.get("max_parallel_nodes")
            or initial_input.get("maxParallelNodes")
            or initial_input.get("workflow_max_parallel_nodes")
            or initial_input.get("workflowMaxParallelNodes")
        )

    if raw is not None and str(raw).strip():
        try:
            parsed = int(float(raw))
        except Exception:
            parsed = engine.DEFAULT_MAX_PARALLEL_NODES
        return max(1, min(parsed, 32))

    return engine.DEFAULT_MAX_PARALLEL_NODES


def select_outgoing_edges(
    engine: Any,
    node: Dict[str, Any],
    outgoing_edges: List[Dict[str, Any]],
    routing: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not outgoing_edges:
        return []

    mode = (routing or {}).get("mode", "all")
    if mode == "none":
        return []
    if mode == "all":
        return outgoing_edges

    if mode == "branch":
        branch = (routing.get("branch") or "true").lower()
        preferred_handle = "output-true" if branch == "true" else "output-false"
        selected = [edge for edge in outgoing_edges if engine._get_source_handle(edge) == preferred_handle]
        if selected:
            return selected

        sorted_edges = sorted(outgoing_edges, key=lambda edge: edge.get("id", ""))
        idx = 0 if branch == "true" else min(1, len(sorted_edges) - 1)
        return [sorted_edges[idx]]

    if mode == "branch_index":
        branch_index = int(routing.get("branchIndex", 0))
        preferred_handle = f"output-{branch_index}"
        selected = [edge for edge in outgoing_edges if engine._get_source_handle(edge) == preferred_handle]
        if selected:
            return selected

        sorted_edges = sorted(outgoing_edges, key=lambda edge: edge.get("id", ""))
        idx = branch_index % len(sorted_edges)
        return [sorted_edges[idx]]

    if mode == "loop":
        should_continue = bool(routing.get("continue"))
        preferred_handle = "output-true" if should_continue else "output-false"
        selected = [edge for edge in outgoing_edges if engine._get_source_handle(edge) == preferred_handle]
        if selected:
            return selected

        sorted_edges = sorted(outgoing_edges, key=lambda edge: edge.get("id", ""))
        idx = 0 if should_continue else min(1, len(sorted_edges) - 1)
        return [sorted_edges[idx]]

    if mode == "edge_id":
        edge_id = routing.get("edgeId")
        if edge_id:
            selected = [edge for edge in outgoing_edges if edge.get("id") == edge_id]
            if selected:
                return selected

    node_id = node.get("id", "unknown")
    logger.warning("[WorkflowEngine] Unknown routing mode '%s' on node %s, fallback to all", mode, node_id)
    return outgoing_edges


def get_source_handle(engine: Any, edge: Dict[str, Any]) -> str:
    _ = engine
    return edge.get("source_handle") or edge.get("sourceHandle") or ""


def get_node_type(engine: Any, node: Dict[str, Any]) -> str:
    _ = engine
    node_data = node.get("data", {}) or {}
    node_type = node_data.get("type") or node.get("type") or "unknown"
    return str(node_type).strip().lower().replace("-", "_")


def derive_node_input_text(
    engine: Any,
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
) -> str:
    if input_packets:
        latest_packet = input_packets[-1]
        return engine._extract_text_from_value(latest_packet.get("output"))

    latest_output = context.get_latest_output()
    if latest_output is not None:
        return engine._extract_text_from_value(latest_output)

    task = initial_input.get("task") or initial_input.get("input") or initial_input.get("text") or ""
    return str(task)


def evaluate_contains_clause(engine: Any, clause: str) -> Optional[bool]:
    _ = engine
    raw_clause = str(clause or "").strip()
    if not raw_clause:
        return None

    matched = re.match(r"^(.*?)\s+contains\s+(.+)$", raw_clause, flags=re.IGNORECASE)
    if not matched:
        return None

    left = str(matched.group(1) or "").strip().strip("\"'")
    right = str(matched.group(2) or "").strip().strip("\"'")
    if not right:
        return False
    return right in left


def evaluate_contains_expression(engine: Any, expression_text: str) -> Optional[bool]:
    text = str(expression_text or "").strip()
    if not text or " contains " not in text.lower():
        return None

    parts = re.split(r"\s+(or|and)\s+", text, flags=re.IGNORECASE)
    if not parts:
        return None

    first_value = engine._evaluate_contains_clause(parts[0])
    if first_value is None:
        return None

    result = bool(first_value)
    idx = 1
    while idx + 1 < len(parts):
        operator = str(parts[idx] or "").strip().lower()
        clause = parts[idx + 1]
        clause_value = engine._evaluate_contains_clause(clause)
        if clause_value is None:
            return None
        if operator == "and":
            result = result and bool(clause_value)
        else:
            result = result or bool(clause_value)
        idx += 2

    return result


def evaluate_expression(
    engine: Any,
    expression: str,
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
) -> Tuple[bool, str]:
    if expression is None:
        return False, ""

    resolved = context.resolve_template(expression)
    if isinstance(resolved, bool):
        return resolved, str(resolved)
    if isinstance(resolved, (int, float)):
        return resolved != 0, str(resolved)

    resolved_text = str(resolved).strip()
    if resolved_text == "":
        return False, resolved_text

    lowered = resolved_text.lower()
    if lowered in ("true", "yes", "1"):
        return True, resolved_text
    if lowered in ("false", "no", "0"):
        return False, resolved_text

    includes_match = re.match(r'^(.*)\.includes\((.*)\)$', resolved_text)
    if includes_match:
        left = includes_match.group(1).strip().strip("\"'")
        right = includes_match.group(2).strip().strip("\"'")
        return right in left, resolved_text

    contains_value = engine._evaluate_contains_expression(resolved_text)
    if contains_value is not None:
        return contains_value, resolved_text

    normalized = (
        resolved_text
        .replace("&&", " and ")
        .replace("||", " or ")
        .replace("===", "==")
        .replace("!==", "!=")
    )
    normalized = re.sub(r'\btrue\b', "True", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\bfalse\b', "False", normalized, flags=re.IGNORECASE)

    safe_locals = {
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "abs": abs,
        "min": min,
        "max": max,
        "input": initial_input,
        "prev": context.get_latest_output(),
        "packets": input_packets,
    }

    try:
        value = safe_eval_expression(
            normalized,
            variables=safe_locals,
            functions={
                "len": len,
                "int": int,
                "float": float,
                "str": str,
                "abs": abs,
                "min": min,
                "max": max,
            },
        )
        return bool(value), resolved_text
    except Exception:
        logger.warning("[WorkflowEngine] Failed to evaluate expression: %s", resolved_text)
        return False, resolved_text


async def select_router_branch(
    engine: Any,
    strategy: str,
    router_prompt: str,
    input_text: str,
    outgoing_count: int,
) -> Tuple[int, str]:
    if outgoing_count <= 1:
        return 0, "single_branch"

    normalized_strategy = (strategy or "intent").strip().lower()
    if normalized_strategy == "llm":
        try:
            provider_id, model_id = engine._select_text_chat_target()
            routing_prompt = (
                "你是工作流路由器。"
                f"请根据输入与规则，从 0 到 {outgoing_count - 1} 中选一个最合适的分支编号。"
                "只输出 JSON，格式：{\"branchIndex\": number, \"reason\": \"...\"}"
            )
            if router_prompt and router_prompt.strip():
                routing_prompt = f"{routing_prompt}\n\n路由规则：\n{router_prompt.strip()}"

            response = await engine._invoke_llm_chat(
                provider_id=provider_id,
                model_id=model_id,
                messages=[{
                    "role": "user",
                    "content": f"输入内容：\n{input_text or ''}\n\n请输出 JSON。"
                }],
                system_prompt=routing_prompt,
                temperature=0.1,
                max_tokens=256,
            )
            content = str(response.get("text", "") or "").strip()
            parsed_idx = None
            parsed_reason = "llm"
            if content:
                try:
                    payload = json.loads(content)
                    if isinstance(payload, dict):
                        parsed_idx = int(payload.get("branchIndex", 0))
                        if isinstance(payload.get("reason"), str) and payload.get("reason").strip():
                            parsed_reason = f"llm:{payload.get('reason').strip()}"
                except Exception:
                    matched = re.search(r"-?\d+", content)
                    if matched:
                        parsed_idx = int(matched.group(0))

            if parsed_idx is not None:
                return parsed_idx % outgoing_count, parsed_reason
        except Exception as exc:
            logger.warning("[WorkflowEngine] LLM router failed, fallback to heuristic: %s", exc)

    index, reason = engine._select_router_branch_heuristic(
        strategy=normalized_strategy,
        router_prompt=router_prompt,
        input_text=input_text,
        outgoing_count=outgoing_count,
    )
    return index, reason


def select_router_branch_heuristic(
    engine: Any,
    strategy: str,
    router_prompt: str,
    input_text: str,
    outgoing_count: int,
) -> Tuple[int, str]:
    _ = engine
    text = (input_text or "").lower()
    if strategy == "keyword":
        rules = [line.strip() for line in router_prompt.splitlines() if line.strip()]
        for rule in rules:
            if ":" not in rule:
                continue
            idx_raw, keywords_raw = rule.split(":", 1)
            idx_raw = idx_raw.strip()
            if not idx_raw.isdigit():
                continue
            idx = int(idx_raw)
            keywords = [kw.strip().lower() for kw in keywords_raw.split(",") if kw.strip()]
            if any(keyword in text for keyword in keywords):
                return idx % outgoing_count, f"keyword:{','.join(keywords)}"

    if any(keyword in text for keyword in ("error", "失败", "异常", "bug")):
        return min(1, outgoing_count - 1), "intent:error"
    if any(keyword in text for keyword in ("审核", "审批", "confirm", "approve", "人工")):
        return outgoing_count - 1, "intent:approval"
    if any(keyword in text for keyword in ("总结", "summary", "报告", "report")):
        return 0, "intent:summary"

    hash_source = (router_prompt or "") + "|" + (input_text or "")
    hash_value = sum(ord(ch) for ch in hash_source)
    return hash_value % outgoing_count, "intent:hash"


def merge_outputs(engine: Any, inputs: List[Any], strategy: str) -> Any:
    if not inputs:
        return {"text": ""}

    if strategy == "latest":
        return inputs[-1]

    if strategy == "json_merge":
        merged: Dict[str, Any] = {}
        for item in inputs:
            if isinstance(item, dict):
                merged.update(item)
            else:
                merged.setdefault("items", []).append(item)
        return merged

    text_chunks = [engine._extract_text_from_value(item) for item in inputs]
    text_chunks = [chunk for chunk in text_chunks if chunk]
    return {
        "results": inputs,
        "text": "\n\n".join(text_chunks).strip(),
    }


def parse_tool_args(engine: Any, raw_args: Any) -> Dict[str, Any]:
    _ = engine
    if raw_args is None:
        return {}
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, list):
        return {"items": raw_args}

    text = str(raw_args).strip()
    if text == "":
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"items": parsed}
        return {"value": parsed}
    except Exception:
        return {"input": text}


def resolve_tool_args_template(engine: Any, template: Any, context: ExecutionContext) -> Any:
    """
    解析 toolArgsTemplate。

    关键策略：
    1) 对 JSON 字符串先解析为 Python 对象，再逐字段做模板替换，避免替换后 JSON 失效。
    2) 对 dict/list 模板做递归替换。
    3) 其他字符串沿用原模板解析逻辑。
    """
    if template is None or template == "":
        return {}

    if isinstance(template, (dict, list)):
        return engine._resolve_template_value(template, context)

    if not isinstance(template, str):
        return template

    stripped = template.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            return engine._resolve_template_value(parsed, context)
        except Exception:
            return context.resolve_template(template)

    return context.resolve_template(template)


def resolve_template_value(engine: Any, value: Any, context: ExecutionContext) -> Any:
    if isinstance(value, str):
        return context.resolve_template(value)
    if isinstance(value, list):
        return [engine._resolve_template_value(item, context) for item in value]
    if isinstance(value, dict):
        return {
            key: engine._resolve_template_value(item, context)
            for key, item in value.items()
        }
    return value
