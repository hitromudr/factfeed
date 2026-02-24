"""Search page route with full-text search, source/date filters, and sort."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article, Source
from factfeed.web.deps import get_db

router = APIRouter()

templates = Jinja2Templates(directory="factfeed/templates")


def _date_cutoff(from_filter: Optional[str]) -> Optional[datetime]:
    """Convert a date range filter string to a UTC cutoff datetime."""
    if not from_filter:
        return None
    now = datetime.now(timezone.utc)
    mapping = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    delta = mapping.get(from_filter)
    if delta is None:
        return None
    return now - delta


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
        from factfeed.db.models import Sentence

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
async def search_page(
    request: Request,
    q: str = "",
    source: Optional[int] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    sort: str = "facts",
    db: AsyncSession = Depends(get_db),
):
    """Render the search page with results."""
    articles = await search_articles(db, q=q, source=source, from_filter=from_filter, sort=sort)

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
    }

    # HTMX partial response
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_results.html", context)

    return templates.TemplateResponse("search.html", context)


@router.get("/search")
async def search_endpoint(
    request: Request,
    q: str = "",
    source: Optional[int] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    sort: str = "facts",
    db: AsyncSession = Depends(get_db),
):
    """HTMX search endpoint — returns partial or full page."""
    articles = await search_articles(db, q=q, source=source, from_filter=from_filter, sort=sort)

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
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_results.html", context)

    return templates.TemplateResponse("search.html", context)
