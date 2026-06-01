"""Workflow Agent binding validation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.db_models import AgentRegistry
from .workflow_payload_normalizer import (
    _coerce_optional_bool,
    _is_active_inline_provider_token,
    _is_auto_inline_model_token,
)


def _safe_string(value: Any) -> str:
    return str(value or "").strip()


def _node_type(node: Dict[str, Any]) -> str:
    data = node.get("data")
    if isinstance(data, dict):
        node_type = _safe_string(data.get("type")).lower().replace("-", "_")
        if node_type:
            return node_type
    return _safe_string(node.get("type")).lower().replace("-", "_")


def _agent_node_data(node: Dict[str, Any]) -> Dict[str, Any]:
    data = node.get("data")
    return data if isinstance(data, dict) else {}


def _has_inline_binding(node_data: Dict[str, Any]) -> bool:
    inline_use_active_profile = _coerce_optional_bool(
        node_data.get("inlineUseActiveProfile")
        if "inlineUseActiveProfile" in node_data
        else node_data.get("inline_use_active_profile"),
        default=False,
    )
    if inline_use_active_profile:
        return True

    inline_provider = _safe_string(
        node_data.get("inlineProviderId")
        or node_data.get("inline_provider_id")
        or node_data.get("providerId")
        or node_data.get("provider_id")
        or node_data.get("modelOverrideProviderId")
        or node_data.get("model_override_provider_id")
    )
    inline_model = _safe_string(
        node_data.get("inlineModelId")
        or node_data.get("inline_model_id")
        or node_data.get("modelId")
        or node_data.get("model_id")
        or node_data.get("modelOverrideModelId")
        or node_data.get("model_override_model_id")
    )
    if _is_active_inline_provider_token(inline_provider) and _is_auto_inline_model_token(
        inline_model
    ):
        return True
    return bool(inline_provider and inline_model)


def _find_active_agent(
    db: Session,
    *,
    user_id: str,
    agent_id: str,
    agent_name: str,
) -> Optional[AgentRegistry]:
    normalized_user_id = _safe_string(user_id)
    normalized_agent_id = _safe_string(agent_id)
    normalized_agent_name = _safe_string(agent_name)

    if normalized_agent_id:
        query = db.query(AgentRegistry).filter(
            AgentRegistry.id == normalized_agent_id,
            AgentRegistry.status == "active",
        )
        if normalized_user_id:
            query = query.filter(AgentRegistry.user_id == normalized_user_id)
        agent = query.first()
        if agent:
            return agent

    if normalized_agent_name:
        query = db.query(AgentRegistry).filter(
            func.lower(AgentRegistry.name) == normalized_agent_name.lower(),
            AgentRegistry.status == "active",
        )
        if normalized_user_id:
            query = query.filter(AgentRegistry.user_id == normalized_user_id)
        return query.first()

    return None


def validate_workflow_agent_bindings(
    *,
    db: Session,
    user_id: str,
    nodes: List[Dict[str, Any]],
) -> Optional[str]:
    """Validate registry-bound workflow Agent nodes before execution starts."""

    if not isinstance(nodes, list):
        return "工作流节点必须是数组"

    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or _node_type(node) != "agent":
            continue

        node_id = _safe_string(node.get("id")) or str(index)
        node_data = _agent_node_data(node)
        if _has_inline_binding(node_data):
            continue

        agent_id = _safe_string(node_data.get("agentId") or node_data.get("agent_id"))
        agent_name = _safe_string(node_data.get("agentName") or node_data.get("agent_name"))
        if not agent_id and not agent_name:
            return (
                f"智能体节点[{node_id}] 必须配置 agentId / agentName，"
                "或提供 inlineProviderId + inlineModelId，"
                "或启用 inlineUseActiveProfile"
            )

        agent = _find_active_agent(
            db,
            user_id=user_id,
            agent_id=agent_id,
            agent_name=agent_name,
        )
        if not agent:
            return (
                f"智能体节点[{node_id}] 绑定的 Agent 不存在或已停用: "
                f"id={agent_id or '<empty>'}, name={agent_name or '<empty>'}"
            )

    return None
