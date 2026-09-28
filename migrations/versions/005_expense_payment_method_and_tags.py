"""Add payment_method and tags to expenses

Revision ID: 005
Revises: 004
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("payment_method", sa.String(20), nullable=True))
    op.add_column(
        "expenses",
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("expenses", "tags")
    op.drop_column("expenses", "payment_method")
