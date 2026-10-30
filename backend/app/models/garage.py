"""
Entities 2, 3: garages + garage_registration_history
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApprovalStatus, RegistrationHistoryStatus


class Garage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "garages"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    phone: Mapped[str] = mapped_column(sa.String(20), nullable=False)          # E.164
    address: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    location: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    timezone: Mapped[str] = mapped_column(sa.String(64), nullable=False)       # IANA tz
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        sa.Enum(ApprovalStatus, name="approval_status"),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )
    is_suspended: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    is_temporarily_unavailable: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, nullable=False
    )
    temporary_unavailability_message: Mapped[str | None] = mapped_column(
        sa.String(300), nullable=True
    )
    registration_version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="garage", foreign_keys=[owner_id]
    )
    registration_history: Mapped[list["GarageRegistrationHistory"]] = relationship(
        "GarageRegistrationHistory", back_populates="garage", order_by="GarageRegistrationHistory.submitted_at"
    )
    operating_hours: Mapped[list["OperatingHours"]] = relationship(
        "OperatingHours", back_populates="garage", order_by="OperatingHours.day_of_week"
    )
    photos: Mapped[list["GaragePhoto"]] = relationship(
        "GaragePhoto", back_populates="garage", order_by="GaragePhoto.display_order"
    )
    reviews: Mapped[list["Review"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Review", back_populates="garage"
    )
    analytics_events: Mapped[list["AnalyticsEvent"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "AnalyticsEvent", back_populates="garage"
    )
    profile_change_requests: Mapped[list["GarageProfileChangeRequest"]] = relationship(
        "GarageProfileChangeRequest", back_populates="garage"
    )
    garage_services: Mapped[list["GarageService"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GarageService", back_populates="garage"
    )
    garage_vehicle_types: Mapped[list["GarageVehicleType"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GarageVehicleType", back_populates="garage"
    )

    def __repr__(self) -> str:
        return f"<Garage id={self.id} name={self.name} status={self.approval_status}>"


class GarageRegistrationHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "garage_registration_history"

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[RegistrationHistoryStatus] = mapped_column(
        sa.Enum(RegistrationHistoryStatus, name="reg_history_status"),
        nullable=False,
    )
    # Immutable JSONB snapshot of submitted fields
    submission_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped[Garage] = relationship("Garage", back_populates="registration_history")
    reviewer: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[reviewed_by]
    )

    def __repr__(self) -> str:
        return f"<GarageRegistrationHistory garage={self.garage_id} status={self.status}>"


class GarageProfileChangeRequest(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "garage_profile_change_requests"

    __table_args__ = (
        # Only one PENDING request per garage at a time
        sa.Index(
            "uq_pending_profile_change",
            "garage_id",
            unique=True,
            postgresql_where=sa.text("status = 'PENDING'"),
        ),
    )

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposed_changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), default="PENDING", nullable=False, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped[Garage] = relationship("Garage", back_populates="profile_change_requests")
    submitted_by_user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="submitted_profile_change_requests",
        foreign_keys=[submitted_by],
    )
    reviewed_by_user: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[reviewed_by]
    )

    def __repr__(self) -> str:
        return f"<GarageProfileChangeRequest garage={self.garage_id} status={self.status}>"

