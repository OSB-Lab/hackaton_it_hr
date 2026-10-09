from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.models import User
from app.modules.auth.dependencies import AuthSession, require_role
from app.modules.assessments.schemas import AttemptDTO, StartRequest, SubmitDTO, SubmitRequest
from app.modules.assessments.service import read_attempt, start_attempt, submit_attempt

router = APIRouter(prefix="/assessments", tags=["assessments"])
CandidateUser = Annotated[User, Depends(require_role("candidate"))]


@router.post("/start", response_model=AttemptDTO, status_code=201,
             responses={200: {"model": AttemptDTO, "description": "Existing active attempt"}})
def start(request: StartRequest, response: Response, user: CandidateUser, session: AuthSession):
    attempt, created = start_attempt(session, user.id, request)
    response.status_code = 201 if created else 200
    return attempt


@router.get("/{attempt_id}", response_model=AttemptDTO)
def read(attempt_id: int, user: CandidateUser, session: AuthSession):
    return read_attempt(session, user.id, attempt_id)


@router.post("/{attempt_id}/submit", response_model=SubmitDTO)
def submit(attempt_id: int, request: SubmitRequest, user: CandidateUser, session: AuthSession):
    return submit_attempt(session, user.id, attempt_id, request)
