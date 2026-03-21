"""
Workflow Template Service - 工作流模板服务

提供：
- 工作流模板保存
- 工作流模板加载
- 工作流模板列表和搜索
- 模板版本管理
"""

import logging
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from ....models.db_models import WorkflowTemplate, WorkflowTemplateCategory
from ...common.reference_image_catalog import (
    is_placeholder_reference_image_url,
    pick_reference_image,
)
from .starter_templates import load_starter_template_definitions

logger = logging.getLogger(__name__)

SUPPORTED_TEMPLATE_TASK_TYPES = {
    "chat",
    "image-gen",
    "image-edit",
    "video-gen",
    "audio-gen",
    "vision-understand",
    "data-analysis",
}

TASK_TYPE_ALIASES = {
    "image-generation": "image-gen",
    "image-understanding": "vision-understand",
    "image-understand": "vision-understand",
    "image-analyze": "vision-understand",
    "vision-analyze": "vision-understand",
    "vision-understanding": "vision-understand",
    "video": "video-gen",
    "video-generate": "video-gen",
    "video-generation": "video-gen",
    "text-to-video": "video-gen",
    "audio": "audio-gen",
    "audio-generate": "audio-gen",
    "audio-generation": "audio-gen",
    "speech": "audio-gen",
    "speech-gen": "audio-gen",
    "speech-generate": "audio-gen",
    "speech-generation": "audio-gen",
    "text-to-speech": "audio-gen",
    "tts": "audio-gen",
    "table-analysis": "data-analysis",
    "excel-analysis": "data-analysis",
    "sheet-analysis": "data-analysis",
}

STARTER_TEMPLATE_DEFINITIONS: List[Dict[str, Any]] = load_starter_template_definitions()
DEFAULT_TEMPLATE_CATEGORIES: List[str] = [
    "图像工作流",
    "多模态工作流",
    "数据分析",
    "亚马逊运营",
    "运营协同",
]


class WorkflowTemplateService:
    """
    工作流模板服务
    
    负责：
    - 工作流模板的 CRUD 操作
    - 模板搜索和过滤
    - 模板版本管理
    """
    
    def __init__(self, db: Session):
        """
        初始化工作流模板服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[WorkflowTemplateService] Initialized")

    def _normalize_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(config, dict):
            return {"schemaVersion": 2, "nodes": [], "edges": []}

        normalized = dict(config)
        if not isinstance(normalized.get("nodes"), list):
            normalized["nodes"] = []
        if not isinstance(normalized.get("edges"), list):
            normalized["edges"] = []

        normalized_nodes: List[Any] = []
        image_node_index = 0
        for node in normalized.get("nodes", []):
            if not isinstance(node, dict):
                normalized_nodes.append(node)
                continue

            normalized_node = dict(node)
            node_data = normalized_node.get("data")
            if isinstance(node_data, dict):
                normalized_data = dict(node_data)
                node_type = str(
                    normalized_data.get("type")
                    or normalized_node.get("type")
                    or ""
                ).strip().lower().replace("-", "_")
                if node_type == "input_image":
                    current_url = normalized_data.get("startImageUrl")
                    if current_url is None:
                        current_url = normalized_data.get("start_image_url")
                    if is_placeholder_reference_image_url(current_url):
                        fallback_url = pick_reference_image(
                            seed=str(normalized_node.get("id") or ""),
                            index=image_node_index,
                        )
                        if fallback_url:
                            normalized_data["startImageUrl"] = fallback_url
                    image_node_index += 1
                normalized_node["data"] = normalized_data
            normalized_nodes.append(normalized_node)

        normalized["nodes"] = normalized_nodes
        normalized.setdefault("schemaVersion", 2)
        return normalized

    def _extract_tags(self, config: Dict[str, Any]) -> List[str]:
        candidates: List[Any] = []
        meta = config.get("_templateMeta")
        if isinstance(meta, dict):
            candidates.append(meta.get("tags"))

        tags: List[str] = []
        for candidate in candidates:
            if not isinstance(candidate, list):
                continue
            for item in candidate:
                text = str(item).strip()
                if text:
                    tags.append(text)

        dedup: List[str] = []
        seen = set()
        for tag in tags:
            lower = tag.lower()
            if lower in seen:
                continue
            seen.add(lower)
            dedup.append(tag)
        return dedup

    def _inject_template_meta(
        self,
        config: Dict[str, Any],
        workflow_type: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized = self._normalize_config(config)
        existing_meta = normalized.get("_templateMeta")
        if not isinstance(existing_meta, dict):
            existing_meta = {}

        normalized_tags = tags if tags is not None else self._extract_tags(normalized)
        normalized_tags = [str(tag).strip() for tag in normalized_tags if str(tag).strip()]

        normalized["_templateMeta"] = {
            **existing_meta,
            "workflowType": workflow_type or existing_meta.get("workflowType") or "graph",
            "tags": normalized_tags,
        }
        return self._apply_template_analysis_meta(normalized)

    def _extract_starter_key(self, config: Dict[str, Any]) -> Optional[str]:
        meta = config.get("_templateMeta")
        if not isinstance(meta, dict):
            return None
        starter_key = meta.get("starterKey")
        if isinstance(starter_key, str) and starter_key.strip():
            return starter_key.strip()
        return None

    def _extract_template_meta(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(config, dict):
            return {}
        raw_meta = config.get("_templateMeta")
        if not isinstance(raw_meta, dict):
            return {}
        return raw_meta

    def _normalize_name_key(self, name: str) -> str:
        return str(name or "").strip().lower()

    def _normalize_category_name(self, category: Optional[str], default: str = "通用") -> str:
        normalized = str(category or "").strip()
        if normalized:
            return normalized
        return default

    def _normalize_tags(self, tags: Optional[List[Any]]) -> List[str]:
        normalized_tags: List[str] = []
        seen = set()
        for item in tags or []:
            value = str(item or "").strip()
            if not value:
                continue
            dedupe_key = value.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized_tags.append(value)
        return normalized_tags

    def _normalize_task_type(self, value: Any) -> Optional[str]:
        normalized = str(value or "").strip().lower().replace("_", "-")
        if not normalized:
            return None
        normalized = TASK_TYPE_ALIASES.get(normalized, normalized)
        if normalized in SUPPORTED_TEMPLATE_TASK_TYPES:
            return normalized
        return None

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        normalized = str(value or "").strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    def _map_tool_name_to_task_type(self, value: Any) -> Optional[str]:
        normalized = str(value or "").strip().lower().replace("-", "_")
        if not normalized:
            return None
        if normalized in {"image_generate", "generate_image", "image_gen"}:
            return "image-gen"
        if normalized in {"video_generate", "generate_video", "video_gen"}:
            return "video-gen"
        if normalized in {"video_understand", "understand_video"}:
            return "vision-understand"
        if normalized in {
            "image_edit",
            "edit_image",
            "image_chat_edit",
            "image_mask_edit",
            "image_inpainting",
            "image_background_edit",
            "image_recontext",
            "image_outpaint",
            "image_outpainting",
            "expand_image",
        }:
            return "image-edit"
        if normalized in {
            "table_analyze",
            "excel_analyze",
            "analyze_table",
            "sheet_analyze",
            "sheet_profile",
            "sheet_stage_ingest",
            "sheet_stage_profile",
            "sheet_stage_query",
            "sheet_stage_export",
        }:
            return "data-analysis"
        if normalized in {
            "prompt_optimize",
            "prompt_optimizer",
            "optimize_prompt",
            "prompt_rewrite",
            "rewrite_prompt",
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
            return "chat"
        if normalized in {
            "mcp_tool_call",
            "mcp_call",
            "mcp_invoke",
            "video_delete",
            "delete_video",
        }:
            return "data-analysis"
        return None

    def _collect_template_task_types(
        self,
        config: Dict[str, Any],
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        task_types: List[str] = []
        node_task_order: List[str] = []

        def append_task(raw_value: Any, *, is_node_task: bool = False) -> None:
            normalized_task = self._normalize_task_type(raw_value)
            if not normalized_task:
                return
            if normalized_task not in task_types:
                task_types.append(normalized_task)
            if is_node_task and normalized_task not in node_task_order:
                node_task_order.append(normalized_task)

        for node in config.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_data = node.get("data") if isinstance(node.get("data"), dict) else {}
            node_type = str(
                node_data.get("type")
                or node.get("type")
                or ""
            ).strip().lower().replace("-", "_")
            if node_type == "agent":
                append_task(
                    node_data.get("agentTaskType")
                    or node_data.get("agent_task_type")
                    or "",
                    is_node_task=True,
                )
            elif node_type == "tool":
                append_task(
                    self._map_tool_name_to_task_type(
                        node_data.get("toolName") or node_data.get("tool_name")
                    ),
                    is_node_task=True,
                )

        for tag in tags or []:
            append_task(tag, is_node_task=False)

        primary_task_type = node_task_order[0] if node_task_order else (task_types[0] if task_types else None)
        return {
            "task_types": task_types,
            "primary_task_type": primary_task_type,
        }

    def _collect_template_binding_payload(self, config: Dict[str, Any]) -> Dict[str, Any]:
        binding_modes: List[str] = []
        legacy_name_binding_node_ids: List[str] = []

        for node in config.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_data = node.get("data") if isinstance(node.get("data"), dict) else {}
            node_type = str(
                node_data.get("type")
                or node.get("type")
                or ""
            ).strip().lower().replace("-", "_")
            if node_type != "agent":
                continue

            has_agent_id = bool(
                str(node_data.get("agentId") or node_data.get("agent_id") or "").strip()
            )
            has_agent_name = bool(
                str(node_data.get("agentName") or node_data.get("agent_name") or "").strip()
            )
            uses_active_profile = self._coerce_bool(
                node_data.get("inlineUseActiveProfile")
                if node_data.get("inlineUseActiveProfile") is not None
                else node_data.get("inline_use_active_profile")
            )
            has_inline_binding = any(
                str(node_data.get(key) or "").strip()
                for key in (
                    "inlineProviderId",
                    "inline_provider_id",
                    "inlineModelId",
                    "inline_model_id",
                    "inlineProfileId",
                    "inline_profile_id",
                    "inlineSystemPrompt",
                    "inline_system_prompt",
                )
            )

            if uses_active_profile:
                mode = "inline-active-profile"
            elif has_inline_binding:
                mode = "inline-explicit"
            elif has_agent_id:
                mode = "registry-id"
            elif has_agent_name:
                mode = "registry-name"
            else:
                mode = "unbound"

            if mode not in binding_modes:
                binding_modes.append(mode)
            if mode == "registry-name":
                node_id = str(node.get("id") or "").strip()
                if node_id:
                    legacy_name_binding_node_ids.append(node_id)

        effective_modes = [mode for mode in binding_modes if mode != "unbound"]
        if len(effective_modes) > 1:
            binding_strategy = "mixed"
        elif effective_modes:
            binding_strategy = effective_modes[0]
        elif binding_modes:
            binding_strategy = binding_modes[0]
        else:
            binding_strategy = "none"

        return {
            "binding_strategy": binding_strategy,
            "legacy_name_binding_node_ids": legacy_name_binding_node_ids,
        }

    def _build_template_analysis_payload(self, config: Dict[str, Any]) -> Dict[str, Any]:
        meta = self._extract_template_meta(config)
        tags = self._extract_tags(config)
        task_payload = self._collect_template_task_types(config=config, tags=tags)
        binding_payload = self._collect_template_binding_payload(config=config)

        starter_key = self._extract_starter_key(config)
        copied_from_starter_key = str(meta.get("copiedFromStarterKey") or "").strip()
        legacy_name_binding_node_ids = binding_payload["legacy_name_binding_node_ids"]
        is_legacy_starter_copy = bool(
            not starter_key
            and copied_from_starter_key
            and legacy_name_binding_node_ids
        )

        legacy_flags: List[str] = []
        legacy_reason: Optional[str] = None
        if is_legacy_starter_copy:
            legacy_flags.append("starter-copy-agent-name-binding")
            legacy_reason = "Copied from starter and still binds registry agents by agentName."

        return {
            "taskTypes": task_payload["task_types"],
            "primaryTaskType": task_payload["primary_task_type"],
            "bindingStrategy": binding_payload["binding_strategy"],
            "isLegacyStarterCopy": is_legacy_starter_copy,
            "legacyFlags": legacy_flags,
            "legacyReason": legacy_reason,
        }

    def _apply_template_analysis_meta(self, config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_config(config)
        existing_meta = self._extract_template_meta(normalized)
        normalized["_templateMeta"] = {
            **existing_meta,
            **self._build_template_analysis_payload(normalized),
        }
        return normalized

    def _build_template_runtime_scope(
        self,
        starter_key: Optional[str],
        tags: Optional[List[str]],
    ) -> Dict[str, str]:
        normalized_starter_key = str(starter_key or "").strip().lower()
        normalized_tags = {str(tag or "").strip().lower() for tag in (tags or []) if str(tag or "").strip()}

        is_google_runtime = (
            normalized_starter_key.startswith("adk_sample_")
            or "google-adk" in normalized_tags
        )
        if is_google_runtime:
            return {
                "runtime_scope": "google-runtime",
                "runtime_label": "Google runtime",
            }
        return {
            "runtime_scope": "provider-neutral",
            "runtime_label": "Provider-neutral",
        }

    def _sanitize_non_starter_template_config(
        self,
        config: Dict[str, Any],
        workflow_type: str,
        tags: Optional[List[str]] = None,
        copied_from: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = self._inject_template_meta(
            config=config,
            workflow_type=workflow_type,
            tags=tags,
        )
        template_meta = self._extract_template_meta(normalized)
        next_meta = {
            key: value
            for key, value in template_meta.items()
            if key not in {"starterKey", "starterVersion"}
        }

        normalized_tags = self._normalize_tags(
            [
                tag
                for tag in self._extract_tags(normalized)
                if str(tag or "").strip().lower() not in {"starter", "official"}
            ]
        )
        next_meta["workflowType"] = workflow_type or next_meta.get("workflowType") or "graph"
        next_meta["tags"] = normalized_tags

        if isinstance(copied_from, dict):
            copied_starter_key = str(copied_from.get("starter_key") or "").strip()
            copied_template_id = str(copied_from.get("template_id") or "").strip()
            copied_template_name = str(copied_from.get("template_name") or "").strip()
            if copied_starter_key:
                next_meta["copiedFromStarterKey"] = copied_starter_key
            if copied_template_id:
                next_meta["copiedFromTemplateId"] = copied_template_id
            if copied_template_name:
                next_meta["copiedFromTemplateName"] = copied_template_name

        normalized["_templateMeta"] = next_meta
        return self._apply_template_analysis_meta(normalized)

    def _load_template_config(self, template: WorkflowTemplate) -> Dict[str, Any]:
        try:
            config = json.loads(template.config_json or "{}")
        except Exception:
            config = {}
        normalized_config = config if isinstance(config, dict) else {}
        return self._normalize_config(normalized_config)

    def _template_is_starter(self, template: WorkflowTemplate) -> bool:
        return bool(self._extract_starter_key(self._load_template_config(template)))

    def _build_template_origin_payload(
        self,
        template: WorkflowTemplate,
        config: Dict[str, Any],
        tags: List[str],
    ) -> Dict[str, Any]:
        meta = self._extract_template_meta(config)
        starter_key = self._extract_starter_key(config)
        starter_version = None
        if meta.get("starterVersion") is not None:
            try:
                starter_version = int(meta.get("starterVersion"))
            except Exception:
                starter_version = None

        copied_from_starter_key = str(meta.get("copiedFromStarterKey") or "").strip() or None
        is_starter = bool(starter_key)
        if is_starter:
            origin_kind = "starter"
            origin_label = "官方 Starter"
        elif bool(template.is_public):
            origin_kind = "public"
            origin_label = "公开模板"
        else:
            origin_kind = "user"
            origin_label = "我的模板"

        runtime_payload = self._build_template_runtime_scope(starter_key=starter_key, tags=tags)
        return {
            "is_starter": is_starter,
            "starter_key": starter_key or None,
            "starter_version": starter_version,
            "copied_from_starter_key": copied_from_starter_key,
            "origin": {
                "kind": origin_kind,
                "label": origin_label,
                "is_locked": is_starter,
                **runtime_payload,
            },
            "is_editable": not is_starter,
            "is_deletable": not is_starter,
            **runtime_payload,
        }

    def _build_template_sort_key(self, payload: Dict[str, Any]) -> Any:
        origin = payload.get("origin") if isinstance(payload.get("origin"), dict) else {}
        origin_kind = str(origin.get("kind") or "user").strip().lower()
        runtime_scope = str(
            origin.get("runtime_scope")
            or payload.get("runtime_scope")
            or "provider-neutral"
        ).strip().lower()
        category = self._normalize_category_name(payload.get("category"))
        category_rank = {
            self._normalize_name_key(name): index
            for index, name in enumerate(DEFAULT_TEMPLATE_CATEGORIES)
        }.get(self._normalize_name_key(category), 9999)

        has_sample_result = bool(
            payload.get("sample_result")
            or (isinstance(payload.get("sample_result_summary"), dict) and payload["sample_result_summary"].get("hasResult"))
        )
        origin_rank = {
            "user": 0,
            "starter": 1,
            "public": 2,
        }.get(origin_kind, 9)
        runtime_rank = 1 if runtime_scope == "google-runtime" else 0
        legacy_rank = 1 if bool(payload.get("is_legacy_starter_copy")) else 0
        updated_at = int(payload.get("updated_at") or 0)
        name_key = self._normalize_name_key(payload.get("name"))

        return (
            origin_rank,
            runtime_rank,
            legacy_rank,
            0 if has_sample_result else 1,
            category_rank,
            -updated_at,
            name_key,
        )

    def _pick_canonical_starter_entry(
        self,
        entries: List[Dict[str, Any]],
        definition_name: str,
    ) -> Optional[Dict[str, Any]]:
        if not entries:
            return None

        normalized_definition_name = self._normalize_name_key(definition_name)
        return sorted(
            entries,
            key=lambda item: (
                0 if self._normalize_name_key(getattr(item.get("template"), "name", "")) == normalized_definition_name else 1,
                int(getattr(item.get("template"), "created_at", 0) or 0),
                self._normalize_name_key(getattr(item.get("template"), "name", "")),
            ),
        )[0]

    def _demote_duplicate_starter_entry(
        self,
        template: WorkflowTemplate,
        existing_config: Dict[str, Any],
        original_starter_key: str,
        now: int,
    ) -> bool:
        next_config = self._sanitize_non_starter_template_config(
            config=existing_config,
            workflow_type=template.workflow_type or "graph",
            tags=self._extract_tags(existing_config),
            copied_from={
                "starter_key": original_starter_key,
            },
        )
        if next_config == existing_config:
            return False

        template.config_json = json.dumps(next_config, ensure_ascii=False)
        template.updated_at = now
        template.version = int(template.version or 1) + 1
        return True

    def _refresh_template_analysis_metadata(
        self,
        *,
        template: WorkflowTemplate,
        now: int,
    ) -> bool:
        existing_config = self._load_template_config(template)
        next_config = self._apply_template_analysis_meta(existing_config)
        if next_config == existing_config:
            return False

        template.config_json = json.dumps(next_config, ensure_ascii=False)
        template.updated_at = now
        template.version = int(template.version or 1) + 1
        return True

    def _serialize_category(self, category: WorkflowTemplateCategory) -> Dict[str, Any]:
        payload = category.to_dict()
        payload.pop("user_id", None)
        return payload

    def _ensure_category_record(self, user_id: str, category_name: str) -> Optional[WorkflowTemplateCategory]:
        normalized_key = self._normalize_name_key(category_name)
        if not normalized_key:
            return None

        existing = self.db.query(WorkflowTemplateCategory).filter(
            WorkflowTemplateCategory.user_id == user_id,
            func.lower(WorkflowTemplateCategory.name) == normalized_key,
        ).first()
        if existing:
            return existing

        now = int(time.time() * 1000)
        category = WorkflowTemplateCategory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=category_name.strip(),
            created_at=now,
            updated_at=now,
        )
        self.db.add(category)
        return category

    async def ensure_default_categories(self, user_id: str) -> List[Dict[str, Any]]:
        existing = self.db.query(WorkflowTemplateCategory).filter(
            WorkflowTemplateCategory.user_id == user_id
        ).all()
        existing_keys = {self._normalize_name_key(item.name) for item in existing}
        created: List[WorkflowTemplateCategory] = []
        now = int(time.time() * 1000)

        for default_name in DEFAULT_TEMPLATE_CATEGORIES:
            key = self._normalize_name_key(default_name)
            if key in existing_keys:
                continue
            category = WorkflowTemplateCategory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=default_name,
                created_at=now,
                updated_at=now,
            )
            self.db.add(category)
            existing_keys.add(key)
            created.append(category)

        if created:
            self.db.commit()
            for item in created:
                self.db.refresh(item)
            logger.info(
                "[WorkflowTemplateService] Initialized default categories for user %s: %s",
                user_id,
                ", ".join([item.name for item in created]),
            )

        return [self._serialize_category(item) for item in created]

    async def create_category(self, user_id: str, name: str) -> Dict[str, Any]:
        normalized_name = self._normalize_category_name(name, default="")
        if not normalized_name:
            raise ValueError("Category name cannot be empty")

        existing = self.db.query(WorkflowTemplateCategory).filter(
            WorkflowTemplateCategory.user_id == user_id,
            func.lower(WorkflowTemplateCategory.name) == self._normalize_name_key(normalized_name),
        ).first()
        if existing:
            raise ValueError(f"Template category already exists: {normalized_name}")

        now = int(time.time() * 1000)
        category = WorkflowTemplateCategory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=normalized_name,
            created_at=now,
            updated_at=now,
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        logger.info(
            "[WorkflowTemplateService] Created category %s for user %s",
            normalized_name,
            user_id,
        )
        return self._serialize_category(category)

    async def list_categories(
        self,
        user_id: str,
        include_public: bool = True,
        ensure_defaults: bool = True,
    ) -> List[Dict[str, Any]]:
        if ensure_defaults:
            await self.ensure_default_categories(user_id=user_id)

        persisted_categories = self.db.query(WorkflowTemplateCategory).filter(
            WorkflowTemplateCategory.user_id == user_id
        ).all()
        persisted_name_map: Dict[str, WorkflowTemplateCategory] = {
            self._normalize_name_key(item.name): item for item in persisted_categories
        }

        template_category_query = self.db.query(WorkflowTemplate.category)
        if include_public:
            template_category_query = template_category_query.filter(
                (WorkflowTemplate.user_id == user_id) | (WorkflowTemplate.is_public == True)
            )
        else:
            template_category_query = template_category_query.filter(
                WorkflowTemplate.user_id == user_id
            )
        template_category_rows = template_category_query.distinct().all()

        merged_names: Dict[str, str] = {}
        for item in persisted_categories:
            name = self._normalize_category_name(item.name, default="")
            if not name:
                continue
            merged_names[self._normalize_name_key(name)] = name

        for row in template_category_rows:
            raw_value = row[0] if isinstance(row, (tuple, list)) else getattr(row, "category", None)
            name = self._normalize_category_name(raw_value, default="")
            if not name:
                continue
            key = self._normalize_name_key(name)
            if key not in merged_names:
                merged_names[key] = name

        default_rank = {
            self._normalize_name_key(name): index
            for index, name in enumerate(DEFAULT_TEMPLATE_CATEGORIES)
        }
        sorted_names = sorted(
            merged_names.values(),
            key=lambda value: (
                default_rank.get(self._normalize_name_key(value), 9999),
                value,
            ),
        )

        results: List[Dict[str, Any]] = []
        for name in sorted_names:
            key = self._normalize_name_key(name)
            persisted = persisted_name_map.get(key)
            if persisted:
                results.append(self._serialize_category(persisted))
            else:
                results.append({
                    "id": None,
                    "name": name,
                    "created_at": None,
                    "updated_at": None,
                })

        return results

    def _ensure_unique_template_name(
        self,
        user_id: str,
        name: str,
        exclude_template_id: Optional[str] = None,
    ) -> None:
        normalized_name = self._normalize_name_key(name)
        if not normalized_name:
            raise ValueError("Template name cannot be empty")

        query = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.user_id == user_id,
        )
        if exclude_template_id:
            query = query.filter(WorkflowTemplate.id != exclude_template_id)

        for template in query.all():
            if self._normalize_name_key(template.name) == normalized_name:
                raise ValueError(f"Template name already exists: {name}")

    def _validate_template_graph_minimum(self, config: Dict[str, Any]) -> None:
        if not isinstance(config, dict):
            raise ValueError("Template config must be an object")

        nodes = config.get("nodes")
        edges = config.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise ValueError("Template config must contain nodes[] and edges[]")
        if not nodes:
            raise ValueError("Template config nodes cannot be empty")

        node_ids: List[str] = []
        seen = set()
        for node in nodes:
            node_id = str((node or {}).get("id") or "").strip()
            if not node_id:
                raise ValueError("Template config contains node without id")
            if node_id in seen:
                raise ValueError(f"Template config contains duplicate node id: {node_id}")
            seen.add(node_id)
            node_ids.append(node_id)

        node_set = set(node_ids)
        start_count = 0
        end_count = 0
        for node in nodes:
            node_data = (node or {}).get("data") if isinstance(node, dict) else {}
            node_type = ""
            if isinstance(node_data, dict):
                node_type = str(node_data.get("type") or "").strip()
            if not node_type:
                node_type = str((node or {}).get("type") or "").strip()
            normalized_type = node_type.lower().replace("-", "_")
            if normalized_type == "start":
                start_count += 1
            elif normalized_type == "end":
                end_count += 1

        if start_count != 1:
            raise ValueError("Template config must contain exactly one start node")
        if end_count != 1:
            raise ValueError("Template config must contain exactly one end node")

        for edge in edges:
            source = str((edge or {}).get("source") or "").strip()
            target = str((edge or {}).get("target") or "").strip()
            if not source or not target:
                raise ValueError("Template config contains edge without source/target")
            if source not in node_set or target not in node_set:
                raise ValueError(f"Template edge references unknown node: {source} -> {target}")

    def _serialize_template(self, template: WorkflowTemplate) -> Dict[str, Any]:
        payload = template.to_dict()
        config = self._apply_template_analysis_meta(self._normalize_config(payload.get("config")))
        tags = self._extract_tags(config)
        meta = self._extract_template_meta(config)
        sample_result_summary = meta.get("sampleResultSummary")
        if not isinstance(sample_result_summary, dict):
            sample_result_summary = {}
        sample_result_updated_at = None
        if meta.get("sampleResultUpdatedAt") is not None:
            try:
                sample_result_updated_at = int(meta.get("sampleResultUpdatedAt"))
            except Exception:
                sample_result_updated_at = None

        payload["config"] = config
        payload["tags"] = tags
        payload["workflow_type"] = payload.get("workflow_type") or config.get("_templateMeta", {}).get("workflowType") or "graph"
        payload["estimated_node_count"] = len(config.get("nodes", [])) if isinstance(config.get("nodes"), list) else 0
        payload["estimated_edge_count"] = len(config.get("edges", [])) if isinstance(config.get("edges"), list) else 0
        payload["sample_result"] = meta.get("sampleResult")
        payload["sample_result_summary"] = sample_result_summary
        payload["sample_result_updated_at"] = sample_result_updated_at
        payload["sample_execution_id"] = str(meta.get("sampleExecutionId") or "").strip() or None
        payload["sample_input"] = meta.get("sampleInput") if isinstance(meta.get("sampleInput"), dict) else None
        payload["task_types"] = list(meta.get("taskTypes") or []) if isinstance(meta.get("taskTypes"), list) else []
        payload["primary_task_type"] = str(meta.get("primaryTaskType") or "").strip() or None
        payload["binding_strategy"] = str(meta.get("bindingStrategy") or "").strip() or None
        payload["is_legacy_starter_copy"] = bool(meta.get("isLegacyStarterCopy"))
        payload["legacy_flags"] = list(meta.get("legacyFlags") or []) if isinstance(meta.get("legacyFlags"), list) else []
        payload["legacy_reason"] = str(meta.get("legacyReason") or "").strip() or None
        payload.update(self._build_template_origin_payload(template=template, config=config, tags=tags))
        return payload

    async def update_template_sample_result(
        self,
        *,
        user_id: str,
        template_id: str,
        result_payload: Any,
        result_summary: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_template_id = str(template_id or "").strip()
        if not normalized_template_id:
            raise ValueError("template_id is required")

        template = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == normalized_template_id,
            WorkflowTemplate.user_id == user_id,
        ).first()
        if not template:
            return None

        now = int(time.time() * 1000)
        try:
            existing_config = json.loads(template.config_json or "{}")
        except Exception:
            existing_config = {}
        normalized_config = self._normalize_config(existing_config if isinstance(existing_config, dict) else {})
        template_meta = self._extract_template_meta(normalized_config)
        normalized_summary = result_summary if isinstance(result_summary, dict) else {}

        next_meta = {
            **template_meta,
            "sampleResult": result_payload,
            "sampleResultSummary": normalized_summary,
            "sampleResultUpdatedAt": now,
        }
        if isinstance(input_payload, dict):
            next_meta["sampleInput"] = input_payload
        if execution_id:
            next_meta["sampleExecutionId"] = str(execution_id).strip()

        normalized_config["_templateMeta"] = next_meta
        template.config_json = json.dumps(normalized_config, ensure_ascii=False)
        template.updated_at = now
        template.version = int(template.version or 1) + 1

        self.db.commit()
        self.db.refresh(template)
        logger.info(
            "[WorkflowTemplateService] Updated sample result for template %s (user=%s, execution=%s)",
            normalized_template_id,
            user_id,
            execution_id or "",
        )
        return self._serialize_template(template)

    async def ensure_starter_templates(self, user_id: str) -> List[Dict[str, Any]]:
        def _safe_version(value: Any, default: int = 1) -> int:
            try:
                return int(value)
            except Exception:
                return default

        existing_templates = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.user_id == user_id
        ).all()

        existing_starter_templates: Dict[str, List[Dict[str, Any]]] = {}
        existing_templates_by_name: Dict[str, WorkflowTemplate] = {}
        existing_names = set()
        for template in existing_templates:
            normalized_name = (template.name or "").strip().lower()
            existing_names.add(normalized_name)
            if normalized_name:
                existing_templates_by_name[normalized_name] = template
            try:
                config = json.loads(template.config_json or "{}")
            except Exception:
                config = {}
            normalized_config = config if isinstance(config, dict) else {}
            starter_key = self._extract_starter_key(normalized_config)
            if starter_key:
                meta = normalized_config.get("_templateMeta") if isinstance(normalized_config.get("_templateMeta"), dict) else {}
                starter_version = _safe_version(meta.get("starterVersion"), default=1)
                existing_starter_templates.setdefault(starter_key, []).append({
                    "template": template,
                    "config": normalized_config,
                    "starter_version": starter_version,
                })

        now = int(time.time() * 1000)
        created_templates: List[WorkflowTemplate] = []
        updated_count = 0

        for definition in STARTER_TEMPLATE_DEFINITIONS:
            starter_key = definition["starter_key"]
            starter_version = _safe_version(definition.get("starter_version"), default=1)
            normalized_name = str(definition["name"]).strip().lower()
            config = self._inject_template_meta(
                config=definition["config"],
                workflow_type=definition.get("workflow_type", "graph"),
                tags=definition.get("tags", []),
            )
            template_meta = config.get("_templateMeta") if isinstance(config.get("_templateMeta"), dict) else {}
            raw_sample_input = definition.get("sample_input")
            sample_input = raw_sample_input if isinstance(raw_sample_input, dict) else None
            config["_templateMeta"] = {
                **template_meta,
                "starterKey": starter_key,
                "starterVersion": starter_version,
                **({"sampleInput": sample_input} if sample_input else {}),
            }

            existing_entries = existing_starter_templates.get(starter_key) or []
            canonical_entry = self._pick_canonical_starter_entry(
                existing_entries,
                definition_name=definition["name"],
            )
            duplicate_entries = [
                entry for entry in existing_entries
                if canonical_entry is not None and entry is not canonical_entry
            ]
            for duplicate_entry in duplicate_entries:
                if self._demote_duplicate_starter_entry(
                    template=duplicate_entry["template"],
                    existing_config=duplicate_entry["config"],
                    original_starter_key=starter_key,
                    now=now,
                ):
                    updated_count += 1
            existing_entry = canonical_entry
            if existing_entry:
                existing_version = _safe_version(existing_entry.get("starter_version"), default=1)
                if existing_version >= starter_version:
                    continue

                target_template: WorkflowTemplate = existing_entry["template"]
                target_template.name = definition["name"]
                target_template.description = definition.get("description")
                target_template.category = definition.get("category", "general")
                target_template.workflow_type = definition.get("workflow_type", "graph")
                target_template.config_json = json.dumps(config, ensure_ascii=False)
                target_template.updated_at = now
                target_template.version = int(target_template.version or 1) + 1
                updated_count += 1
                continue

            if normalized_name and normalized_name in existing_names:
                matched_template = existing_templates_by_name.get(normalized_name)
                if not matched_template:
                    continue

                try:
                    matched_config = json.loads(matched_template.config_json or "{}")
                except Exception:
                    matched_config = {}
                normalized_matched_config = matched_config if isinstance(matched_config, dict) else {}
                matched_meta = (
                    normalized_matched_config.get("_templateMeta")
                    if isinstance(normalized_matched_config.get("_templateMeta"), dict)
                    else {}
                )
                matched_starter_key = str(matched_meta.get("starterKey") or "").strip()
                if matched_starter_key:
                    continue

                # Backfill starter metadata for old templates created before starterKey was introduced.
                backfilled_config_source = normalized_matched_config if normalized_matched_config else definition["config"]
                backfilled_config = self._inject_template_meta(
                    config=backfilled_config_source,
                    workflow_type=matched_template.workflow_type or definition.get("workflow_type", "graph"),
                    tags=definition.get("tags", []),
                )
                backfilled_meta = (
                    backfilled_config.get("_templateMeta")
                    if isinstance(backfilled_config.get("_templateMeta"), dict)
                    else {}
                )
                raw_sample_input = definition.get("sample_input")
                sample_input = raw_sample_input if isinstance(raw_sample_input, dict) else None
                backfilled_config["_templateMeta"] = {
                    **backfilled_meta,
                    "starterKey": starter_key,
                    "starterVersion": starter_version,
                    **({"sampleInput": sample_input} if sample_input else {}),
                }

                matched_template.config_json = json.dumps(backfilled_config, ensure_ascii=False)
                matched_template.updated_at = now
                matched_template.version = int(matched_template.version or 1) + 1
                updated_count += 1
                continue

            created_templates.append(WorkflowTemplate(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=definition["name"],
                description=definition.get("description"),
                category=definition.get("category", "general"),
                workflow_type=definition.get("workflow_type", "graph"),
                config_json=json.dumps(config, ensure_ascii=False),
                is_public=False,
                version=1,
                created_at=now,
                updated_at=now,
            ))
            if normalized_name:
                existing_names.add(normalized_name)

        analysis_updated_count = 0
        for template in existing_templates:
            if self._refresh_template_analysis_metadata(template=template, now=now):
                analysis_updated_count += 1

        if not created_templates and updated_count == 0 and analysis_updated_count == 0:
            return []

        for template in created_templates:
            self.db.add(template)
        self.db.commit()
        for template in created_templates:
            self.db.refresh(template)

        logger.info(
            f"[WorkflowTemplateService] Synced starter templates for user {user_id}: "
            f"created={len(created_templates)}, updated={updated_count}, analysis_updated={analysis_updated_count}"
        )
        return [self._serialize_template(template) for template in created_templates]
    
    async def create_template(
        self,
        user_id: str,
        name: str,
        category: str,
        workflow_type: str,
        config: Dict[str, Any],
        tags: Optional[List[str]] = None,
        description: Optional[str] = None,
        is_public: bool = False
    ) -> Dict[str, Any]:
        """
        创建工作流模板
        
        Args:
            user_id: 用户 ID
            name: 模板名称
            category: 模板分类（image-edit, excel-analysis, general等）
            workflow_type: 工作流类型（sequential, parallel, coordinator）
            config: 工作流配置（节点、边、参数等）
            description: 模板描述（可选）
            is_public: 是否公开（可选，默认 False）
            
        Returns:
            创建的模板信息
        """
        now = int(time.time() * 1000)
        template_id = str(uuid.uuid4())
        normalized_name = str(name or "").strip()
        self._ensure_unique_template_name(user_id=user_id, name=normalized_name)
        self._validate_template_graph_minimum(config)

        normalized_config = self._sanitize_non_starter_template_config(
            config=config,
            workflow_type=workflow_type or "graph",
            tags=tags,
        )

        normalized_category = self._normalize_category_name(category)
        self._ensure_category_record(user_id=user_id, category_name=normalized_category)

        template = WorkflowTemplate(
            id=template_id,
            user_id=user_id,
            name=normalized_name,
            description=description,
            category=normalized_category,
            workflow_type=workflow_type or "graph",
            config_json=json.dumps(normalized_config),
            is_public=is_public,
            version=1,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"[WorkflowTemplateService] Created template {template_id} for user {user_id}")
        return self._serialize_template(template)
    
    async def update_template(
        self,
        user_id: str,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        workflow_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        is_public: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        更新工作流模板
        
        Args:
            user_id: 用户 ID
            template_id: 模板 ID
            name: 模板名称（可选）
            description: 模板描述（可选）
            category: 模板分类（可选）
            workflow_type: 工作流类型（可选）
            config: 工作流配置（可选）
            is_public: 是否公开（可选）
            
        Returns:
            更新后的模板信息
        """
        template = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.user_id == user_id
        ).first()
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        if self._template_is_starter(template):
            raise ValueError("Starter template is read-only. Please copy it before editing.")

        now = int(time.time() * 1000)
        
        if name is not None:
            normalized_name = str(name or "").strip()
            self._ensure_unique_template_name(
                user_id=user_id,
                name=normalized_name,
                exclude_template_id=template_id,
            )
            template.name = normalized_name
        if description is not None:
            template.description = description
        if category is not None:
            normalized_category = self._normalize_category_name(category)
            template.category = normalized_category
            self._ensure_category_record(user_id=user_id, category_name=normalized_category)
        if workflow_type is not None:
            template.workflow_type = workflow_type
        if config is not None or tags is not None:
            current_config = {}
            try:
                current_config = json.loads(template.config_json or "{}")
            except Exception:
                current_config = {}
            next_config = config if config is not None else current_config
            if config is not None:
                self._validate_template_graph_minimum(next_config if isinstance(next_config, dict) else {})
            merged_config = self._sanitize_non_starter_template_config(
                config=next_config,
                workflow_type=workflow_type or template.workflow_type or "graph",
                tags=tags,
            )
            template.config_json = json.dumps(merged_config)
        if is_public is not None:
            template.is_public = is_public
        
        template.updated_at = now
        template.version += 1
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"[WorkflowTemplateService] Updated template {template_id}")
        return self._serialize_template(template)
    
    async def get_template(
        self,
        template_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取工作流模板
        
        Args:
            template_id: 模板 ID
            user_id: 用户 ID（可选，用于权限检查）
            
        Returns:
            模板信息，如果不存在则返回 None
        """
        query = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        )
        
        # 如果提供了 user_id，检查权限（用户自己的模板或公开模板）
        if user_id:
            query = query.filter(
                (WorkflowTemplate.user_id == user_id) | (WorkflowTemplate.is_public == True)
            )
        
        template = query.first()
        
        if template:
            return self._serialize_template(template)
        return None
    
    async def list_templates(
        self,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        workflow_type: Optional[str] = None,
        search: Optional[str] = None,
        include_public: bool = True
    ) -> List[Dict[str, Any]]:
        """
        列出工作流模板
        
        Args:
            user_id: 用户 ID（可选，如果提供则只返回该用户的模板和公开模板）
            category: 模板分类过滤（可选）
            workflow_type: 工作流类型过滤（可选）
            search: 搜索关键词（可选，搜索名称和描述）
            include_public: 是否包含公开模板（默认 True）
            
        Returns:
            模板列表
        """
        query = self.db.query(WorkflowTemplate)
        
        # 用户过滤
        if user_id:
            if include_public:
                query = query.filter(
                    (WorkflowTemplate.user_id == user_id) | (WorkflowTemplate.is_public == True)
                )
            else:
                query = query.filter(WorkflowTemplate.user_id == user_id)
        elif not include_public:
            # 如果没有 user_id 且不包含公开模板，返回空列表
            return []
        
        # 分类过滤
        if category:
            query = query.filter(WorkflowTemplate.category == category)
        
        # 工作流类型过滤
        if workflow_type:
            query = query.filter(WorkflowTemplate.workflow_type == workflow_type)
        
        # 搜索过滤
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (WorkflowTemplate.name.like(search_pattern)) |
                (WorkflowTemplate.description.like(search_pattern))
            )
        
        templates = query.order_by(WorkflowTemplate.created_at.desc()).all()
        serialized_templates = [self._serialize_template(template) for template in templates]
        serialized_templates.sort(key=self._build_template_sort_key)
        return serialized_templates

    def _generate_available_copy_name(self, user_id: str, base_name: str) -> str:
        normalized_base = str(base_name or "").strip()
        if not normalized_base:
            normalized_base = "模板副本"

        try_name = normalized_base
        suffix = 2
        while True:
            try:
                self._ensure_unique_template_name(user_id=user_id, name=try_name)
                return try_name
            except ValueError:
                try_name = f"{normalized_base} {suffix}"
                suffix += 1

    async def copy_template(
        self,
        user_id: str,
        template_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_template_id = str(template_id or "").strip()
        if not normalized_template_id:
            raise ValueError("template_id is required")

        source_template = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == normalized_template_id,
            (WorkflowTemplate.user_id == user_id) | (WorkflowTemplate.is_public == True),
        ).first()
        if not source_template:
            raise ValueError(f"Template not found: {normalized_template_id}")

        source_name = str(source_template.name or "").strip() or "模板"
        requested_name = str(name or "").strip()
        base_name = requested_name or f"{source_name} 副本"
        target_name = self._generate_available_copy_name(user_id=user_id, base_name=base_name)

        normalized_config: Dict[str, Any] = {}
        try:
            normalized_config = self._normalize_config(json.loads(source_template.config_json or "{}"))
        except Exception:
            normalized_config = self._normalize_config({})
        normalized_config = self._sanitize_non_starter_template_config(
            config=normalized_config,
            workflow_type=source_template.workflow_type or "graph",
            tags=self._extract_tags(normalized_config),
            copied_from={
                "template_id": source_template.id,
                "template_name": source_template.name,
                "starter_key": self._extract_starter_key(normalized_config),
            },
        )

        now = int(time.time() * 1000)
        copied_template = WorkflowTemplate(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=target_name,
            description=source_template.description,
            category=source_template.category,
            workflow_type=source_template.workflow_type or "graph",
            config_json=json.dumps(normalized_config, ensure_ascii=False),
            is_public=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.db.add(copied_template)
        self.db.commit()
        self.db.refresh(copied_template)
        logger.info(
            "[WorkflowTemplateService] Copied template %s -> %s for user %s",
            normalized_template_id,
            copied_template.id,
            user_id,
        )
        return self._serialize_template(copied_template)
    
    async def delete_template(
        self,
        user_id: str,
        template_id: str
    ) -> bool:
        """
        删除工作流模板
        
        Args:
            user_id: 用户 ID
            template_id: 模板 ID
            
        Returns:
            是否删除成功
        """
        template = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.user_id == user_id
        ).first()
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        if self._template_is_starter(template):
            raise ValueError("Starter template is read-only. Please copy it before deleting.")

        self.db.delete(template)
        self.db.commit()
        
        logger.info(f"[WorkflowTemplateService] Deleted template {template_id}")
        return True
