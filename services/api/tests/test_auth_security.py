import base64
import time

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.auth import security

TEST_SECRET = "security-unit-tests-only-" + "x" * 64


@pytest.fixture
def security_settings(monkeypatch):
    settings = Settings(
        _env_file=None,
        POSTGRES_USER="unused",
        POSTGRES_PASSWORD="unused",
        POSTGRES_DB="unused",
        POSTGRES_HOST="unused.invalid",
        JWT_SECRET=TEST_SECRET,
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_TTL_MINUTES=7,
        EMAIL_VERIFICATION_TOKEN_TTL_MINUTES=23,
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    return settings


@pytest.fixture
def password_hash():
    return security.hash_password("test-password-Юникод")


def payload(token_type):
    claims = {
        "sub": "42", "exp": int(time.time()) + 300, "type": token_type,
    }
    if token_type == "access":
        claims["role"] = "candidate"
    return claims


def sign(claims, algorithm="HS256", key=TEST_SECRET):
    return jwt.encode(claims, key, algorithm=algorithm)


def decoder(token_type):
    return (
        security.decode_access_token if token_type == "access"
        else security.decode_email_verification_token
    )


def test_argon2id_hash_and_verification(password_hash):
    assert password_hash != "test-password-Юникод"
    assert password_hash.startswith("$argon2id$")
    assert security.verify_password("test-password-Юникод", password_hash)
    assert not security.verify_password("wrong-password", password_hash)


def test_password_hash_uses_random_salt(password_hash):
    second_hash = security.hash_password("test-password-Юникод")
    assert second_hash != password_hash
    assert security.verify_password("test-password-Юникод", second_hash)


@pytest.mark.parametrize("invalid_hash", [
    "", "not-a-hash", "$2b$12$unsupported-bcrypt",
    "$argon2i$unsupported", "$argon2d$unsupported",
    "$argon2id$malformed", "$argon2id$v=19$m=invalid,t=3,p=4$salt$hash", None,
])
def test_invalid_password_hash_returns_false(invalid_hash):
    assert security.verify_password("test-password", invalid_hash) is False


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_access_round_trip_and_configured_ttl(security_settings, role):
    before = int(time.time())
    token = security.create_access_token(42, role)
    after = int(time.time())
    claims = security.decode_access_token(token)
    assert claims.sub == "42"
    assert claims.role == role
    assert claims.type == "access"
    ttl = security_settings.ACCESS_TOKEN_TTL_MINUTES * 60
    assert before + ttl <= claims.exp <= after + ttl
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_verification_round_trip_and_configured_ttl(security_settings):
    before = int(time.time())
    token = security.create_email_verification_token(42)
    after = int(time.time())
    assert security.decode_email_verification_token(token) == 42
    claims = jwt.decode(token, TEST_SECRET, algorithms=["HS256"])
    assert claims["sub"] == "42"
    assert claims["type"] == "email_verification"
    ttl = security_settings.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES * 60
    assert before + ttl <= claims["exp"] <= after + ttl


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
def test_expired_tokens_are_rejected(security_settings, token_type):
    claims = payload(token_type)
    claims["exp"] = int(time.time()) - 60
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(sign(claims))


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
@pytest.mark.parametrize("token", ["", "not-a-token", "a.b.c"])
def test_malformed_tokens_are_rejected(security_settings, token_type, token):
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(token)


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
def test_tampered_signature_is_rejected(security_settings, token_type):
    header, body, signature = sign(payload(token_type)).split(".")
    raw = bytearray(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
    raw[0] ^= 1
    changed = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(f"{header}.{body}.{changed}")


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
def test_wrong_signing_key_is_rejected(security_settings, token_type):
    token = sign(payload(token_type), key="another-test-key-" + "y" * 64)
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(token)


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
@pytest.mark.parametrize("algorithm", ["HS512", "none"])
def test_algorithm_is_taken_from_settings_not_header(security_settings, token_type, algorithm):
    token = sign(
        payload(token_type), algorithm=algorithm,
        key=None if algorithm == "none" else TEST_SECRET,
    )
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(token)


@pytest.mark.parametrize("role", ["admin", "Candidate", None, 1, ""])
def test_invalid_access_role_is_rejected(security_settings, role):
    claims = payload("access")
    claims["role"] = role
    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(sign(claims))


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
@pytest.mark.parametrize("sub", ["abc", "", "0", "-1", "+1", "01", "1.5", " 1", "١", "1\n", 42, None])
def test_invalid_subject_is_rejected(security_settings, token_type, sub):
    claims = payload(token_type)
    claims["sub"] = sub
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(sign(claims))


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
@pytest.mark.parametrize("claim", ["sub", "exp", "type"])
def test_required_claims(security_settings, token_type, claim):
    claims = payload(token_type)
    del claims[claim]
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(sign(claims))


def test_access_role_is_required(security_settings):
    claims = payload("access")
    del claims["role"]
    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(sign(claims))


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
@pytest.mark.parametrize("exp", [None, True, "9999999999", 9999999999.5, float("inf")])
def test_invalid_expiration_type_is_rejected(security_settings, token_type, exp):
    claims = payload(token_type)
    claims["exp"] = exp
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(sign(claims))


def test_token_types_are_not_interchangeable(security_settings):
    access = security.create_access_token(42, "candidate")
    verification = security.create_email_verification_token(42)
    with pytest.raises(security.InvalidTokenError):
        security.decode_email_verification_token(access)
    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(verification)


@pytest.mark.parametrize("token_type", ["access", "email_verification"])
def test_unknown_purpose_is_rejected(security_settings, token_type):
    claims = payload(token_type)
    claims["type"] = "password_reset"
    with pytest.raises(security.InvalidTokenError):
        decoder(token_type)(sign(claims))


@pytest.mark.parametrize("user_id", [0, -1, True, "42"])
def test_creation_rejects_invalid_user_id(security_settings, user_id):
    with pytest.raises(ValueError):
        security.create_access_token(user_id, "candidate")
    with pytest.raises(ValueError):
        security.create_email_verification_token(user_id)


def test_creation_rejects_invalid_role(security_settings):
    with pytest.raises(ValidationError):
        security.create_access_token(42, "admin")


@pytest.mark.parametrize("setting", [
    "ACCESS_TOKEN_TTL_MINUTES", "EMAIL_VERIFICATION_TOKEN_TTL_MINUTES",
])
@pytest.mark.parametrize("value", [0, -1])
def test_ttl_must_be_positive(security_settings, setting, value):
    values = security_settings.model_dump()
    values[setting] = value
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_settings_reject_unsigned_algorithm(security_settings):
    values = security_settings.model_dump()
    values["JWT_ALGORITHM"] = "none"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
