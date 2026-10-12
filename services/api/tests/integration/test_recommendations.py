import copy

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (CandidateProfile, Company, Consent, HiringNeed, RecommendationItem,
                        RecommendationSnapshot, User)
from app.models import TestAttempt as AssessmentAttempt
from app.modules.recommendations import service
from test_employer_company import company_env


@pytest.fixture
def recommendation_env(company_env):
    client, headers, ids, engine = company_env
    with Session(engine) as session, session.begin():
        company = Company(user_id=ids[0], name="Owner")
        other = Company(user_id=ids[1], name="Other")
        session.add_all([company, other])
        session.flush()
        need = HiringNeed(company_id=company.id, title="Need")
        other_need = HiringNeed(company_id=other.id, title="Other need")
        candidate = CandidateProfile(user_id=ids[2], grade="senior", self_declared_grade="senior",
                                     full_name="contact@example.com", phone="+79991234567")
        session.add_all([need, other_need, candidate])
        session.get(User, ids[2]).is_verified = True
        session.add(Consent(user_id=ids[2], kind="publish_profile", granted=True))
        session.flush()
        snapshot = RecommendationSnapshot(need_id=need.id)
        session.add(snapshot)
        session.flush()
        session.add(RecommendationItem(snapshot_id=snapshot.id, candidate_id=candidate.id,
                    score=12, rank=1, reason='contact@example.com answerKey +79991234567'))
        values = need.id, other_need.id, candidate.id, snapshot.id
    return company_env, values


def path(need, snapshot=None):
    base = f"/employer/needs/{need}/recommendations"
    return base if snapshot is None else f"{base}/{snapshot}"


@pytest.mark.parametrize("method", ["post", "get"])
@pytest.mark.parametrize("actor,status", [(None, 401), (2, 403), (1, 404)])
def test_rbac_and_ownership(recommendation_env, method, actor, status):
    (client, headers, _, _), (need, _, _, snapshot) = recommendation_env
    url = path(need, snapshot if method == "get" else None)
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    assert getattr(client, method)(url, **kwargs).status_code == status
    if actor == 1:
        missing = path(999999, snapshot if method == "get" else None)
        assert getattr(client, method)(url, **kwargs).json() == getattr(client, method)(missing, **kwargs).json()


def test_invalid_legacy_need_no_writes_and_scoped_snapshot(recommendation_env):
    (client, headers, _, engine), (need, other, _, snapshot) = recommendation_env
    with Session(engine) as session:
        before = [session.scalar(select(func.count()).select_from(model))
                  for model in (RecommendationSnapshot, RecommendationItem)]
    for _ in range(2):
        response = client.post(path(need), headers=headers[0])
        assert response.status_code == 422
    assert client.get(path(other, snapshot), headers=headers[1]).status_code == 404
    assert client.get(path(need, 999999), headers=headers[0]).status_code == 404
    with Session(engine) as session:
        assert before == [session.scalar(select(func.count()).select_from(model))
                          for model in (RecommendationSnapshot, RecommendationItem)]


@pytest.mark.parametrize("condition", ["email", "consent", "missing_consent", "privacy", "role"])
def test_disclosure_rechecks_current_privacy(recommendation_env, condition):
    (client, headers, ids, engine), (need, _, candidate, snapshot) = recommendation_env
    assert client.get(path(need, snapshot), headers=headers[0]).status_code == 200
    with Session(engine) as session, session.begin():
        if condition == "email": session.get(User, ids[2]).is_verified = False
        elif condition == "role": session.get(User, ids[2]).role = "employer"
        elif condition == "privacy": session.get(CandidateProfile, candidate).privacy_settings = {"publish_profile": False}
        else:
            consent = session.scalar(select(Consent).where(Consent.user_id == ids[2]))
            if condition == "missing_consent": session.delete(consent)
            else: consent.granted = False
    response = client.get(path(need, snapshot), headers=headers[0])
    assert response.status_code == 409
    assert str(candidate) not in response.json()["detail"]
    with Session(engine) as session:
        assert not service.can_disclose_candidate(session, candidate)
        assert session.scalar(select(func.count()).select_from(RecommendationItem)) == 1


def test_no_false_qualification(recommendation_env):
    (_, _, _, engine), (_, _, candidate, _) = recommendation_env
    with Session(engine) as session, session.begin():
        session.add(AssessmentAttempt(candidate_id=candidate, test_id="fixture", status="submitted",
                    grade="senior", score=100, result={"outcome": "high"}))
    with Session(engine) as session:
        assert service.can_disclose_candidate(session, candidate)
        assert not service.has_verified_qualification(session, candidate)
        assert not service.eligible_for_ranking(session, candidate)
        assert not service.eligible_for_ranking(session, 999999)


def test_legacy_snapshot_safe_and_unchanged(recommendation_env):
    (client, headers, _, engine), (need, _, candidate, snapshot) = recommendation_env
    first = client.get(path(need, snapshot), headers=headers[0])
    assert first.status_code == 200
    assert first.json()["algorithmVersion"] is None
    assert first.json()["weights"] is None
    assert first.json()["items"] == [{"candidate": {"id": candidate}, "rank": 1, "score": 12.0, "components": None, "reasons": []}]
    for word in ("email", "phone", "answerKey", "rubric", "scoring", "contact@example.com", "+79991234567"):
        assert word not in first.text
    with Session(engine) as session, session.begin():
        session.get(CandidateProfile, candidate).grade = "junior"
        session.get(HiringNeed, need).stack = ["changed"]
    assert client.get(path(need, snapshot), headers=headers[0]).json() == first.json()
    with Session(engine) as session:
        row = session.get(RecommendationSnapshot, snapshot)
        assert row.ordered_items is row.algorithm_version is row.weights is None
        assert session.scalar(select(RecommendationItem)).reason == 'contact@example.com answerKey +79991234567'


def test_versioned_snapshot_reads_saved_data_only(recommendation_env, monkeypatch):
    (client, headers, _, engine), (need, _, candidate, snapshot) = recommendation_env
    # Persistence fixture only; these numbers are not a ranking policy.
    weights = {"skillFit": 2, "assessmentStrength": 3, "fspBonus": 4}
    items = [{"candidate": {"id": candidate}, "rank": 1, "score": 19,
              "components": {"skillFit": 5, "assessmentStrength": 6, "fspBonus": 0}}]
    with Session(engine) as session, session.begin():
        row = session.get(RecommendationSnapshot, snapshot)
        row.algorithm_version, row.weights, row.ordered_items = "fixture-v1", weights, copy.deepcopy(items)
    def forbidden(*args, **kwargs): raise AssertionError("No recalculation or qualification inference on historical read")
    monkeypatch.setattr(service, "has_verified_qualification", forbidden)
    from app.modules.catalog.repository import CatalogRepository
    monkeypatch.setattr(CatalogRepository, "catalog", forbidden)
    first = client.get(path(need, snapshot), headers=headers[0])
    assert first.status_code == 200
    assert first.json()["items"] == [{**item, "reasons": []} for item in items]
    assert client.get(path(need, snapshot), headers=headers[0]).json() == first.json()
    with Session(engine) as session:
        row = session.get(RecommendationSnapshot, snapshot)
        assert (row.weights, row.ordered_items) == (weights, items)
    with Session(engine) as session, session.begin():
        row = session.get(RecommendationSnapshot, snapshot)
        bad = copy.deepcopy(items)
        bad[0]["candidate"]["email"] = "secret@example.com"
        row.ordered_items = bad
    response = client.get(path(need, snapshot), headers=headers[0])
    assert response.status_code == 503 and "secret" not in response.text


def test_openapi(recommendation_env):
    (client, _, _, _), _ = recommendation_env
    paths = client.get("/openapi.json").json()["paths"]
    base = "/employer/needs/{need_id}/recommendations"
    for url, method in [(base, "post"), (base + "/{snapshot_id}", "get")]:
        assert paths[url][method]["security"] == [{"HTTPBearer": []}]
