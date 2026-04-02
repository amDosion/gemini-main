"""
Chat API Router

This module provides a chat API endpoint that works with all AI providers.
It handles both streaming and non-streaming responses, and integrates with the
ProviderFactory to create appropriate service instances.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging
import hashlib
import json

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.credential_manager import get_provider_credentials
from ...core.config import settings
from ...core.provider_param_whitelist import (
    ProviderParamValidationError,
    validate_chat_option_keys,
)
from ...models.db_models import Persona as DBPersona, UserMcpConfig
from ...services.mcp.types import (
    MCPServerType,
    MCPServerConfig,
    MCPStdioPolicyError,
    validate_mcp_stdio_command_policy,
)
from ...services.mcp.mcp_manager import get_mcp_manager
from ...utils.sse import build_safe_error_chunk, create_sse_response, encode_sse_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modes", tags=["chat"])
GOOGLE_PROVIDERS = {"google", "google-custom"}


# ==================== Request Models ====================

class Attachment(BaseModel):
    """Attachment model (images, files, etc.)"""
    id: str
    mime_type: str
    name: str
    url: Optional[str] = None
    temp_url: Optional[str] = None
    file_uri: Optional[str] = None
    base64_data: Optional[str] = None  # 直接 Base64 数据（不含 data: 前缀）
    google_file_uri: Optional[str] = None  # Google Files API URI


class Message(BaseModel):
    """Message model"""
    role: str  # "user" | "assistant" | "system"
    content: str
    is_error: Optional[bool] = False
    attachments: Optional[List[Attachment]] = None


class ChatOptions(BaseModel):
    """Chat options"""
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[Any] = None
    response_format: Optional[Any] = None
    logit_bias: Optional[Dict[str, Any]] = None
    n: Optional[int] = None
    user: Optional[str] = None
    enable_search: Optional[bool] = False
    enable_thinking: Optional[bool] = False
    enable_code_execution: Optional[bool] = False
    enable_browser: Optional[bool] = False
    enable_grounding: Optional[bool] = False
    persona_id: Optional[str] = None
    mcp_server_key: Optional[str] = None
    base_url: Optional[str] = None  # Custom API URL

    model_config = ConfigDict(extra="allow")


class ChatRequest(BaseModel):
    """Chat request"""
    model_id: str
    messages: List[Message]
    message: str
    attachments: Optional[List[Attachment]] = None
    options: Optional[ChatOptions] = None
    api_key: Optional[str] = None  # Optional, will try to get from database/env
    stream: Optional[bool] = True  # Default to streaming


# ==================== Helper Functions ====================

def convert_messages_to_provider_format(
    history: List[Message],
    current_message: str,
    provider: str = None,
    current_attachments: Optional[List[Attachment]] = None
) -> List[Dict[str, Any]]:
    """
    Convert frontend message format to provider format.

    Role conversion rules:
    - Google/Gemini: Keep "model" as "model" (Gemini API expects "model")
    - OpenAI-compatible: Convert "model" to "assistant" (OpenAI API expects "assistant")
    - Default: Convert "model" to "assistant" for backward compatibility

    Attachment handling:
    - current_attachments are injected into the last user message
    - Supports inline_data (Base64) and file_data (Google Files API URI)
    """
    messages = []

    # Determine if provider is Google (needs "model" role)
    is_google = provider and provider in ["google", "google-custom"]

    for msg in history:
        if msg.is_error:
            continue
        if not msg.content:
            continue

        role = msg.role
        # Only convert "model" to "assistant" for non-Google providers
        if role == "model" and not is_google:
            role = "assistant"
        # For Google, keep "model" as "model" (Gemini API requirement)

        messages.append({
            "role": role,
            "content": msg.content
        })

    if current_message:
        msg_dict: Dict[str, Any] = {
            "role": "user",
            "content": current_message
        }
        # 注入当前消息的附件数据
        if current_attachments:
            msg_dict["attachments"] = [
                {
                    "mime_type": att.mime_type,
                    "url": att.url,
                    "temp_url": att.temp_url,
                    "file_uri": att.file_uri or att.google_file_uri,
                    "base64_data": att.base64_data,
                }
                for att in current_attachments
                if att.mime_type  # 只包含有效 MIME 类型的附件
            ]
        messages.append(msg_dict)

    return messages


def convert_chunk_to_frontend_format(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Convert provider chunk format to frontend format.
    """
    chunk_type = chunk.get("chunk_type", "content")
    browser_operation_id = (
        chunk.get("browser_operation_id")
        or chunk.get("browserOperationId")
    )

    # reasoning/content 统一透传，由前端按 chunk_type 决定渲染（不再注入 <thinking> 标签）
    result = {
        "text": chunk.get("content", ""),
        "chunk_type": chunk_type
    }
    
    if chunk_type == "done":
        result["usage"] = {
            "prompt_tokens": chunk.get("prompt_tokens", 0),
            "completion_tokens": chunk.get("completion_tokens", 0),
            "total_tokens": chunk.get("total_tokens", 0)
        }
        if chunk.get("finish_reason"):
            result["finish_reason"] = chunk["finish_reason"]

    if chunk_type == "tool_call":
        result["tool_name"] = chunk.get("tool_name")
        result["tool_args"] = chunk.get("tool_args", {})
        if chunk.get("call_id"):
            result["call_id"] = chunk.get("call_id")
        if chunk.get("tool_type"):
            result["tool_type"] = chunk.get("tool_type")
        if browser_operation_id:
            result["browser_operation_id"] = browser_operation_id

    if chunk_type == "tool_result":
        result["tool_name"] = chunk.get("tool_name")
        result["tool_result"] = chunk.get("tool_result", "")
        if chunk.get("call_id"):
            result["call_id"] = chunk.get("call_id")
        if chunk.get("tool_error"):
            result["tool_error"] = chunk.get("tool_error")
        if chunk.get("screenshot_url"):
            result["screenshot_url"] = chunk.get("screenshot_url")
        if chunk.get("screenshot"):
            result["screenshot"] = chunk.get("screenshot")
        if browser_operation_id:
            result["browser_operation_id"] = browser_operation_id

    if chunk.get("error"):
        result["error"] = chunk["error"]
    if browser_operation_id and chunk_type not in {"tool_call", "tool_result"}:
        result["browser_operation_id"] = browser_operation_id
    
    return result


def build_stream_error_done_chunk() -> Dict[str, Any]:
    """SSE done chunk for stream error fallback path."""
    return {
        "text": "",
        "chunk_type": "done",
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "finish_reason": "error",
    }


def resolve_persona_system_prompt(
    db: Session,
    user_id: str,
    persona_id: Optional[str]
) -> Optional[str]:
    """
    Resolve persona system prompt from backend single source (database).
    """
    if not persona_id:
        return None

    persona = db.query(DBPersona).filter(
        DBPersona.id == persona_id,
        DBPersona.user_id == user_id
    ).first()

    if not persona:
        logger.warning(f"[Chat] Persona not found or unauthorized: user_id={user_id}, persona_id={persona_id}")
        return None

    system_prompt = (persona.system_prompt or "").strip()
    if not system_prompt:
        logger.warning(f"[Chat] Persona has empty system prompt: user_id={user_id}, persona_id={persona_id}")
        return None

    return system_prompt


def _is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def _extract_mcp_server_map(root: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    mcp_servers = root.get("mcpServers")
    if _is_plain_object(mcp_servers):
        return {
            str(key): value
            for key, value in mcp_servers.items()
            if _is_plain_object(value)
        }

    # 兼容 root 直接是 server map 的格式
    if root and all(_is_plain_object(value) for value in root.values()):
        return {
            str(key): value
            for key, value in root.items()
            if _is_plain_object(value)
        }

    return {}


def _parse_mcp_server_type(raw_type: Optional[str], server_config: Dict[str, Any]) -> MCPServerType:
    normalized = (raw_type or "").strip().lower()
    if normalized in {"stdio"}:
        return MCPServerType.STDIO
    if normalized in {"sse"}:
        return MCPServerType.SSE
    if normalized in {"http"}:
        return MCPServerType.HTTP
    if normalized in {"streamablehttp", "streamable_http", "streamable-http"}:
        return MCPServerType.STREAMABLE_HTTP

    # 没显式类型时按字段推断
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
    server_type = _parse_mcp_server_type(
        server_config.get("serverType")
        or server_config.get("server_type")
        or server_config.get("type"),
        server_config
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


async def resolve_mcp_session_id(
    db: Session,
    user_id: str,
    mcp_server_key: str,
) -> Optional[str]:
    record = db.query(UserMcpConfig).filter(UserMcpConfig.user_id == user_id).first()
    if not record or not record.config_json:
        raise ValueError("No MCP config found for current user")

    try:
        root = json.loads(record.config_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid persisted MCP config JSON: {exc.msg}") from exc

    if not isinstance(root, dict):
        raise ValueError("MCP config root must be a JSON object")

    server_map = _extract_mcp_server_map(root)
    selected_server = server_map.get(mcp_server_key)
    if not selected_server:
        raise ValueError(f"MCP server '{mcp_server_key}' not found in user config")

    if selected_server.get("disabled") is True or selected_server.get("enabled") is False:
        raise ValueError(f"MCP server '{mcp_server_key}' is disabled")

    mcp_config = _build_mcp_server_config(selected_server)
    validate_mcp_stdio_command_policy(
        mcp_config,
        policy=settings.mcp_stdio_command_policy,
        allowed_commands=settings.mcp_stdio_allowed_commands,
        context=f"chat:{mcp_server_key}",
    )
    fingerprint = hashlib.sha256(
        json.dumps(selected_server, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    session_id = f"chat:{user_id}:{mcp_server_key}:{fingerprint}"

    manager = get_mcp_manager()
    await manager.create_session(session_id, mcp_config)
    return session_id


# ==================== API Endpoints ====================

@router.post("/{provider}/chat")
async def chat_with_provider(
    provider: str,
    request: ChatRequest,
    request_obj: Request,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat API endpoint for all providers.
    
    Supports both streaming and non-streaming responses.
    """
    try:
        attachment_count = len(request.attachments) if request.attachments else 0
        logger.info(
            f"[Chat] provider={provider}, "
            f"model={request.model_id}, "
            f"stream={request.stream}, "
            f"messages={len(request.messages)}, "
            f"attachments={attachment_count}, "
            f"user_id={user_id}"
        )

        if request.options:
            option_keys = set(request.options.model_dump(exclude_none=True).keys())
            validate_chat_option_keys(
                provider=provider,
                option_keys=option_keys,
            )
        
        # 从数据库获取 API key 和 base URL
        api_key, db_base_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request.api_key,
            request_base_url=request.options.base_url if request.options else None
        )
        
        # 优先使用数据库中的 base_url
        base_url = db_base_url
        if not base_url and request.options and request.options.base_url:
            base_url = request.options.base_url
        
        # Create provider service
        from ...services.common.provider_factory import ProviderFactory
        
        try:
            service = ProviderFactory.create(
                provider=provider,
                api_key=api_key,
                api_url=base_url,
                user_id=user_id,
                db=db,
                timeout=120.0
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        is_google_provider = provider in GOOGLE_PROVIDERS
        mcp_session_id: Optional[str] = None
        mcp_tool_names: List[str] = []
        mcp_function_declarations: List[Dict[str, Any]] = []
        if is_google_provider and request.options and request.options.mcp_server_key:
            try:
                mcp_session_id = await resolve_mcp_session_id(
                    db=db,
                    user_id=user_id,
                    mcp_server_key=request.options.mcp_server_key
                )
                try:
                    mcp_manager = get_mcp_manager()
                    gemini_tools = await mcp_manager.get_gemini_tools(mcp_session_id)
                    seen_names = set()
                    for tool_group in gemini_tools:
                        if not isinstance(tool_group, dict):
                            continue
                        for decl in tool_group.get("function_declarations", []):
                            if not isinstance(decl, dict):
                                continue
                            name = decl.get("name")
                            if not name or name in seen_names:
                                continue
                            seen_names.add(name)
                            mcp_tool_names.append(name)
                            mcp_function_declarations.append(
                                {
                                    "name": name,
                                    "description": decl.get("description", ""),
                                    "parameters": decl.get("parameters"),
                                }
                            )
                except Exception as tool_err:
                    logger.warning(
                        f"[Chat] Failed to list MCP tools for session={mcp_session_id}: {tool_err}"
                    )
                logger.info(
                    f"[Chat] MCP session ready for user_id={user_id}, "
                    f"mcp_server_key={request.options.mcp_server_key}, "
                    f"session_id={mcp_session_id}"
                )
            except MCPStdioPolicyError as exc:
                logger.warning(
                    f"[Chat] MCP stdio policy rejected for user_id={user_id}, "
                    f"mcp_server_key={request.options.mcp_server_key}: {exc}"
                )
                raise HTTPException(status_code=400, detail=f"MCP stdio policy violation: {exc}") from exc
            except ValueError as exc:
                logger.warning(
                    f"[Chat] Invalid MCP config for user_id={user_id}, "
                    f"mcp_server_key={request.options.mcp_server_key}: {exc}"
                )
                raise HTTPException(status_code=400, detail=f"Invalid MCP server config: {exc}") from exc
            except Exception as exc:
                logger.error(f"[Chat] Failed to initialize MCP session: {exc}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Failed to initialize MCP server: {exc}") from exc

        persona_system_prompt = resolve_persona_system_prompt(
            db=db,
            user_id=user_id,
            persona_id=request.options.persona_id if request.options else None
        )

        history_messages = list(request.messages)
        existing_system_prompts = [
            msg.content.strip()
            for msg in history_messages
            if msg.role == "system" and msg.content and msg.content.strip()
        ]
        google_system_instruction: Optional[str] = None

        if is_google_provider:
            # Google uses system_instruction config; remove system-role messages from history.
            system_parts: List[str] = []
            if persona_system_prompt:
                system_parts.append(persona_system_prompt)
            if mcp_tool_names:
                tools_text = ", ".join(mcp_tool_names)
                system_parts.append(
                    "当前会话已连接 MCP 数据工具。"
                    f"可用工具: {tools_text}。"
                    "当用户询问亚马逊类目、关键词、ASIN、趋势、评论、选品等实时电商数据时，"
                    "优先调用最匹配的 MCP 工具并严格遵循工具参数约束。"
                )
                if request.options and request.options.mcp_server_key and "sorftime" in request.options.mcp_server_key.lower():
                    system_parts.append(
                        "当前 MCP 覆盖跨境电商分析能力（如类目市场趋势、类目报告、核心关键词、"
                        "热搜词趋势、ASIN 明细/子体/评论、选品筛选等）。"
                        "涉及上述需求时优先工具调用，并在回答中明确站点、关键词/类目、时间范围与筛选条件。"
                    )
            system_parts.extend(existing_system_prompts)
            if system_parts:
                google_system_instruction = "\n\n".join(system_parts)

            history_messages = [msg for msg in history_messages if msg.role != "system"]
        elif persona_system_prompt:
            has_same_system_prompt = any(
                msg.role == "system" and msg.content and msg.content.strip() == persona_system_prompt
                for msg in history_messages
            )
            if not has_same_system_prompt:
                history_messages = [
                    Message(role="system", content=persona_system_prompt),
                    *history_messages
                ]

        # Convert messages
        messages = convert_messages_to_provider_format(
            history_messages,
            request.message,
            provider=provider,
            current_attachments=request.attachments
        )
        
        # Prepare options
        options = {}
        if request.options:
            if request.options.temperature is not None:
                options["temperature"] = request.options.temperature
            if request.options.max_tokens is not None:
                options["max_tokens"] = request.options.max_tokens
            if request.options.top_p is not None:
                options["top_p"] = request.options.top_p
            if request.options.top_k is not None:
                options["top_k"] = request.options.top_k
            if request.options.frequency_penalty is not None:
                options["frequency_penalty"] = request.options.frequency_penalty
            if request.options.presence_penalty is not None:
                options["presence_penalty"] = request.options.presence_penalty
            if request.options.seed is not None:
                options["seed"] = request.options.seed
            if request.options.stop is not None:
                options["stop"] = request.options.stop
            if request.options.response_format is not None:
                options["response_format"] = request.options.response_format
            if request.options.logit_bias is not None:
                options["logit_bias"] = request.options.logit_bias
            if request.options.n is not None:
                options["n"] = request.options.n
            if request.options.user is not None:
                options["user"] = request.options.user
            if request.options.enable_search:
                options["enable_search"] = request.options.enable_search
            if request.options.enable_thinking:
                options["enable_thinking"] = request.options.enable_thinking
            if request.options.enable_code_execution:
                options["enable_code_execution"] = request.options.enable_code_execution
            if request.options.enable_browser:
                options["enable_browser"] = request.options.enable_browser
            if request.options.enable_grounding:
                options["enable_grounding"] = request.options.enable_grounding
            if is_google_provider and google_system_instruction:
                options["system_instruction"] = google_system_instruction
            if is_google_provider and mcp_session_id:
                options["mcp_session_id"] = mcp_session_id
            if is_google_provider and mcp_function_declarations:
                options["additional_function_declarations"] = mcp_function_declarations
        if is_google_provider:
            options["user_id"] = user_id
        
        # Streaming response
        if request.stream:
            async def generate():
                try:
                    async for chunk in service.stream_chat(
                        messages=messages,
                        model=request.model_id,
                        **options
                    ):
                        frontend_chunk = convert_chunk_to_frontend_format(chunk)
                        chunk_type = frontend_chunk.get("chunk_type", "content")

                        if chunk_type == "done":
                            usage = frontend_chunk.get("usage", {})
                            logger.info(
                                f"[Chat] {provider} usage: "
                                f"prompt={usage.get('prompt_tokens', 0)}, "
                                f"completion={usage.get('completion_tokens', 0)}, "
                                f"total={usage.get('total_tokens', 0)}"
                            )

                        yield encode_sse_data(frontend_chunk, camel_case=True)
                
                except Exception as e:
                    logger.error(f"[Chat] Stream error: {e}", exc_info=True)
                    error_chunk = build_safe_error_chunk(
                        code="stream_error",
                        message="Stream processing failed",
                        details={"provider": provider, "mode": "chat"},
                        retryable=True,
                    )
                    yield encode_sse_data(error_chunk, camel_case=True)
                    yield encode_sse_data(build_stream_error_done_chunk(), camel_case=True)
            
            return create_sse_response(generate(), heartbeat_interval=15.0)
        
        # Non-streaming response
        else:
            response = await service.chat(
                messages=messages,
                model=request.model_id,
                **options
            )
            
            if response.get("usage"):
                usage = response["usage"]
                logger.info(
                    f"[Chat] {provider} usage: "
                    f"prompt={usage.get('prompt_tokens', 0)}, "
                    f"completion={usage.get('completion_tokens', 0)}, "
                    f"total={usage.get('total_tokens', 0)}"
                )
            
            return response
    
    except ProviderParamValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_http_detail())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Chat] Request error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
