from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, Consent, User
from app.modules.candidate.schemas import (
    CandidateProfilePatch, ConsentDTO, HiringCandidateDTO, SelfCandidateDTO, contact_free,
)

CONSENT_KINDS = {"processing": "privacy", "publication": "publish_profile"}
FIELDS = {"fullName": "full_name", "phone": "phone", "stack": "stack",
          "role": "professional_role", "experienceMonths": "experience_months",
          "softSkills": "soft_skills", "specialization": "specialization",
          "selfDeclaredGrade": "self_declared_grade"}


def get_profile(session: Session, user_id: int) -> CandidateProfile | None:
    return session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))


def consent_state(session: Session, user_id: int) -> ConsentDTO:
    rows = {row.kind: row.granted for row in session.scalars(
        select(Consent).where(Consent.user_id == user_id))}
    return ConsentDTO(**{key: rows.get(kind, False) for key, kind in CONSENT_KINDS.items()})


def eligible_for_employer_search(session: Session, user_id: int) -> bool:
    user = session.get(User, user_id)
    profile = get_profile(session, user_id)
    return bool(user and user.role == "candidate" and profile
                and consent_state(session, user_id).publication
                and profile.privacy_settings.get("publish_profile", True) is True)


def self_profile(session: Session, user: User) -> SelfCandidateDTO:
    profile = get_profile(session, user.id)
    values = {key: getattr(profile, attr) for key, attr in FIELDS.items()} if profile else {}
    privacy = {"showContacts": bool(profile and (profile.privacy_settings or {}).get("show_contacts") is True)}
    from app.modules.assessments.qualification import qualification
    proof = qualification(session, profile.id) if profile else None
    return SelfCandidateDTO(verifiedGrade=profile.verified_grade if proof else None,
                            verifiedSpecialization=profile.verified_specialization if proof else None,
                            email=user.email, **values, privacy=privacy, consents=consent_state(session, user.id),
                            eligibleForEmployerSearch=bool(proof and user.is_verified and eligible_for_employer_search(session, user.id)))


def patch_profile(session: Session, user: User, patch: CandidateProfilePatch) -> SelfCandidateDTO:
    # Serialize first creation and updates for this owner, including consent changes.
    session.execute(select(User.id).where(User.id == user.id).with_for_update()).one()
    profile = get_profile(session, user.id)
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        session.add(profile)
    for key in patch.model_fields_set - {"consents", "privacy"}:
        setattr(profile, FIELDS[key], getattr(patch, key))
    if "showContacts" in patch.privacy.model_fields_set:
        profile.privacy_settings = {**(profile.privacy_settings or {}), "show_contacts": patch.privacy.showContacts}
    for key in patch.consents.model_fields_set:
        granted = getattr(patch.consents, key)
        kind = CONSENT_KINDS[key]
        consent = session.scalar(select(Consent).where(Consent.user_id == user.id, Consent.kind == kind))
        if consent is None:
            consent = Consent(user_id=user.id, kind=kind)
            session.add(consent)
        if consent.granted != granted:
            consent.granted_at = datetime.now(timezone.utc) if granted else None
        consent.granted = granted
        if key == "publication":
            profile.privacy_settings = {**(profile.privacy_settings or {}), "publish_profile": granted}
    session.commit()
    return self_profile(session, user)


def hiring_profile(session: Session, user_id: int) -> HiringCandidateDTO | None:
    """Only this gated projection should feed future employer search/matching."""
    if not eligible_for_employer_search(session, user_id):
        return None
    profile = get_profile(session, user_id)
    return HiringCandidateDTO(
        id=profile.id, fullName=contact_free(profile.full_name),
        stack=tuple(v for v in profile.stack if contact_free(v) is not None),
        role=contact_free(profile.professional_role), experienceMonths=profile.experience_months,
        softSkills=tuple(v for v in profile.soft_skills if contact_free(v) is not None),
        specialization=contact_free(profile.specialization), selfDeclaredGrade=profile.self_declared_grade,
    )
