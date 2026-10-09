from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
import hashlib
import json
import shutil

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CandidateProfile, TestAttempt as Attempt
from app.modules.assessments import service
from app.modules.catalog.repository import CatalogRepository, DATA_ROOT
from test_candidate_profile import env as assessment_env

START = "/assessments/start"
BODY = {"specialization": "backend", "grade": "junior"}


def prepare(env):
    client, headers, ids, engine = env
    assert client.patch("/me/candidate-profile", headers=headers[0], json={"fullName": "Assessment candidate"}).status_code == 200
    return client, headers, ids, engine


@pytest.mark.parametrize("variant", ["A", "B"])
@pytest.mark.parametrize("initial_grade", [None, "senior"])
def test_start_repeat_snapshot_and_no_grade_change(assessment_env, monkeypatch, variant, initial_grade):
    client, headers, ids, engine = prepare(assessment_env)
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        profile.grade = initial_grade
    monkeypatch.setattr(service.secrets, "choice", lambda values: variant)
    created = client.post(START, headers=headers[0], json=BODY)
    assert created.status_code == 201
    data = created.json()
    assert data["status"] == "active" and data["submittedAt"] is None
    assert data["assessment"]["status"] == "DEMO"
    assert data["assessment"]["variant"] == variant
    for forbidden in ("answerKey", "optionId", "rubric", "scoring", "threshold", "checksum", "weight", "maxScore"):
        assert forbidden not in created.text
    path = f'/assessments/{data["id"]}'
    with Session(engine) as session:
        row = session.get(Attempt, data["id"])
        snapshot = row.snapshot
        assert row.content_status == "DEMO" and row.status == "active"
        assert row.score is None and row.grade is None and row.answers == []
        assert session.get(CandidateProfile, row.candidate_id).grade == initial_grade
        catalog = CatalogRepository()
        assert row.catalog_checksum == catalog.catalog().checksum
        assert row.blueprint_checksum == catalog.blueprint("backend-junior-v1-demo").checksum
        assert row.snapshot["blueprint"]["variants"][0]["questions"][0]["answerKey"]
    # GET and retry must not touch the repository, even if files/active pointers change.
    def unavailable():
        raise AssertionError("Existing attempt must not load the current catalog")
    monkeypatch.setattr(service, "CatalogRepository", unavailable)
    monkeypatch.setattr(service.secrets, "choice", unavailable)
    assert client.get(path, headers=headers[0]).json() == data
    repeat = client.post(START, headers=headers[0], json=BODY)
    assert repeat.status_code == 200 and repeat.json() == data
    assert client.post(START, headers=headers[0], json={**BODY, "grade": "middle"}).status_code == 409
    with Session(engine) as session:
        assert session.get(Attempt, data["id"]).snapshot == snapshot
        assert session.scalar(select(func.count()).select_from(Attempt)) == 1
        assert session.scalar(select(CandidateProfile.grade).where(CandidateProfile.user_id == ids[0])) == initial_grade


def test_active_blueprint_switch_preserves_started_attempt(assessment_env, monkeypatch, tmp_path):
    client, headers, _, engine = prepare(assessment_env)
    root = tmp_path / "catalog"
    shutil.copytree(DATA_ROOT, root)
    monkeypatch.setattr(service, "CatalogRepository", lambda: CatalogRepository(root))
    monkeypatch.setattr(service.secrets, "choice", lambda values: "A")
    first = client.post(START, headers=headers[0], json=BODY)
    assert first.status_code == 201
    original = first.json()
    with Session(engine) as session:
        attempt = session.get(Attempt, original["id"])
        snapshot, checksum = attempt.snapshot, attempt.blueprint_checksum

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    old_key = "backend-junior-v1-demo"
    ref = next(r for r in manifest["artifacts"] if r["key"] == old_key)
    new_ref = {**ref, "key": "backend-junior-v2-demo", "version": "v2-demo", "path": "v2-demo.json"}
    blueprint = json.loads((root / ref["path"]).read_text())
    blueprint["version"] = "v2-demo"
    blueprint["variants"][0]["questions"][0]["prompt"] = "DEMO: Changed question"
    question = blueprint["variants"][0]["questions"][0]
    question["answerKey"]["optionId"] = next(o["id"] for o in question["options"] if o["id"] != question["answerKey"]["optionId"])
    blueprint["scoring"]["thresholds"]["passScore"] = 75
    raw = json.dumps(blueprint).encode()
    (root / new_ref["path"]).write_bytes(raw)
    new_ref["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest["artifacts"].append(new_ref)
    manifest["activeBlueprints"] = [new_ref["key"] if k == old_key else k for k in manifest["activeBlueprints"]]
    manifest_path.write_text(json.dumps(manifest))
    CatalogRepository(root).validate_all()
    monkeypatch.setattr(service.secrets, "choice", lambda values: "B")

    repeat = client.post(START, headers=headers[0], json=BODY)
    assert repeat.status_code == 200 and repeat.json() == original
    assert client.get(f'/assessments/{original["id"]}', headers=headers[0]).json() == original
    with Session(engine) as session:
        attempt = session.get(Attempt, original["id"])
        assert attempt.snapshot == snapshot and attempt.blueprint_checksum == checksum
        assert attempt.variant == "A" and attempt.blueprint_version == "v1-demo"
    fresh = client.post(START, headers=headers[1], json=BODY)
    assert fresh.status_code == 201
    assert fresh.json()["assessment"]["blueprintVersion"] == "v2-demo"
    assert fresh.json()["assessment"]["variant"] == "B"
    answers = [{"questionId": q["id"], "optionId": q["answerKey"]["optionId"]}
               for q in snapshot["blueprint"]["variants"][0]["questions"]]
    submitted = client.post(f'/assessments/{original["id"]}/submit', headers=headers[0], json={"answers": answers})
    assert submitted.status_code == 200
    assert submitted.json()["result"]["totalScore"] == 100
    assert submitted.json()["result"]["outcome"] == "high"


@pytest.mark.parametrize("method,path", [("post", START), ("get", "/assessments/1")])
@pytest.mark.parametrize("actor,status", [(2, 403), (None, 401)])
def test_rbac(assessment_env, method, path, actor, status):
    client, headers, _, _ = assessment_env
    kwargs = {"headers": headers[actor]} if actor is not None else {}
    if method == "post": kwargs["json"] = BODY
    assert getattr(client, method)(path, **kwargs).status_code == status


def test_owner_only_and_missing_profile(assessment_env):
    client, headers, _, _ = assessment_env
    assert client.post(START, headers=headers[0], json=BODY).status_code == 409
    prepare(assessment_env)
    aid = client.post(START, headers=headers[0], json=BODY).json()["id"]
    foreign = client.get(f"/assessments/{aid}", headers=headers[1])
    missing = client.get("/assessments/999999", headers=headers[1])
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


@pytest.mark.parametrize("field,value", [("candidateId", 1), ("variant", "A"),
    ("blueprintVersion", "v1-demo"), ("grade", "senior"), ("specialization", "unknown"), ("grade", "")])
def test_invalid_start(assessment_env, field, value):
    client, headers, _, engine = prepare(assessment_env)
    assert client.post(START, headers=headers[0], json={**BODY, field: value}).status_code == 422
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Attempt)) == 0


def test_catalog_failure_does_not_create_attempt(assessment_env, monkeypatch):
    client, headers, _, engine = prepare(assessment_env)
    def broken(): raise ValueError("checksum mismatch")
    monkeypatch.setattr(service, "CatalogRepository", broken)
    assert client.post(START, headers=headers[0], json=BODY).status_code == 503
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Attempt)) == 0


@pytest.mark.parametrize("same", [True, False])
def test_concurrent_start(assessment_env, same):
    client, headers, _, engine = prepare(assessment_env)
    barrier = Barrier(2)
    def start(grade):
        barrier.wait(timeout=10)
        return client.post(START, headers=headers[0], json={**BODY, "grade": grade})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(start, grade) for grade in ("junior", "junior" if same else "middle")]
        responses = [f.result(timeout=20) for f in futures]
    assert sorted(r.status_code for r in responses) == ([200, 201] if same else [201, 409])
    if same: assert responses[0].json() == responses[1].json()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Attempt)) == 1


def test_partial_unique_index_and_completed_history(assessment_env):
    client, headers, _, engine = prepare(assessment_env)
    first = client.post(START, headers=headers[0], json=BODY).json()
    with Session(engine) as session:
        row = session.get(Attempt, first["id"])
        candidate_id = row.candidate_id
        session.add(Attempt(candidate_id=candidate_id, test_id="duplicate", status="active"))
        with pytest.raises(IntegrityError): session.commit()
        session.rollback()
        row = session.get(Attempt, first["id"])
        # Historical submitted row without a SPR-15.2 result.
        row.status = "submitted"
        row.submitted_at = datetime.now(timezone.utc)
        session.add(Attempt(candidate_id=candidate_id, test_id="historical", score=42, grade="junior"))
        session.commit()
        legacy_id = session.scalar(select(Attempt.id).where(Attempt.test_id == "historical"))
    assert client.get(f"/assessments/{legacy_id}", headers=headers[0]).status_code == 409
    assert client.get(f'/assessments/{first["id"]}', headers=headers[0]).json()["status"] == "submitted"
    new = client.post(START, headers=headers[0], json=BODY)
    assert new.status_code == 201 and new.json()["id"] != first["id"]
    with Session(engine) as session:
        legacy = session.get(Attempt, legacy_id)
        assert legacy.status == "legacy" and legacy.snapshot is None
        assert legacy.snapshot_schema_version is None and legacy.variant is None
        assert legacy.blueprint_version is None and legacy.catalog_version is None
        assert legacy.blueprint_checksum is None and legacy.catalog_checksum is None
        assert legacy.grade == "junior" and legacy.score == 42


def test_assessment_openapi(assessment_env):
    client, _, _, _ = assessment_env
    paths = client.get("/openapi.json").json()["paths"]
    assert {p for p in paths if p.startswith("/assessments")} == {START, "/assessments/{attempt_id}", "/assessments/{attempt_id}/submit"}
    assert set(paths[START]["post"]["responses"]) >= {"200", "201"}
