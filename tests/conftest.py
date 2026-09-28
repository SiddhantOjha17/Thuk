"""Shared pytest fixtures for API-level tests.

Uses a real Postgres database (not SQLite) because the models rely on
Postgres-specific column types (UUID, JSONB) that SQLite can't compile.
Defaults to a local `thuk_test` database owned by the current OS user
(no password, matching local peer/trust auth) — override with
TEST_DATABASE_URL for CI or a different local setup. This is always a
separate database from the app's own .env DATABASE_URL, so tests never
touch real dev/prod data.

The engine is created fresh per test (function-scoped), not at module
level, because pytest-asyncio gives each test its own event loop and an
asyncpg connection pool can't be reused across event loops.
"""

import getpass
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.base import Base, get_db

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{getpass.getuser()}@localhost:5432/thuk_test",
)


@pytest_asyncio.fixture
async def db_session():
    """A DB session against a freshly created schema, rolled back and torn down after."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """An httpx client for the FastAPI app, wired to the isolated test session."""
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
