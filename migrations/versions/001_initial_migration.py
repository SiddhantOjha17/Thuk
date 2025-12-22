"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2024-12-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone_number", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("preferences", postgresql.JSONB(), server_default="{}", nullable=False),
    )

    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(10), nullable=True),
        sa.Column("is_default", sa.Boolean(), default=False),
    )

    # Create expenses table
    op.create_table(
        "expenses",
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
        sa.Column("currency", sa.String(3), default="INR", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(10), default="text"),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
    )

    # Create splits table
    op.create_table(
        "splits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "expense_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_people", sa.Integer(), nullable=False),
        sa.Column("per_person_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("user_paid", sa.Numeric(12, 2), nullable=False),
        sa.Column("user_share", sa.Numeric(12, 2), nullable=False),
    )

    # Create debts table
    op.create_table(
        "debts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("person_name", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), default="INR", nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("is_settled", sa.Boolean(), default=False),
        sa.Column(
            "related_expense_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("debts")
    op.drop_table("splits")
    op.drop_table("expenses")
    op.drop_table("categories")
    op.drop_table("users")
