from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, RecommendationItem, RecommendationSnapshot, User
from app.modules.candidate.service import eligible_for_employer_search
from app.modules.employer.needs_service import get_need
from app.modules.recommendations.schemas import CandidateDTO, ItemDTO, SnapshotDTO, SnapshotPayload


def can_disclose_candidate(session: Session, candidate_id: int) -> bool:
    profile = session.get(CandidateProfile, candidate_id)
    user = session.get(User, profile.user_id) if profile else None
    return bool(user and user.is_verified and eligible_for_employer_search(session, user.id))


def has_verified_qualification(session: Session, candidate_id: int) -> bool:
    from app.modules.assessments.qualification import qualification
    return qualification(session, candidate_id) is not None


def eligible_for_ranking(session: Session, candidate_id: int, need=None) -> bool:
    from app.modules.assessments.qualification import matches_need
    if need is not None and not matches_need(session, candidate_id, need):
        return False
    return can_disclose_candidate(session, candidate_id) and has_verified_qualification(session, candidate_id)


def create_snapshot(session: Session, user_id: int, need_id: int):
    from app.modules.assessments.qualification import qualification
    from app.modules.assessments.schemas import ResultDTO
    from app.modules.catalog.repository import CatalogRepository
    from app.modules.catalog.validators import validate_grade, validate_skills, validate_specialization
    from app.modules.recommendations.ranking import ALGORITHM_VERSION, WEIGHTS, calculate

    need = get_need(session, user_id, need_id, lock=True)
    try:
        catalog = CatalogRepository().catalog().document
    except (ValueError, OSError):
        raise HTTPException(503, "Catalog unavailable") from None
    try:
        validate_specialization(catalog, need.specialization)
        validate_grade(catalog, need.min_grade)
        required, optional = need.stack, need.optional_skills or []
        validate_skills(catalog, required + optional, need.specialization)
        if "teamwork" in required + optional or len(set(required + optional)) != len(required + optional):
            raise ValueError("Ranking requires distinct canonical technical skills")
    except (ValueError, TypeError):
        raise HTTPException(422, "Need requires specialization, minGrade and canonical technical skills") from None
    items = []
    # Same lock order as profile privacy PATCH: User first, then profile.
    users = session.scalars(select(User).where(User.role == "candidate").order_by(User.id).with_for_update()).all()
    for user in users:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id).with_for_update())
        if profile is None or not eligible_for_ranking(session, profile.id, need):
            continue
        proof = qualification(session, profile.id)
        _, attempt, saved = proof
        result = ResultDTO.model_validate(attempt.result)
        technical = {tag for slot in saved.blueprint.slots for tag in slot.skillTags} - {"teamwork"}
        evidence = {s: result.subscores[s] for s in technical if (result.evidenceCounts or {}).get(s, 0) > 0}
        try:
            # No trusted FSP confirmation source exists yet; never promote seed/linked rows.
            score, components, reasons = calculate(required, optional, evidence, result.technicalTotal)
        except ValueError:
            raise HTTPException(503, "Certified evidence unavailable") from None
        items.append(ItemDTO(candidate=CandidateDTO(id=profile.id), rank=1, score=score,
                             components=components, reasons=reasons))
    items.sort(key=lambda item: (-item.score, -item.components.assessmentStrength, item.candidate.id))
    payload = SnapshotPayload(algorithmVersion=ALGORITHM_VERSION, weights=WEIGHTS,
                              items=tuple(item.model_copy(update={"rank": i}) for i, item in enumerate(items, 1)))
    row = RecommendationSnapshot(need_id=need.id, algorithm_version=payload.algorithmVersion,
                                 weights=payload.weights.model_dump(),
                                 ordered_items=[item.model_dump(mode="json") for item in payload.items])
    try:
        session.add(row)
        session.flush()
        session.add_all([RecommendationItem(snapshot_id=row.id, candidate_id=item.candidate.id,
                         score=item.score, rank=item.rank, reason="; ".join(item.reasons)) for item in payload.items])
        response = SnapshotDTO(id=row.id, needId=need.id, createdAt=row.created_at,
                               algorithmVersion=payload.algorithmVersion, weights=payload.weights, items=payload.items)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return response


def read_snapshot(session: Session, user_id: int, need_id: int, snapshot_id: int) -> SnapshotDTO:
    get_need(session, user_id, need_id)
    snapshot = session.scalar(select(RecommendationSnapshot).where(
        RecommendationSnapshot.id == snapshot_id, RecommendationSnapshot.need_id == need_id))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        if all(value is None for value in (snapshot.algorithm_version, snapshot.weights, snapshot.ordered_items)):
            # Preserve recorded ranks; never infer missing algorithm/components.
            rows = session.scalars(select(RecommendationItem).where(
                RecommendationItem.snapshot_id == snapshot.id).order_by(
                RecommendationItem.rank.asc().nulls_last(), RecommendationItem.candidate_id, RecommendationItem.id))
            items = tuple(ItemDTO(candidate=CandidateDTO(id=row.candidate_id), rank=row.rank,
                                  score=row.score, components=None) for row in rows)
            version, weights = None, None
        else:
            payload = SnapshotPayload.model_validate({"algorithmVersion": snapshot.algorithm_version,
                       "weights": snapshot.weights, "items": snapshot.ordered_items})
            items, version, weights = payload.items, payload.algorithmVersion, payload.weights
    except (ValidationError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail="Saved snapshot unavailable") from None
    # Historical reading is NOT certification or a new selection. Revocation must
    # still prevent disclosure; do not silently filter/re-rank the stored result.
    if any(not can_disclose_candidate(session, item.candidate.id) for item in items):
        raise HTTPException(status_code=409, detail="Snapshot disclosure unavailable")
    return SnapshotDTO(id=snapshot.id, needId=need_id, createdAt=snapshot.created_at,
                       algorithmVersion=version, weights=weights, items=items)
