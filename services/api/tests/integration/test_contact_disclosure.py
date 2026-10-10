from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (AuditEvent, CandidateProfile, Company, Consent, ContactDisclosure, HiringNeed,
                        Invitation, RecommendationItem, RecommendationSnapshot, User)
from app.modules.auth import security
from app.modules.candidate.schemas import HiringCandidateDTO
from app.modules.candidate.service import hiring_profile
from app.modules.invitations import service
from conftest import alembic_config
from test_employer_company import company_env
from test_invitations import invite_env, records, seed_invitation
from test_invitation_migrations import legacy


def masked(response):
    assert response.status_code in (200, 404)
    for secret in ("company2@example.com", "+79991234567", '"email"', '"phone"'):
        assert secret not in response.text


def test_accept_grant_is_atomic_and_get_is_read_only(invite_env):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    url = f"/invitations/{iid}"
    masked(client.get(url, headers=headers[0]))
    assert records(engine, ContactDisclosure) == []
    accepted = client.post(url + "/accept", headers=headers[2])
    assert accepted.status_code == 200
    assert len(records(engine, ContactDisclosure)) == len(records(engine, AuditEvent)) == 1
    grant = records(engine, ContactDisclosure)[0]
    assert grant.invitation_id == iid and grant.revealed_at is not None
    events = [(e.id, e.action, e.payload, e.created_at) for e in records(engine, AuditEvent)]
    assert events[0][1] == "invitation.accepted"
    for _ in range(2):
        assert client.post(url + "/accept", headers=headers[2]).json() == accepted.json()
        assert client.get(url, headers=headers[0]).json()["contacts"]["email"] == "company2@example.com"
    assert [(e.id, e.action, e.payload, e.created_at) for e in records(engine, AuditEvent)] == events
    assert len(records(engine, ContactDisclosure)) == 1
    with Session(engine) as session:
        session.add(ContactDisclosure(invitation_id=iid))
        with pytest.raises(IntegrityError) as exc: session.commit()
        assert exc.value.orig.sqlstate == "23505"
        session.rollback()
        assert session.scalar(select(ContactDisclosure.id)) == grant.id
    masked(client.get(url, headers=headers[2]))  # Recipient gets no employer contact projection.


@pytest.mark.parametrize("state", ["sent", "viewed", "rejected", "accepted"])
def test_legacy_without_grant_never_auto_discloses_or_backfills(invite_env, state):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env, state)
    for _ in range(2): masked(client.get(f"/invitations/{iid}", headers=headers[0]))
    if state == "accepted":
        assert client.post(f"/invitations/{iid}/accept", headers=headers[2]).status_code == 200
        masked(client.get(f"/invitations/{iid}", headers=headers[0]))
    assert records(engine, ContactDisclosure) == records(engine, AuditEvent) == []


def test_decline_never_creates_disclosure(invite_env):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    for _ in range(2): assert client.post(f"/invitations/{iid}/decline", headers=headers[2]).status_code == 200
    masked(client.get(f"/invitations/{iid}", headers=headers[0]))
    assert client.post(f"/invitations/{iid}/accept", headers=headers[2]).status_code == 409
    assert records(engine, ContactDisclosure) == []
    assert len(records(engine, AuditEvent)) == 1


@pytest.mark.parametrize("actions", [("accept", "accept"), ("accept", "decline")])
def test_concurrent_actions_keep_one_grant(invite_env, actions):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda action: client.post(f"/invitations/{iid}/{action}", headers=headers[2]), actions))
    assert sorted(r.status_code for r in responses) == ([200, 200] if actions[0] == actions[1] else [200, 409])
    row = records(engine, Invitation)[0]
    assert len(records(engine, ContactDisclosure)) == (1 if row.status == "accepted" else 0)
    assert len(records(engine, AuditEvent)) == 1


@pytest.mark.parametrize("failure", ["disclosure", "audit"])
def test_accept_rollback_covers_disclosure_status_audit(invite_env, monkeypatch, failure):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env)
    def reject_disclosure(session, *args):
        if any(isinstance(row, ContactDisclosure) for row in session.new):
            raise RuntimeError("Disclosure unavailable")
    if failure == "audit":
        def reject_audit(session, *args):
            session.flush()  # Prove even an already inserted grant is rolled back.
            assert session.scalar(select(ContactDisclosure.id)) is not None
            raise RuntimeError("Audit unavailable")
        monkeypatch.setattr(service, "audit", reject_audit)
    else: event.listen(Session, "before_flush", reject_disclosure)
    try:
        with pytest.raises(RuntimeError, match="unavailable"):
            client.post(f"/invitations/{iid}/accept", headers=headers[2])
    finally:
        if failure == "disclosure": event.remove(Session, "before_flush", reject_disclosure)
    assert records(engine, Invitation)[0].status == "sent"
    assert records(engine, ContactDisclosure) == records(engine, AuditEvent) == []


def test_origin_company_only_and_no_leaks_across_employer_surfaces(invite_env):
    (client, headers, ids, engine), body, other_company = invite_env
    iid = seed_invitation(invite_env)
    with Session(engine) as session, session.begin():
        # Other employer has their own accepted invitation but NO grant.
        second = Invitation(company_id=other_company, candidate_id=body["candidateId"],
                            salary_from=100, salary_to=200, status="accepted")
        session.add(second)
        snapshots = []
        for company in (body["companyId"], other_company):
            need = HiringNeed(company_id=company)
            session.add(need)
            session.flush()
            snapshot = RecommendationSnapshot(need_id=need.id)
            session.add(snapshot)
            session.flush()
            session.add(RecommendationItem(snapshot_id=snapshot.id, candidate_id=body["candidateId"], score=1, rank=1))
            snapshots.append((need.id, snapshot.id))
        session.flush()
        second_id = second.id
    for accepted in (False, True):
        if accepted: client.post(f"/invitations/{iid}/accept", headers=headers[2])
        foreign = client.get(f"/invitations/{iid}", headers=headers[1])
        assert foreign.status_code == 404
        masked(foreign)
        masked(client.get(f"/invitations/{second_id}", headers=headers[1]))
        for actor in (0, 1):
            masked(client.get("/invitations", headers=headers[actor]))
            need, snapshot = snapshots[actor]
            for suffix in ("", "/items"):
                masked(client.get(f"/employer/needs/{need}/recommendations/{snapshot}{suffix}", headers=headers[actor]))
        with Session(engine) as session:
            candidate = hiring_profile(session, ids[2])
            assert isinstance(candidate, HiringCandidateDTO) and candidate.contacts is None
            for secret in ('"email"', '"phone"', "company2@example.com", "+79991234567"):
                assert secret not in candidate.model_dump_json()
    assert client.get(f"/invitations/{iid}", headers=headers[0]).json()["contacts"] is not None
    # Grant from the first invitation does not authorize another invitation, even within the same company.
    with Session(engine) as session, session.begin():
        third = Invitation(company_id=body["companyId"], candidate_id=body["candidateId"],
                           salary_from=100, salary_to=200, status="accepted")
        session.add(third)
        session.flush()
        third_id = third.id
    masked(client.get(f"/invitations/{third_id}", headers=headers[0]))


def test_existing_disclosure_migrates_unchanged(migration_connection):
    c = migration_connection
    config = legacy(c)
    invitation = c.scalar(text("SELECT id FROM invitations WHERE status='accepted'"))
    c.execute(text("INSERT INTO contact_disclosures(invitation_id) VALUES (:id)"), {"id": invitation})
    c.execute(text("INSERT INTO audit_events(action,payload) VALUES ('invitation.contacts_disclosed','{}')"))
    before = [dict(row) for row in c.execute(text("SELECT * FROM contact_disclosures")).mappings()]
    audits = [dict(row) for row in c.execute(text("SELECT * FROM audit_events")).mappings()]
    c.commit()
    command.upgrade(config, "head")
    assert [dict(row) for row in c.execute(text("SELECT * FROM contact_disclosures")).mappings()] == before
    assert [dict(row) for row in c.execute(text("SELECT * FROM audit_events")).mappings()] == audits
    assert any(constraint["column_names"] == ["invitation_id"] for constraint in inspect(c).get_unique_constraints("contact_disclosures"))
    assert any(fk["constrained_columns"] == ["invitation_id"] and fk["referred_table"] == "invitations"
               for fk in inspect(c).get_foreign_keys("contact_disclosures"))
    c.commit()
    command.check(config)


@pytest.mark.parametrize("state", ["sent", "viewed", "rejected"])
def test_nonaccepted_never_discloses_even_with_historical_grant(invite_env, state):
    (client, headers, _, engine), _, _ = invite_env
    iid = seed_invitation(invite_env, state)
    # Deliberately inconsistent historical fixture: a grant alone is insufficient.
    with Session(engine) as session, session.begin():
        session.add(ContactDisclosure(invitation_id=iid))
    response = client.get(f"/invitations/{iid}", headers=headers[0])
    masked(response)
    assert response.json()["contacts"] is None
    assert response.headers["cache-control"] == "no-store"
    assert records(engine, AuditEvent) == []


def test_candidate_acceptance_and_disclosure_do_not_cross_recipient(invite_env):
    (client, headers, _, engine), body, _ = invite_env
    first = seed_invitation(invite_env)
    with Session(engine) as session, session.begin():
        user = User(email="second-candidate@fixture.test", password_hash="fixture",
                    role="candidate", is_verified=True)
        session.add(user)
        session.flush()
        profile = CandidateProfile(user_id=user.id, phone="+79997654321",
                                   privacy_settings={"publish_profile": True, "show_contacts": True})
        session.add(profile)
        session.add_all([Consent(user_id=user.id, kind=kind, granted=True)
                         for kind in ("privacy", "publish_profile")])
        session.flush()
        second = Invitation(company_id=body["companyId"], candidate_id=profile.id,
                            salary_from=100, salary_to=200, status="sent")
        session.add(second)
        session.flush()
        second_id = second.id
        second_headers = {"Authorization": "Bearer " + security.create_access_token(user.id, user.role)}
    for invitation_id, actor in ((first, second_headers), (second_id, headers[2])):
        for method, suffix in (("get", ""), ("post", "/accept"), ("post", "/decline")):
            response = getattr(client, method)(f"/invitations/{invitation_id}{suffix}", headers=actor)
            assert response.status_code == 404
            assert all(secret not in response.text for secret in
                       ("company2@example.com", "second-candidate@fixture.test", "+79997654321", "+79991234567"))
    assert records(engine, ContactDisclosure) == records(engine, AuditEvent) == []
    viewed = client.get(f"/invitations/{first}", headers=headers[2])
    assert viewed.json()["status"] == "viewed" and viewed.json()["contacts"] is None
    masked(client.get(f"/invitations/{first}", headers=headers[0]))
    assert records(engine, ContactDisclosure) == []
    assert client.post(f"/invitations/{first}/accept", headers=headers[2]).status_code == 200
    own = client.get(f"/invitations/{first}", headers=headers[0])
    assert own.json()["contacts"] == {"email": "company2@example.com", "phone": "+79991234567"}
    assert "second-candidate@fixture.test" not in own.text and "+79997654321" not in own.text
    other = client.get(f"/invitations/{second_id}", headers=headers[0])
    assert other.json()["contacts"] is None
    assert "second-candidate@fixture.test" not in other.text and "+79997654321" not in other.text
    assert client.post(f"/invitations/{second_id}/accept", headers=second_headers).status_code == 200
    second_detail = client.get(f"/invitations/{second_id}", headers=headers[0])
    assert second_detail.json()["contacts"] == {"email": "second-candidate@fixture.test", "phone": "+79997654321"}
    assert "company2@example.com" not in second_detail.text and "+79991234567" not in second_detail.text
    assert {row.invitation_id for row in records(engine, ContactDisclosure)} == {first, second_id}
    for actor in (headers[0], headers[1], headers[2], second_headers):
        listing = client.get("/invitations", headers=actor)
        assert listing.status_code == 200
        assert all(secret not in listing.text for secret in
                   ('"email"', '"phone"', "company2@example.com", "second-candidate@fixture.test", "+79997654321", "+79991234567"))
