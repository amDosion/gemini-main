"""Residual LFI in geminiapi reference-image loaders: a raw absolute / file://
path from a (user/model-influenced) reference must NOT be read off disk.

Legit local references arrive as allow-rooted /api/storage/local-files/ URLs
(resolved via resolve_local_public_file_path); an arbitrary filesystem path must
be denied (CANON-027/028 policy), not read and base64-embedded into the request.
"""

import pytest


def test_recontext_reference_rejects_arbitrary_absolute_path(tmp_path):
    from app.services.gemini.geminiapi.recontext_image_service import (
        GeminiRecontextImageService as RecontextImageService,
    )

    secret = tmp_path / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n\x1a\nSECRET")

    svc = RecontextImageService.__new__(RecontextImageService)
    with pytest.raises(ValueError):
        svc._part_from_reference_item(str(secret))


def test_recontext_reference_rejects_file_scheme(tmp_path):
    from app.services.gemini.geminiapi.recontext_image_service import (
        GeminiRecontextImageService as RecontextImageService,
    )

    secret = tmp_path / "secret2.png"
    secret.write_bytes(b"\x89PNG\r\n\x1a\nSECRET2")

    svc = RecontextImageService.__new__(RecontextImageService)
    with pytest.raises(ValueError):
        svc._part_from_reference_item(f"file://{secret}")


def _secret_marker_b64() -> str:
    import base64

    return base64.b64encode(b"SECRETMARKER-DO-NOT-LEAK").decode("ascii")


def test_conversational_string_ref_does_not_read_arbitrary_path(tmp_path):
    from app.services.gemini.geminiapi.conversational_image_edit_service import (
        ConversationalImageEditService,
    )

    secret = tmp_path / "secret.png"
    secret.write_bytes(b"SECRETMARKER-DO-NOT-LEAK")

    svc = ConversationalImageEditService.__new__(ConversationalImageEditService)
    result = svc._convert_reference_images({"raw": str(secret)})

    # The arbitrary local file must NOT be read and base64-embedded into any part.
    blob = repr(result)
    assert _secret_marker_b64() not in blob
    assert "SECRETMARKER" not in blob


def test_conversational_dict_ref_does_not_read_arbitrary_path(tmp_path):
    from app.services.gemini.geminiapi.conversational_image_edit_service import (
        ConversationalImageEditService,
    )

    secret = tmp_path / "secret2.png"
    secret.write_bytes(b"SECRETMARKER-DO-NOT-LEAK")

    svc = ConversationalImageEditService.__new__(ConversationalImageEditService)
    result = svc._convert_reference_images({"raw": {"url": str(secret)}})

    blob = repr(result)
    assert _secret_marker_b64() not in blob
    assert "SECRETMARKER" not in blob
