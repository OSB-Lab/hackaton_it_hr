"""End-to-end MVP scenario over real HTTP APIs (TEST-ONLY approved content).

Steps (audit trail of the final QA run):
 1. candidate registration
 2. email verification
 3. login
 4. candidate profile + consents + contact privacy
 5. assessment start
 6. assessment submit (all answers correct)
 7. employer registration/login
 8. employer company + hiring need
 9. formal eligibility + RankScore snapshot (positive cohort)
10. invitation sent by the employer
11. candidate accepts; employer receives disclosed contacts

The DEMO catalog is asserted separately: it must never certify and must yield an
empty cohort. The positive path runs only against a TEST-ONLY APPROVED copy
created by the shared ``approved`` fixture; nothing here touches published data.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User
from test_candidate_profile import env as assessment_env  # noqa: F401
from test_assessment_v3_lifecycle import approved  # noqa: F401  (TEST-ONLY fixture)

PASSWORD = "DemoPass12345!"  # local test fixture only, never a real credential
CANDIDATE_EMAIL = "e2e-candidate@fsp-qa.dev"
EMPLOYER_EMAIL = "e2e-employer@fsp-qa.dev"


def _register(client, email, role):
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD, "role": role})
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, email):
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _verify(client, monkeypatch, email):
    captured = {}
    from app.modules.auth import router as auth_router

    def capture(address, token):
        captured["token"] = token
        captured["address"] = address
        return True

    monkeypatch.setattr(auth_router, "send_verification_email", capture)
    _register(client, email, "candidate")
    assert captured.get("address") == email
    response = client.post("/auth/verify-email", json={"token": captured["token"]})
    assert response.status_code == 200, response.text


def test_full_mvp_scenario_with_test_only_approved_content(assessment_env, approved, monkeypatch):  # noqa: F811
    client, _headers, _ids, engine = assessment_env

    # 1-3. candidate registration, email verification, login
    _verify(client, monkeypatch, CANDIDATE_EMAIL)
    candidate = _login(client, CANDIDATE_EMAIL)

    # 4. profile, consents and contact privacy
    profile = client.patch("/me/candidate-profile", headers=candidate, json={
        "fullName": "E2E Candidate", "specialization": "backend", "stack": ["Python"],
        "experienceMonths": 24, "consents": {"processing": True, "publication": True},
        "privacy": {"showContacts": True}})
    assert profile.status_code == 200, profile.text

    # 5. assessment start
    started = client.post("/assessments/start", headers=candidate,
                          json={"specialization": "backend", "grade": "junior"})
    assert started.status_code == 201, started.text
    attempt_id = started.json()["id"]

    # 6. submit every answer correctly
    from app.models import TestAttempt
    with Session(engine) as session:
        attempt = session.get(TestAttempt, attempt_id)
        questions = next(v["questions"] for v in attempt.snapshot["blueprint"]["variants"]
                         if v["id"] == attempt.variant)
        candidate_id = attempt.candidate_id
    answers = [{"questionId": q["id"], "optionId": q["answerKey"]["optionId"]} for q in questions]
    submitted = client.post(f"/assessments/{attempt_id}/submit", headers=candidate,
                            json={"answers": answers})
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()["result"]
    assert result["outcome"] == "high" and result["verifiedGrade"] == "junior"
    assert result["verifiedSpecialization"] == "backend"

    # 7. employer registration and login
    _register(client, EMPLOYER_EMAIL, "employer")
    employer = _login(client, EMPLOYER_EMAIL)

    # 8. company and hiring need
    company = client.put("/employer/company", headers=employer,
                         json={"name": "E2E Employer", "description": None, "contacts": None})
    assert company.status_code == 200, company.text
    company_id = company.json()["id"]
    need = client.post("/employer/needs", headers=employer, json={
        "title": "E2E Backend Junior", "specialization": "backend", "minGrade": "junior",
        "targetGrade": "junior", "requiredSkills": ["python", "sql"], "optionalSkills": []})
    assert need.status_code == 201, need.text
    need_id = need.json()["id"]

    # 9. formal eligibility + RankScore snapshot
    eligibility = client.get(f"/employer/needs/{need_id}/eligibility/{candidate_id}", headers=employer)
    assert eligibility.status_code == 200, eligibility.text
    assert eligibility.json()["eligible"] is True, eligibility.text
    snapshot = client.post(f"/employer/needs/{need_id}/recommendations", headers=employer)
    assert snapshot.status_code == 200, snapshot.text
    items = snapshot.json()["items"]
    assert [item["candidate"]["id"] for item in items] == [candidate_id], items
    assert items[0]["score"] > 0 and items[0]["rank"] == 1

    # 10. invitation with a salary range
    invitation = client.post("/invitations", headers=employer, json={
        "companyId": company_id, "candidateId": candidate_id,
        "offerDescription": "Backend role", "contactMethod": "email",
        "salaryMin": "120000.00", "salaryMax": "180000.00", "currency": "RUB"})
    assert invitation.status_code == 201, invitation.text
    invitation_id = invitation.json()["id"]

    # 11. candidate sees it, accepts, employer receives contacts
    inbox = client.get("/invitations", headers=candidate)
    assert inbox.status_code == 200 and [i["id"] for i in inbox.json()] == [invitation_id]
    detail = client.get(f"/invitations/{invitation_id}", headers=candidate)
    assert detail.status_code == 200 and detail.json()["contacts"] is None
    accepted = client.post(f"/invitations/{invitation_id}/accept", headers=candidate)
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    disclosed = client.get(f"/invitations/{invitation_id}", headers=employer)
    assert disclosed.status_code == 200
    assert disclosed.json()["contacts"] == {"email": CANDIDATE_EMAIL, "phone": None}


def test_demo_catalog_never_certifies_and_yields_empty_cohort(assessment_env):  # noqa: F811
    """The shipped DEMO content must stay honest: no qualification, no candidates."""
    client, headers, ids, engine = assessment_env
    assert client.patch("/me/candidate-profile", headers=headers[0], json={
        "specialization": "backend", "consents": {"publication": True},
        "privacy": {"showContacts": True}}).status_code == 200
    with Session(engine) as session, session.begin():
        session.get(User, ids[0]).is_verified = True
    started = client.post("/assessments/start", headers=headers[0],
                          json={"specialization": "backend", "grade": "junior"})
    assert started.status_code == 201
    from app.models import TestAttempt
    with Session(engine) as session:
        attempt = session.get(TestAttempt, started.json()["id"])
        questions = next(v["questions"] for v in attempt.snapshot["blueprint"]["variants"]
                         if v["id"] == attempt.variant)
    answers = [{"questionId": q["id"], "optionId": q["answerKey"]["optionId"]} for q in questions]
    result = client.post(f"/assessments/{started.json()['id']}/submit", headers=headers[0],
                         json={"answers": answers}).json()["result"]
    assert result["outcome"] == "high" and result["verifiedGrade"] is None

    assert client.put("/employer/company", headers=headers[2],
                      json={"name": "Demo Employer", "description": None, "contacts": None}).status_code == 200
    need = client.post("/employer/needs", headers=headers[2], json={
        "title": "DEMO backend junior", "specialization": "backend", "minGrade": "junior",
        "targetGrade": "junior", "requiredSkills": ["python"], "optionalSkills": []})
    assert need.status_code == 201
    snapshot = client.post(f"/employer/needs/{need.json()['id']}/recommendations", headers=headers[2])
    assert snapshot.status_code == 200 and snapshot.json()["items"] == []


