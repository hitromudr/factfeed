"""
Shared pytest fixtures for FactFeed test suite.

Requires a running PostgreSQL instance. Set TEST_DATABASE_URL environment variable
to point at a test database, or set up a local PostgreSQL with the default credentials:

    TEST_DATABASE_URL=postgresql+asyncpg://factfeed:factfeed@localhost:5432/factfeed_test

The test database must exist before running tests:
    createdb -U factfeed factfeed_test

The fixtures create all tables at session start and drop them at session end.
Each test function gets a fresh session that is rolled back after the test.
"""

import os
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factfeed.db.models import Base
from factfeed.web.main import app

# Use a separate test database — never the production database
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://factfeed:factfeed@localhost:5432/factfeed_test",
)


@pytest.fixture(scope="session", autouse=True)
def disable_lifespan():
    """Disable FastAPI lifespan events during tests to prevent background tasks/seeding."""
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    yield
    app.router.lifespan_context = original_lifespan


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Function-scoped async engine. Creates all tables on setup, drops them on teardown."""
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    """Function-scoped session that rolls back after each test for isolation."""
    connection = await engine.connect()
    transaction = await connection.begin()

    session_maker = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
        join_transaction_mode="create_savepoint",
    )
    async with session_maker() as session:
        yield session
        await session.close()

    await transaction.rollback()
    await connection.close()
