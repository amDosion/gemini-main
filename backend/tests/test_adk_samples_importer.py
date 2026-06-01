import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import WorkflowTemplate
from app.services.gemini.agent.adk_samples_importer import ADK_TEMPLATES, ADKSamplesImporter
from app.services.agent.workflow_payload_normalizer import _validate_workflow_execute_payload


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


def _iter_agent_node_data(config):
    nodes = config.get("nodes") if isinstance(config.get("nodes"), list) else []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("data"), dict):
            continue
        data = node["data"]
        node_type = str(data.get("type") or node.get("type") or "").strip().lower().replace("-", "_")
        if node_type == "agent":
            yield node, data


@pytest.mark.asyncio
async def test_adk_samples_import_binds_agent_nodes_to_agent_manager_ids(db_session):
    importer = ADKSamplesImporter(db_session)

    imported = await importer.import_all_templates(user_id="user-1")

    assert len(imported) == len(ADK_TEMPLATES)

    bad_templates = []
    templates = db_session.query(WorkflowTemplate).filter(WorkflowTemplate.user_id == "user-1").all()
    for template in templates:
        config = json.loads(template.config_json)
        meta = config.get("_templateMeta") if isinstance(config.get("_templateMeta"), dict) else {}
        agent_nodes = list(_iter_agent_node_data(config))
        error = _validate_workflow_execute_payload(
            config.get("nodes") if isinstance(config.get("nodes"), list) else [],
            config.get("edges") if isinstance(config.get("edges"), list) else [],
        )
        missing_binding_nodes = [
            node.get("id")
            for node, data in agent_nodes
            if not str(data.get("agentId") or "").strip() or not str(data.get("agentName") or "").strip()
        ]
        missing_preset_key_nodes = [
            node.get("id")
            for node, data in agent_nodes
            if not str(data.get("agentPresetKey") or "").strip()
        ]
        if (
            meta.get("source") != "adk-samples"
            or meta.get("bindingStrategy") != "registry-id"
            or missing_binding_nodes
            or missing_preset_key_nodes
            or error
        ):
            bad_templates.append(
                {
                    "template": template.name,
                    "source": meta.get("source"),
                    "bindingStrategy": meta.get("bindingStrategy"),
                    "missingBindingNodes": missing_binding_nodes,
                    "missingPresetKeyNodes": missing_preset_key_nodes,
                    "error": error,
                }
            )

    assert bad_templates == []
