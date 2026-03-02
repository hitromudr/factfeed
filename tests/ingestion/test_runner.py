"""Integration test for full ingestion cycle with mocked feeds and DB."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Helper to mock DB objects and session behavior
class MockSessionFactory:
    def __init__(self, sources, article_existence_results=None):
        self.sources = sources
        self.article_existence_results = article_existence_results or []
        # Add dummy value for the initial select(Source) query which consumes one iterator item
        self._iter = iter([None] + self.article_existence_results)

    @asynccontextmanager
    async def __call__(self):
        session = AsyncMock()

        async def execute_side_effect(stmt):
            result = MagicMock()

            # Mock scalars().all() which is used by select(Source)
            result.scalars.return_value.all.return_value = self.sources

            # Mock scalar_one_or_none() which is used by the article existence check
            # logic in runner: result = await session.execute(select(Article.is_partial)...)
            try:
                val = next(self._iter)
            except StopIteration:
                val = None  # Default to None (Article not found) if we run out of mocked values

            result.scalar_one_or_none.return_value = val

            return result

        session.execute.side_effect = execute_side_effect
        yield session


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


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.extract_article")
async def test_run_ingestion_cycle_processes_entries(
    mock_extract,
    mock_fetch_page,
    mock_can_fetch,
    mock_fetch_rss,
    mock_sleep,
):
    """Full cycle: 2 entries from 1 source, both new, both saved."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source = _make_source("Test Source", "https://example.com/rss", 1)

    # Both articles are new (None returned by existence check)
    session_factory = MockSessionFactory(
        [source], article_existence_results=[None, None]
    )

    feed = _make_feed(
        [
            _make_feed_entry("https://example.com/1", "Article 1"),
            _make_feed_entry("https://example.com/2", "Article 2"),
        ]
    )
    mock_fetch_rss.return_value = feed
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
    with patch(
        "factfeed.ingestion.persister.save_article", new_callable=AsyncMock
    ) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    assert result["total_found"] == 2
    assert result["total_inserted"] == 2
    assert result["total_skipped"] == 0


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.extract_article")
async def test_run_ingestion_cycle_skips_duplicates(
    mock_extract,
    mock_fetch_page,
    mock_can_fetch,
    mock_fetch_rss,
    mock_sleep,
):
    """First entry is a duplicate (False returned: full exists), second is new (None)."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source = _make_source("Test Source", "https://example.com/rss", 1)

    # 1. False = Full article exists (skip)
    # 2. None = New article (process)
    # logic in runner:
    #   existing_partial = result.scalar_one_or_none()
    #   if existing_partial is False: skip
    #   elif existing_partial is True: retry (update)
    #   else (None): process new

    session_factory = MockSessionFactory(
        [source], article_existence_results=[False, None]
    )

    feed = _make_feed(
        [
            _make_feed_entry("https://example.com/old", "Old Article"),
            _make_feed_entry("https://example.com/new", "New Article"),
        ]
    )
    mock_fetch_rss.return_value = feed

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

    with patch(
        "factfeed.ingestion.persister.save_article", new_callable=AsyncMock
    ) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    # 1 skipped (duplicate) + 1 inserted
    assert result["total_skipped"] == 1
    assert result["total_inserted"] == 1


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.extract_article")
async def test_run_ingestion_cycle_continues_after_source_error(
    mock_extract,
    mock_fetch_page,
    mock_can_fetch,
    mock_fetch_rss,
    mock_sleep,
):
    """First source raises exception, second source still processed."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source1 = _make_source("Bad Source", "https://bad.com/rss", 1)
    source2 = _make_source("Good Source", "https://good.com/rss", 2)

    # existence check for the successful source's article
    session_factory = MockSessionFactory(
        [source1, source2], article_existence_results=[None]
    )

    feed = _make_feed(
        [
            _make_feed_entry("https://good.com/article", "Good Article"),
        ]
    )

    # First source raises, second returns valid feed
    mock_fetch_rss.side_effect = [Exception("Network error"), feed]
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

    with patch(
        "factfeed.ingestion.persister.save_article", new_callable=AsyncMock
    ) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    # First source errored (1 error), second processed normally (1 inserted)
    assert result["total_errors"] >= 1
    assert result["total_inserted"] == 1


@pytest.mark.asyncio
@patch("factfeed.ingestion.runner.asyncio.sleep", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_rss_feed", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.can_fetch", new_callable=AsyncMock)
@patch("factfeed.ingestion.runner.fetch_article_page", new_callable=AsyncMock)
async def test_run_ingestion_cycle_handles_partial_extraction(
    mock_fetch_page,
    mock_can_fetch,
    mock_fetch_rss,
    mock_sleep,
):
    """When fetch_article_page returns None, article is saved with is_partial=True."""
    from factfeed.ingestion.runner import run_ingestion_cycle

    source = _make_source("Test Source", "https://example.com/rss", 1)
    session_factory = MockSessionFactory([source], article_existence_results=[None])

    feed = _make_feed(
        [
            _make_feed_entry(
                "https://example.com/1", "Article 1", summary="RSS summary"
            ),
        ]
    )
    mock_fetch_rss.return_value = feed
    mock_can_fetch.return_value = True
    mock_fetch_page.return_value = None  # Failed to fetch page

    with patch(
        "factfeed.ingestion.persister.save_article", new_callable=AsyncMock
    ) as patched_save:
        patched_save.return_value = True
        result = await run_ingestion_cycle(session_factory, AsyncMock())

    assert result["total_inserted"] == 1
    # Verify the saved article has is_partial=True
    saved_data = patched_save.call_args[0][1]  # Second positional arg
    assert saved_data["is_partial"] is True
    assert saved_data["body"] == "RSS summary"
