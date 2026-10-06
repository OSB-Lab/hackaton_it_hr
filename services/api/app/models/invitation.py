from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
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
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    title: Mapped[str | None]
    salary_from: Mapped[int]
    salary_to: Mapped[int]
    status: Mapped[str] = mapped_column(default="sent", server_default="sent")


class ContactDisclosure(Base):
    __tablename__ = "contact_disclosures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("invitations.id"), unique=True)
    revealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
