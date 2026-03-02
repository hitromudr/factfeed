"""Analytics dashboard route and logic."""

import json
from typing import Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.services.analytics import (
    get_geographic_stats,
    get_source_factuality_stats,
)
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_locale, get_translator

router = APIRouter()
templates = Jinja2Templates(directory="factfeed/templates")


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
