import pytest
from pydantic import ValidationError

from app.models.user import User
from app.modules.auth.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    VerifyEmailRequest, VerifyEmailResponse,
)


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_register_accepts_supported_roles(role):
    request = RegisterRequest(email="demo@example.com", password="demo-password", role=role)
    assert request.model_dump() == {
        "email": "demo@example.com", "password": "demo-password", "role": role,
    }


@pytest.mark.parametrize("role", ["admin", "Candidate", "", None, 1])
def test_register_rejects_unsupported_roles(role):
    with pytest.raises(ValidationError):
        RegisterRequest(email="demo@example.com", password="demo-password", role=role)


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_user_response_from_existing_orm_model(role):
    user = User(
        id=42, email="demo@example.com", password_hash="not-for-the-response",
        role=role, is_verified=False,
    )
    assert UserResponse.model_validate(user).model_dump() == {
        "id": 42, "email": "demo@example.com", "role": role, "is_verified": False,
    }


def test_user_response_rejects_unsupported_role():
    with pytest.raises(ValidationError):
        UserResponse(id=42, email="demo@example.com", role="admin", is_verified=False)


def test_login_request_and_token_response_contract():
    request = LoginRequest.model_validate({
        "email": "demo@example.com", "password": "demo-password",
    })
    assert request.password == "demo-password"
    assert TokenResponse(access_token="example-token").model_dump() == {
        "access_token": "example-token", "token_type": "bearer",
    }
    with pytest.raises(ValidationError):
        TokenResponse(access_token="example-token", token_type="basic")


def test_verify_email_contract():
    assert VerifyEmailRequest(token="example-token").model_dump() == {"token": "example-token"}
    assert VerifyEmailResponse().model_dump() == {"status": "ok"}
    with pytest.raises(ValidationError):
        VerifyEmailResponse(status="error")


@pytest.mark.parametrize(
    "schema, data",
    [
        (RegisterRequest, {"email": "demo@example.com", "password": "demo-password"}),
        (LoginRequest, {"email": "demo@example.com"}),
        (TokenResponse, {}),
        (VerifyEmailRequest, {}),
        (UserResponse, {"id": 42, "email": "demo@example.com", "role": "candidate"}),
    ],
)
def test_required_fields(schema, data):
    with pytest.raises(ValidationError):
        schema.model_validate(data)


def test_password_is_not_in_request_repr():
    password = "not-for-logs"
    assert password not in repr(LoginRequest(email="demo@example.com", password=password))
    assert password not in repr(
        RegisterRequest(email="demo@example.com", password=password, role="candidate")
    )


@pytest.mark.parametrize("schema", [RegisterRequest, LoginRequest])
def test_shared_email_normalization(schema):
    data = {"email": "  Demo@EXAMPLE.COM  ", "password": "demo-password"}
    if schema is RegisterRequest:
        data["role"] = "candidate"
    assert schema.model_validate(data).email == "demo@example.com"


@pytest.mark.parametrize("schema", [RegisterRequest, LoginRequest])
@pytest.mark.parametrize("email", ["not-an-email", "user@", "user @example.com"])
def test_shared_email_validation(schema, email):
    data = {"email": email, "password": "demo-password"}
    if schema is RegisterRequest:
        data["role"] = "candidate"
    with pytest.raises(ValidationError):
        schema.model_validate(data)
