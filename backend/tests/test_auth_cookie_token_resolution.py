from types import SimpleNamespace

from app.routers.auth.auth import (
    _build_public_token_response,
    _get_request_token,
    _get_valid_request_token,
    _safe_auth_log_text,
)


def make_request(*, authorization: str | None = None, cookies: dict[str, str] | None = None):
    headers = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    return SimpleNamespace(headers=headers, cookies=cookies or {})


def test_request_token_prefers_bearer_header_over_cookie():
    request = make_request(
        authorization="Bearer header-token",
        cookies={"access_token": "cookie-token"},
    )

    assert _get_request_token(request, cookie_name="access_token") == "header-token"


def test_request_token_falls_back_to_named_cookie():
    request = make_request(cookies={"refresh_token": "cookie-refresh"})

    assert _get_request_token(request, cookie_name="refresh_token") == "cookie-refresh"


def test_request_token_ignores_malformed_authorization_header():
    request = make_request(
        authorization="Basic not-a-bearer-token",
        cookies={"access_token": "cookie-token"},
    )

    assert _get_request_token(request, cookie_name="access_token") == "cookie-token"


def test_valid_request_token_falls_back_to_cookie_when_bearer_fails_validation():
    request = make_request(
        authorization="Bearer provider-api-key",
        cookies={"access_token": "cookie-token"},
    )

    assert (
        _get_valid_request_token(
            request,
            cookie_name="access_token",
            is_valid_token=lambda token: token == "cookie-token",
        )
        == "cookie-token"
    )


def test_valid_request_token_keeps_valid_bearer_header_precedence():
    request = make_request(
        authorization="Bearer header-token",
        cookies={"access_token": "cookie-token"},
    )

    assert (
        _get_valid_request_token(
            request,
            cookie_name="access_token",
            is_valid_token=lambda token: token == "header-token",
        )
        == "header-token"
    )


def test_public_token_response_does_not_expose_tokens_to_browser_js():
    tokens = SimpleNamespace(
        access_token="access-token",
        refresh_token="refresh-token",
        token_type="bearer",
        expires_in=900,
    )

    response = _build_public_token_response(tokens)

    assert "access_token" not in response
    assert "refresh_token" not in response
    assert response == {"token_type": "bearer", "expires_in": 900}


def test_safe_auth_log_text_redacts_exception_content():
    secret = "refresh-token-secret"

    output = _safe_auth_log_text(RuntimeError(f"database failure {secret}"))

    assert secret not in output
    assert "database failure" not in output
    assert "RuntimeError" in output
    assert output.startswith("<redacted error;")
