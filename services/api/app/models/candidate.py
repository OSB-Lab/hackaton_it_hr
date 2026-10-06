from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin, UpdatedAtMixin


class CandidateProfile(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint(
            "grade IN ('junior', 'middle', 'senior')",
            name="ck_candidate_profiles_grade",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str | None]
    stack: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    grade: Mapped[str | None]
    specialization: Mapped[str | None]
    privacy_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'")
    )


class TestAttempt(CreatedAtMixin, Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    test_id: Mapped[str]
    answers: Mapped[list[Any]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    score: Mapped[float | None]
    grade: Mapped[str | None]


class CompetencyScore(CreatedAtMixin, Base):
    __tablename__ = "competency_scores"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "competency", "source",
            name="uq_competency_scores_candidate_competency_source",
        ),
        CheckConstraint("source IN ('test', 'fsp', 'manual')", name="ck_competency_scores_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    competency: Mapped[str]
    score: Mapped[float]
    source: Mapped[str]
