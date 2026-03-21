#!/usr/bin/env python3
"""
Run a full two-phase ASIN workflow:
1) Chat + MCP: collect full product and keyword information.
2) Deep Research: produce final conclusions from phase-1 findings.

Output:
  Markdown report saved into docs/ by default.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx


def login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    resp = client.post(
        f"{base_url}/api/auth/login",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("accessToken")
    if not token:
        raise RuntimeError(f"Login response missing accessToken: {data}")
    return token


def sse_payloads(resp: httpx.Response) -> Iterable[str]:
    for raw in resp.iter_lines():
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        if not line:
            continue
        if line.startswith(":"):
            # heartbeat comment
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        yield payload


def extract_text_from_node(node: Any) -> List[str]:
    texts: List[str] = []
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        for item in node:
            texts.extend(extract_text_from_node(item))
        return texts
    if not isinstance(node, dict):
        return texts

    text = node.get("text")
    if isinstance(text, str) and text:
        texts.append(text)

    for key in ("parts", "content", "outputs"):
        if key in node:
            texts.extend(extract_text_from_node(node[key]))

    return texts


def count_non_whitespace_chars(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def run_phase1_chat(
    client: httpx.Client,
    base_url: str,
    token: str,
    model: str,
    persona_id: str,
    mcp_server_key: str,
    prompt: str,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body: Dict[str, Any] = {
        "modelId": model,
        "messages": [],
        "message": prompt,
        "attachments": [],
        "options": {
            "enableSearch": False,
            "enableThinking": False,
            "enableCodeExecution": False,
            "personaId": persona_id,
            "mcpServerKey": mcp_server_key,
        },
        "stream": True,
    }

    start = time.time()
    text_parts: List[str] = []
    chunk_count = 0
    tool_calls = 0
    tool_results = 0
    errors = 0
    completed = False

    with client.stream(
        "POST",
        f"{base_url}/api/modes/google/chat",
        headers=headers,
        json=body,
        timeout=httpx.Timeout(connect=20.0, read=240.0, write=20.0, pool=30.0),
    ) as resp:
        resp.raise_for_status()
        for payload in sse_payloads(resp):
            chunk_count += 1
            obj = json.loads(payload)
            chunk_type = obj.get("chunkType")
            if chunk_type == "tool_call":
                tool_calls += 1
            elif chunk_type == "tool_result":
                tool_results += 1
            elif chunk_type == "error":
                errors += 1
            elif chunk_type == "done":
                completed = True
                break

            text = obj.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)

    content = "".join(text_parts)
    return {
        "elapsed_sec": round(time.time() - start, 2),
        "chunk_count": chunk_count,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "errors": errors,
        "completed": completed,
        "content": content,
        "content_chars": count_non_whitespace_chars(content),
    }


def start_deep_research(
    client: httpx.Client,
    base_url: str,
    token: str,
    agent: str,
    prompt: str,
) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "prompt": prompt,
        "agent": agent,
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
    data = resp.json()
    interaction_id = data.get("interactionId") or data.get("interaction_id")
    if not interaction_id:
        raise RuntimeError(f"Missing interactionId in /start response: {data}")
    return interaction_id


def stream_deep_research_until_complete(
    client: httpx.Client,
    base_url: str,
    token: str,
    interaction_id: str,
    max_seconds: int,
) -> Dict[str, Any]:
    start = time.time()
    reconnect_attempt = 0
    max_reconnect = 80
    last_event_id: Optional[str] = None
    completed = False
    error: Optional[str] = None
    event_count = 0

    text_parts: List[str] = []
    thought_parts: List[str] = []

    while (time.time() - start) < max_seconds and reconnect_attempt <= max_reconnect:
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
                    event_count += 1
                    obj = json.loads(payload)
                    event_type = obj.get("eventType") or obj.get("event_type")
                    event_id = obj.get("eventId") or obj.get("event_id")
                    if isinstance(event_id, str) and event_id:
                        last_event_id = event_id

                    if event_type == "content.delta":
                        delta = obj.get("delta") or {}
                        delta_type = delta.get("type")
                        delta_text = delta.get("text") or (delta.get("content") or {}).get("text")
                        if isinstance(delta_text, str) and delta_text:
                            if delta_type in ("thought", "thought_summary"):
                                thought_parts.append(delta_text)
                            else:
                                text_parts.append(delta_text)
                        continue

                    if event_type == "interaction.complete":
                        completed = True
                        interaction = obj.get("interaction") or {}
                        completion_texts = extract_text_from_node(interaction.get("outputs"))
                        for item in completion_texts:
                            if isinstance(item, str) and item:
                                text_parts.append(item)
                        break

                    if event_type == "error":
                        err = obj.get("error")
                        error = err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)
                        break

                    if (time.time() - start) >= max_seconds:
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

    elapsed = round(time.time() - start, 2)
    content = "".join(text_parts)
    return {
        "interaction_id": interaction_id,
        "elapsed_sec": elapsed,
        "event_count": event_count,
        "completed": completed,
        "error": error,
        "content": content,
        "content_chars": count_non_whitespace_chars(content),
        "thoughts": "\n\n".join(thought_parts),
        "last_event_id": last_event_id,
    }


def build_phase1_prompt(site: str, asin: str) -> str:
    return f"""
你是电商研究分析助手。请严格调用 Sorftime MCP 工具完成两步，并输出结构化结果。

目标站点: {site}
目标ASIN: {asin}

步骤1（产品全量信息）：
1) 调用“产品详情”工具获取基础信息（标题、品牌、价格、评分、评论数、类目、BSR、卖家、上架时间、变体等）。
2) 调用“子体明细”工具获取所有子体。
3) 调用“历史趋势”工具分别拉取：月销量趋势、月销额趋势、价格趋势、所属大类排名趋势。
4) 调用“近一年评论”工具，至少分别获取：全部评论、积极评论、消极评论（若支持）。
5) 如可行，补充类目特征（根据类目名调用类目产品特点工具）。

步骤2（关键词全量信息）：
1) 调用“产品反查关键词”工具，分页抓取直到无新数据。
2) 基于反查结果，提取核心关键词（至少Top20）。
3) 对核心关键词逐个调用：
   - 热搜关键词详情
   - 关键词历史趋势（搜索量/排名/CPC）
   - 延伸词关键词（至少第1页）
   - 自然位产品清单（至少第1页）
4) 调用“竞品在核心关键词下自然曝光位置”工具，评估该ASIN获取流量能力。
5) 对最关键的5-10个词调用“该ASIN在关键词下曝光排名趋势”工具。

输出要求：
1) 先给“产品全量信息总表”。
2) 再给“关键词全量信息总表”（含每个词的搜索量、趋势、CPC、自然位表现、相关词）。
3) 最后给“数据质量说明”：哪些数据有、哪些缺失、是否命中分页上限。
""".strip()


def build_phase2_prompt(site: str, asin: str, phase1_content: str) -> str:
    return f"""
你将基于已采集的亚马逊数据进行第二阶段 Deep Research。

研究对象: {site} 站 ASIN {asin}

你的任务：
1) 验证 Phase1 里的关键结论，指出证据强/弱和不确定性。
2) 完成“产品-关键词-流量-转化-竞争”一体化分析。
3) 输出可执行策略：内容、广告、关键词运营、价格、变体、评论运营、站外引流。
4) 给出90天执行路线图（按周拆解）和可量化KPI。
5) 明确风险与假设，以及监测指标。

以下是 Phase1 全量数据与结论，请作为研究输入：

{phase1_content}
""".strip()


def render_report(
    asin: str,
    site: str,
    chat_model: str,
    research_model: str,
    phase1: Dict[str, Any],
    phase2: Dict[str, Any],
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""# ASIN Full Research Report

- ASIN: `{asin}`
- Site: `{site}`
- Generated At (UTC): `{generated_at}`
- Phase1 Model: `{chat_model}`
- Phase2 Model: `{research_model}`

## Phase 1 - Product and Keyword Full Collection

### Runtime Metrics
- Elapsed: `{phase1["elapsed_sec"]}s`
- Chunks: `{phase1["chunk_count"]}`
- Tool Calls: `{phase1["tool_calls"]}`
- Tool Results: `{phase1["tool_results"]}`
- Errors: `{phase1["errors"]}`
- Completed: `{phase1["completed"]}`
- Content Chars: `{phase1["content_chars"]}`

### Output

{phase1["content"] or "(empty)"}

## Phase 2 - Deep Research Final Result

### Runtime Metrics
- Interaction ID: `{phase2["interaction_id"]}`
- Elapsed: `{phase2["elapsed_sec"]}s`
- Events: `{phase2["event_count"]}`
- Completed: `{phase2["completed"]}`
- Error: `{phase2["error"] or "-"}`
- Last Event ID: `{phase2["last_event_id"] or "-"}`
- Content Chars: `{phase2["content_chars"]}`

### Final Conclusion

{phase2["content"] or "(empty)"}

### Thought Summary (Optional)

{phase2["thoughts"] or "(empty)"}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:21574")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="Admin@2026")
    parser.add_argument("--site", default="US")
    parser.add_argument("--asin", required=True)
    parser.add_argument("--chat-model", default="gemini-3.1-pro-preview")
    parser.add_argument("--research-model", default="deep-research-pro-preview-12-2025")
    parser.add_argument("--persona-id", default="gemini2026_g97v3adg:general")
    parser.add_argument("--mcp-server-key", default="Sorftime MCP")
    parser.add_argument("--max-research-seconds", type=int, default=1800)
    parser.add_argument(
        "--min-phase1-content-chars",
        type=int,
        default=200,
        help="Minimum non-whitespace chars required for phase1 output.",
    )
    parser.add_argument(
        "--min-phase2-content-chars",
        type=int,
        default=400,
        help="Minimum non-whitespace chars required for phase2 output.",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    output_path = (
        Path(args.output)
        if args.output
        else Path("docs") / f"asin_{args.site.lower()}_{args.asin}_full_research.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=None) as client:
        token = login(client, args.base_url, args.email, args.password)

        phase1_prompt = build_phase1_prompt(args.site, args.asin)
        print(f"[Phase1] Collecting product+keyword data for {args.site}:{args.asin} ...", flush=True)
        phase1 = run_phase1_chat(
            client=client,
            base_url=args.base_url,
            token=token,
            model=args.chat_model,
            persona_id=args.persona_id,
            mcp_server_key=args.mcp_server_key,
            prompt=phase1_prompt,
        )
        print(
            f"[Phase1] done elapsed={phase1['elapsed_sec']}s "
            f"tool_calls={phase1['tool_calls']} tool_results={phase1['tool_results']}",
            flush=True,
        )

        phase2_prompt = build_phase2_prompt(args.site, args.asin, phase1["content"])
        print("[Phase2] Starting Deep Research ...", flush=True)
        interaction_id = start_deep_research(
            client=client,
            base_url=args.base_url,
            token=token,
            agent=args.research_model,
            prompt=phase2_prompt,
        )
        print(f"[Phase2] interaction_id={interaction_id}", flush=True)

        phase2 = stream_deep_research_until_complete(
            client=client,
            base_url=args.base_url,
            token=token,
            interaction_id=interaction_id,
            max_seconds=args.max_research_seconds,
        )
        print(
            f"[Phase2] done elapsed={phase2['elapsed_sec']}s "
            f"completed={phase2['completed']} error={phase2['error'] or '-'}",
            flush=True,
        )

    report = render_report(
        asin=args.asin,
        site=args.site,
        chat_model=args.chat_model,
        research_model=args.research_model,
        phase1=phase1,
        phase2=phase2,
    )
    output_path.write_text(report, encoding="utf-8")
    print(f"[Report] saved: {output_path}", flush=True)

    failures: List[str] = []
    if phase1["errors"] > 0:
        failures.append(f"phase1 errors={phase1['errors']}")
    if not phase1["completed"]:
        failures.append("phase1 not completed")
    if phase1["content_chars"] < args.min_phase1_content_chars:
        failures.append(
            f"phase1 content too short ({phase1['content_chars']}<{args.min_phase1_content_chars})"
        )
    if phase2["error"]:
        failures.append(f"phase2 error={phase2['error']}")
    if not phase2["completed"]:
        failures.append("phase2 not completed")
    if phase2["content_chars"] < args.min_phase2_content_chars:
        failures.append(
            f"phase2 content too short ({phase2['content_chars']}<{args.min_phase2_content_chars})"
        )

    if failures:
        print("[Result] FAILED", flush=True)
        for item in failures:
            print(f"  - {item}", flush=True)
        return 1

    print("[Result] PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
