from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.models import User
from app.modules.auth.dependencies import AuthSession, current_user
from app.modules.candidate.router import CandidateUser
from app.modules.employer.router import EmployerUser
from app.modules.invitations import service
from app.modules.invitations.schemas import InvitationCreate, InvitationDTO, InvitationDetailDTO

router = APIRouter(prefix="/invitations", tags=["invitations"])
AuthenticatedUser = Annotated[User, Depends(current_user)]


@router.post("", response_model=InvitationDTO, status_code=201)
def create(payload: InvitationCreate, user: EmployerUser, session: AuthSession):
    return service.create(session, user, payload)


@router.get("", response_model=list[InvitationDTO])
def list_own(user: AuthenticatedUser, session: AuthSession):
    return service.list_own(session, user)


@router.get("/{invitation_id}", response_model=InvitationDetailDTO)
def detail(invitation_id: int, user: AuthenticatedUser, session: AuthSession, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.detail(session, user, invitation_id)


@router.post("/{invitation_id}/accept", response_model=InvitationDTO)
def accept(invitation_id: int, user: CandidateUser, session: AuthSession):
    return service.transition(session, user, invitation_id, "accepted")


@router.post("/{invitation_id}/decline", response_model=InvitationDTO)
def decline(invitation_id: int, user: CandidateUser, session: AuthSession):
    return service.transition(session, user, invitation_id, "rejected")
