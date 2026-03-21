"""Health check routes."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

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
    """Probe redis readiness via ping."""
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


def _sanitize_component_for_public(component: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {
        "status": component.get("status"),
        "latency_ms": component.get("latency_ms"),
    }
    status = str(component.get("status") or "").strip().lower()
    if status == "error":
        sanitized["error"] = "component check failed"
    elif status == "timeout":
        sanitized["error"] = "component check timed out"
    return sanitized


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

    if include_internal_errors:
        components = raw_components
    else:
        components = {name: _sanitize_component_for_public(result) for name, result in raw_components.items()}
        for name, result in raw_components.items():
            if result.get("error"):
                logger.warning(
                    "[Health] component check failed: component=%s status=%s error=%s",
                    name,
                    result.get("status"),
                    result.get("error"),
                )

    return {
        "status": _derive_overall_status(raw_components),
        "components": components,
        "selenium": SELENIUM_AVAILABLE,
        "pdf_extraction": PDF_EXTRACTION_AVAILABLE,
        "embedding": EMBEDDING_AVAILABLE,
        "upload_worker_pool": WORKER_POOL_AVAILABLE,
        "version": "1.0.0",
    }


@router.get("/")
async def root():
    """根路径健康检查端点"""
    return {
        "status": "ok",
        "message": "Gemini Chat Backend API",
        "selenium_available": SELENIUM_AVAILABLE,
        "pdf_extraction_available": PDF_EXTRACTION_AVAILABLE,
        "embedding_available": EMBEDDING_AVAILABLE,
        "upload_worker_pool_available": WORKER_POOL_AVAILABLE
    }


@router.get("/health")
async def health_check():
    """详细健康检查端点（含依赖组件健康状态）"""
    return await build_health_payload(include_internal_errors=False)
