import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.models import CandidateProfile, CompetencyScore, TestAttempt as Attempt, User, Consent, HiringNeed
from app.modules.assessments import service
from app.modules.assessments.qualification import qualification, matches_need
from app.modules.assessments.schemas import SubmitRequest
from app.modules.catalog.repository import CatalogRepository, DATA_ROOT, decode
from app.modules.recommendations.service import eligible_for_ranking, has_verified_qualification
from test_candidate_profile import env as assessment_env
from test_assessments import prepare, START, BODY
from conftest import alembic_config


@pytest.fixture
def approved(monkeypatch, tmp_path):
    """Isolated copy of the published catalog; content certifies on score alone."""
    root = tmp_path / "approved"
    shutil.copytree(DATA_ROOT, root)
    monkeypatch.setattr(service, "CatalogRepository", lambda: CatalogRepository(root))
    return root


def start(env, grade="junior"):
    client, headers, _, _ = env
    return client.post(START, headers=headers[0], json={**BODY, "grade": grade})


def submit(env, aid, fail=False):
    client, headers, _, engine = env
    with Session(engine) as session:
        row = session.get(Attempt, aid)
        qs = next(v["questions"] for v in row.snapshot["blueprint"]["variants"] if v["id"] == row.variant)
        body = {"answers": [{"questionId": q["id"], "optionId": None if fail else q["answerKey"]["optionId"]} for q in qs]}
    return client.post(f"/assessments/{aid}/submit", headers=headers[0], json=body)


def test_approved_transitions_cooldown_evidence_and_privacy(assessment_env, approved):
    client, headers, ids, engine = prepare(assessment_env)
    first = start(assessment_env).json()
    response = submit(assessment_env, first["id"])
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["verifiedGrade"] == "junior" and result["verifiedSpecialization"] == "backend"
    assert result["retestTargetGrade"] == "middle"
    for grade in ("junior", "middle"):
        blocked = start(assessment_env, grade)
        assert blocked.status_code == 409 and "retest_available_at" in blocked.json()["detail"]
    assert start(assessment_env, "senior").status_code == 422
    assert client.post(START, headers=headers[0], json={"specialization": "frontend", "grade": "junior"}).status_code == 409
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        pid = profile.id
        assert qualification(session, pid)
        assert profile.grade is None  # legacy/self description stays untouched
        scores = session.scalars(select(CompetencyScore)).all()
        assert len(scores) == 4
        assert {s.source for s in scores} == {"test", "assessment_diagnostic"}
        assert all(s.attempt_id == first["id"] for s in scores)
        assert not eligible_for_ranking(session, pid)  # publication is independently required
        session.get(User, ids[0]).is_verified = True
        session.add(Consent(user_id=ids[0], kind="publish_profile", granted=True))
        profile.privacy_settings = {"publish_profile": True}
        profile.last_grade_change_at -= timedelta(days=91)
        original_date = profile.last_grade_change_at
    with Session(engine) as session:
        assert eligible_for_ranking(session, pid)
        assert matches_need(session, pid, HiringNeed(specialization="backend", min_grade="junior"))
        assert not matches_need(session, pid, HiringNeed(specialization="frontend", min_grade="junior"))
        assert not matches_need(session, pid, HiringNeed(specialization="backend", min_grade="middle"))
    failed = start(assessment_env, "middle").json()
    result = submit(assessment_env, failed["id"], True).json()["result"]
    assert result["verifiedGrade"] == "junior" and result["retestOffer"] is None
    with Session(engine) as session:
        assert session.get(CandidateProfile, pid).last_grade_change_at == original_date
    promoted = start(assessment_env, "middle")
    assert promoted.status_code == 201
    assert promoted.json()["assessment"]["variant"] != failed["assessment"]["variant"]
    response = submit(assessment_env, promoted.json()["id"])
    assert response.json()["result"]["verifiedGrade"] == "middle"
    # Idempotent response and original snapshot survive a repeat with no answers.
    assert client.post(f'/assessments/{promoted.json()["id"]}/submit', headers=headers[0], json={"answers": []}).json() == response.json()
    with Session(engine) as session:
        assert matches_need(session, pid, HiringNeed(specialization="backend", min_grade="middle"))


def test_lower_retest_after_initial_fail(assessment_env, approved):
    prepare(assessment_env)
    first = start(assessment_env, "middle").json()
    result = submit(assessment_env, first["id"], True).json()["result"]
    assert result["retestOffer"] == "lower_retest_offered" and result["retestTargetGrade"] == "junior"
    assert result["retestAvailableAt"] is None
    assert start(assessment_env, "junior").status_code == 201


def test_atomic_and_concurrent_submit(assessment_env, approved, monkeypatch):
    client, headers, ids, engine = prepare(assessment_env)
    first = start(assessment_env).json()
    original = service.apply_result
    def broken(*args):
        original(*args)
        args[0].flush()
        raise RuntimeError("forced qualification write failure")
    monkeypatch.setattr(service, "apply_result", broken)
    with pytest.raises(RuntimeError): submit(assessment_env, first["id"])
    with Session(engine) as session:
        assert session.get(Attempt, first["id"]).status == "active"
        assert session.scalar(select(func.count()).select_from(CompetencyScore)) == 0
        assert session.scalar(select(CandidateProfile.verified_grade)) is None
    monkeypatch.setattr(service, "apply_result", original)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(assessment_env, first["id"]), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json() == responses[1].json()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CompetencyScore)) == 4


def test_migration_preserves_legacy_and_does_not_verify(migration_connection):
    c = migration_connection
    cfg = alembic_config(c)
    command.upgrade(cfg, "0009")
    uid = c.scalar(text("INSERT INTO users(email,password_hash,role) VALUES ('v3@fixture.test','fixture','candidate') RETURNING id"))
    pid = c.scalar(text("INSERT INTO candidate_profiles(user_id,grade) VALUES (:u,'senior') RETURNING id"), {"u": uid})
    c.execute(text("INSERT INTO test_attempts(candidate_id,test_id,answers,score,grade) VALUES (:p,'seed','[1,2]',100,'senior')"), {"p": pid})
    before = dict(c.execute(text("SELECT * FROM test_attempts")).mappings().one())
    c.commit()
    command.upgrade(cfg, "head")
    after = dict(c.execute(text("SELECT * FROM test_attempts")).mappings().one())
    before.pop("content_status", None)  # 0012 drops the demo/real status column
    assert after == before
    assert tuple(c.execute(text("SELECT verified_grade,verified_specialization,verified_attempt_id,last_grade_change_at FROM candidate_profiles")).one()) == (None, None, None, None)
    c.commit()
    command.check(cfg)


def test_v3_snapshot_owner_active_switch(assessment_env, monkeypatch):
    client, headers, ids, engine = prepare(assessment_env)
    first = start(assessment_env).json()
    def unavailable():
        raise AssertionError("Existing snapshot must not reload active blueprint")
    monkeypatch.setattr(service, "CatalogRepository", unavailable)
    assert start(assessment_env).json() == first
    path = f'/assessments/{first["id"]}'
    assert client.get(path, headers=headers[0]).json() == first
    assert client.get(path, headers=headers[1]).status_code == 404
    assert client.get(path, headers=headers[2]).status_code == 403
    assert client.get(path).status_code == 401
    assert submit(assessment_env, first["id"]).status_code == 200


def test_real_qualification_unlocks_invitation_and_revocation_still_blocks(assessment_env, approved):
    from app.models import Company, Invitation, AuditEvent, RecommendationSnapshot, RecommendationItem
    client, headers, ids, engine = prepare(assessment_env)
    with Session(engine) as session, session.begin():
        company = Company(user_id=ids[2], name="Origin employer")
        session.add(company)
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        session.get(User, ids[0]).is_verified = True
        profile.privacy_settings = {"publish_profile": True}
        session.add(Consent(user_id=ids[0], kind="publish_profile", granted=True))
        session.flush()
        payload = {"companyId": company.id, "candidateId": profile.id, "offerDescription": "Backend",
                   "contactMethod": "email", "salaryMin": "100", "salaryMax": "200"}
    assert client.post("/invitations", headers=headers[2], json=payload).status_code == 503
    aid = start(assessment_env).json()["id"]
    assert submit(assessment_env, aid).json()["result"]["verifiedGrade"] == "junior"
    created = client.post("/invitations", headers=headers[2], json=payload)
    assert created.status_code == 201 and "contacts" not in created.json()
    with Session(engine) as session, session.begin():
        need = HiringNeed(company_id=payload["companyId"], title="Fixture", specialization="backend", min_grade="junior")
        session.add(need)
        session.flush()
        snapshot = RecommendationSnapshot(need_id=need.id)
        session.add(snapshot)
        session.flush()
        session.add(RecommendationItem(snapshot_id=snapshot.id, candidate_id=payload["candidateId"], rank=3, score=42))
        path = f"/employer/needs/{need.id}/recommendations/{snapshot.id}/items"
    visible = client.get(path, headers=headers[2], params={"grade": "junior"})
    assert visible.status_code == 200
    item = visible.json()["items"][0]
    assert (item["candidate"]["grade"], item["rank"], item["score"]) == ("junior", 3, 42)
    assert client.get(path, headers=headers[2], params={"grade": "middle"}).json()["items"] == []
    assert all(secret not in visible.text for secret in ("email", "phone", "answerKey", "rubric"))
    with Session(engine) as session, session.begin():
        consent = session.scalar(select(Consent).where(Consent.user_id == ids[0], Consent.kind == "publish_profile"))
        consent.granted = False
    assert client.post("/invitations", headers=headers[2], json=payload).status_code == 404
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Invitation)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_same_grade_does_not_restart_cooldown(assessment_env, approved):
    _, _, ids, engine = prepare(assessment_env)
    aid = start(assessment_env).json()["id"]
    submit(assessment_env, aid)
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        profile.last_grade_change_at -= timedelta(days=91)
        original = profile.last_grade_change_at
    second = start(assessment_env)
    assert second.status_code == 201
    assert submit(assessment_env, second.json()["id"]).status_code == 200
    with Session(engine) as session:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        assert profile.last_grade_change_at == original and profile.verified_attempt_id == aid
