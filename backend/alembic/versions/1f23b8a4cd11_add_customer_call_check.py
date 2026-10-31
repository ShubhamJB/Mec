"""record rider confirmation that garage called

Revision ID: 1f23b8a4cd11
Revises: bf6e18d54290
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1f23b8a4cd11"
down_revision: Union[str, None] = "bf6e18d54290"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("roadside_requests", sa.Column("customer_contact_confirmed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("roadside_requests", "customer_contact_confirmed")
