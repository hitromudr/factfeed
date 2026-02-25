"""Tests for per-IP rate limiting on the search endpoint.

Rate limit: 30 requests/minute per IP.
Search routes (/ and /search) are limited; article detail is not.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock


def _make_mock_db():
    """Return an async DB session mock that yields empty query results."""

    async def _empty_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = _empty_execute
    return session


@pytest_asyncio.fixture
async def rate_limit_client():
    """Test client with rate-limit storage reset per test to avoid state leakage.

    Resets the production limiter's in-memory storage before each test so each
    test starts with a clean counter. Uses a mock DB session so no PostgreSQL is
    required for rate-limit tests.
    """
    from factfeed.web.deps import get_db
    from factfeed.web.main import app
    from factfeed.web.limiter import limiter

    # Reset in-memory rate limit counters before each test
    limiter._limiter.storage.reset()

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_under_rate_limit(rate_limit_client):
    """5 requests to /search should all return 200 (well under 30/minute limit)."""
    for i in range(5):
        resp = await rate_limit_client.get("/search", params={"q": "test"})
        assert resp.status_code == 200, f"Request {i + 1} failed with {resp.status_code}"


@pytest.mark.asyncio
async def test_search_rate_limit_429(rate_limit_client):
    """31st request to /search from the same IP should return 429."""
    # Send 30 requests that should all succeed
    for i in range(30):
        resp = await rate_limit_client.get("/search", params={"q": "test"})
        assert resp.status_code == 200, f"Request {i + 1} unexpectedly failed with {resp.status_code}"

    # The 31st request should be rate limited
    resp = await rate_limit_client.get("/search", params={"q": "test"})
    assert resp.status_code == 429, (
        f"Expected 429 on request 31, got {resp.status_code}"
    )


@pytest.mark.asyncio
async def test_article_detail_not_rate_limited(rate_limit_client):
    """Article detail endpoint is NOT rate limited — 35 requests should not return 429.

    Uses article ID 99999 (nonexistent) so we get 404s but never 429.
    """
    for i in range(35):
        resp = await rate_limit_client.get("/article/99999")
        # Must not be 429 — article detail has no rate limit
        assert resp.status_code != 429, (
            f"Request {i + 1} to article detail returned unexpected 429"
        )
        assert resp.status_code in (200, 404), (
            f"Request {i + 1} returned unexpected status {resp.status_code}"
        )
