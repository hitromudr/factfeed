"""Search page route with full-text search, source/date filters, and sort."""

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article, Sentence, Source
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_locale, get_translator
from factfeed.web.limiter import limiter

router = APIRouter()

templates = Jinja2Templates(directory="factfeed/templates")


def _date_cutoff(from_filter: Optional[str]) -> Optional[datetime]:
    """Convert a date range filter string to a UTC cutoff datetime."""
    if not from_filter:
        return None
    now = datetime.now(timezone.utc)
    mapping = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    delta = mapping.get(from_filter)
    if delta is None:
        return None
    return now - delta


async def _attach_fact_scores(db: AsyncSession, articles: list) -> list:
    """Attach fact_count, opinion_count, mixed_count, total_count to each article."""
    if not articles:
        return articles
    article_ids = [a.id for a in articles]
    stmt = (
        select(
            Sentence.article_id,
            Sentence.label,
            func.count().label("cnt"),
        )
        .where(Sentence.article_id.in_(article_ids))
        .group_by(Sentence.article_id, Sentence.label)
    )
    result = await db.execute(stmt)
    # Build {article_id: {label: count}}
    counts: dict[int, dict[str, int]] = {}
    for row in result:
        counts.setdefault(row.article_id, {})[row.label or "unclear"] = row.cnt
    for article in articles:
        c = counts.get(article.id, {})
        article.fact_count = c.get("fact", 0)
        article.opinion_count = c.get("opinion", 0)
        article.mixed_count = c.get("mixed", 0)
        article.total_count = sum(c.values())
        article.fact_pct = (
            round(100 * article.fact_count / article.total_count)
            if article.total_count
            else None
        )
    return articles


async def search_articles(
    db: AsyncSession,
    q: str = "",
    source: Optional[int] = None,
    from_filter: Optional[str] = None,
    sort: str = "facts",
    limit: int = 50,
):
    """Build and execute a composable search query with FTS, filters, and sort."""
    stmt = select(Article).options(selectinload(Article.source))

    # Full-text search filter
    if q.strip():
        ts_query = func.plainto_tsquery("english", q.strip())
        stmt = stmt.where(Article.search_vector.op("@@")(ts_query))

    # Source filter
    if source is not None:
        stmt = stmt.where(Article.source_id == source)

    # Date range filter
    cutoff = _date_cutoff(from_filter)
    if cutoff is not None:
        stmt = stmt.where(Article.published_at >= cutoff)

    # Sort order
    if sort == "recent":
        stmt = stmt.order_by(Article.published_at.desc().nullslast())
    else:
        # Fact-density: ratio of fact sentences to total sentences (descending)
        fact_count = (
            select(func.count())
            .where(Sentence.article_id == Article.id, Sentence.label == "fact")
            .correlate(Article)
            .scalar_subquery()
        )
        total_count = (
            select(func.count())
            .where(Sentence.article_id == Article.id)
            .correlate(Article)
            .scalar_subquery()
        )
        # Articles with no sentences go last; otherwise order by fact ratio descending
        fact_ratio = func.coalesce(
            func.cast(fact_count, Float) / func.nullif(total_count, 0), 0
        )
        stmt = stmt.order_by(fact_ratio.desc(), Article.published_at.desc().nullslast())

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/")
@limiter.limit("30/minute")
async def search_page(
    request: Request,
    q: str = "",
    source: Optional[int] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    sort: str = "facts",
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
    locale: str = Depends(get_locale),
):
    """Render the search page with results."""
    articles = await search_articles(
        db, q=q, source=source, from_filter=from_filter, sort=sort
    )
    await _attach_fact_scores(db, articles)

    # Load available sources for filter dropdown
    sources_result = await db.execute(select(Source).order_by(Source.name))
    sources = sources_result.scalars().all()

    context = {
        "request": request,
        "articles": articles,
        "sources": sources,
        "q": q,
        "source": source,
        "from_filter": from_filter,
        "sort": sort,
        "_": trans,
        "locale": locale,
    }

    # HTMX partial response
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_results.html", context)

    return templates.TemplateResponse("search.html", context)


@router.get("/search")
@limiter.limit("30/minute")
async def search_endpoint(
    request: Request,
    q: str = "",
    source: Optional[int] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    sort: str = "facts",
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
    locale: str = Depends(get_locale),
):
    """HTMX search endpoint — returns partial or full page."""
    articles = await search_articles(
        db, q=q, source=source, from_filter=from_filter, sort=sort
    )
    await _attach_fact_scores(db, articles)

    sources_result = await db.execute(select(Source).order_by(Source.name))
    sources = sources_result.scalars().all()

    context = {
        "request": request,
        "articles": articles,
        "sources": sources,
        "q": q,
        "source": source,
        "from_filter": from_filter,
        "sort": sort,
        "_": trans,
        "locale": locale,
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_results.html", context)

    return templates.TemplateResponse("search.html", context)
