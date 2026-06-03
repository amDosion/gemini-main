"""Shared Vertex AI config loader for vertexai image services.

`ExpandService` and `SegmentationService` (and any future Vertex-only service)
need the same per-user Vertex AI configuration: GCP ``project_id``, ``location``,
and a decrypted ``service_account.Credentials`` object. Previously each service
carried a near-verbatim ``_load_config`` copy that:

- duplicated the DB query + decrypt + credential-construction logic, and
- bypassed the process-wide TTL cache used by the coordinator layer
  (`coordinators/_config_cache.py`), forcing a fresh ``VertexAIConfig`` SELECT
  on every service instance even within a single fanned-out user request.

This module centralizes that logic and routes the DB read through the SAME
shared cache (kind ``"vertex_ai_config"``) the coordinators use, so the row is
read once per user per TTL window across both services and coordinators.

The cache stores only a plain dict snapshot of column values (never ORM rows or
credential objects), matching the cache contract. Decryption and credential
construction happen per-call from that snapshot.

Return shape (unchanged from the old per-service ``_load_config``):
    {
        "project_id": str,
        "location": str,                       # defaults to "us-central1"
        "credentials": service_account.Credentials,  # only when available
    }
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..coordinators._config_cache import get_or_load as _cached_load

logger = logging.getLogger(__name__)

DEFAULT_LOCATION = "us-central1"
CREDENTIALS_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_CACHE_KIND = "vertex_ai_config"


def _load_vertex_row_snapshot(db: Any, user_id: str) -> dict[str, Any] | None:
    """Return a plain-dict snapshot of the user's VertexAIConfig row, or None.

    The snapshot holds only column values so it is safe to store in the shared
    cross-session TTL cache (no detached-ORM-instance hazard).
    """
    from ....models.db_models import VertexAIConfig

    row = (
        db.query(VertexAIConfig)
        .filter(VertexAIConfig.user_id == user_id)
        .first()
    )
    if not row:
        return None
    return {
        "api_mode": row.api_mode,
        "vertex_ai_project_id": row.vertex_ai_project_id,
        "vertex_ai_location": row.vertex_ai_location,
        "vertex_ai_credentials_json": row.vertex_ai_credentials_json,
    }


def _build_credentials(encrypted_blob: str, *, log_prefix: str):
    """Decrypt the stored credentials blob and build a Credentials object.

    Returns the credentials object, or None when decryption/parsing fails.
    Failures are logged (not raised) to preserve the prior fail-soft behavior:
    a missing/undecryptable credential degrades to "no credentials", which the
    client builder turns into an explicit, user-facing error downstream.
    """
    from ....core.encryption import decrypt_data

    try:
        credentials_json = decrypt_data(encrypted_blob)
        from google.oauth2 import service_account

        credentials_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=CREDENTIALS_SCOPES,
        )
        logger.info("%s Successfully loaded Vertex AI credentials from database", log_prefix)
        return credentials
    except Exception as exc:
        logger.error("%s Failed to decrypt/parse credentials: %s", log_prefix, exc)
        return None


def load_vertex_ai_config(
    user_id: str | None,
    db: Any,
    *,
    log_prefix: str = "[VertexConfig]",
) -> dict[str, Any]:
    """Load Vertex AI config for a user, with shared-cache-backed DB reads.

    Precedence (unchanged from the original per-service loaders):
    1. The user's ``VertexAIConfig`` row when ``api_mode == 'vertex_ai'``
       (DB read coalesced through the shared TTL cache).
    2. Environment variables (``settings.gcp_project_id`` / ``gcp_location``).

    Raises:
        ValueError: when no usable ``project_id`` can be resolved.
    """
    config: dict[str, Any] = {}

    # 1) Database (per-user), routed through the shared TTL cache.
    if user_id and db is not None:
        try:
            user_config = _cached_load(
                user_id,
                _CACHE_KIND,
                lambda: _load_vertex_row_snapshot(db, user_id),
            )

            if user_config and user_config.get("api_mode") == "vertex_ai":
                logger.info(
                    "%s Using Vertex AI config from database for user=%s",
                    log_prefix,
                    user_id,
                )
                config["project_id"] = user_config.get("vertex_ai_project_id")
                config["location"] = (
                    user_config.get("vertex_ai_location") or DEFAULT_LOCATION
                )

                encrypted_blob = user_config.get("vertex_ai_credentials_json")
                if encrypted_blob:
                    credentials = _build_credentials(
                        encrypted_blob, log_prefix=log_prefix
                    )
                    if credentials is not None:
                        config["credentials"] = credentials

                return config

            logger.info(
                "%s No Vertex AI config in database for user=%s, falling back to environment",
                log_prefix,
                user_id,
            )
        except Exception as exc:
            logger.warning("%s Failed to load config from database: %s", log_prefix, exc)

    # 2) Environment fallback.
    try:
        from ....core.config import settings

        config["project_id"] = settings.gcp_project_id
        config["location"] = settings.gcp_location or DEFAULT_LOCATION
        logger.info("%s Using config from environment variables", log_prefix)
    except Exception as exc:
        logger.error("%s Failed to load config from environment: %s", log_prefix, exc)
        raise ValueError("GCP configuration not available") from exc

    if not config.get("project_id"):
        raise ValueError(
            "GCP_PROJECT_ID not configured (neither in database nor environment)"
        )

    return config
