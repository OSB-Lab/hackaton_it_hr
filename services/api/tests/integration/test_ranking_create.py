from copy import deepcopy
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session

from app.models import (CandidateProfile, Company, HiringNeed, User, TestAttempt as Attempt,
                        CompetencyScore, RecommendationSnapshot, FspLink, FspAchievement)
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved


def setup(env):
    client, headers, ids, engine = env
    for header in headers[:2]:
        assert client.patch("/me/candidate-profile", headers=header, json={
            "fullName": "secret@example.com", "phone": "+79991234567",
            "stack": ["made-up"], "consents": {"publication": True}}).status_code == 200
    with Session(engine) as session, session.begin():
        for uid in ids[:2]: session.get(User, uid).is_verified = True
        company = Company(user_id=ids[2], name="Employer")
        session.add(company)
        session.flush()
        need = HiringNeed(company_id=company.id, title="Backend", specialization="backend", min_grade="junior",
                          grade="middle", stack=["python", "sql"], optional_skills=["api"])
        session.add(need)
        session.flush()
        return f"/employer/needs/{need.id}/recommendations", need.id


def certify(env, actor, count):
    client, headers, _, engine = env
    response = client.post("/assessments/start", headers=headers[actor], json={"specialization": "backend", "grade": "junior"})
    assert response.status_code == 201
    aid = response.json()["id"]
    with Session(engine) as session:
        attempt = session.get(Attempt, aid)
        questions = next(v["questions"] for v in attempt.snapshot["blueprint"]["variants"] if v["id"] == attempt.variant)
        # Spread five wrong single-tag answers: python 2, sql 2, api 1.
        wrong = set([0, 4, 8, 1, 5][:18 - count])
        body = {"answers": [{"questionId": q["id"], "optionId": None if i in wrong else q["answerKey"]["optionId"]}
                            for i, q in enumerate(questions)]}
    assert client.post(f"/assessments/{aid}/submit", headers=headers[actor], json=body).status_code == 200
    return aid


def test_create_persist_replay_no_latest_attempt_or_seed_boost(env, approved):
    client, headers, ids, engine = env
    url, need_id = setup(env)
    first = certify(env, 0, 18)
    certify(env, 1, 13)
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        pid = profile.id
        session.add(Attempt(candidate_id=pid, test_id="later-unrelated", score=0, status="submitted", result={}))
        for score in session.scalars(select(CompetencyScore).where(CompetencyScore.candidate_id == pid)):
            score.score = 0  # Latest mutable cache must not replace certifying evidence.
        session.add(FspLink(candidate_id=pid, status="linked", fsp_id="seed", linked_at=datetime.now(timezone.utc)))
        session.add(FspAchievement(candidate_id=pid, discipline="seed", result="winner"))
    response = client.post(url, headers=headers[2])
    assert response.status_code == 200
    saved = response.json()
    assert len(saved["items"]) == 2
    top = saved["items"][0]
    assert top["candidate"]["id"] == pid
    assert top["score"] == 0.85 and top["rank"] == 1
    assert top["components"] == {"skillFit": 1, "assessmentStrength": 1, "fspBonus": 0}
    assert len(top["reasons"]) == 3
    assert saved["items"][1]["components"]["skillFit"] == pytest.approx(0.8)
    assert saved["items"][1]["score"] == pytest.approx(0.4 + 0.35 * 13 / 18)
    repeated = client.post(url, headers=headers[2])
    assert repeated.status_code == 200
    assert repeated.json()["items"] == saved["items"]
    assert repeated.json()["id"] != saved["id"]
    for word in ("secret@example.com", "+79991234567", "answerKey", "rubric", "optionId", "made-up"):
        assert word not in response.text
    with Session(engine) as session, session.begin():
        original = deepcopy(session.get(RecommendationSnapshot, saved["id"]).ordered_items)
        session.get(HiringNeed, need_id).stack = ["api"]
        session.get(Attempt, first).score = 0
    assert client.get(f"{url}/{saved['id']}", headers=headers[2]).json() == saved
    with Session(engine) as session:
        assert session.get(RecommendationSnapshot, saved["id"]).ordered_items == original


def test_demo_and_empty_cohort(env):
    client, headers, _, _ = env
    url, _ = setup(env)
    certify(env, 0, 18)  # Real DEMO submit; no fixture approval.
    response = client.post(url, headers=headers[2])
    assert response.status_code == 200 and response.json()["items"] == []
    assert client.get(f"{url}/{response.json()['id']}", headers=headers[2]).json() == response.json()


@pytest.mark.parametrize("gate", ["email", "publication", "privacy", "specialization", "grade", "proof"])
def test_filters_before_ranking(env, approved, gate):
    client, headers, ids, engine = env
    url, need = setup(env)
    aid = certify(env, 0, 18)
    if gate == "publication":
        client.patch("/me/candidate-profile", headers=headers[0], json={"consents": {"publication": False}})
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        if gate == "email": session.get(User, ids[0]).is_verified = False
        if gate == "privacy": profile.privacy_settings = {"publish_profile": False}
        if gate == "specialization":
            session.get(HiringNeed, need).specialization = "frontend"
            session.get(HiringNeed, need).stack = ["react"]
            session.get(HiringNeed, need).optional_skills = []
        if gate == "grade": session.get(HiringNeed, need).min_grade = "middle"
        if gate == "proof": session.get(Attempt, aid).content_status = "DEMO"
    response = client.post(url, headers=headers[2])
    assert response.status_code == 200 and response.json()["items"] == []


def test_snapshot_write_rollback(env, approved):
    client, headers, _, engine = env
    url, _ = setup(env)
    certify(env, 0, 18)
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO recommendation_items"):
            raise RuntimeError("forced write failure")
    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError): client.post(url, headers=headers[2])
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(RecommendationSnapshot)) == 0
