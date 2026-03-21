"""Credential resolver for provider-backed LLM runtime."""

from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.credential_manager import get_provider_credentials
from ...core.encryption import decrypt_data, is_encrypted
from ...models.db_models import ConfigProfile, UserSettings


class ProviderCredentialsResolver:
    """Resolve provider API credentials for a user."""

    async def resolve(
        self,
        provider_id: str,
        db: Session,
        user_id: str,
        profile_id: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        normalized_profile_id = str(profile_id or "").strip()
        if normalized_profile_id:
            return self._resolve_sync_for_explicit_profile(
                provider_id=provider_id,
                profile_id=normalized_profile_id,
                db=db,
                user_id=user_id,
            )

        try:
            return await get_provider_credentials(
                provider=provider_id,
                db=db,
                user_id=user_id,
            )
        except HTTPException:
            # Keep previous fallback semantics used by AgentLLMService:
            # when exact provider key is not found, allow base provider prefix lookup.
            return self._resolve_sync_with_base_provider_fallback(
                provider_id=provider_id,
                db=db,
                user_id=user_id,
            )

    def _provider_matches(self, expected_provider: str, profile_provider: str) -> bool:
        expected = str(expected_provider or "").strip().lower()
        actual = str(profile_provider or "").strip().lower()
        if not expected:
            return bool(actual)
        if not actual:
            return False
        if expected == actual:
            return True
        if expected.startswith(actual) or actual.startswith(expected):
            return True
        return False

    def _decrypt_api_key(self, api_key: str) -> str:
        raw = str(api_key or "")
        if not raw:
            return raw
        if is_encrypted(raw):
            return decrypt_data(raw, silent=True)
        return raw

    def _resolve_sync_for_explicit_profile(
        self,
        provider_id: str,
        profile_id: str,
        db: Session,
        user_id: str,
    ) -> Tuple[str, Optional[str]]:
        profile = db.query(ConfigProfile).filter(
            ConfigProfile.id == profile_id,
            ConfigProfile.user_id == user_id,
        ).first()

        if not profile:
            raise HTTPException(
                status_code=401,
                detail=f"Profile not found: {profile_id}. Please select a valid profile.",
            )

        profile_provider = str(profile.provider_id or "").strip()
        if not self._provider_matches(provider_id, profile_provider):
            raise HTTPException(
                status_code=401,
                detail=(
                    f"Profile {profile_id} provider mismatch. "
                    f"Expected {provider_id}, got {profile_provider}."
                ),
            )

        api_key = self._decrypt_api_key(str(profile.api_key or ""))
        if not str(api_key or "").strip():
            raise HTTPException(
                status_code=401,
                detail=f"API Key not found for profile: {profile_id}. Please configure it in Settings → Profiles.",
            )

        return api_key, profile.base_url

    def _resolve_sync_with_base_provider_fallback(
        self,
        provider_id: str,
        db: Session,
        user_id: str,
    ) -> Tuple[str, Optional[str]]:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        active_profile_id = settings.active_profile_id if settings else None

        profiles = db.query(ConfigProfile).filter(
            ConfigProfile.provider_id == provider_id,
            ConfigProfile.user_id == user_id,
        ).all()

        if not profiles:
            base_provider = provider_id.split("-")[0] if "-" in provider_id else provider_id
            profiles = db.query(ConfigProfile).filter(
                ConfigProfile.provider_id.like(f"{base_provider}%"),
                ConfigProfile.user_id == user_id,
            ).all()

        if not profiles:
            raise HTTPException(
                status_code=401,
                detail=f"API Key not found for provider: {provider_id}. Please configure it in Settings → Profiles.",
            )

        api_key = None
        base_url = None
        for profile in profiles:
            if active_profile_id and profile.id == active_profile_id and profile.api_key:
                api_key = profile.api_key
                base_url = profile.base_url
                break

        if not api_key:
            for profile in profiles:
                if profile.api_key:
                    api_key = profile.api_key
                    base_url = profile.base_url
                    break

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail=f"API Key not found for provider: {provider_id}. Please configure it in Settings → Profiles.",
            )

        api_key = self._decrypt_api_key(api_key)

        return api_key, base_url
