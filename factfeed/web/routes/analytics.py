"""Analytics dashboard route and logic."""

import json
from typing import Callable

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Source
from factfeed.services.analytics import (
    get_geographic_stats,
    get_source_factuality_stats,
)
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_locale, get_translator
from factfeed.web.routes.search import _attach_fact_scores
from factfeed.web.templating import templates

router = APIRouter()


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    locale: str = Depends(get_locale),
    trans: Callable[[str], str] = Depends(get_translator),
):
    """Render the analytics dashboard."""
    stats = await get_source_factuality_stats(db)
    geo_stats = await get_geographic_stats(db)

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "request": request,
            "locale": locale,
            "_": trans,
            "active_page": "analytics",
            "stats": stats,
            "stats_json": json.dumps(stats),
            "geo_stats": geo_stats,
            "geo_stats_json": json.dumps(geo_stats),
        },
    )


@router.get("/analytics/drilldown", response_class=HTMLResponse)
async def analytics_drilldown(
    request: Request,
    source: str = Query(..., description="Source name"),
    label: str = Query(..., description="Classification label"),
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
    locale: str = Depends(get_locale),
):
    """Return filtered articles for drill-down view."""
    # Find source
    src_stmt = select(Source).where(Source.name == source)
    src_res = await db.execute(src_stmt)
    src_obj = src_res.scalar_one_or_none()

    if not src_obj:
        return HTMLResponse(f"<p>{trans('Source not found')}</p>")

    # Fetch recent articles (limit 100 to filter from)
    stmt = (
        select(Article)
        .where(Article.source_id == src_obj.id)
        .order_by(Article.published_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    articles = result.scalars().all()

    # Calculate scores
    await _attach_fact_scores(db, articles)

    # Filter based on label
    filtered = []
    target_label = label.lower()

    for art in articles:
        total = getattr(art, "total_count", 0) or 0
        fact = getattr(art, "fact_count", 0) or 0
        ratio = fact / total if total > 0 else 0

        art_label = "unclear"
        if total > 0:
            if ratio >= 0.7:
                art_label = "fact"
            elif ratio <= 0.4:
                art_label = "opinion"
            else:
                art_label = "mixed"

        if art_label == target_label:
            filtered.append(art)

    return templates.TemplateResponse(
        request=request,
        name="_drilldown_results.html",
        context={
            "articles": filtered[:20],
            "_": trans,
            "locale": locale,
            "source_name": source,
            "label": label,
        },
    )
