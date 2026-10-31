from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.garage import Garage


class GarageStaff(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "garage_staff"

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    phone: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    role_title: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.true(), nullable=False
    )

    garage: Mapped["Garage"] = relationship("Garage", back_populates="staff")
