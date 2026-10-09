from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, HiringNeed
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.validators import validate_grade, validate_skills, validate_specialization
from app.modules.employer.needs_schemas import NeedCreate, NeedDTO, NeedPatch

FIELDS = {"title": "title", "teamDescription": "team_description",
          "specialization": "specialization", "minGrade": "min_grade",
          "targetGrade": "grade", "requiredSkills": "stack", "optionalSkills": "optional_skills"}


def owned_needs(user_id: int):
    return select(HiringNeed).join(Company).where(Company.user_id == user_id)


def get_need(session: Session, user_id: int, need_id: int, *, lock=False) -> HiringNeed:
    statement = owned_needs(user_id).where(HiringNeed.id == need_id)
    if lock:
        statement = statement.with_for_update(of=HiringNeed)
    need = session.scalar(statement)
    if need is None:
        raise HTTPException(status_code=404, detail="Need not found")
    return need


def dto(need: HiringNeed) -> NeedDTO:
    return NeedDTO(id=need.id, **{key: getattr(need, attr) for key, attr in FIELDS.items()})


def validate_values(values: dict, changed: set[str]):
    if not changed & {"specialization", "minGrade", "targetGrade", "requiredSkills", "optionalSkills"}:
        return
    try:
        catalog = CatalogRepository().catalog().document
    except (ValueError, OSError):
        raise HTTPException(status_code=503, detail="Catalog unavailable") from None
    try:
        if changed & {"minGrade", "targetGrade"}:
            for key in ("minGrade", "targetGrade"):
                if values[key] is not None:
                    validate_grade(catalog, values[key])
            order = {g.id: g.order for g in catalog.grades}
            if (values["minGrade"] is not None and values["targetGrade"] is not None
                    and order[values["minGrade"]] > order[values["targetGrade"]]):
                raise ValueError("minGrade must not exceed targetGrade")
        if changed & {"specialization", "requiredSkills", "optionalSkills"}:
            validate_specialization(catalog, values["specialization"])
            required, optional = values["requiredSkills"], values["optionalSkills"] or []
            for skills in (required, optional):
                validate_skills(catalog, skills, values["specialization"])
                if len(skills) != len(set(skills)):
                    raise ValueError("Duplicate skills")
            if set(required) & set(optional):
                raise ValueError("Required and optional skills must not overlap")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


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
    validate_values(payload.model_dump(), set(FIELDS))
    need = HiringNeed(company_id=company.id, **{FIELDS[k]: v for k, v in payload.model_dump().items()})
    session.add(need)
    commit_need(session)
    return dto(need)


def update_need(session: Session, user_id: int, need_id: int, payload: NeedPatch) -> NeedDTO:
    try:
        need = get_need(session, user_id, need_id, lock=True)
        changes = payload.model_dump(exclude_unset=True)
        merged = {key: getattr(need, attr) for key, attr in FIELDS.items()} | changes
        validate_values(merged, set(changes))
        for key, value in changes.items():
            setattr(need, FIELDS[key], value)
        commit_need(session)
        return dto(need)
    except Exception:
        session.rollback()
        raise
