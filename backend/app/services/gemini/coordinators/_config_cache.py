"""
Shared TTL cache for coordinator `_load_config` DB reads.

Multiple coordinators (ImagenCoordinator, ImageEditCoordinator,
VideoUnderstandingCoordinator, VideoGenerationCoordinator) all read the
same per-user rows from `VertexAIConfig`, `ConfigProfile` (provider='google'),
and `UserSettings`. When a request fans out to multiple coordinators within
the same user request, each coordinator was re-issuing the same SELECT.

This module provides a process-wide TTL cache (60s, max 512 entries) keyed
by `(user_id, kind, *extra)` where `kind` describes which row is being
fetched. The cache stores plain dicts of column values (NOT ORM rows), so
they're safe to share across sessions without detached-instance hazards.

Call `clear_config_cache(user_id=...)` after writes to invalidate.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Module-level singleton — intentionally NOT on `self`.
# 60s TTL is short enough to pick up config changes quickly while still
# coalescing the per-request fan-out across coordinators.
_CACHE: TTLCache = TTLCache(maxsize=512, ttl=60)
_LOCK = threading.RLock()

# Per-key load locks so concurrent get_or_load() calls for the SAME key
# collapse to a single loader() invocation (avoids the TOCTOU stampede where
# every racing caller observed a miss and re-issued the same DB read), while
# distinct keys still load in parallel.
_KEY_LOCKS: Dict[Tuple[Any, ...], threading.Lock] = {}

# Sentinel to distinguish "cached None" (no row) from "cache miss"
_MISS = object()


def _make_key(user_id: str, kind: str, *extra: Any) -> Tuple[Any, ...]:
    return (str(user_id), str(kind), *extra)


def _get_key_lock(key: Tuple[Any, ...]) -> threading.Lock:
    """Return (creating if needed) the dedicated load lock for `key`."""
    with _LOCK:
        lock = _KEY_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _KEY_LOCKS[key] = lock
        return lock


def get_or_load(
    user_id: Optional[str],
    kind: str,
    loader: Callable[[], Optional[Dict[str, Any]]],
    *extra: Any,
) -> Optional[Dict[str, Any]]:
    """
    Return cached row dict for (user_id, kind, *extra), or run `loader()`
    and cache its result.

    `loader` MUST return either a plain dict of column values (snapshot
    of the DB row) or None. Returning ORM rows is not supported because
    they may carry a detached session reference.

    If `user_id` is falsy, caching is skipped (loader runs every time).
    """
    if not user_id:
        return loader()

    key = _make_key(user_id, kind, *extra)

    # Fast path: serve a hit without taking the per-key load lock.
    with _LOCK:
        cached = _CACHE.get(key, _MISS)
    if cached is not _MISS:
        return cached  # type: ignore[return-value]

    # Miss: serialize loaders for THIS key so concurrent callers collapse to a
    # single DB read. Different keys use different locks and still run in
    # parallel.
    key_lock = _get_key_lock(key)
    with key_lock:
        # Double-check: another thread may have populated the cache while we
        # were waiting on `key_lock`.
        with _LOCK:
            cached = _CACHE.get(key, _MISS)
        if cached is not _MISS:
            return cached  # type: ignore[return-value]

        value = loader()
        with _LOCK:
            _CACHE[key] = value
        return value


def clear_config_cache(
    user_id: Optional[str] = None,
    kind: Optional[str] = None,
) -> None:
    """
    Invalidate cached config entries.

    - `clear_config_cache()` — wipe everything.
    - `clear_config_cache(user_id="u1")` — wipe all entries for one user.
    - `clear_config_cache(user_id="u1", kind="vertex_ai")` — wipe one kind.
    """
    with _LOCK:
        if user_id is None and kind is None:
            _CACHE.clear()
            _prune_idle_key_locks()
            return
        target_user = None if user_id is None else str(user_id)
        target_kind = None if kind is None else str(kind)
        # Snapshot keys since we mutate the dict during iteration.
        keys = list(_CACHE.keys())
        for key in keys:
            if not isinstance(key, tuple) or len(key) < 2:
                continue
            key_user, key_kind = key[0], key[1]
            if target_user is not None and key_user != target_user:
                continue
            if target_kind is not None and key_kind != target_kind:
                continue
            _CACHE.pop(key, None)
        _prune_idle_key_locks()


def _prune_idle_key_locks() -> None:
    """
    Drop per-key locks that are not currently held and whose cache entry is
    gone, keeping `_KEY_LOCKS` bounded. Caller MUST hold `_LOCK`.

    A lock that another thread is mid-load on (held) is skipped via a
    non-blocking acquire probe so we never delete a lock in active use.
    """
    for lock_key in list(_KEY_LOCKS.keys()):
        if lock_key in _CACHE:
            continue
        lock = _KEY_LOCKS.get(lock_key)
        if lock is None:
            continue
        if lock.acquire(blocking=False):
            try:
                _KEY_LOCKS.pop(lock_key, None)
            finally:
                lock.release()
