from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile
from app.modules.fsp.demo import active_registry, achievements_for
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.validators import validate_grade, validate_skills, validate_specialization
from app.modules.recommendations.service import read_snapshot
from app.modules.recommendations.talent_schemas import (
    TalentCandidateDTO, TalentFilters, TalentItemDTO, TalentViewDTO,
)


def read_items(session: Session, user_id: int, need_id: int, snapshot_id: int,
               filters: TalentFilters) -> TalentViewDTO:
    # Reuse ownership and current disclosure checks BEFORE filtering. A filter
    # cannot bypass consent withdrawal, and foreign snapshots remain 404.
    snapshot = read_snapshot(session, user_id, need_id, snapshot_id)
    if filters.category is not None:
        raise HTTPException(status_code=422, detail={"code": "category_catalog_unavailable"})
    try:
        catalog = CatalogRepository().catalog().document
    except (ValueError, OSError):
        raise HTTPException(status_code=503, detail="Catalog unavailable") from None
    try:
        if filters.specialization is not None:
            validate_specialization(catalog, filters.specialization)
        if filters.grade is not None:
            validate_grade(catalog, filters.grade)
        # A valid but nonmatching combination is an empty result, not a new policy.
        validate_skills(catalog, filters.stack)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

    ids = [item.candidate.id for item in snapshot.items]
    profiles = {p.id: p for p in session.scalars(select(CandidateProfile).where(CandidateProfile.id.in_(ids)))}
    from app.modules.recommendations.ranking import ALGORITHM_VERSION
    from app.modules.recommendations.similar_service import SIMILAR_VERSION
    if snapshot.algorithmVersion in (ALGORITHM_VERSION, SIMILAR_VERSION):
        achieved = {item.candidate.id for item in snapshot.items
                    if item.components and item.components.fspBonus > 0}
    else:
        try:
            registry = active_registry()
        except ValueError:
            raise HTTPException(status_code=503, detail="Synthetic FSP registry unavailable") from None
        achieved = {pid for pid in ids if achievements_for(session, pid, registry)}
    specializations = {s.id for s in catalog.specializations}
    skills = {s.id for s in catalog.skills}
    items = []
    for item in snapshot.items:
        profile = profiles.get(item.candidate.id)
        if profile is None:
            raise HTTPException(status_code=409, detail="Snapshot disclosure unavailable")
        from app.modules.assessments.qualification import qualification
        proof = qualification(session, profile.id)
        candidate = TalentCandidateDTO(
            grade=profile.verified_grade if proof else None,
            id=profile.id,
            specialization=(profile.verified_specialization if proof else
                            profile.specialization if profile.specialization in specializations else None),
            stack=tuple(dict.fromkeys(skill for skill in profile.stack if skill in skills)),
            hasFspAchievements=profile.id in achieved,
        )
        if filters.grade is not None and candidate.grade != filters.grade:
            continue
        if filters.specialization is not None and candidate.specialization != filters.specialization:
            continue
        if not set(filters.stack) <= set(candidate.stack):
            continue
        if (filters.hasFspAchievements is not None
                and candidate.hasFspAchievements != filters.hasFspAchievements):
            continue
        items.append(TalentItemDTO.model_validate({**item.model_dump(mode="json"),
                                                   "candidate": candidate.model_dump(mode="json")}))
    return TalentViewDTO(baseSnapshotId=snapshot.id, needId=need_id, items=tuple(items))
