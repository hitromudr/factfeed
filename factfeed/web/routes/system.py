"""System monitoring routes for UI widgets."""

from typing import Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from factfeed.services.system_monitor import monitor
from factfeed.web.i18n import get_translator

router = APIRouter()
templates = Jinja2Templates(directory="factfeed/templates")


@router.get("/widget", response_class=HTMLResponse)
async def system_widget(
    request: Request,
    trans: Callable[[str], str] = Depends(get_translator),
):
    """Render the system monitor widget."""
    return templates.TemplateResponse(
        request=request,
        name="_system_monitor.html",
        context={
            "state": monitor.state,
            "_": trans,
        },
    )
