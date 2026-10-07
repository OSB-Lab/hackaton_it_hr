import re
from datetime import datetime, timedelta, timezone
from typing import Literal, TypeVar

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.core.config import get_settings
from app.modules.auth.schemas import AuthRole

_password_hasher = PasswordHasher(type=Type.ID)


class InvalidTokenError(ValueError):
    """Invalid signature, expiration, token purpose or claims; no HTTP semantics."""


class _TokenClaims(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    sub: str
    exp: int

    @field_validator("sub")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        if re.fullmatch(r"[1-9][0-9]*", value) is None:
            raise ValueError("Token subject must be a positive integer user id")
        # Also reject strings exceeding Python's integer conversion limit.
        int(value)
        return value


class AccessTokenClaims(_TokenClaims):
    role: AuthRole
    type: Literal["access"]


class _EmailVerificationClaims(_TokenClaims):
    type: Literal["email_verification"]


Claims = TypeVar("Claims", bound=_TokenClaims)


def hash_password(password: str) -> str:
    """Return a randomly salted Argon2id hash without storing the password."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return False for mismatches, malformed hashes and unsupported formats."""
    if not isinstance(password_hash, str) or not password_hash.startswith("$argon2id$"):
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, UnicodeError):
        return False


def _subject(user_id: int) -> str:
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("User id must be a positive integer")
    return str(user_id)


def _expiration(ttl_minutes: int) -> int:
    return int(
        (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).timestamp()
    )


def _encode(claims: _TokenClaims) -> str:
    settings = get_settings()
    return jwt.encode(
        claims.model_dump(),
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def _decode(token: str, claims_model: type[Claims]) -> Claims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
        return claims_model.model_validate(payload)
    except (jwt.InvalidTokenError, ValidationError, ValueError, TypeError, OverflowError):
        # Do not expose token contents or underlying library errors to callers.
        raise InvalidTokenError("Invalid or expired token") from None


def create_access_token(user_id: int, role: AuthRole) -> str:
    settings = get_settings()
    return _encode(AccessTokenClaims(
        sub=_subject(user_id),
        role=role,
        exp=_expiration(settings.ACCESS_TOKEN_TTL_MINUTES),
        type="access",
    ))


def decode_access_token(token: str) -> AccessTokenClaims:
    return _decode(token, AccessTokenClaims)


def create_email_verification_token(user_id: int) -> str:
    settings = get_settings()
    return _encode(_EmailVerificationClaims(
        sub=_subject(user_id),
        exp=_expiration(settings.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES),
        type="email_verification",
    ))


def decode_email_verification_token(token: str) -> int:
    return int(_decode(token, _EmailVerificationClaims).sub)
