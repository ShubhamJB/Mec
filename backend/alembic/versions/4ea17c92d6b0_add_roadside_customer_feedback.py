"""store customer completion feedback on roadside requests

Revision ID: 4ea17c92d6b0
Revises: 6d8a20f4c713
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4ea17c92d6b0"
down_revision: Union[str, None] = "6d8a20f4c713"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roadside_requests", sa.Column("customer_feedback_resolution", sa.String(length=16), nullable=True))
    op.add_column("roadside_requests", sa.Column("customer_feedback_rating", sa.SmallInteger(), nullable=True))
    op.add_column("roadside_requests", sa.Column("customer_feedback_comment", sa.String(length=1000), nullable=True))
    op.add_column("roadside_requests", sa.Column("customer_feedback_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_roadside_feedback_resolution",
        "roadside_requests",
        "customer_feedback_resolution IS NULL OR customer_feedback_resolution IN ('RESOLVED', 'PARTIAL', 'UNRESOLVED')",
    )
    op.create_check_constraint(
        "ck_roadside_feedback_rating",
        "roadside_requests",
        "customer_feedback_rating IS NULL OR customer_feedback_rating BETWEEN 1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_roadside_feedback_rating", "roadside_requests", type_="check")
    op.drop_constraint("ck_roadside_feedback_resolution", "roadside_requests", type_="check")
    op.drop_column("roadside_requests", "customer_feedback_at")
    op.drop_column("roadside_requests", "customer_feedback_comment")
    op.drop_column("roadside_requests", "customer_feedback_rating")
    op.drop_column("roadside_requests", "customer_feedback_resolution")
