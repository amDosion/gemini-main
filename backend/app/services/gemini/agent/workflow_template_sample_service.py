"""
Workflow Template Sample Service

Render real sample outputs for workflow templates and persist them
into template metadata, so templates can be previewed with real results.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from ....models.db_models import ActiveStorage
from ...agent.agent_llm_service import AgentLLMService
from ...agent.workflow_engine import WorkflowEngine
from ...agent.workflow_result_contract import (
    extract_runtime_hints as _extract_runtime_hints_shared,
    extract_text_preview as _extract_text_preview_shared,
    normalize_runtime_hint as _normalize_runtime_hint_shared,
    pick_primary_runtime as _pick_primary_runtime_shared,
)
from ...common.attachment_service import AttachmentService
from ...common.reference_image_catalog import pick_reference_image
from ....utils.case_converter import to_camel_case
from .test_template_fixture_service import (
    ADS_SAMPLE_SPREADSHEET_PATH,
    DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH,
    LISTING_SAMPLE_SPREADSHEET_PATH,
    ensure_data_analysis_sample_spreadsheet,
    ensure_listing_sample_spreadsheet,
)
from .tools.excel_tools import analyze_dataframe, clean_dataframe, read_excel_file
from .workflow_template_service import WorkflowTemplateService

logger = logging.getLogger(__name__)


DEFAULT_SAMPLE_FILE_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/2014_apple_stock.csv"
)
SAMPLE_TEMPLATE_ASSET_DIR = Path(__file__).resolve().parent / "test_templates"
TRUSTED_SAMPLE_ASSET_HOSTS = {
    "storage.googleapis.com",
    "raw.githubusercontent.com",
    "images.unsplash.com",
    "m.media-amazon.com",
    "images-cn.ssl-images-amazon.cn",
}
SAMPLE_ASSET_MAX_BYTES = {
    "image": 8 * 1024 * 1024,
    "audio": 16 * 1024 * 1024,
    "video": 32 * 1024 * 1024,
}


class WorkflowTemplateSampleService:
    def __init__(self, db: Session):
        self.db = db
        self.template_service = WorkflowTemplateService(db=db)
        try:
            ensure_listing_sample_spreadsheet()
            ensure_data_analysis_sample_spreadsheet()
        except Exception as exc:
            logger.warning("[TemplateSample] Failed to ensure local fixtures: %s", exc)

    @staticmethod
    def _normalize_node_type(node: Dict[str, Any]) -> str:
        if not isinstance(node, dict):
            return ""
        data = node.get("data")
        node_type = ""
        if isinstance(data, dict):
            node_type = str(data.get("type") or "").strip()
        if not node_type:
            node_type = str(node.get("type") or "").strip()
        return node_type.lower().replace("-", "_")

    @classmethod
    def _collect_node_types(cls, config: Dict[str, Any]) -> set[str]:
        node_types: set[str] = set()
        for node in config.get("nodes", []):
            normalized = cls._normalize_node_type(node)
            if normalized:
                node_types.add(normalized)
        return node_types

    @staticmethod
    def _default_task(template_name: str, category: str) -> str:
        normalized_name = str(template_name or "").strip()
        normalized_category = str(category or "").strip()
        if "亚马逊" in normalized_category or "amazon" in normalized_category.lower():
            return f"请按模板《{normalized_name}》生成一份可执行的亚马逊运营输出。"
        if "图像" in normalized_category or "image" in normalized_category.lower():
            return f"请按模板《{normalized_name}》生成高质量视觉结果。"
        if "数据" in normalized_category or "analysis" in normalized_category.lower():
            return f"请按模板《{normalized_name}》输出结构化分析结论。"
        return f"请按模板《{normalized_name}》执行并输出完整结果。"

    @staticmethod
    def _extract_template_meta(template_payload: Dict[str, Any]) -> Dict[str, Any]:
        config = template_payload.get("config") if isinstance(template_payload.get("config"), dict) else {}
        meta = config.get("_templateMeta")
        if isinstance(meta, dict):
            return meta
        return {}

    @classmethod
    def _collect_template_tags(cls, template_payload: Dict[str, Any]) -> set[str]:
        tags: set[str] = set()
        for value in template_payload.get("tags") or []:
            text = str(value or "").strip().lower()
            if text:
                tags.add(text)

        meta = cls._extract_template_meta(template_payload)
        for value in meta.get("tags") or []:
            text = str(value or "").strip().lower()
            if text:
                tags.add(text)
        return tags

    @classmethod
    def _is_ads_analysis_template(cls, template_payload: Dict[str, Any]) -> bool:
        name = str(template_payload.get("name") or "").strip().lower()
        category = str(template_payload.get("category") or "").strip().lower()
        meta = cls._extract_template_meta(template_payload)
        starter_key = str(meta.get("starterKey") or "").strip().lower()
        tags = cls._collect_template_tags(template_payload)

        keyword_candidates = [
            name,
            category,
            starter_key,
            " ".join(sorted(tags)),
        ]
        haystack = " ".join(item for item in keyword_candidates if item).lower()
        if not haystack:
            return False
        return any(
            keyword in haystack
            for keyword in (
                "ads",
                "ppc",
                "campaign",
                "roas",
                "acos",
                "广告",
                "竞价",
                "投放",
            )
        )

    @classmethod
    def _is_listing_optimization_template(cls, template_payload: Dict[str, Any]) -> bool:
        name = str(template_payload.get("name") or "").strip().lower()
        category = str(template_payload.get("category") or "").strip().lower()
        meta = cls._extract_template_meta(template_payload)
        starter_key = str(meta.get("starterKey") or "").strip().lower()
        tags = cls._collect_template_tags(template_payload)

        keyword_candidates = [
            name,
            category,
            starter_key,
            " ".join(sorted(tags)),
        ]
        haystack = " ".join(item for item in keyword_candidates if item).lower()
        if not haystack:
            return False
        return any(
            keyword in haystack
            for keyword in (
                "listing",
                "title",
                "bullet",
                "search terms",
                "searchterms",
                "标题",
                "五点",
                "产品描述",
                "文案",
                "优化",
            )
        )

    @classmethod
    def _is_data_analysis_template(cls, template_payload: Dict[str, Any]) -> bool:
        name = str(template_payload.get("name") or "").strip().lower()
        category = str(template_payload.get("category") or "").strip().lower()
        meta = cls._extract_template_meta(template_payload)
        starter_key = str(meta.get("starterKey") or "").strip().lower()
        tags = cls._collect_template_tags(template_payload)

        keyword_candidates = [
            name,
            category,
            starter_key,
            " ".join(sorted(tags)),
        ]
        haystack = " ".join(item for item in keyword_candidates if item).lower()
        if not haystack:
            return False
        return any(
            keyword in haystack
            for keyword in (
                "data-analysis",
                "table-analysis",
                "excel-analysis",
                "excel",
                "table",
                "数据分析",
                "表格分析",
                "报表分析",
            )
        )

    @classmethod
    def _resolve_sample_file_url(cls, template_payload: Dict[str, Any], node_types: set[str]) -> str:
        if cls._is_ads_analysis_template(template_payload) and ADS_SAMPLE_SPREADSHEET_PATH.exists():
            return ADS_SAMPLE_SPREADSHEET_PATH.resolve().as_uri()
        if cls._is_listing_optimization_template(template_payload) and LISTING_SAMPLE_SPREADSHEET_PATH.exists():
            return LISTING_SAMPLE_SPREADSHEET_PATH.resolve().as_uri()
        if cls._is_data_analysis_template(template_payload) and DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH.exists():
            return DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH.resolve().as_uri()
        if "input_file" not in node_types:
            return ""
        return DEFAULT_SAMPLE_FILE_URL

    def build_sample_input(self, template_payload: Dict[str, Any]) -> Dict[str, Any]:
        config = template_payload.get("config") if isinstance(template_payload.get("config"), dict) else {}
        node_types = self._collect_node_types(config)
        meta = config.get("_templateMeta") if isinstance(config.get("_templateMeta"), dict) else {}
        sample_input = meta.get("sampleInput")
        if isinstance(sample_input, dict) and sample_input:
            normalized_sample_input = dict(sample_input)
            file_url = self._resolve_sample_file_url(template_payload=template_payload, node_types=node_types)
            if file_url:
                normalized_sample_input["fileUrl"] = file_url
            return self._materialize_sample_input_assets(normalized_sample_input)

        template_id = str(template_payload.get("id") or "").strip()
        template_name = str(template_payload.get("name") or "").strip()
        category = str(template_payload.get("category") or "").strip()

        payload: Dict[str, Any] = {
            "task": self._default_task(template_name=template_name, category=category),
        }
        if "input_image" in node_types or "start" in node_types:
            payload["imageUrl"] = pick_reference_image(seed=template_id or template_name, index=0)
        file_url = self._resolve_sample_file_url(template_payload=template_payload, node_types=node_types)
        if file_url:
            payload["fileUrl"] = file_url
        return self._materialize_sample_input_assets(payload)

    @staticmethod
    def _is_trusted_sample_asset_url(url: str) -> bool:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme not in {"http", "https"}:
            return False
        hostname = str(parsed.hostname or "").strip().lower()
        if not hostname:
            return False
        if hostname in TRUSTED_SAMPLE_ASSET_HOSTS:
            return True
        return any(hostname.endswith(f".{allowed}") for allowed in TRUSTED_SAMPLE_ASSET_HOSTS)

    @classmethod
    def _download_sample_remote_asset(
        cls,
        url: str,
        *,
        asset_kind: str,
    ) -> Tuple[bytes, str]:
        max_bytes = SAMPLE_ASSET_MAX_BYTES.get(asset_kind, 8 * 1024 * 1024)
        request = Request(
            url=str(url).strip(),
            headers={
                "User-Agent": "WorkflowTemplateSampleService/1.0",
                "Accept": "*/*",
            },
        )
        with urlopen(request, timeout=20) as response:  # nosec B310 - guarded by allowlist
            mime_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"sample {asset_kind} exceeds {max_bytes // (1024 * 1024)}MB limit")
        if not mime_type:
            guessed = mimetypes.guess_type(str(url).strip())[0]
            mime_type = str(guessed or "").strip().lower()
        return raw, mime_type

    @staticmethod
    def _read_local_sample_asset(path: Path, *, asset_kind: str) -> Tuple[bytes, str]:
        max_bytes = SAMPLE_ASSET_MAX_BYTES.get(asset_kind, 8 * 1024 * 1024)
        if path.stat().st_size > max_bytes:
            raise ValueError(f"sample {asset_kind} exceeds {max_bytes // (1024 * 1024)}MB limit")
        mime_type = str(mimetypes.guess_type(str(path))[0] or "").strip().lower()
        return path.read_bytes(), mime_type

    @staticmethod
    def _encode_data_url(binary: bytes, mime_type: str, fallback_prefix: str) -> str:
        normalized_mime = str(mime_type or "").strip().lower()
        if not normalized_mime:
            normalized_mime = f"{fallback_prefix}/octet-stream"
        encoded = base64.b64encode(binary).decode("ascii")
        return f"data:{normalized_mime};base64,{encoded}"

    @classmethod
    def _inline_sample_asset_if_needed(
        cls,
        value: Any,
        *,
        asset_kind: str,
    ) -> Any:
        if isinstance(value, list):
            return [
                cls._inline_sample_asset_if_needed(item, asset_kind=asset_kind)
                for item in value
            ]
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized or normalized.startswith("data:"):
            return value
        if normalized.startswith("sample://"):
            sample_name = normalized[len("sample://"):].strip().lstrip("/")
            sample_path = (SAMPLE_TEMPLATE_ASSET_DIR / sample_name).resolve()
            try:
                sample_path.relative_to(SAMPLE_TEMPLATE_ASSET_DIR.resolve())
            except Exception as exc:
                raise ValueError(f"invalid sample asset path: {normalized}") from exc
            if not sample_path.exists():
                raise ValueError(f"sample asset not found: {normalized}")
            binary, mime_type = cls._read_local_sample_asset(sample_path, asset_kind=asset_kind)
            return cls._encode_data_url(binary, mime_type, asset_kind)
        local_path = cls._resolve_local_file_path(normalized)
        if local_path is not None:
            binary, mime_type = cls._read_local_sample_asset(local_path, asset_kind=asset_kind)
            return cls._encode_data_url(binary, mime_type, asset_kind)
        if not cls._is_trusted_sample_asset_url(normalized):
            return value
        binary, mime_type = cls._download_sample_remote_asset(normalized, asset_kind=asset_kind)
        return cls._encode_data_url(binary, mime_type, asset_kind)

    @classmethod
    def _materialize_sample_input_assets(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized_payload = dict(payload or {})
        for image_key in ("imageUrl", "imageUrls"):
            if image_key in normalized_payload:
                normalized_payload[image_key] = cls._inline_sample_asset_if_needed(
                    normalized_payload.get(image_key),
                    asset_kind="image",
                )
        for video_key in ("videoUrl", "videoUrls"):
            if video_key in normalized_payload:
                normalized_payload[video_key] = cls._inline_sample_asset_if_needed(
                    normalized_payload.get(video_key),
                    asset_kind="video",
                )
        for audio_key in ("audioUrl", "audioUrls"):
            if audio_key in normalized_payload:
                normalized_payload[audio_key] = cls._inline_sample_asset_if_needed(
                    normalized_payload.get(audio_key),
                    asset_kind="audio",
                )
        return normalized_payload

    @classmethod
    def _prepare_nodes_for_sample_run(cls, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict):
                prepared.append(node)
                continue
            normalized = copy.deepcopy(node)
            node_type = cls._normalize_node_type(normalized)
            if node_type == "agent":
                data = normalized.get("data")
                if isinstance(data, dict):
                    # Keep template execution deterministic: do not auto-switch to unknown "latest" model ids.
                    data["agentPreferLatestModel"] = False
                    task_type = str(data.get("agentTaskType") or "").strip().lower().replace("_", "-")
                    model_candidates = [
                        str(data.get("modelOverrideModelId") or "").strip().lower(),
                        str(data.get("agentModelId") or "").strip().lower(),
                    ]
                    model_id = next((item for item in model_candidates if item), "")
                    if (
                        model_id
                        and any(token in model_id for token in ("imagen", "image", "nano-banana"))
                        and task_type in {"", "chat"}
                    ):
                        # Some templates bind image model ids but keep default chat task; coerce to image-gen for sample rendering.
                        data["agentTaskType"] = "image-gen"
                    normalized["data"] = data
            prepared.append(normalized)
        return prepared

    @staticmethod
    def _guess_image_mime_type(image_url: str) -> str:
        raw = str(image_url or "").strip()
        if not raw:
            return "image/png"

        lowered = raw.lower()
        if lowered.startswith("data:image/"):
            header = raw.split(",", 1)[0]
            mime = str(header.split(":", 1)[1].split(";", 1)[0] if ":" in header else "").strip().lower()
            if mime.startswith("image/"):
                return mime
            return "image/png"

        clean_url = raw.split("?", 1)[0].split("#", 1)[0]
        guessed, _ = mimetypes.guess_type(clean_url)
        normalized = str(guessed or "").strip().lower()
        if normalized.startswith("image/"):
            return normalized
        return "image/png"

    @classmethod
    def _extract_image_urls(cls, payload: Any) -> List[str]:
        urls: List[str] = []
        seen: set[str] = set()
        image_pattern = re.compile(
            r"^data:image/|^https?://|^/api/temp-images/",
            re.IGNORECASE,
        )

        def push(candidate: Any):
            if not isinstance(candidate, str):
                return
            value = candidate.strip()
            if not value:
                return
            if image_pattern.search(value) is None:
                return
            if value in seen:
                return
            seen.add(value)
            urls.append(value)

        def walk(obj: Any):
            push(obj)
            if isinstance(obj, list):
                for item in obj:
                    walk(item)
            elif isinstance(obj, dict):
                for value in obj.values():
                    walk(value)

        walk(payload)
        return urls

    @classmethod
    def _replace_payload_image_urls(cls, payload: Any, replacements: Dict[str, str]) -> Any:
        if not replacements:
            return payload
        if isinstance(payload, str):
            return replacements.get(payload, payload)
        if isinstance(payload, list):
            return [cls._replace_payload_image_urls(item, replacements) for item in payload]
        if isinstance(payload, dict):
            return {
                key: cls._replace_payload_image_urls(value, replacements)
                for key, value in payload.items()
            }
        return payload

    async def _persist_result_images(
        self,
        *,
        user_id: str,
        template_id: str,
        result_payload: Any,
    ) -> Tuple[Any, Dict[str, str]]:
        if result_payload is None:
            return result_payload, {}

        extracted_urls = self._extract_image_urls(result_payload)
        if not extracted_urls:
            return result_payload, {}

        candidates: List[str] = []
        seen: set[str] = set()
        for url in extracted_urls:
            raw = str(url or "").strip()
            if not raw or raw in seen:
                continue
            lowered = raw.lower()
            if lowered.startswith("/api/temp-images/"):
                continue
            if lowered.startswith("blob:"):
                continue
            if not lowered.startswith(("data:image/", "http://", "https://")):
                continue
            seen.add(raw)
            candidates.append(raw)

        if not candidates:
            return result_payload, {}

        active_storage = self.db.query(ActiveStorage).filter(
            ActiveStorage.user_id == user_id
        ).first()
        storage_id = active_storage.storage_id if active_storage and active_storage.storage_id else None
        attachment_service = AttachmentService(self.db)
        safe_ref_id = str(template_id or "").strip()[:36] or str(user_id or "").strip()[:36]
        replacements: Dict[str, str] = {}

        for index, image_url in enumerate(candidates, start=1):
            try:
                processed = await attachment_service.process_ai_result(
                    ai_url=image_url,
                    mime_type=self._guess_image_mime_type(image_url),
                    session_id=safe_ref_id,
                    message_id=safe_ref_id,
                    user_id=user_id,
                    prefix=f"template-sample-{index:02d}",
                    storage_id=storage_id,
                )
                display_url = str(processed.get("display_url") or "").strip()
                replacements[image_url] = display_url or image_url
            except Exception as exc:
                self.db.rollback()
                logger.warning("[TemplateSample] Failed to persist result image: %s", exc)

        if not replacements:
            return result_payload, {}
        return self._replace_payload_image_urls(result_payload, replacements), replacements

    @staticmethod
    def _extract_text_preview(payload: Any, max_length: int = 280) -> str:
        return _extract_text_preview_shared(payload, max_length=max_length, strip_markdown_fence=False)

    @staticmethod
    def _normalize_runtime_hint(value: Any) -> Optional[str]:
        return _normalize_runtime_hint_shared(value)

    @classmethod
    def _extract_runtime_hints(
        cls,
        payload: Any,
        _seen: Optional[set[str]] = None,
        _depth: int = 0,
        _allow_scalar: bool = False,
    ) -> List[str]:
        return _extract_runtime_hints_shared(
            payload,
            _seen=_seen,
            _depth=_depth,
            _allow_scalar=_allow_scalar,
        )

    @staticmethod
    def _pick_primary_runtime(runtime_hints: List[str]) -> str:
        return _pick_primary_runtime_shared(runtime_hints)

    @classmethod
    def _build_result_summary(cls, result_payload: Any) -> Dict[str, Any]:
        from ....routers.ai.workflows import _build_workflow_result_summary

        return _build_workflow_result_summary(result_payload)

    @staticmethod
    def _resolve_local_file_path(file_url: str) -> Optional[Path]:
        candidate = str(file_url or "").strip()
        if not candidate:
            return None
        if candidate.startswith("file://"):
            parsed = urlparse(candidate)
            path_text = unquote(parsed.path or "")
            if not path_text:
                return None
            path = Path(path_text)
            return path if path.exists() else None
        path = Path(candidate)
        if path.exists():
            return path
        return None

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): WorkflowTemplateSampleService._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [WorkflowTemplateSampleService._to_json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [WorkflowTemplateSampleService._to_json_safe(item) for item in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return str(value)
        return str(value)

    @classmethod
    def _resolve_analysis_type_from_template(
        cls,
        template_payload: Dict[str, Any],
        sample_input: Dict[str, Any],
    ) -> str:
        configured = str(
            sample_input.get("analysisType")
            or sample_input.get("analysis_type")
            or ""
        ).strip().lower()
        if configured:
            return configured

        config = template_payload.get("config") if isinstance(template_payload.get("config"), dict) else {}
        nodes = config.get("nodes") if isinstance(config.get("nodes"), list) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_data = node.get("data")
            if not isinstance(node_data, dict):
                continue
            task_type = str(node_data.get("agentTaskType") or node_data.get("agent_task_type") or "").strip().lower()
            if task_type in {"data-analysis", "table-analysis"}:
                candidate = str(
                    node_data.get("toolAnalysisType")
                    or node_data.get("tool_analysis_type")
                    or node_data.get("analysisType")
                    or node_data.get("analysis_type")
                    or ""
                ).strip().lower()
                if candidate:
                    return candidate
        return "comprehensive"

    @classmethod
    async def _run_non_workflow_data_analysis(
        cls,
        *,
        template_payload: Dict[str, Any],
        sample_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        template_name = str(template_payload.get("name") or "数据分析模板").strip() or "数据分析模板"
        file_url = str(sample_input.get("fileUrl") or sample_input.get("file_url") or "").strip()
        if not file_url:
            raise ValueError("data-analysis template sample requires fileUrl")

        local_path = cls._resolve_local_file_path(file_url)
        if local_path is None:
            raise ValueError(f"data-analysis template requires a local fixture file, got: {file_url}")

        read_result = await read_excel_file(str(local_path), sheet_name=0)
        if isinstance(read_result, dict) and read_result.get("error"):
            raise ValueError(f"read_excel_file failed: {read_result.get('error')}")

        cleaning_rules = sample_input.get("cleaningRules")
        if not isinstance(cleaning_rules, dict):
            cleaning_rules = {
                "handle_nulls": "fill",
                "fill_value": 0,
                "remove_outliers": False,
                "standardize": False,
            }

        cleaned_result = await clean_dataframe(read_result, cleaning_rules)
        source_for_analysis: Dict[str, Any] = cleaned_result if isinstance(cleaned_result, dict) else {}
        if source_for_analysis.get("error"):
            source_for_analysis = read_result

        analysis_type = cls._resolve_analysis_type_from_template(template_payload, sample_input)
        analysis_result = await analyze_dataframe(source_for_analysis, analysis_type=analysis_type)

        shape = read_result.get("shape") if isinstance(read_result, dict) else None
        row_count = int(shape[0]) if isinstance(shape, list) and len(shape) > 0 else 0
        column_count = int(shape[1]) if isinstance(shape, list) and len(shape) > 1 else 0
        insights = analysis_result.get("insights") if isinstance(analysis_result, dict) else []
        if not isinstance(insights, list):
            insights = []

        report_lines = [
            f"# {template_name} 分析报告",
            "",
            f"- 数据文件: {file_url}",
            f"- 行数: {row_count}",
            f"- 列数: {column_count}",
            f"- 分析类型: {analysis_type}",
            "",
            "## 核心洞察",
        ]
        if insights:
            for item in insights:
                text = str(item or "").strip()
                if text:
                    report_lines.append(f"- {text}")
        else:
            report_lines.append("- 未识别到明显洞察。")
        report_text = "\n".join(report_lines).strip()

        result_payload: Dict[str, Any] = {
            "finalOutput": {
                "text": report_text,
                "runtime": "template-non-workflow-analysis",
                "analysisType": analysis_type,
                "sourceFileUrl": file_url,
                "sourceFilePath": str(local_path),
                "rowCount": row_count,
                "columnCount": column_count,
                "insights": insights,
                "analysis": analysis_result,
            },
            "outputs": {
                "template-data-reader": {
                    "runtime": "template-non-workflow-analysis",
                    "text": f"已读取数据文件: {local_path.name}",
                    "readResult": read_result,
                },
                "template-data-cleaner": {
                    "runtime": "template-non-workflow-analysis",
                    "text": "已执行数据清理",
                    "cleanResult": cleaned_result,
                },
                "template-data-analyzer": {
                    "runtime": "template-non-workflow-analysis",
                    "text": "已执行结构化数据分析",
                    "analysisResult": analysis_result,
                },
                "template-report": {
                    "runtime": "template-non-workflow-analysis",
                    "text": report_text,
                },
            },
            "errors": {},
            "finalNodeId": "template-report",
            "loopIterations": {},
            "nodeStates": {
                "template-data-reader": "completed",
                "template-data-cleaner": "completed",
                "template-data-analyzer": "completed",
                "template-report": "completed",
            },
            "visitCounts": {
                "template-data-reader": 1,
                "template-data-cleaner": 1,
                "template-data-analyzer": 1,
                "template-report": 1,
            },
        }
        return cls._to_json_safe(result_payload)

    async def _run_one_template(
        self,
        *,
        user_id: str,
        template_payload: Dict[str, Any],
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        template_id = str(template_payload.get("id") or "").strip()
        config = template_payload.get("config") if isinstance(template_payload.get("config"), dict) else {}
        nodes = config.get("nodes") if isinstance(config.get("nodes"), list) else []
        edges = config.get("edges") if isinstance(config.get("edges"), list) else []
        prepared_nodes = self._prepare_nodes_for_sample_run(nodes=nodes)
        if not template_id or not nodes:
            raise ValueError("invalid template payload")

        is_data_analysis_template = self._is_data_analysis_template(template_payload)
        if is_data_analysis_template:
            fixture_path = ensure_data_analysis_sample_spreadsheet()
            if not fixture_path.exists():
                raise ValueError(f"data-analysis fixture is missing: {fixture_path}")

        sample_input = self.build_sample_input(template_payload=template_payload)
        if is_data_analysis_template:
            # Data-analysis templates are materialized through a non-workflow path
            # so the sample is deterministic and always bound to local fixtures.
            raw_result = await asyncio.wait_for(
                self._run_non_workflow_data_analysis(
                    template_payload=template_payload,
                    sample_input=sample_input,
                ),
                timeout=max(30, int(timeout_seconds)),
            )
        else:
            llm_service = AgentLLMService(user_id=user_id, db=self.db)
            engine = WorkflowEngine(db=self.db, llm_service=llm_service)

            async def _execute():
                return await engine.execute(
                    nodes=prepared_nodes,
                    edges=edges,
                    initial_input=sample_input,
                    on_event=None,
                )

            raw_result = await asyncio.wait_for(_execute(), timeout=max(30, int(timeout_seconds)))
        serialized_result = to_camel_case(raw_result)
        persisted_result, _ = await self._persist_result_images(
            user_id=user_id,
            template_id=template_id,
            result_payload=serialized_result,
        )
        summary = self._build_result_summary(persisted_result)
        await self.template_service.update_template_sample_result(
            user_id=user_id,
            template_id=template_id,
            result_payload=persisted_result,
            result_summary=summary,
            execution_id=None,
            input_payload=sample_input,
        )
        return {
            "template_id": template_id,
            "template_name": str(template_payload.get("name") or ""),
            "status": "success",
            "summary": summary,
        }

    async def materialize_for_user(
        self,
        *,
        user_id: str,
        template_ids: Optional[Sequence[str]] = None,
        force: bool = False,
        limit: Optional[int] = None,
        timeout_seconds: int = 240,
    ) -> Dict[str, Any]:
        all_templates = await self.template_service.list_templates(
            user_id=user_id,
            include_public=False,
        )
        selected_ids = {str(item).strip() for item in (template_ids or []) if str(item).strip()}

        pending_templates: List[Dict[str, Any]] = []
        for template in all_templates:
            template_id = str(template.get("id") or "").strip()
            if not template_id:
                continue
            if selected_ids and template_id not in selected_ids:
                continue
            sample_summary = template.get("sample_result_summary")
            has_sample = isinstance(sample_summary, dict) and bool(sample_summary.get("has_result"))
            if has_sample and not force:
                continue
            pending_templates.append(template)

        if limit is not None:
            safe_limit = max(0, int(limit))
            pending_templates = pending_templates[:safe_limit]

        success_items: List[Dict[str, Any]] = []
        failed_items: List[Dict[str, Any]] = []

        for template in pending_templates:
            template_id = str(template.get("id") or "").strip()
            template_name = str(template.get("name") or "")
            try:
                logger.info(
                    "[TemplateSample] Materializing template sample: user=%s template=%s(%s)",
                    user_id,
                    template_name,
                    template_id,
                )
                result = await self._run_one_template(
                    user_id=user_id,
                    template_payload=template,
                    timeout_seconds=timeout_seconds,
                )
                success_items.append(result)
            except Exception as exc:
                logger.error(
                    "[TemplateSample] Materialize failed: user=%s template=%s(%s) error=%s",
                    user_id,
                    template_name,
                    template_id,
                    exc,
                    exc_info=True,
                )
                failed_items.append({
                    "template_id": template_id,
                    "template_name": template_name,
                    "status": "failed",
                    "error": str(exc),
                })

        return {
            "user_id": user_id,
            "requested_count": len(pending_templates),
            "success_count": len(success_items),
            "failed_count": len(failed_items),
            "successes": success_items,
            "failures": failed_items,
        }
