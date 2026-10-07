import time
from typing import Annotated
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.modules.auth import dependencies, security
from app.modules.auth.router import router

PASSWORD = "Login-Test-Password!"
SECRET = "login-test-secret-" + "x" * 64


@pytest.fixture
def login_env(migrated_engine, monkeypatch):
    settings = get_settings().model_copy(update={"JWT_SECRET": SecretStr(SECRET)})
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    with Session(migrated_engine) as session, session.begin():
        users = [User(email=f"{role}@example.com", role=role,
                      password_hash=security.hash_password(PASSWORD), is_verified=False)
                 for role in ("candidate", "employer")]
        session.add_all(users)
        session.flush()
        ids = {user.role: user.id for user in users}

    test_app = FastAPI()
    test_app.include_router(router)

    def get_session():
        with Session(migrated_engine) as session:
            yield session

    test_app.dependency_overrides[dependencies.get_auth_session] = get_session

    def protected(role):
        def endpoint(user: Annotated[User, Depends(dependencies.require_role(role))]):
            assert isinstance(user, User)
            return {"id": user.id, "role": user.role}
        return endpoint

    for role in ids:
        test_app.get(f"/test/{role}")(protected(role))
    with TestClient(test_app) as client:
        yield SimpleNamespace(client=client, ids=ids, engine=migrated_engine)


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_login_and_me_for_unverified_users(login_env, role):
    response = login_env.client.post("/auth/login", json={
        "email": f"  {role.upper()}@EXAMPLE.COM  ", "password": PASSWORD,
    })
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    token = response.json()["access_token"]
    claims = security.decode_access_token(token)
    assert claims.sub == str(login_env.ids[role]) and claims.role == role
    response = login_env.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {
        "id": login_env.ids[role], "email": f"{role}@example.com",
        "role": role, "is_verified": False,
    }


def test_bad_credentials_have_identical_public_error(login_env):
    results = [login_env.client.post("/auth/login", json={"email": email, "password": password})
               for email, password in [("candidate@example.com", "wrong"),
                                       ("unknown@example.com", PASSWORD)]]
    for response in results:
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    assert results[0].json() == results[1].json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize("kind", ["absent", "malformed", "empty", "basic", "expired",
                                  "verification", "missing-user", "signature"])
def test_me_rejects_unauthenticated_requests(login_env, kind):
    user_id = login_env.ids["candidate"]
    token = "broken-token"
    if kind == "expired" or kind == "signature":
        token = jwt.encode({"sub": str(user_id), "role": "candidate", "type": "access",
                            "exp": int(time.time()) + (-60 if kind == "expired" else 600)},
                           SECRET if kind == "expired" else "wrong-secret-" + "z" * 64,
                           algorithm="HS256")
    elif kind == "verification":
        token = security.create_email_verification_token(user_id)
    elif kind == "missing-user":
        token = security.create_access_token(user_id + 10000, "candidate")
    headers = {"Authorization": f"Bearer {token}"}
    if kind == "absent":
        headers = {}
    elif kind == "empty":
        headers = {"Authorization": "Bearer"}
    elif kind == "basic":
        headers = {"Authorization": "Basic abc"}
    response = login_env.client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize("role,target,status", [
    ("candidate", "candidate", 200), ("employer", "employer", 200),
    ("candidate", "employer", 403), ("employer", "candidate", 403),
])
def test_role_access(login_env, role, target, status):
    token = security.create_access_token(login_env.ids[role], role)
    response = login_env.client.get(f"/test/{target}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status
    if status == 200:
        assert response.json() == {"id": login_env.ids[role], "role": role}


def test_me_and_rbac_use_current_database_role(login_env):
    user_id = login_env.ids["candidate"]
    token = security.create_access_token(user_id, "candidate")
    with Session(login_env.engine) as session, session.begin():
        session.get(User, user_id).role = "employer"
    headers = {"Authorization": f"Bearer {token}"}
    assert login_env.client.get("/auth/me", headers=headers).json()["role"] == "employer"
    assert login_env.client.get("/test/candidate", headers=headers).status_code == 403
    assert login_env.client.get("/test/employer", headers=headers).status_code == 200
    with Session(login_env.engine) as session, session.begin():
        session.delete(session.get(User, user_id))
    assert login_env.client.get("/auth/me", headers=headers).status_code == 401


def test_role_route_requires_authentication(login_env):
    assert login_env.client.get("/test/candidate").status_code == 401


def test_openapi_bearer_security(login_env):
    schema = login_env.client.get("/openapi.json").json()
    assert schema["paths"]["/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
