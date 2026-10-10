import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, CandidateProfile, Consent, ContactDisclosure, User
from test_candidate_profile import env, URL
from test_employer_company import company_env
from test_invitations import invite_env, records, seed_invitation


def test_show_contacts_default_owner_patch_and_preserved_json(env):
    client, headers, ids, engine = env
    assert client.get(URL, headers=headers[0]).json()["privacy"] == {"showContacts": False}
    assert client.get(URL, headers=headers[1]).json()["privacy"] == {"showContacts": False}
    result = client.patch(URL, headers=headers[0], json={"privacy": {"showContacts": True}})
    assert result.status_code == 200 and result.json()["privacy"] == {"showContacts": True}
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        profile.privacy_settings = {**profile.privacy_settings, "publish_profile": False, "custom": {"preserve": 1}}
    for payload in ({}, {"privacy": {}}, {"fullName": "Name"}):
        assert client.patch(URL, headers=headers[0], json=payload).json()["privacy"]["showContacts"] is True
    assert client.get(URL, headers=headers[1]).json()["privacy"]["showContacts"] is False
    result = client.patch(URL, headers=headers[0], json={"privacy": {"showContacts": False}, "consents": {"publication": True}})
    assert result.json()["privacy"]["showContacts"] is False
    with Session(engine) as session:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        assert profile.privacy_settings == {"show_contacts": False, "publish_profile": True, "custom": {"preserve": 1}}
    assert client.patch(URL, headers=headers[0], json={"privacy": {"showContacts": True}, "userId": ids[1]}).status_code == 422


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false", [], {}])
def test_strict_boolean(env, value):
    client, headers, _, _ = env
    assert client.patch(URL, headers=headers[0], json={"privacy": {"showContacts": value}}).status_code == 422
    assert client.get(URL, headers=headers[0]).json()["privacy"]["showContacts"] is False


@pytest.mark.parametrize("method", ["get", "patch"])
@pytest.mark.parametrize("actor,status", [(None, 401), (2, 403)])
def test_privacy_rbac(env, method, actor, status):
    client, headers, _, _ = env
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    if method == "patch": kwargs["json"] = {"privacy": {"showContacts": True}}
    assert getattr(client, method)(URL, **kwargs).status_code == status


@pytest.mark.parametrize("revocation", ["show_contacts", "publication", "processing", "email", "publish_profile", "missing_processing", "missing_publish_profile"])
def test_contact_permissions_rechecked_history_preserved(invite_env, revocation):
    (client, headers, ids, engine), body, _ = invite_env
    iid = seed_invitation(invite_env)
    detail = f"/invitations/{iid}"
    client.patch(URL, headers=headers[2], json={"privacy": {"showContacts": False}})
    assert client.post(detail + "/accept", headers=headers[2]).status_code == 200
    assert client.get(detail, headers=headers[0]).json()["contacts"] is None
    assert len(records(engine, AuditEvent)) == len(records(engine, ContactDisclosure)) == 1
    allowed = client.patch(URL, headers=headers[2], json={"privacy": {"showContacts": True},
                                  "consents": {"processing": True, "publication": True}})
    assert allowed.status_code == 200
    result = client.get(detail, headers=headers[0])
    assert result.json()["contacts"] == {"email": "company2@example.com", "phone": "+79991234567"}
    audit_before = [(r.id, r.action, r.payload, r.created_at) for r in records(engine, AuditEvent)]
    disclosure_before = [(r.id, r.invitation_id, r.revealed_at) for r in records(engine, ContactDisclosure)]
    if revocation == "show_contacts":
        client.patch(URL, headers=headers[2], json={"privacy": {"showContacts": False}})
    elif revocation in ("publication", "processing"):
        client.patch(URL, headers=headers[2], json={"consents": {revocation: False}})
    else:
        with Session(engine) as session, session.begin():
            if revocation == "email": session.get(User, ids[2]).is_verified = False
            elif revocation == "missing_processing":
                session.delete(session.scalar(select(Consent).where(Consent.user_id == ids[2], Consent.kind == "privacy")))
            else:
                profile = session.get(CandidateProfile, body["candidateId"])
                values = dict(profile.privacy_settings)
                if revocation == "publish_profile": values["publish_profile"] = False
                else: values.pop("publish_profile")
                profile.privacy_settings = values
    for _ in range(2):
        response = client.get(detail, headers=headers[0])
        assert response.json()["contacts"] is None
        assert "company2@example.com" not in response.text and "+79991234567" not in response.text
    assert [(r.id, r.action, r.payload, r.created_at) for r in records(engine, AuditEvent)] == audit_before
    assert [(r.id, r.invitation_id, r.revealed_at) for r in records(engine, ContactDisclosure)] == disclosure_before
