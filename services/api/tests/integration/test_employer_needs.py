import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HiringNeed
from app.modules.employer.needs_schemas import NeedCreate, NeedPatch
from app.modules.employer.needs_service import create_need, update_need
from test_employer_company import company_env

URL = "/employer/needs"
BODY = {"title": "Engineer", "teamDescription": "Our team", "specialization": "future-specialization",
        "minGrade": "future-min", "targetGrade": "future-target",
        "requiredSkills": ["future-skill"], "optionalSkills": ["another-skill"]}


def companies(client, headers):
    for i in (0, 1):
        assert client.put("/employer/company", headers=headers[i], json={"name": f"Company {i}"}).status_code == 200


def test_create_read_list_patch_and_ownership(company_env):
    client, headers, ids, engine = company_env
    assert client.post(URL, headers=headers[0], json=BODY).status_code == 409
    assert client.get(URL, headers=headers[0]).json() == []
    companies(client, headers)
    created = client.post(URL, headers=headers[0], json=BODY)
    assert created.status_code == 201
    need = created.json()
    assert need == {"id": need["id"], **BODY}
    path = f'{URL}/{need["id"]}'
    assert client.get(path, headers=headers[0]).json() == need
    assert client.get(URL, headers=headers[0]).json() == [need]
    assert client.get(URL, headers=headers[1]).json() == []
    for method in ("get", "patch"):
        kwargs = {"json": {"title": "Stolen"}} if method == "patch" else {}
        foreign = getattr(client, method)(path, headers=headers[1], **kwargs)
        missing = getattr(client, method)(URL + "/999999", headers=headers[1], **kwargs)
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()
    assert client.get(path, headers=headers[0]).json() == need
    # Identical titles across companies are allowed.
    assert client.post(URL, headers=headers[1], json=BODY).status_code == 201
    updated = client.patch(path, headers=headers[0], json={"teamDescription": None, "optionalSkills": []})
    assert updated.status_code == 200
    assert updated.json() == {**need, "teamDescription": None, "optionalSkills": []}
    assert client.patch(path, headers=headers[0], json={}).json() == updated.json()
    with Session(engine) as session:
        row = session.get(HiringNeed, need["id"])
        assert row.grade == BODY["targetGrade"] and row.stack == BODY["requiredSkills"]


def test_duplicate_create_and_patch_rollback(company_env):
    client, headers, ids, engine = company_env
    companies(client, headers)
    first = client.post(URL, headers=headers[0], json=BODY).json()
    assert client.post(URL, headers=headers[0], json=BODY).status_code == 409
    second = client.post(URL, headers=headers[0], json={**BODY, "title": "Second"}).json()
    path = f'{URL}/{second["id"]}'
    assert client.patch(path, headers=headers[0], json={"title": BODY["title"], "teamDescription": "Should roll back"}).status_code == 409
    assert client.get(path, headers=headers[0]).json() == second
    with Session(engine, expire_on_commit=False) as session:
        for operation in (
            lambda: create_need(session, ids[0], NeedCreate(**BODY)),
            lambda: update_need(session, ids[0], second["id"], NeedPatch(title=BODY["title"])),
        ):
            with pytest.raises(HTTPException) as exc:
                operation()
            assert exc.value.status_code == 409
            assert not session.in_transaction()
            assert session.scalar(select(1)) == 1
        assert session.get(HiringNeed, first["id"]).title == BODY["title"]


@pytest.mark.parametrize("method,suffix", [("post", ""), ("get", ""), ("get", "/1"), ("patch", "/1")])
@pytest.mark.parametrize("actor,status", [(2, 403), (None, 401)])
def test_rbac(company_env, method, suffix, actor, status):
    client, headers, _, _ = company_env
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    if method in ("post", "patch"):
        kwargs["json"] = BODY
    assert getattr(client, method)(URL + suffix, **kwargs).status_code == status


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("field,value", [
    ("id", 1), ("companyId", 1), ("userId", 1), ("ownerId", 1),
    ("company_id", 1), ("unknown", "value"), ("title", "  "),
    ("specialization", ""), ("minGrade", " "), ("targetGrade", None),
    ("requiredSkills", [""]), ("optionalSkills", [7]), ("requiredSkills", "Python"),
])
def test_validation(company_env, method, field, value):
    client, headers, _, _ = company_env
    companies(client, headers)
    existing = client.post(URL, headers=headers[0], json=BODY).json()
    payload = {**BODY, field: value} if method == "post" else {field: value}
    path = URL if method == "post" else f'{URL}/{existing["id"]}'
    assert getattr(client, method)(path, headers=headers[0], json=payload).status_code == 422
    assert client.get(URL, headers=headers[0]).json() == [existing]


def test_openapi(company_env):
    client, _, _, _ = company_env
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in [(URL, {"get", "post"}), (URL + "/{need_id}", {"get", "patch"})]:
        assert set(paths[path]) == methods
        for method in methods:
            assert paths[path][method]["security"] == [{"HTTPBearer": []}]
