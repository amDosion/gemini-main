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
from ...models.db_models import User
from ...services.common.system_config_service import get_system_config, update_system_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/admin", tags=["system-admin"])

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

    key: str
    label: str
    type: Literal["boolean", "number", "string"]
    description: Optional[str] = None
    editable: bool = True
    min: Optional[int] = None
    max: Optional[int] = None
    step: Optional[int] = None
    unit: Optional[str] = None


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


@router.get("/config")
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


@router.patch("/config")
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
    return {
        "values": _serialize_system_config(config),
        "fields": [field.model_dump() for field in SYSTEM_CONFIG_FIELDS],
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@router.get("/status")
async def get_admin_system_status(_: str = Depends(require_admin_user)):
    """Get runtime host resource metrics (admin only)."""

    return _collect_system_status()


@router.get("/health")
async def get_admin_health_details(_: str = Depends(require_admin_user)):
    """Get health check details (admin only, includes internal component errors)."""
    from . import health as health_module

    return await health_module.build_health_payload(include_internal_errors=True)
