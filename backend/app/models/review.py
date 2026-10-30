"""
Entities 10, 11: reviews + review_reports
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from app.models.enums import ReviewReportReason, ReviewReportStatus, ReviewStatus


class Review(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "reviews"

    __table_args__ = (
        # Only one active published review per customer per garage
        sa.Index(
            "uq_active_customer_garage_review",
            "garage_id",
            "customer_id",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND status = 'PUBLISHED'"),
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating_range"),
    )

    garage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("garages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rating: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(sa.String(2000), nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        sa.Enum(ReviewStatus, name="review_status"),
        default=ReviewStatus.PUBLISHED,
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    garage: Mapped["Garage"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Garage", back_populates="reviews"
    )
    customer: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="reviews", foreign_keys=[customer_id]
    )
    removed_by_admin: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[removed_by]
    )
    reports: Mapped[list["ReviewReport"]] = relationship(
        "ReviewReport", back_populates="review"
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} garage={self.garage_id} rating={self.rating}>"


class ReviewReport(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "review_reports"

    __table_args__ = (
        # One report per reporter per review
        sa.UniqueConstraint("review_id", "reporter_id", name="uq_review_reporter"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("reviews.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[ReviewReportReason] = mapped_column(
        sa.Enum(ReviewReportReason, name="review_report_reason"),
        nullable=False,
    )
    details: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[ReviewReportStatus] = mapped_column(
        sa.Enum(ReviewReportStatus, name="review_report_status"),
        default=ReviewReportStatus.PENDING,
        nullable=False,
        index=True,
    )
    admin_note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    review: Mapped[Review] = relationship("Review", back_populates="reports")
    reporter: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", back_populates="review_reports", foreign_keys=[reporter_id]
    )
    reviewed_by_admin: Mapped["User | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User", foreign_keys=[reviewed_by]
    )

    def __repr__(self) -> str:
        return f"<ReviewReport id={self.id} review={self.review_id} status={self.status}>"

