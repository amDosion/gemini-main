from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.common.auth_service import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
)


def test_login_request_rejects_unknown_fields_and_oversized_password() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(
            email="user@example.com",
            password="valid-password",
            unexpected=True,
        )

    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="x" * 1025)


def test_register_request_rejects_control_chars_and_oversized_name() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password="valid-password\n",
            confirm_password="valid-password\n",
        )

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="user@example.com",
            password="valid-password",
            confirm_password="valid-password",
            name="x" * 129,
        )


def test_change_password_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ChangePasswordRequest(
            current_password="old-password",
            new_password="new-password",
            confirm_password="new-password",
            role="admin",
        )

