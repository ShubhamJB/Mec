"""
Entity 9: garage_photos
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


class GaragePhoto(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "garage_photos"

    __table_args__ = (
        # Unique display_order per garage among non-deleted photos
        sa.Index(
            "uq_active_photo_order",
            "garage_id",
            "display_order",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    caption: Mapped[str | None] = mapped_column(sa.String(300), nullable=True)
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="photos"
    )

    def __repr__(self) -> str:
        return f"<GaragePhoto id={self.id} garage={self.garage_id} order={self.display_order}>"

