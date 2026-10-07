from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin


class RecommendationSnapshot(CreatedAtMixin, Base):
    __tablename__ = "recommendation_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id"), index=True)


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("recommendation_snapshots.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    score: Mapped[float]
    reason: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None]
