"""
Entities 15, 16: refresh_tokens + email_verification_tokens
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


# ── Entity 15: refresh_tokens ────────────────────────────────────────────────
class RefreshToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Only the hash is stored — never the raw token
    token_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    device_info: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="refresh_tokens"
    )

    @property
    def is_valid(self) -> bool:
        from datetime import timezone
        now = datetime.now(tz=timezone.utc)
        return self.revoked_at is None and self.expires_at > now

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user={self.user_id} valid={self.is_valid}>"


# ── Entity 16: email_verification_tokens ─────────────────────────────────────
class EmailVerificationToken(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="email_verification_tokens"
    )

    @property
    def is_valid(self) -> bool:
        from datetime import timezone
        now = datetime.now(tz=timezone.utc)
        return self.used_at is None and self.revoked_at is None and self.expires_at > now

    def __repr__(self) -> str:
        return f"<EmailVerificationToken id={self.id} user={self.user_id}>"

