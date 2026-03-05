"""System monitoring routes for UI widgets and data management."""

import asyncio
import copy
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Sentence, Source, Translation
from factfeed.services.system_monitor import monitor
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_locale, get_translator
from factfeed.web.templating import templates

router = APIRouter()

_ingestion_lock = asyncio.Lock()


async def _get_db_size(db: AsyncSession) -> str:
    """Get total database size as human-readable string."""
    result = await db.execute(
        text("SELECT pg_size_pretty(pg_database_size(current_database()))")
    )
    return result.scalar() or "N/A"


async def _get_table_sizes(db: AsyncSession) -> dict[str, str]:
    """Get sizes of main tables."""
    sizes = {}
    for table in ("articles", "sentences", "translations", "sources"):
        result = await db.execute(
            text(f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))")
        )
        sizes[table] = result.scalar() or "0"
    return sizes


@router.get("/widget", response_class=HTMLResponse)
async def system_widget(
    request: Request,
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
):
    """Render the system monitor widget."""
    state = copy.copy(monitor.state)

    # Fetch actual totals from the database
    articles_count = await db.scalar(select(func.count(Article.id)))
    articles_with_body = await db.scalar(
        select(func.count(Article.id)).where(
            func.length(Article.body) > 0
        )
    )
    classified_count = await db.scalar(
        select(func.count(func.distinct(Sentence.article_id)))
    )
    db_size = await _get_db_size(db)

    return templates.TemplateResponse(
        request=request,
        name="_system_monitor.html",
        context={
            "state": state,
            "db_articles_count": articles_count or 0,
            "db_articles_with_body": articles_with_body or 0,
            "db_classified_count": classified_count or 0,
            "db_size": db_size,
            "_": trans,
        },
    )


@router.get("/manage", response_class=HTMLResponse)
async def manage_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
):
    """Render the data management page."""
    sources = (await db.execute(
        select(Source).order_by(Source.name)
    )).scalars().all()

    # Per-source article counts
    source_stats = (await db.execute(
        select(
            Source.id,
            Source.name,
            func.count(Article.id).label("count"),
        )
        .outerjoin(Article, Article.source_id == Source.id)
        .group_by(Source.id, Source.name)
        .order_by(Source.name)
    )).all()

    table_sizes = await _get_table_sizes(db)
    db_size = await _get_db_size(db)

    # Oldest and newest article dates
    oldest = await db.scalar(
        select(func.min(Article.published_at)).where(Article.published_at.isnot(None))
    )
    newest = await db.scalar(
        select(func.max(Article.published_at)).where(Article.published_at.isnot(None))
    )

    locale = get_locale(request)

    return templates.TemplateResponse(
        request=request,
        name="manage.html",
        context={
            "sources": sources,
            "source_stats": source_stats,
            "table_sizes": table_sizes,
            "db_size": db_size,
            "oldest_date": oldest,
            "newest_date": newest,
            "locale": locale,
            "_": trans,
        },
    )


@router.delete("/articles", response_class=HTMLResponse)
async def delete_articles(
    request: Request,
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
    before: str = Query(None, description="Delete articles before this date (YYYY-MM-DD)"),
    source_id: int = Query(None, description="Delete articles from this source"),
):
    """Delete articles matching criteria. Returns updated stats HTML fragment."""
    conditions = []
    if before:
        cutoff = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        conditions.append(Article.published_at < cutoff)
    if source_id:
        conditions.append(Article.source_id == source_id)

    if not conditions:
        return HTMLResponse(
            f'<div class="manage-result error">{trans("No filter specified")}</div>',
            status_code=400,
        )

    # Count articles to be deleted
    count_stmt = select(func.count(Article.id)).where(*conditions)
    count = await db.scalar(count_stmt) or 0

    if count == 0:
        return HTMLResponse(
            f'<div class="manage-result">{trans("No articles match the criteria")}</div>'
        )

    # Delete (cascades to sentences and translations via FK)
    del_stmt = delete(Article).where(*conditions)
    await db.execute(del_stmt)
    await db.commit()

    return HTMLResponse(
        f'<div class="manage-result success">{trans("Deleted")} {count} {trans("articles")}</div>'
    )


@router.post("/sync", response_class=JSONResponse)
async def trigger_sync(request: Request):
    """Trigger an immediate ingestion cycle."""
    if _ingestion_lock.locked():
        return JSONResponse({"status": "already_running"}, status_code=409)

    async def _run():
        async with _ingestion_lock:
            await request.app.state.ingestion_job()

    asyncio.create_task(_run())
    return {"status": "started"}
