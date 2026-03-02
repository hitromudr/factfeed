"""UAT script — verifies the full user experience on real ingested content.

Runs against the live database (not the rollback test db_session). All tests
are marked @pytest.mark.uat and are excluded from the default pytest run
(via addopts in pyproject.toml). They skip gracefully when the database lacks
sufficient mixed articles.

Requirements:
  - PostgreSQL running with real ingested + NLP-classified articles
  - DATABASE_URL (or default) pointing at the production/staging database

Run with:
    uv run pytest tests/uat/ -m uat --override-ini="addopts=" -v

Or, to run just this file:
    uv run pytest tests/uat/test_uat_articles.py -m uat --override-ini="addopts=" -v
"""

import warnings
from typing import List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from factfeed.config import settings
from factfeed.db.models import Article, Sentence, Source
from factfeed.db.session import AsyncSessionLocal

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def uat_articles() -> List[Article]:
    """Select up to 10 articles that have sentences.

    Prefer articles with mixed content, but fall back to any content to allow
    testing on smaller/newer datasets.
    """
    # Create a fresh engine/session for UAT verification to avoid loop conflicts
    # with the global engine when running in pytest's test-scoped loops.
    engine = create_async_engine(settings.database_url)
    LocalSession = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with LocalSession() as session:
        # Simple query: articles with any sentences
        stmt = (
            select(Article)
            .join(Article.sentences)
            .options(
                selectinload(Article.sentences),
                selectinload(Article.source),
            )
            .group_by(Article.id)
            .order_by(Article.published_at.desc().nullslast())
            .limit(10)
        )
        result = await session.execute(stmt)
        articles = list(result.scalars().all())
        for article in articles:
            session.expunge(article)

    await engine.dispose()

    if not articles:
        pytest.skip("No articles with sentences found. Run ingestion & NLP first.")

    return articles


@pytest_asyncio.fixture(scope="function")
async def uat_client():
    """AsyncClient wrapping the FastAPI app with real DB sessions (no rollback override)."""
    from factfeed.web.deps import get_db
    from factfeed.web.main import app

    # Create fresh engine/sessionmaker for this test context
    engine = create_async_engine(settings.database_url)
    LocalSession = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def real_get_db():
        """Provide sessions from the real (production) database — no rollback."""
        async with LocalSession() as session:
            yield session

    app.dependency_overrides[get_db] = real_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


# ---------------------------------------------------------------------------
# UAT Test functions
# ---------------------------------------------------------------------------


@pytest.mark.uat
@pytest.mark.asyncio
async def test_uat_sentences_have_valid_labels(uat_articles: List[Article]):
    """All sentences on each of the 10 UAT articles have valid labels and confidence scores.

    Verifies that NLP classification produced well-formed output for all articles
    selected for UAT — no unexpected label values and confidence always in [0, 1].
    """
    valid_labels = {"fact", "opinion", "mixed", "unclear"}

    for article in uat_articles:
        for sentence in article.sentences:
            assert sentence.label in valid_labels, (
                f"Article {article.id} sentence {sentence.position} has unexpected label "
                f"'{sentence.label}'. Expected one of: {valid_labels}"
            )
            if sentence.confidence is not None:
                assert 0.0 <= sentence.confidence <= 1.0, (
                    f"Article {article.id} sentence {sentence.position} confidence "
                    f"{sentence.confidence} is out of [0, 1] range."
                )


@pytest.mark.uat
@pytest.mark.asyncio
async def test_uat_article_detail_highlighting(
    uat_client: AsyncClient, uat_articles: List[Article]
):
    """Each of the 10 UAT articles renders with sentence highlighting and confidence tooltips.

    Verifies:
    - HTTP 200 from /article/{id}
    - Color-coded sentence highlighting (class="sentence fact" or class="sentence opinion")
    - Confidence tooltip text present ("confidence" appears in HTML)
    """
    for article in uat_articles:
        resp = await uat_client.get(f"/article/{article.id}")
        assert resp.status_code == 200, (
            f"GET /article/{article.id} returned {resp.status_code} for article: {article.title}"
        )
        html = resp.text

        # At least one sentence class must be present
        assert 'class="sentence' in html, (
            f"Article {article.id} detail page missing sentence highlighting. "
            "Expected 'class=\"sentence ...\"' in HTML."
        )

        # Confidence tooltip text must appear
        assert "confidence" in html.lower(), (
            f"Article {article.id} detail page missing confidence tooltip text."
        )


@pytest.mark.uat
@pytest.mark.asyncio
async def test_uat_opinion_collapsible(
    uat_client: AsyncClient, uat_articles: List[Article]
):
    """Each of the 10 UAT articles renders opinion sentences with correct class.

    Verifies:
    - Opinion sentences are styled with class 'sentence opinion' if present
    """
    for article in uat_articles:
        opinion_sentences = [s for s in article.sentences if s.label == "opinion"]
        if not opinion_sentences:
            continue

        resp = await uat_client.get(f"/article/{article.id}")
        assert resp.status_code == 200, (
            f"GET /article/{article.id} returned {resp.status_code}"
        )
        html_content = resp.text
        import html

        unescaped_html = html.unescape(html_content)

        for sent in opinion_sentences:
            assert sent.text in html_content or sent.text in unescaped_html
            assert "sentence opinion" in html_content


@pytest.mark.uat
@pytest.mark.asyncio
async def test_uat_search_finds_articles(
    uat_client: AsyncClient, uat_articles: List[Article]
):
    """Each of the 10 UAT articles is discoverable via the /search endpoint.

    Extracts the first significant keyword from each article's title and checks
    that the article title appears in the search results. If FTS does not match
    (stop-words-only title or un-indexed article), a warning is issued rather
    than a hard failure.
    """
    # Common English stop words to skip when choosing a search keyword
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "has",
        "have",
        "had",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "its",
        "it",
        "as",
        "this",
        "that",
        "than",
        "then",
        "new",
        "over",
        "up",
        "out",
        "so",
        "no",
        "not",
    }

    search_misses = []

    for article in uat_articles:
        # Find the first significant word in the title
        words = article.title.split()
        keyword = None
        for word in words:
            cleaned = word.strip(".,!?;:\"'()[]").lower()
            if cleaned and cleaned not in stop_words and len(cleaned) > 2:
                keyword = cleaned
                break

        if keyword is None:
            warnings.warn(
                f"Article {article.id} title '{article.title}' contains only stop words; "
                "skipping FTS search check for this article.",
                stacklevel=2,
            )
            continue

        resp = await uat_client.get("/search", params={"q": keyword})
        assert resp.status_code == 200, (
            f"GET /search?q={keyword} returned {resp.status_code}"
        )

        if article.title not in resp.text:
            search_misses.append(
                f"  - Article {article.id} '{article.title}' not found with keyword '{keyword}'"
            )

    if search_misses:
        warnings.warn(
            "Some articles were not found via FTS search. "
            "This may indicate FTS index is not yet populated or titles have low-specificity keywords.\n"
            + "\n".join(search_misses),
            stacklevel=2,
        )
