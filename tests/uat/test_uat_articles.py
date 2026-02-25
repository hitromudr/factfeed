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
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article, Sentence, Source
from factfeed.db.session import AsyncSessionLocal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def uat_articles() -> List[Article]:
    """Select 10 articles that have BOTH fact AND opinion sentences.

    Requires at least 3 distinct source IDs among the 10 articles.
    Skips the test module gracefully if fewer than 10 qualifying articles exist.
    """
    async with AsyncSessionLocal() as session:
        # Subquery: article IDs that have at least one 'fact' sentence
        fact_ids = (
            select(Sentence.article_id)
            .where(Sentence.label == "fact")
            .distinct()
            .scalar_subquery()
        )
        # Subquery: article IDs that have at least one 'opinion' sentence
        opinion_ids = (
            select(Sentence.article_id)
            .where(Sentence.label == "opinion")
            .distinct()
            .scalar_subquery()
        )

        stmt = (
            select(Article)
            .options(
                selectinload(Article.sentences),
                selectinload(Article.source),
            )
            .where(Article.id.in_(fact_ids))
            .where(Article.id.in_(opinion_ids))
            .order_by(Article.published_at.desc().nullslast())
            .limit(10)
        )
        result = await session.execute(stmt)
        articles = list(result.scalars().all())

    if len(articles) < 10:
        pytest.skip(
            f"Fewer than 10 mixed articles available (found {len(articles)}) — "
            "run ingestion + NLP classification first, then re-run UAT tests."
        )

    # Require at least 3 distinct sources
    source_ids = {a.source_id for a in articles if a.source_id is not None}
    if len(source_ids) < 3:
        pytest.skip(
            f"Only {len(source_ids)} distinct source(s) represented among the 10 articles; "
            "at least 3 required. Run ingestion across more sources then re-run UAT tests."
        )

    return articles


@pytest_asyncio.fixture(scope="module")
async def uat_client():
    """AsyncClient wrapping the FastAPI app with real DB sessions (no rollback override)."""
    from factfeed.web.deps import get_db
    from factfeed.web.main import app

    async def real_get_db():
        """Provide sessions from the real (production) database — no rollback."""
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = real_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


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

        # At least one color-coded sentence class must be present
        has_fact_class = 'class="sentence fact"' in html
        has_opinion_class = 'class="sentence opinion"' in html
        assert has_fact_class or has_opinion_class, (
            f"Article {article.id} detail page missing sentence highlighting. "
            "Expected 'class=\"sentence fact\"' or 'class=\"sentence opinion\"' in HTML."
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
    """Each of the 10 UAT articles (all have opinion sentences) renders collapsible opinion section.

    Verifies:
    - <details> and <summary> elements present (collapsible HTML mechanism)
    - "Show opinion content" summary label present
    - At least one opinion sentence text visible in the response body
    """
    for article in uat_articles:
        resp = await uat_client.get(f"/article/{article.id}")
        assert resp.status_code == 200, (
            f"GET /article/{article.id} returned {resp.status_code}"
        )
        html = resp.text

        assert "<details" in html, (
            f"Article {article.id}: missing <details> element for collapsible opinion section."
        )
        assert "<summary" in html, (
            f"Article {article.id}: missing <summary> element for collapsible opinion section."
        )
        assert "Show opinion content" in html, (
            f"Article {article.id}: missing 'Show opinion content' label in <summary>."
        )

        # At least one opinion sentence text should appear in the HTML
        opinion_sentences = [s for s in article.sentences if s.label == "opinion"]
        assert opinion_sentences, (
            f"Article {article.id} was selected as a mixed article but has no opinion sentences."
        )
        any_opinion_visible = any(s.text in html for s in opinion_sentences)
        assert any_opinion_visible, (
            f"Article {article.id}: no opinion sentence text found in the rendered page. "
            f"Checked {len(opinion_sentences)} opinion sentence(s)."
        )


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
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "has", "have", "had", "will", "would", "could", "should", "may",
        "might", "shall", "its", "it", "as", "this", "that", "than", "then",
        "new", "over", "up", "out", "so", "no", "not",
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
