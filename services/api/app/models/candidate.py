from typing import Any
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, text
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
        CheckConstraint("verified_grade IN ('junior', 'middle', 'senior')", name="ck_candidate_verified_grade"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    verified_grade: Mapped[str | None]
    verified_specialization: Mapped[str | None]
    verified_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("test_attempts.id", name="fk_candidate_verified_attempt", use_alter=True))
    last_grade_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    full_name: Mapped[str | None]
    stack: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    grade: Mapped[str | None]
    specialization: Mapped[str | None]
    phone: Mapped[str | None]
    professional_role: Mapped[str | None]
    experience_months: Mapped[int | None]
    soft_skills: Mapped[list[str]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    self_declared_grade: Mapped[str | None]
    privacy_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("'{}'")
    )


class TestAttempt(CreatedAtMixin, Base):
    __tablename__ = "test_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('legacy', 'active', 'submitted')", name="ck_test_attempts_status"),
        CheckConstraint("variant IN ('A', 'B', 'C')", name="ck_test_attempts_variant"),
        Index("uq_test_attempts_active_candidate", "candidate_id", unique=True,
              postgresql_where=text("status = 'active'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    test_id: Mapped[str]
    answers: Mapped[list[Any]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    score: Mapped[float | None]
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    grade: Mapped[str | None]
    specialization: Mapped[str | None]
    requested_grade: Mapped[str | None]
    blueprint_version: Mapped[str | None]
    catalog_version: Mapped[str | None]
    blueprint_checksum: Mapped[str | None]
    catalog_checksum: Mapped[str | None]
    snapshot_schema_version: Mapped[int | None]
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    variant: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="legacy", server_default="legacy")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CompetencyScore(CreatedAtMixin, Base):
    __tablename__ = "competency_scores"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "competency", "source",
            name="uq_competency_scores_candidate_competency_source",
        ),
        CheckConstraint("source IN ('test', 'fsp', 'manual', 'assessment_diagnostic')", name="ck_competency_scores_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    competency: Mapped[str]
    score: Mapped[float]
    source: Mapped[str]
    evidence_count: Mapped[int | None]
    blueprint_version: Mapped[str | None]
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("test_attempts.id"))
