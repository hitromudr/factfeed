"""Article detail route with sentence highlighting and collapsible opinions."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article
from factfeed.web.deps import get_db

router = APIRouter()

templates = Jinja2Templates(directory="factfeed/templates")


def _confidence_label(confidence: float | None) -> str:
    """Convert raw confidence float to High/Medium/Low display label."""
    if confidence is None:
        return "Unknown"
    if confidence >= 0.7:
        return "High"
    if confidence >= 0.4:
        return "Medium"
    return "Low"


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Render article detail with inline sentence highlighting."""
    stmt = (
        select(Article)
        .options(selectinload(Article.source), selectinload(Article.sentences))
        .where(Article.id == article_id)
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Split sentences by type for template rendering
    non_opinion_sentences = []
    opinion_sentences = []

    for s in article.sentences:
        s.confidence_label = _confidence_label(s.confidence)
        if s.label == "opinion":
            opinion_sentences.append(s)
        else:
            non_opinion_sentences.append(s)

    return templates.TemplateResponse(
        "article.html",
        {
            "request": request,
            "article": article,
            "sentences": article.sentences,
            "non_opinion_sentences": non_opinion_sentences,
            "opinion_sentences": opinion_sentences,
            "opinion_count": len(opinion_sentences),
            "confidence_label": _confidence_label,
        },
    )
