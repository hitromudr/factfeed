"""Search page route with full-text search, source/date filters, and sort."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article, Sentence, Source
from factfeed.nlp.translator import get_or_create_translation
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
    source: Optional[str] = None,
    from_filter: Optional[str] = None,
    classification: Optional[str] = None,
    sort: str = "facts",
    limit: int = 20,
):
    """Build and execute a composable search query with FTS, filters, and sort."""
    stmt = select(Article).options(selectinload(Article.source))

    # Filter out empty content
    stmt = stmt.where(Article.body.is_not(None), Article.body != "")

    # Subqueries for fact density calculation
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
    fact_ratio = func.coalesce(
        func.cast(fact_count, Float) / func.nullif(total_count, 0), 0
    )

    # Full-text search filter
    if q.strip():
        ts_query = func.plainto_tsquery("english", q.strip())
        stmt = stmt.where(Article.search_vector.op("@@")(ts_query))

    # Source filter
    if source and str(source).isdigit():
        stmt = stmt.where(Article.source_id == int(source))

    # Date range filter
    cutoff = _date_cutoff(from_filter)
    if cutoff is not None:
        stmt = stmt.where(Article.published_at >= cutoff)

    # Classification filter
    if classification == "fact":
        stmt = stmt.where(fact_ratio >= 0.7)
    elif classification == "opinion":
        stmt = stmt.where(fact_ratio <= 0.3)
    elif classification == "mixed":
        stmt = stmt.where(fact_ratio > 0.3, fact_ratio < 0.7)

    # Sort order
    if sort == "recent":
        stmt = stmt.order_by(Article.published_at.desc().nullslast())
    else:
        # Fact-density: ratio of fact sentences to total sentences (descending)
        stmt = stmt.order_by(fact_ratio.desc(), Article.published_at.desc().nullslast())

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/")
@limiter.limit("30/minute")
async def search_page(
    request: Request,
    q: str = "",
    source: Optional[str] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    classification: Optional[str] = None,
    sort: str = "facts",
    db: AsyncSession = Depends(get_db),
    locale: str = Depends(get_locale),
):
    """Render the search page with results."""
    trans = get_translator(request)

    articles = await search_articles(
        db,
        q=q,
        source=source,
        from_filter=from_filter,
        classification=classification,
        sort=sort,
    )
    await _attach_fact_scores(db, articles)

    # Translate titles AND snippets if needed
    if locale != "en":
        # Process translations in parallel using DB cache where available
        tasks = [get_or_create_translation(db, a, locale) for a in articles]
        if tasks:
            await asyncio.gather(*tasks)
            for article in articles:
                # Use the translated body (now on the object) to create snippet
                snippet_text = article.body[:300] if article.body else ""
                article.translated_snippet = snippet_text

    # Group articles by title
    groups = {}
    for article in articles:
        # Use title as key
        key = article.title
        if key not in groups:
            groups[key] = []
        groups[key].append(article)

    article_groups = []
    for title, group in groups.items():
        # Sort group by date desc to pick the freshest as 'main'
        group.sort(
            key=lambda a: a.published_at.timestamp() if a.published_at else 0,
            reverse=True,
        )
        main_article = group[0]
        article_groups.append(
            {
                "title": title,
                "articles": group,
                "main": main_article,
                # Use translated snippet if available, else original body
                "snippet": getattr(
                    main_article, "translated_snippet", main_article.body
                ),
            }
        )

    # Load available sources for filter dropdown
    sources_result = await db.execute(select(Source).order_by(Source.name))
    sources = sources_result.scalars().all()

    context = {
        "request": request,
        "article_groups": article_groups,
        "sources": sources,
        "q": q,
        "source": source,
        "from_filter": from_filter,
        "classification": classification,
        "sort": sort,
        "_": trans,
        "locale": locale,
    }

    # HTMX partial response
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="_results.html", context=context
        )

    return templates.TemplateResponse(
        request=request, name="search.html", context=context
    )


@router.get("/search")
@limiter.limit("30/minute")
async def search_endpoint(
    request: Request,
    q: str = "",
    source: Optional[str] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    classification: Optional[str] = None,
    sort: str = "facts",
    db: AsyncSession = Depends(get_db),
    locale: str = Depends(get_locale),
):
    """HTMX search endpoint — returns partial or full page."""
    trans = get_translator(request)

    articles = await search_articles(
        db,
        q=q,
        source=source,
        from_filter=from_filter,
        classification=classification,
        sort=sort,
    )
    await _attach_fact_scores(db, articles)

    if locale != "en":
        tasks = [get_or_create_translation(db, a, locale) for a in articles]
        if tasks:
            await asyncio.gather(*tasks)
            for article in articles:
                snippet_text = article.body[:300] if article.body else ""
                article.translated_snippet = snippet_text

    # Group articles by title
    groups = {}
    for article in articles:
        key = article.title
        if key not in groups:
            groups[key] = []
        groups[key].append(article)

    article_groups = []
    for title, group in groups.items():
        group.sort(
            key=lambda a: a.published_at.timestamp() if a.published_at else 0,
            reverse=True,
        )
        main_article = group[0]
        article_groups.append(
            {
                "title": title,
                "articles": group,
                "main": main_article,
                "snippet": getattr(
                    main_article, "translated_snippet", main_article.body
                ),
            }
        )

    sources_result = await db.execute(select(Source).order_by(Source.name))
    sources = sources_result.scalars().all()

    context = {
        "request": request,
        "article_groups": article_groups,
        "sources": sources,
        "q": q,
        "source": source,
        "from_filter": from_filter,
        "classification": classification,
        "sort": sort,
        "_": trans,
        "locale": locale,
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="_results.html", context=context
        )

    return templates.TemplateResponse(
        request=request, name="search.html", context=context
    )
