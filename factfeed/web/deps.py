"""Async DB session dependency for route injection."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closing it after the request."""
    async with AsyncSessionLocal() as session:
        yield session
