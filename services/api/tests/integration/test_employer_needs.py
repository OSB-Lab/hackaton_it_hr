import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HiringNeed
from app.models import Company
from app.commands.seed_demo import _read_json
from app.modules.employer.needs_schemas import NeedCreate, NeedPatch
from app.modules.employer.needs_service import create_need, update_need
from test_employer_company import company_env

URL = "/employer/needs"
BODY = {"title": "Engineer", "teamDescription": "Our team", "specialization": "backend",
        "minGrade": "junior", "targetGrade": "middle",
        "requiredSkills": ["python"], "optionalSkills": ["sql"]}


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


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("changes", [
    {"specialization": "unknown"}, {"minGrade": "expert"}, {"targetGrade": "expert"},
    {"requiredSkills": ["unknown"]}, {"optionalSkills": ["unknown"]},
    {"requiredSkills": ["react"]}, {"specialization": "frontend"},
    {"minGrade": "senior"},
    {"minGrade": "middle", "targetGrade": "junior"},
    {"requiredSkills": ["python", "python"]}, {"optionalSkills": ["sql", "sql"]},
    {"optionalSkills": ["python"]}, {"requiredSkills": ["sql"]},
])
def test_catalog_and_cross_field_validation_is_atomic(company_env, method, changes):
    client, headers, _, _ = company_env
    companies(client, headers)
    original = client.post(URL, headers=headers[0], json=BODY).json()
    path = URL if method == "post" else f'{URL}/{original["id"]}'
    payload = {**BODY, **changes, "title": "Must not persist"} if method == "post" else {**changes, "title": "Must not persist"}
    response = getattr(client, method)(path, headers=headers[0], json=payload)
    assert response.status_code == 422
    assert client.get(URL, headers=headers[0]).json() == [original]


def test_patch_merged_fields_and_equal_grades(company_env):
    client, headers, _, _ = company_env
    companies(client, headers)
    original = client.post(URL, headers=headers[0], json=BODY).json()
    path = f'{URL}/{original["id"]}'
    response = client.patch(path, headers=headers[0], json={"minGrade": "middle"})
    assert response.status_code == 200
    assert response.json() == {**original, "minGrade": "middle"}
    assert client.patch(path, headers=headers[0], json={"targetGrade": "junior"}).status_code == 422
    changes = {"specialization": "frontend", "requiredSkills": ["react"], "optionalSkills": ["typescript"]}
    response = client.patch(path, headers=headers[0], json=changes)
    assert response.status_code == 200
    assert response.json() == {**original, "minGrade": "middle", **changes}


def test_legacy_seed_row_is_readable_and_can_be_migrated_explicitly(company_env):
    client, headers, ids, engine = company_env
    companies(client, headers)
    old = _read_json("employers.json")["employers"][0]["hiring_needs"][0]
    with Session(engine) as session, session.begin():
        cid = session.scalar(select(Company.id).where(Company.user_id == ids[0]))
        row = HiringNeed(company_id=cid, **old)
        session.add(row)
        session.flush()
        need_id = row.id
    path = f"{URL}/{need_id}"
    response = client.get(path, headers=headers[0])
    assert response.status_code == 200
    expected = {"id": need_id, "title": old["title"], "teamDescription": None,
                "specialization": old["specialization"], "minGrade": None,
                "targetGrade": old["grade"], "requiredSkills": old["stack"], "optionalSkills": None}
    assert response.json() == expected
    assert client.patch(path, headers=headers[0], json={"teamDescription": "Team"}).json() == {**expected, "teamDescription": "Team"}
    assert client.patch(path, headers=headers[0], json={"optionalSkills": ["sql"]}).status_code == 422
    update = {"requiredSkills": ["python"], "optionalSkills": ["sql"], "minGrade": "junior"}
    response = client.patch(path, headers=headers[0], json=update)
    assert response.status_code == 200
    assert response.json() == {**expected, "teamDescription": "Team", **update}


def test_catalog_unavailable_fails_closed(company_env, monkeypatch):
    from app.modules.employer import needs_service
    client, headers, _, _ = company_env
    companies(client, headers)
    original = client.post(URL, headers=headers[0], json=BODY).json()
    def unavailable(): raise ValueError("checksum mismatch")
    monkeypatch.setattr(needs_service, "CatalogRepository", unavailable)
    assert client.post(URL, headers=headers[0], json={**BODY, "title": "Another"}).status_code == 503
    assert client.patch(f'{URL}/{original["id"]}', headers=headers[0], json={"minGrade": "middle"}).status_code == 503
    assert client.get(URL, headers=headers[0]).json() == [original]
