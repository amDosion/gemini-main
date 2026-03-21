"""
Analysis tool helpers extracted from WorkflowEngine.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


async def run_sheet_analyze_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    from ..adk_builtin_tools import build_adk_builtin_tools

    sheet_tool = next(
        (
            tool for tool in build_adk_builtin_tools()
            if getattr(tool, "__name__", "") == "sheet_analyze"
        ),
        None,
    )
    if sheet_tool is None:
        raise RuntimeError("sheet_analyze tool is unavailable")

    normalized_tool_args = dict(tool_args or {})
    if not any(
        normalized_tool_args.get(key) is not None and str(normalized_tool_args.get(key)).strip()
        for key in ("file_url", "data_url", "content")
    ):
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
                    normalized_tool_args[target_key] = value
                    break
        elif isinstance(latest_input, str) and latest_input.strip():
            latest_text = latest_input.strip()
            if latest_text.startswith("data:"):
                normalized_tool_args["data_url"] = latest_text
            elif "://" in latest_text:
                normalized_tool_args["file_url"] = latest_text
            else:
                normalized_tool_args["content"] = latest_text

    result = sheet_tool(**normalized_tool_args)
    if isinstance(result, dict):
        rendered = result.get("text") or result.get("summaryText") or result.get("summary_text") or result.get("rendered")
        if rendered:
            result.setdefault("summaryText", str(rendered))
            result.setdefault("text", str(rendered))
    return result


async def run_prompt_optimize_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    source_prompt = (
        engine._get_tool_arg(tool_args, "prompt", "text", "query", "input")
        or engine._extract_text_from_value(latest_input)
    )
    source_prompt = str(source_prompt or "").strip()
    if not source_prompt:
        raise ValueError("prompt_optimize 缺少 prompt 文本，无法执行优化")

    goal = str(engine._get_tool_arg(tool_args, "goal", "target", "objective") or "").strip()
    style = str(engine._get_tool_arg(tool_args, "style", "tone", "voice") or "").strip()
    language = str(engine._get_tool_arg(tool_args, "language", "lang") or "auto").strip()
    length = str(engine._get_tool_arg(tool_args, "length", "verbosity") or "medium").strip().lower()
    output_format = str(
        engine._get_tool_arg(tool_args, "output_format", "outputFormat", "format")
        or "text"
    ).strip().lower()

    def normalize_keywords(raw_value: Any) -> List[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        text_value = str(raw_value).strip()
        if not text_value:
            return []
        parts = re.split(r"[,，;\n]+", text_value)
        return [part.strip() for part in parts if part.strip()]

    must_keep = normalize_keywords(engine._get_tool_arg(tool_args, "must_keep", "mustKeep", "keywords_keep"))
    avoid = normalize_keywords(engine._get_tool_arg(tool_args, "avoid", "negative", "forbidden"))
    extra_requirements = str(
        engine._get_tool_arg(tool_args, "requirements", "constraints", "notes")
        or ""
    ).strip()

    requested_provider = str(
        engine._get_tool_arg(tool_args, "provider_id", "providerId", "provider")
        or ""
    ).strip()
    requested_model = str(
        engine._get_tool_arg(tool_args, "model_id", "modelId", "model")
        or ""
    ).strip()
    requested_profile_id = str(
        engine._get_tool_arg(tool_args, "profile_id", "profileId", "provider_profile_id", "providerProfileId")
        or ""
    ).strip()

    provider_id, model_id = engine._select_text_chat_target(
        requested_provider=requested_provider,
        requested_model=requested_model,
        requested_profile_id=requested_profile_id,
    )

    control_payload: Dict[str, Any] = {
        "goal": goal or "让提示词更清晰、可执行、可复现",
        "style": style or "专业、具体、可控",
        "language": language or "auto",
        "length": length if length in {"short", "medium", "long"} else "medium",
        "output_format": output_format if output_format in {"text", "markdown", "json"} else "text",
        "must_keep": must_keep,
        "avoid": avoid,
        "extra_requirements": extra_requirements,
    }

    optimizer_prompt = (
        "你是提示词优化专家。请根据输入约束优化 prompt，并返回 JSON。\n"
        "JSON schema:\n"
        "{\n"
        "  \"optimized_prompt\": \"string, 优化后的最终可用提示词\",\n"
        "  \"rationale\": [\"string\"],\n"
        "  \"changes\": [\"string\"],\n"
        "  \"warnings\": [\"string\"]\n"
        "}\n"
        "要求：\n"
        "1) optimized_prompt 必须可直接投喂模型；\n"
        "2) 必须保留 must_keep 关键词；\n"
        "3) 必须避免 avoid 内容；\n"
        "4) 除 JSON 外不要输出任何解释文本。\n\n"
        f"优化控制参数:\n{json.dumps(control_payload, ensure_ascii=False)}\n\n"
        f"原始 prompt:\n{source_prompt}"
    )

    result = await engine._invoke_llm_chat(
        provider_id=provider_id,
        model_id=model_id,
        messages=[{"role": "user", "content": optimizer_prompt}],
        system_prompt="你专注于提示词重写优化，输出必须严格是 JSON。",
        temperature=0.2,
        max_tokens=2048,
        profile_id=requested_profile_id,
    )
    raw_text = engine._normalize_agent_response_text(
        text=result.get("text", ""),
        expected_format="json",
    )
    stripped = engine._strip_markdown_code_fence(raw_text)

    parsed_payload: Dict[str, Any] = {}
    try:
        maybe_json = json.loads(stripped)
        if isinstance(maybe_json, dict):
            parsed_payload = maybe_json
    except Exception:
        parsed_payload = {}

    optimized_prompt = str(
        parsed_payload.get("optimized_prompt")
        or parsed_payload.get("optimizedPrompt")
        or stripped
    ).strip()
    if not optimized_prompt:
        raise ValueError("prompt_optimize 未返回有效的 optimized_prompt")

    rationale_raw = parsed_payload.get("rationale")
    changes_raw = parsed_payload.get("changes")
    warnings_raw = parsed_payload.get("warnings")

    def normalize_list(raw_value: Any) -> List[str]:
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        if isinstance(raw_value, str) and raw_value.strip():
            return [raw_value.strip()]
        return []

    return {
        "tool": "prompt_optimize",
        "status": "optimized",
        "model": f"{provider_id}/{model_id}",
        "originalPrompt": source_prompt,
        "optimizedPrompt": optimized_prompt,
        "rationale": normalize_list(rationale_raw),
        "changes": normalize_list(changes_raw),
        "warnings": normalize_list(warnings_raw),
        "config": control_payload,
        "text": optimized_prompt,
    }


async def run_table_analyze_tool(
    engine: Any,
    tool_args: Dict[str, Any],
    latest_input: Any,
) -> Dict[str, Any]:
    def build_lineage(
        *,
        payload: Any,
        source: str,
        parse_elapsed_ms: int,
        row_count: int,
        preview_rows: int,
    ) -> Dict[str, Any]:
        source_text = str(source or "").strip().lower()
        pipeline = ["input"]
        input_kind = "unknown"
        reference = ""
        extension = ""
        mime_type = ""

        if isinstance(payload, str):
            reference = payload.strip()
            if reference.startswith("data:"):
                input_kind = "data_url"
                mime_type = reference.split(";", 1)[0].replace("data:", "", 1).strip().lower()
            else:
                parsed = urlparse(reference)
                if parsed.scheme in {"http", "https", "file"}:
                    input_kind = f"{parsed.scheme}_url"
                elif parsed.scheme:
                    input_kind = f"{parsed.scheme}_reference"
                else:
                    input_kind = "path_or_inline_text"
                extension = Path(parsed.path or reference).suffix.lower()
        elif isinstance(payload, list):
            input_kind = "list"
        elif isinstance(payload, dict):
            input_kind = "object"

        if ".xlsx" in source_text or extension in {".xlsx", ".xls", ".xlsm", ".xlsb"}:
            pipeline.extend(["xlsx -> DataFrame", "DataFrame -> CSV"])
        elif ".csv" in source_text or extension in {".csv", ".tsv"} or "csv" in source_text:
            pipeline.extend(["csv/tsv -> DataFrame", "DataFrame -> CSV"])
        elif "json" in source_text or extension == ".json":
            pipeline.extend(["json -> DataFrame", "DataFrame -> CSV"])
        else:
            pipeline.extend(["text/object -> DataFrame", "DataFrame -> CSV"])

        return {
            "source_type": source,
            "input_kind": input_kind,
            "reference": reference[:1024] if reference else None,
            "mime_type": mime_type or None,
            "extension": extension or None,
            "pipeline": pipeline,
            "parse_elapsed_ms": max(0, int(parse_elapsed_ms or 0)),
            "row_count": int(row_count or 0),
            "preview_rows": int(preview_rows or 0),
            "generated_at_ms": int(time.time() * 1000),
        }

    def build_report_schema(
        *,
        analysis_text: str,
        analysis_type_text: str,
        source: str,
        row_count: int,
    ) -> Dict[str, Any]:
        lines = [line.strip() for line in str(analysis_text or "").splitlines() if line.strip()]
        recommendations: List[str] = []
        trends: List[str] = []
        anomalies: List[str] = []
        for line in lines:
            lowered = line.lower()
            if len(recommendations) < 5 and ("建议" in line or lowered.startswith("- ")):
                recommendations.append(line.lstrip("- ").strip())
            if len(trends) < 5 and ("趋势" in line or "trend" in lowered):
                trends.append(line.lstrip("- ").strip())
            if len(anomalies) < 5 and ("异常" in line or "anomaly" in lowered):
                anomalies.append(line.lstrip("- ").strip())

        return {
            "overview": {
                "analysis_type": analysis_type_text,
                "source_type": source,
                "row_count": int(row_count or 0),
            },
            "anomalies": anomalies,
            "trends": trends,
            "recommendations": recommendations,
            "narrative": analysis_text,
        }

    table_payload = (
        tool_args.get("table")
        or tool_args.get("csv")
        or tool_args.get("content")
        or latest_input
    )
    query = tool_args.get("query") or tool_args.get("question") or ""
    analysis_type = (
        tool_args.get("analysisType")
        or tool_args.get("analysis_type")
        or "comprehensive"
    )
    requested_provider = str(
        engine._get_tool_arg(tool_args, "provider_id", "providerId", "provider")
        or ""
    ).strip()
    requested_model = str(
        engine._get_tool_arg(tool_args, "model_id", "modelId", "model")
        or ""
    ).strip()
    requested_profile_id = str(
        engine._get_tool_arg(tool_args, "profile_id", "profileId", "provider_profile_id", "providerProfileId")
        or ""
    ).strip()

    parse_started_at = int(time.time() * 1000)
    try:
        table_text, source_type = engine._table_payload_to_text(table_payload)
    except Exception as exc:
        return {
            "tool": "table_analyze",
            "analysisType": analysis_type,
            "rowCount": 0,
            "summary": f"表格数据解析失败：{exc}",
            "status": "invalid_input",
            "lineage": {
                "source_type": "parse_failed",
                "input_kind": type(table_payload).__name__,
                "reference": str(table_payload)[:1024] if isinstance(table_payload, str) else None,
                "pipeline": ["input", "parse_failed"],
                "parse_elapsed_ms": max(0, int(time.time() * 1000) - parse_started_at),
                "row_count": 0,
                "preview_rows": 0,
                "generated_at_ms": int(time.time() * 1000),
            },
        }

    rows = [line for line in table_text.splitlines() if line.strip()]

    if not rows:
        return {
            "tool": "table_analyze",
            "analysisType": analysis_type,
            "rowCount": 0,
            "summary": "未检测到有效的表格数据，请提供 CSV、JSON 或可解析文本。",
            "status": "no_data",
            "lineage": build_lineage(
                payload=table_payload,
                source=source_type,
                parse_elapsed_ms=int(time.time() * 1000) - parse_started_at,
                row_count=0,
                preview_rows=0,
            ),
        }

    max_rows = 200
    table_preview = "\n".join(rows[:max_rows])
    truncated = len(rows) > max_rows

    prompt = f"""你是一位专业的数据分析师。请对以下表格数据进行 {analysis_type} 分析。

## 表格数据（共 {len(rows)} 行{f"，仅展示前 {max_rows} 行" if truncated else ""}）:
```
{table_preview}
```

{f"## 分析需求: {query}" if query else ""}

请提供:
1. **数据概览**: 数据结构、字段含义、数据量
2. **关键发现**: 重要趋势、异常值、数据特征
3. **深度分析**: 根据分析类型（{analysis_type}）进行针对性分析
4. **行动建议**: 基于数据的具体可执行建议

请用中文回答，使用 Markdown 格式。"""

    try:
        provider_id, model_id = engine._select_text_chat_target(
            requested_provider=requested_provider,
            requested_model=requested_model,
            requested_profile_id=requested_profile_id,
        )
        result = await engine._invoke_llm_chat(
            provider_id=provider_id,
            model_id=model_id,
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一位资深数据分析师，擅长从表格数据中发现洞察和趋势。请提供专业、可操作的分析结果。",
            temperature=0.3,
            max_tokens=4096,
            profile_id=requested_profile_id,
        )
        analysis_text = engine._normalize_agent_response_text(
            text=result.get("text", ""),
            expected_format="markdown",
        )
        used_target = f"{provider_id}/{model_id}"
    except Exception as exc:
        logger.warning(f"[WorkflowEngine] table_analyze LLM 调用失败，降级为基础统计: {exc}")
        analysis_text = (
            f"## 基础统计信息\n\n"
            f"- **总行数**: {len(rows)}\n"
            f"- **分析类型**: {analysis_type}\n"
            f"- **数据来源**: {source_type}\n"
            f"- **首行（标题）**: {rows[0] if rows else 'N/A'}\n"
            f"- **备注**: LLM 服务暂时不可用，仅提供基础统计。请检查 API Key 配置。\n"
        )
        used_target = "fallback"

    parse_elapsed_ms = int(time.time() * 1000) - parse_started_at
    lineage = build_lineage(
        payload=table_payload,
        source=source_type,
        parse_elapsed_ms=parse_elapsed_ms,
        row_count=len(rows),
        preview_rows=min(len(rows), max_rows),
    )
    schema_payload = build_report_schema(
        analysis_text=analysis_text,
        analysis_type_text=analysis_type,
        source=source_type,
        row_count=len(rows),
    )

    return {
        "tool": "table_analyze",
        "analysisType": analysis_type,
        "rowCount": len(rows),
        "sourceType": source_type,
        "model": used_target,
        "text": analysis_text,
        "summary": f"已完成 {analysis_type} 分析，共 {len(rows)} 行数据。",
        "status": "analyzed",
        "schema": schema_payload,
        "lineage": lineage,
    }
