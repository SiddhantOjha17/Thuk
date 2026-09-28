"""Add recurring_expenses table

Recurring expenses (rent, subscriptions, EMIs) are materialized into real
Expense rows lazily, on the next authenticated request after they come due —
see `crud.materialize_due_recurring_expenses` — rather than via a standing
scheduler, since free-tier hosting scales to zero and would kill one anyway.

Revision ID: 004
Revises: 003
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recurring_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(10), nullable=False),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute('ALTER TABLE "recurring_expenses" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("recurring_expenses")
