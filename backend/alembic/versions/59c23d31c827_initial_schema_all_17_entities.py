"""initial_schema_all_17_entities

Revision ID: 59c23d31c827
Revises:
Create Date: 2026-10-30

Creates all 17 core entities for Find Your Mechanic MVP.
Requires PostgreSQL with PostGIS and pgcrypto extensions.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "59c23d31c827"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE user_role AS ENUM ('CUSTOMER', 'GARAGE_OWNER', 'ADMIN')")
    op.execute("CREATE TYPE account_status AS ENUM ('ACTIVE', 'SUSPENDED')")
    op.execute("CREATE TYPE approval_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")
    op.execute("CREATE TYPE reg_history_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")
    op.execute("CREATE TYPE review_status AS ENUM ('PUBLISHED', 'REMOVED')")
    op.execute("CREATE TYPE review_report_reason AS ENUM ('SPAM', 'ABUSIVE_CONTENT', 'FAKE_REVIEW', 'IRRELEVANT', 'OTHER')")
    op.execute("CREATE TYPE review_report_status AS ENUM ('PENDING', 'DISMISSED', 'REVIEW_REMOVED')")
    op.execute("CREATE TYPE analytics_event_type AS ENUM ('PROFILE_VIEW', 'CALL_CLICK')")
    op.execute("""
        CREATE TYPE notification_type AS ENUM (
            'EMAIL_VERIFICATION',
            'REGISTRATION_APPROVED', 'REGISTRATION_REJECTED',
            'PROFILE_CHANGE_APPROVED', 'PROFILE_CHANGE_REJECTED',
            'GARAGE_SUSPENDED', 'GARAGE_RESTORED',
            'ACCOUNT_SUSPENDED', 'ACCOUNT_RESTORED',
            'REVIEW_RECEIVED', 'REVIEW_REPORT_RECEIVED', 'REVIEW_REPORT_RESOLVED'
        )
    """)
    op.execute("""
        CREATE TYPE admin_action_type AS ENUM (
            'APPROVE_REGISTRATION', 'REJECT_REGISTRATION',
            'APPROVE_PROFILE_CHANGE', 'REJECT_PROFILE_CHANGE',
            'SUSPEND_GARAGE', 'RESTORE_GARAGE', 'DELETE_GARAGE',
            'SUSPEND_USER', 'RESTORE_USER',
            'DISMISS_REVIEW_REPORT', 'REMOVE_REVIEW'
        )
    """)

    # ── 1. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("CUSTOMER", "GARAGE_OWNER", "ADMIN", name="user_role", create_type=False), nullable=False),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("account_status", sa.Enum("ACTIVE", "SUSPENDED", name="account_status", create_type=False), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── 2. garages ────────────────────────────────────────────────────────────
    op.create_table(
        "garages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("approval_status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="approval_status", create_type=False), nullable=False, server_default="PENDING"),
        sa.Column("is_suspended", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_temporarily_unavailable", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("temporary_unavailability_message", sa.String(300), nullable=True),
        sa.Column("registration_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_garages_owner_id", "garages", ["owner_id"])
    op.create_index("ix_garages_approval_status", "garages", ["approval_status"])
    op.create_index("ix_garages_location", "garages", ["location"], postgresql_using="gist")
    # One non-deleted garage per owner
    op.execute(
        "CREATE UNIQUE INDEX uq_active_garage_per_owner ON garages(owner_id) WHERE deleted_at IS NULL"
    )

    # ── 3. garage_registration_history ───────────────────────────────────────
    op.create_table(
        "garage_registration_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="reg_history_status", create_type=False), nullable=False),
        sa.Column("submission_data", JSONB, nullable=False),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_garage_registration_history_garage_id", "garage_registration_history", ["garage_id"])

    # ── 4. services ───────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_predefined", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_services_is_active", "services", ["is_active"])
    op.execute("CREATE UNIQUE INDEX uq_service_name_normalized ON services(lower(trim(name)))")

    # ── 5. garage_services ────────────────────────────────────────────────────
    op.create_table(
        "garage_services",
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 6. vehicle_types ─────────────────────────────────────────────────────
    op.create_table(
        "vehicle_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_predefined", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_vehicle_types_is_active", "vehicle_types", ["is_active"])
    op.execute("CREATE UNIQUE INDEX uq_vehicle_type_name_normalized ON vehicle_types(lower(trim(name)))")

    # ── 7. garage_vehicle_types ───────────────────────────────────────────────
    op.create_table(
        "garage_vehicle_types",
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("vehicle_type_id", UUID(as_uuid=True), sa.ForeignKey("vehicle_types.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 8. operating_hours ────────────────────────────────────────────────────
    op.create_table(
        "operating_hours",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("is_closed", sa.Boolean, nullable=False),
        sa.Column("opening_time", sa.Time, nullable=True),
        sa.Column("closing_time", sa.Time, nullable=True),
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_operating_hours_day_range"),
        sa.CheckConstraint(
            "(is_closed = true AND opening_time IS NULL AND closing_time IS NULL) OR "
            "(is_closed = false AND opening_time IS NOT NULL AND closing_time IS NOT NULL AND opening_time < closing_time)",
            name="ck_operating_hours_times",
        ),
        sa.UniqueConstraint("garage_id", "day_of_week", name="uq_operating_hours_day"),
    )
    op.create_index("ix_operating_hours_garage_id", "operating_hours", ["garage_id"])

    # ── 9. garage_photos ──────────────────────────────────────────────────────
    op.create_table(
        "garage_photos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("storage_key", name="uq_garage_photos_storage_key"),
    )
    op.create_index("ix_garage_photos_garage_id", "garage_photos", ["garage_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_active_photo_order ON garage_photos(garage_id, display_order) WHERE deleted_at IS NULL"
    )

    # ── 10. reviews ───────────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("comment", sa.String(2000), nullable=True),
        sa.Column("status", sa.Enum("PUBLISHED", "REMOVED", name="review_status", create_type=False), nullable=False, server_default="PUBLISHED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating_range"),
    )
    op.create_index("ix_reviews_garage_id", "reviews", ["garage_id"])
    op.create_index("ix_reviews_customer_id", "reviews", ["customer_id"])
    op.create_index("ix_reviews_status", "reviews", ["status"])
    # One active published review per customer per garage
    op.execute(
        "CREATE UNIQUE INDEX uq_active_customer_garage_review ON reviews(garage_id, customer_id) "
        "WHERE deleted_at IS NULL AND status = 'PUBLISHED'"
    )

    # ── 11. review_reports ────────────────────────────────────────────────────
    op.create_table(
        "review_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("review_id", UUID(as_uuid=True), sa.ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reporter_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reason", sa.Enum("SPAM", "ABUSIVE_CONTENT", "FAKE_REVIEW", "IRRELEVANT", "OTHER", name="review_report_reason", create_type=False), nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("PENDING", "DISMISSED", "REVIEW_REMOVED", name="review_report_status", create_type=False), nullable=False, server_default="PENDING"),
        sa.Column("admin_note", sa.Text, nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("review_id", "reporter_id", name="uq_review_reporter"),
    )
    op.create_index("ix_review_reports_review_id", "review_reports", ["review_id"])
    op.create_index("ix_review_reports_reporter_id", "review_reports", ["reporter_id"])
    op.create_index("ix_review_reports_status", "review_reports", ["status"])

    # ── 12. notifications ─────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("notification_type", sa.Text, nullable=False),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    # ── 13. analytics_events ──────────────────────────────────────────────────
    op.create_table(
        "analytics_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.Enum("PROFILE_VIEW", "CALL_CLICK", name="analytics_event_type", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_events_garage_id", "analytics_events", ["garage_id"])
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])
    op.create_index("ix_analytics_events_created_at", "analytics_events", ["created_at"])

    # ── 14. admin_actions ─────────────────────────────────────────────────────
    op.create_table(
        "admin_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("admin_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action_type", sa.Text, nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_admin_actions_admin_id", "admin_actions", ["admin_id"])
    op.create_index("ix_admin_actions_action_type", "admin_actions", ["action_type"])
    op.create_index("ix_admin_actions_created_at", "admin_actions", ["created_at"])

    # ── 15. refresh_tokens ────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("device_info", sa.String(500), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # ── 16. email_verification_tokens ─────────────────────────────────────────
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("token_hash", name="uq_email_verification_tokens_token_hash"),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])

    # ── 17. garage_profile_change_requests ────────────────────────────────────
    op.create_table(
        "garage_profile_change_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("garage_id", UUID(as_uuid=True), sa.ForeignKey("garages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposed_changes", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_garage_profile_change_requests_garage_id", "garage_profile_change_requests", ["garage_id"])
    op.create_index("ix_garage_profile_change_requests_status", "garage_profile_change_requests", ["status"])
    # Only one PENDING request per garage
    op.execute(
        "CREATE UNIQUE INDEX uq_pending_profile_change ON garage_profile_change_requests(garage_id) "
        "WHERE status = 'PENDING'"
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("garage_profile_change_requests")
    op.drop_table("email_verification_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("admin_actions")
    op.drop_table("analytics_events")
    op.drop_table("notifications")
    op.drop_table("review_reports")
    op.drop_table("reviews")
    op.drop_table("garage_photos")
    op.drop_table("operating_hours")
    op.drop_table("garage_vehicle_types")
    op.drop_table("vehicle_types")
    op.drop_table("garage_services")
    op.drop_table("services")
    op.drop_table("garage_registration_history")
    op.drop_table("garages")
    op.drop_table("users")

    # Drop enums
    for enum_name in [
        "admin_action_type", "notification_type", "analytics_event_type",
        "review_report_status", "review_report_reason", "review_status",
        "reg_history_status", "approval_status", "account_status", "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
