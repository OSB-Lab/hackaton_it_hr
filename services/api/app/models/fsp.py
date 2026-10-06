from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin


class FspLink(Base):
    __tablename__ = "fsp_links"
    __table_args__ = (
        CheckConstraint("status IN ('linked', 'no_history')", name="ck_fsp_links_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), unique=True)
    fsp_id: Mapped[str | None] = mapped_column(unique=True)
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(default="no_history", server_default="no_history")


class FspAchievement(CreatedAtMixin, Base):
    __tablename__ = "fsp_achievements"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "discipline", "competition",
            name="uq_fsp_achievements_candidate_discipline_competition",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    discipline: Mapped[str]
    competition: Mapped[str | None]
    result: Mapped[str | None]
    role: Mapped[str | None]
    rank: Mapped[str | None]
