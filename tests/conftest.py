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
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from factfeed.db.models import Base

# Use a separate test database — never the production database
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://factfeed:factfeed@localhost:5432/factfeed_test",
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Session-scoped async engine. Creates all tables on setup, drops them on teardown."""
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
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
        await session.rollback()
