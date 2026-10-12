"""One authoritative qualification: profile pointer to its certifying attempt."""
import json
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.models import CandidateProfile, CompetencyScore, TestAttempt
from app.modules.assessments.schemas import AttemptSnapshot, ResultDTO
from app.modules.catalog.repository import decode


def qualification(session, candidate_id):
    profile = session.get(CandidateProfile, candidate_id)
    if not profile or not profile.verified_attempt_id or not profile.verified_grade or not profile.last_grade_change_at:
        return None
    attempt = session.get(TestAttempt, profile.verified_attempt_id)
    if not attempt or attempt.candidate_id != profile.id or attempt.status != "submitted" or not attempt.submitted_at:
        return None
    try:
        snapshot = decode(AttemptSnapshot, json.dumps(attempt.snapshot))
        result = ResultDTO.model_validate(attempt.result)
        if (snapshot.blueprint.schemaVersion != 3
                or result.outcome not in ("pass", "high")
                or result.correctTechnical is None or result.correctTechnical < 13
                or any(result.subscores.get(s, -1) < 50 for s in
                       {tag for slot in snapshot.blueprint.slots for tag in slot.skillTags} - {"teamwork"})
                or (profile.verified_specialization, profile.verified_grade) !=
                   (snapshot.blueprint.specialization, snapshot.blueprint.grade)
                or (attempt.specialization, attempt.requested_grade, attempt.blueprint_version, attempt.catalog_version) !=
                   (snapshot.blueprint.specialization, snapshot.blueprint.grade, snapshot.blueprint.version, snapshot.catalog.version)):
            return None
        return profile, attempt, snapshot
    except (ValueError, TypeError):
        return None


def matches_need(session, candidate_id, need):
    proof = qualification(session, candidate_id)
    if proof is None:
        return False
    profile, _, snapshot = proof
    order = {g.id: g.order for g in snapshot.catalog.grades}
    return (profile.verified_specialization == need.specialization and
            (need.min_grade is None or (need.min_grade in order and
             order[profile.verified_grade] >= order[need.min_grade])))


def available_at(profile):
    return (profile.last_grade_change_at + timedelta(days=get_settings().ASSESSMENT_COOLDOWN_DAYS)
            if profile.last_grade_change_at else None)


def check_start(profile, request, catalog, now):
    if not profile.verified_grade:
        return
    if profile.verified_specialization != request.specialization:
        raise HTTPException(409, "Specialization change policy unavailable")
    grades = [g.id for g in sorted(catalog.grades, key=lambda g: g.order)]
    current, requested = grades.index(profile.verified_grade), grades.index(request.grade)
    if requested > current + 1:
        raise HTTPException(422, "Only the adjacent higher grade is available")
    until = available_at(profile)
    if requested >= current and until and now < until:
        raise HTTPException(409, {"code": "assessment_cooldown", "retest_available_at": until.isoformat()})


def apply_result(session, profile, attempt, snapshot, result):
    """Called once under profile + attempt locks in the submit transaction."""
    blueprint = snapshot.blueprint
    if blueprint.schemaVersion != 3:
        return
    grades = [g.id for g in sorted(snapshot.catalog.grades, key=lambda g: g.order)]
    index = grades.index(blueprint.grade)
    for skill, score in result.subscores.items():
        source = "assessment_diagnostic" if skill == "teamwork" else "test"
        row = session.scalar(select(CompetencyScore).where(
            CompetencyScore.candidate_id == profile.id, CompetencyScore.competency == skill,
            CompetencyScore.source == source))
        if row is None:
            row = CompetencyScore(candidate_id=profile.id, competency=skill, source=source)
            session.add(row)
        row.score, row.evidence_count = score, result.evidenceCounts[skill]
        row.blueprint_version, row.attempt_id = blueprint.version, attempt.id
    if result.outcome != "fail" and (not profile.verified_grade or index > grades.index(profile.verified_grade)):
        if profile.verified_specialization not in (None, blueprint.specialization):
            raise HTTPException(409, "Specialization change policy unavailable")
        profile.verified_grade = blueprint.grade
        profile.verified_specialization = blueprint.specialization
        profile.verified_attempt_id = attempt.id
        profile.last_grade_change_at = attempt.submitted_at
    result.verifiedGrade = profile.verified_grade
    result.verifiedSpecialization = profile.verified_specialization
    result.retestAvailableAt = available_at(profile)
    if result.outcome == "fail" and not profile.verified_grade and index > 0:
        result.retestOffer, result.retestTargetGrade = "lower_retest_offered", grades[index - 1]
    elif result.outcome == "high" and index + 1 < len(grades):
        # An offer is not an exemption from cooldown or blueprint availability.
        result.retestOffer, result.retestTargetGrade = "higher_retest_offered", grades[index + 1]
