from copy import deepcopy

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, TestAttempt as Attempt, User, Company, HiringNeed
from app.modules.recommendations import ranking
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved
from test_ranking_create import setup, certify


@pytest.mark.parametrize("mutation", [None, "missing", "zero", "wrong-id", "demo", "self-declared"])
def test_formal_gate_and_read_only_api(env, approved, monkeypatch, mutation):
    client, headers, ids, engine = env
    ranking_url, need = setup(env)
    aid = certify(env, 0, 18)
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        pid = profile.id
        attempt = session.get(Attempt, aid)
        result = deepcopy(attempt.result)
        if mutation == "missing": result["evidenceCounts"].pop("python")
        if mutation == "zero": result["evidenceCounts"]["python"] = 0
        if mutation == "wrong-id": result["evidenceCounts"]["Python"] = result["evidenceCounts"].pop("python")
        if mutation == "demo": attempt.content_status = "DEMO"
        if mutation == "self-declared":
            profile.stack = ["python", "sql"]
            profile.verified_attempt_id = None
        attempt.result = result
    url = f"/employer/needs/{need}/eligibility/{pid}"
    writes = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(url, headers=headers[2])
        assert client.get(url, headers=headers[2]).json() == response.json()
        assert not writes
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    if mutation in {"demo", "self-declared"}:
        assert response.status_code == 404
        assert response.json() == client.get(f"/employer/needs/{need}/eligibility/999999", headers=headers[2]).json()
    else:
        assert response.status_code == 200
        assert response.json()["eligible"] == (mutation is None)
        if mutation:
            assert response.json()["missingRequiredSkills"] == ["python"]
    for secret in ("secret@example.com", "+79991234567", "answerKey", "evidenceCounts", "snapshot", "subscores"):
        assert secret not in response.text
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers[0]).status_code == 403
    assert client.get(url.replace(f"/{need}/", "/999999/"), headers=headers[2]).status_code == 404
    original = ranking.calculate
    calls = []
    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(ranking, "calculate", spy)
    response = client.post(ranking_url, headers=headers[2])
    assert response.status_code == 200
    assert len(calls) == (1 if mutation is None else 0)
    if mutation is None:
        assert response.json()["items"][0]["score"] == 0.85


@pytest.mark.parametrize("gate", ["email", "publication", "privacy", "specialization", "grade"])
def test_api_visibility_and_safe_reasons(env, approved, gate):
    client, headers, ids, engine = env
    _, need_id = setup(env)
    certify(env, 0, 18)
    if gate == "publication":
        client.patch("/me/candidate-profile", headers=headers[0], json={"consents": {"publication": False}})
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        pid = profile.id
        need = session.get(HiringNeed, need_id)
        if gate == "email": session.get(User, ids[0]).is_verified = False
        if gate == "privacy": profile.privacy_settings = {"publish_profile": False}
        if gate == "specialization":
            need.specialization, need.stack, need.optional_skills = "frontend", [], []
        if gate == "grade": need.min_grade = "middle"
        # Existing need owned by another employer, not merely a missing ID.
        other = User(email="other-employer@example.test", password_hash="unused", role="employer")
        session.add(other)
        session.flush()
        company = Company(user_id=other.id, name="Other")
        session.add(company)
        session.flush()
        foreign = HiringNeed(company_id=company.id, title="Foreign")
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id
    response = client.get(f"/employer/needs/{need_id}/eligibility/{pid}", headers=headers[2])
    if gate in {"email", "publication", "privacy"}:
        assert response.status_code == 404 and response.json() == {"detail": "Candidate not found"}
    else:
        assert response.status_code == 200 and response.json()["eligible"] is False
        assert response.json()["reasonCodes"] == [
            "SPECIALIZATION_MISMATCH" if gate == "specialization" else "GRADE_BELOW_MINIMUM"]
    assert client.get(f"/employer/needs/{foreign_id}/eligibility/{pid}", headers=headers[2]).status_code == 404
