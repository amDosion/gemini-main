import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import AgentRegistry
from app.services.agent.agent_seed_service import (
    ensure_seed_agents,
    get_default_seed_agents,
)
from app.services.gemini.agent.starter_templates import load_starter_template_definitions


def _create_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    return engine, db


def _starter_agent_preset_keys() -> set[str]:
    preset_keys: set[str] = set()
    for definition in load_starter_template_definitions():
        config = definition.get("config") if isinstance(definition.get("config"), dict) else {}
        for node in config.get("nodes", []):
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            node_type = str(data.get("type") or node.get("type") or "").strip().lower().replace("-", "_")
            if node_type != "agent":
                continue
            preset_key = str(data.get("agentPresetKey") or data.get("agent_preset_key") or "").strip()
            if preset_key:
                preset_keys.add(preset_key)
    return preset_keys


def _seed_agent_keys() -> set[str]:
    keys: set[str] = set()
    for seed in get_default_seed_agents():
        agent_card = seed.get("agent_card") if isinstance(seed.get("agent_card"), dict) else {}
        metadata = agent_card.get("metadata") if isinstance(agent_card.get("metadata"), dict) else {}
        seed_key = str(metadata.get("seedKey") or seed.get("seed_key") or "").strip()
        if seed_key:
            keys.add(seed_key)
    return keys


def test_default_seed_agents_cover_every_starter_template_agent_reference():
    starter_preset_keys = _starter_agent_preset_keys()
    seed_keys = _seed_agent_keys()

    assert starter_preset_keys
    assert starter_preset_keys <= seed_keys


def test_analytics_seed_agents_have_data_analysis_default_task_type():
    expected_data_analysis_agents = {
        "亚马逊广告分析师",
        "亚马逊选品分析师",
        "关键词研究专家",
        "竞品分析专家",
        "数据报表分析师",
        "多店铺运营整合师",
    }
    bad_agents = []
    for seed in get_default_seed_agents():
        if seed.get("name") not in expected_data_analysis_agents:
            continue
        agent_card = seed.get("agent_card") if isinstance(seed.get("agent_card"), dict) else {}
        defaults = agent_card.get("defaults") if isinstance(agent_card.get("defaults"), dict) else {}
        if defaults.get("defaultTaskType") != "data-analysis":
            bad_agents.append({
                "name": seed.get("name"),
                "defaultTaskType": defaults.get("defaultTaskType"),
            })

    assert bad_agents == []


def test_ensure_seed_agents_creates_agent_manager_builtins_for_starter_agents():
    engine, db = _create_db()
    try:
        ensure_seed_agents(db, "user-1", seeds=get_default_seed_agents())

        agents = db.query(AgentRegistry).filter(
            AgentRegistry.user_id == "user-1",
            AgentRegistry.agent_type == "seed",
            AgentRegistry.status == "active",
        ).all()
        agent_seed_keys = set()
        for agent in agents:
            agent_card = json.loads(agent.agent_card_json or "{}")
            metadata = agent_card.get("metadata") if isinstance(agent_card.get("metadata"), dict) else {}
            seed_key = str(metadata.get("seedKey") or "").strip()
            if seed_key:
                agent_seed_keys.add(seed_key)

        assert _starter_agent_preset_keys() <= agent_seed_keys
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_ensure_seed_agents_updates_existing_seed_definition_fields():
    engine, db = _create_db()
    try:
        seed = next(seed for seed in get_default_seed_agents() if seed["name"] == "图片编辑优化师")
        db.add(
            AgentRegistry(
                id="seed-image-edit",
                user_id="user-1",
                name=seed["name"],
                description="旧描述",
                agent_type="seed",
                provider_id=seed["provider_id"],
                model_id=seed["model_id"],
                system_prompt="旧提示词",
                temperature=0.1,
                max_tokens=128,
                icon="🤖",
                color="#000000",
                status="active",
                created_at=1,
                updated_at=1,
                agent_card_json=json.dumps({"defaults": {"defaultTaskType": "chat"}}, ensure_ascii=False),
            )
        )
        db.commit()

        ensure_seed_agents(db, "user-1", seeds=get_default_seed_agents())

        agent = db.query(AgentRegistry).filter(AgentRegistry.id == "seed-image-edit").one()
        agent_card = json.loads(agent.agent_card_json)

        assert agent.description == seed["description"]
        assert agent.system_prompt == seed["system_prompt"]
        assert agent.temperature == seed["temperature"]
        assert agent.max_tokens == seed["max_tokens"]
        assert agent.icon == seed["icon"]
        assert agent.color == seed["color"]
        assert agent_card["defaults"]["defaultTaskType"] == "image-edit"
        assert agent_card["defaults"]["imageEdit"]["preserveProductIdentity"] is True
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_ensure_seed_agents_reactivates_existing_inactive_seed_instead_of_creating_duplicate():
    engine, db = _create_db()
    try:
        seed = next(seed for seed in get_default_seed_agents() if seed["name"] == "视频创意导演")
        db.add(
            AgentRegistry(
                id="seed-video-director",
                user_id="user-1",
                name=seed["name"],
                description=seed["description"],
                agent_type="seed",
                provider_id=seed["provider_id"],
                model_id=seed["model_id"],
                system_prompt=seed["system_prompt"],
                temperature=seed["temperature"],
                max_tokens=seed["max_tokens"],
                icon=seed["icon"],
                color=seed["color"],
                status="inactive",
                created_at=1,
                updated_at=1,
                agent_card_json=json.dumps(seed.get("agent_card"), ensure_ascii=False),
            )
        )
        db.commit()

        ensure_seed_agents(db, "user-1", seeds=[seed])

        agents = db.query(AgentRegistry).filter(
            AgentRegistry.user_id == "user-1",
            AgentRegistry.name == seed["name"],
        ).all()

        assert len(agents) == 1
        assert agents[0].id == "seed-video-director"
        assert agents[0].status == "active"
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
