"""
Coordinator for selecting Gemini API or Vertex AI video understanding.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..geminiapi.video_understanding_service import GeminiAPIVideoUnderstandingService
from ..vertexai.video_understanding_service import VertexAIVideoUnderstandingService
from ._config_cache import get_or_load as _cached_load

logger = logging.getLogger(__name__)


class VideoUnderstandingCoordinator:
    def __init__(
        self,
        *,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        api_key: Optional[str] = None,
        http_options: Any = None,
    ) -> None:
        self._user_id = user_id
        self._db = db
        self._provided_api_key = api_key
        self._http_options = http_options
        self._config = self._load_config()
        self._service_cache: Dict[str, Any] = {}

    def _load_config(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {}

        if self._user_id and self._db:
            try:
                from ....models.db_models import ConfigProfile, VertexAIConfig
                from ....core.encryption import decrypt_data, is_encrypted

                def _load_vertex() -> Optional[Dict[str, Any]]:
                    row = self._db.query(VertexAIConfig).filter(
                        VertexAIConfig.user_id == self._user_id
                    ).first()
                    if not row:
                        return None
                    return {
                        "api_mode": row.api_mode,
                        "vertex_ai_project_id": row.vertex_ai_project_id,
                        "vertex_ai_location": row.vertex_ai_location,
                        "vertex_ai_credentials_json": row.vertex_ai_credentials_json,
                    }

                vertex_snapshot = _cached_load(self._user_id, "vertex_ai_config", _load_vertex)
                if vertex_snapshot:
                    config["api_mode"] = vertex_snapshot.get("api_mode") or "gemini_api"
                    config["vertex_ai_project_id"] = vertex_snapshot.get("vertex_ai_project_id")
                    config["vertex_ai_location"] = vertex_snapshot.get("vertex_ai_location") or "us-central1"
                    raw_credentials = vertex_snapshot.get("vertex_ai_credentials_json")
                    if raw_credentials:
                        config["vertex_ai_credentials_json"] = (
                            decrypt_data(raw_credentials) if is_encrypted(raw_credentials) else raw_credentials
                        )

                if self._provided_api_key:
                    config["gemini_api_key"] = self._provided_api_key
                else:
                    def _load_google_profile() -> Optional[Dict[str, Any]]:
                        row = self._db.query(ConfigProfile).filter(
                            ConfigProfile.user_id == self._user_id,
                            ConfigProfile.provider_id == "google",
                        ).order_by(ConfigProfile.updated_at.desc()).first()
                        if not row:
                            return None
                        return {"api_key": row.api_key}

                    google_snapshot = _cached_load(
                        self._user_id, "config_profile", _load_google_profile, "google"
                    )
                    if google_snapshot and google_snapshot.get("api_key"):
                        key = google_snapshot["api_key"]
                        if is_encrypted(key):
                            key = decrypt_data(key, silent=True)
                        config["gemini_api_key"] = key

                if config:
                    return config
            except Exception as exc:
                logger.warning("[VideoUnderstandingCoordinator] Failed to load DB config, falling back to env: %s", exc)

        config["api_mode"] = "vertex_ai" if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true" else "gemini_api"
        config["gemini_api_key"] = self._provided_api_key or os.getenv("GOOGLE_API_KEY")
        config["vertex_ai_project_id"] = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
        config["vertex_ai_location"] = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GCP_LOCATION", "us-central1")
        config["vertex_ai_credentials_json"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        return config

    def _create_vertex_service(self) -> VertexAIVideoUnderstandingService:
        project_id = self._config.get("vertex_ai_project_id")
        location = self._config.get("vertex_ai_location") or "us-central1"
        credentials_json = self._config.get("vertex_ai_credentials_json")
        if not project_id or not credentials_json:
            raise ValueError("Vertex AI video understanding requires project_id and credentials_json.")
        return VertexAIVideoUnderstandingService(
            project_id=project_id,
            location=location,
            credentials_json=credentials_json,
            http_options=self._http_options,
        )

    def _create_gemini_api_service(self) -> GeminiAPIVideoUnderstandingService:
        api_key = self._config.get("gemini_api_key") or self._provided_api_key
        if not api_key:
            raise ValueError("Gemini API video understanding requires a Google API key.")
        return GeminiAPIVideoUnderstandingService(
            api_key=api_key,
            http_options=self._http_options,
        )

    def get_service(self, api_mode_override: Optional[str] = None) -> Any:
        api_mode = str(api_mode_override or self._config.get("api_mode") or "gemini_api").strip().lower()
        if api_mode in self._service_cache:
            return self._service_cache[api_mode]

        try:
            if api_mode == "vertex_ai":
                service = self._create_vertex_service()
            else:
                service = self._create_gemini_api_service()
            self._service_cache[api_mode] = service
            return service
        except Exception as exc:
            if api_mode == "vertex_ai":
                logger.warning("[VideoUnderstandingCoordinator] Vertex AI init failed, falling back to Gemini API: %s", exc)
                service = self._create_gemini_api_service()
                self._service_cache["gemini_api"] = service
                return service
            raise

    async def understand_video(self, prompt: str, model: str, **kwargs) -> Dict[str, Any]:
        service = self.get_service()
        result = await service.understand_video(prompt=prompt, model=model, **kwargs)
        if isinstance(result, dict):
            result.setdefault("coordinator_api_mode", self.get_current_api_mode())
        return result

    def get_current_api_mode(self) -> str:
        service = self.get_service()
        if isinstance(service, VertexAIVideoUnderstandingService):
            return "vertex_ai"
        return "gemini_api"
