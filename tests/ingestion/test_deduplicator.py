"""Unit tests for URL hash computation and normalization."""

import pytest
from factfeed.ingestion.deduplicator import compute_url_hash, article_exists
from factfeed.db.models import Article


def test_compute_url_hash_returns_64_char_hex():
    """Hash output should be a 64-character hexadecimal string."""
    h = compute_url_hash("https://example.com/article")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_url_hash_deterministic():
    """Same URL produces the same hash on repeated calls."""
    url = "https://example.com/article"
    assert compute_url_hash(url) == compute_url_hash(url)


def test_compute_url_hash_strips_query_params():
    """URLs differing only in query parameters produce the same hash."""
    base = "https://example.com/article"
    with_params = "https://example.com/article?utm_source=twitter&ref=homepage"
    assert compute_url_hash(base) == compute_url_hash(with_params)


def test_compute_url_hash_strips_fragment():
    """URLs differing only in fragment produce the same hash."""
    base = "https://example.com/article"
    with_fragment = "https://example.com/article#section1"
    assert compute_url_hash(base) == compute_url_hash(with_fragment)


def test_compute_url_hash_normalizes_case():
    """Scheme and netloc are lowercased for consistent hashing."""
    lower = "https://example.com/article"
    upper = "HTTPS://Example.COM/article"
    assert compute_url_hash(lower) == compute_url_hash(upper)


def test_compute_url_hash_different_paths_different_hash():
    """Different paths produce different hashes."""
    h1 = compute_url_hash("https://example.com/a")
    h2 = compute_url_hash("https://example.com/b")
    assert h1 != h2


@pytest.mark.asyncio
async def test_article_exists_returns_false_for_nonexistent(db_session):
    """With empty DB, article_exists returns False."""
    result = await article_exists("a" * 64, db_session)
    assert result is False


@pytest.mark.asyncio
async def test_article_exists_returns_true_after_insert(db_session):
    """After inserting an article, article_exists returns True for its url_hash."""
    url_hash = compute_url_hash("https://example.com/test-article")
    article = Article(
        url="https://example.com/test-article",
        url_hash=url_hash,
        title="Test Article",
        body="Test body content",
    )
    db_session.add(article)
    await db_session.flush()

    result = await article_exists(url_hash, db_session)
    assert result is True
