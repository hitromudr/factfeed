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

import fastapi
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factfeed.db import session as db_session_module
from factfeed.db.models import Base
from factfeed.web.deps import get_db
from factfeed.web.main import app

# Use a separate test database — never the production database
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://factfeed:factfeed@localhost:5432/factfeed_test",
)


@pytest.fixture(autouse=True)
def disable_background_tasks(monkeypatch):
    """Disable background tasks execution during tests to avoid race conditions."""
    monkeypatch.setattr(
        fastapi.BackgroundTasks, "add_task", lambda *args, **kwargs: None
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
        # Patch the global session maker used by background tasks/schedulers
        # so they use this test session instead of creating a new one
        original_session_maker = db_session_module.AsyncSessionLocal
        db_session_module.AsyncSessionLocal = lambda: session

        # Override dependency for web routes
        app.dependency_overrides[get_db] = lambda: session

        yield session

        # Cleanup overrides
        app.dependency_overrides.pop(get_db, None)
        db_session_module.AsyncSessionLocal = original_session_maker
        await session.close()

    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncClient:
    """Async test client for FastAPI app.

    Depends on db_session to ensure the app's DB dependency is overridden
    with the test session before requests are made.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
