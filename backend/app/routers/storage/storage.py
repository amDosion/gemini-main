"""
云存储配置和上传路由
支持兰空图床和阿里云 OSS
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks, Response, Request, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, Any
from datetime import datetime
import uuid
import httpx
import os
import json
import mimetypes
import re
import time
import zipfile
from pathlib import Path
import logging
from urllib.parse import quote, urlparse
from fastapi.responses import FileResponse, StreamingResponse
import asyncio
import hashlib

from ...core.database import SessionLocal, get_db
from ...core.config import settings
from ...models.db_models import StorageConfig, ActiveStorage, UploadTask, ChatSession, MessageAttachment
from ...services.storage.storage_service import StorageService
from ...services.storage.storage_manager import StorageManager
from ...services.storage.local_provider import (
    DEFAULT_LOCAL_URL_PREFIX,
    resolve_local_public_file_path,
)
from ...services.common.redis_queue_service import redis_queue
from ...services.common.cache_service import CacheService
from ...core.dependencies import require_current_user, get_cache
from ...core.user_scoped_query import UserScopedQuery
from ...core.encryption import decrypt_config
from ...middleware.case_conversion_middleware import case_conversion_options
from ...utils.url_security import (
    UnsafeURLError,
    validate_outbound_http_url,
)

router = APIRouter(prefix="/api/storage", tags=["storage"])
logger = logging.getLogger(__name__)

_METADATA_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "avif", "heic", "heif", "tif", "tiff"
}
_METADATA_VIDEO_EXTENSIONS = {
    "mp4", "mov", "avi", "mkv", "webm", "m4v", "wmv", "flv", "ts", "m2ts"
}
_BROWSE_METADATA_BACKFILL_MAX_FETCH = 12
_BROWSE_METADATA_BACKFILL_FETCH_TIMEOUT_SECONDS = 4.0
_BROWSE_METADATA_BACKFILL_TOTAL_TIMEOUT_SECONDS = 8.0

# 导入路径工具
from ...core.path_utils import get_temp_dir, get_temp_dir_relative, resolve_relative_path, ensure_relative_path

# 项目内临时文件目录（使用统一的路径工具）
TEMP_DIR = get_temp_dir()
_STORAGE_REVISION_KEY_PREFIX = "storage:revision:"
_STORAGE_REVISION_TTL_SECONDS = 30 * 24 * 60 * 60
_STORAGE_DOWNLOAD_DIR = Path(TEMP_DIR) / "storage_downloads"
_STORAGE_DOWNLOAD_TTL_SECONDS = 6 * 60 * 60
_STORAGE_DOWNLOAD_BROWSE_LIMIT = 500
_STORAGE_DOWNLOAD_MAX_TOTAL_FILES = 500
_STORAGE_DOWNLOAD_MAX_FILE_BYTES = 512 * 1024 * 1024
_STORAGE_DOWNLOAD_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_STORAGE_DOWNLOAD_INVALID_NAME_PATTERN = re.compile(r'[\\/:*?"<>|]+')

# Startup log to verify TEMP_DIR (只记录一次)
if not hasattr(router, '_temp_dir_logged'):
    logger.info(f"[Storage Router] TEMP_DIR initialized: {TEMP_DIR}")
    router._temp_dir_logged = True

_STORAGE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
_AUTH_VARY_HEADER_VALUES = ("Authorization", "Cookie")


def _storage_revision_key(user_id: str) -> str:
    normalized_user_id = str(user_id or "").strip() or "default"
    return f"{_STORAGE_REVISION_KEY_PREFIX}{normalized_user_id}"


def _storage_browse_total_cache_key(
    user_id: str,
    storage_id: str,
    path: str,
    storage_revision: int | None = None,
) -> str:
    normalized_user_id = str(user_id or "").strip() or "default"
    normalized_storage_id = str(storage_id or "").strip() or "unknown"
    normalized_path = str(path or "").replace("\\", "/").strip().strip("/")
    try:
        revision = int(storage_revision) if storage_revision is not None else 0
    except (TypeError, ValueError):
        revision = 0
    digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:24]
    return f"cache:storage:browse-total:{normalized_user_id}:{normalized_storage_id}:{revision}:{digest}"


async def _get_storage_revision_redis():
    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        return redis_queue._redis
    except Exception:
        logger.debug("[StorageRevision] redis unavailable", exc_info=True)
        return None


async def _get_storage_revision(user_id: str) -> int:
    redis_conn = await _get_storage_revision_redis()
    if redis_conn is None:
        return 0

    try:
        raw_value = await redis_conn.get(_storage_revision_key(user_id))
        if raw_value is None:
            return 0
        return int(raw_value)
    except Exception:
        logger.debug("[StorageRevision] get revision failed", exc_info=True)
        return 0


async def _bump_storage_revision(user_id: str) -> int:
    redis_conn = await _get_storage_revision_redis()
    if redis_conn is None:
        return 0

    key = _storage_revision_key(user_id)
    try:
        # 获取旧 revision 用于清理旧缓存
        old_revision = await _get_storage_revision(user_id)
        next_revision = int(await redis_conn.incr(key))
        await redis_conn.expire(key, _STORAGE_REVISION_TTL_SECONDS)
        # 主动清理旧 revision 的缓存，不等 TTL 过期
        if old_revision and old_revision != next_revision:
            normalized_user_id = str(user_id or "").strip() or "default"
            old_pattern = f"cache:storage:*:{normalized_user_id}:*:{old_revision}:*"
            async for matched_key in redis_conn.scan_iter(match=old_pattern):
                await redis_conn.delete(matched_key)
        return next_revision
    except Exception:
        logger.debug("[StorageRevision] bump revision failed", exc_info=True)
        return await _get_storage_revision(user_id)


def _mask_url(url: str) -> str:
    try:
        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        creds, tail = rest.split("@", 1)
        if ":" not in creds:
            return url
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{tail}"
    except Exception:
        return url


def _validate_outbound_http_url(url: str) -> str:
    try:
        return validate_outbound_http_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _safe_get_with_redirect_guard(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = 5,
    allowed_hosts: set[str] | None = None,
) -> tuple[httpx.Response, str]:
    redirect_status_codes = {301, 302, 303, 307, 308}
    hosts_allowlist = allowed_hosts or set()
    current_url = _resolve_safe_preview_fetch_url(url, hosts_allowlist)
    redirect_count = 0

    while True:
        response = await client.get(current_url, follow_redirects=False)
        if response.status_code not in redirect_status_codes:
            return response, current_url

        if redirect_count >= max_redirects:
            raise HTTPException(status_code=400, detail=f"重定向次数超过限制 ({max_redirects})")

        location = str(response.headers.get("location") or "").strip()
        if not location:
            raise HTTPException(status_code=400, detail="重定向缺少 Location")

        try:
            next_url = str(httpx.URL(current_url).join(location))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="重定向目标非法") from exc

        current_url = _resolve_safe_preview_fetch_url(next_url, hosts_allowlist)
        redirect_count += 1


async def _open_safe_stream_with_redirect_guard(
    url: str,
    *,
    max_redirects: int = 5,
    allowed_hosts: set[str] | None = None,
    timeout: float = 30.0,
    request_headers: dict[str, str] | None = None,
) -> tuple[httpx.AsyncClient, httpx.Response, str]:
    redirect_status_codes = {301, 302, 303, 307, 308}
    hosts_allowlist = allowed_hosts or set()
    client = httpx.AsyncClient(timeout=timeout)

    try:
        current_url = _resolve_safe_preview_fetch_url(url, hosts_allowlist)
        redirect_count = 0

        while True:
            request = client.build_request("GET", current_url, headers=request_headers or None)
            response = await client.send(request, follow_redirects=False, stream=True)

            if response.status_code not in redirect_status_codes:
                return client, response, current_url

            if redirect_count >= max_redirects:
                await response.aclose()
                raise HTTPException(status_code=400, detail=f"重定向次数超过限制 ({max_redirects})")

            location = str(response.headers.get("location") or "").strip()
            await response.aclose()
            if not location:
                raise HTTPException(status_code=400, detail="重定向缺少 Location")

            try:
                next_url = str(httpx.URL(current_url).join(location))
            except Exception as exc:
                raise HTTPException(status_code=400, detail="重定向目标非法") from exc

            current_url = _resolve_safe_preview_fetch_url(next_url, hosts_allowlist)
            redirect_count += 1
    except Exception:
        await client.aclose()
        raise


async def _read_upstream_error_detail(response: httpx.Response) -> str:
    try:
        data = await response.aread()
    except Exception:
        return ""

    if not data:
        return ""
    try:
        return data.decode("utf-8", errors="replace").strip()[:300]
    except Exception:
        return ""


def _streaming_proxy_response(
    client: httpx.AsyncClient,
    upstream_response: httpx.Response,
    *,
    media_type: str,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> StreamingResponse:
    async def iterator():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        iterator(),
        media_type=media_type,
        headers=headers or {},
        status_code=status_code,
    )


def _build_preview_proxy_etag(safe_url: str, storage_revision: int) -> str:
    revision = storage_revision if storage_revision >= 0 else 0
    digest = hashlib.sha256(f"{safe_url}|{revision}".encode("utf-8")).hexdigest()[:16]
    return f'W/"storage-preview-{revision}-{digest}"'


def _normalize_etag_token(value: str) -> str:
    token = str(value or "").strip()
    if token.startswith("W/"):
        token = token[2:].strip()
    return token


def _looks_like_etag_validator(value: str) -> bool:
    token = str(value or "").strip()
    return token.startswith('"') or token.startswith("W/")


def _request_matches_etag(request: Request, current_etag: str) -> bool:
    if_none_match = str(request.headers.get("if-none-match") or "").strip()
    if not if_none_match:
        return False
    if if_none_match == "*":
        return True

    current_normalized = _normalize_etag_token(current_etag)
    return any(
        _normalize_etag_token(candidate) == current_normalized
        for candidate in if_none_match.split(",")
    )


def _build_upstream_range_request_headers(
    request: Request,
    *,
    current_etag: str | None = None,
) -> dict[str, str]:
    range_header = str(request.headers.get("range") or "").strip()
    if not range_header:
        return {}

    headers = {"Range": range_header}
    if_range = str(request.headers.get("if-range") or "").strip()
    if not if_range:
        return headers

    if current_etag and _looks_like_etag_validator(if_range):
        if _normalize_etag_token(if_range) == _normalize_etag_token(current_etag):
            return headers
        return {}

    headers["If-Range"] = if_range
    return headers


def _copy_upstream_proxy_headers(
    headers: dict[str, str],
    upstream_response: httpx.Response,
    *,
    include_upstream_etag: bool = False,
) -> None:
    content_length = upstream_response.headers.get("content-length")
    if content_length:
        headers["Content-Length"] = content_length

    accept_ranges = upstream_response.headers.get("accept-ranges")
    content_range = upstream_response.headers.get("content-range")
    if accept_ranges:
        headers["Accept-Ranges"] = accept_ranges
    elif content_range or int(upstream_response.status_code) == 206:
        headers["Accept-Ranges"] = "bytes"
    if content_range:
        headers["Content-Range"] = content_range

    upstream_last_modified = upstream_response.headers.get("last-modified")
    if upstream_last_modified:
        headers["Last-Modified"] = upstream_last_modified

    if include_upstream_etag:
        upstream_etag = upstream_response.headers.get("etag")
        if upstream_etag:
            headers["ETag"] = upstream_etag


def _apply_private_auth_vary(headers: dict[str, str]) -> None:
    existing = [
        token.strip()
        for token in str(headers.get("Vary") or "").split(",")
        if token.strip()
    ]
    seen = {token.lower() for token in existing}
    for token in _AUTH_VARY_HEADER_VALUES:
        if token.lower() not in seen:
            existing.append(token)
            seen.add(token.lower())
    if existing:
        headers["Vary"] = ", ".join(existing)


def _storage_metadata_cache_key(
    user_id: str,
    safe_url: str,
    *,
    storage_revision: int | None = None,
) -> str:
    digest = hashlib.sha256(safe_url.encode("utf-8")).hexdigest()
    try:
        revision = int(storage_revision) if storage_revision is not None else 0
    except (TypeError, ValueError):
        revision = 0
    if revision < 0:
        revision = 0
    return f"cache:storage:meta:{user_id}:{revision}:{digest}"


def _normalize_optional_int(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


async def _fetch_url_metadata(
    safe_url: str,
    *,
    allowed_hosts: set[str],
    timeout: float = 20.0,
) -> dict[str, Any]:
    client, upstream_response, final_url = await _open_safe_stream_with_redirect_guard(
        safe_url,
        allowed_hosts=allowed_hosts,
        timeout=timeout,
    )

    try:
        status = int(upstream_response.status_code)
        if status < 200 or status >= 300:
            detail_text = await _read_upstream_error_detail(upstream_response)
            detail = detail_text or f"上游请求失败: HTTP {status}"
            raise HTTPException(status_code=status, detail=detail)

        headers = upstream_response.headers
        return {
            "url": safe_url,
            "finalUrl": final_url,
            "contentType": headers.get("content-type"),
            "contentLength": _normalize_optional_int(headers.get("content-length")),
            "lastModified": headers.get("last-modified"),
            "etag": headers.get("etag"),
            "cacheControl": headers.get("cache-control"),
            "fetchedAt": datetime.utcnow().isoformat() + "Z",
            "source": "upstream",
            "error": None,
        }
    finally:
        await upstream_response.aclose()
        await client.aclose()


def _normalize_storage_metadata_payload(data: dict[str, Any], *, source: str) -> dict[str, Any]:
    return {
        "url": str(data.get("url") or "").strip(),
        "finalUrl": data.get("finalUrl"),
        "contentType": data.get("contentType"),
        "contentLength": data.get("contentLength"),
        "lastModified": data.get("lastModified"),
        "etag": data.get("etag"),
        "cacheControl": data.get("cacheControl"),
        "fetchedAt": data.get("fetchedAt"),
        "source": source,
        "error": data.get("error"),
    }


def _build_unavailable_metadata(url: str, error: str) -> dict[str, Any]:
    return {
        "url": str(url or "").strip(),
        "finalUrl": None,
        "contentType": None,
        "contentLength": None,
        "lastModified": None,
        "etag": None,
        "cacheControl": None,
        "fetchedAt": None,
        "source": "unavailable",
        "error": str(error or "").strip() or "metadata unavailable",
    }


async def _get_cache_optional() -> CacheService | None:
    try:
        return await get_cache()
    except Exception:
        logger.warning("[StorageMetadata] cache unavailable, fallback to upstream only", exc_info=True)
        return None


def _normalize_total_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, parsed)


async def _attach_total_count_to_browse_payload(
    result: dict[str, Any],
    *,
    manager: StorageManager,
    storage_id: str | None,
    user_id: str,
    cache: CacheService | None,
    storage_revision: int = 0,
    allow_fresh_count: bool = True,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return result
    if not result.get("supported"):
        result["total_count"] = None
        return result

    resolved_storage_id = str(result.get("storage_id") or storage_id or "").strip()
    resolved_path = str(result.get("path") or "").replace("\\", "/").strip().strip("/")
    if not resolved_storage_id:
        result["total_count"] = None
        return result

    cache_key = _storage_browse_total_cache_key(
        user_id=user_id,
        storage_id=resolved_storage_id,
        path=resolved_path,
        storage_revision=storage_revision,
    )

    if cache is not None:
        try:
            cached_value = await cache.get(cache_key)
        except Exception:
            cached_value = None
        if isinstance(cached_value, dict):
            cached_total = _normalize_total_count(cached_value.get("total_count"))
            if cached_total is not None:
                result["total_count"] = cached_total
                return result

    if not allow_fresh_count:
        result["total_count"] = None
        return result

    try:
        count_result = await manager.count_storage_items(
            storage_id=resolved_storage_id,
            path=resolved_path,
        )
    except Exception:
        logger.warning(
            "[StorageBrowse] count_storage_items failed for storage_id=%s path=%s",
            resolved_storage_id,
            resolved_path,
            exc_info=True,
        )
        result["total_count"] = None
        return result
    total_count = _normalize_total_count(count_result.get("total_count"))
    result["total_count"] = total_count

    if cache is not None and total_count is not None:
        try:
            await cache.set(
                cache_key,
                {
                    "storage_id": resolved_storage_id,
                    "path": resolved_path,
                    "total_count": total_count,
                },
                ttl=60,
            )
        except Exception:
            logger.debug("[StorageBrowse] total_count cache set failed", exc_info=True)

    return result


async def _resolve_storage_metadata_list(
    urls: list[str],
    *,
    user_id: str,
    allowed_hosts: set[str],
    cache: CacheService | None,
    storage_revision: int = 0,
    force_refresh: bool = False,
    max_fetch: int = 100,
    fetch_timeout: float = 20.0,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(8)
    fetch_budget = max(0, int(max_fetch))
    safe_fetch_timeout = max(0.5, min(float(fetch_timeout), 30.0))
    fetch_count = 0

    async def resolve_one(url: str) -> dict[str, Any]:
        nonlocal fetch_count

        try:
            safe_url = _resolve_safe_preview_fetch_url(url, allowed_hosts)
        except HTTPException as exc:
            return _build_unavailable_metadata(url, str(exc.detail))

        cache_key = _storage_metadata_cache_key(
            user_id,
            safe_url,
            storage_revision=storage_revision,
        )
        if cache is not None and not force_refresh:
            try:
                cached_data = await cache.get(cache_key)
            except Exception:
                cached_data = None
            if isinstance(cached_data, dict):
                return _normalize_storage_metadata_payload(cached_data, source="cache")

        if fetch_count >= fetch_budget:
            return _build_unavailable_metadata(safe_url, "metadata fetch budget exceeded")

        fetch_count += 1
        async with semaphore:
            try:
                fetched = await _fetch_url_metadata(
                    safe_url,
                    allowed_hosts=allowed_hosts,
                    timeout=safe_fetch_timeout,
                )
            except HTTPException as exc:
                return _build_unavailable_metadata(safe_url, str(exc.detail))
            except Exception as exc:
                return _build_unavailable_metadata(safe_url, str(exc))

            if cache is not None:
                try:
                    await cache.set(cache_key, fetched, ttl=600)
                except Exception:
                    logger.debug("[StorageMetadata] cache set failed", exc_info=True)
            return _normalize_storage_metadata_payload(fetched, source="upstream")

    return await asyncio.gather(*(resolve_one(url) for url in urls))


async def _resolve_storage_metadata_cache_only(
    safe_urls: list[str],
    *,
    user_id: str,
    cache: CacheService | None,
    storage_revision: int = 0,
) -> dict[str, dict[str, Any]]:
    if cache is None or len(safe_urls) == 0:
        return {}

    async def resolve_one(safe_url: str) -> tuple[str, dict[str, Any] | None]:
        cache_key = _storage_metadata_cache_key(
            user_id,
            safe_url,
            storage_revision=storage_revision,
        )
        try:
            cached_data = await cache.get(cache_key)
        except Exception:
            cached_data = None
        if isinstance(cached_data, dict):
            return safe_url, _normalize_storage_metadata_payload(cached_data, source="cache")
        return safe_url, None

    pairs = await asyncio.gather(*(resolve_one(url) for url in safe_urls))
    return {
        key: value
        for key, value in pairs
        if value is not None
    }


def _build_preview_proxy_url(url: str) -> str:
    return f"/api/storage/preview?url={quote(url, safe='')}"


def _extract_hostname_from_value(value: str) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    candidate = raw_value if "://" in raw_value else f"https://{raw_value}"
    parsed = urlparse(candidate)
    host = str(parsed.hostname or "").strip().strip(".").lower()
    return host or None


def _is_restricted_network_error(exc: UnsafeURLError) -> bool:
    detail = str(exc)
    return detail in {"URL 指向受限地址", "URL 指向受限网络地址"}


def _collect_storage_preview_host_allowlist(db: Session, user_id: str) -> set[str]:
    allowlist: set[str] = set()
    configs = db.query(StorageConfig).filter(
        StorageConfig.user_id == user_id,
        StorageConfig.enabled == True  # noqa: E712 - SQLAlchemy boolean expression
    ).all()

    for config in configs:
        decrypted = decrypt_config(config.config or {})
        if not isinstance(decrypted, dict):
            continue

        for key in ("domain", "custom_domain", "customDomain", "endpoint", "url_prefix", "urlPrefix"):
            host = _extract_hostname_from_value(decrypted.get(key))
            if host:
                allowlist.add(host)

        provider = str(config.provider or "").strip().lower()
        bucket = str(decrypted.get("bucket") or "").strip()
        endpoint = str(decrypted.get("endpoint") or "").strip()
        region = str(decrypted.get("region") or "").strip()

        if provider == "aliyun-oss" and bucket and endpoint:
            host = _extract_hostname_from_value(f"https://{bucket}.{endpoint}")
            if host:
                allowlist.add(host)

        if provider == "tencent-cos" and bucket and region:
            host = _extract_hostname_from_value(f"https://{bucket}.cos.{region}.myqcloud.com")
            if host:
                allowlist.add(host)

    return allowlist


def _resolve_safe_preview_fetch_url(url: str, allowed_hosts: set[str]) -> str:
    raw_url = str(url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="url 不能为空")

    try:
        return validate_outbound_http_url(raw_url)
    except UnsafeURLError as exc:
        if _is_restricted_network_error(exc):
            host = _extract_hostname_from_value(raw_url)
            if host and host in allowed_hosts:
                return raw_url
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _attach_preview_urls_to_browse_payload(payload: dict, allowed_hosts: set[str]) -> dict:
    items = payload.get("items")
    if not isinstance(items, list):
        return payload

    enriched_items = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            enriched_items.append(raw_item)
            continue

        item = dict(raw_item)
        preview_url = None
        if item.get("entry_type") == "file":
            file_url = item.get("url")
            if isinstance(file_url, str):
                normalized_url = file_url.strip()
                if normalized_url:
                    try:
                        safe_url = _resolve_safe_preview_fetch_url(normalized_url, allowed_hosts)
                    except HTTPException:
                        preview_url = None
                    else:
                        preview_url = _build_preview_proxy_url(safe_url)
        item["preview_url"] = preview_url
        enriched_items.append(item)

    payload["items"] = enriched_items
    return payload


async def _attach_metadata_to_browse_payload(
    payload: dict,
    *,
    user_id: str,
    allowed_hosts: set[str],
    cache: CacheService | None,
    storage_revision: int = 0,
) -> dict:
    items = payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return payload

    unique_safe_urls: list[str] = []
    seen_safe_urls: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("entry_type") != "file":
            item["metadata"] = None
            continue

        file_name = str(item.get("name") or "").strip().lower()
        file_ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
        if file_ext not in _METADATA_IMAGE_EXTENSIONS and file_ext not in _METADATA_VIDEO_EXTENSIONS:
            item["metadata"] = None
            continue

        raw_url = str(item.get("url") or "").strip()
        if not raw_url:
            item["metadata"] = None
            continue

        try:
            safe_url = _resolve_safe_preview_fetch_url(raw_url, allowed_hosts)
        except HTTPException as exc:
            item["metadata"] = _build_unavailable_metadata(raw_url, str(exc.detail))
            continue

        item["__meta_safe_url"] = safe_url
        if safe_url not in seen_safe_urls:
            seen_safe_urls.add(safe_url)
            unique_safe_urls.append(safe_url)

    metadata_by_url = await _resolve_storage_metadata_cache_only(
        unique_safe_urls,
        user_id=user_id,
        cache=cache,
        storage_revision=storage_revision,
    )

    missing_safe_urls = [
        safe_url
        for safe_url in unique_safe_urls
        if safe_url not in metadata_by_url
    ]
    backfill_targets = missing_safe_urls[:_BROWSE_METADATA_BACKFILL_MAX_FETCH]
    if len(backfill_targets) > 0:
        try:
            backfilled = await asyncio.wait_for(
                _resolve_storage_metadata_list(
                    backfill_targets,
                    user_id=user_id,
                    allowed_hosts=allowed_hosts,
                    cache=cache,
                    storage_revision=storage_revision,
                    force_refresh=False,
                    max_fetch=len(backfill_targets),
                    fetch_timeout=_BROWSE_METADATA_BACKFILL_FETCH_TIMEOUT_SECONDS,
                ),
                timeout=_BROWSE_METADATA_BACKFILL_TOTAL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.debug(
                "[StorageMetadata] browse metadata backfill timeout: user_id=%s targets=%s timeout=%s",
                user_id,
                len(backfill_targets),
                _BROWSE_METADATA_BACKFILL_TOTAL_TIMEOUT_SECONDS,
            )
            backfilled = []
        except Exception:
            logger.debug(
                "[StorageMetadata] browse metadata backfill failed: user_id=%s targets=%s",
                user_id,
                len(backfill_targets),
                exc_info=True,
            )
            backfilled = []

        for entry in backfilled:
            if not isinstance(entry, dict):
                continue
            safe_url = str(entry.get("url") or "").strip()
            if safe_url:
                metadata_by_url[safe_url] = entry

    for item in items:
        if not isinstance(item, dict):
            continue
        safe_url = item.pop("__meta_safe_url", None)
        if safe_url:
            item["metadata"] = metadata_by_url.get(safe_url)
        elif "metadata" not in item:
            item["metadata"] = None

    return payload


def _is_upload_task_owned_by_user(db: Session, task: UploadTask, user_id: str) -> bool:
    session_id = str(task.session_id or "").strip()
    if session_id:
        owned_session = db.query(ChatSession.id).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        ).first()
        if owned_session:
            return True

    attachment_id = str(task.attachment_id or "").strip()
    if attachment_id:
        owned_attachment = db.query(MessageAttachment.id).filter(
            MessageAttachment.id == attachment_id,
            MessageAttachment.user_id == user_id,
        ).first()
        if owned_attachment:
            return True

    message_id = str(task.message_id or "").strip()
    if message_id:
        owned_message_attachment = db.query(MessageAttachment.id).filter(
            MessageAttachment.message_id == message_id,
            MessageAttachment.user_id == user_id,
        ).first()
        if owned_message_attachment:
            return True

    return False


def _require_owned_upload_task(db: Session, task_id: str, user_id: str) -> UploadTask:
    task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if not _is_upload_task_owned_by_user(db, task, user_id):
        raise HTTPException(status_code=404, detail="上传任务不存在")
    return task


def _sanitize_download_name(name: str, fallback: str) -> str:
    normalized = _STORAGE_DOWNLOAD_INVALID_NAME_PATTERN.sub("_", str(name or "").strip())
    normalized = normalized.strip().strip(".")
    return normalized or fallback


def _normalize_storage_item_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().strip("/")


def _storage_item_parent_path(path: str) -> str:
    normalized = _normalize_storage_item_path(path)
    if not normalized or "/" not in normalized:
        return ""
    return normalized.rsplit("/", 1)[0]


def _extract_non_negative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _describe_storage_download_byte_limit(max_bytes: int) -> str:
    return f"{max(1, max_bytes // (1024 * 1024))} MiB"


def _storage_download_size_limit_message(label: str, max_bytes: int) -> str:
    return f"{label}超过 {_describe_storage_download_byte_limit(max_bytes)} 限制"


def _storage_download_file_limit_message(max_total_files: int) -> str:
    return f"下载项数量超过 {max_total_files} 个文件限制"


def _sanitize_archive_path(path: str, fallback: str = "item") -> str:
    raw_segments = str(path or "").replace("\\", "/").split("/")
    segments = [
        _sanitize_download_name(segment, fallback)
        for segment in raw_segments
        if segment and segment not in {".", ".."}
    ]
    return "/".join(segments) or fallback


def _ensure_unique_archive_path(archive_path: str, used_paths: set[str]) -> str:
    candidate = archive_path
    suffix = 2
    base_path = Path(archive_path)
    stem = base_path.stem or "file"
    ext = base_path.suffix
    parent = str(base_path.parent).replace("\\", "/")
    while candidate in used_paths:
        file_name = f"{stem}-{suffix}{ext}"
        candidate = f"{parent}/{file_name}" if parent not in {"", "."} else file_name
        suffix += 1
    used_paths.add(candidate)
    return candidate


def _storage_download_meta_path(download_id: str) -> Path:
    return _STORAGE_DOWNLOAD_DIR / f"{download_id}.json"


def _storage_download_payload_path(download_id: str, suffix: str) -> Path:
    return _STORAGE_DOWNLOAD_DIR / f"{download_id}{suffix}"


def _cleanup_storage_download_artifacts(meta_path: Path, file_path: Path | None = None) -> None:
    targets = [meta_path]
    if file_path is not None:
        targets.append(file_path)
    for target in targets:
        try:
            if target.exists():
                target.unlink()
        except Exception:
            logger.debug("[StorageDownload] failed to delete %s", target, exc_info=True)


def _cleanup_storage_download_by_id(download_id: str) -> None:
    meta_path = _storage_download_meta_path(download_id)
    for target in _STORAGE_DOWNLOAD_DIR.glob(f"{download_id}*"):
        try:
            if target.is_file():
                target.unlink()
        except Exception:
            logger.debug("[StorageDownload] failed to delete %s", target, exc_info=True)
    try:
        if meta_path.exists():
            meta_path.unlink()
    except Exception:
        logger.debug("[StorageDownload] failed to delete %s", meta_path, exc_info=True)


def _cleanup_expired_storage_downloads() -> None:
    now = time.time()
    try:
        meta_paths = list(_STORAGE_DOWNLOAD_DIR.glob("*.json"))
    except Exception:
        logger.debug("[StorageDownload] failed to scan temp dir", exc_info=True)
        return

    for meta_path in meta_paths:
        file_path: Path | None = None
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            file_raw = str(payload.get("file_path") or "").strip()
            if file_raw:
                file_path = Path(file_raw)
            expires_at = float(payload.get("expires_at_ts") or 0)
            if expires_at > now and file_path and file_path.exists():
                continue
        except Exception:
            logger.debug("[StorageDownload] invalid metadata file %s", meta_path, exc_info=True)
        _cleanup_storage_download_artifacts(meta_path, file_path)


def _persist_storage_download_metadata(
    download_id: str,
    *,
    user_id: str,
    file_path: Path,
    file_name: str,
    media_type: str,
    archive: bool,
    total_files: int,
    skipped_count: int,
) -> dict[str, Any]:
    created_at_ts = time.time()
    expires_at_ts = created_at_ts + _STORAGE_DOWNLOAD_TTL_SECONDS
    payload = {
        "download_id": download_id,
        "user_id": user_id,
        "file_path": str(file_path),
        "file_name": file_name,
        "media_type": media_type,
        "archive": bool(archive),
        "total_files": int(total_files),
        "skipped_count": int(skipped_count),
        "created_at_ts": created_at_ts,
        "expires_at_ts": expires_at_ts,
        "created_at": datetime.utcfromtimestamp(created_at_ts).isoformat() + "Z",
        "expires_at": datetime.utcfromtimestamp(expires_at_ts).isoformat() + "Z",
    }
    _storage_download_meta_path(download_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def _load_storage_download_metadata(download_id: str, *, user_id: str) -> dict[str, Any]:
    meta_path = _storage_download_meta_path(download_id)
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="下载不存在或已过期")

    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _cleanup_storage_download_artifacts(meta_path)
        raise HTTPException(status_code=404, detail="下载不存在或已过期") from exc

    if str(payload.get("user_id") or "") != str(user_id or ""):
        raise HTTPException(status_code=404, detail="下载不存在或已过期")

    file_path_raw = str(payload.get("file_path") or "").strip()
    file_path = Path(file_path_raw) if file_path_raw else None
    expires_at_ts = float(payload.get("expires_at_ts") or 0)
    if expires_at_ts <= time.time() or file_path is None or not file_path.exists():
        _cleanup_storage_download_artifacts(meta_path, file_path)
        raise HTTPException(status_code=404, detail="下载不存在或已过期")

    return payload


async def _stream_safe_url_to_file(
    safe_url: str,
    *,
    target_path: Path,
    allowed_hosts: set[str],
    timeout: float = 120.0,
    max_bytes: int | None = None,
    size_limit_label: str = "下载内容",
) -> dict[str, Any]:
    client, upstream_response, final_url = await _open_safe_stream_with_redirect_guard(
        safe_url,
        allowed_hosts=allowed_hosts,
        timeout=timeout,
    )

    try:
        status = int(upstream_response.status_code)
        if status < 200 or status >= 300:
            detail_text = await _read_upstream_error_detail(upstream_response)
            detail = detail_text or f"上游下载失败: HTTP {status}"
            raise HTTPException(status_code=status, detail=detail)

        if max_bytes is not None:
            header_content_length = _extract_non_negative_int(upstream_response.headers.get("content-length"))
            if header_content_length is not None and header_content_length > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=_storage_download_size_limit_message(size_limit_label, max_bytes),
                )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        with target_path.open("wb") as handle:
            async for chunk in upstream_response.aiter_bytes():
                if not chunk:
                    continue
                if max_bytes is not None and total_bytes + len(chunk) > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=_storage_download_size_limit_message(size_limit_label, max_bytes),
                    )
                handle.write(chunk)
                total_bytes += len(chunk)

        return {
            "final_url": final_url,
            "content_type": upstream_response.headers.get("content-type", "application/octet-stream"),
            "content_length": total_bytes,
        }
    finally:
        await upstream_response.aclose()
        await client.aclose()


async def _write_safe_url_to_zip(
    zip_file: zipfile.ZipFile,
    *,
    archive_path: str,
    safe_url: str,
    allowed_hosts: set[str],
    timeout: float = 120.0,
    max_bytes: int | None = None,
    size_limit_label: str = "下载归档",
) -> dict[str, Any]:
    client, upstream_response, final_url = await _open_safe_stream_with_redirect_guard(
        safe_url,
        allowed_hosts=allowed_hosts,
        timeout=timeout,
    )

    try:
        status = int(upstream_response.status_code)
        if status < 200 or status >= 300:
            detail_text = await _read_upstream_error_detail(upstream_response)
            detail = detail_text or f"上游下载失败: HTTP {status}"
            raise HTTPException(status_code=status, detail=detail)

        if max_bytes is not None:
            header_content_length = _extract_non_negative_int(upstream_response.headers.get("content-length"))
            if header_content_length is not None and header_content_length > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=_storage_download_size_limit_message(size_limit_label, max_bytes),
                )

        total_bytes = 0
        with zip_file.open(archive_path, "w") as archive_entry:
            async for chunk in upstream_response.aiter_bytes():
                if not chunk:
                    continue
                if max_bytes is not None and total_bytes + len(chunk) > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=_storage_download_size_limit_message(size_limit_label, max_bytes),
                    )
                archive_entry.write(chunk)
                total_bytes += len(chunk)

        return {
            "final_url": final_url,
            "content_type": upstream_response.headers.get("content-type", "application/octet-stream"),
            "content_length": total_bytes,
        }
    finally:
        await upstream_response.aclose()
        await client.aclose()


async def _list_storage_directory_files(
    manager: StorageManager,
    *,
    storage_id: str,
    path: str,
    existing_paths: set[str] | None = None,
    max_total_files: int | None = None,
) -> list[dict[str, Any]]:
    queue = [str(path or "").strip()]
    seen_dirs: set[str] = set(queue)
    files: list[dict[str, Any]] = []
    counted_paths = set(existing_paths or set())

    while queue:
        current_path = queue.pop(0)
        for item in await _list_storage_path_entries(
            manager,
            storage_id=storage_id,
            path=current_path,
            existing_paths=counted_paths,
            max_total_files=max_total_files,
        ):
            item_path = str(item.get("path") or "").strip()
            if not item_path:
                continue
            entry_type = str(item.get("entry_type") or "").strip()
            if entry_type == "directory":
                if item_path not in seen_dirs:
                    seen_dirs.add(item_path)
                    queue.append(item_path)
            elif entry_type == "file":
                files.append(item)

    return files


async def _list_storage_path_entries(
    manager: StorageManager,
    *,
    storage_id: str,
    path: str,
    existing_paths: set[str] | None = None,
    max_total_files: int | None = None,
) -> list[dict[str, Any]]:
    cursor: Optional[str] = None
    entries: list[dict[str, Any]] = []
    counted_paths = existing_paths if existing_paths is not None else set()

    while True:
        browse_result = await manager.browse_storage(
            storage_id=storage_id,
            path=path,
            limit=_STORAGE_DOWNLOAD_BROWSE_LIMIT,
            cursor=cursor,
        )

        if not browse_result.get("supported", False):
            raise HTTPException(
                status_code=400,
                detail=browse_result.get("message") or "当前存储提供商不支持目录浏览",
            )

        for item in browse_result.get("items") or []:
            if isinstance(item, dict):
                entries.append(item)
                if max_total_files is None:
                    continue
                item_path = _normalize_storage_item_path(str(item.get("path") or ""))
                item_url = str(item.get("url") or "").strip()
                if str(item.get("entry_type") or "").strip() != "file" or not item_path or not item_url:
                    continue
                if item_path in counted_paths:
                    continue
                counted_paths.add(item_path)
                if len(counted_paths) > max_total_files:
                    raise HTTPException(
                        status_code=413,
                        detail=_storage_download_file_limit_message(max_total_files),
                    )

        next_cursor = browse_result.get("next_cursor")
        has_more = bool(browse_result.get("has_more"))
        if not has_more or not next_cursor:
            break
        cursor = str(next_cursor)

    return entries


async def _resolve_storage_file_download_item(
    manager: StorageManager,
    *,
    storage_id: str,
    path: str,
    directory_entries_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    normalized_target_path = _normalize_storage_item_path(path)
    if not normalized_target_path:
        return None

    parent_path = _storage_item_parent_path(normalized_target_path)
    if parent_path not in directory_entries_cache:
        directory_entries_cache[parent_path] = await _list_storage_path_entries(
            manager,
            storage_id=storage_id,
            path=parent_path,
        )

    for item in directory_entries_cache[parent_path]:
        if str(item.get("entry_type") or "").strip() != "file":
            continue
        candidate_path = _normalize_storage_item_path(str(item.get("path") or ""))
        if candidate_path == normalized_target_path:
            return item

    return None


async def _collect_storage_download_entries(
    manager: StorageManager,
    *,
    storage_id: str,
    items: list[dict[str, Any]],
    max_total_files: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    directory_entries_cache: dict[str, list[dict[str, Any]]] = {}

    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue

        item_path = str(raw_item.get("path") or "").strip()
        normalized_item_path = _normalize_storage_item_path(item_path)
        if not item_path:
            skipped.append({
                "path": "",
                "status": "skipped",
                "reason": "missing path",
            })
            continue

        item_name = str(raw_item.get("name") or Path(item_path).name or "item").strip()
        is_directory = bool(raw_item.get("is_directory", False))

        if is_directory:
            directory_entries = await _list_storage_directory_files(
                manager,
                storage_id=storage_id,
                path=item_path,
                existing_paths=seen_paths,
                max_total_files=max_total_files,
            )
            root_archive = _sanitize_archive_path(item_path, fallback=_sanitize_download_name(item_name, "directory"))
            if len(directory_entries) == 0:
                skipped.append({
                    "path": item_path,
                    "status": "skipped",
                    "reason": "empty directory",
                })
                continue

            for nested_item in directory_entries:
                nested_path = str(nested_item.get("path") or "").strip()
                normalized_nested_path = _normalize_storage_item_path(nested_path)
                if not nested_path or normalized_nested_path in seen_paths:
                    continue
                nested_url = str(nested_item.get("url") or "").strip()
                if not nested_url:
                    skipped.append({
                        "path": nested_path,
                        "status": "skipped",
                        "reason": "missing file url",
                    })
                    continue

                relative_path = nested_path[len(item_path):].lstrip("/") if nested_path.startswith(item_path) else Path(nested_path).name
                archive_path = f"{root_archive}/{_sanitize_archive_path(relative_path, fallback='file')}"
                seen_paths.add(normalized_nested_path)
                entries.append({
                    "path": nested_path,
                    "name": str(nested_item.get("name") or Path(nested_path).name or "file"),
                    "file_url": nested_url,
                    "archive_path": archive_path,
                    "is_directory": False,
                    "size": _extract_non_negative_int(nested_item.get("size")),
                })
            continue

        if normalized_item_path in seen_paths:
            continue
        resolved_item = await _resolve_storage_file_download_item(
            manager,
            storage_id=storage_id,
            path=item_path,
            directory_entries_cache=directory_entries_cache,
        )
        resolved_url = str((resolved_item or {}).get("url") or "").strip()
        resolved_name = str((resolved_item or {}).get("name") or item_name or Path(item_path).name or "file").strip()
        if not resolved_item:
            skipped.append({
                "path": item_path,
                "status": "skipped",
                "reason": "file not found",
            })
            continue
        if not resolved_url:
            skipped.append({
                "path": item_path,
                "status": "skipped",
                "reason": "missing file url",
            })
            continue

        if max_total_files is not None and len(seen_paths) >= max_total_files:
            raise HTTPException(
                status_code=413,
                detail=_storage_download_file_limit_message(max_total_files),
            )
        seen_paths.add(normalized_item_path)
        entries.append({
            "path": item_path,
            "name": resolved_name or "file",
            "file_url": resolved_url,
            "archive_path": _sanitize_archive_path(item_path, fallback=_sanitize_download_name(resolved_name or item_name, "file")),
            "is_directory": False,
            "size": _extract_non_negative_int((resolved_item or {}).get("size")),
        })

    return entries, skipped


def _resolve_enabled_storage_config(
    db: Session,
    user_id: str,
    storage_id: Optional[str] = None,
) -> tuple[str, StorageConfig]:
    resolved_storage_id = storage_id
    user_query = UserScopedQuery(db, user_id)

    if resolved_storage_id:
        config = user_query.get(StorageConfig, resolved_storage_id)
    else:
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == user_id).first()
        if not active or not active.storage_id:
            raise HTTPException(status_code=400, detail="未设置存储配置")
        resolved_storage_id = active.storage_id
        config = user_query.get(StorageConfig, resolved_storage_id)

    if not config:
        raise HTTPException(status_code=404, detail="存储配置不存在或无权访问")
    if not config.enabled:
        raise HTTPException(status_code=400, detail="存储配置已禁用")

    return resolved_storage_id, config


@router.get("/debug")
async def storage_debug(user_id: str = Depends(require_current_user)):
    """返回后端运行态信息（用于排查是否命中最新代码/路由）。"""
    backend_env = Path(__file__).resolve().parents[2] / ".env"
    return {
        "module_file": __file__,
        "cwd": os.getcwd(),
        "temp_dir": TEMP_DIR,
        "backend_env_exists": backend_env.exists(),
        "database_url": _mask_url(settings.database_url),
        "redis_url": _mask_url(settings.redis_url),
        "features": {
            "upload_logs": True,
            "upload_status": True,
            "upload_async": True,
        },
    }


@router.get("/worker-status")
async def get_worker_status(user_id: str = Depends(require_current_user)):
    """查看 WorkerPool/Redis 状态（用于定位“排队后不处理，重启才成功”）。"""
    try:
        from ...services.common.upload_worker_pool import worker_pool
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"WorkerPool 不可用: {e}")

    redis_error: str | None = None
    stats = None
    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        stats = await redis_queue.get_stats()
    except Exception as e:
        redis_error = str(e)

    workers_total = len(worker_pool._workers)
    workers_alive = sum(1 for t in worker_pool._workers if not t.done())

    return {
        "worker_pool": {
            "running": bool(worker_pool._running),
            "workers_total": workers_total,
            "workers_alive": workers_alive,
            "reconcile_interval_s": getattr(worker_pool, "_reconcile_interval_s", None),
            "reconcile_limit": getattr(worker_pool, "_reconcile_limit", None),
        },
        "redis": {
            "connected": redis_queue._redis is not None,
            "error": redis_error,
            "stats": stats,
        },
        "server": {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "module_file": __file__,
        },
    }


# ==================== 配置管理 ====================

@router.get("/configs")
async def get_storage_configs(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取所有存储配置（自动解密）"""
    logger.info(f"[StorageConfigs] 获取用户存储配置: user_id={user_id}")
    
    manager = StorageManager(db, user_id)
    configs = manager.get_all_configs()
    
    logger.info(f"[StorageConfigs] 返回 {len(configs)} 个配置给前端")
    return configs


@router.post("/configs")
async def create_storage_config(
    config_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """创建存储配置（自动加密敏感字段）"""
    manager = StorageManager(db, user_id)
    result = manager.create_config(config_data)
    revision = await _bump_storage_revision(user_id)
    if isinstance(result, dict):
        result["storage_revision"] = revision
        return result
    return {
        "data": result,
        "storage_revision": revision,
    }


@router.put("/configs/{config_id}")
async def update_storage_config(
    config_id: str,
    config_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """更新存储配置（自动加密敏感字段）"""
    manager = StorageManager(db, user_id)
    result = manager.update_config(config_id, config_data)
    revision = await _bump_storage_revision(user_id)
    if isinstance(result, dict):
        result["storage_revision"] = revision
        return result
    return {
        "data": result,
        "storage_revision": revision,
    }


@router.delete("/configs/{config_id}")
async def delete_storage_config(
    config_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """删除存储配置"""
    manager = StorageManager(db, user_id)
    manager.delete_config(config_id)
    revision = await _bump_storage_revision(user_id)
    return {"success": True, "storage_revision": revision}


@router.get("/active")
async def get_active_storage(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取当前激活的存储配置"""
    manager = StorageManager(db, user_id)
    storage_id = manager.get_active_storage_id()

    return {"storage_id": storage_id}


@router.get("/active/browse")
async def browse_active_storage(
    path: str = Query(default="", description="目录路径，空字符串表示根目录"),
    limit: int = Query(default=200, ge=1, le=1000, description="每页最多返回数量"),
    cursor: Optional[str] = Query(default=None, description="分页游标"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache: CacheService | None = Depends(_get_cache_optional),
):
    """浏览当前激活存储的目录内容"""
    manager = StorageManager(db, user_id)
    result = await manager.browse_active_storage(path=path, limit=limit, cursor=cursor)
    allowed_hosts = _collect_storage_preview_host_allowlist(db, user_id)
    storage_revision = await _get_storage_revision(user_id)
    result = await _attach_total_count_to_browse_payload(
        result,
        manager=manager,
        storage_id=result.get("storage_id"),
        user_id=user_id,
        cache=cache,
        storage_revision=storage_revision,
        allow_fresh_count=not bool(cursor),
    )
    result = _attach_preview_urls_to_browse_payload(result, allowed_hosts)
    result = await _attach_metadata_to_browse_payload(
        result,
        user_id=user_id,
        allowed_hosts=allowed_hosts,
        cache=cache,
        storage_revision=storage_revision,
    )
    result["storage_revision"] = storage_revision
    return result


@router.get("/browse/{storage_id}")
async def browse_storage(
    storage_id: str,
    path: str = Query(default="", description="目录路径，空字符串表示根目录"),
    limit: int = Query(default=200, ge=1, le=1000, description="每页最多返回数量"),
    cursor: Optional[str] = Query(default=None, description="分页游标"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache: CacheService | None = Depends(_get_cache_optional),
):
    """浏览指定 storage 的目录内容"""
    manager = StorageManager(db, user_id)
    result = await manager.browse_storage(
        storage_id=storage_id,
        path=path,
        limit=limit,
        cursor=cursor
    )
    allowed_hosts = _collect_storage_preview_host_allowlist(db, user_id)
    storage_revision = await _get_storage_revision(user_id)
    result = await _attach_total_count_to_browse_payload(
        result,
        manager=manager,
        storage_id=storage_id,
        user_id=user_id,
        cache=cache,
        storage_revision=storage_revision,
        allow_fresh_count=not bool(cursor),
    )
    result = _attach_preview_urls_to_browse_payload(result, allowed_hosts)
    result = await _attach_metadata_to_browse_payload(
        result,
        user_id=user_id,
        allowed_hosts=allowed_hosts,
        cache=cache,
        storage_revision=storage_revision,
    )
    result["storage_revision"] = storage_revision
    return result


@router.post("/metadata/batch")
async def batch_get_storage_file_metadata(
    payload: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache: CacheService | None = Depends(_get_cache_optional),
):
    """
    批量获取文件元数据（优先 Redis 缓存，未命中回源）。

    请求体：
    {
      "urls": ["https://..."],
      "force_refresh": false
    }
    """
    urls_raw = payload.get("urls")
    if not isinstance(urls_raw, list):
        raise HTTPException(status_code=400, detail="urls 必须是数组")

    force_refresh = bool(payload.get("force_refresh", payload.get("forceRefresh", False)))
    allowed_hosts = _collect_storage_preview_host_allowlist(db, user_id)
    storage_revision = await _get_storage_revision(user_id)

    # 去重并限制单次请求规模，避免滥用。
    normalized_urls: list[str] = []
    seen_urls: set[str] = set()
    for value in urls_raw:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen_urls:
            continue
        seen_urls.add(candidate)
        normalized_urls.append(candidate)
        if len(normalized_urls) >= 100:
            break

    results = await _resolve_storage_metadata_list(
        normalized_urls,
        user_id=user_id,
        allowed_hosts=allowed_hosts,
        cache=cache,
        storage_revision=storage_revision,
        force_refresh=force_refresh,
        max_fetch=100,
    )
    return {
        "items": results,
        "total": len(results),
        "storage_revision": storage_revision,
    }


@router.post("/items/delete")
async def delete_storage_item(
    payload: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    删除存储项（文件/目录）
    """
    storage_id = payload.get("storage_id")
    path = (payload.get("path") or "").strip()
    is_directory = bool(payload.get("is_directory", False))
    file_url = payload.get("file_url")

    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    manager = StorageManager(db, user_id)
    result = await manager.delete_storage_item(
        storage_id=storage_id,
        path=path,
        is_directory=is_directory,
        file_url=file_url
    )
    if result.get("success"):
        result["storage_revision"] = await _bump_storage_revision(user_id)
        return result

    result["storage_revision"] = await _get_storage_revision(user_id)
    raise HTTPException(status_code=400, detail=result)


@router.post("/items/batch-delete")
async def batch_delete_storage_items(
    payload: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    批量删除存储项
    """
    storage_id = payload.get("storage_id")
    items = payload.get("items") or []
    if not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="items is required")

    manager = StorageManager(db, user_id)
    results = []
    for item in items:
        path = (item or {}).get("path")
        if not path:
            results.append({
                "success": False,
                "path": "",
                "message": "missing path"
            })
            continue

        try:
            result = await manager.delete_storage_item(
                storage_id=storage_id,
                path=path,
                is_directory=bool((item or {}).get("is_directory", False)),
                file_url=(item or {}).get("file_url")
            )
            results.append(result)
        except Exception as e:
            results.append({
                "success": False,
                "path": path,
                "message": str(e)
            })

    success_count = sum(1 for r in results if r.get("success"))
    failure_count = len(results) - success_count
    if success_count > 0:
        revision = await _bump_storage_revision(user_id)
    else:
        revision = await _get_storage_revision(user_id)

    response_payload = {
        "success": failure_count == 0,
        "total": len(results),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
        "storage_revision": revision,
    }

    if failure_count > 0:
        response_payload["failures"] = [r for r in results if not r.get("success")]
        raise HTTPException(status_code=400, detail=response_payload)

    return response_payload


@router.post("/items/rename")
async def rename_storage_item(
    payload: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    重命名存储项（文件/目录）
    """
    storage_id = payload.get("storage_id")
    path = (payload.get("path") or "").strip()
    new_name = (payload.get("new_name") or "").strip()
    is_directory = bool(payload.get("is_directory", False))

    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    if not new_name:
        raise HTTPException(status_code=400, detail="new_name is required")

    manager = StorageManager(db, user_id)
    result = await manager.rename_storage_item(
        storage_id=storage_id,
        path=path,
        new_name=new_name,
        is_directory=is_directory
    )
    if result.get("success"):
        result["storage_revision"] = await _bump_storage_revision(user_id)
        return result

    result["storage_revision"] = await _get_storage_revision(user_id)
    raise HTTPException(status_code=400, detail=result)


@router.post("/active/{storage_id}")
async def set_active_storage(
    storage_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """设置当前激活的存储配置"""
    manager = StorageManager(db, user_id)
    manager.set_active_storage(storage_id)
    revision = await _bump_storage_revision(user_id)
    return {"success": True, "storage_id": storage_id, "storage_revision": revision}


@router.post("/test")
async def test_storage_config(
    config_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    测试存储配置
    
    请求参数：
    {
        "provider": "lsky" | "aliyun-oss" | "tencent-cos" | "google-drive" | "local" | "s3-compatible",
        "config": {
            // Provider-specific configuration
        }
    }
    
    返回：
    {
        "success": true,
        "message": "Configuration test successful",
        "test_url": "https://..."
    }
    """
    manager = StorageManager(db, user_id)
    result = await manager.test_config(config_data)
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message") or result.get("error") or "配置测试失败",
        )
    return result


# ==================== 文件上传 ====================

def upload_to_active_storage(content: bytes, filename: str, content_type: str, user_id: Optional[str] = None) -> dict:
    """
    同步上传文件到当前激活的存储配置

    供其他模块（如 image_expand）调用

    Args:
        content: 文件内容（字节）
        filename: 文件名
        content_type: MIME 类型

    Returns:
        {"success": True, "url": "https://..."} 或 {"success": False, "error": "..."}
    """
    db = SessionLocal()
    try:
        resolved_user_id = user_id or "default"
        # 获取当前激活的存储配置
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == resolved_user_id).first()
        if not active or not active.storage_id:
            return {"success": False, "error": "未设置存储配置"}

        config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
        if not config:
            return {"success": False, "error": "存储配置不存在"}

        if not config.enabled:
            return {"success": False, "error": "存储配置已禁用"}

        # 根据提供商类型上传
        if config.provider == "lsky":
            return upload_to_lsky_sync(filename, content, content_type, config.config)
        else:
            return {"success": False, "error": f"不支持的存储类型: {config.provider}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def upload_to_active_storage_async(content: bytes, filename: str, content_type: str, user_id: Optional[str] = None) -> dict:
    """
    异步上传文件到当前激活的存储配置

    供其他异步模块（如 chat_handler）调用
    
    使用 StorageManager 统一管理配置，实现配置获取、解密和上传的统一处理。

    Args:
        content: 文件内容（字节）
        filename: 文件名
        content_type: MIME 类型
        user_id: 用户 ID（用于确定存储配置）

    Returns:
        {"success": True, "url": "https://..."} 或 {"success": False, "error": "..."}
    """
    db = SessionLocal()
    try:
        resolved_user_id = user_id or "default"
        logger.info(f"[Storage] Async upload for user: {resolved_user_id}, file: {filename}")

        # ✅ 使用 StorageManager 统一管理配置和上传
        manager = StorageManager(db, resolved_user_id)
        result = await manager.upload_file(
            filename=filename,
            content=content,
            content_type=content_type
        )

        if result.get('success'):
            logger.info(f"[Storage] Upload successful: {result.get('url', '')[:60]}...")
        else:
            logger.error(f"[Storage] Upload failed: {result.get('error', 'Unknown error')}")

        return result
    except HTTPException as e:
        logger.error(f"[Storage] Async upload HTTP error: {e.detail}")
        return {"success": False, "error": e.detail}
    except Exception as e:
        logger.error(f"[Storage] Async upload error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def upload_to_lsky_sync(filename: str, content: bytes, content_type: str, config: dict) -> dict:
    """
    同步上传到兰空图床
    """
    import requests
    
    domain = config.get("domain")
    token = config.get("token")
    strategy_id = config.get("strategyId")
    
    if not domain or not token:
        return {"success": False, "error": "兰空图床配置不完整"}
    
    auth_token = token if token.startswith("Bearer ") else f"Bearer {token}"
    upload_url = f"{domain.rstrip('/')}/api/v1/upload"
    
    files = {"file": (filename, content, content_type)}
    headers = {"Authorization": auth_token, "Accept": "application/json"}
    data = {"strategy_id": strategy_id} if strategy_id else {}
    
    try:
        response = requests.post(upload_url, files=files, headers=headers, data=data, timeout=60)
        result = response.json()
        
        if result.get("status") and result.get("data", {}).get("links", {}).get("url"):
            return {
                "success": True,
                "url": result["data"]["links"]["url"],
                "provider": "lsky"
            }
        else:
            return {"success": False, "error": result.get("message", "上传失败")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/upload")
@case_conversion_options(skip_request_body=True)
async def upload_file(
    file: UploadFile = File(...),
    storage_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    上传文件到云存储（使用 StorageManager）
    如果不指定 storage_id，使用当前激活的配置
    """
    
    # 读取文件内容
    file_content = await file.read()
    
    # 使用 StorageManager 上传
    manager = StorageManager(db, user_id)
    result = await manager.upload_file(
        filename=file.filename,
        content=file_content,
        content_type=file.content_type,
        storage_id=storage_id
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error") or result.get("message") or "上传失败",
        )
    result["storage_revision"] = await _bump_storage_revision(user_id)
    return result


# ==================== 异步上传任务处理 ====================

async def process_upload_task(task_id: str, _db: Session = None):
    """
    后台处理上传任务
    
    支持两种模式：
    1. 从本地文件上传（source_file_path 存在）
    2. 从 URL 下载后上传（source_url 存在）
    
    上传完成后自动更新数据库中的会话消息
    
    注意：此函数创建独立的数据库会话，避免与请求处理器共享会话导致的竞态条件
    """
    # ✅ 创建独立的数据库会话，避免与其他后台任务共享
    db = SessionLocal()
    try:
        task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
        if not task:
            logger.warning(f"[UploadTask] 任务不存在: {task_id}")
            return
        
        # ✅ 详细日志：确认任务数据
        logger.info(f"[UploadTask] 开始处理任务: {task_id}")
        logger.info(f"  - 文件名: {task.filename}")
        logger.info(f"  - session_id: {task.session_id if task.session_id else 'None'}")
        logger.info(f"  - message_id: {task.message_id if task.message_id else 'None'}")
        logger.info(f"  - attachment_id: {task.attachment_id if task.attachment_id else 'None'}")
        
        # 1. 更新状态为 uploading
        task.status = 'uploading'
        db.commit()
        
        # 2. 获取用户ID和存储配置
        # ✅ 使用 StorageManager 统一管理配置
        user_id = "default"
        if task.session_id:
            session = db.query(ChatSession).filter(ChatSession.id == task.session_id).first()
            if session:
                user_id = session.user_id
        
        # ✅ 使用 StorageManager 统一管理配置和上传
        manager = StorageManager(db, user_id)
        
        # 3. 获取图片内容
        image_content = None
        temp_path = None
        
        if task.source_file_path:
            # 模式 1: 从本地文件读取（使用统一的路径解析）
            file_path = resolve_relative_path(task.source_file_path)
            if os.path.exists(file_path):
                logger.info(f"[UploadTask] 读取本地文件: {ensure_relative_path(task.source_file_path)}")
                with open(file_path, 'rb') as f:
                    image_content = f.read()
                temp_path = file_path
            else:
                raise Exception(f"文件不存在: {task.source_file_path}")
        elif task.source_url:
            # 模式 2: 从 URL 下载
            safe_source_url = _validate_outbound_http_url(task.source_url)
            logger.info(f"[UploadTask] 下载图片: {safe_source_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response, final_url = await _safe_get_with_redirect_guard(client, safe_source_url)
                response.raise_for_status()
                image_content = response.content
            logger.info(f"[UploadTask] 下载完成（最终URL）: {final_url}")
            
            # 保存到项目内临时目录（使用相对路径存储）
            filename_with_id = f"upload_{task_id}_{task.filename}"
            temp_path_abs = os.path.join(TEMP_DIR, filename_with_id)
            temp_path_rel = f"{get_temp_dir_relative()}/{filename_with_id}"
            
            with open(temp_path_abs, 'wb') as f:
                f.write(image_content)
            logger.info(f"[UploadTask] 临时文件: {temp_path_rel}")
            temp_path = temp_path_abs
        else:
            raise Exception("没有可用的图片来源")
        
        # 4. 上传到云存储
        # ✅ 使用 StorageManager 统一管理上传（自动处理配置获取、解密和上传）
        logger.info(f"[UploadTask] 上传到云存储（使用 StorageManager）")
        result = await manager.upload_file(
            filename=task.filename,
            content=image_content,
            content_type='image/png',
            storage_id=task.storage_id  # 如果指定了 storage_id，使用指定的配置
        )
        
        # 5. 删除临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"[UploadTask] 临时文件已删除: {temp_path}")
            except Exception as e:
                logger.warning(f"[UploadTask] 删除临时文件失败: {e}")
        
        # 6. 更新任务状态
        if result.get('success'):
            task.status = 'completed'
            task.target_url = result.get('url')
            task.completed_at = int(datetime.now().timestamp() * 1000)
            db.commit()  # ✅ 先提交任务状态，确保上传成功被记录
            logger.info(f"[UploadTask] 上传成功: {task.target_url}")
            revision = await _bump_storage_revision(user_id)
            logger.info(f"[UploadTask] storage revision bumped: user={user_id}, revision={revision}")
            
            # 7. 更新数据库中的会话消息（即使失败也不影响任务状态）
            if task.session_id and task.message_id and task.attachment_id:
                try:
                    await update_session_attachment_url(
                        db, 
                        task.session_id, 
                        task.message_id, 
                        task.attachment_id, 
                        task.target_url
                    )
                except Exception as e:
                    logger.warning(f"[UploadTask] ⚠️ 更新会话附件 URL 失败（任务已完成）: {e}")
        else:
            task.status = 'failed'
            task.error_message = result.get('error', '上传失败')
            db.commit()
            logger.error(f"[UploadTask] 上传失败: {task.error_message}")
        
    except Exception as e:
        logger.error(f"[UploadTask] 任务失败: {str(e)}")
        try:
            task.status = 'failed'
            task.error_message = str(e)
            db.commit()
        except:
            pass
    finally:
        # ✅ 确保关闭独立的数据库会话
        db.close()


async def update_session_attachment_url(
    db: Session, 
    session_id: str, 
    message_id: str, 
    attachment_id: str, 
    url: str,
    max_retries: int = 10,
    retry_delay: float = 2.0
):
    """
    更新会话中指定附件的 URL (v3 架构)
    
    直接更新 message_attachments 表，无需遍历 JSON
    
    参数：
    - max_retries: 最大重试次数（默认10次）
    - retry_delay: 每次重试间隔（默认2秒）
    """
    from ...models.db_models import MessageAttachment
    import asyncio
    
    logger.info(f"[UploadTask] 开始更新附件 URL: session={session_id}, msg={message_id}, att={attachment_id}")

    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    if not session:
        logger.warning(f"[UploadTask] ⚠️ 会话不存在，跳过附件更新: session={session_id}")
        return

    expected_user_id = session.user_id
    
    for attempt in range(max_retries):
        try:
            db.expire_all()
            
            attachment = db.query(MessageAttachment).filter(
                MessageAttachment.id == attachment_id,
                MessageAttachment.message_id == message_id,
                MessageAttachment.session_id == session_id,
                MessageAttachment.user_id == expected_user_id,
            ).first()
            
            if attachment:
                attachment.url = url
                attachment.upload_status = 'completed'
                attachment.temp_url = None
                db.commit()
                logger.info(f"[UploadTask] 附件表已更新: {attachment_id}, URL: {url}")
                return
            else:
                if attempt < max_retries - 1:
                    logger.debug(f"[UploadTask] 附件不存在，等待重试 ({attempt + 1}/{max_retries}): {attachment_id}")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.warning(f"[UploadTask] 重试 {max_retries} 次后仍未找到附件: {attachment_id}")
                
        except Exception as e:
            logger.error(f"[UploadTask] 更新附件失败: {str(e)}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)


@router.post("/upload-async")
@case_conversion_options(skip_request_body=True)
async def upload_file_async(
    file: UploadFile = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    异步上传文件到云存储（使用 AttachmentService 统一处理）

    使用 AttachmentService.process_user_upload() 统一处理：
    1. 保存文件到临时目录
    2. 创建 MessageAttachment 记录
    3. 创建 UploadTask 记录
    4. 任务 ID 入队 Redis（调度）
    5. 立即返回 task_id（不阻塞）

    请求参数（multipart/form-data）：
    - file: 要上传的文件
    - priority: 优先级 (high/normal/low，默认 normal)
    - session_id: 会话 ID（必需）
    - message_id: 消息 ID（必需）
    - attachment_id: 附件 ID（可选，如果不提供则自动生成）
    - storage_id: 云存储配置 ID（可选）

    返回：
    {
        "task_id": "task-xxx",
        "attachment_id": "att-xxx",
        "status": "pending",
        "priority": "normal",
        "queue_position": 5
    }
    """
    import time
    start_time = time.time()
    
    logger.info(f"[UploadAsync] ========== 开始处理异步上传请求 ==========")
    logger.info(f"[UploadAsync] 📥 请求参数:")
    logger.info(f"[UploadAsync]     - filename: {file.filename}")
    logger.info(f"[UploadAsync]     - content_type: {file.content_type}")
    logger.info(f"[UploadAsync]     - session_id: {session_id if session_id else 'None'}")
    logger.info(f"[UploadAsync]     - message_id: {message_id if message_id else 'None'}")
    logger.info(f"[UploadAsync]     - attachment_id: {attachment_id if attachment_id else 'None'}")
    logger.info(f"[UploadAsync]     - storage_id: {storage_id if storage_id else 'None'}")
    logger.info(f"[UploadAsync]     - priority: {priority}")
    logger.info(f"[UploadAsync]     - user_id: {user_id}")
    
    # ✅ 验证必需参数
    if not session_id or not message_id:
        logger.error(f"[UploadAsync] ❌ 验证失败: session_id 和 message_id 是必需的参数")
        raise HTTPException(
            status_code=400, 
            detail="session_id 和 message_id 是必需的参数"
        )
    logger.info(f"[UploadAsync] ✅ 参数验证通过")
    
    # ✅ 使用 AttachmentService 统一处理用户上传
    from ...services.common.attachment_service import AttachmentService
    
    # ✅ 详细日志：步骤1 - 保存文件到临时目录
    logger.info(f"[UploadAsync] 🔄 [步骤1] 保存文件到临时目录...")
    task_id = str(uuid.uuid4())
    filename_with_id = f"upload_{task_id}_{file.filename}"
    temp_path_abs = os.path.join(TEMP_DIR, filename_with_id)
    temp_path_rel = f"{get_temp_dir_relative()}/{filename_with_id}"
    
    logger.info(f"[UploadAsync]     - 临时文件路径: {temp_path_abs}")
    logger.info(f"[UploadAsync]     - 相对路径: {temp_path_rel}")
    
    file_content = await file.read()
    file_size = len(file_content)
    logger.info(f"[UploadAsync]     - 文件大小: {file_size / 1024:.2f} KB")
    
    with open(temp_path_abs, 'wb') as f:
        f.write(file_content)
    
    step1_time = (time.time() - start_time) * 1000
    logger.info(f"[UploadAsync] ✅ [步骤1] 文件已保存 (耗时: {step1_time:.2f}ms)")
    
    # ✅ 详细日志：步骤2 - 获取存储配置ID
    logger.info(f"[UploadAsync] 🔄 [步骤2] 获取存储配置ID...")
    if storage_id:
        logger.info(f"[UploadAsync]     - 使用提供的 storage_id: {storage_id}")
    else:
        logger.info(f"[UploadAsync]     - 未提供 storage_id，查询激活的配置...")
    resolved_storage_id, _ = _resolve_enabled_storage_config(
        db=db,
        user_id=user_id,
        storage_id=storage_id,
    )
    logger.info(f"[UploadAsync] ✅ [步骤2] 存储配置验证通过: {resolved_storage_id}")
    
    # ✅ 详细日志：步骤3 - 使用 AttachmentService 处理用户上传
    logger.info(f"[UploadAsync] 🔄 [步骤3] 调用 AttachmentService.process_user_upload()...")
    attachment_service = AttachmentService(db)
    result = await attachment_service.process_user_upload(
        file_path=temp_path_rel,  # 相对路径
        filename=file.filename,
        mime_type=file.content_type or 'application/octet-stream',
        session_id=session_id,
        message_id=message_id,
        user_id=user_id,
        storage_id=resolved_storage_id,  # ✅ 传递存储配置ID
        priority=priority  # ✅ 传递优先级
    )
    step3_time = (time.time() - start_time) * 1000
    logger.info(f"[UploadAsync] ✅ [步骤3] AttachmentService 处理完成 (耗时: {step3_time:.2f}ms)")
    logger.info(f"[UploadAsync]     - attachment_id: {result['attachment_id']}")
    logger.info(f"[UploadAsync]     - task_id: {result.get('task_id') if result.get('task_id') else 'None'}")
    logger.info(f"[UploadAsync]     - status: {result['status']}")
    
    # ✅ 详细日志：步骤4 - 如果提供了 attachment_id，更新记录（向后兼容）
    if attachment_id and attachment_id != result['attachment_id']:
        logger.info(f"[UploadAsync] 🔄 [步骤4] 更新 attachment_id (向后兼容)...")
        logger.info(f"[UploadAsync]     - 提供的 attachment_id: {attachment_id}")
        logger.info(f"[UploadAsync]     - 生成的 attachment_id: {result['attachment_id']}")
        from ...models.db_models import MessageAttachment, UploadTask
        
        attachment = db.query(MessageAttachment).filter_by(
            id=result['attachment_id']
        ).first()
        if attachment:
            # 更新 MessageAttachment.id
            attachment.id = attachment_id
            db.commit()
            
            # ✅ 新增：同步更新 UploadTask.attachment_id
            upload_task = db.query(UploadTask).filter_by(
                attachment_id=result['attachment_id']
            ).first()
            if upload_task:
                upload_task.attachment_id = attachment_id
                db.commit()
                logger.info(f"[UploadAsync] ✅ [步骤4] UploadTask.attachment_id 已同步更新")
            else:
                logger.warning(f"[UploadAsync] ⚠️ [步骤4] 未找到 UploadTask 记录，跳过同步更新")
            
            result['attachment_id'] = attachment_id
            logger.info(f"[UploadAsync] ✅ [步骤4] attachment_id 已更新")
        else:
            logger.warning(f"[UploadAsync] ⚠️ [步骤4] 未找到附件记录，跳过更新")
    else:
        logger.info(f"[UploadAsync] ⏭️ [步骤4] 跳过 attachment_id 更新（未提供或已匹配）")
    
    # 注意：AttachmentService._submit_upload_task() 已经入队 Redis
    # 这里不需要再次入队，只需要返回结果
    queue_position = 0  # AttachmentService 已入队，位置由 Worker Pool 管理
    enqueue_error = None
    
    total_time = (time.time() - start_time) * 1000
    logger.info(f"[UploadAsync] ========== 异步上传请求处理完成 (总耗时: {total_time:.2f}ms) ==========")
    logger.info(f"[UploadAsync]     - attachment_id: {result['attachment_id']}")
    logger.info(f"[UploadAsync]     - task_id: {result.get('task_id') if result.get('task_id') else 'None'}")
    logger.info(f"[UploadAsync]     - status: {result['status']}")
    
    return {
        "task_id": result.get('task_id'),
        "attachment_id": result['attachment_id'],
        "status": result['status'],
        "priority": priority,
        "queue_position": queue_position,
        "enqueued": queue_position != -1,
        "enqueue_error": enqueue_error
    }


@router.post("/upload-from-url")
@case_conversion_options(skip_request_body=True)
async def upload_from_url(
    data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    从 URL 下载图片并上传到云存储（异步）
    
    请求参数：
    {
        "url": "https://dashscope.aliyuncs.com/...",  # DashScope 临时 URL
        "filename": "expanded-1234567890.png",         # 文件名
        "session_id": "session-xxx",                   # 会话 ID（用于更新数据库）
        "message_id": "msg-xxx",                       # 消息 ID
        "attachment_id": "att-xxx",                    # 附件 ID
        "storage_id": "storage-xxx"                    # 云存储配置 ID（可选）
    }
    
    返回：
    {
        "task_id": "task-xxx",
        "status": "pending",
        "message": "上传任务已创建"
    }
    """
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="请求体必须为 JSON 对象")

    safe_source_url = _validate_outbound_http_url(data.get("url"))
    filename = str(data.get("filename") or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename 不能为空")

    resolved_storage_id, _ = _resolve_enabled_storage_config(
        db=db,
        user_id=user_id,
        storage_id=data.get("storage_id"),
    )

    # 创建上传任务
    task_id = str(uuid.uuid4())
    priority = data.get("priority", "normal")

    task = UploadTask(
        id=task_id,
        session_id=data.get('session_id'),
        message_id=data.get('message_id'),
        attachment_id=data.get('attachment_id'),
        source_url=safe_source_url,
        filename=filename,
        storage_id=resolved_storage_id,
        priority=priority,
        retry_count=0,
        status='pending',
        created_at=int(datetime.now().timestamp() * 1000)
    )

    db.add(task)
    db.commit()

    # 入队任务到 Redis
    enqueue_error: str | None = None
    queue_position: int = -1

    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        queue_position = await redis_queue.enqueue(task_id, priority)
        await redis_queue.append_task_log(
            task_id,
            level="info",
            message=f"enqueued to redis (position={queue_position})",
            source="api",
        )
    except Exception as e:
        enqueue_error = f"Redis 入队失败: {e}"
        try:
            task.error_message = enqueue_error
            db.commit()
        except Exception:
            db.rollback()
        queue_position = -1

    return {
        "task_id": task_id,
        "status": "pending",
        "priority": priority,
        "queue_position": queue_position,
        "enqueued": queue_position != -1,
        "enqueue_error": enqueue_error
    }


@router.get("/upload-status/{task_id}")
async def get_upload_status(
    task_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    查询上传任务状态

    返回：
    {
        "id": "task-xxx",
        "status": "completed",
        "targetUrl": "https://cdn.example.com/xxx.png",
        "errorMessage": null,
        "createdAt": 1234567890000,
        "completedAt": 1234567890000
    }
    """
    task = _require_owned_upload_task(db, task_id, user_id)
    return task.to_dict()


@router.get("/worker-pool/health")
async def get_worker_pool_health(db: Session = Depends(get_db)):
    """
    获取 Worker 池健康状态

    返回：
    {
        "available": true,
        "running": true,
        "num_workers": 5,
        "redis_connected": true,
        "pending_tasks_count": 3,
        "redis_queue_length": 3
    }
    """
    try:
        from ...services.common.upload_worker_pool import worker_pool, WORKER_POOL_AVAILABLE
        from ...services.common.redis_queue_service import redis_queue
    except ImportError:
        return {
            "available": False,
            "running": False,
            "num_workers": 0,
            "redis_connected": False,
            "pending_tasks_count": 0,
            "redis_queue_length": 0,
            "error": "Worker pool module not available"
        }

    health = {
        "available": WORKER_POOL_AVAILABLE,
        "running": False,
        "num_workers": 0,
        "redis_connected": False,
        "pending_tasks_count": 0,
        "redis_queue_length": 0
    }

    if WORKER_POOL_AVAILABLE:
        health["running"] = worker_pool._running
        health["num_workers"] = len(worker_pool._workers)

        # 检查 Redis 连接
        try:
            health["redis_connected"] = redis_queue._redis is not None
            if health["redis_connected"]:
                # 获取队列长度
                stats = await redis_queue.get_stats()
                health["redis_queue_length"] = stats.get("total_enqueued", 0) - stats.get("total_dequeued", 0)
        except Exception:
            health["redis_connected"] = False

        # 获取 pending 任务数量
        try:
            health["pending_tasks_count"] = db.query(UploadTask).filter(
                UploadTask.status == 'pending'
            ).count()
        except Exception:
            pass

    return health


@router.get("/upload-task-db/{task_id}")
async def get_upload_task_db(
    task_id: str,
    response: Response,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    直接从数据库读取 upload_tasks 行（用于排查“看不到更新/必须重启才刷新”）。

    - 不经过 ORM 对象缓存（使用 SQL 读取）
    - 返回 server 信息用于确认命中的是哪个后端进程
    """
    response.headers["Cache-Control"] = "no-store"
    _require_owned_upload_task(db, task_id, user_id)

    row = (
        db.execute(
            text(
                """
                SELECT
                  id,
                  status,
                  filename,
                  priority,
                  retry_count,
                  source_url,
                  source_file_path,
                  target_url,
                  error_message,
                  created_at,
                  completed_at
                FROM upload_tasks
                WHERE id = :id
                """
            ),
            {"id": task_id},
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    return {
        "task": dict(row),
        "server": {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "module_file": __file__,
        },
    }


@router.get("/upload-logs/{task_id}")
async def get_upload_logs(
    task_id: str,
    tail: int = 200,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """获取上传任务日志（来自 Redis）。"""
    _require_owned_upload_task(db, task_id, user_id)
    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        logs = await redis_queue.get_task_logs(task_id, tail=tail)
        return {"task_id": task_id, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"获取任务日志失败: {e}")


@router.post("/retry-upload/{task_id}")
async def retry_upload(
    task_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    重试失败的上传任务（Redis 队列）

    返回：
    {
        "task_id": "task-xxx",
        "status": "pending",
        "queue_position": 5
    }
    """
    task = _require_owned_upload_task(db, task_id, user_id)

    if task.status not in ['failed', 'completed']:
        raise HTTPException(status_code=400, detail="只能重试失败的任务")

    # 重置任务状态
    task.status = 'pending'
    task.error_message = None
    task.target_url = None
    task.completed_at = None
    db.commit()

    # 重新入队 Redis（低优先级）
    queue_position = await redis_queue.enqueue(task_id, 'low')

    return {
        "task_id": task_id,
        "status": "pending",
        "queue_position": queue_position
    }


@router.post("/items/downloads")
async def prepare_storage_download(
    payload: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    准备云存储下载包，返回可稳定复用的下载地址。

    支持：
    - 单文件下载
    - 多文件打包下载
    - 目录递归打包下载
    """
    _cleanup_expired_storage_downloads()

    storage_id = payload.get("storage_id")
    items = payload.get("items") or []
    if not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="items is required")

    resolved_storage_id, _ = _resolve_enabled_storage_config(db, user_id, storage_id)
    manager = StorageManager(db, user_id)
    allowed_hosts = _collect_storage_preview_host_allowlist(db, user_id)

    entries, skipped_entries = await _collect_storage_download_entries(
        manager,
        storage_id=resolved_storage_id,
        items=items,
        max_total_files=_STORAGE_DOWNLOAD_MAX_TOTAL_FILES,
    )
    if len(entries) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "没有可下载的文件",
                "skipped": skipped_entries,
            },
        )

    requested_single_file = len(items) == 1 and not bool((items[0] or {}).get("is_directory", False))
    if len(entries) > _STORAGE_DOWNLOAD_MAX_TOTAL_FILES:
        raise HTTPException(
            status_code=413,
            detail=_storage_download_file_limit_message(_STORAGE_DOWNLOAD_MAX_TOTAL_FILES),
        )

    if requested_single_file and len(entries) == 1:
        known_file_size = _extract_non_negative_int(entries[0].get("size"))
        if known_file_size is not None and known_file_size > _STORAGE_DOWNLOAD_MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=_storage_download_size_limit_message("单文件下载", _STORAGE_DOWNLOAD_MAX_FILE_BYTES),
            )
    else:
        known_archive_bytes = 0
        for entry in entries:
            entry_size = _extract_non_negative_int(entry.get("size"))
            if entry_size is None:
                continue
            known_archive_bytes += entry_size
            if known_archive_bytes > _STORAGE_DOWNLOAD_MAX_ARCHIVE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=_storage_download_size_limit_message("下载归档", _STORAGE_DOWNLOAD_MAX_ARCHIVE_BYTES),
                )

    download_id = uuid.uuid4().hex

    try:
        if requested_single_file and len(entries) == 1:
            entry = entries[0]
            safe_url = _resolve_safe_preview_fetch_url(str(entry.get("file_url") or ""), allowed_hosts)
            provisional_name = _sanitize_download_name(
                str(entry.get("name") or ""),
                f"storage-download-{download_id[:8]}",
            )
            suffix = Path(provisional_name).suffix or ".bin"
            file_path = _storage_download_payload_path(download_id, suffix)
            stream_result = await _stream_safe_url_to_file(
                safe_url,
                target_path=file_path,
                allowed_hosts=allowed_hosts,
                max_bytes=_STORAGE_DOWNLOAD_MAX_FILE_BYTES,
                size_limit_label="单文件下载",
            )

            file_name = provisional_name
            if not Path(file_name).suffix:
                final_suffix = Path(urlparse(str(stream_result.get("final_url") or "")).path).suffix
                if not final_suffix:
                    mime_type = str(stream_result.get("content_type") or "").split(";", 1)[0].strip()
                    final_suffix = mimetypes.guess_extension(mime_type) or ""
                if final_suffix:
                    file_name = f"{file_name}{final_suffix}"

            metadata = _persist_storage_download_metadata(
                download_id,
                user_id=user_id,
                file_path=file_path,
                file_name=file_name,
                media_type=str(stream_result.get("content_type") or "application/octet-stream"),
                archive=False,
                total_files=1,
                skipped_count=len(skipped_entries),
            )

            return {
                "success": True,
                "download_id": download_id,
                "download_url": f"/api/storage/downloads/{download_id}",
                "file_name": file_name,
                "archive": False,
                "total_files": 1,
                "skipped_count": len(skipped_entries),
                "created_at": metadata["created_at"],
                "expires_at": metadata["expires_at"],
            }

        root_name = str((items[0] or {}).get("name") or "").strip() if len(items) == 1 else ""
        archive_name_base = _sanitize_download_name(
            root_name or f"storage-download-{download_id[:8]}",
            "storage-download",
        )
        archive_name = archive_name_base if archive_name_base.lower().endswith(".zip") else f"{archive_name_base}.zip"
        archive_path = _storage_download_payload_path(download_id, ".zip")

        manifest_items: list[dict[str, Any]] = [dict(item) for item in skipped_entries]
        used_archive_paths: set[str] = set()
        downloaded_count = 0
        downloaded_bytes = 0

        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zip_file:
            for entry in entries:
                safe_url = _resolve_safe_preview_fetch_url(str(entry.get("file_url") or ""), allowed_hosts)
                archive_member_path = _ensure_unique_archive_path(
                    str(entry.get("archive_path") or "file"),
                    used_archive_paths,
                )
                try:
                    remaining_archive_bytes = _STORAGE_DOWNLOAD_MAX_ARCHIVE_BYTES - downloaded_bytes
                    if remaining_archive_bytes <= 0:
                        raise HTTPException(
                            status_code=413,
                            detail=_storage_download_size_limit_message("下载归档", _STORAGE_DOWNLOAD_MAX_ARCHIVE_BYTES),
                        )
                    stream_result = await _write_safe_url_to_zip(
                        zip_file,
                        archive_path=archive_member_path,
                        safe_url=safe_url,
                        allowed_hosts=allowed_hosts,
                        max_bytes=remaining_archive_bytes,
                        size_limit_label="下载归档",
                    )
                    downloaded_count += 1
                    downloaded_bytes += _extract_non_negative_int(stream_result.get("content_length")) or 0
                    manifest_items.append({
                        "path": entry.get("path"),
                        "archivePath": archive_member_path,
                        "status": "downloaded",
                        "size": stream_result.get("content_length"),
                        "mimeType": str(stream_result.get("content_type") or "").split(";", 1)[0].strip(),
                        "resolvedUrl": stream_result.get("final_url"),
                    })
                except HTTPException as exc:
                    if exc.status_code == 413:
                        raise
                    manifest_items.append({
                        "path": entry.get("path"),
                        "archivePath": archive_member_path,
                        "status": "skipped",
                        "reason": str(exc.detail),
                    })
                except Exception as exc:
                    manifest_items.append({
                        "path": entry.get("path"),
                        "archivePath": archive_member_path,
                        "status": "skipped",
                        "reason": str(exc),
                    })

            manifest_payload = {
                "storageId": resolved_storage_id,
                "generatedAt": int(time.time() * 1000),
                "downloadedCount": downloaded_count,
                "skippedCount": len([item for item in manifest_items if item.get("status") != "downloaded"]),
                "items": manifest_items,
            }
            zip_file.writestr(
                "manifest.json",
                json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            )

        if downloaded_count <= 0:
            _cleanup_storage_download_by_id(download_id)
            raise HTTPException(status_code=400, detail="没有可下载的文件")

        skipped_count = len([item for item in manifest_items if item.get("status") != "downloaded"])
        metadata = _persist_storage_download_metadata(
            download_id,
            user_id=user_id,
            file_path=archive_path,
            file_name=archive_name,
            media_type="application/zip",
            archive=True,
            total_files=downloaded_count,
            skipped_count=skipped_count,
        )

        return {
            "success": True,
            "download_id": download_id,
            "download_url": f"/api/storage/downloads/{download_id}",
            "file_name": archive_name,
            "archive": True,
            "total_files": downloaded_count,
            "skipped_count": skipped_count,
            "created_at": metadata["created_at"],
            "expires_at": metadata["expires_at"],
        }
    except HTTPException:
        _cleanup_storage_download_by_id(download_id)
        raise
    except Exception as exc:
        _cleanup_storage_download_by_id(download_id)
        raise HTTPException(status_code=500, detail=f"准备下载失败: {str(exc)}") from exc


@router.get("/downloads/{download_id}")
async def get_prepared_storage_download(
    download_id: str,
    user_id: str = Depends(require_current_user),
):
    """
    获取已准备好的下载文件。

    文件保存在服务端临时目录中，通过稳定 URL 提供，便于浏览器继续/续传下载。
    """
    _cleanup_expired_storage_downloads()
    metadata = _load_storage_download_metadata(download_id, user_id=user_id)
    file_path = Path(str(metadata.get("file_path") or ""))

    return FileResponse(
        path=file_path,
        media_type=str(metadata.get("media_type") or "application/octet-stream"),
        filename=str(metadata.get("file_name") or file_path.name),
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=0, must-revalidate",
            "Vary": "Authorization, Cookie",
            "X-Content-Type-Options": "nosniff",
            "X-Storage-Download-Id": download_id,
            "X-Storage-Download-Expires-At": str(metadata.get("expires_at") or ""),
        },
    )


@router.get("/local-files/{relative_path:path}", include_in_schema=False)
async def get_local_storage_file(relative_path: str):
    normalized_relative_path = str(relative_path or "").strip().lstrip("/")
    if not normalized_relative_path:
        raise HTTPException(status_code=404, detail="File not found")

    public_url = f"{DEFAULT_LOCAL_URL_PREFIX}/{normalized_relative_path}"
    file_path = resolve_local_public_file_path(public_url)
    if file_path is None or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    guessed_media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    return FileResponse(
        path=file_path,
        media_type=guessed_media_type,
        filename=file_path.name,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/download")
async def download_image(
    url: str,
    request: Request,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    图片下载代理接口
    
    解决跨域问题，后端下载图片后返回给前端
    
    请求参数：
    - url: 图片 URL（云存储地址）
    
    返回：
    - 图片文件流
    """
    try:
        allowed_hosts = _collect_storage_preview_host_allowlist(db, user_id)
        safe_url = _resolve_safe_preview_fetch_url(url, allowed_hosts)
        storage_revision = await _get_storage_revision(user_id)
        upstream_request_headers = _build_upstream_range_request_headers(request)
        client, upstream_response, final_url = await _open_safe_stream_with_redirect_guard(
            safe_url,
            allowed_hosts=allowed_hosts,
            timeout=30.0,
            request_headers=upstream_request_headers or None,
        )

        if upstream_response.status_code < 200 or upstream_response.status_code >= 300:
            detail_text = await _read_upstream_error_detail(upstream_response)
            await upstream_response.aclose()
            await client.aclose()
            detail = detail_text or f"上游下载失败: HTTP {upstream_response.status_code}"
            raise HTTPException(status_code=upstream_response.status_code, detail=detail)

        content_type = upstream_response.headers.get('content-type', 'application/octet-stream')
        filename = final_url.split('/')[-1].split('?')[0] or f'image-{uuid.uuid4().hex[:8]}.png'

        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=0, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        }
        headers["X-Storage-Revision"] = str(storage_revision)
        _apply_private_auth_vary(headers)
        _copy_upstream_proxy_headers(headers, upstream_response, include_upstream_etag=True)

        return _streaming_proxy_response(
            client,
            upstream_response,
            media_type=content_type,
            headers=headers,
            status_code=upstream_response.status_code,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.get("/preview")
async def preview_file(
    url: str,
    request: Request,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    文件预览代理接口

    用于前端缩略图/预览，返回 inline 内容（不强制 attachment）。
    """
    try:
        allowed_hosts = _collect_storage_preview_host_allowlist(db, user_id)
        safe_url = _resolve_safe_preview_fetch_url(url, allowed_hosts)
        storage_revision = await _get_storage_revision(user_id)
        proxy_etag = _build_preview_proxy_etag(safe_url, storage_revision)
        base_headers = {
            "Cache-Control": "private, max-age=86400, stale-while-revalidate=604800",
            "X-Storage-Revision": str(storage_revision),
            "ETag": proxy_etag,
            "X-Content-Type-Options": "nosniff",
        }
        _apply_private_auth_vary(base_headers)

        range_requested = bool(str(request.headers.get("range") or "").strip())
        if not range_requested and _request_matches_etag(request, proxy_etag):
            return Response(status_code=304, headers=base_headers)

        upstream_request_headers = _build_upstream_range_request_headers(
            request,
            current_etag=proxy_etag,
        )
        client, upstream_response, _ = await _open_safe_stream_with_redirect_guard(
            safe_url,
            allowed_hosts=allowed_hosts,
            timeout=30.0,
            request_headers=upstream_request_headers or None,
        )

        if upstream_response.status_code < 200 or upstream_response.status_code >= 300:
            detail_text = await _read_upstream_error_detail(upstream_response)
            await upstream_response.aclose()
            await client.aclose()
            detail = detail_text or f"上游预览失败: HTTP {upstream_response.status_code}"
            raise HTTPException(status_code=upstream_response.status_code, detail=detail)

        content_type = upstream_response.headers.get('content-type', 'application/octet-stream')
        headers = dict(base_headers)
        _copy_upstream_proxy_headers(headers, upstream_response)

        return _streaming_proxy_response(
            client,
            upstream_response,
            media_type=content_type,
            headers=headers,
            status_code=upstream_response.status_code,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")
