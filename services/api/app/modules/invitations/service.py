from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, CandidateProfile, Company, ContactDisclosure, Invitation, User
from app.modules.recommendations import service as eligibility
from app.modules.candidate.service import consent_state
from app.modules.invitations.schemas import ContactsDTO, InvitationCreate, InvitationDTO, InvitationDetailDTO


def public_status(status: str) -> str:
    return "declined" if status == "rejected" else status


def dto(row: Invitation) -> InvitationDTO:
    return InvitationDTO(id=row.id, companyId=row.company_id, candidateId=row.candidate_id,
                         offerDescription=row.title, contactMethod=row.contact_method,
                         salaryMin=row.salary_from, salaryMax=row.salary_to, currency=row.currency,
                         status=public_status(row.status), createdAt=row.created_at, updatedAt=row.updated_at)


def owned(user: User):
    if user.role == "employer":
        return select(Invitation).join(Company).where(Company.user_id == user.id)
    return select(Invitation).join(CandidateProfile).where(CandidateProfile.user_id == user.id)


def get_owned(session: Session, user: User, invitation_id: int) -> Invitation:
    row = session.scalar(owned(user).where(Invitation.id == invitation_id).with_for_update(of=Invitation))
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return row


def audit(session: Session, actor: int, row: Invitation, action: str, before: str | None):
    session.add(AuditEvent(user_id=actor, action="invitation." + action,
                payload={"invitationId": row.id, "from": public_status(before) if before else None,
                         "to": public_status(row.status)}))


def create(session: Session, user: User, payload: InvitationCreate) -> InvitationDTO:
    try:
        # Stable company lock serializes pair creation; partial index also protects
        # against independent SQL writers. User lock coordinates privacy PATCH.
        company = session.scalar(select(Company).where(Company.id == payload.companyId,
                                  Company.user_id == user.id).with_for_update())
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        candidate_user = session.scalar(select(User).join(CandidateProfile).where(
            CandidateProfile.id == payload.candidateId).with_for_update(of=User))
        if candidate_user is None or not eligibility.can_disclose_candidate(session, payload.candidateId):
            raise HTTPException(status_code=404, detail="Candidate unavailable")
        if not eligibility.has_verified_qualification(session, payload.candidateId):
            raise HTTPException(status_code=503, detail={"code": "verified_qualification_unavailable"})
        active = session.scalar(select(Invitation.id).where(Invitation.company_id == company.id,
                 Invitation.candidate_id == payload.candidateId, Invitation.status.in_(("sent", "viewed"))))
        if active is not None:
            raise HTTPException(status_code=409, detail="Active invitation already exists")
        row = Invitation(company_id=company.id, candidate_id=payload.candidateId,
                         title=payload.offerDescription, contact_method=payload.contactMethod,
                         salary_from=payload.salaryMin, salary_to=payload.salaryMax,
                         currency=payload.currency, status="sent")
        session.add(row)
        session.flush()
        audit(session, user.id, row, "created", None)
        result = dto(row)
        session.commit()
        return result
    except IntegrityError as error:
        session.rollback()
        if (getattr(error.orig, "sqlstate", None) == "23505"
                and getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_invitations_active_pair"):
            raise HTTPException(status_code=409, detail="Active invitation already exists") from None
        raise
    except Exception:
        session.rollback()
        raise


def transition(session: Session, user: User, invitation_id: int, target: str) -> InvitationDTO:
    try:
        row = get_owned(session, user, invitation_id)
        if row.status != target:
            if row.status not in ("sent", "viewed"):
                raise HTTPException(status_code=409, detail="Invitation is terminal")
            before = row.status
            row.status = target
            if target == "accepted":
                # Same locked invitation and transaction as acceptance/audit.
                # Candidate and origin company are bound through its immutable FK.
                existing = session.scalar(select(ContactDisclosure.id).where(ContactDisclosure.invitation_id == row.id))
                if existing is None:
                    session.add(ContactDisclosure(invitation_id=row.id))
            audit(session, user.id, row, "accepted" if target == "accepted" else "declined", before)
            session.flush()
        result = dto(row)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def detail(session: Session, user: User, invitation_id: int) -> InvitationDetailDTO:
    try:
        row = get_owned(session, user, invitation_id)
        if user.role == "candidate" and row.status == "sent":
            row.status = "viewed"
            audit(session, user.id, row, "viewed", "sent")
            session.flush()
        contacts = None
        # get_owned already verified current employer -> origin Company ownership.
        # A grant for another invitation/company is never sufficient.
        if (user.role == "employer" and row.status == "accepted"
                and session.scalar(select(ContactDisclosure.id).where(
                    ContactDisclosure.invitation_id == row.id)) is not None):
            profile = session.get(CandidateProfile, row.candidate_id)
            candidate_user = session.scalar(select(User).where(User.id == profile.user_id).with_for_update())
            # Explicit existing privacy flag; never default consent to true.
            session.refresh(profile)
            if (profile.privacy_settings.get("show_contacts") is True
                    and profile.privacy_settings.get("publish_profile") is True
                    and eligibility.can_disclose_candidate(session, profile.id)
                    and consent_state(session, profile.user_id).processing):
                contacts = ContactsDTO(email=candidate_user.email, phone=profile.phone)
        result = InvitationDetailDTO(**dto(row).model_dump(), contacts=contacts)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def list_own(session: Session, user: User) -> list[InvitationDTO]:
    # Lists never disclose contacts and never mark invitations viewed.
    return [dto(row) for row in session.scalars(owned(user).order_by(Invitation.id.desc()))]
