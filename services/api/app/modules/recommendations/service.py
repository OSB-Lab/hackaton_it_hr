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
    get_need(session, user_id, need_id)
    # No flush/commit, empty snapshot or fallback algorithm.
    raise HTTPException(status_code=503, detail={"code": "ranking_unavailable",
                        "message": "Verified qualification and approved ranking specification are required"})


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
