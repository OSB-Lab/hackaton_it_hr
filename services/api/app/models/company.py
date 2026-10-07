from typing import Any

from sqlalchemy import JSON, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin


class Company(CreatedAtMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text)
    contacts: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))


class HiringNeed(CreatedAtMixin, Base):
    __tablename__ = "hiring_needs"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "title", name="uq_hiring_needs_company_title",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str | None]
    stack: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    grade: Mapped[str | None]
    specialization: Mapped[str | None]
    team_description: Mapped[str | None] = mapped_column(Text)
    min_grade: Mapped[str | None]
    optional_skills: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True), default=list)
