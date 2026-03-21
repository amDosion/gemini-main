from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.dependencies import get_rate_limiter, get_research_cache, get_validator, require_current_user
from ...services.common.interactions_event_utils import serialize_usage
from ...services.common.interactions_manager import get_interactions_manager
from ...services.common.model_capabilities import is_deep_research_model
from ...services.llm import ProviderCredentialsResolver
from ...utils.error_handler import handle_gemini_error
from ...utils.performance_metrics import performance_metrics
from ...utils.prompt_security_validator import PromptSecurityValidator
from ...utils.rate_limiter import RateLimiter
from ...utils.research_cache import ResearchCache

# Reuse canonical deep-research tool normalization from stream router.
from .research_stream import _normalize_deep_research_tools

router = APIRouter(prefix="/api/research", tags=["research"])
logger = logging.getLogger(__name__)
credentials_resolver = ProviderCredentialsResolver()


class ResearchStartRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=10000)
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True
    format: Optional[str] = None
    include_private_data: bool = False
    file_search_store_names: Optional[List[str]] = None
    language: Optional[str] = None
    tone: Optional[str] = None


class ResearchStartResponse(BaseModel):
    interaction_id: str
    status: str
    cached: bool = False


class ResearchStatusResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[str] = None
    usage: Optional[dict] = None


class ResearchContinueRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=10000)
    agent: str = "deep-research-pro-preview-12-2025"
    background: bool = True


class ResearchFollowupRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=5000)


class ResearchSummarizeRequest(BaseModel):
    format: Optional[str] = "markdown"
    max_length: Optional[int] = 1000


class ResearchFormatRequest(BaseModel):
    output_format: str = Field(..., description="Output format (json, xml, yaml, etc.)")
    output_schema: Optional[dict] = Field(None, description="Custom output schema")


def _ensure_safe_prompt(
    validator: PromptSecurityValidator,
    prompt: str,
) -> None:
    is_safe, warnings = validator.validate_prompt(prompt)
    if is_safe:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "error": "INVALID_ARGUMENT",
            "message": "输入包含不安全内容",
            "warnings": warnings,
        },
    )


def _build_prompt(request: ResearchStartRequest) -> str:
    full_prompt = request.prompt

    if request.format:
        full_prompt += f"\n\n{request.format}"

    if request.language:
        full_prompt += f"\n\nPlease respond in {request.language}."

    if request.tone:
        tone_instructions = {
            "professional": "Use a professional and formal tone.",
            "casual": "Use a casual and conversational tone.",
            "technical": "Use technical language appropriate for experts.",
        }
        full_prompt += f"\n\n{tone_instructions.get(request.tone, '')}"

    return full_prompt


def _collect_texts(value: Any, bucket: List[str], depth: int = 0) -> None:
    if depth > 8 or value is None:
        return
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            bucket.append(stripped)
        return
    if isinstance(value, list):
        for item in value:
            _collect_texts(item, bucket, depth + 1)
        return
    if isinstance(value, dict):
        direct_text = value.get("text")
        if isinstance(direct_text, str) and direct_text.strip():
            bucket.append(direct_text.strip())
        for key in ("content", "parts", "result", "output", "outputs", "delta"):
            if key in value:
                _collect_texts(value[key], bucket, depth + 1)


def _extract_result(outputs: Any) -> str:
    if not isinstance(outputs, list):
        return ""
    fragments: List[str] = []
    _collect_texts(outputs, fragments, 0)
    dedup: List[str] = []
    seen = set()
    for item in fragments:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return "\n\n".join(dedup).strip()


def _extract_progress(outputs: Any) -> str:
    if not isinstance(outputs, list) or not outputs:
        return "Research in progress..."

    for output in reversed(outputs):
        if not isinstance(output, dict):
            continue
        output_type = str(output.get("type") or "").strip().lower()
        if output_type in {"status_update", "thought_summary"}:
            texts: List[str] = []
            _collect_texts(output, texts, 0)
            if texts:
                return texts[-1]
    return "Research in progress..."


async def _resolve_google_api_key(db: Session, user_id: str) -> str:
    api_key, _ = await credentials_resolver.resolve(
        provider_id="google",
        db=db,
        user_id=user_id,
    )
    key_text = str(api_key or "").strip()
    if not key_text:
        raise HTTPException(status_code=401, detail="Google provider credentials not configured")
    return key_text


def _build_research_tools(
    *,
    include_private_data: bool,
    file_search_store_names: Optional[List[str]],
) -> List[Dict[str, Any]]:
    requested_tools: Optional[List[Dict[str, Any]]] = None
    if include_private_data and isinstance(file_search_store_names, list) and file_search_store_names:
        requested_tools = [
            {
                "type": "file_search",
                "file_search_store_names": file_search_store_names,
            }
        ]
    return _normalize_deep_research_tools(
        requested_tools=requested_tools,
        file_search_store_names=file_search_store_names,
    )


async def _ensure_interaction_completed(
    *,
    manager: Any,
    api_key: str,
    interaction_id: str,
) -> Dict[str, Any]:
    result = await manager.get_interaction_status_async(
        api_key=api_key,
        interaction_id=interaction_id,
        vertexai=False,
        user_id=None,
    )
    status = str(result.get("status") or "").strip().lower()
    if status != "completed":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_ARGUMENT",
                "message": f"Previous interaction must be completed (current status: {status or 'unknown'})",
            },
        )
    return result


@router.post("/start", response_model=ResearchStartResponse)
async def start_research(
    request: ResearchStartRequest,
    user_id: str = Depends(require_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_research_cache),
    validator: PromptSecurityValidator = Depends(get_validator),
    db: Session = Depends(get_db),
):
    """Start a deep research task via canonical interactions flow."""

    start_time = time.time()
    success = False

    try:
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试",
                    "suggestions": ["等待1分钟后重试", "减少请求频率"],
                },
            )

        _ensure_safe_prompt(validator, request.prompt)

        agent_id = str(request.agent or "").strip()
        if not is_deep_research_model("google", agent_id):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_DEEP_RESEARCH_AGENT",
                    "message": "Selected agent does not support Deep Research",
                    "agent": agent_id,
                },
            )

        performance_metrics.record_cache_miss()

        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        result = await manager.create_interaction(
            input=_build_prompt(request),
            api_key=api_key,
            agent=agent_id,
            background=True,
            store=True,
            tools=_build_research_tools(
                include_private_data=request.include_private_data,
                file_search_store_names=request.file_search_store_names,
            ),
            agent_config=None,
            vertexai=False,
            user_id=None,
        )

        interaction_id = str(result.get("id") or "").strip()
        interaction_status = str(result.get("status") or "running").strip().lower() or "running"
        if not interaction_id:
            raise HTTPException(status_code=500, detail="Failed to get interaction_id")

        cache.cache_interaction(
            interaction_id,
            {
                "prompt": request.prompt,
                "status": interaction_status,
                "created_at": datetime.now().isoformat(),
            },
            ttl=3600,
        )

        success = True
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success)

        return ResearchStartResponse(
            interaction_id=interaction_id,
            status=interaction_status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(exc)


@router.get("/status/{interaction_id}", response_model=ResearchStatusResponse)
async def get_research_status(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    cache: ResearchCache = Depends(get_research_cache),
    db: Session = Depends(get_db),
):
    """Get research task status via canonical interactions flow."""

    cached_interaction = cache.get_cached_interaction(interaction_id)
    if cached_interaction and cached_interaction.get("status") == "completed":
        return ResearchStatusResponse(
            status="completed",
            result=str(cached_interaction.get("result") or ""),
        )

    try:
        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        result = await manager.get_interaction_status_async(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=False,
            user_id=None,
        )

        status = str(result.get("status") or "").strip().lower() or "in_progress"
        outputs = result.get("outputs") or []

        if status == "completed":
            result_text = _extract_result(outputs)
            cache.cache_interaction(
                interaction_id,
                {
                    "status": "completed",
                    "result": result_text,
                    "completed_at": datetime.now().isoformat(),
                },
                ttl=3600,
            )
            if cached_interaction and cached_interaction.get("prompt"):
                prompt_hash = hashlib.sha256(str(cached_interaction["prompt"]).encode()).hexdigest()
                cache.cache_research_result(
                    prompt_hash,
                    result_text,
                    ttl=86400,
                )
            return ResearchStatusResponse(
                status="completed",
                result=result_text,
                usage=serialize_usage(result.get("usage")) if result.get("usage") else None,
            )

        if status in {"failed", "cancelled"}:
            error_message = str(result.get("error") or "Research task failed")
            return ResearchStatusResponse(status=status, error=error_message)

        return ResearchStatusResponse(
            status="in_progress",
            progress=_extract_progress(outputs),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_gemini_error(exc)


@router.post("/cancel/{interaction_id}")
async def cancel_research(
    interaction_id: str,
    user_id: str = Depends(require_current_user),
    cache: ResearchCache = Depends(get_research_cache),
    db: Session = Depends(get_db),
):
    """Cancel research task."""

    try:
        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        await manager.cancel_interaction(
            api_key=api_key,
            interaction_id=interaction_id,
            vertexai=False,
        )
        cache.delete_cached_interaction(interaction_id)
        return {"message": "Research task cancelled"}
    except HTTPException:
        raise
    except Exception as exc:
        raise handle_gemini_error(exc)


@router.post("/continue/{interaction_id}", response_model=ResearchStartResponse)
async def continue_research(
    interaction_id: str,
    request: ResearchContinueRequest,
    user_id: str = Depends(require_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_research_cache),
    validator: PromptSecurityValidator = Depends(get_validator),
    db: Session = Depends(get_db),
):
    """Continue research from previous interaction with previous_interaction_id."""

    start_time = time.time()
    success = False

    try:
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后重试",
                    "suggestions": ["等待1分钟后重试", "减少请求频率"],
                },
            )

        _ensure_safe_prompt(validator, request.prompt)
        agent_id = str(request.agent or "").strip()
        if not is_deep_research_model("google", agent_id):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_DEEP_RESEARCH_AGENT",
                    "message": "Selected agent does not support Deep Research",
                    "agent": agent_id,
                },
            )

        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        await _ensure_interaction_completed(
            manager=manager,
            api_key=api_key,
            interaction_id=interaction_id,
        )

        result = await manager.create_interaction(
            input=request.prompt,
            api_key=api_key,
            agent=agent_id,
            background=bool(request.background),
            store=True,
            tools=[{"type": "google_search"}],
            agent_config=None,
            previous_interaction_id=interaction_id,
            vertexai=False,
            user_id=None,
        )

        new_interaction_id = str(result.get("id") or "").strip()
        new_status = str(result.get("status") or "running").strip().lower() or "running"
        if not new_interaction_id:
            raise HTTPException(status_code=500, detail="Failed to create continuation interaction")

        cache.cache_interaction(
            new_interaction_id,
            {
                "prompt": request.prompt,
                "status": new_status,
                "previous_interaction_id": interaction_id,
                "created_at": datetime.now().isoformat(),
            },
            ttl=3600,
        )

        success = True
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success)
        return ResearchStartResponse(interaction_id=new_interaction_id, status=new_status)
    except HTTPException:
        raise
    except Exception as exc:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(exc)


@router.post("/followup/{interaction_id}", response_model=ResearchStartResponse)
async def followup_research(
    interaction_id: str,
    request: ResearchFollowupRequest,
    user_id: str = Depends(require_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_research_cache),
    validator: PromptSecurityValidator = Depends(get_validator),
    db: Session = Depends(get_db),
):
    """Ask follow-up question using previous_interaction_id context."""

    start_time = time.time()
    success = False

    try:
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={"error": "RATE_LIMIT_EXCEEDED", "message": "请求过于频繁，请稍后重试"},
            )

        _ensure_safe_prompt(validator, request.question)

        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        await _ensure_interaction_completed(
            manager=manager,
            api_key=api_key,
            interaction_id=interaction_id,
        )

        result = await manager.create_interaction(
            input=request.question,
            api_key=api_key,
            agent="gemini-2.5-flash",
            background=False,
            tools=None,
            agent_config=None,
            previous_interaction_id=interaction_id,
            vertexai=False,
            user_id=None,
        )

        new_interaction_id = str(result.get("id") or "").strip()
        new_status = str(result.get("status") or "running").strip().lower() or "running"
        if not new_interaction_id:
            raise HTTPException(status_code=500, detail="Failed to create follow-up interaction")

        cache.cache_interaction(
            new_interaction_id,
            {
                "question": request.question,
                "status": new_status,
                "previous_interaction_id": interaction_id,
                "created_at": datetime.now().isoformat(),
            },
            ttl=3600,
        )

        success = True
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success)
        return ResearchStartResponse(interaction_id=new_interaction_id, status=new_status)
    except HTTPException:
        raise
    except Exception as exc:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(exc)


@router.post("/summarize/{interaction_id}", response_model=ResearchStartResponse)
async def summarize_research(
    interaction_id: str,
    request: ResearchSummarizeRequest,
    user_id: str = Depends(require_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_research_cache),
    db: Session = Depends(get_db),
):
    """Summarize research results with lightweight model in same interaction chain."""

    start_time = time.time()
    success = False

    try:
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={"error": "RATE_LIMIT_EXCEEDED", "message": "请求过于频繁，请稍后重试"},
            )

        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        await _ensure_interaction_completed(
            manager=manager,
            api_key=api_key,
            interaction_id=interaction_id,
        )

        summarize_prompt = f"Please provide a concise summary of the research findings in {request.format} format"
        if request.max_length:
            summarize_prompt += f", limited to approximately {request.max_length} words"
        summarize_prompt += "."

        result = await manager.create_interaction(
            input=summarize_prompt,
            api_key=api_key,
            agent="gemini-2.5-flash",
            background=False,
            tools=None,
            agent_config=None,
            previous_interaction_id=interaction_id,
            vertexai=False,
            user_id=None,
        )

        new_interaction_id = str(result.get("id") or "").strip()
        new_status = str(result.get("status") or "running").strip().lower() or "running"
        if not new_interaction_id:
            raise HTTPException(status_code=500, detail="Failed to create summarize interaction")

        cache.cache_interaction(
            new_interaction_id,
            {
                "type": "summarize",
                "format": request.format,
                "status": new_status,
                "previous_interaction_id": interaction_id,
                "created_at": datetime.now().isoformat(),
            },
            ttl=3600,
        )

        success = True
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success)
        return ResearchStartResponse(interaction_id=new_interaction_id, status=new_status)
    except HTTPException:
        raise
    except Exception as exc:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(exc)


@router.post("/format/{interaction_id}", response_model=ResearchStartResponse)
async def format_research(
    interaction_id: str,
    request: ResearchFormatRequest,
    user_id: str = Depends(require_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    cache: ResearchCache = Depends(get_research_cache),
    db: Session = Depends(get_db),
):
    """Format research results with lightweight model in same interaction chain."""

    start_time = time.time()
    success = False

    try:
        if not await rate_limiter.check_rate_limit(user_id, max_requests=60, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail={"error": "RATE_LIMIT_EXCEEDED", "message": "请求过于频繁，请稍后重试"},
            )

        api_key = await _resolve_google_api_key(db=db, user_id=user_id)
        manager = get_interactions_manager(db=db, default_vertexai=False)
        await _ensure_interaction_completed(
            manager=manager,
            api_key=api_key,
            interaction_id=interaction_id,
        )

        format_prompt = f"Please format the research findings as {request.output_format.upper()}"
        if request.output_schema:
            format_prompt += f" following this schema: {request.output_schema}"
        format_prompt += "."

        result = await manager.create_interaction(
            input=format_prompt,
            api_key=api_key,
            agent="gemini-2.5-flash",
            background=False,
            tools=None,
            agent_config=None,
            previous_interaction_id=interaction_id,
            vertexai=False,
            user_id=None,
        )

        new_interaction_id = str(result.get("id") or "").strip()
        new_status = str(result.get("status") or "running").strip().lower() or "running"
        if not new_interaction_id:
            raise HTTPException(status_code=500, detail="Failed to create format interaction")

        cache.cache_interaction(
            new_interaction_id,
            {
                "type": "format",
                "output_format": request.output_format,
                "status": new_status,
                "previous_interaction_id": interaction_id,
                "created_at": datetime.now().isoformat(),
            },
            ttl=3600,
        )

        success = True
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success)
        return ResearchStartResponse(interaction_id=new_interaction_id, status=new_status)
    except HTTPException:
        raise
    except Exception as exc:
        response_time = time.time() - start_time
        performance_metrics.record_request(response_time, success=False)
        raise handle_gemini_error(exc)
