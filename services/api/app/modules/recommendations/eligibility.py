"""Read-only formal eligibility policy; never computes RankScore."""
from math import isfinite

from pydantic import BaseModel, ConfigDict

from app.models import CandidateProfile, User
from app.modules.assessments.qualification import qualification, matches_need
from app.modules.candidate.service import eligible_for_employer_search

POLICY_VERSION = "required-skills-v1"
REQUIRED_SKILL_MIN_PERCENT = 50.0
HIDDEN_REASONS = frozenset({"PROFILE_UNAVAILABLE", "EMAIL_UNVERIFIED",
                          "PUBLICATION_NOT_ALLOWED", "QUALIFICATION_UNCONFIRMED"})


class EligibilityDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    eligible: bool
    reasonCodes: tuple[str, ...]
    missingRequiredSkills: tuple[str, ...]
    policyVersion: str = POLICY_VERSION


def required_skill_failures(required, result, blueprint):
    """Use only canonical technical tags of the certifying blueprint.

    subscores are percentages, evidenceCounts are question counts. Reject invalid
    raw JSON types before Pydantic can coerce bool/strings into numbers.
    """
    technical = {tag for slot in blueprint.slots for tag in slot.skillTags} - {"teamwork"}
    scores, counts = result.get("subscores"), result.get("evidenceCounts")
    reasons, missing = [], []
    for skill in sorted(set(required)):
        code = None
        if (skill not in technical or not isinstance(scores, dict) or not isinstance(counts, dict)
                or skill not in scores or skill not in counts):
            code = "REQUIRED_SKILL_EVIDENCE_MISSING"
        else:
            value, count = scores[skill], counts[skill]
            expected = sum(skill in slot.skillTags for slot in blueprint.slots)
            if (type(count) is not int or count <= 0 or count != expected
                    or type(value) not in (int, float)
                    or not isfinite(value) or not 0 <= value <= 100
                    or abs(value * count / 100 - round(value * count / 100)) > 1e-8):
                code = "REQUIRED_SKILL_EVIDENCE_INVALID"
            elif value < REQUIRED_SKILL_MIN_PERCENT:
                code = "REQUIRED_SKILL_BELOW_THRESHOLD"
        if code:
            missing.append(skill)
            if code not in reasons:
                reasons.append(code)
    return reasons, missing


def evaluate_candidate(session, candidate_id, need=None):
    profile = session.get(CandidateProfile, candidate_id)
    user = session.get(User, profile.user_id) if profile else None
    reasons, missing = [], []
    if not user or user.role != "candidate":
        reasons.append("PROFILE_UNAVAILABLE")
    else:
        if not user.is_verified:
            reasons.append("EMAIL_UNVERIFIED")
        if not eligible_for_employer_search(session, user.id):
            reasons.append("PUBLICATION_NOT_ALLOWED")
        proof = qualification(session, candidate_id)
        if proof is None:
            reasons.append("QUALIFICATION_UNCONFIRMED")
        elif need is not None:
            _, attempt, snapshot = proof
            if profile.verified_specialization != need.specialization:
                reasons.append("SPECIALIZATION_MISMATCH")
            elif not matches_need(session, candidate_id, need):
                reasons.append("GRADE_BELOW_MINIMUM")
            skill_reasons, missing = required_skill_failures(need.stack, attempt.result, snapshot.blueprint)
            reasons.extend(skill_reasons)
    return EligibilityDTO(eligible=not reasons, reasonCodes=tuple(reasons),
                          missingRequiredSkills=tuple(missing))
