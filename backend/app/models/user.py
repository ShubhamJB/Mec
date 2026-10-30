"""
Entity 1: users
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AccountStatus, UserRole


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        sa.String(254),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(UserRole, name="user_role"),
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(
        sa.Enum(AccountStatus, name="account_status"),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="owner", uselist=False, foreign_keys="Garage.owner_id"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Review", back_populates="customer", foreign_keys="Review.customer_id"
    )
    review_reports: Mapped[list["ReviewReport"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ReviewReport", back_populates="reporter", foreign_keys="ReviewReport.reporter_id"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Notification", back_populates="user"
    )
    admin_actions: Mapped[list["AdminAction"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "AdminAction", back_populates="admin"
    )
    created_services: Mapped[list["Service"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Service", back_populates="created_by"
    )
    created_vehicle_types: Mapped[list["VehicleType"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "VehicleType", back_populates="created_by"
    )
    submitted_profile_change_requests: Mapped[list["GarageProfileChangeRequest"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GarageProfileChangeRequest",
        back_populates="submitted_by_user",
        foreign_keys="GarageProfileChangeRequest.submitted_by",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"

