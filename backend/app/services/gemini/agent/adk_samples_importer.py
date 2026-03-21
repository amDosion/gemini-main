"""
ADK Samples Template Importer - 从 GitHub adk-samples 导入模板

目标：
- 将 ADK 样例映射为本系统可直接执行的 graph 工作流；
- 模板统一使用 start/input/agent/parallel/merge/end 组件；
- 节点绑定现有 seed agentName，导入时会按需补齐统一 seed 集。
"""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ....models.db_models import WorkflowTemplate
from ...agent.agent_seed_service import ensure_seed_agents, get_default_seed_agents

logger = logging.getLogger(__name__)

# ADK Samples GitHub 仓库信息
ADK_SAMPLES_REPO = "google/adk-samples"
ADK_SAMPLES_BASE_URL = f"https://api.github.com/repos/{ADK_SAMPLES_REPO}"


def _node(node_id: str, node_type: str, x: int, y: int, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": x, "y": y},
        "data": {"type": node_type, **(data or {})},
    }


def _edge(edge_id: str, source: str, target: str) -> Dict[str, Any]:
    return {"id": edge_id, "source": source, "target": target}


def _build_marketing_agency_config() -> Dict[str, Any]:
    nodes = [
        _node(
            "start-marketing",
            "start",
            80,
            220,
            {
                "label": "开始",
                "description": "输入图生图营销任务",
                "icon": "🚀",
                "iconColor": "bg-blue-500",
            },
        ),
        _node(
            "input-image-marketing",
            "input_image",
            300,
            220,
            {
                "label": "参考图输入",
                "description": "上传产品原图（图生图必填）",
                "icon": "🖼️",
                "iconColor": "bg-lime-500",
                "startImageUrl": "",
            },
        ),
        _node(
            "input-text-marketing",
            "input_text",
            520,
            220,
            {
                "label": "营销目标",
                "description": "输入场景、文案语气、卖点重点",
                "icon": "📝",
                "iconColor": "bg-emerald-500",
                "startTask": "",
            },
        ),
        _node(
            "agent-plan-marketing",
            "agent",
            760,
            220,
            {
                "label": "编辑规划",
                "description": "理解原图并输出多路编辑策略",
                "icon": "🧠",
                "iconColor": "bg-violet-500",
                "agentName": "图片编辑优化师",
                "agentTaskType": "image-edit",
                "agentReferenceImageUrl": "{{input-image-marketing.output.imageUrl}}",
                "inputMapping": "目标：{{input-text-marketing.output.text}}\n参考图：{{input-image-marketing.output.imageUrl}}\n\n请输出三路图生图策略：模特图、场景图、卖点文案图。",
                "instructions": "只给出可执行编辑规划，强调主体一致性与电商可用性。",
            },
        ),
        _node(
            "parallel-marketing",
            "parallel",
            1000,
            220,
            {
                "label": "并行产图",
                "description": "并行生成多种营销图片",
                "icon": "⚡",
                "iconColor": "bg-yellow-500",
                "joinMode": "wait_all",
            },
        ),
        _node(
            "agent-model-marketing",
            "agent",
            1240,
            80,
            {
                "label": "模特图分支",
                "description": "基于参考图生成模特展示图",
                "icon": "🧍",
                "iconColor": "bg-fuchsia-500",
                "agentName": "图片编辑优化师",
                "agentTaskType": "image-edit",
                "agentReferenceImageUrl": "{{input-image-marketing.output.imageUrl}}",
                "agentNumberOfImages": 2,
                "agentOutputLanguage": "en",
                "inputMapping": "编辑规划：{{agent-plan-marketing.output.text}}\n请执行模特图分支，输出英文卖点文案且不遮挡主体。",
                "instructions": "必须保持产品主体一致；文本布局避开主体关键区域。",
            },
        ),
        _node(
            "agent-scene-marketing",
            "agent",
            1240,
            220,
            {
                "label": "场景图分支",
                "description": "生成真实使用场景营销图",
                "icon": "🏞️",
                "iconColor": "bg-indigo-500",
                "agentName": "图片编辑优化师",
                "agentTaskType": "image-edit",
                "agentReferenceImageUrl": "{{input-image-marketing.output.imageUrl}}",
                "agentNumberOfImages": 2,
                "agentOutputLanguage": "en",
                "inputMapping": "编辑规划：{{agent-plan-marketing.output.text}}\n请执行场景图分支，场景自然、卖点清晰。",
            },
        ),
        _node(
            "agent-sellpoint-marketing",
            "agent",
            1240,
            360,
            {
                "label": "卖点图分支",
                "description": "生成带排版卖点文案图",
                "icon": "💡",
                "iconColor": "bg-amber-500",
                "agentName": "图片编辑优化师",
                "agentTaskType": "image-edit",
                "agentReferenceImageUrl": "{{input-image-marketing.output.imageUrl}}",
                "agentNumberOfImages": 2,
                "agentOutputLanguage": "en",
                "inputMapping": "编辑规划：{{agent-plan-marketing.output.text}}\n请执行卖点图分支，英文文案排版需避开主体。",
                "instructions": "卖点标题+短描述，信息层次清晰，避免文字遮挡产品主体。",
            },
        ),
        _node(
            "merge-marketing",
            "merge",
            1480,
            220,
            {
                "label": "结果汇总",
                "description": "汇总并行产图结果",
                "icon": "🔗",
                "iconColor": "bg-gray-500",
                "mergeStrategy": "append",
            },
        ),
        _node(
            "agent-qa-marketing",
            "agent",
            1720,
            220,
            {
                "label": "质量终审",
                "description": "输出可交付版本与迭代建议",
                "icon": "✅",
                "iconColor": "bg-emerald-500",
                "agentName": "图片编辑优化师",
                "inputMapping": "汇总结果：{{merge-marketing.output.text}}",
                "instructions": "输出最终交付清单（各分支推荐图、风险点、可选迭代提示词）。",
            },
        ),
        _node(
            "end-marketing",
            "end",
            1960,
            220,
            {
                "label": "结束",
                "description": "输出营销图交付结果",
                "icon": "🏁",
                "iconColor": "bg-green-500",
            },
        ),
    ]
    edges = [
        _edge("mk-e1", "start-marketing", "input-image-marketing"),
        _edge("mk-e2", "input-image-marketing", "input-text-marketing"),
        _edge("mk-e3", "input-text-marketing", "agent-plan-marketing"),
        _edge("mk-e4", "agent-plan-marketing", "parallel-marketing"),
        _edge("mk-e5", "parallel-marketing", "agent-model-marketing"),
        _edge("mk-e6", "parallel-marketing", "agent-scene-marketing"),
        _edge("mk-e7", "parallel-marketing", "agent-sellpoint-marketing"),
        _edge("mk-e8", "agent-model-marketing", "merge-marketing"),
        _edge("mk-e9", "agent-scene-marketing", "merge-marketing"),
        _edge("mk-e10", "agent-sellpoint-marketing", "merge-marketing"),
        _edge("mk-e11", "merge-marketing", "agent-qa-marketing"),
        _edge("mk-e12", "agent-qa-marketing", "end-marketing"),
    ]
    return {"schemaVersion": 2, "nodes": nodes, "edges": edges}


def _build_data_engineering_config() -> Dict[str, Any]:
    nodes = [
        _node(
            "start-data",
            "start",
            80,
            240,
            {"label": "开始", "description": "输入分析目标", "icon": "🚀", "iconColor": "bg-blue-500"},
        ),
        _node(
            "input-file-data",
            "input_file",
            300,
            240,
            {
                "label": "报表文件",
                "description": "上传 Excel/CSV 数据文件",
                "icon": "📎",
                "iconColor": "bg-cyan-500",
                "startFileUrl": "",
            },
        ),
        _node(
            "input-text-data",
            "input_text",
            520,
            240,
            {
                "label": "分析目标",
                "description": "例如：控 ACoS + 找增量词",
                "icon": "📝",
                "iconColor": "bg-emerald-500",
                "startTask": "",
            },
        ),
        _node(
            "agent-parse-data",
            "agent",
            760,
            240,
            {
                "label": "数据解析底稿",
                "description": "识别字段并输出标准化分析底稿",
                "icon": "🧩",
                "iconColor": "bg-indigo-500",
                "agentName": "数据报表分析师",
                "agentTaskType": "data-analysis",
                "agentFileUrl": "{{input-file-data.output.fileUrl}}",
                "inputMapping": "目标：{{input-text-data.output.text}}\n文件：{{input-file-data.output.fileUrl}}",
                "instructions": "自动识别表头和字段别名，统一映射并输出底稿。",
            },
        ),
        _node(
            "parallel-data",
            "parallel",
            1000,
            240,
            {
                "label": "并行复核",
                "description": "多 Agent 并行复核策略",
                "icon": "⚡",
                "iconColor": "bg-yellow-500",
                "joinMode": "wait_all",
            },
        ),
        _node(
            "agent-quality-data",
            "agent",
            1240,
            80,
            {
                "label": "数据质量复核",
                "description": "核对字段映射与统计口径",
                "icon": "📈",
                "iconColor": "bg-cyan-500",
                "agentName": "数据报表分析师",
                "inputMapping": "底稿：{{agent-parse-data.output.text}}",
                "instructions": "输出数据可靠性评分、异常和样本风险。",
            },
        ),
        _node(
            "agent-ads-data",
            "agent",
            1240,
            240,
            {
                "label": "广告动作复核",
                "description": "审阅否定词/加投词与预算建议",
                "icon": "📊",
                "iconColor": "bg-blue-500",
                "agentName": "亚马逊广告分析师",
                "inputMapping": "底稿：{{agent-parse-data.output.text}}\n目标：{{input-text-data.output.text}}",
            },
        ),
        _node(
            "agent-strategy-data",
            "agent",
            1240,
            400,
            {
                "label": "经营策略复核",
                "description": "结合目标给出执行节奏",
                "icon": "🧮",
                "iconColor": "bg-violet-500",
                "agentName": "运营策略顾问",
                "inputMapping": "底稿：{{agent-parse-data.output.text}}\n目标：{{input-text-data.output.text}}",
            },
        ),
        _node(
            "merge-data",
            "merge",
            1480,
            240,
            {
                "label": "复核汇总",
                "description": "汇总并行复核结果",
                "icon": "🔗",
                "iconColor": "bg-gray-500",
                "mergeStrategy": "append",
            },
        ),
        _node(
            "agent-final-data",
            "agent",
            1720,
            240,
            {
                "label": "最终决策报告",
                "description": "输出可执行动作 + 阈值 + 回滚条件",
                "icon": "✅",
                "iconColor": "bg-emerald-500",
                "agentName": "运营策略顾问",
                "inputMapping": "并行汇总：{{merge-data.output.text}}",
                "instructions": "输出可执行清单：否定词、加投词、预算动作、风险阈值。",
            },
        ),
        _node(
            "end-data",
            "end",
            1960,
            240,
            {"label": "结束", "description": "输出分析结果", "icon": "🏁", "iconColor": "bg-green-500"},
        ),
    ]
    edges = [
        _edge("de-e1", "start-data", "input-file-data"),
        _edge("de-e2", "input-file-data", "input-text-data"),
        _edge("de-e3", "input-text-data", "agent-parse-data"),
        _edge("de-e4", "agent-parse-data", "parallel-data"),
        _edge("de-e5", "parallel-data", "agent-quality-data"),
        _edge("de-e6", "parallel-data", "agent-ads-data"),
        _edge("de-e7", "parallel-data", "agent-strategy-data"),
        _edge("de-e8", "agent-quality-data", "merge-data"),
        _edge("de-e9", "agent-ads-data", "merge-data"),
        _edge("de-e10", "agent-strategy-data", "merge-data"),
        _edge("de-e11", "merge-data", "agent-final-data"),
        _edge("de-e12", "agent-final-data", "end-data"),
    ]
    return {"schemaVersion": 2, "nodes": nodes, "edges": edges}


def _build_customer_service_config() -> Dict[str, Any]:
    nodes = [
        _node("start-cs", "start", 80, 220, {"label": "开始", "description": "输入客户任务", "icon": "🚀", "iconColor": "bg-blue-500"}),
        _node(
            "input-cs",
            "input_text",
            300,
            220,
            {"label": "客户需求", "description": "输入客服问题和约束", "icon": "📝", "iconColor": "bg-emerald-500", "startTask": ""},
        ),
        _node(
            "parallel-cs",
            "parallel",
            540,
            220,
            {"label": "并行会诊", "description": "并行评估问题与风险", "icon": "⚡", "iconColor": "bg-yellow-500", "joinMode": "wait_all"},
        ),
        _node(
            "agent-copy-cs",
            "agent",
            780,
            80,
            {"label": "回复草稿", "description": "产出结构化回复草稿", "icon": "✍️", "iconColor": "bg-pink-500", "agentName": "电商文案创作师", "inputMapping": "需求：{{input-cs.output.text}}"},
        ),
        _node(
            "agent-policy-cs",
            "agent",
            780,
            220,
            {"label": "合规检查", "description": "检查政策风险与措辞边界", "icon": "🛡️", "iconColor": "bg-sky-500", "agentName": "亚马逊合规审核师", "inputMapping": "需求：{{input-cs.output.text}}"},
        ),
        _node(
            "agent-strategy-cs",
            "agent",
            780,
            360,
            {"label": "策略建议", "description": "给出沟通与升级策略", "icon": "🧠", "iconColor": "bg-indigo-500", "agentName": "运营策略顾问", "inputMapping": "需求：{{input-cs.output.text}}"},
        ),
        _node(
            "merge-cs",
            "merge",
            1020,
            220,
            {"label": "汇总", "description": "汇总并行结果", "icon": "🔗", "iconColor": "bg-gray-500", "mergeStrategy": "append"},
        ),
        _node(
            "agent-final-cs",
            "agent",
            1260,
            220,
            {
                "label": "最终答复",
                "description": "输出可发送版本与后续动作",
                "icon": "✅",
                "iconColor": "bg-emerald-500",
                "agentName": "电商文案创作师",
                "inputMapping": "汇总：{{merge-cs.output.text}}",
                "instructions": "输出最终客户回复、内部处理步骤和升级条件。",
            },
        ),
        _node("end-cs", "end", 1500, 220, {"label": "结束", "description": "输出客服方案", "icon": "🏁", "iconColor": "bg-green-500"}),
    ]
    edges = [
        _edge("cs-e1", "start-cs", "input-cs"),
        _edge("cs-e2", "input-cs", "parallel-cs"),
        _edge("cs-e3", "parallel-cs", "agent-copy-cs"),
        _edge("cs-e4", "parallel-cs", "agent-policy-cs"),
        _edge("cs-e5", "parallel-cs", "agent-strategy-cs"),
        _edge("cs-e6", "agent-copy-cs", "merge-cs"),
        _edge("cs-e7", "agent-policy-cs", "merge-cs"),
        _edge("cs-e8", "agent-strategy-cs", "merge-cs"),
        _edge("cs-e9", "merge-cs", "agent-final-cs"),
        _edge("cs-e10", "agent-final-cs", "end-cs"),
    ]
    return {"schemaVersion": 2, "nodes": nodes, "edges": edges}


def _build_camel_config() -> Dict[str, Any]:
    nodes = [
        _node("start-camel", "start", 80, 240, {"label": "开始", "description": "输入综合任务", "icon": "🚀", "iconColor": "bg-blue-500"}),
        _node(
            "input-camel",
            "input_text",
            300,
            240,
            {"label": "任务文本", "description": "输入电商运营复合任务", "icon": "📝", "iconColor": "bg-emerald-500", "startTask": ""},
        ),
        _node(
            "agent-decompose-camel",
            "agent",
            540,
            240,
            {
                "label": "任务分解",
                "description": "拆分为关键词/Listing/投放子任务",
                "icon": "🧩",
                "iconColor": "bg-violet-500",
                "agentName": "多店铺运营整合师",
                "instructions": "将任务拆解为可并行执行的子任务，并明确目标与约束。",
            },
        ),
        _node(
            "parallel-camel",
            "parallel",
            780,
            240,
            {"label": "并行执行", "description": "多专家并行处理", "icon": "⚡", "iconColor": "bg-yellow-500", "joinMode": "wait_all"},
        ),
        _node("agent-keyword-camel", "agent", 1020, 80, {"label": "关键词子任务", "description": "提炼关键词策略", "icon": "🔑", "iconColor": "bg-amber-500", "agentName": "关键词研究专家", "inputMapping": "分解结果：{{agent-decompose-camel.output.text}}"}),
        _node("agent-listing-camel", "agent", 1020, 240, {"label": "Listing 子任务", "description": "生成标题/五点/描述", "icon": "✍️", "iconColor": "bg-emerald-500", "agentName": "Listing优化专家", "inputMapping": "分解结果：{{agent-decompose-camel.output.text}}"}),
        _node("agent-ads-camel", "agent", 1020, 400, {"label": "投放子任务", "description": "产出广告动作建议", "icon": "📊", "iconColor": "bg-blue-500", "agentName": "亚马逊广告分析师", "inputMapping": "分解结果：{{agent-decompose-camel.output.text}}"}),
        _node("merge-camel", "merge", 1260, 240, {"label": "汇总结果", "description": "汇总并行子任务结果", "icon": "🔗", "iconColor": "bg-gray-500", "mergeStrategy": "append"}),
        _node(
            "agent-final-camel",
            "agent",
            1500,
            240,
            {
                "label": "统一执行方案",
                "description": "输出统一节奏与落地计划",
                "icon": "✅",
                "iconColor": "bg-emerald-500",
                "agentName": "运营策略顾问",
                "inputMapping": "并行汇总：{{merge-camel.output.text}}",
                "instructions": "输出周计划：任务优先级、执行顺序、风险回滚。",
            },
        ),
        _node("end-camel", "end", 1740, 240, {"label": "结束", "description": "输出综合方案", "icon": "🏁", "iconColor": "bg-green-500"}),
    ]
    edges = [
        _edge("cm-e1", "start-camel", "input-camel"),
        _edge("cm-e2", "input-camel", "agent-decompose-camel"),
        _edge("cm-e3", "agent-decompose-camel", "parallel-camel"),
        _edge("cm-e4", "parallel-camel", "agent-keyword-camel"),
        _edge("cm-e5", "parallel-camel", "agent-listing-camel"),
        _edge("cm-e6", "parallel-camel", "agent-ads-camel"),
        _edge("cm-e7", "agent-keyword-camel", "merge-camel"),
        _edge("cm-e8", "agent-listing-camel", "merge-camel"),
        _edge("cm-e9", "agent-ads-camel", "merge-camel"),
        _edge("cm-e10", "merge-camel", "agent-final-camel"),
        _edge("cm-e11", "agent-final-camel", "end-camel"),
    ]
    return {"schemaVersion": 2, "nodes": nodes, "edges": edges}


# 预定义 ADK samples 模板映射（已转换为本系统可执行 graph）
ADK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "marketing-agency": {
        "name": "ADK Marketing Agency (Executable)",
        "description": "图生图营销生产流（理解 → 并行产图 → 终审），对齐 ADK Marketing Agency 思路。",
        "category": "图像工作流",
        "workflow_type": "graph",
        "path": "python/agents/marketing-agency",
        "config_builder": _build_marketing_agency_config,
    },
    "data-engineering": {
        "name": "ADK Data Engineering (Executable)",
        "description": "数据分析执行流（解析 → 并行复核 → 决策输出），对齐 ADK Data Engineering 思路。",
        "category": "数据分析",
        "workflow_type": "graph",
        "path": "python/agents/data-engineering",
        "config_builder": _build_data_engineering_config,
    },
    "customer-service": {
        "name": "ADK Customer Service (Executable)",
        "description": "客服协同流（并行会诊 → 答复生成），对齐 ADK Coordinator/Dispatcher 思路。",
        "category": "运营协同",
        "workflow_type": "graph",
        "path": "python/agents/customer-service",
        "config_builder": _build_customer_service_config,
    },
    "camel": {
        "name": "ADK CAMEL (Executable)",
        "description": "任务分解 + 并行执行 + 汇总策略的多 Agent 协作流，对齐 CAMEL 协作思路。",
        "category": "运营协同",
        "workflow_type": "graph",
        "path": "python/agents/camel",
        "config_builder": _build_camel_config,
    },
}


class ADKSamplesImporter:
    """
    ADK Samples 模板导入器

    负责：
    - 列出可导入样例；
    - 生成本系统可执行模板配置；
    - 导入或更新用户模板。
    """

    def __init__(self, db: Session):
        self.db = db
        logger.info("[ADKSamplesImporter] Initialized")

    def _ensure_runtime_seed_agents(self, user_id: str) -> None:
        ensure_seed_agents(self.db, user_id, seeds=get_default_seed_agents())

    def _build_template_config(self, template_id: str, template_info: Dict[str, Any]) -> Dict[str, Any]:
        builder = template_info.get("config_builder")
        if callable(builder):
            config = builder()
        else:
            raw_config = template_info.get("config")
            config = copy.deepcopy(raw_config) if isinstance(raw_config, dict) else {}

        if not isinstance(config, dict):
            raise ValueError(f"Invalid config for ADK template: {template_id}")

        config.setdefault("schemaVersion", 2)
        meta = config.get("_templateMeta")
        if not isinstance(meta, dict):
            meta = {}
        meta.update(
            {
                "source": "adk-samples",
                "sampleId": template_id,
                "importedAt": int(time.time() * 1000),
            }
        )
        config["_templateMeta"] = meta
        return config

    async def list_available_templates(self) -> List[Dict[str, Any]]:
        templates: List[Dict[str, Any]] = []
        for template_id, template_info in ADK_TEMPLATES.items():
            templates.append(
                {
                    "id": template_id,
                    "name": template_info["name"],
                    "description": template_info["description"],
                    "category": template_info["category"],
                    "workflow_type": template_info["workflow_type"],
                    "path": template_info["path"],
                    "source": "adk-samples",
                }
            )

        logger.info("[ADKSamplesImporter] Found %s templates", len(templates))
        return templates

    async def import_template(
        self,
        user_id: str,
        template_id: str,
        custom_name: Optional[str] = None,
        is_public: bool = False,
        _ensure_sample_agents: bool = True,
    ) -> Dict[str, Any]:
        if template_id not in ADK_TEMPLATES:
            raise ValueError(f"Template '{template_id}' not found. Available templates: {list(ADK_TEMPLATES.keys())}")

        if _ensure_sample_agents:
            self._ensure_runtime_seed_agents(user_id)

        template_info = ADK_TEMPLATES[template_id]
        template_name = str(custom_name or template_info["name"]).strip()
        if not template_name:
            raise ValueError("Template name cannot be empty")

        config_payload = self._build_template_config(template_id=template_id, template_info=template_info)
        now = int(time.time() * 1000)

        existing = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.user_id == user_id,
            func.lower(WorkflowTemplate.name) == template_name.lower(),
        ).first()

        if existing:
            existing.description = template_info["description"]
            existing.category = template_info["category"]
            existing.workflow_type = template_info["workflow_type"]
            existing.config_json = json.dumps(config_payload, ensure_ascii=False)
            existing.is_public = bool(is_public)
            existing.updated_at = now
            existing.version = int(existing.version or 1) + 1
            self.db.commit()
            self.db.refresh(existing)
            logger.info("[ADKSamplesImporter] Updated template %s for user %s", existing.id, user_id)
            return existing.to_dict()

        template = WorkflowTemplate(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=template_name,
            description=template_info["description"],
            category=template_info["category"],
            workflow_type=template_info["workflow_type"],
            config_json=json.dumps(config_payload, ensure_ascii=False),
            is_public=bool(is_public),
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        logger.info("[ADKSamplesImporter] Imported %s as %s for user %s", template_id, template.id, user_id)
        return template.to_dict()

    async def import_all_templates(
        self,
        user_id: str,
        is_public: bool = False,
    ) -> List[Dict[str, Any]]:
        self._ensure_runtime_seed_agents(user_id)
        imported: List[Dict[str, Any]] = []
        for template_id in ADK_TEMPLATES.keys():
            try:
                imported.append(
                    await self.import_template(
                        user_id=user_id,
                        template_id=template_id,
                        is_public=is_public,
                        _ensure_sample_agents=False,
                    )
                )
            except Exception as exc:
                logger.error("[ADKSamplesImporter] Failed to import %s: %s", template_id, exc, exc_info=True)
        logger.info("[ADKSamplesImporter] Imported %s/%s templates", len(imported), len(ADK_TEMPLATES))
        return imported

    async def get_template_info(self, template_id: str) -> Optional[Dict[str, Any]]:
        if template_id not in ADK_TEMPLATES:
            return None
        template_info = ADK_TEMPLATES[template_id].copy()
        template_info["id"] = template_id
        template_info["source"] = "adk-samples"
        template_info["config"] = self._build_template_config(template_id=template_id, template_info=template_info)
        return template_info

    async def fetch_github_repo_metadata(self) -> Dict[str, Any]:
        """
        可选的 GitHub 元数据读取（不影响模板导入）。
        """
        url = ADK_SAMPLES_BASE_URL
        timeout = httpx.Timeout(connect=3.0, read=8.0, write=3.0, pool=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        return {
            "repo": ADK_SAMPLES_REPO,
            "url": payload.get("html_url"),
            "default_branch": payload.get("default_branch"),
            "updated_at": payload.get("updated_at"),
            "stargazers_count": payload.get("stargazers_count"),
        }
