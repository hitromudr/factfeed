"""Article detail route with sentence highlighting and collapsible opinions."""

import asyncio
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article
from factfeed.nlp.translator import get_or_create_translation, translate_text
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_locale, get_translator

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
    trans: Callable[[str], str] = Depends(get_translator),
    locale: str = Depends(get_locale),
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

    # Find other providers covering the same story
    similar_stmt = (
        select(Article)
        .options(selectinload(Article.source))
        .where(Article.title == article.title, Article.id != article.id)
        .order_by(Article.published_at.desc())
    )
    similar_result = await db.execute(similar_stmt)
    similar_articles = similar_result.scalars().all()

    # Translate title immediately (using DB cache if available)
    if locale != "en":
        await get_or_create_translation(db, article, locale)

    # Add confidence labels to all sentences
    for s in article.sentences:
        s.confidence_label = _confidence_label(s.confidence)

    return templates.TemplateResponse(
        request=request,
        name="article.html",
        context={
            "article": article,
            "sentences": article.sentences,
            "confidence_label": _confidence_label,
            "similar_articles": similar_articles,
            "_": trans,
            "locale": locale,
        },
    )


@router.get("/article/{article_id}/content", response_class=HTMLResponse)
async def article_content(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
    locale: str = Depends(get_locale),
):
    """HTMX endpoint to load translated article content."""
    stmt = (
        select(Article)
        .options(selectinload(Article.sentences))
        .where(Article.id == article_id)
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()

    if not article:
        return ""

    if locale != "en":
        await get_or_create_translation(db, article, locale)

        tasks = [translate_text(s.text, locale) for s in article.sentences]
        if tasks:
            translated_texts = await asyncio.gather(*tasks)
            for s, t_text in zip(article.sentences, translated_texts):
                s.text = t_text

    # Add confidence labels
    for s in article.sentences:
        s.confidence_label = _confidence_label(s.confidence)

    # We only render the body part
    return templates.TemplateResponse(
        request=request,
        name="_article_body.html",
        context={
            "article": article,
            "sentences": article.sentences,
            "confidence_label": _confidence_label,
            "_": trans,
        },
    )
