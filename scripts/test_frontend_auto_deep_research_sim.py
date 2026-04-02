#!/usr/bin/env python3
"""
Strict simulation of frontend auto-deep-research flow:

1) Phase1 Chat (with persona + MCP) via:
   POST /api/modes/google/chat (SSE stream)
2) Build auto deep-research prompt (same strategy as frontend useChat.ts)
3) Phase2 Deep Research via:
   POST /api/research/stream/start
   GET  /api/research/stream/{interaction_id} (SSE stream)

Outputs:
- Injected prompt markdown
- Full test report markdown
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

AUTO_RESEARCH_CONTEXT_WINDOW = 6
AUTO_RESEARCH_EVIDENCE_WINDOW = 20


@dataclass
class ToolCall:
    id: str
    type: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    name: str
    call_id: str
    result: Any
    error: Optional[str] = None


def login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    resp = client.post(
        f"{base_url}/api/auth/login",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload.get("accessToken")
    if not token:
        raise RuntimeError(f"Login response missing accessToken: {payload}")
    return token


def sse_payloads(resp: httpx.Response) -> Iterable[str]:
    for raw in resp.iter_lines():
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        if not line:
            continue
        if line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        yield payload


def resolve_persona_key(persona_id: str) -> str:
    trimmed = (persona_id or "").strip()
    if not trimmed:
        return ""
    if ":" not in trimmed:
        return trimmed
    return trimmed.split(":")[-1].strip()


def resolve_lead_role(persona_id: str) -> str:
    key = resolve_persona_key(persona_id)
    mapping = {
        "amazon-selection-strategist": "selection",
        "amazon-ads-keyword-operator": "ads",
        "amazon-listing-cvr-optimizer": "listing",
    }
    return mapping.get(key, "selection")


def describe_lead_role(role: str) -> str:
    if role == "ads":
        return "广告与关键词主导（B主导，A/C联动）"
    if role == "listing":
        return "Listing转化主导（C主导，A/B联动）"
    return "选品策略主导（A主导，B/C联动）"


def summarize_context_for_auto_research(history: List[Tuple[str, str]]) -> str:
    sliced = history[-AUTO_RESEARCH_CONTEXT_WINDOW:]
    if not sliced:
        return "无"
    lines: List[str] = []
    for role, content in sliced:
        text = (content or "").strip()
        preview = f"{text[:280]}..." if len(text) > 280 else text
        lines.append(f"[{role}] {preview or '(空内容)'}")
    return "\n".join(lines)


def summarize_tool_evidence(
    tool_calls: List[ToolCall],
    tool_results: List[ToolResult],
) -> str:
    if not tool_calls and not tool_results:
        return "无工具调用记录（可能未启用 MCP 或工具未触发）。"

    call_by_id: Dict[str, ToolCall] = {item.id: item for item in tool_calls}
    lines: List[str] = [
        f"工具调用数: {len(tool_calls)}",
        f"工具结果数: {len(tool_results)}",
    ]

    recent_results = tool_results[-AUTO_RESEARCH_EVIDENCE_WINDOW:]
    for idx, result in enumerate(recent_results, 1):
        call = call_by_id.get(result.call_id)
        tool_name = (call.name if call else None) or result.name or "unknown_tool"
        args_text = "{}"
        if call and isinstance(call.arguments, dict):
            args_text = json.dumps(call.arguments, ensure_ascii=False)[:280]
        raw = result.result
        if isinstance(raw, str):
            raw_text = raw
        else:
            raw_text = json.dumps(raw if raw is not None else {}, ensure_ascii=False)
        raw_text = raw_text[:420]
        status = f"失败: {result.error}" if result.error else "成功"
        lines.extend(
            [
                f"- [{idx}] {tool_name}",
                f"  call_id={result.call_id or 'unknown'}",
                f"  参数={args_text}",
                f"  状态={status}",
                f"  摘要={raw_text or '(空结果)'}",
            ]
        )

    if len(tool_results) > len(recent_results):
        lines.append(
            f"（仅展示最近 {len(recent_results)} 条工具结果，共 {len(tool_results)} 条）"
        )

    return "\n".join(lines)


def build_auto_deep_research_prompt(
    user_question: str,
    chat_answer: str,
    context_summary: str,
    lead_role: str,
    persona_id: str,
    tool_evidence_summary: str,
) -> str:
    persona_key = resolve_persona_key(persona_id) or "未指定"
    lead_role_text = describe_lead_role(lead_role)
    return "\n".join(
        [
            "你正在执行自动深挖的第二阶段（Deep Research）。",
            "该流程是单次输入触发，你必须在一次响应内完成跨角色联动分析，不允许拆分为多轮提问。",
            "",
            "流程上下文（已完成）：",
            "1) MCP 工具采集（产品/关键词/趋势/排名等）",
            "2) Chat 阶段整理与初步判断",
            "3) 你当前接手：Deep Research 纵深分析与执行方案",
            "",
            "联动规则（强制）：",
            "1. 采用 A/B/C 三角色串联并在单次响应中融合：",
            "   A=选品与市场结构，B=广告与关键词流量，C=Listing与转化优化。",
            f"2. 主导视角：{lead_role_text}（来源 persona={persona_key}）。",
            "3. 先做证据校验，再给策略，不得直接跳到建议。",
            "4. 必须区分：事实（工具证据）/推断（有不确定性）/执行动作（可落地）。",
            "5. 如数据不足，明确指出缺口与下一步 MCP 补采动作。",
            "",
            "输出格式（强制）：",
            "## 1. 事实核验与不确定性",
            "## 2. A/B/C 串联诊断（产品-关键词-流量-转化-竞争）",
            "## 3. 14/30/90 天执行计划（按优先级）",
            "## 4. KPI 看板（目标值/当前值/阈值/预警）",
            "## 5. 风险、假设与下一步数据补采",
            "",
            f"用户原始问题：\n{user_question or '(空问题)'}",
            "",
            f"最近会话摘要：\n{context_summary or '无'}",
            "",
            f"Phase1-Chat 整理结果（待深挖）：\n{chat_answer or '(空回答)'}",
            "",
            f"Phase1-MCP 工具证据摘要：\n{tool_evidence_summary}",
        ]
    ).strip()


def run_phase1_chat(
    client: httpx.Client,
    base_url: str,
    token: str,
    model: str,
    persona_id: str,
    mcp_server_key: str,
    prompt: str,
    max_chat_seconds: int,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "modelId": model,
        "messages": [],
        "message": prompt,
        "attachments": [],
        "options": {
            "enableSearch": False,
            "enableThinking": False,
            "enableBrowser": False,
            "enableCodeExecution": False,
            "personaId": persona_id,
            "mcpServerKey": mcp_server_key,
        },
        "stream": True,
    }

    start = time.time()
    chunk_count = 0
    errors = 0
    done = False
    text_parts: List[str] = []
    tool_calls: List[ToolCall] = []
    tool_results: List[ToolResult] = []

    with client.stream(
        "POST",
        f"{base_url}/api/modes/google/chat",
        headers=headers,
        json=body,
        timeout=httpx.Timeout(connect=20.0, read=600.0, write=20.0, pool=30.0),
    ) as resp:
        resp.raise_for_status()
        for payload in sse_payloads(resp):
            if (time.time() - start) > max_chat_seconds:
                raise TimeoutError(f"Phase1 chat exceeded {max_chat_seconds}s")

            obj = json.loads(payload)
            chunk_count += 1
            chunk_type = obj.get("chunkType")

            if chunk_type == "tool_call":
                call_id = str(obj.get("callId") or f"tool_call_{chunk_count}")
                tool_calls.append(
                    ToolCall(
                        id=call_id,
                        type=str(obj.get("toolType") or "function_call"),
                        name=str(obj.get("toolName") or "unknown_tool"),
                        arguments=obj.get("toolArgs") if isinstance(obj.get("toolArgs"), dict) else {},
                    )
                )
                continue

            if chunk_type == "tool_result":
                tool_results.append(
                    ToolResult(
                        name=str(obj.get("toolName") or "unknown_tool"),
                        call_id=str(obj.get("callId") or ""),
                        result=obj.get("toolResult"),
                        error=str(obj.get("toolError")) if obj.get("toolError") else None,
                    )
                )
                continue

            if chunk_type == "error":
                errors += 1

            if chunk_type == "done":
                done = True
                break

            text = obj.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)

    return {
        "elapsed_sec": round(time.time() - start, 2),
        "chunk_count": chunk_count,
        "errors": errors,
        "done": done,
        "content": "".join(text_parts),
        "tool_calls": tool_calls,
        "tool_results": tool_results,
    }


def start_deep_research(
    client: httpx.Client,
    base_url: str,
    token: str,
    research_model: str,
    prompt: str,
) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "prompt": prompt,
        "agent": research_model,
        "background": True,
        "stream": False,
        "agent_config": {
            "type": "deep-research",
            "thinkingSummaries": "auto",
        },
    }
    resp = client.post(
        f"{base_url}/api/research/stream/start",
        headers=headers,
        json=body,
        timeout=httpx.Timeout(connect=20.0, read=120.0, write=20.0, pool=30.0),
    )
    resp.raise_for_status()
    payload = resp.json()
    interaction_id = payload.get("interactionId") or payload.get("interaction_id")
    if not interaction_id:
        raise RuntimeError(f"Missing interaction id in start response: {payload}")
    return str(interaction_id)


def stream_deep_research_until_done(
    client: httpx.Client,
    base_url: str,
    token: str,
    interaction_id: str,
    max_research_seconds: int,
) -> Dict[str, Any]:
    start = time.time()
    event_count = 0
    completed = False
    error: Optional[str] = None
    text_parts: List[str] = []
    thought_parts: List[str] = []
    reconnect_attempt = 0
    max_reconnect = 80
    last_event_id: Optional[str] = None

    while (time.time() - start) < max_research_seconds and reconnect_attempt <= max_reconnect:
        headers: Dict[str, str] = {"Authorization": f"Bearer {token}"}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id

        try:
            with client.stream(
                "GET",
                f"{base_url}/api/research/stream/{interaction_id}",
                headers=headers,
                timeout=httpx.Timeout(connect=20.0, read=600.0, write=20.0, pool=30.0),
            ) as resp:
                resp.raise_for_status()
                for payload in sse_payloads(resp):
                    if (time.time() - start) > max_research_seconds:
                        raise TimeoutError(f"Deep Research exceeded {max_research_seconds}s")

                    event_count += 1
                    obj = json.loads(payload)
                    event_id = obj.get("eventId") or obj.get("event_id")
                    if isinstance(event_id, str) and event_id:
                        last_event_id = event_id
                    event_type = obj.get("eventType") or obj.get("event_type")

                    if event_type == "content.delta":
                        delta = obj.get("delta") or {}
                        delta_type = delta.get("type")
                        delta_text = delta.get("text")
                        if not delta_text and isinstance(delta.get("content"), dict):
                            delta_text = delta["content"].get("text")
                        if isinstance(delta_text, str) and delta_text:
                            if delta_type in ("thought", "thought_summary"):
                                thought_parts.append(delta_text)
                            else:
                                text_parts.append(delta_text)
                        continue

                    if event_type == "error":
                        err = obj.get("error")
                        error = err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)
                        break

                    if event_type == "interaction.complete":
                        completed = True
                        interaction = obj.get("interaction") or {}
                        outputs = interaction.get("outputs")
                        if isinstance(outputs, list):
                            for item in outputs:
                                if isinstance(item, dict) and isinstance(item.get("text"), str):
                                    text_parts.append(item["text"])
                        break

            if completed or error:
                break

            reconnect_attempt += 1
            time.sleep(min(2.0 * reconnect_attempt, 20.0))
        except Exception as exc:
            reconnect_attempt += 1
            if reconnect_attempt > max_reconnect:
                error = str(exc)
                break
            time.sleep(min(2.0 * reconnect_attempt, 20.0))

    return {
        "elapsed_sec": round(time.time() - start, 2),
        "event_count": event_count,
        "completed": completed,
        "error": error,
        "content": "".join(text_parts),
        "thoughts": "\n\n".join(thought_parts),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:21573")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="Admin@2026")
    parser.add_argument("--chat-model", default="gemini-3.1-pro-preview")
    parser.add_argument("--research-model", default="deep-research-pro-preview-12-2025")
    parser.add_argument(
        "--persona-id",
        default="gemini2026_g97v3adg:amazon-selection-strategist",
    )
    parser.add_argument("--mcp-server-key", default="Sorftime MCP")
    parser.add_argument(
        "--prompt",
        default=(
            "调用 Sorftime MCP 分析 US 站 ASIN B0FQ35LKQH："
            "先收集产品详情、子体、历史趋势与评论，再反查关键词并整理 Top20 核心词。"
        ),
    )
    parser.add_argument("--max-chat-seconds", type=int, default=360)
    parser.add_argument("--max-research-seconds", type=int, default=1800)
    parser.add_argument("--output-prefix", default="")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = args.output_prefix.strip() or f"frontend_auto_deep_research_sim_{ts}"
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = docs_dir / f"{stem}.prompt.md"
    report_path = docs_dir / f"{stem}.report.md"

    with httpx.Client(timeout=None) as client:
        token = login(client, args.base_url, args.email, args.password)

        print("[Phase1] chat + MCP streaming ...", flush=True)
        phase1 = run_phase1_chat(
            client=client,
            base_url=args.base_url,
            token=token,
            model=args.chat_model,
            persona_id=args.persona_id,
            mcp_server_key=args.mcp_server_key,
            prompt=args.prompt,
            max_chat_seconds=args.max_chat_seconds,
        )
        print(
            f"[Phase1] done={phase1['done']} elapsed={phase1['elapsed_sec']}s "
            f"chunks={phase1['chunk_count']} tool_calls={len(phase1['tool_calls'])} "
            f"tool_results={len(phase1['tool_results'])} errors={phase1['errors']}",
            flush=True,
        )

        context_summary = summarize_context_for_auto_research(
            [
                ("用户", args.prompt),
                ("助手", phase1["content"]),
            ]
        )
        lead_role = resolve_lead_role(args.persona_id)
        tool_evidence = summarize_tool_evidence(
            tool_calls=phase1["tool_calls"],
            tool_results=phase1["tool_results"],
        )
        injected_prompt = build_auto_deep_research_prompt(
            user_question=args.prompt,
            chat_answer=phase1["content"],
            context_summary=context_summary,
            lead_role=lead_role,
            persona_id=args.persona_id,
            tool_evidence_summary=tool_evidence,
        )

        prompt_path.write_text(injected_prompt, encoding="utf-8")
        print(f"[Prompt] saved: {prompt_path}", flush=True)

        print("[Phase2] deep research start ...", flush=True)
        interaction_id = start_deep_research(
            client=client,
            base_url=args.base_url,
            token=token,
            research_model=args.research_model,
            prompt=injected_prompt,
        )
        print(f"[Phase2] interaction_id={interaction_id}", flush=True)

        phase2 = stream_deep_research_until_done(
            client=client,
            base_url=args.base_url,
            token=token,
            interaction_id=interaction_id,
            max_research_seconds=args.max_research_seconds,
        )
        print(
            f"[Phase2] completed={phase2['completed']} elapsed={phase2['elapsed_sec']}s "
            f"events={phase2['event_count']} error={phase2['error'] or '-'}",
            flush=True,
        )

    checks = {
        "contains_phase1_chat_block": "Phase1-Chat 整理结果（待深挖）" in injected_prompt,
        "contains_phase1_tool_block": "Phase1-MCP 工具证据摘要" in injected_prompt,
        "contains_single_response_rule": "一次响应内完成跨角色联动分析" in injected_prompt,
        "phase1_has_tool_results": len(phase1["tool_results"]) > 0,
        "phase2_completed": bool(phase2["completed"]),
        "phase2_has_content": bool((phase2["content"] or "").strip()),
    }
    strict_pass = all(checks.values())

    generated_at = datetime.now(timezone.utc).isoformat()
    report = "\n".join(
        [
            "# Frontend Auto Deep Research Simulation Report",
            "",
            f"- Generated At (UTC): `{generated_at}`",
            f"- Base URL: `{args.base_url}`",
            f"- Chat Model: `{args.chat_model}`",
            f"- Deep Research Model: `{args.research_model}`",
            f"- Persona ID: `{args.persona_id}`",
            f"- MCP Server Key: `{args.mcp_server_key}`",
            "",
            "## Strict Checks",
            *[f"- {key}: `{value}`" for key, value in checks.items()],
            f"- strict_pass: `{strict_pass}`",
            "",
            "## Phase1 Metrics",
            f"- done: `{phase1['done']}`",
            f"- elapsed_sec: `{phase1['elapsed_sec']}`",
            f"- chunk_count: `{phase1['chunk_count']}`",
            f"- errors: `{phase1['errors']}`",
            f"- tool_calls: `{len(phase1['tool_calls'])}`",
            f"- tool_results: `{len(phase1['tool_results'])}`",
            "",
            "## Phase2 Metrics",
            f"- interaction_id: `{interaction_id}`",
            f"- completed: `{phase2['completed']}`",
            f"- elapsed_sec: `{phase2['elapsed_sec']}`",
            f"- event_count: `{phase2['event_count']}`",
            f"- error: `{phase2['error'] or '-'}`",
            "",
            "## Prompt Artifact",
            f"- injected_prompt_path: `{prompt_path}`",
            "",
            "## Phase1 Chat Output",
            phase1["content"] or "(empty)",
            "",
            "## Phase2 Deep Research Output",
            phase2["content"] or "(empty)",
            "",
            "## Phase2 Thoughts (Optional)",
            phase2["thoughts"] or "(empty)",
        ]
    )
    report_path.write_text(report, encoding="utf-8")
    print(f"[Report] saved: {report_path}", flush=True)
    print(f"[Result] strict_pass={strict_pass}", flush=True)

    return 0 if strict_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
