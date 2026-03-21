"""
Excel Analysis Workflow - Excel 分析工作流

统一走 WorkflowEngine：
- start -> input_file -> tool(table_analyze) -> end
- 复用 workflow_engine 的表格解析和 LLM 分析能力
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy.orm import Session

from ....agent.agent_llm_service import AgentLLMService
from ....agent.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class ExcelAnalysisWorkflow:
    """Excel 分析工作流（WorkflowEngine 统一链路实现）"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = str(user_id or "").strip()
        logger.info("[ExcelAnalysisWorkflow] Initialized with WorkflowEngine")

    @staticmethod
    def _normalize_analysis_type(analysis_type: str) -> str:
        raw = str(analysis_type or "comprehensive").strip().lower()
        aliases = {
            "summary": "statistics",
            "stats": "statistics",
            "statistic": "statistics",
            "trend": "trends",
            "anomaly": "distribution",
            "anomalies": "distribution",
            "all": "comprehensive",
        }
        normalized = aliases.get(raw, raw)
        allowed = {"comprehensive", "statistics", "correlation", "trends", "distribution"}
        return normalized if normalized in allowed else "comprehensive"

    @staticmethod
    def _default_cleaning_rules() -> Dict[str, Any]:
        return {
            "handle_nulls": "fill",
            "fill_value": 0,
            "remove_outliers": False,
            "standardize": False,
        }

    @staticmethod
    def _build_graph() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = [
            {
                "id": "start",
                "type": "start",
                "data": {"type": "start"},
            },
            {
                "id": "input-file",
                "type": "input_file",
                "data": {"type": "input_file"},
            },
            {
                "id": "table-analyze",
                "type": "tool",
                "data": {
                    "type": "tool",
                    "tool_name": "table_analyze",
                    "tool_args_template": {
                        "table": "{{input.fileUrl}}",
                        "analysis_type": "{{input.analysis_type}}",
                        "query": "{{input.task}}",
                    },
                },
            },
            {
                "id": "end",
                "type": "end",
                "data": {"type": "end"},
            },
        ]
        edges = [
            {"id": "edge-start-input", "source": "start", "target": "input-file"},
            {"id": "edge-input-tool", "source": "input-file", "target": "table-analyze"},
            {"id": "edge-tool-end", "source": "table-analyze", "target": "end"},
        ]
        return nodes, edges

    @staticmethod
    def _build_analysis_prompt(
        *,
        analysis_type: str,
        cleaning_rules: Dict[str, Any],
    ) -> str:
        return (
            f"请对该 Excel/CSV 数据执行 {analysis_type} 分析。\n"
            "输出要求：\n"
            "1. 数据概览（字段、规模、质量）\n"
            "2. 关键发现（趋势、异常、相关性）\n"
            "3. 可执行建议（至少 3 条）\n"
            "4. 结论摘要（业务可读）\n"
            f"清理规则参考：{json.dumps(cleaning_rules, ensure_ascii=False)}"
        )

    @staticmethod
    def _extract_table_analyze_result(outputs: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(outputs, dict):
            return {}
        tool_node_output = outputs.get("table-analyze") or outputs.get("table_analyze")
        if not isinstance(tool_node_output, dict):
            return {}
        tool_result = tool_node_output.get("result")
        if isinstance(tool_result, dict):
            return tool_result
        return {}

    @staticmethod
    def _normalize_report_schema(
        table_analysis: Dict[str, Any],
        *,
        analysis_type: str,
        source_type: str,
        row_count: int,
    ) -> Dict[str, Any]:
        schema_payload = table_analysis.get("schema")
        if isinstance(schema_payload, dict):
            overview = schema_payload.get("overview") if isinstance(schema_payload.get("overview"), dict) else {}
            return {
                "overview": {
                    "analysis_type": str(overview.get("analysis_type") or analysis_type),
                    "source_type": str(overview.get("source_type") or source_type),
                    "row_count": int(overview.get("row_count") or row_count),
                },
                "anomalies": schema_payload.get("anomalies") if isinstance(schema_payload.get("anomalies"), list) else [],
                "trends": schema_payload.get("trends") if isinstance(schema_payload.get("trends"), list) else [],
                "recommendations": (
                    schema_payload.get("recommendations")
                    if isinstance(schema_payload.get("recommendations"), list)
                    else []
                ),
                "narrative": str(
                    schema_payload.get("narrative")
                    or table_analysis.get("text")
                    or ""
                ).strip(),
            }

        return {
            "overview": {
                "analysis_type": analysis_type,
                "source_type": source_type,
                "row_count": row_count,
            },
            "anomalies": [],
            "trends": [],
            "recommendations": [],
            "narrative": str(table_analysis.get("text") or "").strip(),
        }

    @staticmethod
    def _collect_steps(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("event_type") or "").strip()
            node_id = str(event.get("nodeId") or event.get("node_id") or "").strip()
            if not event_type or not node_id:
                continue
            if event_type == "node_complete":
                steps.append(
                    {
                        "node_id": node_id,
                        "status": "completed",
                        "timestamp": event.get("timestamp"),
                    }
                )
            elif event_type == "node_error":
                steps.append(
                    {
                        "node_id": node_id,
                        "status": "failed",
                        "timestamp": event.get("timestamp"),
                        "error": event.get("error"),
                    }
                )
        return steps

    async def execute(
        self,
        file_reference: str,
        analysis_type: str = "comprehensive",
        cleaning_rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行 Excel 分析工作流。

        Args:
            file_reference: 文件引用（http(s)/data URL 或受控本地路径）
            analysis_type: 分析类型
            cleaning_rules: 清理规则（用于提示上下文）

        Returns:
            统一的分析结果
        """
        normalized_file_reference = str(file_reference or "").strip()
        if not normalized_file_reference:
            return {"success": False, "error": "file_reference is required"}

        normalized_analysis_type = self._normalize_analysis_type(analysis_type)
        normalized_cleaning_rules = (
            dict(cleaning_rules) if isinstance(cleaning_rules, dict) else self._default_cleaning_rules()
        )

        logger.info(
            "[ExcelAnalysisWorkflow] Starting execution: source=%s analysis_type=%s",
            normalized_file_reference,
            normalized_analysis_type,
        )

        try:
            llm_service = AgentLLMService(user_id=self.user_id, db=self.db)
            engine = WorkflowEngine(db=self.db, llm_service=llm_service)
            nodes, edges = self._build_graph()

            events: List[Dict[str, Any]] = []

            async def on_event(event_type: str, data: Dict[str, Any]) -> None:
                payload = {"event_type": event_type}
                if isinstance(data, dict):
                    payload.update(data)
                events.append(payload)

            prompt = self._build_analysis_prompt(
                analysis_type=normalized_analysis_type,
                cleaning_rules=normalized_cleaning_rules,
            )
            result = await engine.execute(
                nodes=nodes,
                edges=edges,
                initial_input={
                    "task": prompt,
                    "text": prompt,
                    "analysis_type": normalized_analysis_type,
                    "cleaning_rules": normalized_cleaning_rules,
                    "fileUrl": normalized_file_reference,
                    "file_url": normalized_file_reference,
                },
                on_event=on_event,
            )

            outputs = result.get("outputs") if isinstance(result, dict) else {}
            if not isinstance(outputs, dict):
                outputs = {}
            table_analysis = self._extract_table_analyze_result(outputs)
            input_file_payload = outputs.get("input-file") if isinstance(outputs.get("input-file"), dict) else {}
            analysis_text = str(
                table_analysis.get("text")
                or (result.get("final_output") if isinstance(result.get("final_output"), str) else "")
                or ""
            ).strip()
            row_count = int(table_analysis.get("rowCount") or 0)
            source_type = str(table_analysis.get("sourceType") or "")
            report_schema = self._normalize_report_schema(
                table_analysis,
                analysis_type=normalized_analysis_type,
                source_type=source_type,
                row_count=row_count,
            )
            report_payload = {
                "text": analysis_text,
                "status": table_analysis.get("status"),
                "summary": table_analysis.get("summary"),
                "schema": report_schema,
            }

            errors = result.get("errors") if isinstance(result, dict) else {}
            success = not bool(errors)

            return {
                "success": success,
                "workflow": "excel_analysis",
                "file_reference": normalized_file_reference,
                "file_path": normalized_file_reference,
                "analysis_type": normalized_analysis_type,
                "cleaning_rules": normalized_cleaning_rules,
                "raw_data": input_file_payload,
                "cleaned_data": None,
                "analysis_results": table_analysis,
                "schema": report_schema,
                "lineage": table_analysis.get("lineage") if isinstance(table_analysis.get("lineage"), dict) else {},
                "report": report_payload,
                "final_output": result.get("final_output") if isinstance(result, dict) else None,
                "steps": self._collect_steps(events),
                "node_states": result.get("node_states") if isinstance(result, dict) else {},
                "errors": errors if isinstance(errors, dict) else {},
            }
        except Exception as e:
            logger.error(f"[ExcelAnalysisWorkflow] Execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "workflow": "excel_analysis",
                "file_reference": normalized_file_reference,
                "file_path": normalized_file_reference,
                "analysis_type": normalized_analysis_type,
                "cleaning_rules": normalized_cleaning_rules,
                "error": str(e),
            }
