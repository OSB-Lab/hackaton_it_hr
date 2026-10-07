from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import CreatedAtMixin


class User(CreatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('candidate', 'employer')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    role: Mapped[str]
    is_verified: Mapped[bool] = mapped_column(default=False, server_default=false())


class Consent(CreatedAtMixin, Base):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_consents_user_kind"),
        CheckConstraint(
            "kind IN ('terms', 'privacy', 'publish_profile')", name="ck_consents_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str]
    granted: Mapped[bool] = mapped_column(default=False, server_default=false())
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(CreatedAtMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str]
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
