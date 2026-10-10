from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app
from app.models import Company, User
from app.modules.auth import dependencies, security

URL = "/employer/company"


@pytest.fixture
def company_env(migrated_engine, monkeypatch):
    settings = get_settings().model_copy(update={"JWT_SECRET": SecretStr("company-tests-" + "x" * 64)})
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    with Session(migrated_engine) as session, session.begin():
        users = [User(email=f"company{i}@example.com", password_hash="fixture", role=role)
                 for i, role in enumerate(("employer", "employer", "candidate"))]
        session.add_all(users)
        session.flush()
        ids = [user.id for user in users]
        headers = [{"Authorization": "Bearer " + security.create_access_token(user.id, user.role)}
                   for user in users]

    def get_session():
        with Session(migrated_engine, expire_on_commit=False) as session:
            yield session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[dependencies.get_auth_session] = get_session
    try:
        with TestClient(app) as client:
            yield client, headers, ids, migrated_engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_create_edit_repeat_and_owner_isolation(company_env):
    client, headers, ids, engine = company_env
    assert client.get(URL, headers=headers[0]).status_code == 404
    payload = {"name": "Company A", "description": "First", "contacts": {"email": "a@example.com"}}
    created = client.put(URL, headers=headers[0], json=payload)
    assert created.status_code == 200
    company_id = created.json()["id"]
    assert created.json() == {"id": company_id, **payload}
    assert client.get(URL, headers=headers[0]).json() == created.json()
    assert client.get(URL, headers=headers[1]).status_code == 404
    other = client.put(URL, headers=headers[1], json={"name": "Company B"})
    assert other.status_code == 200 and other.json()["id"] != company_id
    assert client.get(URL, headers=headers[0]).json() == created.json()
    updated_payload = {"name": "Updated A", "description": "Updated", "contacts": {"phone": "+123456789"}}
    for _ in range(2):
        updated = client.put(URL, headers=headers[0], json=updated_payload)
        assert updated.status_code == 200
        assert updated.json() == {"id": company_id, **updated_payload}
    assert client.get(URL, headers=headers[1]).json() == other.json()
    replaced = client.put(URL, headers=headers[0], json={"name": "Only name"})
    assert replaced.json() == {"id": company_id, "name": "Only name", "description": None, "contacts": None}
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Company)) == 2
        assert session.get(Company, company_id).user_id == ids[0]


@pytest.mark.parametrize("method", ["get", "put"])
@pytest.mark.parametrize("actor,status", [(2, 403), (None, 401)])
def test_access_control(company_env, method, actor, status):
    client, headers, _, _ = company_env
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    if method == "put":
        kwargs["json"] = {"name": "Forbidden"}
    assert getattr(client, method)(URL, **kwargs).status_code == status


@pytest.mark.parametrize("field", ["id", "company_id", "companyId", "user_id", "userId", "owner_id", "ownerId"])
def test_foreign_ids_cannot_transfer_ownership(company_env, field):
    client, headers, ids, engine = company_env
    original = client.put(URL, headers=headers[0], json={"name": "Owner A"}).json()
    value = ids[0] if "user" in field.lower() or "owner" in field.lower() else original["id"]
    response = client.put(URL, headers=headers[1], json={"name": "Stolen", field: value})
    assert response.status_code == 422
    assert client.get(URL, headers=headers[0]).json() == original
    assert client.get(URL, headers=headers[1]).status_code == 404
    with Session(engine) as session:
        assert session.get(Company, original["id"]).user_id == ids[0]


@pytest.mark.parametrize("payload", [{}, {"name": " "}, {"name": None}, {"name": "A", "contacts": []}])
def test_invalid_payload(company_env, payload):
    client, headers, _, _ = company_env
    assert client.put(URL, headers=headers[0], json=payload).status_code == 422


def test_concurrent_put_keeps_one_company(company_env):
    client, headers, ids, engine = company_env
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.put, URL, headers=headers[0], json={"name": name})
                   for name in ("First", "Second")]
        responses = [future.result(timeout=15) for future in futures]
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Company).where(Company.user_id == ids[0])) == 1


def test_company_openapi(company_env):
    client, _, _, _ = company_env
    schema = client.get("/openapi.json").json()
    assert {path for path in schema["paths"] if path.startswith("/employer/")} == {
        URL, "/employer/needs", "/employer/needs/{need_id}",
        "/employer/needs/{need_id}/recommendations",
        "/employer/needs/{need_id}/recommendations/{snapshot_id}",
        "/employer/needs/{need_id}/recommendations/{snapshot_id}/items",
    }
    assert set(schema["paths"][URL]) == {"get", "put"}
    for method in ("get", "put"):
        assert schema["paths"][URL][method]["security"] == [{"HTTPBearer": []}]
