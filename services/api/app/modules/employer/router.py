from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.modules.auth.dependencies import AuthSession, require_role
from app.modules.employer.schemas import CompanyDTO, CompanyPut
from app.modules.employer.service import get_company, put_company

router = APIRouter(prefix="/employer/company", tags=["employer"])
EmployerUser = Annotated[User, Depends(require_role("employer"))]


@router.get("", response_model=CompanyDTO)
def get_my_company(user: EmployerUser, session: AuthSession) -> CompanyDTO:
    company = get_company(session, user.id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyDTO.model_validate(company)


@router.put("", response_model=CompanyDTO)
def put_my_company(payload: CompanyPut, user: EmployerUser, session: AuthSession) -> CompanyDTO:
    return CompanyDTO.model_validate(put_company(session, user.id, payload))
