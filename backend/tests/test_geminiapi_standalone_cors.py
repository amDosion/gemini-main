from app.services.gemini.geminiapi.main import (
    DEFAULT_CORS_ALLOW_ORIGINS,
    _resolve_cors_allow_origins,
)


def _default_origins() -> list[str]:
    return [origin.strip() for origin in DEFAULT_CORS_ALLOW_ORIGINS.split(",") if origin.strip()]


def test_geminiapi_standalone_cors_defaults_to_local_origins(monkeypatch):
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)

    assert _resolve_cors_allow_origins() == _default_origins()


def test_geminiapi_standalone_cors_uses_explicit_origins():
    assert _resolve_cors_allow_origins("https://app.example, http://localhost:21573") == [
        "https://app.example",
        "http://localhost:21573",
    ]


def test_geminiapi_standalone_cors_rejects_wildcard_origin():
    assert _resolve_cors_allow_origins("*") == _default_origins()
    assert _resolve_cors_allow_origins("*, https://app.example") == ["https://app.example"]
