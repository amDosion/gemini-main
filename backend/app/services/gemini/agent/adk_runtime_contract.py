"""
ADK runtime contract helpers.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException
from ....core.config import (
    ADK_RUNTIME_STRATEGY_VALUES as _CONFIG_ADK_RUNTIME_STRATEGY_VALUES,
    build_adk_runtime_contract_payload as _build_contract_payload_from_config,
    is_adk_runtime_fallback_allowed as _is_fallback_allowed_from_config,
    normalize_adk_runtime_strategy as _normalize_strategy_from_config,
)


class ADKRuntimeStrategy(str, Enum):
    OFFICIAL_ONLY = "official_only"
    OFFICIAL_OR_LEGACY = "official_or_legacy"
    ALLOW_LEGACY = "allow_legacy"


ADK_RUNTIME_STRATEGY_VALUES = tuple(_CONFIG_ADK_RUNTIME_STRATEGY_VALUES)


class ADKRuntimeErrorCode(str, Enum):
    ADK_RUNTIME_UNAVAILABLE = "ADK_RUNTIME_UNAVAILABLE"
    ADK_FALLBACK_FORBIDDEN = "ADK_FALLBACK_FORBIDDEN"
    ADK_STRATEGY_VIOLATION = "ADK_STRATEGY_VIOLATION"
    ADK_INVALID_REQUEST = "ADK_INVALID_REQUEST"


def normalize_adk_runtime_strategy(
    raw_value: Any,
    *,
    default: str = ADKRuntimeStrategy.OFFICIAL_OR_LEGACY.value,
    reject_invalid: bool = True,
) -> str:
    return _normalize_strategy_from_config(
        str(raw_value or ""),
        default=default,
        reject_invalid=reject_invalid,
    )


def is_adk_runtime_fallback_allowed(*, runtime_strategy: str, strict_mode: bool) -> bool:
    return _is_fallback_allowed_from_config(
        runtime_strategy=str(runtime_strategy or ""),
        strict_mode=bool(strict_mode),
    )


def build_adk_runtime_contract_payload(
    *,
    runtime_strategy_raw: Any,
    strict_mode: bool,
) -> Dict[str, Any]:
    return _build_contract_payload_from_config(
        runtime_strategy_raw=str(runtime_strategy_raw or ""),
        strict_mode=bool(strict_mode),
    )


def build_adk_runtime_error(
    *,
    error_code: ADKRuntimeErrorCode | str,
    message: str,
    runtime_strategy: str,
    strict_mode: bool,
    fallback_allowed: Optional[bool] = None,
    mode: Optional[str] = None,
    cause: Optional[str] = None,
) -> Dict[str, Any]:
    code_value = error_code.value if isinstance(error_code, ADKRuntimeErrorCode) else str(error_code or "").strip()
    runtime_strategy_raw = str(runtime_strategy or "").strip().lower()
    try:
        normalized_runtime_strategy = normalize_adk_runtime_strategy(
            runtime_strategy_raw,
            default=ADKRuntimeStrategy.OFFICIAL_OR_LEGACY.value,
            reject_invalid=True,
        )
    except ValueError:
        normalized_runtime_strategy = runtime_strategy_raw or ADKRuntimeStrategy.OFFICIAL_OR_LEGACY.value
    detail: Dict[str, Any] = {
        "error_code": code_value,
        "message": str(message or "").strip() or "ADK runtime contract error",
        "runtime_strategy": normalized_runtime_strategy,
        "strict_mode": bool(strict_mode),
    }
    if fallback_allowed is not None:
        detail["fallback_allowed"] = bool(fallback_allowed)
    if mode:
        detail["mode"] = str(mode).strip()
    if cause:
        detail["cause"] = str(cause).strip()
    return detail


def build_adk_runtime_http_exception(
    *,
    status_code: int,
    error_code: ADKRuntimeErrorCode | str,
    message: str,
    runtime_strategy: str,
    strict_mode: bool,
    fallback_allowed: Optional[bool] = None,
    mode: Optional[str] = None,
    cause: Optional[str] = None,
) -> HTTPException:
    return HTTPException(
        status_code=int(status_code),
        detail=build_adk_runtime_error(
            error_code=error_code,
            message=message,
            runtime_strategy=runtime_strategy,
            strict_mode=strict_mode,
            fallback_allowed=fallback_allowed,
            mode=mode,
            cause=cause,
        ),
    )
