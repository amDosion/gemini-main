"""Admin system routes for system configuration and runtime status."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.logger import DatabaseLoggingFilter
from ...models.db_models import User
from ...services.common.system_config_service import get_system_config, update_system_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/admin", tags=["system-admin"])
NO_CONTROL_CHARS_PATTERN = r"^[^\x00-\x1F\x7F]*$"
MAX_RUNTIME_BYTES = 9_000_000_000_000_000

PROCESS_START_TIME = time.time()
_NETWORK_SNAPSHOT_LOCK = threading.Lock()
_NETWORK_SNAPSHOT: Optional[Dict[str, float]] = None
_DISK_IO_SNAPSHOT_LOCK = threading.Lock()
_DISK_IO_SNAPSHOT: Optional[Dict[str, float]] = None


class SystemConfigUpdateRequest(BaseModel):
    """Mutable system configuration fields for admin updates."""

    allow_registration: Optional[bool] = None
    max_login_attempts: Optional[int] = Field(default=None, ge=1, le=100)
    max_login_attempts_per_ip: Optional[int] = Field(default=None, ge=1, le=200)
    login_lockout_duration: Optional[int] = Field(default=None, ge=60, le=86400)
    enable_logging: Optional[bool] = None


class SystemConfigField(BaseModel):
    """Schema metadata for frontend dynamic form rendering."""

    key: str = Field(max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)
    label: str = Field(max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    type: Literal["boolean", "number", "string"]
    description: Optional[str] = Field(default=None, max_length=512, pattern=NO_CONTROL_CHARS_PATTERN)
    editable: bool = True
    min: Optional[int] = None
    max: Optional[int] = None
    step: Optional[int] = None
    unit: Optional[str] = Field(default=None, max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)


class SystemConfigValuesResponse(BaseModel):
    allowRegistration: bool
    maxLoginAttempts: int = Field(ge=1, le=100)
    maxLoginAttemptsPerIp: int = Field(ge=1, le=200)
    loginLockoutDuration: int = Field(ge=60, le=86400)
    enableLogging: bool


class SystemConfigResponse(BaseModel):
    values: SystemConfigValuesResponse
    fields: List[SystemConfigField] = Field(max_length=32)
    updated_at: Optional[str] = Field(default=None, max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)


class SystemHostResponse(BaseModel):
    hostname: str = Field(max_length=255, pattern=NO_CONTROL_CHARS_PATTERN)
    platform: str = Field(max_length=512, pattern=NO_CONTROL_CHARS_PATTERN)
    python_version: str = Field(max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)
    cpu_count: int = Field(ge=1, le=4096)
    process_uptime_seconds: int = Field(ge=0, le=31_536_000_000)


class SystemCpuMetricsResponse(BaseModel):
    usage_percent: Optional[float] = Field(default=None, ge=0, le=100)


class SystemMemoryMetricsResponse(BaseModel):
    usage_percent: Optional[float] = Field(default=None, ge=0, le=100)
    used_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    total_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    available_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)


class SystemDiskMetricsResponse(BaseModel):
    path: str = Field(max_length=4096, pattern=NO_CONTROL_CHARS_PATTERN)
    usage_percent: Optional[float] = Field(default=None, ge=0, le=100)
    used_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    total_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    free_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    read_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    write_bytes: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    read_rate_bps: Optional[float] = Field(default=None, ge=0, le=1_000_000_000_000_000)
    write_rate_bps: Optional[float] = Field(default=None, ge=0, le=1_000_000_000_000_000)


class SystemNetworkMetricsResponse(BaseModel):
    usage_percent: Optional[float] = Field(default=None, ge=0, le=100)
    bytes_sent: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    bytes_recv: Optional[int] = Field(default=None, ge=0, le=MAX_RUNTIME_BYTES)
    tx_rate_bps: Optional[float] = Field(default=None, ge=0, le=1_000_000_000_000_000)
    rx_rate_bps: Optional[float] = Field(default=None, ge=0, le=1_000_000_000_000_000)
    max_link_speed_mbps: Optional[float] = Field(default=None, ge=0, le=1_000_000)


class SystemMetricsResponse(BaseModel):
    cpu: SystemCpuMetricsResponse
    memory: SystemMemoryMetricsResponse
    disk: SystemDiskMetricsResponse
    network: SystemNetworkMetricsResponse


class SystemStatusResponse(BaseModel):
    timestamp: str = Field(max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)
    host: SystemHostResponse
    collector: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    metrics: SystemMetricsResponse


class AdminHealthComponentResponse(BaseModel):
    status: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    latency_ms: float = Field(ge=0, le=3_600_000)
    error: Optional[str] = Field(default=None, max_length=1024, pattern=NO_CONTROL_CHARS_PATTERN)


class AdminGeminiPoolHealthResponse(BaseModel):
    initialized: bool
    sdk_available: bool
    active_clients: int = Field(ge=0, le=10_000)
    max_size: int = Field(ge=0, le=10_000)
    error: Optional[str] = Field(default=None, max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)


class AdminHealthResponse(BaseModel):
    status: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)
    components: Dict[str, AdminHealthComponentResponse]
    selenium: bool
    pdf_extraction: bool
    embedding: bool
    upload_worker_pool: bool
    gemini_pool: AdminGeminiPoolHealthResponse
    version: str = Field(max_length=32, pattern=NO_CONTROL_CHARS_PATTERN)


class GeminiPoolClientMetadataResponse(BaseModel):
    created_at: str = Field(max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)
    api_key_configured: bool
    vertexai: bool
    project: Optional[str] = Field(default=None, max_length=256, pattern=NO_CONTROL_CHARS_PATTERN)
    location: Optional[str] = Field(default=None, max_length=128, pattern=NO_CONTROL_CHARS_PATTERN)
    client_type: str = Field(max_length=64, pattern=NO_CONTROL_CHARS_PATTERN)
    http_timeout: Optional[int] = Field(default=None, ge=0, le=3_600_000)
    http_retry_attempts: Optional[int] = Field(default=None, ge=0, le=100)


class GeminiPoolStatsResponse(BaseModel):
    total_clients: int = Field(ge=0, le=10_000_000)
    active_clients: int = Field(ge=0, le=10_000)
    max_size: int = Field(ge=0, le=10_000)
    cache_hits: int = Field(ge=0, le=10_000_000_000)
    cache_misses: int = Field(ge=0, le=10_000_000_000)
    rejected_due_to_max_size: int = Field(ge=0, le=10_000_000_000)
    total_requests: int = Field(ge=0, le=10_000_000_000)
    hit_rate: float = Field(ge=0, le=1)
    clients: Dict[str, GeminiPoolClientMetadataResponse]


class SystemCleanupResponse(BaseModel):
    cleaned: Dict[str, int]
    freed_bytes: int = Field(ge=0, le=MAX_RUNTIME_BYTES)


SYSTEM_CONFIG_FIELDS: List[SystemConfigField] = [
    SystemConfigField(
        key="allowRegistration",
        label="允许注册",
        type="boolean",
        description="控制是否允许新用户注册",
    ),
    SystemConfigField(
        key="maxLoginAttempts",
        label="邮箱最大失败次数",
        type="number",
        description="单个邮箱在锁定窗口内允许的最大登录失败次数",
        min=1,
        max=100,
        step=1,
        unit="次",
    ),
    SystemConfigField(
        key="maxLoginAttemptsPerIp",
        label="IP 最大尝试次数",
        type="number",
        description="单个 IP 在锁定窗口内允许的最大登录尝试次数",
        min=1,
        max=200,
        step=1,
        unit="次",
    ),
    SystemConfigField(
        key="loginLockoutDuration",
        label="锁定时长",
        type="number",
        description="登录限制触发后的锁定时长",
        min=60,
        max=86400,
        step=60,
        unit="秒",
    ),
    SystemConfigField(
        key="enableLogging",
        label="启用日志展示",
        type="boolean",
        description="控制前端是否展示系统日志信息",
    ),
]


def require_admin_user(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> str:
    """Require current authenticated user to be an admin user."""

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not bool(user.is_admin):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user_id


def _serialize_system_config(config: Any) -> Dict[str, Any]:
    return {
        "allowRegistration": bool(config.allow_registration),
        "maxLoginAttempts": int(config.max_login_attempts),
        "maxLoginAttemptsPerIp": int(config.max_login_attempts_per_ip),
        "loginLockoutDuration": int(config.login_lockout_duration),
        "enableLogging": bool(config.enable_logging),
    }


def _round2(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def _safe_disk_path() -> str:
    if os.name == "nt":
        return os.path.splitdrive(os.getcwd())[0] + "\\"
    return "/"


def _calculate_rate(
    previous: Optional[Dict[str, float]],
    now: float,
    total_key: str,
    current_total: float,
) -> Optional[float]:
    if not previous:
        return None
    previous_ts = float(previous.get("timestamp", 0.0))
    if now <= previous_ts:
        return None
    elapsed = max(0.001, now - previous_ts)
    previous_total = float(previous.get(total_key, 0.0))
    return max(0.0, (current_total - previous_total) / elapsed)


def _collect_system_status() -> Dict[str, Any]:
    """
    Collect runtime metrics.

    Priority:
    1. psutil (accurate CPU/memory/disk/network)
    2. fallback using stdlib when psutil is unavailable
    """

    now = time.time()
    status: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count() or 1,
            "process_uptime_seconds": int(max(0.0, now - PROCESS_START_TIME)),
        },
    }

    try:
        import psutil  # type: ignore

        cpu_percent = float(psutil.cpu_percent(interval=0.1))

        memory = psutil.virtual_memory()
        disk_path = _safe_disk_path()
        disk = psutil.disk_usage(disk_path)
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        tx_rate_bps: Optional[float] = None
        rx_rate_bps: Optional[float] = None

        global _NETWORK_SNAPSHOT
        with _NETWORK_SNAPSHOT_LOCK:
            previous = _NETWORK_SNAPSHOT
            _NETWORK_SNAPSHOT = {
                "timestamp": now,
                "bytes_sent": float(net_io.bytes_sent),
                "bytes_recv": float(net_io.bytes_recv),
            }

        tx_rate_bps = _calculate_rate(
            previous=previous,
            now=now,
            total_key="bytes_sent",
            current_total=float(net_io.bytes_sent),
        )
        rx_rate_bps = _calculate_rate(
            previous=previous,
            now=now,
            total_key="bytes_recv",
            current_total=float(net_io.bytes_recv),
        )

        read_bytes_total: Optional[int] = None
        write_bytes_total: Optional[int] = None
        read_rate_bps: Optional[float] = None
        write_rate_bps: Optional[float] = None
        if disk_io:
            read_bytes_total = int(disk_io.read_bytes)
            write_bytes_total = int(disk_io.write_bytes)

            global _DISK_IO_SNAPSHOT
            with _DISK_IO_SNAPSHOT_LOCK:
                previous_disk = _DISK_IO_SNAPSHOT
                _DISK_IO_SNAPSHOT = {
                    "timestamp": now,
                    "read_bytes": float(disk_io.read_bytes),
                    "write_bytes": float(disk_io.write_bytes),
                }

            read_rate_bps = _calculate_rate(
                previous=previous_disk,
                now=now,
                total_key="read_bytes",
                current_total=float(disk_io.read_bytes),
            )
            write_rate_bps = _calculate_rate(
                previous=previous_disk,
                now=now,
                total_key="write_bytes",
                current_total=float(disk_io.write_bytes),
            )

        max_link_speed_mbps: Optional[float] = None
        try:
            speeds = []
            for _, stats in psutil.net_if_stats().items():
                if stats.isup and getattr(stats, "speed", 0) and stats.speed > 0:
                    speeds.append(float(stats.speed))
            if speeds:
                max_link_speed_mbps = max(speeds)
        except Exception:
            max_link_speed_mbps = None

        network_usage_percent: Optional[float] = None
        if max_link_speed_mbps and (tx_rate_bps is not None or rx_rate_bps is not None):
            capacity_bps = (max_link_speed_mbps * 1_000_000.0) / 8.0
            if capacity_bps > 0:
                network_usage_percent = min(100.0, ((tx_rate_bps or 0.0) + (rx_rate_bps or 0.0)) / capacity_bps * 100.0)

        status["collector"] = "psutil"
        status["metrics"] = {
            "cpu": {
                "usage_percent": _round2(cpu_percent),
            },
            "memory": {
                "usage_percent": _round2(memory.percent),
                "used_bytes": int(memory.used),
                "total_bytes": int(memory.total),
                "available_bytes": int(memory.available),
            },
            "disk": {
                "path": disk_path,
                "usage_percent": _round2(disk.percent),
                "used_bytes": int(disk.used),
                "total_bytes": int(disk.total),
                "free_bytes": int(disk.free),
                "read_bytes": read_bytes_total,
                "write_bytes": write_bytes_total,
                "read_rate_bps": _round2(read_rate_bps),
                "write_rate_bps": _round2(write_rate_bps),
            },
            "network": {
                "usage_percent": _round2(network_usage_percent),
                "bytes_sent": int(net_io.bytes_sent),
                "bytes_recv": int(net_io.bytes_recv),
                "tx_rate_bps": _round2(tx_rate_bps),
                "rx_rate_bps": _round2(rx_rate_bps),
                "max_link_speed_mbps": _round2(max_link_speed_mbps),
            },
        }
        return status
    except Exception as exc:
        logger.warning("[SystemAdmin] Failed to collect metrics via psutil, using fallback: %s", exc)

    # Fallback (no psutil)
    cpu_usage_percent: Optional[float] = None
    if hasattr(os, "getloadavg"):
        try:
            load_avg_1m = os.getloadavg()[0]
            cpu_count = float(os.cpu_count() or 1)
            if cpu_count > 0:
                cpu_usage_percent = min(100.0, load_avg_1m / cpu_count * 100.0)
        except Exception:
            cpu_usage_percent = None

    disk_path = _safe_disk_path()
    disk_usage = shutil.disk_usage(disk_path)

    status["collector"] = "fallback"
    status["metrics"] = {
        "cpu": {
            "usage_percent": _round2(cpu_usage_percent),
        },
        "memory": {
            "usage_percent": None,
            "used_bytes": None,
            "total_bytes": None,
            "available_bytes": None,
        },
        "disk": {
            "path": disk_path,
            "usage_percent": _round2((disk_usage.used / disk_usage.total) * 100.0 if disk_usage.total else None),
            "used_bytes": int(disk_usage.used),
            "total_bytes": int(disk_usage.total),
            "free_bytes": int(disk_usage.free),
            "read_bytes": None,
            "write_bytes": None,
            "read_rate_bps": None,
            "write_rate_bps": None,
        },
        "network": {
            "usage_percent": None,
            "bytes_sent": None,
            "bytes_recv": None,
            "tx_rate_bps": None,
            "rx_rate_bps": None,
            "max_link_speed_mbps": None,
        },
    }
    return status


@router.get("/config", response_model=SystemConfigResponse)
async def get_admin_system_config(
    _: str = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """Get current system configuration (admin only)."""

    config = get_system_config(db)
    return {
        "values": _serialize_system_config(config),
        "fields": [field.model_dump() for field in SYSTEM_CONFIG_FIELDS],
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@router.patch("/config", response_model=SystemConfigResponse)
async def patch_admin_system_config(
    payload: SystemConfigUpdateRequest,
    _: str = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """Patch mutable system configuration fields (admin only)."""

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No configuration changes provided")

    config = update_system_config(db, **updates)
    if "enable_logging" in updates:
        DatabaseLoggingFilter.set_enable_logging(config.enable_logging)
    return {
        "values": _serialize_system_config(config),
        "fields": [field.model_dump() for field in SYSTEM_CONFIG_FIELDS],
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@router.get("/status", response_model=SystemStatusResponse)
async def get_admin_system_status(_: str = Depends(require_admin_user)):
    """Get runtime host resource metrics (admin only)."""

    return _collect_system_status()


@router.get("/health", response_model=AdminHealthResponse)
async def get_admin_health_details(_: str = Depends(require_admin_user)):
    """Get health check details (admin only, includes internal component errors)."""
    from . import health as health_module

    return await health_module.build_health_payload(include_internal_errors=True)


@router.get("/gemini-pool/stats", response_model=GeminiPoolStatsResponse)
async def get_gemini_pool_stats(_: str = Depends(require_admin_user)):
    """GeminiClientPool 运行时统计（admin only）。

    返回字段：
      - total_clients: 累计创建的 client 数（含已被 close 的）
      - active_clients: 当前池中持有的 client 数
      - max_size: 池上限（GEMINI_POOL_MAX_SIZE 控制，默认 200）
      - cache_hits / cache_misses / hit_rate: 复用率指标
      - rejected_due_to_max_size: 因 OOM 防护拒绝的次数
      - clients: 每个 client 的元数据（已脱敏，仅含 api_key_configured / vertexai /
        project / location / 创建时间 / timeout / retry）

    注意：进程内为单例，多 worker 部署下本端点只反映**当前 worker** 视角。
    告警阈值需要乘以 worker 数（参见 services/gemini/docs/README.md 多 worker 说明）。
    """
    from ...services.gemini.client_pool import get_client_pool

    return get_client_pool().get_stats()


@router.post("/cleanup", response_model=SystemCleanupResponse)
async def cleanup_system(
    _: str = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """Clean system garbage: pycache, temp files, expired DB records, stale Redis keys."""

    from pathlib import Path

    results: Dict[str, int] = {}
    freed_bytes = 0

    # 1. __pycache__ directories
    try:
        pycache_count = 0
        backend_root = Path(__file__).resolve().parents[3]  # backend/
        for d in backend_root.rglob("__pycache__"):
            if d.is_dir():
                try:
                    dir_size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    freed_bytes += dir_size
                    shutil.rmtree(d, ignore_errors=True)
                    pycache_count += 1
                except Exception:
                    logger.debug("[Cleanup] Failed to remove __pycache__ entry: %s", d, exc_info=True)
        results["pycache_dirs"] = pycache_count
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean __pycache__: %s", exc)
        results["pycache_dirs"] = -1

    # 2. Upload temp files (older than 1 hour)
    try:
        temp_dir = Path(__file__).resolve().parents[2] / "temp"
        upload_temp_count = 0
        one_hour_ago = time.time() - 3600
        if temp_dir.is_dir():
            for f in temp_dir.iterdir():
                if f.is_file() and f.name.startswith("upload_"):
                    try:
                        if f.stat().st_mtime < one_hour_ago:
                            file_size = f.stat().st_size
                            f.unlink()
                            upload_temp_count += 1
                            freed_bytes += file_size
                    except Exception:
                        logger.debug("[Cleanup] Failed to remove upload temp file: %s", f, exc_info=True)
        results["temp_upload_files"] = upload_temp_count
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean upload temp files: %s", exc)
        results["temp_upload_files"] = -1

    # 3. Storage downloads cache (clear all)
    try:
        storage_downloads_dir = Path(__file__).resolve().parents[2] / "temp" / "storage_downloads"
        storage_count = 0
        if storage_downloads_dir.is_dir():
            for item in storage_downloads_dir.iterdir():
                try:
                    if item.is_file():
                        freed_bytes += item.stat().st_size
                        item.unlink()
                        storage_count += 1
                    elif item.is_dir():
                        dir_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        freed_bytes += dir_size
                        shutil.rmtree(item, ignore_errors=True)
                        storage_count += 1
                except Exception:
                    logger.debug("[Cleanup] Failed to remove storage download entry: %s", item, exc_info=True)
        results["storage_downloads"] = storage_count
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean storage downloads: %s", exc)
        results["storage_downloads"] = -1

    # 4. Test temp files (clear all)
    try:
        test_dir = Path(__file__).resolve().parents[2] / "temp" / "local_storage_script_test"
        test_count = 0
        if test_dir.is_dir():
            for item in test_dir.iterdir():
                try:
                    if item.is_file():
                        freed_bytes += item.stat().st_size
                        item.unlink()
                        test_count += 1
                    elif item.is_dir():
                        dir_size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                        freed_bytes += dir_size
                        shutil.rmtree(item, ignore_errors=True)
                        test_count += 1
                except Exception:
                    logger.debug("[Cleanup] Failed to remove test temp entry: %s", item, exc_info=True)
        results["test_temp_files"] = test_count
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean test temp files: %s", exc)
        results["test_temp_files"] = -1

    # 5. Expired upload tasks (completed > 7 days ago)
    try:
        from ...models.db_models import UploadTask
        import time as _time

        seven_days_ago_ms = int((_time.time() - 7 * 86400) * 1000)
        expired_tasks = (
            db.query(UploadTask)
            .filter(
                UploadTask.status == "completed",
                UploadTask.completed_at.isnot(None),
                UploadTask.completed_at < seven_days_ago_ms,
            )
            .all()
        )
        expired_task_count = len(expired_tasks)
        for task in expired_tasks:
            db.delete(task)
        if expired_task_count > 0:
            db.commit()
        results["expired_upload_tasks"] = expired_task_count
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean expired upload tasks: %s", exc)
        db.rollback()
        results["expired_upload_tasks"] = -1

    # 6. Expired refresh tokens
    try:
        from ...models.db_models import RefreshToken

        now_utc = datetime.now(timezone.utc)
        expired_tokens = (
            db.query(RefreshToken)
            .filter(RefreshToken.expires_at < now_utc)
            .all()
        )
        expired_token_count = len(expired_tokens)
        for token in expired_tokens:
            db.delete(token)
        if expired_token_count > 0:
            db.commit()
        results["expired_refresh_tokens"] = expired_token_count
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean expired refresh tokens: %s", exc)
        db.rollback()
        results["expired_refresh_tokens"] = -1

    # 7. Redis stale keys (cleanup expired keys via SCAN)
    try:
        from ...services.common.redis_queue_service import redis_queue

        if redis_queue._redis:
            stale_count = 0
            cursor = 0
            while True:
                cursor, keys = await redis_queue._redis.scan(cursor=cursor, count=100)
                for key in keys:
                    ttl = await redis_queue._redis.ttl(key)
                    if ttl is not None and ttl == -2:
                        # Key already expired / doesn't exist
                        stale_count += 1
                if cursor == 0:
                    break
            # Force memory reclaim
            try:
                await redis_queue._redis.execute_command("MEMORY", "PURGE")
            except Exception:
                logger.debug("[Cleanup] Redis MEMORY PURGE failed", exc_info=True)
            results["redis_stale_keys"] = stale_count
        else:
            results["redis_stale_keys"] = 0
    except Exception as exc:
        logger.warning("[Cleanup] Failed to clean Redis stale keys: %s", exc)
        results["redis_stale_keys"] = -1

    logger.info("[Cleanup] System cleanup completed: %s, freed %d bytes", results, freed_bytes)

    return {"cleaned": results, "freed_bytes": freed_bytes}
