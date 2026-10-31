"""add garage staff

Revision ID: a91f0d6c3b42
Revises: 59c23d31c827
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "a91f0d6c3b42"
down_revision: Union[str, None] = "59c23d31c827"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "garage_staff",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("garage_id", UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("role_title", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["garage_id"], ["garages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_garage_staff_garage_id", "garage_staff", ["garage_id"])


def downgrade() -> None:
    op.drop_index("ix_garage_staff_garage_id", table_name="garage_staff")
    op.drop_table("garage_staff")
