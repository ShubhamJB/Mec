"""
Entities 4-8: services, garage_services, vehicle_types, garage_vehicle_types, operating_hours
"""
from __future__ import annotations

import uuid
from datetime import time

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


# ── Entity 4: services ────────────────────────────────────────────────────────
class Service(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "services"

    __table_args__ = (
        # Normalized case-insensitive uniqueness enforced in application + this index
        sa.Index("uq_service_name_normalized", sa.func.lower(sa.func.trim(sa.text("name"))), unique=True),
    )

    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    is_predefined: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    created_by: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="created_services"
    )
    garage_services: Mapped[list["GarageService"]] = relationship(
        "GarageService", back_populates="service"
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name}>"


# ── Entity 5: garage_services (junction) ──────────────────────────────────────
class GarageService(Base):
    __tablename__ = "garage_services"

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("services.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="garage_services"
    )
    service: Mapped[Service] = relationship("Service", back_populates="garage_services")


# ── Entity 6: vehicle_types ───────────────────────────────────────────────────
class VehicleType(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vehicle_types"

    __table_args__ = (
        sa.Index("uq_vehicle_type_name_normalized", sa.func.lower(sa.func.trim(sa.text("name"))), unique=True),
    )

    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    is_predefined: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    created_by: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="created_vehicle_types"
    )
    garage_vehicle_types: Mapped[list["GarageVehicleType"]] = relationship(
        "GarageVehicleType", back_populates="vehicle_type"
    )

    def __repr__(self) -> str:
        return f"<VehicleType id={self.id} name={self.name}>"


# ── Entity 7: garage_vehicle_types (junction) ─────────────────────────────────
class GarageVehicleType(Base):
    __tablename__ = "garage_vehicle_types"

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    vehicle_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("vehicle_types.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="garage_vehicle_types"
    )
    vehicle_type: Mapped[VehicleType] = relationship(
        "VehicleType", back_populates="garage_vehicle_types"
    )


# ── Entity 8: operating_hours ─────────────────────────────────────────────────
class OperatingHours(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "operating_hours"

    __table_args__ = (
        # Unique day per garage
        sa.UniqueConstraint("garage_id", "day_of_week", name="uq_operating_hours_day"),
        # day_of_week 1=Monday .. 7=Sunday
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_operating_hours_day_range"),
        # Open day must have both times, closed day must have neither
        sa.CheckConstraint(
            "(is_closed = true AND opening_time IS NULL AND closing_time IS NULL) OR "
            "(is_closed = false AND opening_time IS NOT NULL AND closing_time IS NOT NULL AND opening_time < closing_time)",
            name="ck_operating_hours_times",
        ),
    )

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)  # 1–7
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    opening_time: Mapped[time | None] = mapped_column(sa.Time, nullable=True)
    closing_time: Mapped[time | None] = mapped_column(sa.Time, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="operating_hours"
    )

    def __repr__(self) -> str:
        return f"<OperatingHours garage={self.garage_id} day={self.day_of_week} closed={self.is_closed}>"

