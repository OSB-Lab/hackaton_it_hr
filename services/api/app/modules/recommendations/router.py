from typing import Annotated

from fastapi import APIRouter, Query

from app.modules.auth.dependencies import AuthSession
from app.modules.employer.router import EmployerUser
from app.modules.recommendations.schemas import SnapshotDTO
from app.modules.recommendations.service import create_snapshot, read_snapshot
from app.modules.recommendations.talent_schemas import TalentFilters, TalentViewDTO
from app.modules.recommendations.talent_service import read_items

router = APIRouter(prefix="/employer/needs/{need_id}/recommendations", tags=["recommendations"])


@router.post("", response_model=SnapshotDTO, responses={503: {"description": "Ranking unavailable"}})
def create(need_id: int, user: EmployerUser, session: AuthSession):
    return create_snapshot(session, user.id, need_id)


@router.get("/{snapshot_id}", response_model=SnapshotDTO,
            responses={409: {"description": "Snapshot disclosure unavailable"}})
def read(need_id: int, snapshot_id: int, user: EmployerUser, session: AuthSession):
    return read_snapshot(session, user.id, need_id, snapshot_id)


@router.get("/{snapshot_id}/items", response_model=TalentViewDTO,
            responses={409: {"description": "Snapshot disclosure unavailable"}})
def talent_items(need_id: int, snapshot_id: int, user: EmployerUser, session: AuthSession,
                 filters: Annotated[TalentFilters, Query()]):
    return read_items(session, user.id, need_id, snapshot_id, filters)
