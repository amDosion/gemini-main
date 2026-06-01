from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.db_models import AgentRegistry
from app.services.agent.workflow_agent_binding import validate_workflow_agent_bindings


def _node(node_id: str, node_type: str, data: dict | None = None) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "data": {
            "type": node_type,
            "label": node_id,
            **(data or {}),
        },
        "position": {"x": 0, "y": 0},
    }


def _agent_node(data: dict) -> list[dict]:
    return [
        _node("start", "start"),
        _node("agent-1", "agent", data),
        _node("end", "end"),
    ]


def _create_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    return engine, db


def test_validate_workflow_agent_bindings_resolves_agent_name_case_insensitively():
    engine, db = _create_db()
    try:
        db.add(
            AgentRegistry(
                id="agent-1",
                user_id="user-1",
                name="Image Agent",
                description="",
                agent_type="custom",
                provider_id="google",
                model_id="imagen-3.0-generate-002",
                system_prompt="",
                temperature=0.7,
                max_tokens=4096,
                icon="🎨",
                color="#d946ef",
                status="active",
                created_at=1,
                updated_at=1,
            )
        )
        db.commit()

        error = validate_workflow_agent_bindings(
            db=db,
            user_id="user-1",
            nodes=_agent_node({"agentName": "image agent"}),
        )

        assert error is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_validate_workflow_agent_bindings_rejects_missing_registry_agent_before_execution():
    engine, db = _create_db()
    try:
        error = validate_workflow_agent_bindings(
            db=db,
            user_id="user-1",
            nodes=_agent_node({"agentId": "missing-agent", "agentName": "Missing Agent"}),
        )

        assert error
        assert "agent-1" in error
        assert "missing-agent" in error
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_validate_workflow_agent_bindings_allows_inline_active_profile_agent():
    engine, db = _create_db()
    try:
        error = validate_workflow_agent_bindings(
            db=db,
            user_id="user-1",
            nodes=_agent_node({"inlineUseActiveProfile": True, "agentTaskType": "chat"}),
        )

        assert error is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
