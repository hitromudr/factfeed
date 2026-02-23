"""Integration test for full ingestion cycle with mocked feeds and DB."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_feed_entry(url: str, title: str = "Test Article", summary: str = "Summary"):
    """Create a mock feedparser entry."""
    return {
        "link": url,
        "title": title,
        "summary": summary,
        "published_parsed": None,
    }


def _make_feed(entries: list[dict]):
    """Create a mock feedparser FeedParserDict."""
    feed = MagicMock()
    feed.entries = [SimpleNamespace(**e) for e in entries]
    # Make entries dict-like for .get() calls
    for entry in feed.entries:
        entry.get = lambda k, d=None, _e=entry: getattr(_e, k, d)
    return feed


def _make_source(name: str, feed_url: str, source_id: int = 1):
    """Create a mock Source ORM object."""
    source = MagicMock()
    source.name = name
    source.feed_url = feed_url
    source.id = source_id
    return source


def _mock_session_factory(sources: list):
    """Create a mock async session factory that returns sources on query."""
    @asynccontextmanager
    async def factory():
        session = AsyncMock()
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = sources
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock
        yield session
    return factory


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.article_exists", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.extract_article")
@patch("factfeed.ingestion.runner.save_article", new_callable=AsyncMock, create=True)
async def test_run_ingestion_cycle_processes_entries(
    mock_save, mock_extract, mock_fetch_page, mock_can_fetch,
    mock_article_exists, mock_fetch_rss, mock_sleep,
):
    """Full cycle: 2 entries from 1 source, both new, both saved."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source = _make_source("Test Source", "https://example.com/rss", 1)
    session_factory = _mock_session_factory([source])

    feed = _make_feed([
        _make_feed_entry("https://example.com/1", "Article 1"),
        _make_feed_entry("https://example.com/2", "Article 2"),
    ])
    mock_fetch_rss.return_value = feed
    mock_article_exists.return_value = False
    mock_can_fetch.return_value = True
    mock_fetch_page.return_value = b"<html>Content</html>"
    mock_extract.return_value = {
        "body": "A" * 300,
        "body_html": "<p>" + "A" * 300 + "</p>",
        "author": "Author",
        "published_at": None,
        "lead_image_url": None,
        "is_partial": False,
    }

    # Mock save_article via persister import inside runner
    with patch("factfeed.ingestion.persister.save_article", new_callable=AsyncMock) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    assert result["total_found"] == 2
    assert result["total_inserted"] == 2
    assert result["total_skipped"] == 0


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.article_exists", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.extract_article")
async def test_run_ingestion_cycle_skips_duplicates(
    mock_extract, mock_fetch_page, mock_can_fetch,
    mock_article_exists, mock_fetch_rss, mock_sleep,
):
    """First entry is a duplicate (article_exists=True), second is new."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source = _make_source("Test Source", "https://example.com/rss", 1)
    session_factory = _mock_session_factory([source])

    feed = _make_feed([
        _make_feed_entry("https://example.com/old", "Old Article"),
        _make_feed_entry("https://example.com/new", "New Article"),
    ])
    mock_fetch_rss.return_value = feed

    # First call returns True (duplicate), second returns False (new)
    mock_article_exists.side_effect = [True, False]
    mock_can_fetch.return_value = True
    mock_fetch_page.return_value = b"<html>Content</html>"
    mock_extract.return_value = {
        "body": "B" * 300,
        "body_html": "<p>" + "B" * 300 + "</p>",
        "author": None,
        "published_at": None,
        "lead_image_url": None,
        "is_partial": False,
    }

    with patch("factfeed.ingestion.persister.save_article", new_callable=AsyncMock) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    # 1 skipped (duplicate) + 1 inserted
    assert result["total_skipped"] == 1
    assert result["total_inserted"] == 1


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.article_exists", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.extract_article")
async def test_run_ingestion_cycle_continues_after_source_error(
    mock_extract, mock_fetch_page, mock_can_fetch,
    mock_article_exists, mock_fetch_rss, mock_sleep,
):
    """First source raises exception, second source still processed."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source1 = _make_source("Bad Source", "https://bad.com/rss", 1)
    source2 = _make_source("Good Source", "https://good.com/rss", 2)
    session_factory = _mock_session_factory([source1, source2])

    feed = _make_feed([
        _make_feed_entry("https://good.com/article", "Good Article"),
    ])

    # First source raises, second returns valid feed
    mock_fetch_rss.side_effect = [Exception("Network error"), feed]
    mock_article_exists.return_value = False
    mock_can_fetch.return_value = True
    mock_fetch_page.return_value = b"<html>Content</html>"
    mock_extract.return_value = {
        "body": "C" * 300,
        "body_html": "<p>" + "C" * 300 + "</p>",
        "author": None,
        "published_at": None,
        "lead_image_url": None,
        "is_partial": False,
    }

    with patch("factfeed.ingestion.persister.save_article", new_callable=AsyncMock) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    # First source errored (1 error), second processed normally (1 inserted)
    assert result["total_errors"] >= 1
    assert result["total_inserted"] == 1


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.article_exists", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
async def test_run_ingestion_cycle_handles_partial_extraction(
    mock_fetch_page, mock_can_fetch,
    mock_article_exists, mock_fetch_rss, mock_sleep,
):
    """When fetch_article_page returns None, article is saved with is_partial=True."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source = _make_source("Test Source", "https://example.com/rss", 1)
    session_factory = _mock_session_factory([source])

    feed = _make_feed([
        _make_feed_entry("https://example.com/1", "Article 1", summary="RSS summary"),
    ])
    mock_fetch_rss.return_value = feed
    mock_article_exists.return_value = False
    mock_can_fetch.return_value = True
    mock_fetch_page.return_value = None  # Failed to fetch page

    with patch("factfeed.ingestion.persister.save_article", new_callable=AsyncMock) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    assert result["total_inserted"] == 1
    # Verify the saved article has is_partial=True
    saved_data = patched_save.call_args[0][1]  # Second positional arg
    assert saved_data["is_partial"] is True
    assert saved_data["body"] == "RSS summary"
