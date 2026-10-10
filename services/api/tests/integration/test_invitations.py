from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, CandidateProfile, Company, Consent, ContactDisclosure, Invitation, User
from app.modules.invitations import service
from test_employer_company import company_env

BODY = {"offerDescription": "Backend role", "contactMethod": "email", "salaryMin": "100.01", "salaryMax": "200.02"}


@pytest.fixture
def invite_env(company_env):
    client, headers, ids, engine = company_env
    with Session(engine) as session, session.begin():
        companies = [Company(user_id=uid, name="Company") for uid in ids[:2]]
        profile = CandidateProfile(user_id=ids[2], grade="senior", self_declared_grade="senior",
                                   phone="+79991234567", privacy_settings={"show_contacts": True, "publish_profile": True})
        session.add_all([*companies, profile])
        session.get(User, ids[2]).is_verified = True
        session.add(Consent(user_id=ids[2], kind="publish_profile", granted=True))
        session.add(Consent(user_id=ids[2], kind="privacy", granted=True))
        session.flush()
        body = {**BODY, "companyId": companies[0].id, "candidateId": profile.id}
        other = companies[1].id
    return company_env, body, other


def approve_for_test(monkeypatch):
    # Test-only stand-in for a future authoritative SPR-15.3 provider, never shipped as runtime policy.
    monkeypatch.setattr(service.eligibility, "has_verified_qualification", lambda session, candidate_id: True)


def records(engine, model):
    with Session(engine) as session:
        return list(session.scalars(select(model).order_by(model.id)))


def seed_invitation(env, status="sent"):
    (_, _, _, engine), body, _ = env
    with Session(engine) as session, session.begin():
        row = Invitation(company_id=body["companyId"], candidate_id=body["candidateId"], title="Legacy offer",
                         salary_from=100, salary_to=200, status=status)
        session.add(row)
        session.flush()
        return row.id


def test_create_and_decimal_storage(invite_env, monkeypatch):
    (client, headers, ids, engine), body, _ = invite_env
    approve_for_test(monkeypatch)
    response = client.post("/invitations", headers=headers[0], json=body)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "sent" and data["currency"] == "RUB"
    assert Decimal(data["salaryMin"]) == Decimal("100.01")
    assert "contacts" not in data and "password" not in response.text
    row = records(engine, Invitation)[0]
    assert row.salary_from == Decimal("100.01")
    audit = records(engine, AuditEvent)
    assert len(audit) == 1 and audit[0].user_id == ids[0] and audit[0].created_at is not None
    assert audit[0].action == "invitation.created"
    assert audit[0].payload == {"invitationId": data["id"], "from": None, "to": "sent"}
    assert client.get("/invitations", headers=headers[2]).json()[0]["id"] == data["id"]
    assert client.get("/invitations", headers=headers[1]).json() == []
    assert len(records(engine, AuditEvent)) == 1  # Listing does not view.


@pytest.mark.parametrize("field", ["salaryMin", "salaryMax", "companyId", "candidateId", "offerDescription", "contactMethod"])
def test_required_fields(invite_env, field):
    (client, headers, _, engine), body, _ = invite_env
    payload = dict(body)
    del payload[field]
    assert client.post("/invitations", headers=headers[0], json=payload).status_code == 422
    assert records(engine, Invitation) == records(engine, AuditEvent) == []


@pytest.mark.parametrize("changes", [
    {"salaryMin": "0"}, {"salaryMin": "-1"}, {"salaryMax": "0"}, {"salaryMax": "-1"},
    {"salaryMax": "1"}, {"salaryMin": 100.01}, {"salaryMax": 200.02}, {"salaryMin": True},
    {"salaryMin": "NaN"}, {"salaryMax": "Infinity"}, {"salaryMin": "0.001"},
    {"salaryMax": "10000000000000000"}, {"salaryMin": None}, {"currency": "USD"},
    {"currency": "rub"}, {"currency": None}, {"offerDescription": " "}, {"contactMethod": ""},
    {"status": "accepted"}, {"ownerId": 1},
])
def test_validation(invite_env, changes):
    (client, headers, _, engine), body, _ = invite_env
    assert client.post("/invitations", headers=headers[0], json=body | changes).status_code == 422
    assert records(engine, Invitation) == records(engine, AuditEvent) == []


def test_no_qualification_or_private_candidate_no_writes(invite_env):
    (client, headers, ids, engine), body, _ = invite_env
    response = client.post("/invitations", headers=headers[0], json=body)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "verified_qualification_unavailable"
    with Session(engine) as session, session.begin():
        session.get(User, ids[2]).is_verified = False
    assert client.post("/invitations", headers=headers[0], json=body).status_code == 404
    assert records(engine, Invitation) == records(engine, AuditEvent) == []


@pytest.mark.parametrize("condition", ["consent", "privacy", "role", "missing"])
def test_not_searchable(invite_env, monkeypatch, condition):
    (client, headers, ids, engine), body, _ = invite_env
    approve_for_test(monkeypatch)
    with Session(engine) as session, session.begin():
        if condition == "consent": session.scalar(select(Consent).where(Consent.kind == "publish_profile")).granted = False
        elif condition == "privacy": session.get(CandidateProfile, body["candidateId"]).privacy_settings = {"publish_profile": False}
        elif condition == "role": session.get(User, ids[2]).role = "employer"
        else: body = body | {"candidateId": 999999}
    assert client.post("/invitations", headers=headers[0], json=body).status_code == 404
    assert records(engine, Invitation) == records(engine, AuditEvent) == []


def test_rbac_ownership_and_missing(invite_env):
    (client, headers, _, engine), body, other = invite_env
    iid = seed_invitation(invite_env)
    assert client.post("/invitations", json=body).status_code == 401
    assert client.post("/invitations", headers=headers[2], json=body).status_code == 403
    assert client.post("/invitations", headers=headers[1], json=body).status_code == 404
    assert client.post("/invitations", headers=headers[0], json=body | {"companyId": 999999}).status_code == 404
    assert client.get(f"/invitations/{iid}", headers=headers[1]).status_code == 404
    assert client.get(f"/invitations/{iid}").status_code == 401
    for action in ("accept", "decline"):
        assert client.post(f"/invitations/{iid}/{action}", headers=headers[0]).status_code == 403
        assert client.post(f"/invitations/999999/{action}", headers=headers[2]).status_code == 404
    # A second candidate cannot read or act on the original recipient's invitation.
    from app.modules.auth.security import create_access_token
    with Session(engine) as session, session.begin():
        user = User(email="other@example.com", password_hash="fixture", role="candidate")
        session.add(user)
        session.flush()
        other_headers = {"Authorization": "Bearer " + create_access_token(user.id, user.role)}
    assert client.get(f"/invitations/{iid}", headers=other_headers).status_code == 404
    for action in ("accept", "decline"):
        assert client.post(f"/invitations/{iid}/{action}", headers=other_headers).status_code == 404
    assert records(engine, AuditEvent) == []


@pytest.mark.parametrize("view_first", [False, True])
@pytest.mark.parametrize("action", ["accept", "decline"])
def test_transitions_and_idempotence(invite_env, view_first, action):
    (client, headers, ids, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    url = f"/invitations/{iid}"
    assert client.get(url, headers=headers[0]).json()["status"] == "sent"
    assert records(engine, AuditEvent) == []
    if view_first:
        first = client.get(url, headers=headers[2])
        assert first.json()["status"] == "viewed"
        assert client.get(url, headers=headers[2]).json() == first.json()
        assert len(records(engine, AuditEvent)) == 1
    result = client.post(url + "/" + action, headers=headers[2])
    assert result.status_code == 200
    target = "accepted" if action == "accept" else "declined"
    assert result.json()["status"] == target
    assert client.post(url + "/" + action, headers=headers[2]).json() == result.json()
    opposite = "decline" if action == "accept" else "accept"
    assert client.post(url + "/" + opposite, headers=headers[2]).status_code == 409
    assert client.get(url, headers=headers[2]).json()["status"] == target
    events = records(engine, AuditEvent)
    assert len(events) == (2 if view_first else 1)
    assert all(e.user_id == ids[2] and e.created_at is not None for e in events)
    assert events[-1].payload == {"invitationId": iid, "from": "viewed" if view_first else "sent", "to": target}


def test_duplicate_concurrency_terminal_allows_new_and_other_company(invite_env, monkeypatch):
    (client, headers, _, engine), body, other = invite_env
    approve_for_test(monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post("/invitations", headers=headers[0], json=body), range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert len(records(engine, Invitation)) == len(records(engine, AuditEvent)) == 1
    iid = records(engine, Invitation)[0].id
    assert client.post("/invitations", headers=headers[1], json=body | {"companyId": other}).status_code == 201
    client.get(f"/invitations/{iid}", headers=headers[2])
    assert client.post("/invitations", headers=headers[0], json=body).status_code == 409
    assert client.post(f"/invitations/{iid}/decline", headers=headers[2]).status_code == 200
    assert client.post("/invitations", headers=headers[0], json=body).status_code == 201
    with Session(engine) as session:
        session.add(Invitation(company_id=body["companyId"], candidate_id=body["candidateId"], salary_from=1, salary_to=1))
        with pytest.raises(IntegrityError): session.commit()
        session.rollback()
        assert session.scalar(select(1)) == 1


def test_concurrent_terminal_actions(invite_env):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda action: client.post(f"/invitations/{iid}/{action}", headers=headers[2]), ["accept", "decline"]))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert len(records(engine, AuditEvent)) == 1


@pytest.mark.parametrize("action", ["create", "view", "accept", "decline"])
def test_audit_failure_rolls_back(invite_env, monkeypatch, action):
    (client, headers, _, engine), body, _ = invite_env
    approve_for_test(monkeypatch)
    iid = seed_invitation(invite_env) if action != "create" else None
    def reject_audit(session, *args):
        if any(isinstance(row, AuditEvent) for row in session.new):
            raise RuntimeError("Audit unavailable")
    event.listen(Session, "before_flush", reject_audit)
    try:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            if action == "create": client.post("/invitations", headers=headers[0], json=body)
            elif action == "view": client.get(f"/invitations/{iid}", headers=headers[2])
            else: client.post(f"/invitations/{iid}/{action}", headers=headers[2])
    finally:
        event.remove(Session, "before_flush", reject_audit)
    assert records(engine, AuditEvent) == []
    if iid is None: assert records(engine, Invitation) == []
    else: assert records(engine, Invitation)[0].status == "sent"


def test_contact_disclosure_privacy_and_no_list_leaks(invite_env):
    (client, headers, ids, engine), body, _ = invite_env
    iid = seed_invitation(invite_env)
    url = f"/invitations/{iid}"
    assert client.get(url, headers=headers[0]).json()["contacts"] is None
    client.post(url + "/accept", headers=headers[2])
    first = client.get(url, headers=headers[0])
    assert first.json()["contacts"] == {"email": "company2@example.com", "phone": "+79991234567"}
    assert first.headers["cache-control"] == "no-store"
    assert client.get(url, headers=headers[0]).json() == first.json()
    assert len(records(engine, ContactDisclosure)) == 1
    assert [e.action for e in records(engine, AuditEvent)] == ["invitation.accepted"]
    for actor in (0, 2):
        result = client.get("/invitations", headers=headers[actor])
        assert "company2@example.com" not in result.text and "+79991234567" not in result.text
        assert "contacts" not in result.text
    with Session(engine) as session, session.begin():
        session.get(CandidateProfile, body["candidateId"]).privacy_settings = {"show_contacts": False}
    assert client.get(url, headers=headers[0]).json()["contacts"] is None
    with Session(engine) as session, session.begin():
        session.get(CandidateProfile, body["candidateId"]).privacy_settings = {"show_contacts": True, "publish_profile": True}
        session.scalar(select(Consent).where(Consent.kind == "publish_profile")).granted = False
    assert client.get(url, headers=headers[0]).json()["contacts"] is None
    assert len(records(engine, AuditEvent)) == 1


def test_legacy_rejected_and_openapi(invite_env):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env, "rejected")
    result = client.get(f"/invitations/{iid}", headers=headers[2]).json()
    assert result["status"] == "declined" and result["currency"] is result["contactMethod"] is None
    assert records(engine, AuditEvent) == []
    schema = client.get("/openapi.json").json()["paths"]
    for path, methods in {"/invitations": ["post", "get"], "/invitations/{invitation_id}": ["get"],
                          "/invitations/{invitation_id}/accept": ["post"], "/invitations/{invitation_id}/decline": ["post"]}.items():
        for method in methods: assert schema[path][method]["security"] == [{"HTTPBearer": []}]


def test_exact_money_boundary_and_equal_range():
    from app.modules.invitations.schemas import InvitationCreate
    payload = {**BODY, "companyId": 1, "candidateId": 1}
    for amount in (1, "0.01", "9999999999999999.99"):
        result = InvitationCreate.model_validate(payload | {"salaryMin": amount, "salaryMax": amount})
        assert result.salaryMin == result.salaryMax == Decimal(str(amount))


@pytest.mark.parametrize("action", ["view", "accept"])
def test_concurrent_idempotent_actions(invite_env, action):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    def request(_):
        if action == "view": return client.get(f"/invitations/{iid}", headers=headers[2])
        return client.post(f"/invitations/{iid}/accept", headers=headers[2])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, range(2)))
    assert all(result.status_code == 200 for result in results)
    assert results[0].json() == results[1].json()
    assert len(records(engine, AuditEvent)) == 1
