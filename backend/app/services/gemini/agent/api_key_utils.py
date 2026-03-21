"""
API Key Utilities - API 密钥获取工具

Extracts the duplicated API key retrieval logic from router and orchestrator
into a single reusable function.
"""

import logging
from typing import Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def get_google_service(
    db: Session,
    user_id: str,
) -> Optional[Any]:
    """
    Get a GoogleService instance for the given user.

    Looks up the user's Google API key from their config profiles,
    preferring the active profile.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        GoogleService instance, or None if no API key found
    """
    try:
        from ...models.db_models import UserSettings, ConfigProfile
        from ..common.provider_factory import ProviderFactory

        settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()
        active_profile_id = settings.active_profile_id if settings else None

        matching_profiles = db.query(ConfigProfile).filter(
            ConfigProfile.provider_id == 'google',
            ConfigProfile.user_id == user_id
        ).all()

        if not matching_profiles:
            return None

        api_key = None

        # Prefer active profile
        if active_profile_id:
            for profile in matching_profiles:
                if profile.id == active_profile_id and profile.api_key:
                    api_key = profile.api_key
                    break

        # Fallback to first profile with a key
        if not api_key:
            for profile in matching_profiles:
                if profile.api_key:
                    api_key = profile.api_key
                    break

        if not api_key:
            return None

        return ProviderFactory.create(
            provider='google',
            api_key=api_key,
            user_id=user_id,
            db=db
        )

    except Exception as e:
        logger.warning(f"[api_key_utils] Failed to create GoogleService: {e}")
        return None
