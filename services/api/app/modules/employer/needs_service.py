from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, HiringNeed
from app.modules.employer.needs_schemas import NeedCreate, NeedDTO, NeedPatch

FIELDS = {"title": "title", "teamDescription": "team_description",
          "specialization": "specialization", "minGrade": "min_grade",
          "targetGrade": "grade", "requiredSkills": "stack", "optionalSkills": "optional_skills"}


def owned_needs(user_id: int):
    return select(HiringNeed).join(Company).where(Company.user_id == user_id)


def get_need(session: Session, user_id: int, need_id: int) -> HiringNeed:
    need = session.scalar(owned_needs(user_id).where(HiringNeed.id == need_id))
    if need is None:
        raise HTTPException(status_code=404, detail="Need not found")
    return need


def dto(need: HiringNeed) -> NeedDTO:
    return NeedDTO(id=need.id, **{key: getattr(need, attr) for key, attr in FIELDS.items()})


def commit_need(session: Session):
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if (getattr(error.orig, "sqlstate", None) == "23505"
                and getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                == "uq_hiring_needs_company_title"):
            raise HTTPException(status_code=409, detail="Need title already exists") from None
        raise


def create_need(session: Session, user_id: int, payload: NeedCreate) -> NeedDTO:
    company = session.scalar(select(Company).where(Company.user_id == user_id))
    if company is None:
        raise HTTPException(status_code=409, detail="Company required")
    need = HiringNeed(company_id=company.id, **{FIELDS[k]: v for k, v in payload.model_dump().items()})
    session.add(need)
    commit_need(session)
    return dto(need)


def update_need(session: Session, user_id: int, need_id: int, payload: NeedPatch) -> NeedDTO:
    need = get_need(session, user_id, need_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(need, FIELDS[key], value)
    commit_need(session)
    return dto(need)
