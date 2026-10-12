from typing import Annotated

from fastapi import APIRouter, Depends, Response, HTTPException

from app.models import User
from app.modules.auth.dependencies import AuthSession, require_role
from app.modules.assessments.schemas import AttemptDTO, StartRequest, SubmitDTO, SubmitRequest
from app.modules.assessments.service import read_attempt, start_attempt, submit_attempt
from app.modules.assessments.taxonomy_bank import load_bank
from app.modules.assessments.taxonomy_service import (
    DiagnosticAttempt, read_diagnostic, start_diagnostic, submit_diagnostic,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])
CandidateUser = Annotated[User, Depends(require_role("candidate"))]


@router.post("/start", response_model=AttemptDTO, status_code=201,
             responses={200: {"model": AttemptDTO, "description": "Existing active attempt"}})
def start(request: StartRequest, response: Response, user: CandidateUser, session: AuthSession):
    attempt, created = start_attempt(session, user.id, request)
    response.status_code = 201 if created else 200
    return attempt


@router.get('/taxonomy/catalog')
def taxonomy_catalog(user: CandidateUser, session: AuthSession):
    try:
        bank = load_bank(session)
    except ValueError:
        raise HTTPException(503, 'Question bank unavailable') from None
    roles = sorted({role for role, _ in bank.cells})
    grades = sorted({grade for _, grade in bank.cells})
    return {'version': bank.version,
            'roles': [{'id': role, 'skillCount': len(bank.cell(role, grades[0]).skillIds)} for role in roles],
            'grades': grades}


@router.post('/taxonomy/start', response_model=DiagnosticAttempt, status_code=201,
             responses={200: {'model': DiagnosticAttempt, 'description': 'Existing active diagnostic'}})
def taxonomy_start(request: StartRequest, response: Response, user: CandidateUser, session: AuthSession):
    attempt, created = start_diagnostic(session, user.id, request)
    response.status_code = 201 if created else 200
    return attempt


@router.get('/taxonomy/{attempt_id}', response_model=DiagnosticAttempt)
def taxonomy_read(attempt_id: int, user: CandidateUser, session: AuthSession):
    return read_diagnostic(session, user.id, attempt_id)


@router.post('/taxonomy/{attempt_id}/submit', response_model=SubmitDTO)
def taxonomy_submit(attempt_id: int, request: SubmitRequest, user: CandidateUser, session: AuthSession):
    return submit_diagnostic(session, user.id, attempt_id, request)


@router.get("/{attempt_id}", response_model=AttemptDTO)
def read(attempt_id: int, user: CandidateUser, session: AuthSession):
    return read_attempt(session, user.id, attempt_id)


@router.post("/{attempt_id}/submit", response_model=SubmitDTO)
def submit(attempt_id: int, request: SubmitRequest, user: CandidateUser, session: AuthSession):
    return submit_attempt(session, user.id, attempt_id, request)
