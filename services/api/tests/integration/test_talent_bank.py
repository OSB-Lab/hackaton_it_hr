from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (CandidateProfile, Consent, FspAchievement, FspLink,
                        RecommendationItem, RecommendationSnapshot, User)
from app.models import TestAttempt as AssessmentAttempt
from app.modules.recommendations import service
from app.modules.recommendations.talent_schemas import TalentCandidateDTO
from test_recommendations import recommendation_env, path
from test_employer_company import company_env


@pytest.fixture
def talent_env(recommendation_env):
    env, (need, other, candidate, snapshot) = recommendation_env
    client, headers, user_ids, engine = env
    with Session(engine) as session, session.begin():
        first = session.get(CandidateProfile, candidate)
        first.specialization, first.stack = "backend", ["python", "sql", "secret@example.com", "+79991234567"]
        session.add(FspLink(candidate_id=candidate, status="linked", fsp_id="fixture-1", linked_at=datetime.now(timezone.utc)))
        session.add(FspAchievement(candidate_id=candidate, discipline="fixture", result="secret@example.com"))
        candidates = [candidate]
        for i, spec, stack in [(2, "backend", ["python"]), (3, "frontend", ["react"])]:
            user = User(email=f"talent{i}@example.com", password_hash="fixture", role="candidate", is_verified=True)
            session.add(user)
            session.flush()
            profile = CandidateProfile(user_id=user.id, specialization=spec, stack=stack, grade="senior",
                                       self_declared_grade="senior", full_name="Private Name")
            session.add(profile)
            session.add(Consent(user_id=user.id, kind="publish_profile", granted=True))
            session.flush()
            candidates.append(profile.id)
            session.add(RecommendationItem(snapshot_id=snapshot, candidate_id=profile.id, score=12-i,
                                          rank=i, reason="phone=+79991234567"))
    return env, (need, other, snapshot), candidates


def url(need, snapshot):
    return path(need, snapshot) + "/items"


def database_state(engine):
    with engine.connect() as connection:
        return {table: [dict(row) for row in connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings()]
                for table in ("recommendation_snapshots", "recommendation_items")}


@pytest.mark.parametrize("filters,positions", [
    ({"specialization": "backend"}, [0, 1]),
    ({"specialization": "frontend"}, [2]),
    ({"grade": "senior"}, []),
    ({"stack": "python"}, [0, 1]),
    ([("stack", "python"), ("stack", "sql")], [0]),
    ({"hasFspAchievements": "true"}, [0]),
    ({"hasFspAchievements": "false"}, [1, 2]),
    ({"specialization": "backend", "stack": "python", "hasFspAchievements": "false"}, [1]),
    ({"specialization": "frontend", "stack": "python"}, []),
    ({"specialization": "backend", "grade": "junior", "stack": "python", "hasFspAchievements": "true"}, []),
])
def test_filters_and_reset_preserve_snapshot(talent_env, filters, positions, monkeypatch):
    (client, headers, _, engine), (need, _, snapshot), candidates = talent_env
    before = database_state(engine)
    def forbidden(*args, **kwargs): raise AssertionError("Ranking must not be called")
    monkeypatch.setattr(service, "create_snapshot", forbidden)
    original = client.get(url(need, snapshot), headers=headers[0])
    assert original.status_code == 200
    response = client.get(url(need, snapshot), params=filters, headers=headers[0])
    assert response.status_code == 200
    data = response.json()
    assert data["baseSnapshotId"] == snapshot
    assert [item["candidate"]["id"] for item in data["items"]] == [candidates[i] for i in positions]
    assert data["items"] == [original.json()["items"][i] for i in positions]
    assert [i["rank"] for i in original.json()["items"]] == [1, 2, 3]
    assert client.get(url(need, snapshot), headers=headers[0]).json() == original.json()
    assert database_state(engine) == before


@pytest.mark.parametrize("filters", [
    {"specialization": "unknown"}, {"specialization": ""}, {"grade": "expert"},
    {"grade": ""}, {"stack": "unknown"}, {"stack": "Python"}, {"stack": ""},
    {"category": "high"}, {"category": "pass"}, {"category": "unknown"}, {"category": ""},
    {"hasFspAchievements": "unknown"}, {"ownerId": "1"},
])
def test_invalid_filters(talent_env, filters):
    (client, headers, _, engine), (need, _, snapshot), _ = talent_env
    before = database_state(engine)
    response = client.get(url(need, snapshot), params=filters, headers=headers[0])
    assert response.status_code == 422
    if "category" in filters:
        assert response.json()["detail"]["code"] == "category_catalog_unavailable"
    assert database_state(engine) == before


@pytest.mark.parametrize("actor,status", [(None, 401), (2, 403), (1, 404)])
def test_rbac(talent_env, actor, status):
    (client, headers, _, _), (need, _, snapshot), _ = talent_env
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    assert client.get(url(need, snapshot), **kwargs).status_code == status


def test_snapshot_ownership(talent_env):
    (client, headers, _, _), (need, other, snapshot), _ = talent_env
    for need_id, snap, actor in [(need, 999999, 0), (other, snapshot, 1), (999999, snapshot, 0)]:
        assert client.get(url(need_id, snap), headers=headers[actor]).status_code == 404
    # An invalid catalog filter must not disclose existence of a foreign need.
    assert client.get(url(need, snapshot), params={"grade": "unknown"}, headers=headers[1]).status_code == 404


@pytest.mark.parametrize("condition", ["consent", "email", "privacy"])
def test_revocation_even_when_filter_would_hide_candidate(talent_env, condition):
    (client, headers, users, engine), (need, _, snapshot), candidates = talent_env
    before = database_state(engine)
    with Session(engine) as session, session.begin():
        if condition == "email": session.get(User, users[2]).is_verified = False
        elif condition == "privacy": session.get(CandidateProfile, candidates[0]).privacy_settings = {"publish_profile": False}
        else:
            session.scalar(select(Consent).where(Consent.user_id == users[2])).granted = False
    for params in ({}, {"specialization": "frontend"}, {"grade": "senior"}):
        response = client.get(url(need, snapshot), headers=headers[0], params=params)
        assert response.status_code == 409
        assert "items" not in response.json()
    assert database_state(engine) == before


def test_no_pii_or_false_qualification(talent_env):
    (client, headers, _, engine), (need, _, snapshot), candidates = talent_env
    with Session(engine) as session, session.begin():
        session.add(AssessmentAttempt(candidate_id=candidates[0], test_id="fixture", status="submitted",
                    content_status="APPROVED", grade="senior", score=100,
                    result={"outcome": "high", "status": "APPROVED"}, answers=["answerKey"]))
    response = client.get(url(need, snapshot), headers=headers[0])
    assert response.status_code == 200
    for word in ("email", "phone", "fullName", "answerKey", "rubric", "scoring", "@", "79991234567", "Private Name", "senior", "high"):
        assert word not in response.text
    assert set(TalentCandidateDTO.model_fields) == {"id", "specialization", "stack", "grade", "category", "hasFspAchievements"}
    for item in response.json()["items"]:
        assert item["candidate"]["grade"] is item["candidate"]["category"] is None
    assert client.get(url(need, snapshot), headers=headers[0], params={"grade": "senior"}).json()["items"] == []


@pytest.mark.parametrize("missing", ["link", "history", "linked_at", "fsp_id", "linked_status"])
def test_fsp_requires_linked_history(talent_env, missing):
    (client, headers, _, engine), (need, _, snapshot), candidates = talent_env
    with Session(engine) as session, session.begin():
        link = session.scalar(select(FspLink).where(FspLink.candidate_id == candidates[0]))
        if missing == "link": session.delete(link)
        elif missing == "history": session.delete(session.scalar(select(FspAchievement)))
        elif missing == "linked_status": link.status = "no_history"
        else: setattr(link, missing, None)
    response = client.get(url(need, snapshot), headers=headers[0], params={"hasFspAchievements": "true"})
    assert response.status_code == 200 and response.json()["items"] == []
    assert len(client.get(url(need, snapshot), headers=headers[0], params={"hasFspAchievements": "false"}).json()["items"]) == 3


def test_versioned_items_and_legacy_values(talent_env):
    (client, headers, _, engine), (need, _, snapshot), candidates = talent_env
    with Session(engine) as session, session.begin():
        profile = session.get(CandidateProfile, candidates[1])
        profile.stack, profile.specialization = ["Python", "person@example.com"], "person@example.com"
        row = session.get(RecommendationSnapshot, snapshot)
        row.algorithm_version = "fixture-v1"
        row.weights = {"skillFit": 1, "assessmentStrength": 1, "fspBonus": 1}
        row.ordered_items = [{"candidate": {"id": cid}, "rank": rank, "score": 10-rank,
                             "components": {"skillFit": rank, "assessmentStrength": 0, "fspBonus": 0}}
                            for rank, cid in enumerate(reversed(candidates), 1)]
    before = database_state(engine)
    reset = client.get(url(need, snapshot), headers=headers[0]).json()
    assert [i["candidate"]["id"] for i in reset["items"]] == list(reversed(candidates))
    assert reset["items"][1]["candidate"]["stack"] == []
    assert reset["items"][1]["candidate"]["specialization"] is None
    filtered = client.get(url(need, snapshot), params={"stack": "python"}, headers=headers[0]).json()
    assert filtered["items"] == [reset["items"][2]]
    assert database_state(engine) == before


def test_catalog_failure_and_openapi(talent_env, monkeypatch):
    from app.modules.recommendations import talent_service
    (client, headers, _, _), (need, _, snapshot), _ = talent_env
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/employer/needs/{need_id}/recommendations/{snapshot_id}/items"]["get"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {p["name"] for p in operation["parameters"] if p["in"] == "query"} == {
        "specialization", "grade", "category", "stack", "hasFspAchievements"}
    def unavailable(): raise ValueError("bad checksum")
    monkeypatch.setattr(talent_service, "CatalogRepository", unavailable)
    assert client.get(url(need, snapshot), headers=headers[0]).status_code == 503
    # Original snapshot read remains independent of the current catalog.
    assert client.get(path(need, snapshot), headers=headers[0]).status_code == 200
