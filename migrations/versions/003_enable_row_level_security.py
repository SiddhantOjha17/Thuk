"""Enable Row-Level Security on all tables

Supabase flags any table with RLS disabled as publicly readable/writable
through its auto-generated REST/GraphQL API (PostgREST), because that API
connects as the `anon`/`authenticated` roles rather than the table owner.

This app never uses that API — the backend talks to Postgres directly as
the `postgres` role (see DATABASE_URL), which has BYPASSRLS and is
completely unaffected by RLS. So we enable RLS with zero policies: the
backend keeps working exactly as before, while the anon/authenticated
roles behind Supabase's REST API can no longer read or write anything.

Revision ID: 003
Revises: 002
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["users", "categories", "expenses", "splits", "debts", "refresh_tokens"]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
