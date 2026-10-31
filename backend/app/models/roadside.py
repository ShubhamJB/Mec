"""Roadside assistance readiness and customer requests."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RoadsideRequestStatus


class RoadsideCapability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roadside_capabilities"

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    is_available: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    service_radius_km: Mapped[int] = mapped_column(sa.SmallInteger, default=10, nullable=False)
    availability_note: Mapped[str | None] = mapped_column(sa.String(300), nullable=True)
    callback_phone: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    response_minutes: Mapped[int] = mapped_column(sa.SmallInteger, default=15, nullable=False)

    garage: Mapped["Garage"] = relationship("Garage")  # type: ignore[name-defined]  # noqa: F821


class RoadsideRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roadside_requests"
    __table_args__ = (
        sa.Index("ix_roadside_requests_garage_status_created", "garage_id", "status", "created_at"),
        sa.Index("ix_roadside_requests_customer_created", "customer_id", "created_at"),
        sa.Index("ix_roadside_requests_expires_at", "expires_at"),
        sa.CheckConstraint("coarse_latitude BETWEEN -90 AND 90", name="ck_roadside_latitude"),
        sa.CheckConstraint("coarse_longitude BETWEEN -180 AND 180", name="ck_roadside_longitude"),
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False
    )
    request_code: Mapped[str] = mapped_column(
        sa.String(12), unique=True, nullable=False, index=True
    )
    status: Mapped[RoadsideRequestStatus] = mapped_column(
        sa.Enum(RoadsideRequestStatus, name="roadside_request_status"),
        default=RoadsideRequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    vehicle_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("vehicle_types.id", ondelete="RESTRICT"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    problem_description: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    location_label: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    coarse_latitude: Mapped[float] = mapped_column(sa.Float, nullable=False)
    coarse_longitude: Mapped[float] = mapped_column(sa.Float, nullable=False)
    private_data_encrypted: Mapped[str] = mapped_column(sa.Text, nullable=False)
    quote_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2), nullable=True)
    quote_currency: Mapped[str | None] = mapped_column(sa.String(3), nullable=True)
    eta_minutes: Mapped[int | None] = mapped_column(sa.SmallInteger, nullable=True)
    customer_contact_confirmed: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    owner_calling_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    contacted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    events: Mapped[list["RoadsideRequestEvent"]] = relationship(
        "RoadsideRequestEvent", back_populates="request", order_by="RoadsideRequestEvent.created_at"
    )


class RoadsideRequestEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "roadside_request_events"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("roadside_requests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    from_status: Mapped[RoadsideRequestStatus | None] = mapped_column(
        sa.Enum(RoadsideRequestStatus, name="roadside_request_status", create_type=False),
        nullable=True,
    )
    to_status: Mapped[RoadsideRequestStatus] = mapped_column(
        sa.Enum(RoadsideRequestStatus, name="roadside_request_status", create_type=False),
        nullable=False,
    )
    safe_metadata: Mapped[dict[str, str] | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    request: Mapped[RoadsideRequest] = relationship("RoadsideRequest", back_populates="events")
