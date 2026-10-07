from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuthRole = Literal["candidate", "employer"]


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(repr=False)
    role: AuthRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: AuthRole
    is_verified: bool


class LoginRequest(BaseModel):
    email: str
    password: str = Field(repr=False)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    status: Literal["ok"] = "ok"
