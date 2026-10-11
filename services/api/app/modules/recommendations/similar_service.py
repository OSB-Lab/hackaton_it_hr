"""Explicit v4 similar-candidate lane; strict v3 ranking remains untouched."""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, RecommendationItem, RecommendationSnapshot, User
from app.modules.assessments.qualification import qualification
from app.modules.assessments.schemas import ResultDTO
from app.modules.candidate.service import eligible_for_employer_search
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.validators import validate_grade, validate_skills, validate_specialization
from app.modules.employer.needs_service import get_need
from app.modules.fsp.demo import active_registry, achievements_for, score_achievements
from app.modules.recommendations.ranking import WEIGHTS, calculate
from app.modules.recommendations.schemas import CandidateDTO, ItemDTO, SnapshotDTO, SnapshotPayload
from app.modules.recommendations.taxonomy_filter import (
    Candidate, FilterInputError, FilterNeed, SkillRequirement, filter_candidates, load_runtime,
)

SIMILAR_VERSION = "v4-similar-taxonomy-v1"
TAXONOMY_VERSION = "talent-taxonomy-v1"
FILTER_VERSION = "formal-filter-v1"
FACTOR_CODES = ("role", "grade", "experience", "stack", "achievements",
                "salary", "work_format", "location")


class SimilarCriteria(BaseModel):
    """Optional employer refinements; no unsupported salary/format profile inference."""
    model_config = ConfigDict(extra="forbid")
    minExperienceYears: int | None = Field(default=None, ge=0, le=50, strict=True)
    hardSkillIds: list[str] = Field(default_factory=list, max_length=20)


def create_similar_snapshot(session: Session, user_id: int, need_id: int,
                            criteria: SimilarCriteria | None = None) -> SnapshotDTO:
    criteria = criteria or SimilarCriteria()
    need = get_need(session, user_id, need_id, lock=True)
    try:
        catalog = CatalogRepository().catalog().document
        validate_specialization(catalog, need.specialization)
        validate_grade(catalog, need.min_grade)
        required, optional = need.stack, need.optional_skills or []
        validate_skills(catalog, required + optional, need.specialization)
        if not required or "teamwork" in required + optional or len(set(required + optional)) != len(required + optional):
            raise ValueError("Need requires distinct technical skills")
    except (OSError, ValueError, TypeError):
        raise HTTPException(422, "Need requires canonical specialization, grade and technical skills") from None
    try:
        taxonomy, policy = load_runtime()
        registry = active_registry()
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "Taxonomy or synthetic FSP registry unavailable") from None
    filter_need = FilterNeed(role_id=need.specialization, grade_id=need.min_grade,
        min_experience_years=Decimal(criteria.minExperienceYears) if criteria.minExperienceYears is not None else None,
        skills=tuple(SkillRequirement(skill, required=i < len(required))
                     for i, skill in enumerate(required + optional)),
        hard_skill_ids=frozenset(criteria.hardSkillIds))
    try:
        # Fail fast even for an empty cohort; taxonomy must know every requested concept.
        filter_candidates(filter_need, (), taxonomy, policy)
    except FilterInputError:
        raise HTTPException(422, "Unknown or inconsistent taxonomy criteria") from None
    as_of = date.today()
    # Preserve the strict lane's lock order: User before CandidateProfile.
    users = session.scalars(select(User).where(User.role == "candidate").order_by(User.id).with_for_update()).all()
    candidates, proof_by_id = [], {}
    for user in users:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id).with_for_update())
        if not profile or not user.is_verified or not eligible_for_employer_search(session, user.id):
            continue
        proof = qualification(session, profile.id)
        if proof is None:
            continue
        _, attempt, saved = proof
        try:
            result = ResultDTO.model_validate(attempt.result)
            technical = {tag for slot in saved.blueprint.slots for tag in slot.skillTags} - {"teamwork"}
            evidence = {skill: result.subscores[skill] for skill in technical
                        if (result.evidenceCounts or {}).get(skill, 0) > 0}
            verified_skills = tuple(skill for skill, value in evidence.items() if value >= 50)
            candidates.append(Candidate(candidate_id=str(profile.id),
                role_ids=(profile.verified_specialization,), grade_id=profile.verified_grade,
                experience_years=Decimal(profile.experience_months) / 12 if profile.experience_months is not None else None,
                skill_ids=verified_skills))
            proof_by_id[str(profile.id)] = (profile, result, evidence)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(503, "Certified evidence unavailable") from None
    try:
        filtered = filter_candidates(filter_need, candidates, taxonomy, policy)
    except FilterInputError:
        raise HTTPException(503, "Filtering unavailable") from None
    items = []
    for selected in filtered.selected:
        profile, result, evidence = proof_by_id[selected.candidate_id]
        try:
            bonus = score_achievements(achievements_for(session, profile.id, registry), required, as_of)
            quality, components, reasons = calculate(required, optional, evidence, result.technicalTotal,
                                                      fsp_bonus=bonus)
        except ValueError:
            raise HTTPException(503, "Certified evidence unavailable") from None
        # Stack selects the broad cohort; verified skillFit already scores skills.
        # FSP is scored once inside quality, never as a retrieval penalty/boost.
        ranking_fit = Decimal(1)
        for factor in selected.factors:
            if factor.code not in ("stack", "achievements"):
                ranking_fit *= factor.coefficient
        items.append(ItemDTO(candidate=CandidateDTO(id=profile.id), rank=1,
            score=float(Decimal(str(quality)) * ranking_fit), components=components,
            qualityScore=quality, filterFit=float(selected.filter_fit), rankingFit=float(ranking_fit),
            filterFactors=tuple(dict(code=f.code, coefficient=float(f.coefficient), reason=f.reason)
                                for f in selected.factors),
            taxonomyVersion=TAXONOMY_VERSION, filterPolicyVersion=FILTER_VERSION, reasons=reasons))
    items.sort(key=lambda item: (-item.score, -item.qualityScore, -item.filterFit,
                                 -item.components.assessmentStrength, item.candidate.id))
    payload = SnapshotPayload(algorithmVersion=SIMILAR_VERSION, weights=WEIGHTS,
        items=tuple(item.model_copy(update={"rank": i}) for i, item in enumerate(items, 1)))
    row = RecommendationSnapshot(need_id=need.id, algorithm_version=payload.algorithmVersion,
        weights=payload.weights.model_dump(), ordered_items=[item.model_dump(mode="json") for item in payload.items])
    try:
        session.add(row)
        session.flush()
        session.add_all([RecommendationItem(snapshot_id=row.id, candidate_id=item.candidate.id,
            score=item.score, rank=item.rank, reason="; ".join(item.reasons)) for item in payload.items])
        response = SnapshotDTO(id=row.id, needId=need.id, createdAt=row.created_at,
            algorithmVersion=payload.algorithmVersion, weights=payload.weights, items=payload.items)
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
