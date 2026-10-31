"""store a coarse reverse-geocoded roadside place label

Revision ID: bf6e18d54290
Revises: 7c32a1d9be80
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bf6e18d54290"
down_revision: Union[str, None] = "7c32a1d9be80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roadside_requests", sa.Column("location_label", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("roadside_requests", "location_label")
