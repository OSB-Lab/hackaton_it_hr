import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app
from app.models import CandidateProfile, Consent, User
from app.modules.auth import dependencies, security
from app.modules.candidate.schemas import HiringCandidateDTO
from app.modules.candidate.service import eligible_for_employer_search, hiring_profile

URL = "/me/candidate-profile"


@pytest.fixture
def env(migrated_engine, monkeypatch):
    settings = get_settings().model_copy(update={"JWT_SECRET": SecretStr("candidate-test-" + "x" * 64)})
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    with Session(migrated_engine) as session, session.begin():
        users = [User(email=f"user{i}@example.com", password_hash="unused", role=role)
                 for i, role in enumerate(("candidate", "candidate", "employer"))]
        session.add_all(users)
        session.flush()
        ids = [u.id for u in users]
        headers = [{"Authorization": "Bearer " + security.create_access_token(u.id, u.role)} for u in users]
        session.add(CandidateProfile(user_id=ids[1], full_name="Other owner", grade="senior"))

    def get_session():
        with Session(migrated_engine, expire_on_commit=False) as session:
            yield session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[dependencies.get_auth_session] = get_session
    try:
        with TestClient(app) as client:
            yield client, headers, ids, migrated_engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_owner_profile_partial_update_and_grade_separation(env):
    client, headers, ids, engine = env
    empty = client.get(URL, headers=headers[0])
    assert empty.status_code == 200
    assert empty.json()["email"] == "user0@example.com"
    assert empty.json()["consents"] == {"processing": False, "publication": False}
    payload = {"fullName": "Candidate", "phone": "+7 999 123-45-67", "stack": ["Python"],
               "role": "Backend engineer", "experienceMonths": 24, "softSkills": ["Teamwork"],
               "specialization": "backend", "selfDeclaredGrade": "middle"}
    response = client.patch(URL, headers=headers[0], json=payload)
    assert response.status_code == 200
    assert all(response.json()[key] == value for key, value in payload.items())
    assert client.get(URL, headers=headers[0]).json() == response.json()
    response = client.patch(URL, headers=headers[0], json={"phone": None})
    assert response.json()["phone"] is None
    assert response.json()["stack"] == ["Python"]
    client.patch(URL, headers=headers[1], json={"selfDeclaredGrade": "junior"})
    with Session(engine) as session:
        own = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        other = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[1]))
        assert own.grade is None
        assert other.grade == "senior" and other.full_name == "Other owner"
        assert session.get(User, ids[0]).role == "candidate"


@pytest.mark.parametrize("method", ["get", "patch"])
@pytest.mark.parametrize("actor,status", [(2, 403), (None, 401)])
def test_access_restrictions(env, method, actor, status):
    client, headers, _, _ = env
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    if method == "patch":
        kwargs["json"] = {"fullName": "Forbidden"}
    assert getattr(client, method)(URL, **kwargs).status_code == status


@pytest.mark.parametrize("field,value", [("user_id", 2), ("userId", 2), ("id", 2),
    ("profileId", 2), ("grade", "senior"), ("email", "other@example.com"),
    ("privacy_settings", {"publish_profile": True}), ("experienceMonths", -1),
    ("experienceMonths", True), ("consents", {"publication": None})])
def test_patch_rejects_identity_and_invalid_fields(env, field, value):
    client, headers, ids, engine = env
    assert client.patch(URL, headers=headers[0], json={field: value}).status_code == 422
    with Session(engine) as session:
        assert session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0])) is None
        assert session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[1])).full_name == "Other owner"


@pytest.mark.parametrize("processing,publication", [(False, False), (True, False), (False, True), (True, True)])
def test_independent_consents_and_eligibility(env, processing, publication):
    client, headers, ids, engine = env
    response = client.patch(URL, headers=headers[0], json={
        "consents": {"processing": processing, "publication": publication}})
    assert response.status_code == 200
    assert response.json()["consents"] == {"processing": processing, "publication": publication}
    assert response.json()["eligibleForEmployerSearch"] == publication
    with Session(engine) as session:
        assert eligible_for_employer_search(session, ids[0]) == publication
        assert (hiring_profile(session, ids[0]) is not None) == publication
        rows = {r.kind: r for r in session.scalars(select(Consent).where(Consent.user_id == ids[0]))}
        assert set(rows) == {"privacy", "publish_profile"}
        assert (rows["privacy"].granted_at is not None) == processing
        assert (rows["publish_profile"].granted_at is not None) == publication
    response = client.patch(URL, headers=headers[0], json={"consents": {"publication": False}})
    assert response.json()["consents"]["processing"] == processing
    assert response.json()["eligibleForEmployerSearch"] is False
    with Session(engine) as session:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        profile.privacy_settings = {"publish_profile": True}
        session.commit()
        assert hiring_profile(session, ids[0]) is None


def test_hiring_projection_has_no_contacts_and_fails_closed(env):
    client, headers, ids, engine = env
    email, phone = "private@example.com", "+7 999 123-45-67"
    client.patch(URL, headers=headers[0], json={"phone": phone, "fullName": email,
        "role": phone, "stack": ["Python", email], "softSkills": [phone, "Teamwork"],
        "specialization": email})
    with Session(engine) as session:
        assert hiring_profile(session, ids[0]) is None
    client.patch(URL, headers=headers[0], json={"consents": {"publication": True}})
    with Session(engine) as session:
        dto = hiring_profile(session, ids[0])
        assert isinstance(dto, HiringCandidateDTO)
        serialized = dto.model_dump_json()
        for forbidden in (email, phone, "user0@example.com", '"email"', '"phone"', '"user_id"'):
            assert forbidden not in serialized
        assert dto.stack == ("Python",) and dto.softSkills == ("Teamwork",)
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        profile.privacy_settings = {"publish_profile": False, "email": email, "phone": phone}
        session.commit()
        assert hiring_profile(session, ids[0]) is None
    assert {"email", "phone"}.isdisjoint(HiringCandidateDTO.model_fields)
    with pytest.raises(ValidationError):
        HiringCandidateDTO(id=1, email=email)
    with pytest.raises(ValidationError):
        HiringCandidateDTO(id=1, fullName=phone)


def test_only_new_routes_exist(env):
    client, _, _, _ = env
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths[URL]) == {"get", "patch"}
    assert "/candidate/profile" not in paths
