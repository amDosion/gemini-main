"""Health check routes."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from ...utils.log_sanitization import summarize_text_for_log

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"

# 服务可用性标志（在 main.py 中通过 set_availability() 设置）
SELENIUM_AVAILABLE = False
PDF_EXTRACTION_AVAILABLE = False
EMBEDDING_AVAILABLE = False
WORKER_POOL_AVAILABLE = False


def _load_component_timeout_ms() -> int:
    raw = os.getenv("HEALTH_COMPONENT_TIMEOUT_MS", "1500")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 1500
    return max(100, value)


HEALTH_COMPONENT_TIMEOUT_MS = _load_component_timeout_ms()
ComponentChecker = Callable[[], Awaitable[None]]


class RootResponse(BaseModel):
    status: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    message: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    version: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)


class PublicHealthResponse(BaseModel):
    status: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    version: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)


def set_availability(
    selenium: bool,
    pdf: bool,
    embedding: bool,
    worker_pool: bool = False
):
    """
    设置服务可用性标志
    
    Args:
        selenium: Selenium 浏览器服务是否可用
        pdf: PDF 提取服务是否可用
        embedding: 向量嵌入服务是否可用
        worker_pool: 上传 Worker 池是否可用
    """
    global SELENIUM_AVAILABLE, PDF_EXTRACTION_AVAILABLE, EMBEDDING_AVAILABLE, WORKER_POOL_AVAILABLE
    SELENIUM_AVAILABLE = selenium
    PDF_EXTRACTION_AVAILABLE = pdf
    EMBEDDING_AVAILABLE = embedding
    WORKER_POOL_AVAILABLE = worker_pool


def _normalize_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


async def _close_redis_client(client: Any) -> None:
    close_func = getattr(client, "aclose", None)
    if callable(close_func):
        await close_func()
        return
    await client.close()


async def _check_db() -> None:
    """Probe database readiness with a lightweight query."""

    def _probe() -> None:
        from ...core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    await asyncio.to_thread(_probe)


async def _check_redis() -> None:
    """Probe redis readiness via ping.

    Prefer the application-wide :class:`GlobalRedisConnectionPool` so health
    checks reuse the existing connection (no per-call socket setup). Fall back
    to a one-shot ``redis.from_url`` only when the global pool is not
    initialized (e.g. very early in app startup or in tests that skip pool
    bootstrap).
    """
    from ...services.common.redis_queue_service import GlobalRedisConnectionPool

    pool = GlobalRedisConnectionPool.get_instance()
    if pool.is_initialized():
        client = pool.get_connection()
        if client is not None:
            await client.ping()
            return

    # Fallback: pool not yet initialized — issue a one-shot ping using a
    # transient client. Keep behavior identical to the previous implementation
    # so health output is unchanged on cold-start.
    import redis.asyncio as redis

    from ...core.config import settings

    client = redis.from_url(settings.redis_url, decode_responses=False)
    try:
        await client.ping()
    finally:
        await _close_redis_client(client)


async def _check_provider() -> None:
    """Probe provider layer readiness by ensuring registry can initialize."""

    def _probe() -> None:
        from ...services.common.provider_factory import ProviderFactory

        providers = ProviderFactory.list_providers()
        if not providers:
            raise RuntimeError("no providers registered")

    await asyncio.to_thread(_probe)


async def _run_component_check(
    name: str,
    checker: ComponentChecker,
    timeout_ms: int,
) -> tuple[str, Dict[str, Any]]:
    started = time.perf_counter()
    error: str | None = None
    status = "ok"

    try:
        await asyncio.wait_for(checker(), timeout=timeout_ms / 1000)
    except asyncio.TimeoutError:
        status = "timeout"
        error = f"check timed out after {timeout_ms}ms"
    except Exception as exc:  # noqa: BLE001 - health endpoint should not raise
        status = "error"
        error = _normalize_error(exc)

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    result: Dict[str, Any] = {
        "status": status,
        "latency_ms": latency_ms,
    }
    if error:
        result["error"] = error
    return name, result


def _derive_overall_status(components: Dict[str, Dict[str, Any]]) -> str:
    if all(component.get("status") == "ok" for component in components.values()):
        return "healthy"
    return "degraded"


async def build_health_payload(*, include_internal_errors: bool = False) -> Dict[str, Any]:
    """Build health payload for public (/health) and admin views."""
    checks: tuple[tuple[str, ComponentChecker], ...] = (
        ("db", _check_db),
        ("redis", _check_redis),
        ("provider", _check_provider),
    )
    check_results = await asyncio.gather(
        *(
            _run_component_check(name, checker, HEALTH_COMPONENT_TIMEOUT_MS)
            for name, checker in checks
        )
    )
    raw_components = {name: result for name, result in check_results}

    overall_status = _derive_overall_status(raw_components)

    if not include_internal_errors:
        for name, result in raw_components.items():
            if result.get("error"):
                logger.warning(
                    "[Health] component check failed: component=%s status=%s error=%s",
                    name,
                    result.get("status"),
                    result.get("error"),
                )
        return {
            "status": overall_status,
            "version": "1.0.0",
        }

    return {
        "status": overall_status,
        "components": raw_components,
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,
        "embedding": EMBEDDING_AVAILABLE,
        "upload_worker_pool": WORKER_POOL_AVAILABLE,
        "gemini_pool": _gemini_pool_health(),
        "version": "1.0.0",
    }


def _gemini_pool_health() -> Dict[str, Any]:
    """汇总 GeminiClientPool 健康状态用于 /health payload。

    仅暴露 4 个 boolean / int 字段（initialized / sdk_available / active_clients
    / max_size），不返回 cache_key、api_key_configured 等诊断字段——那些只在
    /api/system/admin/gemini-pool/stats 受 admin guard 保护后暴露。
    """
    try:
        from ...services.gemini.client_pool import (
            GOOGLE_GENAI_AVAILABLE,
            get_client_pool,
        )

        pool = get_client_pool()
        return {
            "initialized": getattr(pool, "_initialized", False),
            "sdk_available": bool(GOOGLE_GENAI_AVAILABLE),
            "active_clients": len(pool._clients),
            "max_size": pool._max_size,
        }
    except Exception as err:
        logger.warning(
            "[Health] gemini_pool health check failed: %s",
            summarize_text_for_log(err, label="error"),
        )
        return {
            "initialized": False,
            "sdk_available": False,
            "active_clients": 0,
            "max_size": 0,
            "error": "pool unavailable",
        }


@router.get("/", response_model=RootResponse, include_in_schema=False)
async def root():
    """Public root endpoint with no operational inventory."""
    return {
        "status": "ok",
        "message": "Gemini Chat Backend API",
        "version": "1.0.0",
    }


@router.get("/health", response_model=PublicHealthResponse)
async def health_check():
    """Public liveness endpoint. Detailed dependency state is admin-only."""
    return await build_health_payload(include_internal_errors=False)
