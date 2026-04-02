#!/usr/bin/env python3
"""
Bulk Sorftime MCP chat-stream verification via frontend proxy /api/modes/google/chat.

Example:
  backend/.venv/bin/python scripts/test_sorftime_chat_bulk.py \
    --base-url http://127.0.0.1:21573 \
    --email admin@example.com --password Admin@2026
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

import httpx


PROMPT_TEMPLATES = [
    "调用Sorftime MCP，针对ASIN {asin}（US站），先获取商品全部信息（标题、品牌、类目、价格、评分、评论、变体、BSR等），再给出结构化总结。",
    "调用Sorftime MCP，针对ASIN {asin}（US站），获取流量词/核心关键词、自然位与广告位（SP/SB/SV）分布，并说明机会词和防守词。",
    "调用Sorftime MCP，针对ASIN {asin}（US站），获取历史趋势数据（价格、销量/BSR、评论增长、关键词趋势），给出近30天与近90天变化结论。",
]


@dataclass
class CaseResult:
    asin: str
    prompt: str
    done: bool
    timed_out: bool
    elapsed_sec: float
    chunk_count: int
    text_chars: int
    tool_calls: int
    tool_results: int
    errors: int
    error_message: str
    preview: str


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


def run_case(
    client: httpx.Client,
    base_url: str,
    token: str,
    model: str,
    persona_id: str,
    mcp_server_key: str,
    prompt: str,
    asin: str,
    max_case_seconds: float,
) -> CaseResult:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    request_body: Dict[str, Any] = {
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
    done = False
    timed_out = False
    chunk_count = 0
    text_chars = 0
    tool_calls = 0
    tool_results = 0
    errors = 0
    error_message = ""
    text_parts: List[str] = []

    try:
        with client.stream(
            "POST",
            f"{base_url}/api/modes/google/chat",
            headers=headers,
            json=request_body,
            timeout=httpx.Timeout(connect=20.0, read=30.0, write=20.0, pool=30.0),
        ) as resp:
            resp.raise_for_status()

            for raw in resp.iter_lines():
                if time.time() - start > max_case_seconds:
                    timed_out = True
                    errors += 1
                    error_message = f"case exceeded {max_case_seconds:.0f}s"
                    break

                line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                if not line:
                    continue
                if line.startswith(":"):
                    # SSE heartbeat comment
                    continue
                if not line.startswith("data:"):
                    continue

                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue

                chunk_count += 1
                obj = json.loads(payload)
                chunk_type = obj.get("chunkType")

                if chunk_type == "tool_call":
                    tool_calls += 1
                elif chunk_type == "tool_result":
                    tool_results += 1
                elif chunk_type == "error":
                    errors += 1
                    if not error_message:
                        error_message = str(obj.get("error") or obj.get("text") or "chunkType=error")
                elif chunk_type == "done":
                    done = True
                    break

                text = obj.get("text")
                if isinstance(text, str) and text:
                    text_chars += len(text)
                    text_parts.append(text)
    except Exception as exc:
        errors += 1
        if not error_message:
            error_message = f"{type(exc).__name__}: {exc}"

    elapsed = time.time() - start
    full_text = "".join(text_parts)
    preview = full_text[:240].replace("\n", " ")

    return CaseResult(
        asin=asin,
        prompt=prompt,
        done=done,
        timed_out=timed_out,
        elapsed_sec=round(elapsed, 2),
        chunk_count=chunk_count,
        text_chars=text_chars,
        tool_calls=tool_calls,
        tool_results=tool_results,
        errors=errors,
        error_message=error_message,
        preview=preview,
    )


def evaluate_case_quality(
    result: CaseResult,
    *,
    min_text_chars: int,
    min_tool_results: int,
    min_chunks: int,
) -> List[str]:
    failures: List[str] = []
    if result.text_chars < min_text_chars:
        failures.append(f"text_chars<{min_text_chars} (actual={result.text_chars})")
    if result.tool_results < min_tool_results:
        failures.append(f"tool_results<{min_tool_results} (actual={result.tool_results})")
    if result.chunk_count < min_chunks:
        failures.append(f"chunk_count<{min_chunks} (actual={result.chunk_count})")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:21573")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="Admin@2026")
    parser.add_argument("--model", default="gemini-3.1-pro-preview")
    parser.add_argument("--persona-id", default="gemini2026_g97v3adg:general")
    parser.add_argument("--mcp-server-key", default="Sorftime MCP")
    parser.add_argument(
        "--asins",
        nargs="+",
        default=["B0CXMJLPJK", "B0FKGVFTVL", "B09HYZPMH5"],
    )
    parser.add_argument("--max-case-seconds", type=float, default=240.0)
    parser.add_argument("--output", default="/tmp/sorftime_bulk_report.json")
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=120,
        help="Per-case minimum generated text chars for a case to be counted as success.",
    )
    parser.add_argument(
        "--min-tool-results",
        type=int,
        default=1,
        help="Per-case minimum tool_result chunks for a case to be counted as success.",
    )
    parser.add_argument(
        "--min-chunks",
        type=int,
        default=3,
        help="Per-case minimum SSE chunks for a case to be counted as success.",
    )
    args = parser.parse_args()

    results: List[CaseResult] = []
    quality_failures_by_case: List[List[str]] = []

    with httpx.Client(timeout=None) as client:
        token = login(client, args.base_url, args.email, args.password)

        total_cases = len(args.asins) * len(PROMPT_TEMPLATES)
        idx = 0
        for asin in args.asins:
            for template in PROMPT_TEMPLATES:
                idx += 1
                prompt = template.format(asin=asin)
                print(f"[{idx}/{total_cases}] ASIN={asin} running...", flush=True)
                result = run_case(
                    client=client,
                    base_url=args.base_url,
                    token=token,
                    model=args.model,
                    persona_id=args.persona_id,
                    mcp_server_key=args.mcp_server_key,
                    prompt=prompt,
                    asin=asin,
                    max_case_seconds=args.max_case_seconds,
                )
                print(
                    f"  done={result.done} timed_out={result.timed_out} elapsed={result.elapsed_sec}s "
                    f"chunks={result.chunk_count} tool_calls={result.tool_calls} "
                    f"tool_results={result.tool_results} errors={result.errors} "
                    f"err={result.error_message or '-'}"
                )
                results.append(result)
                quality_failures = evaluate_case_quality(
                    result,
                    min_text_chars=args.min_text_chars,
                    min_tool_results=args.min_tool_results,
                    min_chunks=args.min_chunks,
                )
                quality_failures_by_case.append(quality_failures)
                if quality_failures:
                    print(f"  quality_failures={'; '.join(quality_failures)}", flush=True)

    report_results: List[Dict[str, Any]] = []
    success = 0
    for result, quality_failures in zip(results, quality_failures_by_case):
        case_failed = (not result.done) or result.errors > 0 or bool(quality_failures)
        if not case_failed:
            success += 1
        payload = asdict(result)
        payload["quality_ok"] = not quality_failures
        payload["quality_failures"] = quality_failures
        report_results.append(payload)

    report = {
        "base_url": args.base_url,
        "model": args.model,
        "persona_id": args.persona_id,
        "mcp_server_key": args.mcp_server_key,
        "thresholds": {
            "min_text_chars": args.min_text_chars,
            "min_tool_results": args.min_tool_results,
            "min_chunks": args.min_chunks,
        },
        "total": len(results),
        "success": success,
        "failed": len(results) - success,
        "results": report_results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\\nReport saved: {args.output}")
    print(
        f"Summary: total={report['total']} success={report['success']} failed={report['failed']}",
        flush=True,
    )
    if report["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
