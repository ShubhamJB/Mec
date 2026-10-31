"""add roadside assistance capability and request lifecycle

Revision ID: 4c7b2e91a6df
Revises: a91f0d6c3b42
Create Date: 2026-10-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "4c7b2e91a6df"
down_revision: Union[str, None] = "a91f0d6c3b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE roadside_request_status AS ENUM (
            'PENDING', 'ACCEPTED', 'CONTACTED', 'CONFIRMED', 'IN_PROGRESS',
            'COMPLETED', 'DECLINED', 'EXPIRED', 'CANCELLED', 'UNABLE_TO_SERVE'
        )
    """)
    op.execute("""
        ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ROADSIDE_REQUEST_RECEIVED'
    """)
    op.execute("""
        ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ROADSIDE_REQUEST_UPDATED'
    """)

    op.create_table(
        "roadside_capabilities",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("garage_id", UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("service_radius_km", sa.SmallInteger(), server_default="10", nullable=False),
        sa.Column("availability_note", sa.String(300), nullable=True),
        sa.Column("callback_phone", sa.String(16), nullable=True),
        sa.Column("response_minutes", sa.SmallInteger(), server_default="15", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "service_radius_km BETWEEN 1 AND 100", name="ck_roadside_capability_radius"
        ),
        sa.CheckConstraint(
            "response_minutes BETWEEN 1 AND 240", name="ck_roadside_capability_response"
        ),
        sa.CheckConstraint(
            "NOT is_available OR enabled", name="ck_roadside_capability_available_enabled"
        ),
        sa.ForeignKeyConstraint(["garage_id"], ["garages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("garage_id", name="uq_roadside_capability_garage"),
    )
    op.create_index("ix_roadside_capabilities_garage_id", "roadside_capabilities", ["garage_id"])

    op.create_table(
        "roadside_requests",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("garage_id", UUID(as_uuid=True), nullable=False),
        sa.Column("request_code", sa.String(12), nullable=False),
        sa.Column(
            "status",
            sa.Enum(name="roadside_request_status", create_type=False),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("vehicle_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), nullable=False),
        sa.Column("problem_description", sa.String(1000), nullable=False),
        sa.Column("coarse_latitude", sa.Float(), nullable=False),
        sa.Column("coarse_longitude", sa.Float(), nullable=False),
        sa.Column("private_data_encrypted", sa.Text(), nullable=False),
        sa.Column("quote_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("quote_currency", sa.String(3), nullable=True),
        sa.Column("eta_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("decline_reason", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("coarse_latitude BETWEEN -90 AND 90", name="ck_roadside_latitude"),
        sa.CheckConstraint("coarse_longitude BETWEEN -180 AND 180", name="ck_roadside_longitude"),
        sa.CheckConstraint(
            "eta_minutes IS NULL OR eta_minutes BETWEEN 1 AND 1440", name="ck_roadside_eta"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["garage_id"], ["garages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vehicle_type_id"], ["vehicle_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_code", name="uq_roadside_request_code"),
    )
    op.create_index("ix_roadside_requests_request_code", "roadside_requests", ["request_code"])
    op.create_index("ix_roadside_requests_status", "roadside_requests", ["status"])
    op.create_index(
        "ix_roadside_requests_garage_status_created",
        "roadside_requests",
        ["garage_id", "status", "created_at"],
    )
    op.create_index(
        "ix_roadside_requests_customer_created", "roadside_requests", ["customer_id", "created_at"]
    )
    op.create_index("ix_roadside_requests_expires_at", "roadside_requests", ["expires_at"])

    op.create_table(
        "roadside_request_events",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "from_status", sa.Enum(name="roadside_request_status", create_type=False), nullable=True
        ),
        sa.Column(
            "to_status", sa.Enum(name="roadside_request_status", create_type=False), nullable=False
        ),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["request_id"], ["roadside_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_roadside_request_events_request_id", "roadside_request_events", ["request_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_roadside_request_events_request_id", table_name="roadside_request_events")
    op.drop_table("roadside_request_events")
    op.drop_index("ix_roadside_requests_expires_at", table_name="roadside_requests")
    op.drop_index("ix_roadside_requests_customer_created", table_name="roadside_requests")
    op.drop_index("ix_roadside_requests_garage_status_created", table_name="roadside_requests")
    op.drop_index("ix_roadside_requests_status", table_name="roadside_requests")
    op.drop_index("ix_roadside_requests_request_code", table_name="roadside_requests")
    op.drop_table("roadside_requests")
    op.drop_index("ix_roadside_capabilities_garage_id", table_name="roadside_capabilities")
    op.drop_table("roadside_capabilities")
    op.execute("DROP TYPE roadside_request_status")
