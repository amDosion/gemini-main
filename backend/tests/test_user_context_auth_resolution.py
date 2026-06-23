from __future__ import annotations

from types import SimpleNamespace

from app.core import user_context
from app.core.jwt_utils import JWTError, TokenPayload


def make_request(
    *,
    authorization: str | None = None,
    cookies: dict[str, str] | None = None,
    path: str = "/api/protected",
):
    headers = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    return SimpleNamespace(
        headers=headers,
        cookies=cookies or {},
        url=SimpleNamespace(path=path),
    )


def _access_payload(user_id: str) -> TokenPayload:
    return TokenPayload(sub=user_id, exp=4_102_444_800, type="access")


def test_get_current_user_id_falls_back_to_cookie_when_bearer_is_not_app_token(monkeypatch):
    decoded_tokens: list[str] = []

    def fake_decode_token(token: str) -> TokenPayload:
        decoded_tokens.append(token)
        if token == "cookie-token":
            return _access_payload("cookie-user")
        raise JWTError("not a local app JWT")

    monkeypatch.setattr(user_context, "decode_token", fake_decode_token)
    monkeypatch.setattr(
        user_context,
        "_is_access_token_active_in_db",
        lambda user_id, token: user_id == "cookie-user" and token == "cookie-token",
    )

    request = make_request(
        authorization="Bearer provider-api-key",
        cookies={"access_token": "cookie-token"},
    )

    assert user_context.get_current_user_id(request) == "cookie-user"
    assert decoded_tokens == ["provider-api-key", "cookie-token"]


def test_get_current_user_id_keeps_valid_bearer_header_precedence(monkeypatch):
    decoded_tokens: list[str] = []

    def fake_decode_token(token: str) -> TokenPayload:
        decoded_tokens.append(token)
        if token == "header-token":
            return _access_payload("header-user")
        if token == "cookie-token":
            return _access_payload("cookie-user")
        raise JWTError("unexpected token")

    monkeypatch.setattr(user_context, "decode_token", fake_decode_token)
    monkeypatch.setattr(user_context, "_is_access_token_active_in_db", lambda _user_id, _token: True)

    request = make_request(
        authorization="Bearer header-token",
        cookies={"access_token": "cookie-token"},
    )

    assert user_context.get_current_user_id(request) == "header-user"
    assert decoded_tokens == ["header-token"]
