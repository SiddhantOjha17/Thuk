"""Auth and schema overhaul: drop phone_number, add email/password/name, add refresh_tokens, add category.color

Revision ID: 002
Revises: 001
Create Date: 2025-01-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users table ────────────────────────────────────────────────────────────
    # Add new columns first (nullable so existing rows don't break)
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(100), nullable=True))

    # Backfill: give any existing rows a placeholder email derived from phone_number
    # (Only relevant if migrating a live DB with data; empty DB skips this.)
    op.execute(
        """
        UPDATE users
        SET email = CONCAT('migrated_', REPLACE(phone_number, '+', ''), '@placeholder.local'),
            password_hash = 'CHANGE_ME',
            name = 'User'
        WHERE email IS NULL
        """
    )

    # Now enforce NOT NULL and unique index
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "password_hash", nullable=False)
    op.alter_column("users", "name", nullable=False)
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])

    # Drop old columns
    op.drop_index("ix_users_phone_number", table_name="users", if_exists=True)
    op.drop_column("users", "phone_number")
    op.drop_column("users", "openai_api_key_encrypted")

    # ── categories table ────────────────────────────────────────────────────────
    op.add_column("categories", sa.Column("color", sa.String(20), nullable=True))
    op.drop_column("categories", "icon")

    # Seed default colors for existing default categories
    category_colors = {
        "Food": "#F97316",
        "Transport": "#38BDF8",
        "Shopping": "#A78BFA",
        "Bills": "#FBBF24",
        "Entertainment": "#F472B6",
        "Health": "#34D399",
        "Other": "#9CA3AF",
        "Others": "#9CA3AF",
    }
    for name, color in category_colors.items():
        op.execute(
            f"UPDATE categories SET color = '{color}' WHERE name = '{name}' AND is_default = true"
        )

    # ── refresh_tokens table ────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.add_column("categories", sa.Column("icon", sa.String(10), nullable=True))
    op.drop_column("categories", "color")
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True))
    op.drop_column("users", "email")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "name")
