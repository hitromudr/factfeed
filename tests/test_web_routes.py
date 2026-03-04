"""Integration tests for web routes covering all Phase 4 requirements.

Tests search with FTS, source/date filters, sort ordering, article detail
with sentence highlighting and collapsible opinions, and no-auth verification.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Sentence, Source


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    """Seed test data: sources, articles with sentences."""
    # Create sources
    bbc = Source(name="BBC News", feed_url="https://feeds.bbci.co.uk/news/rss.xml")
    reuters = Source(name="Reuters", feed_url="https://www.reuters.com/rssFeed/topNews")
    db_session.add_all([bbc, reuters])
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # Article 1: BBC, mostly facts, recent
    art1 = Article(
        url="https://bbc.co.uk/article-1",
        url_hash=hashlib.sha256(b"https://bbc.co.uk/article-1").hexdigest(),
        title="Scientists discover new species in deep ocean",
        body="Scientists have discovered a new species of fish in the deep ocean. The creature was found at a depth of 3000 meters.",
        published_at=now - timedelta(hours=6),
        source_id=bbc.id,
    )
    # Article 2: Reuters, mixed, older
    art2 = Article(
        url="https://reuters.com/article-2",
        url_hash=hashlib.sha256(b"https://reuters.com/article-2").hexdigest(),
        title="Economic outlook remains uncertain amid policy changes",
        body="The economy showed mixed signals this quarter. Many analysts believe the outlook is poor.",
        published_at=now - timedelta(days=10),
        source_id=reuters.id,
    )
    # Article 3: BBC, no sentences (unclassified), very recent
    art3 = Article(
        url="https://bbc.co.uk/article-3",
        url_hash=hashlib.sha256(b"https://bbc.co.uk/article-3").hexdigest(),
        title="Breaking news event unfolds",
        body="A major event is happening right now.",
        published_at=now - timedelta(minutes=30),
        source_id=bbc.id,
    )
    db_session.add_all([art1, art2, art3])
    await db_session.flush()

    # Sentences for article 1 (mostly facts)
    sentences_art1 = [
        Sentence(
            article_id=art1.id,
            position=0,
            text="Scientists have discovered a new species of fish in the deep ocean.",
            label="fact",
            confidence=0.92,
        ),
        Sentence(
            article_id=art1.id,
            position=1,
            text="The creature was found at a depth of 3000 meters.",
            label="fact",
            confidence=0.88,
        ),
    ]
    # Sentences for article 2 (mixed with opinions)
    sentences_art2 = [
        Sentence(
            article_id=art2.id,
            position=0,
            text="The economy showed mixed signals this quarter.",
            label="fact",
            confidence=0.75,
        ),
        Sentence(
            article_id=art2.id,
            position=1,
            text="Many analysts believe the outlook is poor.",
            label="opinion",
            confidence=0.82,
        ),
    ]
    db_session.add_all(sentences_art1 + sentences_art2)
    await db_session.commit()

    return {
        "bbc": bbc,
        "reuters": reuters,
        "art1": art1,
        "art2": art2,
        "art3": art3,
    }


# --- Search endpoint tests ---


@pytest.mark.asyncio
async def test_search_page_renders(client):
    """GET / returns the search page with HTML content."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "FactFeed" in resp.text
    assert "Search" in resp.text or "search" in resp.text.lower()


@pytest.mark.asyncio
async def test_search_returns_articles(client, seed_data):
    """GET / returns article results."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert seed_data["art1"].title in resp.text
    assert seed_data["art2"].title in resp.text


@pytest.mark.asyncio
async def test_search_keyword_filter(client, seed_data):
    """GET /search?q=scientists returns matching articles only."""
    resp = await client.get("/search", params={"q": "scientists"})
    assert resp.status_code == 200
    assert "Scientists discover" in resp.text
    assert "Economic outlook" not in resp.text


@pytest.mark.asyncio
async def test_search_source_filter(client, seed_data):
    """GET /search?source=X returns articles from that source only."""
    bbc_id = seed_data["bbc"].id
    resp = await client.get("/search", params={"source": bbc_id})
    assert resp.status_code == 200
    assert "Scientists discover" in resp.text
    assert "Economic outlook" not in resp.text


@pytest.mark.asyncio
async def test_search_date_filter_24h(client, seed_data):
    """GET /search?from=24h returns only recent articles."""
    resp = await client.get("/search", params={"from": "24h"})
    assert resp.status_code == 200
    # art1 (6h ago) and art3 (30min ago) should be included, art2 (10d ago) excluded
    assert "Scientists discover" in resp.text
    assert "Breaking news" in resp.text
    assert "Economic outlook" not in resp.text


@pytest.mark.asyncio
async def test_search_sort_recent(client, seed_data):
    """GET /search?sort=recent returns articles ordered by date descending."""
    resp = await client.get("/search", params={"sort": "recent"})
    assert resp.status_code == 200
    text = resp.text
    # art3 (most recent) should appear before art1
    pos_art3 = text.find("Breaking news")
    pos_art1 = text.find("Scientists discover")
    assert pos_art3 < pos_art1


@pytest.mark.asyncio
async def test_search_htmx_partial(client, seed_data):
    """GET /search with HX-Request header returns partial HTML (no base template)."""
    resp = await client.get(
        "/search",
        params={"q": "scientists"},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "Scientists discover" in resp.text
    # Partial should not contain full HTML structure
    assert "<!DOCTYPE" not in resp.text


# --- Article detail tests ---


@pytest.mark.asyncio
async def test_article_detail_renders(client, seed_data):
    """GET /article/{id} returns article detail with title."""
    art_id = seed_data["art1"].id
    resp = await client.get(f"/article/{art_id}")
    assert resp.status_code == 200
    assert seed_data["art1"].title in resp.text


@pytest.mark.asyncio
async def test_article_detail_404(client):
    """GET /article/99999 returns 404 for nonexistent article."""
    resp = await client.get("/article/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_article_sentence_highlighting(client, seed_data):
    """Article detail renders sentences with CSS highlighting classes."""
    art_id = seed_data["art1"].id
    resp = await client.get(f"/article/{art_id}")
    assert resp.status_code == 200
    # Fact sentences should have the 'fact' class
    assert 'class="sentence fact"' in resp.text
    # Confidence tooltip should show percentage
    assert "Confidence:" in resp.text


@pytest.mark.asyncio
async def test_article_renders_all_sentences(client, seed_data):
    """Article renders all sentences, both facts and opinions, directly in the body."""
    art_id = seed_data["art2"].id
    resp = await client.get(f"/article/{art_id}")
    assert resp.status_code == 200

    # Both fact and opinion sentences should be rendered in the body
    assert "The economy showed mixed signals this quarter." in resp.text
    assert "Many analysts believe the outlook is poor." in resp.text

    # Opinion sentence should have the 'opinion' class for highlighting
    assert 'class="sentence opinion' in resp.text


@pytest.mark.asyncio
async def test_article_no_sentences(client, seed_data):
    """Article without sentences shows body text with classification pending note."""
    art_id = seed_data["art3"].id
    resp = await client.get(f"/article/{art_id}")
    assert resp.status_code == 200
    assert seed_data["art3"].body in resp.text
    assert "Classification pending" in resp.text


# --- No-auth verification ---


@pytest.mark.asyncio
async def test_no_auth_cookies(client, seed_data):
    """No authentication middleware or session cookies in any response."""
    for url in ["/", "/search", f"/article/{seed_data['art1'].id}"]:
        resp = await client.get(url)
        # No set-cookie header
        assert "set-cookie" not in resp.headers
        # No auth-related content
        assert "login" not in resp.text.lower()
        assert "sign in" not in resp.text.lower()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint still accessible."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Localization tests ---


@pytest.mark.asyncio
async def test_localization_ru(client):
    """GET / with Accept-Language: ru returns Russian UI."""
    resp = await client.get("/", headers={"Accept-Language": "ru"})
    assert resp.status_code == 200
    # Check for Russian strings
    assert "Поиск" in resp.text
    assert "Документация API" in resp.text
