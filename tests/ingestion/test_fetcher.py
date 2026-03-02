"""Unit tests for RSS feed fetching and article page fetching with mocked HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from factfeed.ingestion.fetcher import fetch_article_page, fetch_rss_feed

# Minimal valid RSS XML for feed tests
SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0">
<channel><title>Test</title>
<item><title>Article 1</title><link>https://example.com/1</link><description>Summary</description></item>
</channel></rss>"""

# Malformed RSS that triggers feedparser bozo
MALFORMED_RSS = b"""<?xml version="1.0"?>
<rss version="2.0">
<channel><title>Test</title>
<item><title>Article 1</title><link>https://example.com/1</link>
</channel></rss>"""  # Missing closing </item>


def _mock_response(content: bytes, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    response = MagicMock()
    response.content = content
    response.status_code = status_code
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    return response


@pytest.mark.asyncio
async def test_fetch_rss_feed_success():
    """Successful RSS fetch returns feedparser dict with entries."""
    client = AsyncMock()
    client.get.return_value = _mock_response(SAMPLE_RSS)

    source = {"name": "Test Source", "feed_url": "https://example.com/rss"}
    feed = await fetch_rss_feed(source, client)

    assert len(feed.entries) == 1
    assert feed.entries[0].title == "Article 1"


@pytest.mark.asyncio
async def test_fetch_rss_feed_bozo_continues():
    """Bozo feed is returned (not raised) and entries are accessible."""
    client = AsyncMock()
    # Malformed XML will trigger bozo but feedparser still parses what it can
    client.get.return_value = _mock_response(MALFORMED_RSS)

    source = {"name": "Bozo Source", "feed_url": "https://example.com/rss"}
    feed = await fetch_rss_feed(source, client)

    # Feed is returned regardless of bozo
    assert feed is not None
    # feedparser still extracts whatever it can
    assert hasattr(feed, "entries")


@pytest.mark.asyncio
async def test_fetch_rss_feed_http_error_raises():
    """HTTP 500 raises httpx.HTTPStatusError."""
    client = AsyncMock()
    client.get.return_value = _mock_response(b"", status_code=500)

    source = {"name": "Error Source", "feed_url": "https://example.com/rss"}
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_rss_feed(source, client)


@pytest.mark.asyncio
async def test_fetch_article_page_success():
    """Successful article fetch returns HTML bytes."""
    from unittest.mock import MagicMock, patch

    client = AsyncMock()
    html = b"<html><body>Hello</body></html>"

    # Mock response
    mock_resp = MagicMock()
    mock_resp.content = html
    mock_resp.raise_for_status.return_value = None

    # Mock AsyncSession
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("factfeed.ingestion.fetcher.AsyncSession", return_value=mock_session):
        result = await fetch_article_page("https://example.com/article", client)

    assert result == html


@pytest.mark.asyncio
async def test_fetch_article_page_timeout_returns_none():
    """Timeout returns None instead of raising."""
    client = AsyncMock()
    client.get.side_effect = httpx.TimeoutException("read timeout")

    result = await fetch_article_page("https://example.com/article", client)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_article_page_http_error_returns_none():
    """HTTP 404 returns None instead of raising."""
    client = AsyncMock()
    client.get.return_value = _mock_response(b"", status_code=404)

    result = await fetch_article_page("https://example.com/article", client)
    assert result is None
