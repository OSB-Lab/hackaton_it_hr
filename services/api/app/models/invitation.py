from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin, UpdatedAtMixin


class Invitation(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('sent', 'viewed', 'accepted', 'rejected')",
            name="ck_invitations_status",
        ),
        CheckConstraint("salary_from > 0 AND salary_from <> 'NaN'::numeric", name='ck_invitations_salary_positive'),
        CheckConstraint("salary_to >= salary_from AND salary_to <> 'NaN'::numeric", name='ck_invitations_salary_range'),
        CheckConstraint("currency = 'RUB'", name='ck_invitations_currency'),
        Index("uq_invitations_active_pair", "company_id", "candidate_id", unique=True,
              postgresql_where=text("status IN ('sent', 'viewed')")),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    contact_method: Mapped[str | None]
    currency: Mapped[str | None]
    salary_from: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    salary_to: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(default="sent", server_default="sent")


class ContactDisclosure(Base):
    __tablename__ = "contact_disclosures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("invitations.id"), unique=True)
    revealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
