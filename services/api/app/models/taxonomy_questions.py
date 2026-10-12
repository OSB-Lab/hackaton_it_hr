"""Immutable, pre-authored taxonomy question forms. No runtime generation."""
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin


class TaxonomyQuestionForm(CreatedAtMixin, Base):
    __tablename__ = 'taxonomy_question_forms'
    __table_args__ = (
        UniqueConstraint('role_id', 'grade_id', 'variant', 'version', name='uq_taxonomy_question_form_identity'),
        CheckConstraint("variant IN ('A', 'B', 'C')", name='ck_taxonomy_question_form_variant'),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[str] = mapped_column(String(64), nullable=False)
    grade_id: Mapped[str] = mapped_column(String(32), nullable=False)
    variant: Mapped[str] = mapped_column(String(1), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    skill_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    questions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('true'))
