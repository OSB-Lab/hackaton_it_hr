from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Company
from app.modules.employer.schemas import CompanyPut


def get_company(session: Session, user_id: int) -> Company | None:
    return session.scalar(select(Company).where(Company.user_id == user_id))


def put_company(session: Session, user_id: int, payload: CompanyPut) -> Company:
    values = payload.model_dump()
    # The unique owner constraint also serializes concurrent first PUT requests.
    statement = insert(Company).values(user_id=user_id, **values)
    statement = statement.on_conflict_do_update(
        index_elements=[Company.user_id], set_=values,
    ).returning(Company)
    company = session.scalars(statement, execution_options={"populate_existing": True}).one()
    session.commit()
    return company
