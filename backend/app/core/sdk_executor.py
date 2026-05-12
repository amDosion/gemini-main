"""
Dedicated SDK ThreadPool Executor

Provides a dedicated ThreadPoolExecutor for vendor SDK blocking calls
(Gemini / OpenAI / Tongyi / DashScope), isolating them from the default
asyncio executor (which is shared with other ``asyncio.to_thread`` users
like file I/O and JSON parsing).

Why a dedicated pool:
- ``asyncio.to_thread`` uses the default executor with only
  ``min(32, os.cpu_count() + 4)`` threads. Under high concurrency, SDK
  calls queue waiting for threads while contending with non-SDK work.
- Vendor SDKs typically perform long-running HTTP I/O (image gen, video
  gen, polling) where a separate, larger pool prevents head-of-line
  blocking.

Pool size is configurable via the ``SDK_THREAD_POOL_SIZE`` env var.
Defaults to ``max(8, min(64, (cpu_count or 4) * 4))``.

The pool is created lazily on first use and shut down via ``atexit`` as
a safety net; FastAPI's lifespan should call :func:`shutdown_sdk_executor`
on graceful shutdown.
"""

from __future__ import annotations

import asyncio
import atexit
import os
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import Any, Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")

_SDK_POOL: Optional[ThreadPoolExecutor] = None


def _max_workers() -> int:
    """Compute the SDK pool size.

    Honors ``SDK_THREAD_POOL_SIZE`` env var (clamped to a minimum of 4),
    otherwise scales with CPU count: ``max(8, min(64, cpu*4))``.
    """
    env = os.getenv("SDK_THREAD_POOL_SIZE")
    if env and env.isdigit():
        return max(4, int(env))
    cpu = os.cpu_count() or 4
    return max(8, min(64, cpu * 4))


def get_sdk_executor() -> ThreadPoolExecutor:
    """Return the dedicated SDK ThreadPoolExecutor (lazy-init)."""
    global _SDK_POOL
    if _SDK_POOL is None:
        _SDK_POOL = ThreadPoolExecutor(
            max_workers=_max_workers(),
            thread_name_prefix="sdk",
        )
    return _SDK_POOL


async def run_in_sdk_thread(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Like :func:`asyncio.to_thread` but uses the dedicated SDK pool.

    Preserves :mod:`contextvars` semantics so logger context, tracing
    context, request-scoped state, etc., propagate to the worker thread
    — matching the behavior of ``asyncio.to_thread``.

    Args:
        func: The synchronous callable to run in the SDK pool.
        *args: Positional arguments forwarded to ``func``.
        **kwargs: Keyword arguments forwarded to ``func``.

    Returns:
        The result of ``func(*args, **kwargs)``.
    """
    loop = asyncio.get_running_loop()
    ctx = copy_context()
    # ``ctx.run`` accepts only positional callable+args; bind kwargs via lambda.
    if kwargs:
        def _call() -> T:
            return ctx.run(lambda: func(*args, **kwargs))
    else:
        def _call() -> T:
            return ctx.run(func, *args)
    return await loop.run_in_executor(get_sdk_executor(), _call)


def shutdown_sdk_executor() -> None:
    """Shut down the SDK pool if it has been created.

    Idempotent — safe to call from both FastAPI lifespan and ``atexit``.
    """
    global _SDK_POOL
    if _SDK_POOL is not None:
        try:
            _SDK_POOL.shutdown(wait=False, cancel_futures=False)
        finally:
            _SDK_POOL = None


# Safety net: ensure shutdown if the lifespan handler is bypassed.
atexit.register(shutdown_sdk_executor)
