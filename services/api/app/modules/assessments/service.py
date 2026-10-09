import json
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, TestAttempt
from app.modules.assessments.schemas import AttemptDTO, AttemptSnapshot, StartRequest
from app.modules.catalog.public import public_variant
from app.modules.catalog.repository import CatalogRepository, Loaded, decode


def attempt_dto(attempt: TestAttempt) -> AttemptDTO:
    if attempt.status == "legacy":
        raise HTTPException(status_code=409, detail="Historical attempt has no snapshot")
    try:
        if attempt.snapshot_schema_version != 1:
            raise ValueError("Unsupported snapshot")
        snapshot = decode(AttemptSnapshot, json.dumps(attempt.snapshot))
        public = public_variant(Loaded(snapshot.blueprint, attempt.blueprint_checksum), attempt.variant)
        return AttemptDTO(id=attempt.id, status=attempt.status, createdAt=attempt.created_at,
                          submittedAt=attempt.submitted_at, assessment=public)
    except (ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Assessment snapshot unavailable") from None


def read_attempt(session: Session, user_id: int, attempt_id: int) -> AttemptDTO:
    attempt = session.scalar(select(TestAttempt).join(CandidateProfile).where(
        TestAttempt.id == attempt_id, CandidateProfile.user_id == user_id))
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt_dto(attempt)


def start_attempt(session: Session, user_id: int, request: StartRequest) -> tuple[AttemptDTO, bool]:
    # Lock a stable owner row before checking/inserting, including first creation.
    try:
        profile = session.scalar(select(CandidateProfile).where(
            CandidateProfile.user_id == user_id).with_for_update())
        if profile is None:
            raise HTTPException(status_code=409, detail="Candidate profile required")
        active = session.scalar(select(TestAttempt).where(
            TestAttempt.candidate_id == profile.id, TestAttempt.status == "active"))
        if active is not None:
            if (active.specialization, active.requested_grade) != (request.specialization, request.grade):
                raise HTTPException(status_code=409, detail="Another assessment is active")
            response = attempt_dto(active)
            session.commit()
            return response, False
        try:
            repository = CatalogRepository()
            repository.validate_all()
            matches = [loaded for key in repository.manifest.activeBlueprints
                       if (loaded := repository.blueprint(key)).document.specialization == request.specialization
                       and loaded.document.grade == request.grade]
            if not matches:
                raise HTTPException(status_code=422, detail="Assessment combination unavailable")
            blueprint = matches[0]
            catalog = repository.catalog(blueprint.document.catalogVersion)
        except (ValueError, OSError):
            raise HTTPException(status_code=503, detail="Assessment catalog unavailable") from None
        snapshot = AttemptSnapshot(schemaVersion=1, blueprint=blueprint.document, catalog=catalog.document)
        attempt = TestAttempt(
            candidate_id=profile.id, test_id=blueprint.document.id,
            specialization=request.specialization, requested_grade=request.grade,
            blueprint_version=blueprint.document.version, catalog_version=catalog.document.version,
            blueprint_checksum=blueprint.checksum, catalog_checksum=catalog.checksum,
            snapshot_schema_version=1, snapshot=snapshot.model_dump(mode="json"),
            variant=secrets.choice(("A", "B")), content_status=blueprint.document.status,
            status="active", submitted_at=None,
        )
        session.add(attempt)
        session.flush()
        response = attempt_dto(attempt)
        session.commit()
        return response, True
    except Exception:
        session.rollback()
        raise
