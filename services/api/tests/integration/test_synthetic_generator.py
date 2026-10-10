import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User, CandidateProfile, Company, Consent, HiringNeed, TestAttempt as Attempt
from app.commands.generate_synthetic import generate, validate_target, CONFIRMATION
from app.modules.auth.security import verify_password
from app.modules.assessments.qualification import qualification
from app.modules.employer.needs_service import dto, validate_values

# Test-only fixtures/helpers for the positive eligibility scenario.
from test_candidate_profile import env  # noqa: F401
from test_assessment_v3_lifecycle import approved  # noqa: F401
from test_ranking_create import setup, certify  # noqa: F401


@pytest.mark.parametrize("url,confirmation", [
    ("postgresql+psycopg://localhost/fsp", CONFIRMATION),
    ("postgresql+psycopg://production/fsp_test_" + "a" * 32, CONFIRMATION),
    ("postgresql+psycopg://localhost/fsp_test_" + "a" * 32, "yes"),
    ("postgresql+psycopg://localhost/fsp_test_" + "a" * 32 + "?host=production", CONFIRMATION),
])
def test_refuses_unsafe_target(url, confirmation):
    with pytest.raises(ValueError):
        validate_target(url, confirmation)


def test_generate_100_idempotent_and_safe(migrated_engine, tmp_path):
    url = migrated_engine.url.render_as_string(hide_password=False)
    manifest = tmp_path / "fixture.json"
    password = "synthetic-test-only-42"
    saved = generate(url, manifest, password, CONFIRMATION)
    assert generate(url, manifest, password, CONFIRMATION) == saved
    assert len(saved["candidates"]) == 98 and len(saved["employers"]) == 2
    raw = manifest.read_text(encoding="utf-8")
    assert json.loads(raw) == saved
    for forbidden in (password, "password_hash", "@", "phone", "answerKey", "access_token"):
        assert forbidden not in raw
    with Session(migrated_engine) as session:
        users = session.scalars(select(User)).all()
        assert len(users) == 100 and len({u.email for u in users}) == 100
        assert sum(u.role == "candidate" for u in users) == 98
        assert all(u.password_hash.startswith("$argon2id$") for u in users)
        assert verify_password(password, users[0].password_hash)
        profiles = session.scalars(select(CandidateProfile)).all()
        assert len(profiles) == 98
        for p in profiles:
            assert session.get(User, p.user_id).role == "candidate"
            assert p.verified_grade is None and p.verified_attempt_id is None
            assert qualification(session, p.id) is None
            # Enriched, clearly synthetic profile fields.
            assert p.professional_role and p.experience_months is not None
            assert p.phone and p.phone.startswith("+7 900 ")
            assert isinstance(p.soft_skills, list) and p.soft_skills
        assert len(saved["demoAttempts"]) == 6
        attempts = session.scalars(select(Attempt)).all()
        assert len(attempts) == 6
        assert sum(a.status == "active" for a in attempts) == 3
        assert sum(a.status == "submitted" for a in attempts) == 3
        for a in attempts:
            assert a.content_status == "DEMO"
            if a.status == "submitted":
                assert a.result and a.result.get("status") == "DEMO"
        assert session.scalar(select(func.count()).select_from(Consent)) == 196
        assert session.scalar(select(func.count()).select_from(Company)) == 2
        needs = session.scalars(select(HiringNeed)).all()
        assert len(needs) == 2
        for need in needs:
            values = dto(need).model_dump(exclude={"id"})
            validate_values(values, set(values))
            assert need.stack and need.optional_skills and need.min_grade
            assert session.get(User, session.get(Company, need.company_id).user_id).role == "employer"
    with pytest.raises(ValueError, match="empty domain"):
        generate(url, tmp_path / "other.json", password, CONFIRMATION)
    # A modified existing account must not be overwritten on retry.
    with Session(migrated_engine) as session, session.begin():
        session.get(User, saved["candidates"][0]["userId"]).is_verified = False
    with pytest.raises(ValueError, match="drift"):
        generate(url, manifest, password, CONFIRMATION)


def test_conflict_existing_account(migrated_engine, tmp_path):
    with Session(migrated_engine) as session, session.begin():
        session.add(User(email="existing@example.test", password_hash="do-not-change", role="candidate"))
    with pytest.raises(ValueError, match="empty domain"):
        generate(migrated_engine.url.render_as_string(hide_password=False), tmp_path / "fixture.json",
                 "synthetic-test-only-42", CONFIRMATION)
    with Session(migrated_engine) as session:
        assert session.scalar(select(User)).password_hash == "do-not-change"
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_positive_eligibility_ranking_invitation(env, approved):
    """TEST-ONLY: certified via the `approved` fixture, never real qualifications."""
    client, headers, ids, engine = env
    url, _need_id = setup(env)
    certify(env, 0, 18)  # full correct -> high
    certify(env, 1, 13)  # partial -> pass
    ranking = client.post(url, headers=headers[2])
    assert ranking.status_code == 200
    items = ranking.json()["items"]
    assert len(items) == 2
    assert items[0]["rank"] == 1 and items[0]["score"] == 0.85
    with Session(engine) as session:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        company = session.scalar(select(Company).where(Company.user_id == ids[2]))
    invitation = client.post("/invitations", headers=headers[2], json={
        "companyId": company.id, "candidateId": profile.id,
        "offerDescription": "Backend", "contactMethod": "email",
        "salaryMin": "100", "salaryMax": "200"})
    assert invitation.status_code == 201

