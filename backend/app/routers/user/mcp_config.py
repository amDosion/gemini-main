"""
用户 MCP 配置路由
"""
from __future__ import annotations

import json
import logging
import hashlib
import time
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...models.db_models import UserMcpConfig
from ...services.mcp.types import (
    MCPServerType,
    MCPServerConfig,
    MCPStdioPolicyError,
    validate_mcp_stdio_command_policy,
)
from ...services.mcp.mcp_manager import get_mcp_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp-config"])


class McpConfigUpdatePayload(BaseModel):
    """MCP 配置更新请求体。"""

    config_json: Optional[str] = Field(default=None, alias="configJson")
    config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        extra="ignore",
        validate_by_name=True,
    )

class StopMcpSessionPayload(BaseModel):
    """停止 MCP 会话请求体。"""
    mcp_server_key: Optional[str] = Field(default=None, alias="mcpServerKey")

    model_config = ConfigDict(
        extra="ignore",
        validate_by_name=True,
    )


class McpToolInvokePayload(BaseModel):
    """调用 MCP 工具请求体。"""
    tool_name: str = Field(alias="toolName")
    arguments: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        extra="ignore",
        validate_by_name=True,
    )


def _normalize_config_json(
    config_json: Optional[str],
    config: Optional[Dict[str, Any]],
) -> str:
    """
    校验并标准化 MCP JSON 配置，统一存储为格式化字符串。
    """
    parsed: Any

    if config is not None:
        parsed = config
    else:
        raw = (config_json or "").strip()
        if not raw:
            return "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid MCP JSON: {exc.msg}") from exc

    try:
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid MCP JSON: {exc}") from exc


def _is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def _extract_server_map(root: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    mcp_servers = root.get("mcpServers")
    if _is_plain_object(mcp_servers):
        return {
            str(key): value
            for key, value in mcp_servers.items()
            if _is_plain_object(value)
        }

    if root and all(_is_plain_object(value) for value in root.values()):
        return {
            str(key): value
            for key, value in root.items()
            if _is_plain_object(value)
        }

    return {}


def _parse_server_type(raw_type: Optional[str], server_config: Dict[str, Any]) -> MCPServerType:
    normalized = (raw_type or "").strip().lower()
    if normalized in {"stdio"}:
        return MCPServerType.STDIO
    if normalized in {"sse"}:
        return MCPServerType.SSE
    if normalized in {"http"}:
        return MCPServerType.HTTP
    if normalized in {"streamablehttp", "streamable_http", "streamable-http"}:
        return MCPServerType.STREAMABLE_HTTP

    if server_config.get("command"):
        return MCPServerType.STDIO
    if server_config.get("url"):
        return MCPServerType.HTTP
    raise ValueError("Unsupported or missing MCP server type")


def _normalize_args(raw_args: Any) -> Optional[List[str]]:
    if raw_args is None:
        return None
    if not isinstance(raw_args, list):
        return None
    return [str(item) for item in raw_args]


def _normalize_env(raw_env: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw_env, dict):
        return None
    return {str(key): str(value) for key, value in raw_env.items()}


def _build_mcp_server_config(server_config: Dict[str, Any]) -> MCPServerConfig:
    server_type = _parse_server_type(
        server_config.get("serverType")
        or server_config.get("server_type")
        or server_config.get("type"),
        server_config,
    )

    timeout_raw = server_config.get("timeout", 30.0)
    try:
        timeout = float(timeout_raw)
    except (TypeError, ValueError):
        timeout = 30.0

    config = MCPServerConfig(
        server_type=server_type,
        command=server_config.get("command"),
        args=_normalize_args(server_config.get("args")),
        env=_normalize_env(server_config.get("env")),
        url=server_config.get("url"),
        timeout=timeout,
    )
    config.validate()
    return config


def _build_and_validate_mcp_server_config(
    server_key: str,
    server_config: Dict[str, Any],
    *,
    context: str,
) -> MCPServerConfig:
    try:
        config = _build_mcp_server_config(server_config)
        validate_mcp_stdio_command_policy(
            config,
            policy=settings.mcp_stdio_command_policy,
            allowed_commands=settings.mcp_stdio_allowed_commands,
            context=f"{context}:{server_key}",
        )
        return config
    except (ValueError, MCPStdioPolicyError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MCP server config '{server_key}': {exc}",
        ) from exc


def _validate_config_root_or_raise(root: Any, *, context: str) -> None:
    if not isinstance(root, dict):
        raise HTTPException(status_code=400, detail="MCP config root must be a JSON object")

    server_map = _extract_server_map(root)
    for server_key, server_config in server_map.items():
        _build_and_validate_mcp_server_config(
            str(server_key),
            server_config,
            context=context,
        )


def _session_id_for_server(user_id: str, server_key: str, server_config: Dict[str, Any]) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(server_config, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    return f"chat:{user_id}:{server_key}:{fingerprint}"


def _load_server_config_or_raise(db: Session, user_id: str, server_key: str) -> Dict[str, Any]:
    record = db.query(UserMcpConfig).filter(UserMcpConfig.user_id == user_id).first()
    if not record or not record.config_json:
        raise HTTPException(status_code=404, detail="No MCP config found for current user")

    try:
        root = json.loads(record.config_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid persisted MCP config JSON: {exc.msg}") from exc

    if not isinstance(root, dict):
        raise HTTPException(status_code=500, detail="Invalid MCP config root type")

    server_map = _extract_server_map(root)
    server_config = server_map.get(server_key)
    if not server_config:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_key}' not found")
    if server_config.get("disabled") is True or server_config.get("enabled") is False:
        raise HTTPException(status_code=400, detail=f"MCP server '{server_key}' is disabled")

    return server_config


@router.get("/config")
async def get_mcp_config(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的 MCP JSON 配置。"""
    record = db.query(UserMcpConfig).filter(UserMcpConfig.user_id == user_id).first()
    if not record:
        return {
            "config_json": "{}",
            "updated_at": None,
        }

    raw = (record.config_json or "").strip()
    if not raw:
        raw = "{}"

    try:
        normalized = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        logger.warning(
            "[MCP Config] Invalid persisted config_json for user=%s, fallback to {}",
            user_id,
        )
        normalized = "{}"

    return {
        "config_json": normalized,
        "updated_at": record.updated_at,
    }


@router.put("/config")
async def update_mcp_config(
    payload: McpConfigUpdatePayload,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """更新当前登录用户的 MCP JSON 配置。"""
    try:
        normalized = _normalize_config_json(payload.config_json, payload.config)
        root = json.loads(normalized)
        _validate_config_root_or_raise(root, context="mcp-config-save")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record = db.query(UserMcpConfig).filter(UserMcpConfig.user_id == user_id).first()
    if not record:
        record = UserMcpConfig(
            user_id=user_id,
            config_json=normalized,
        )
        db.add(record)
    else:
        record.config_json = normalized

    try:
        db.commit()
        db.refresh(record)
    except Exception as exc:
        db.rollback()
        logger.error(
            "[MCP Config] Failed to persist config for user=%s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to save MCP config") from exc

    return {
        "config_json": record.config_json or "{}",
        "updated_at": record.updated_at,
    }


@router.get("/config/tools/{server_key}")
async def get_mcp_server_tools(
    server_key: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """获取指定 MCP 服务支持的工具列表。"""
    server_config = _load_server_config_or_raise(db=db, user_id=user_id, server_key=server_key)

    try:
        mcp_config = _build_and_validate_mcp_server_config(
            server_key,
            server_config,
            context="mcp-config-tools",
        )
        session_id = _session_id_for_server(user_id, server_key, server_config)
        manager = get_mcp_manager()
        await manager.create_session(session_id, mcp_config)
        tools = await manager.list_tools(session_id)
    except HTTPException:
        raise
    except (ValueError, MCPStdioPolicyError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid MCP server config: {exc}") from exc
    except Exception as exc:
        logger.error(
            "[MCP Config] Failed to get tools for user=%s, server=%s: %s",
            user_id,
            server_key,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch MCP tools: {exc}") from exc

    return {
        "server_key": server_key,
        "tool_count": len(tools),
        "tools": [
            {
                "name": tool.name,
                "description": tool.description or "",
            }
            for tool in tools
        ],
    }


@router.post("/config/tools/{server_key}/invoke")
async def invoke_mcp_server_tool(
    server_key: str,
    payload: McpToolInvokePayload,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """调用指定 MCP 服务中的工具。"""
    server_config = _load_server_config_or_raise(db=db, user_id=user_id, server_key=server_key)

    tool_name = str(payload.tool_name or "").strip()
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    try:
        mcp_config = _build_and_validate_mcp_server_config(
            server_key,
            server_config,
            context="mcp-config-invoke",
        )
        session_id = _session_id_for_server(user_id, server_key, server_config)
        manager = get_mcp_manager()
        await manager.create_session(session_id, mcp_config)
        arguments = payload.arguments if isinstance(payload.arguments, dict) else {}

        start = time.perf_counter()
        result = await manager.call_tool(session_id, tool_name, arguments)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
    except HTTPException:
        raise
    except (ValueError, MCPStdioPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "[MCP Config] Failed to invoke tool for user=%s, server=%s, tool=%s: %s",
            user_id,
            server_key,
            tool_name,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to invoke MCP tool: {exc}") from exc

    return {
        "server_key": server_key,
        "tool_name": tool_name,
        "session_id": session_id,
        "latency_ms": latency_ms,
        "timestamp": time.time(),
        **result.to_dict(),
    }


@router.post("/session/stop")
async def stop_mcp_sessions(
    payload: StopMcpSessionPayload,
    user_id: str = Depends(require_current_user),
):
    """停止当前用户的 MCP 会话（可按 server_key 精确停止）。"""
    manager = get_mcp_manager()
    all_sessions = manager.list_sessions()

    if payload.mcp_server_key:
        prefix = f"chat:{user_id}:{payload.mcp_server_key}:"
    else:
        prefix = f"chat:{user_id}:"

    matched = [session_id for session_id in all_sessions if session_id.startswith(prefix)]
    closed: List[str] = []
    errors: List[str] = []

    for session_id in matched:
        try:
            await manager.close_session(session_id)
            closed.append(session_id)
        except Exception as exc:
            logger.warning("[MCP Config] Failed to close session=%s: %s", session_id, exc)
            errors.append(f"{session_id}: {exc}")

    return {
        "success": True,
        "closed_count": len(closed),
        "closed_sessions": closed,
        "errors": errors,
    }
