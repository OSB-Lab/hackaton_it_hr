from typing import Annotated

from fastapi import APIRouter, Depends

from app.models import User
from app.modules.auth.dependencies import AuthSession, require_role
from app.modules.candidate.schemas import CandidateProfilePatch, SelfCandidateDTO
from app.modules.candidate.service import patch_profile, self_profile

router = APIRouter(prefix="/me/candidate-profile", tags=["candidate"])
CandidateUser = Annotated[User, Depends(require_role("candidate"))]


@router.get("", response_model=SelfCandidateDTO)
def get_my_profile(user: CandidateUser, session: AuthSession) -> SelfCandidateDTO:
    return self_profile(session, user)


@router.patch("", response_model=SelfCandidateDTO)
def update_my_profile(patch: CandidateProfilePatch, user: CandidateUser, session: AuthSession) -> SelfCandidateDTO:
    return patch_profile(session, user, patch)
