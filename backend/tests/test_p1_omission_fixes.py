"""P1 remediation: LFI omissions + cross-user access control.

- CANON-027: OpenAI video generator must not read an arbitrary local path via the
  generic Path(url) fallback (only allow-rooted local-files URLs are permitted).
- CANON-028: Tongyi/Qwen chat must not read an arbitrary local file; local refs
  must resolve within the allowed local-storage root.
- W02R-008: /browser/sessions exposes all users' session metadata to any
  authenticated user; it must require administrator privileges.
"""

import pytest
from fastapi import HTTPException

from app.utils.url_security import UnsafeURLError


@pytest.mark.asyncio
async def test_openai_video_rejects_arbitrary_local_path(tmp_path):
    from app.services.openai.video_generator import VideoGenerator

    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET", encoding="utf-8")
    gen = VideoGenerator(api_key="k")
    with pytest.raises((UnsafeURLError, ValueError)):
        await gen._load_media_bytes({"url": str(secret)}, "video/mp4")


def test_tongyi_chat_rejects_arbitrary_local_path(tmp_path):
    from app.services.tongyi.chat import QwenNativeProvider

    secret = tmp_path / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n")
    provider = QwenNativeProvider(api_key="k")
    # arbitrary absolute path is not within the allowed local-storage root -> denied
    assert provider._local_path_to_data_url(str(secret)) is None
    # and the normalizer must not turn it into a base64 data URL of the file
    normalized = provider._normalize_multimodal_image_ref(str(secret))
    assert normalized is None or not normalized.startswith("data:")


def test_tongyi_chat_rejects_file_scheme(tmp_path):
    from app.services.tongyi.chat import QwenNativeProvider

    secret = tmp_path / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n")
    provider = QwenNativeProvider(api_key="k")
    assert provider._local_path_to_data_url(f"file://{secret}") is None


def test_require_admin_rejects_non_admin(monkeypatch):
    from app.core import dependencies as deps

    monkeypatch.setattr(deps, "require_current_user", lambda req: "u1")
    monkeypatch.setattr(deps, "_user_is_admin", lambda uid: False)
    with pytest.raises(HTTPException) as exc_info:
        deps.require_admin(object())
    assert exc_info.value.status_code == 403


def test_require_admin_allows_admin(monkeypatch):
    from app.core import dependencies as deps

    monkeypatch.setattr(deps, "require_current_user", lambda req: "admin1")
    monkeypatch.setattr(deps, "_user_is_admin", lambda uid: True)
    assert deps.require_admin(object()) == "admin1"
