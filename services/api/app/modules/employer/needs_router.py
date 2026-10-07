from fastapi import APIRouter

from app.models import HiringNeed
from app.modules.auth.dependencies import AuthSession
from app.modules.employer.router import EmployerUser
from app.modules.employer.needs_schemas import NeedCreate, NeedDTO, NeedPatch
from app.modules.employer.needs_service import create_need, dto, get_need, owned_needs, update_need

router = APIRouter(prefix="/employer/needs", tags=["employer"])


@router.post("", response_model=NeedDTO, status_code=201)
def create(payload: NeedCreate, user: EmployerUser, session: AuthSession):
    return create_need(session, user.id, payload)


@router.get("", response_model=list[NeedDTO])
def list_own(user: EmployerUser, session: AuthSession):
    return [dto(need) for need in session.scalars(owned_needs(user.id).order_by(HiringNeed.id))]


@router.get("/{need_id}", response_model=NeedDTO)
def read(need_id: int, user: EmployerUser, session: AuthSession):
    return dto(get_need(session, user.id, need_id))


@router.patch("/{need_id}", response_model=NeedDTO)
def update(need_id: int, payload: NeedPatch, user: EmployerUser, session: AuthSession):
    return update_need(session, user.id, need_id, payload)
