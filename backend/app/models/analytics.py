"""
Entities 13, 14: analytics_events + admin_actions
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import AdminActionType, AnalyticsEventType


# ── Entity 13: analytics_events ───────────────────────────────────────────────
class AnalyticsEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "analytics_events"

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[AnalyticsEventType] = mapped_column(
        sa.Enum(AnalyticsEventType, name="analytics_event_type"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="analytics_events"
    )
    customer: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[customer_id]
    )

    def __repr__(self) -> str:
        return f"<AnalyticsEvent id={self.id} garage={self.garage_id} type={self.event_type}>"


# ── Entity 14: admin_actions (append-only audit log) ─────────────────────────
class AdminAction(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "admin_actions"

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[AdminActionType] = mapped_column(
        sa.Enum(AdminActionType, name="admin_action_type"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    admin: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="admin_actions"
    )

    def __repr__(self) -> str:
        return f"<AdminAction id={self.id} type={self.action_type} target={self.target_id}>"

