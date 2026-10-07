from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

AuthRole = Literal["candidate", "employer"]


def normalize_email(value):
    return value.strip().lower() if isinstance(value, str) else value


NormalizedEmail = Annotated[EmailStr, BeforeValidator(normalize_email)]


class RegisterRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(repr=False)
    role: AuthRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: AuthRole
    is_verified: bool


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(repr=False)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    status: Literal["ok"] = "ok"
