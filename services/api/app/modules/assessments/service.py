import json
import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, TestAttempt
from app.core.config import get_settings
from app.modules.assessments.qualification import apply_result, check_start
from app.modules.assessments.scoring_v3 import score_v3
from app.modules.assessments.schemas import AttemptDTO, AttemptSnapshot, StartRequest, ResultDTO, SubmitDTO, SubmitRequest
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
    attempt = session.scalar(select(TestAttempt).join(CandidateProfile, TestAttempt.candidate_id == CandidateProfile.id).where(
        TestAttempt.id == attempt_id, CandidateProfile.user_id == user_id))
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt_dto(attempt)


def score_answers(snapshot: AttemptSnapshot, variant: str, request: SubmitRequest) -> ResultDTO:
    blueprint = snapshot.blueprint
    if blueprint.schemaVersion == 3:
        return score_v3(blueprint, variant, request)
    questions = next(v.questions for v in blueprint.variants if v.id == variant)
    answers = {a.questionId: a.optionId for a in request.answers}
    if len(answers) != len(request.answers) or set(answers) != {q.id for q in questions}:
        raise HTTPException(status_code=422, detail="Answers must cover each question exactly once")
    slots = {s.id: s for s in blueprint.slots}
    rubrics = {r.id: r for r in blueprint.rubric}
    earned, weights = {}, {}
    for question in questions:
        option = answers[question.id]
        if option is not None and option not in {o.id for o in question.options}:
            raise HTTPException(status_code=422, detail="Unknown answer option")
        slot = slots[question.slotId]
        rubric = rubrics[slot.rubricId]
        fraction = (rubric.unansweredFraction if option is None else
                    rubric.correctFraction if option == question.answerKey.optionId else rubric.incorrectFraction)
        weight = Decimal(str(slot.weight))
        # awardedScore / maxScore equals the rubric fraction exactly.
        earned[slot.skillId] = earned.get(slot.skillId, Decimal(0)) + weight * Decimal(str(fraction))
        weights[slot.skillId] = weights.get(slot.skillId, Decimal(0)) + weight
    scale = Decimal(str(blueprint.scoring.scaleMax))
    total = scale * sum(earned.values()) / sum(weights.values())
    thresholds = blueprint.scoring.thresholds
    outcome = ("high" if total >= Decimal(str(thresholds.highScore)) else
               "pass" if total >= Decimal(str(thresholds.passScore)) else "fail")
    return ResultDTO(subscores={skill: float(scale * value / weights[skill]) for skill, value in earned.items()},
                     totalScore=float(total), outcome=outcome, status=blueprint.status)


def submit_attempt(session: Session, user_id: int, attempt_id: int, request: SubmitRequest) -> SubmitDTO:
    try:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id).with_for_update())
        attempt = session.scalar(select(TestAttempt).join(CandidateProfile, TestAttempt.candidate_id == CandidateProfile.id).where(
            TestAttempt.id == attempt_id, CandidateProfile.user_id == user_id
        ).with_for_update(of=TestAttempt))
        if attempt is None:
            raise HTTPException(status_code=404, detail="Attempt not found")
        if attempt.snapshot is None or attempt.status == "legacy":
            raise HTTPException(status_code=409, detail="Historical attempt has no snapshot")
        if attempt.status == "active":
            try:
                if attempt.snapshot_schema_version != 1:
                    raise ValueError("Unsupported snapshot")
                snapshot = decode(AttemptSnapshot, json.dumps(attempt.snapshot))
                if attempt.variant not in {v.id for v in snapshot.blueprint.variants}:
                    raise ValueError("Unknown variant")
            except (ValueError, TypeError):
                raise HTTPException(status_code=503, detail="Assessment snapshot unavailable") from None
            result = score_answers(snapshot, attempt.variant, request)
            attempt.answers = [answer.model_dump(mode="json") for answer in request.answers]
            attempt.score = result.totalScore
            attempt.submitted_at = datetime.now(timezone.utc)
            attempt.status = "submitted"
            apply_result(session, profile, attempt, snapshot, result)
            attempt.result = result.model_dump(mode="json")
        if attempt.result is None or attempt.submitted_at is None:
            raise HTTPException(status_code=409, detail="Saved assessment result unavailable")
        response = SubmitDTO(id=attempt.id, status="submitted", submittedAt=attempt.submitted_at,
                             result=ResultDTO.model_validate(attempt.result))
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise


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
                raise HTTPException(status_code=422, detail="no blueprint for grade")
            blueprint = matches[0]
            catalog = repository.catalog(blueprint.document.catalogVersion)
        except (ValueError, OSError):
            raise HTTPException(status_code=503, detail="Assessment catalog unavailable") from None
        variants = ("A", "B")
        if blueprint.document.schemaVersion == 3:
            now = datetime.now(timezone.utc)
            check_start(profile, request, catalog.document, now)
            history = list(session.scalars(select(TestAttempt).where(
                TestAttempt.candidate_id == profile.id,
                TestAttempt.specialization == request.specialization,
                TestAttempt.requested_grade == request.grade,
                TestAttempt.blueprint_version == blueprint.document.version)))
            # A/B first; C is the reserve. Retests never reuse a recently seen form.
            cutoff = now - timedelta(days=get_settings().ASSESSMENT_COOLDOWN_DAYS)
            seen = {a.variant for a in history if a.created_at > cutoff}
            variants = tuple(v.id for v in blueprint.document.variants if v.id not in seen)
            if not history:
                variants = ("A", "B")
            if not variants:
                until = min(a.created_at for a in history if a.created_at > cutoff) + timedelta(days=get_settings().ASSESSMENT_COOLDOWN_DAYS)
                raise HTTPException(409, {"code": "assessment_pool_exhausted", "retest_available_at": until.isoformat()})
        snapshot = AttemptSnapshot(schemaVersion=1, blueprint=blueprint.document, catalog=catalog.document)
        attempt = TestAttempt(
            candidate_id=profile.id, test_id=blueprint.document.id,
            specialization=request.specialization, requested_grade=request.grade,
            blueprint_version=blueprint.document.version, catalog_version=catalog.document.version,
            blueprint_checksum=blueprint.checksum, catalog_checksum=catalog.checksum,
            snapshot_schema_version=1, snapshot=snapshot.model_dump(mode="json"),
            variant=secrets.choice(variants), content_status=blueprint.document.status,
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
