"""
Builtin tool helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..execution_context import ExecutionContext

logger = logging.getLogger(__name__)


def normalize_search_items(payload: Any, max_items: int) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []

    def push_item(title: Any, snippet: Any, url: Any):
        title_text = str(title or "").strip()
        snippet_text = str(snippet or "").strip()
        url_text = str(url or "").strip()
        if not title_text and not snippet_text:
            return
        items.append({
            "title": title_text or "搜索结果",
            "snippet": snippet_text,
            "url": url_text,
        })

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = []

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            push_item(
                item.get("title") or item.get("name"),
                item.get("snippet") or item.get("description") or item.get("text"),
                item.get("url") or item.get("link"),
            )
    elif isinstance(payload, dict):
        abstract = payload.get("AbstractText")
        abstract_url = payload.get("AbstractURL")
        abstract_source = payload.get("AbstractSource")
        if abstract:
            push_item(
                f"{abstract_source or '摘要'}",
                abstract,
                abstract_url,
            )

        for item in payload.get("Results") or []:
            if isinstance(item, dict):
                push_item(
                    item.get("Text"),
                    item.get("Text"),
                    item.get("FirstURL"),
                )

        def walk_related(related_items: Any):
            if not isinstance(related_items, list):
                return
            for related in related_items:
                if not isinstance(related, dict):
                    continue
                if isinstance(related.get("Topics"), list):
                    walk_related(related.get("Topics"))
                    continue
                push_item(
                    related.get("Text"),
                    related.get("Text"),
                    related.get("FirstURL"),
                )

        walk_related(payload.get("RelatedTopics"))

    deduped: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for item in items:
        identity = (item.get("title", ""), item.get("url", ""))
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(item)
        if len(deduped) >= max_items:
            break
    return deduped


def fetch_duckduckgo_results(query: str, region: str) -> List[Dict[str, str]]:
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "no_redirect": "1",
        "skip_disambig": "1",
    }
    if region:
        params["kl"] = region

    url = f"https://api.duckduckgo.com/?{urlencode(params)}"
    request = Request(
        url=url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 WorkflowEngine/1.0",
        }
    )
    with urlopen(request, timeout=8) as response:  # nosec B310
        raw = response.read()
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    return normalize_search_items(payload, max_items=10)


async def run_web_search_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    query = (
        engine._get_tool_arg(tool_args, "query", "q", "text")
        or engine._extract_text_from_value(latest_input)
        or "workflow query"
    )
    region = str(engine._get_tool_arg(tool_args, "region", "locale", "market", "lang") or "").strip()
    max_items = engine._to_int(
        engine._get_tool_arg(tool_args, "max_items", "maxItems", "limit", "top_k", "topK"),
        default=5,
        minimum=1,
        maximum=10,
    ) or 5

    provider = "duckduckgo"
    error_notes: List[str] = []
    items: List[Dict[str, str]] = []
    try:
        items = await asyncio.to_thread(fetch_duckduckgo_results, str(query), region)
    except Exception as exc:
        error_notes.append(f"duckduckgo:{exc}")

    if not items:
        try:
            from ...gemini.common.browser import web_search as fallback_search
            fallback_payload = await asyncio.to_thread(fallback_search, str(query))
            items = normalize_search_items(fallback_payload, max_items=max_items)
            provider = "fallback_search"
        except Exception as exc:
            error_notes.append(f"fallback:{exc}")

    items = items[:max_items]
    status = "completed" if items else "no_results"
    summary = (
        f"共找到 {len(items)} 条结果。"
        if items else
        "未检索到有效结果。"
    )
    response: Dict[str, Any] = {
        "tool": "web_search",
        "query": str(query),
        "provider": provider,
        "region": region or None,
        "items": items,
        "count": len(items),
        "status": status,
        "summary": summary,
        "text": "\n".join(
            f"- {item.get('title')}: {item.get('snippet')}".strip()
            for item in items
        ).strip() or summary,
    }
    if error_notes:
        response["errors"] = error_notes
    return response


def extract_mcp_server_map(root: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(root, dict):
        return {}

    raw_servers = root.get("mcpServers")
    if isinstance(raw_servers, dict):
        return {
            str(key): value
            for key, value in raw_servers.items()
            if isinstance(value, dict)
        }

    if root and all(isinstance(value, dict) for value in root.values()):
        return {
            str(key): value
            for key, value in root.items()
            if isinstance(value, dict)
        }

    return {}


def normalize_mcp_args_list(raw_args: Any) -> Optional[List[str]]:
    if not isinstance(raw_args, list):
        return None
    return [str(item) for item in raw_args]


def normalize_mcp_env_map(raw_env: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw_env, dict):
        return None
    return {str(key): str(value) for key, value in raw_env.items()}


def load_workflow_mcp_server_config(
    engine: Any,
    requested_server_key: str = "",
) -> Tuple[str, Any, str]:
    from ....models.db_models import UserMcpConfig
    from ...mcp.types import (
        MCPServerConfig,
        MCPServerType,
        validate_mcp_stdio_command_policy,
    )
    from ....core.config import settings as app_settings

    user_id = engine._get_workflow_user_id()
    if not user_id:
        raise ValueError("workflow user_id is empty; cannot call MCP tool")
    if engine.db is None:
        raise ValueError("workflow db is unavailable; cannot call MCP tool")

    record = engine.db.query(UserMcpConfig).filter(UserMcpConfig.user_id == user_id).first()
    if not record or not str(record.config_json or "").strip():
        raise ValueError("当前用户未配置 MCP 服务")

    try:
        root = json.loads(record.config_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"当前用户 MCP 配置 JSON 无效: {exc.msg}") from exc

    server_map = extract_mcp_server_map(root)
    if not server_map:
        raise ValueError("当前用户 MCP 配置中未找到可用服务")

    enabled_servers = {
        key: value
        for key, value in server_map.items()
        if isinstance(value, dict) and not (value.get("disabled") is True or value.get("enabled") is False)
    }
    if not enabled_servers:
        raise ValueError("当前用户所有 MCP 服务均已禁用")

    selected_key = str(requested_server_key or "").strip()
    if selected_key:
        selected_config = enabled_servers.get(selected_key)
        if not selected_config:
            raise ValueError(f"MCP 服务不存在或已禁用: {selected_key}")
    else:
        preferred_candidates = [
            key
            for key, value in enabled_servers.items()
            if "sorftime" in key.lower() or "sorftime" in str(value.get("name") or "").lower()
        ]
        if len(enabled_servers) == 1:
            selected_key, selected_config = next(iter(enabled_servers.items()))
        elif len(preferred_candidates) == 1:
            selected_key = preferred_candidates[0]
            selected_config = enabled_servers[selected_key]
        else:
            raise ValueError("检测到多个 MCP 服务，请在工具参数中显式提供 mcp_server_key")

    raw_type = str(
        selected_config.get("serverType")
        or selected_config.get("server_type")
        or selected_config.get("type")
        or ""
    ).strip().lower()
    if raw_type == "stdio":
        server_type = MCPServerType.STDIO
    elif raw_type == "sse":
        server_type = MCPServerType.SSE
    elif raw_type in {"streamablehttp", "streamable_http", "streamable-http"}:
        server_type = MCPServerType.STREAMABLE_HTTP
    elif raw_type == "http":
        server_type = MCPServerType.HTTP
    elif selected_config.get("command"):
        server_type = MCPServerType.STDIO
    else:
        server_type = MCPServerType.HTTP

    timeout_raw = selected_config.get("timeout", 30.0)
    try:
        timeout = float(timeout_raw)
    except (TypeError, ValueError):
        timeout = 30.0

    mcp_config = MCPServerConfig(
        server_type=server_type,
        command=selected_config.get("command"),
        args=normalize_mcp_args_list(selected_config.get("args")),
        env=normalize_mcp_env_map(selected_config.get("env")),
        url=selected_config.get("url"),
        timeout=timeout,
    )
    mcp_config.validate()
    validate_mcp_stdio_command_policy(
        mcp_config,
        policy=app_settings.mcp_stdio_command_policy,
        allowed_commands=app_settings.mcp_stdio_allowed_commands,
        context=f"workflow-mcp:{selected_key}",
    )

    session_material = json.dumps(selected_config, ensure_ascii=False, sort_keys=True)
    session_fingerprint = uuid.uuid5(uuid.NAMESPACE_URL, session_material).hex[:12]
    session_id = f"workflow:{user_id}:{selected_key}:{session_fingerprint}"
    return selected_key, mcp_config, session_id


async def run_mcp_tool_call(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    from ...mcp.mcp_manager import get_mcp_manager
    from ...mcp.result_normalizer import normalize_sorftime_result

    requested_server_key = str(
        engine._get_tool_arg(tool_args, "mcp_server_key", "server_key", "serverKey") or ""
    ).strip()
    requested_tool_name = str(
        engine._get_tool_arg(tool_args, "mcp_tool_name", "tool_name", "toolName") or ""
    ).strip()

    if not requested_tool_name:
        raise ValueError("mcp_tool_call 缺少 mcp_tool_name")

    raw_arguments = engine._get_tool_arg(tool_args, "arguments", "args", "tool_args", "toolArgs")
    arguments: Dict[str, Any] = dict(raw_arguments) if isinstance(raw_arguments, dict) else {}
    reserved_keys = {
        "mcp_server_key",
        "server_key",
        "serverKey",
        "mcp_tool_name",
        "tool_name",
        "toolName",
        "arguments",
        "args",
        "tool_args",
        "toolArgs",
    }
    for key, value in tool_args.items():
        if key in reserved_keys:
            continue
        arguments.setdefault(key, value)

    if not arguments and isinstance(latest_input, dict):
        for fallback_key in ("args", "arguments", "result", "normalized", "parsed"):
            candidate = latest_input.get(fallback_key)
            if isinstance(candidate, dict):
                arguments = dict(candidate)
                break

    server_key, mcp_config, session_id = load_workflow_mcp_server_config(engine, requested_server_key)
    manager = get_mcp_manager()
    await manager.create_session(session_id, mcp_config)
    result = await manager.call_tool(session_id, requested_tool_name, arguments)

    if not result.success or result.is_error:
        error_text = str(result.error or "MCP tool call failed").strip() or "MCP tool call failed"
        return {
            "tool": "mcp_tool_call",
            "serverKey": server_key,
            "mcpToolName": requested_tool_name,
            "args": arguments,
            "status": "error",
            "success": False,
            "error": error_text,
            "text": error_text,
        }

    normalized_payload = normalize_sorftime_result(requested_tool_name, result.result)
    return {
        "tool": "mcp_tool_call",
        "serverKey": server_key,
        "mcpToolName": requested_tool_name,
        "args": arguments,
        "status": "completed",
        "success": True,
        **normalized_payload,
    }


async def run_read_webpage_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    from ...gemini.common.browser import read_webpage

    url = str(engine._get_tool_arg(tool_args, "url") or "").strip()
    if not url and isinstance(latest_input, dict):
        url = str(
            latest_input.get("url")
            or engine._resolve_generic_path(latest_input, "items.0.url")
            or ""
        ).strip()
    if not url:
        raise ValueError("read_webpage 缺少 url")

    max_length = engine._to_int(
        engine._get_tool_arg(tool_args, "max_length", "maxLength"),
        default=50000,
        minimum=1000,
        maximum=100000,
    ) or 50000

    content = await asyncio.to_thread(read_webpage, url, max_length)
    lowered = str(content or "").strip().lower()
    status = "error" if lowered.startswith("error") or lowered.startswith("an unexpected error occurred") else "completed"
    return {
        "tool": "read_webpage",
        "url": url,
        "status": status,
        "content": content,
        "text": str(content or "")[:1200] if status == "completed" else str(content or ""),
    }


async def run_selenium_browse_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    from ...gemini.common.browser import selenium_browse

    url = str(engine._get_tool_arg(tool_args, "url") or "").strip()
    if not url and isinstance(latest_input, dict):
        url = str(
            latest_input.get("url")
            or engine._resolve_generic_path(latest_input, "items.0.url")
            or ""
        ).strip()
    if not url:
        raise ValueError("selenium_browse 缺少 url")

    browse_kwargs = {
        "steps": engine._get_tool_arg(tool_args, "steps") or [],
        "max_length": engine._to_int(
            engine._get_tool_arg(tool_args, "max_length", "maxLength"),
            default=50000,
            minimum=1000,
            maximum=100000,
        ) or 50000,
        "capture_screenshot": engine._to_bool(
            engine._get_tool_arg(tool_args, "capture_screenshot", "captureScreenshot"),
            default=True,
        ),
        "auto_scroll": engine._to_bool(
            engine._get_tool_arg(tool_args, "auto_scroll", "autoScroll"),
            default=True,
        ),
        "scroll_pause": engine._to_float(
            engine._get_tool_arg(tool_args, "scroll_pause", "scrollPause"),
            default=1.0,
            minimum=0.1,
            maximum=5.0,
        ) or 1.0,
        "max_scrolls": engine._to_int(
            engine._get_tool_arg(tool_args, "max_scrolls", "maxScrolls"),
            default=10,
            minimum=1,
            maximum=40,
        ) or 10,
        "user_id": engine._get_workflow_user_id() or "workflow",
    }
    result = await asyncio.to_thread(selenium_browse, url, **browse_kwargs)

    error_text = str((result or {}).get("error") or "").strip()
    screenshot_base64 = str((result or {}).get("screenshot") or "").strip()
    screenshot_data_url = (
        f"data:image/png;base64,{screenshot_base64}"
        if screenshot_base64
        else None
    )
    content = str((result or {}).get("content") or "").strip()

    payload: Dict[str, Any] = {
        "tool": "selenium_browse",
        "url": url,
        "status": "error" if error_text else "completed",
        "content": content,
        "text": error_text or content[:1200] or "浏览完成。",
    }
    if screenshot_data_url:
        payload["imageUrl"] = screenshot_data_url
        payload["screenshotUrl"] = screenshot_data_url
    if error_text:
        payload["error"] = error_text
    return payload


def get_sheet_stage_artifact_service(engine: Any):
    artifact_service = getattr(engine, "_sheet_stage_artifact_service", None)
    if artifact_service is None:
        from ..sheet_stage_protocol_service import get_default_sheet_stage_artifact_service

        artifact_service = get_default_sheet_stage_artifact_service()
        engine._sheet_stage_artifact_service = artifact_service
    return artifact_service


def extract_sheet_stage_artifact_ref_from_value(
    engine: Any,
    value: Any,
    depth: int = 0,
) -> Optional[Dict[str, Any]]:
    if depth >= 4 or value is None:
        return None

    if isinstance(value, dict):
        from ..adk_builtin_tools import normalize_sheet_artifact_ref

        try:
            normalized = normalize_sheet_artifact_ref(value, required=False)
        except Exception:
            normalized = None
        if normalized:
            return normalized

        for key in ("artifact", "result", "data", "payload", "output"):
            if key in value:
                nested = extract_sheet_stage_artifact_ref_from_value(engine, value.get(key), depth + 1)
                if nested:
                    return nested
        return None

    if isinstance(value, list):
        for item in value:
            nested = extract_sheet_stage_artifact_ref_from_value(engine, item, depth + 1)
            if nested:
                return nested
    return None


def extract_sheet_stage_session_id_from_value(
    engine: Any,
    value: Any,
    depth: int = 0,
) -> str:
    if depth >= 4 or value is None:
        return ""

    if isinstance(value, dict):
        for key in ("session_id", "sessionId"):
            session_id = str(value.get(key) or "").strip()
            if session_id:
                return session_id
        for key in ("result", "data", "payload", "output"):
            nested = extract_sheet_stage_session_id_from_value(engine, value.get(key), depth + 1)
            if nested:
                return nested
        return ""

    if isinstance(value, list):
        for item in value:
            nested = extract_sheet_stage_session_id_from_value(engine, item, depth + 1)
            if nested:
                return nested
    return ""


def build_sheet_stage_request_payload(
    engine: Any,
    *,
    stage: str,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    request_payload = dict(tool_args or {})
    request_payload["stage"] = stage
    request_payload.setdefault("protocol_version", "sheet-stage/v1")

    if stage == "ingest":
        has_direct_source = any(
            request_payload.get(key) is not None and str(request_payload.get(key)).strip()
            for key in ("file_url", "fileUrl", "data_url", "dataUrl", "content")
        )
        if not has_direct_source:
            if isinstance(latest_input, dict):
                for source_key, target_key in (
                    ("fileUrl", "file_url"),
                    ("file_url", "file_url"),
                    ("dataUrl", "data_url"),
                    ("data_url", "data_url"),
                    ("content", "content"),
                ):
                    value = latest_input.get(source_key)
                    if value is not None and str(value).strip():
                        request_payload[target_key] = value
                        break
            elif isinstance(latest_input, str) and latest_input.strip():
                latest_text = latest_input.strip()
                if latest_text.startswith("data:"):
                    request_payload["data_url"] = latest_text
                elif "://" in latest_text:
                    request_payload["file_url"] = latest_text
                else:
                    request_payload["content"] = latest_text
        return request_payload

    if not (
        request_payload.get("artifact") is not None and str(request_payload.get("artifact")).strip()
    ):
        artifact_ref = extract_sheet_stage_artifact_ref_from_value(engine, latest_input)
        if artifact_ref:
            request_payload["artifact"] = artifact_ref

    if not (
        request_payload.get("session_id") is not None and str(request_payload.get("session_id")).strip()
    ) and not (
        request_payload.get("sessionId") is not None and str(request_payload.get("sessionId")).strip()
    ):
        session_id = extract_sheet_stage_session_id_from_value(engine, latest_input)
        if session_id:
            request_payload["session_id"] = session_id

    if stage == "query" and not (
        request_payload.get("query") is not None and str(request_payload.get("query")).strip()
    ):
        if isinstance(latest_input, str) and latest_input.strip():
            request_payload["query"] = latest_input.strip()

    return request_payload


async def run_sheet_stage_tool(
    engine: Any,
    *,
    normalized_tool_name: str,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    from ..sheet_stage_protocol_service import (
        SheetStageProtocolError,
        build_sheet_stage_failure_detail,
        execute_sheet_stage_protocol_request,
        extract_sheet_stage_summary_text,
    )

    stage_by_tool_name = {
        "sheet_stage_ingest": "ingest",
        "sheet_stage_profile": "profile",
        "sheet_stage_query": "query",
        "sheet_stage_export": "export",
    }
    stage = stage_by_tool_name.get(normalized_tool_name, "")
    if not stage:
        raise ValueError(f"unsupported sheet-stage tool: {normalized_tool_name}")

    request_payload = build_sheet_stage_request_payload(
        engine,
        stage=stage,
        tool_args=tool_args,
        latest_input=latest_input,
    )

    try:
        result = await execute_sheet_stage_protocol_request(
            request_body=request_payload,
            user_id=engine._get_workflow_user_id(),
            artifact_service=get_sheet_stage_artifact_service(engine),
        )
    except SheetStageProtocolError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if isinstance(detail, dict):
            summary_text = extract_sheet_stage_summary_text(detail)
            if summary_text:
                detail.setdefault("text", summary_text)
        return detail or {
            "status": "failed",
            "error": {"message": str(exc)},
        }
    except (ValueError, PermissionError) as exc:
        detail = build_sheet_stage_failure_detail(
            stage=stage,
            session_id=str(
                request_payload.get("session_id")
                or request_payload.get("sessionId")
                or extract_sheet_stage_session_id_from_value(engine, latest_input)
                or ""
            ),
            message=str(exc),
            error_code="SHEET_STAGE_INVALID_REQUEST",
        )
        summary_text = extract_sheet_stage_summary_text(detail)
        if summary_text:
            detail["text"] = summary_text
        return detail
    except Exception as exc:
        detail = build_sheet_stage_failure_detail(
            stage=stage,
            session_id=str(
                request_payload.get("session_id")
                or request_payload.get("sessionId")
                or extract_sheet_stage_session_id_from_value(engine, latest_input)
                or ""
            ),
            message=str(exc),
            error_code="SHEET_STAGE_UNEXPECTED",
        )
        summary_text = extract_sheet_stage_summary_text(detail)
        if summary_text:
            detail["text"] = summary_text
        return detail

    if isinstance(result, dict):
        summary_text = extract_sheet_stage_summary_text(result)
        if summary_text:
            result = {
                **result,
                "text": summary_text,
            }
    return result


async def execute_builtin_tool(
    engine: Any,
    tool_name: str,
    tool_args: Dict[str, Any],
    context: ExecutionContext,
    input_packets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    name = (tool_name or "tool").strip().lower()
    normalized_name = name.replace("-", "_")
    latest_input = input_packets[-1].get("output") if input_packets else context.get_latest_output()
    category = "generic"
    scheduling_policy = {
        "scheduler": "deterministic_priority",
        "priority": 50,
        "tool": normalized_name,
    }
    if normalized_name in {
        "google_search",
        "web_search",
        "search",
        "read_webpage",
        "read_page",
        "read_url",
        "selenium_browse",
        "browse_webpage",
        "browse_page",
    }:
        category = "search"
        scheduling_policy["priority"] = 20
    elif normalized_name.startswith("image_") or normalized_name in {"generate_image", "edit_image", "expand_image"}:
        category = "image"
        scheduling_policy["priority"] = 40
    elif normalized_name in {
        "video_generate",
        "generate_video",
        "video_gen",
        "video_understand",
        "understand_video",
        "video_delete",
        "delete_video",
    }:
        category = "video"
        scheduling_policy["priority"] = 40
    elif normalized_name in {
        "table_analyze",
        "excel_analyze",
        "analyze_table",
        "sheet_analyze",
        "sheet_profile",
        "sheet_stage_ingest",
        "sheet_stage_profile",
        "sheet_stage_query",
        "sheet_stage_export",
        "amazon_ads_keyword_optimize",
        "amazon_ads_optimize",
        "mcp_tool_call",
        "mcp_call",
        "mcp_invoke",
    }:
        category = "analysis"
        scheduling_policy["priority"] = 30
    elif normalized_name in {"prompt_optimize", "prompt_optimizer", "optimize_prompt", "prompt_rewrite", "rewrite_prompt"}:
        category = "text_optimization"
        scheduling_policy["priority"] = 35

    engine._record_trace_event(
        "tool_dispatch",
        {
            "tool": normalized_name,
            "category": category,
            "policy": scheduling_policy,
        },
    )
    await engine._emit_callback(
        "before_tool",
        {
            "tool": normalized_name,
            "tool_args": tool_args,
            "category": category,
            "policy": scheduling_policy,
        },
    )

    result: Dict[str, Any]
    try:
        browser_aliases = {
            "browser",
            "browser_open",
            "browser_navigate",
            "browser_snapshot",
            "computer_use",
            "computer_call",
        }
        if normalized_name in browser_aliases:
            allow_raw = str(os.getenv("WORKFLOW_BROWSER_TOOL_ALLOWLIST", "") or "").strip()
            allowlist = {
                item.strip().lower()
                for item in allow_raw.split(",")
                if item.strip()
            }
            if normalized_name not in allowlist:
                result = {
                    "tool": normalized_name,
                    "status": "blocked_by_policy",
                    "message": (
                        "Browser-as-a-tool is disabled by policy. "
                        "Set WORKFLOW_BROWSER_TOOL_ALLOWLIST to explicitly allow trusted browser tools."
                    ),
                    "text": "浏览器工具未启用（策略阻断）。",
                    "policy": {
                        "allowlist_env": "WORKFLOW_BROWSER_TOOL_ALLOWLIST",
                        "allowlist": sorted(list(allowlist)),
                    },
                }
            else:
                result = {
                    "tool": normalized_name,
                    "status": "unsupported",
                    "message": "Browser-as-a-tool runtime is not implemented yet in WorkflowEngine.",
                    "text": "浏览器工具暂未在 WorkflowEngine 中接入。",
                    "policy": {
                        "allowlist_env": "WORKFLOW_BROWSER_TOOL_ALLOWLIST",
                        "allowlist": sorted(list(allowlist)),
                    },
                }
        elif normalized_name in ("google_search", "web_search", "search"):
            result = await run_web_search_tool(
                engine=engine,
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in ("read_webpage", "read_page", "read_url"):
            result = await run_read_webpage_tool(
                engine=engine,
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in ("selenium_browse", "browse_webpage", "browse_page"):
            result = await run_selenium_browse_tool(
                engine=engine,
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in ("mcp_tool_call", "mcp_call", "mcp_invoke"):
            result = await run_mcp_tool_call(
                engine=engine,
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in ("text_length", "count_chars"):
            text = tool_args.get("text") or engine._extract_text_from_value(latest_input)
            result = {"text": text, "length": len(str(text or ""))}
        elif normalized_name in ("json_extract", "extract_json"):
            path = tool_args.get("path") or ""
            source = tool_args.get("source") if "source" in tool_args else latest_input
            result = {"path": path, "value": engine._resolve_generic_path(source, path)}
        elif normalized_name in (
            "prompt_optimize",
            "prompt_optimizer",
            "optimize_prompt",
            "prompt_rewrite",
            "rewrite_prompt",
        ):
            result = await engine._run_prompt_optimize_tool(
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in ("image_generate", "generate_image", "image_gen"):
            result = await engine._run_image_generate_tool(
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in (
            "image_chat_edit",
            "image_mask_edit",
            "image_inpainting",
            "image_background_edit",
            "image_recontext",
            "image_edit",
            "edit_image",
            "image_outpaint",
            "image_outpainting",
            "expand_image",
        ):
            is_outpaint, preferred_mode, routed_tool_args = engine._resolve_image_tool_route(
                normalized_tool_name=normalized_name,
                tool_args=tool_args,
            )
            result = await engine._run_image_edit_tool(
                tool_args=routed_tool_args,
                latest_input=latest_input,
                is_outpaint=is_outpaint,
                preferred_mode=preferred_mode,
            )
        elif normalized_name in ("video_generate", "generate_video", "video_gen"):
            prompt = (
                tool_args.get("prompt")
                or tool_args.get("text")
                or engine._extract_text_from_value(latest_input)
                or "生成一段视频"
            )
            provider_id = str(
                tool_args.get("provider_id")
                or tool_args.get("providerId")
                or ""
            ).strip()
            model_id = str(
                tool_args.get("model_id")
                or tool_args.get("modelId")
                or tool_args.get("model")
                or ""
            ).strip()
            profile_id = str(
                tool_args.get("profile_id")
                or tool_args.get("profileId")
                or ""
            ).strip()
            if not provider_id or not model_id:
                raise ValueError("video_generate 需要 provider_id 和 model_id。")
            result = await engine._run_video_generate_task(
                provider_id=provider_id,
                model_id=model_id,
                profile_id=profile_id,
                prompt=str(prompt),
                tool_args={**tool_args, "input": latest_input},
            )
        elif normalized_name in ("video_understand", "understand_video"):
            prompt = (
                tool_args.get("prompt")
                or tool_args.get("instruction")
                or tool_args.get("text")
                or "请分析该视频的主要场景、动作、镜头变化和关键信息。"
            )
            provider_id = str(
                tool_args.get("provider_id")
                or tool_args.get("providerId")
                or ""
            ).strip()
            model_id = str(
                tool_args.get("model_id")
                or tool_args.get("modelId")
                or tool_args.get("model")
                or ""
            ).strip()
            profile_id = str(
                tool_args.get("profile_id")
                or tool_args.get("profileId")
                or ""
            ).strip()
            if not provider_id or not model_id:
                raise ValueError("video_understand 需要 provider_id 和 model_id。")
            result = await engine._run_video_understand_task(
                provider_id=provider_id,
                model_id=model_id,
                profile_id=profile_id,
                prompt=str(prompt),
                tool_args={**tool_args, "input": latest_input},
            )
        elif normalized_name in ("video_delete", "delete_video"):
            provider_id = str(
                tool_args.get("provider_id")
                or tool_args.get("providerId")
                or ""
            ).strip()
            profile_id = str(
                tool_args.get("profile_id")
                or tool_args.get("profileId")
                or ""
            ).strip()
            if not provider_id:
                raise ValueError("video_delete 需要 provider_id。")
            delete_args = dict(tool_args)
            if isinstance(latest_input, dict):
                for src_key, dst_key in (
                    ("provider_file_name", "provider_file_name"),
                    ("providerFileName", "provider_file_name"),
                    ("provider_file_uri", "provider_file_uri"),
                    ("providerFileUri", "provider_file_uri"),
                    ("gcs_uri", "gcs_uri"),
                    ("gcsUri", "gcs_uri"),
                ):
                    value = latest_input.get(src_key)
                    if value is not None and dst_key not in delete_args:
                        delete_args[dst_key] = value
            result = await engine._run_video_delete_task(
                provider_id=provider_id,
                profile_id=profile_id,
                tool_args=delete_args,
            )
        elif normalized_name in ("table_analyze", "excel_analyze", "analyze_table"):
            result = await engine._run_table_analyze_tool(tool_args, latest_input)
        elif normalized_name in ("sheet_analyze", "sheet_profile"):
            result = await engine._run_sheet_analyze_tool(tool_args, latest_input)
        elif normalized_name in (
            "sheet_stage_ingest",
            "sheet_stage_profile",
            "sheet_stage_query",
            "sheet_stage_export",
        ):
            result = await run_sheet_stage_tool(
                engine=engine,
                normalized_tool_name=normalized_name,
                tool_args=tool_args,
                latest_input=latest_input,
            )
        elif normalized_name in (
            "amazon_ads_keyword_optimize",
            "amazon_ads_optimize",
            "ads_keyword_optimize",
            "amazon_ppc_optimize",
            "amazon_search_term_optimize",
            "amazon_ads_decision_validate",
            "amazon_ads_decision_board",
            "amazon_ads_action_board",
        ):
            result = await engine._run_amazon_ads_keyword_optimize_tool(
                tool_args=tool_args,
                latest_input=latest_input,
            )
        else:
            result = {
                "tool": tool_name,
                "args": tool_args,
                "status": "unsupported",
                "message": f"未识别工具：{tool_name}",
                "text": f"工具 {tool_name} 暂未接入，请检查节点配置。",
            }
    except Exception as exc:
        engine._record_trace_event(
            "tool_error",
            {
                "tool": normalized_name,
                "category": category,
                "error": str(exc),
            },
        )
        await engine._emit_callback(
            "on_tool_error",
            {
                "tool": normalized_name,
                "tool_args": tool_args,
                "category": category,
                "error": str(exc),
            },
        )
        raise

    engine._record_trace_event(
        "tool_complete",
        {
            "tool": normalized_name,
            "category": category,
            "status": str(result.get("status") or "").strip() or "completed",
        },
    )
    await engine._emit_callback(
        "after_tool",
        {
            "tool": normalized_name,
            "tool_args": tool_args,
            "category": category,
            "result": result,
            "policy": scheduling_policy,
        },
    )
    if isinstance(result, dict):
        result.setdefault("toolSchedule", scheduling_policy)
        result.setdefault("toolCategory", category)
    return result
