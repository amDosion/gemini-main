import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import WorkflowTemplate
from app.services.agent.agent_seed_service import SEED_AGENTS
from app.services.agent.workflow_contract import ALLOWED_VIDEO_RESOLUTIONS
from app.services.agent.workflow_payload_normalizer import (
    ALLOWED_VIDEO_MASK_MODES,
    _validate_workflow_execute_payload,
)
from app.services.gemini.agent.starter_templates import load_starter_template_definitions
from app.services.gemini.agent.starter_templates import loader as starter_template_loader
from app.services.gemini.agent.workflow_template_service import WorkflowTemplateService


STARTER_TEMPLATE_SOURCE_DIR = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "gemini"
    / "agent"
    / "starter_templates"
    / "templates"
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _node(node_id: str, node_type: str):
    return {
        "id": node_id,
        "type": node_type,
        "data": {
            "type": node_type,
            "label": node_id,
            "description": "",
        },
        "position": {"x": 0, "y": 0},
    }


def _valid_template_config():
    return {
        "schemaVersion": 2,
        "nodes": [
            _node("start", "start"),
            _node("input", "input_text"),
            _node("end", "end"),
        ],
        "edges": [
            {"id": "e-start-input", "source": "start", "target": "input"},
            {"id": "e-input-end", "source": "input", "target": "end"},
        ],
    }


def _invalid_disconnected_template_config():
    return {
        "schemaVersion": 2,
        "nodes": [
            _node("start", "start"),
            _node("end", "end"),
            _node("orphan", "input_text"),
        ],
        "edges": [
            {"id": "e-start-end", "source": "start", "target": "end"},
        ],
    }


def _human_template_config(*, auto_approve=None):
    human_data = {
        "type": "human",
        "label": "review",
        "description": "",
        "approvalPrompt": "确认后继续",
    }
    if auto_approve is not None:
        human_data["autoApprove"] = auto_approve
    return {
        "schemaVersion": 2,
        "nodes": [
            _node("start", "start"),
            {
                "id": "review",
                "type": "human",
                "data": human_data,
                "position": {"x": 0, "y": 0},
            },
            _node("end", "end"),
        ],
        "edges": [
            {"id": "e-start-review", "source": "start", "target": "review"},
            {"id": "e-review-end", "source": "review", "target": "end"},
        ],
    }


def _iter_starter_agent_nodes():
    for definition in load_starter_template_definitions():
        config = definition.get("config") if isinstance(definition.get("config"), dict) else {}
        for node in config.get("nodes", []):
            if not isinstance(node, dict):
                continue
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            node_type = str(data.get("type") or node.get("type") or "").strip().lower().replace("-", "_")
            if node_type == "agent":
                yield definition, node, data


def _iter_raw_starter_template_agent_nodes():
    for path in sorted(STARTER_TEMPLATE_SOURCE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        for node in config.get("nodes", []):
            if not isinstance(node, dict):
                continue
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            node_type = str(data.get("type") or node.get("type") or "").strip().lower().replace("-", "_")
            if node_type == "agent":
                yield path.name, payload, node, data


@pytest.mark.asyncio
async def test_create_template_rejects_graph_that_execution_would_reject(db_session):
    service = WorkflowTemplateService(db=db_session)

    with pytest.raises(ValueError, match="未从开始节点连通"):
        await service.create_template(
            user_id="user-1",
            name="bad disconnected template",
            description="bad graph",
            category="通用",
            workflow_type="graph",
            config=_invalid_disconnected_template_config(),
        )


@pytest.mark.asyncio
async def test_update_template_rejects_graph_that_execution_would_reject(db_session):
    service = WorkflowTemplateService(db=db_session)
    template = await service.create_template(
        user_id="user-1",
        name="valid template",
        description="valid graph",
        category="通用",
        workflow_type="graph",
        config=_valid_template_config(),
    )

    with pytest.raises(ValueError, match="未从开始节点连通"):
        await service.update_template(
            user_id="user-1",
            template_id=template["id"],
            config=_invalid_disconnected_template_config(),
        )


@pytest.mark.asyncio
async def test_create_template_rejects_human_node_without_explicit_auto_approve(db_session):
    service = WorkflowTemplateService(db=db_session)

    with pytest.raises(ValueError, match="autoApprove=true"):
        await service.create_template(
            user_id="user-1",
            name="human review template",
            description="human graph",
            category="通用",
            workflow_type="graph",
            config=_human_template_config(),
        )


@pytest.mark.asyncio
async def test_create_template_accepts_human_node_with_explicit_auto_approve(db_session):
    service = WorkflowTemplateService(db=db_session)

    template = await service.create_template(
        user_id="user-1",
        name="auto approved review template",
        description="human graph",
        category="通用",
        workflow_type="graph",
        config=_human_template_config(auto_approve=True),
    )

    assert template["id"]


def _seed_agent_keys() -> set[str]:
    keys: set[str] = set()
    for seed in SEED_AGENTS:
        agent_card = seed.get("agent_card") if isinstance(seed.get("agent_card"), dict) else {}
        metadata = agent_card.get("metadata") if isinstance(agent_card.get("metadata"), dict) else {}
        seed_key = str(metadata.get("seedKey") or seed.get("seed_key") or "").strip()
        if seed_key:
            keys.add(seed_key)
    return keys


def test_starter_templates_use_agent_preset_keys_without_inline_or_registry_copies():
    seed_agent_keys = _seed_agent_keys()
    bad_nodes = []
    for definition, node, data in _iter_starter_agent_nodes():
        node_id = str(node.get("id") or "<missing>")
        starter_key = str(definition.get("starter_key") or "<missing>")
        preset_key = str(data.get("agentPresetKey") or data.get("agent_preset_key") or "").strip()
        agent_name = str(data.get("agentName") or data.get("agent_name") or "").strip()
        agent_id = str(data.get("agentId") or data.get("agent_id") or "").strip()
        inline_keys = [key for key in data.keys() if str(key).startswith("inline")]
        task_type = str(data.get("agentTaskType") or data.get("agent_task_type") or "").strip()

        if inline_keys or agent_name or agent_id or not task_type or preset_key not in seed_agent_keys:
            bad_nodes.append(
                {
                    "starter_key": starter_key,
                    "node_id": node_id,
                    "preset_key": preset_key,
                    "agent_name": agent_name,
                    "agent_id": agent_id,
                    "inline_keys": inline_keys,
                    "task_type": task_type,
                }
            )

    assert bad_nodes == []


def test_starter_template_source_json_uses_agent_preset_keys():
    seed_agent_keys = _seed_agent_keys()
    bad_nodes = []
    for source_name, definition, node, data in _iter_raw_starter_template_agent_nodes():
        node_id = str(node.get("id") or "<missing>")
        starter_key = str(definition.get("starter_key") or "<missing>")
        preset_key = str(data.get("agentPresetKey") or data.get("agent_preset_key") or "").strip()
        agent_name = str(data.get("agentName") or data.get("agent_name") or "").strip()
        agent_id = str(data.get("agentId") or data.get("agent_id") or "").strip()
        inline_keys = [key for key in data.keys() if str(key).startswith("inline")]
        task_type = str(data.get("agentTaskType") or data.get("agent_task_type") or "").strip()

        if inline_keys or agent_name or agent_id or not task_type or preset_key not in seed_agent_keys:
            bad_nodes.append(
                {
                    "source": source_name,
                    "starter_key": starter_key,
                    "node_id": node_id,
                    "preset_key": preset_key,
                    "agent_name": agent_name,
                    "agent_id": agent_id,
                    "inline_keys": inline_keys,
                    "task_type": task_type,
                }
            )

    assert bad_nodes == []


def test_starter_template_data_analysis_agents_do_not_force_chat_task_type():
    data_analysis_preset_keys = {
        "amazon-ad-analyst",
        "amazon-product-researcher",
        "keyword-researcher",
        "competitor-analyst",
        "data-report-analyst",
        "multi-store-ops-integrator",
    }
    bad_nodes = []
    for source_name, definition, node, data in _iter_raw_starter_template_agent_nodes():
        preset_key = str(data.get("agentPresetKey") or data.get("agent_preset_key") or "").strip()
        task_type = str(data.get("agentTaskType") or data.get("agent_task_type") or "").strip()
        if preset_key in data_analysis_preset_keys and task_type == "chat":
            bad_nodes.append(
                {
                    "source": source_name,
                    "starter_key": definition.get("starter_key"),
                    "node_id": node.get("id"),
                    "label": data.get("label"),
                    "preset_key": preset_key,
                    "task_type": task_type,
                }
            )

    assert bad_nodes == []


def test_starter_template_source_video_mask_modes_match_execution_contract():
    bad_nodes = []
    allowed_modes = {mode for mode in ALLOWED_VIDEO_MASK_MODES if mode}
    for source_name, definition, node, data in _iter_raw_starter_template_agent_nodes():
        mask_mode = str(data.get("agentVideoMaskMode") or data.get("agent_video_mask_mode") or "").strip()
        if mask_mode and mask_mode not in allowed_modes:
            bad_nodes.append(
                {
                    "source": source_name,
                    "starter_key": definition.get("starter_key"),
                    "node_id": node.get("id"),
                    "mask_mode": mask_mode,
                }
            )

    assert bad_nodes == []


def test_starter_template_source_video_resolutions_match_execution_contract():
    bad_nodes = []
    allowed_resolutions = {resolution for resolution in ALLOWED_VIDEO_RESOLUTIONS if resolution}
    for source_name, definition, node, data in _iter_raw_starter_template_agent_nodes():
        task_type = str(data.get("agentTaskType") or data.get("agent_task_type") or "").strip()
        resolution = str(data.get("agentResolutionTier") or data.get("agent_resolution_tier") or "").strip()
        if task_type == "video-gen" and resolution and resolution not in allowed_resolutions:
            bad_nodes.append(
                {
                    "source": source_name,
                    "starter_key": definition.get("starter_key"),
                    "node_id": node.get("id"),
                    "resolution": resolution,
                }
            )

    assert bad_nodes == []


def test_loader_rejects_legacy_inline_agent_copy_instead_of_rewriting(tmp_path, monkeypatch):
    template_path = tmp_path / "legacy_inline_agent_copy.json"
    template_path.write_text(
        json.dumps(
            {
                "starter_key": "legacy_inline_agent_copy",
                "starter_version": 1,
                "name": "Legacy Inline Agent Copy",
                "workflow_type": "graph",
                "config": {
                    "schemaVersion": 2,
                    "nodes": [
                        _node("start", "start"),
                        {
                            "id": "agent-legacy",
                            "type": "agent",
                            "data": {
                                "type": "agent",
                                "label": "legacy",
                                "description": "",
                                "agentName": "运营策略顾问",
                                "inlineSystemPrompt": "old duplicate prompt",
                                "agentTaskType": "chat",
                            },
                            "position": {"x": 0, "y": 0},
                        },
                        _node("end", "end"),
                    ],
                    "edges": [
                        {"id": "e-start-agent", "source": "start", "target": "agent-legacy"},
                        {"id": "e-agent-end", "source": "agent-legacy", "target": "end"},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(starter_template_loader, "_TEMPLATES_DIR", tmp_path)

    with pytest.raises(ValueError, match="legacy inline agent fields"):
        starter_template_loader.load_starter_template_definitions()


@pytest.mark.asyncio
async def test_user_bound_starter_template_graphs_match_execution_validation_contract(db_session):
    service = WorkflowTemplateService(db=db_session)
    await service.ensure_starter_templates(user_id="user-1")

    bad_templates = []
    templates = db_session.query(WorkflowTemplate).filter(WorkflowTemplate.user_id == "user-1").all()
    for template in templates:
        config = json.loads(template.config_json)
        error = _validate_workflow_execute_payload(
            config.get("nodes") if isinstance(config.get("nodes"), list) else [],
            config.get("edges") if isinstance(config.get("edges"), list) else [],
        )
        if error:
            bad_templates.append({
                "template": template.name,
                "error": error,
            })

    assert bad_templates == []


@pytest.mark.asyncio
async def test_user_bound_starter_template_metadata_records_registry_binding(db_session):
    service = WorkflowTemplateService(db=db_session)
    await service.ensure_starter_templates(user_id="user-1")

    bad_templates = []
    templates = db_session.query(WorkflowTemplate).filter(WorkflowTemplate.user_id == "user-1").all()
    for template in templates:
        config = json.loads(template.config_json)
        meta = config.get("_templateMeta") if isinstance(config.get("_templateMeta"), dict) else {}
        nodes = config.get("nodes") if isinstance(config.get("nodes"), list) else []
        has_agent_node = any(
            isinstance(node, dict)
            and isinstance(node.get("data"), dict)
            and str(node["data"].get("type") or node.get("type") or "").strip().lower().replace("-", "_") == "agent"
            for node in nodes
        )
        expected_binding_strategy = "registry-id" if has_agent_node else "none"
        if meta.get("bindingStrategy") != expected_binding_strategy or meta.get("isLegacyStarterCopy") is not False:
            bad_templates.append(
                {
                    "template": template.name,
                    "bindingStrategy": meta.get("bindingStrategy"),
                    "expectedBindingStrategy": expected_binding_strategy,
                    "isLegacyStarterCopy": meta.get("isLegacyStarterCopy"),
                }
            )

    assert bad_templates == []


@pytest.mark.asyncio
async def test_ensure_starter_templates_resolves_agent_presets_to_agent_manager_ids(db_session):
    definitions = load_starter_template_definitions()
    definition = next(item for item in definitions if item["config"].get("nodes"))
    stale_config = copy.deepcopy(definition["config"])
    stale_meta = stale_config.setdefault("_templateMeta", {})
    stale_meta["starterKey"] = definition["starter_key"]
    stale_meta["starterVersion"] = definition["starter_version"]

    degraded_node_data = next(
        node["data"]
        for node in stale_config["nodes"]
        if isinstance(node, dict)
        and isinstance(node.get("data"), dict)
        and node["data"].get("agentPresetKey")
    )
    preset_key = degraded_node_data["agentPresetKey"]
    degraded_node_data["agentName"] = "旧模板内嵌名字"
    degraded_node_data["inlineUseActiveProfile"] = True
    degraded_node_data["inlineSystemPrompt"] = "stale duplicate prompt"

    template = WorkflowTemplate(
        id="starter-template-1",
        user_id="user-1",
        name=definition["name"],
        description=definition.get("description"),
        category=definition.get("category", "general"),
        workflow_type=definition.get("workflow_type", "graph"),
        config_json=json.dumps(stale_config, ensure_ascii=False),
        is_public=False,
        version=1,
        created_at=1,
        updated_at=1,
    )
    db_session.add(template)
    db_session.commit()

    service = WorkflowTemplateService(db=db_session)
    await service.ensure_starter_templates(user_id="user-1")

    db_session.refresh(template)
    refreshed_config = json.loads(template.config_json)
    refreshed_node_data = next(
        node["data"]
        for node in refreshed_config["nodes"]
        if isinstance(node, dict)
        and isinstance(node.get("data"), dict)
        and node["data"].get("agentPresetKey") == preset_key
    )

    assert refreshed_node_data["agentId"]
    assert refreshed_node_data["agentName"]
    assert "inlineUseActiveProfile" not in refreshed_node_data
    assert "inlineSystemPrompt" not in refreshed_node_data
