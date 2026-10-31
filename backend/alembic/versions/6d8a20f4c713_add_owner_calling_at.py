"""record that the garage started calling the rider

Revision ID: 6d8a20f4c713
Revises: 1f23b8a4cd11
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6d8a20f4c713"
down_revision: Union[str, None] = "1f23b8a4cd11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roadside_requests", sa.Column("owner_calling_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("roadside_requests", "owner_calling_at")
