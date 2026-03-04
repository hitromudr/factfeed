"""System monitoring routes for UI widgets."""

import copy
from typing import Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Sentence
from factfeed.services.system_monitor import monitor
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_translator
from factfeed.web.templating import templates

router = APIRouter()


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
    classified_count = await db.scalar(
        select(func.count(func.distinct(Sentence.article_id)))
    )

    return templates.TemplateResponse(
        request=request,
        name="_system_monitor.html",
        context={
            "state": state,
            "db_articles_count": articles_count or 0,
            "db_classified_count": classified_count or 0,
            "_": trans,
        },
    )
