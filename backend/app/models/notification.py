"""
Entity 12: notifications
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import NotificationType


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(
        sa.Enum(NotificationType, name="notification_type"),
        nullable=False,
        index=True,
    )
    related_entity_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="notifications"
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user={self.user_id} type={self.notification_type}>"

