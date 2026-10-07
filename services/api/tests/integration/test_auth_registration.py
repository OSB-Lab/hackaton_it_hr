import json
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.main import app
from app.models.user import User
from app.modules.auth import mailer, router, security, service

PASSWORD = "Registration-Test-Password!"
TOKEN_SECRET = "registration-tests-only-" + "x" * 64


@pytest.fixture
def auth_env(migrated_engine, monkeypatch):
    previous_overrides = app.dependency_overrides.copy()
    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    sessions = []
    sent = []

    def get_session():
        with factory() as session:
            sessions.append(session)
            yield session

    def send_email(email, token):
        sent.append((email, token))
        return True

    settings = get_settings().model_copy(update={"JWT_SECRET": SecretStr(TOKEN_SECRET)})
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(router, "send_verification_email", send_email)
    app.dependency_overrides[router.get_auth_session] = get_session
    try:
        with TestClient(app) as client:
            yield SimpleNamespace(
                client=client, engine=migrated_engine, sessions=sessions, sent=sent,
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def register(client, email="candidate@example.com", role="candidate"):
    return client.post("/auth/register", json={
        "email": email, "password": PASSWORD, "role": role,
    })


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_register(auth_env, role):
    response = register(auth_env.client, role=role)
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"id", "email", "role", "is_verified"}
    assert isinstance(data["id"], int)
    assert data["email"] == "candidate@example.com"
    assert data["role"] == role
    assert data["is_verified"] is False
    with Session(auth_env.engine) as session:
        user = session.get(User, data["id"])
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$argon2id$")
        assert security.verify_password(PASSWORD, user.password_hash)
        assert user.is_verified is False
    assert auth_env.sent[0][0] == data["email"]
    assert security.decode_email_verification_token(auth_env.sent[0][1]) == data["id"]


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_register_login_me_happy_path(auth_env, role):
    registered = register(auth_env.client, role=role)
    assert registered.status_code == 201
    login = auth_env.client.post("/auth/login", json={
        "email": "  Candidate@EXAMPLE.COM  ", "password": PASSWORD,
    })
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    token = login.json()["access_token"]
    claims = security.decode_access_token(token)
    assert claims.sub == str(registered.json()["id"])
    assert claims.role == role
    me = auth_env.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == registered.json()
    assert "password_hash" not in me.json()


def test_register_invalid_role(auth_env):
    assert register(auth_env.client, role="admin").status_code == 422
    assert auth_env.sent == []
    with Session(auth_env.engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("email", ["bad-email", "user@", "user @example.com"])
def test_register_invalid_email(auth_env, email):
    assert register(auth_env.client, email=email).status_code == 422
    assert auth_env.sent == []


def test_email_normalization_and_duplicates(auth_env):
    first = register(auth_env.client, email="  Candidate@EXAMPLE.COM  ")
    assert first.status_code == 201
    assert first.json()["email"] == "candidate@example.com"
    assert register(auth_env.client).status_code == 409
    assert register(auth_env.client, email="CANDIDATE@example.COM").status_code == 409
    assert len(auth_env.sent) == 1
    with Session(auth_env.engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_legacy_mixed_case_email_is_duplicate(auth_env):
    with Session(auth_env.engine) as session, session.begin():
        session.add(User(
            email="Candidate@Example.COM", password_hash="existing-fixture",
            role="candidate", is_verified=False,
        ))
    assert register(auth_env.client).status_code == 409
    assert auth_env.sent == []


def test_verify_email_and_repeat(auth_env):
    user_id = register(auth_env.client).json()["id"]
    token = auth_env.sent[0][1]
    for _ in range(2):
        response = auth_env.client.post("/auth/verify-email", json={"token": token})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    with Session(auth_env.engine) as session:
        assert session.get(User, user_id).is_verified is True


@pytest.mark.parametrize("kind", ["malformed", "expired", "access", "missing-user"])
def test_invalid_verification(auth_env, kind):
    user_id = register(auth_env.client).json()["id"]
    if kind == "malformed":
        token = "invalid-token"
    elif kind == "expired":
        token = jwt.encode({
            "sub": str(user_id), "type": "email_verification",
            "exp": int(time.time()) - 60,
        }, TOKEN_SECRET, algorithm="HS256")
    elif kind == "access":
        token = security.create_access_token(user_id, "candidate")
    else:
        token = security.create_email_verification_token(user_id + 10000)
    response = auth_env.client.post("/auth/verify-email", json={"token": token})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid verification token"}
    with Session(auth_env.engine) as session:
        assert session.get(User, user_id).is_verified is False


def test_registration_sends_smtp_token_after_commit(auth_env, monkeypatch):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp

    def connect(*args, **kwargs):
        assert not auth_env.sessions[-1].in_transaction()
        with Session(auth_env.engine) as session:
            assert session.scalar(select(func.count()).select_from(User)) == 1
        assert kwargs["timeout"] == 5
        return smtp

    monkeypatch.setattr(mailer.smtplib, "SMTP", connect)
    monkeypatch.setattr(router, "send_verification_email", mailer.send_verification_email)
    response = register(auth_env.client)
    assert response.status_code == 201
    smtp.send_message.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert str(message["To"]) == "candidate@example.com"
    assert str(message["From"]) == get_settings().SMTP_FROM
    body = message.get_content()
    assert PASSWORD not in body
    token = json.loads(next(line for line in body.splitlines() if line.startswith("{")))["token"]
    assert security.decode_email_verification_token(token) == response.json()["id"]


@pytest.mark.parametrize("error", [smtplib.SMTPException("SMTP unavailable"), OSError("offline")])
def test_smtp_failure_keeps_committed_user_and_returns_201(auth_env, monkeypatch, caplog, error):
    def unavailable(*args, **kwargs):
        assert not auth_env.sessions[-1].in_transaction()
        raise error

    monkeypatch.setattr(mailer.smtplib, "SMTP", unavailable)
    monkeypatch.setattr(router, "send_verification_email", mailer.send_verification_email)
    response = register(auth_env.client)
    assert response.status_code == 201
    with Session(auth_env.engine) as session:
        user = session.get(User, response.json()["id"])
        assert user is not None and user.is_verified is False
    assert not auth_env.sessions[-1].in_transaction()
    assert register(auth_env.client).status_code == 409
    assert PASSWORD not in caplog.text
    assert "Verification email delivery failed" in caplog.text


def test_duplicate_race_rolls_back_and_returns_409(auth_env):
    barrier = Barrier(2)
    rolled_back = []

    class RaceSession(Session):
        def commit(self):
            # Both requests have passed SELECT before either INSERT is committed.
            barrier.wait(timeout=15)
            return super().commit()

        def rollback(self):
            rolled_back.append(self)
            return super().rollback()

    def race_session():
        with RaceSession(auth_env.engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[router.get_auth_session] = race_session
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(register, auth_env.client, email)
            for email in ("Race@EXAMPLE.COM", " race@example.com ")
        ]
        responses = [future.result(timeout=25) for future in futures]
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert len(rolled_back) == 1
    # The losing request explicitly rolled back, and its Session is reusable.
    with rolled_back[0] as session:
        assert session.scalar(select(1)) == 1
        assert session.scalar(select(func.count()).select_from(User)) == 1
    assert len(auth_env.sent) == 1


def test_other_integrity_error_is_not_reported_as_duplicate(auth_env, monkeypatch):
    # Real NOT NULL violation, not the email unique constraint.
    monkeypatch.setattr(service, "hash_password", lambda password: None)
    response = register(auth_env.client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Registration unavailable"}
    assert auth_env.sent == []
    with auth_env.sessions[-1] as session:
        assert session.scalar(select(1)) == 1
        assert session.scalar(select(func.count()).select_from(User)) == 0


def test_verification_database_error_is_sanitized(auth_env, monkeypatch):
    from sqlalchemy.exc import OperationalError

    user_id = register(auth_env.client).json()["id"]
    token = auth_env.sent[0][1]
    original_get = Session.get

    def unavailable(self, *args, **kwargs):
        raise OperationalError("private SQL", {}, Exception("private DB details"))

    monkeypatch.setattr(Session, "get", unavailable)
    response = auth_env.client.post("/auth/verify-email", json={"token": token})
    assert response.status_code == 503
    assert response.json() == {"detail": "Email verification unavailable"}
    monkeypatch.setattr(Session, "get", original_get)
    with Session(auth_env.engine) as session:
        assert session.get(User, user_id).is_verified is False


def test_openapi_auth_routes(auth_env):
    paths = auth_env.client.get("/openapi.json").json()["paths"]
    assert {path for path in paths if path.startswith("/auth/")} == {
        "/auth/register", "/auth/verify-email", "/auth/login", "/auth/me",
    }
    assert "201" in paths["/auth/register"]["post"]["responses"]
    assert "200" in paths["/auth/verify-email"]["post"]["responses"]
