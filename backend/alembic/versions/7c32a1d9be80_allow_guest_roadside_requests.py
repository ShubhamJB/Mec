"""allow roadside requests without a customer account

Revision ID: 7c32a1d9be80
Revises: 4c7b2e91a6df
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "7c32a1d9be80"
down_revision: Union[str, None] = "4c7b2e91a6df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("roadside_requests", "customer_id", nullable=True)


def downgrade() -> None:
    op.alter_column("roadside_requests", "customer_id", nullable=False)
