"""Article detail route with sentence highlighting and collapsible opinions."""

import asyncio
from typing import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article
from factfeed.db.session import AsyncSessionLocal
from factfeed.ingestion.services.on_demand import ingest_article_on_demand
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


async def _background_ingest_task(article_id: int):
    """Background task to attempt fetching full content for partial articles."""
    async with AsyncSessionLocal() as session:
        await ingest_article_on_demand(session, article_id)


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(
    request: Request,
    article_id: int,
    background_tasks: BackgroundTasks,
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

    # If article is partial (only RSS summary), trigger full fetch in background
    if article.is_partial:
        background_tasks.add_task(_background_ingest_task, article.id)

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

    has_classification = any(
        s.label in ("fact", "opinion", "mixed") for s in article.sentences
    )

    return templates.TemplateResponse(
        request=request,
        name="article.html",
        context={
            "article": article,
            "sentences": article.sentences,
            "has_classification": has_classification,
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
    teaser: bool = True,
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

    display_sentences = article.sentences
    show_read_more = False

    if locale != "en":
        # Lazy loading: translate only first 4 sentences initially (approx 1 paragraph)
        # Only if we have significantly more sentences (>6) to justify a "Read More" button
        if teaser and len(article.sentences) > 6:
            display_sentences = article.sentences[:4]
            show_read_more = True

        # Ensure title/body translation is cached/fetched (even if using sentences for display)
        await get_or_create_translation(db, article, locale)

        # Translate the specific sentences we are displaying
        tasks = [translate_text(s.text, locale) for s in display_sentences]
        if tasks:
            translated_texts = await asyncio.gather(*tasks)
            for s, t_text in zip(display_sentences, translated_texts):
                s.text = t_text

    # Add confidence labels
    for s in display_sentences:
        s.confidence_label = _confidence_label(s.confidence)

    # We only render the body part.
    # To support the "Read More" button without modifying the template significantly,
    # we render the body template and append the button HTML if needed.
    content_html = templates.get_template("_article_body.html").render(
        article=article,
        sentences=display_sentences,
        confidence_label=_confidence_label,
        _=trans,
    )

    if show_read_more:
        # Button to load full content (teaser=false)
        button_html = f"""
        <div id="read-more-wrapper" style="margin-top: 2rem; text-align: center; padding-top: 1rem; border-top: 1px dashed var(--border-color);">
            <button hx-get="/article/{article.id}/content?lang={locale}&teaser=false"
                    hx-target=".article-body"
                    hx-swap="innerHTML"
                    class="btn-secondary"
                    style="cursor: pointer; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.5rem 1rem;">
                {trans("Read full translated article")} ({len(article.sentences)} {trans("sentences")})
            </button>
        </div>
        """
        content_html += button_html

    return HTMLResponse(content=content_html)


@router.post("/article/{article_id}/sync")
async def sync_article(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Force sync article content from source."""
    await ingest_article_on_demand(db, article_id)

    # Redirect back to the article page to refresh content.
    # Using referer to preserve query params like 'lang'.
    redirect_url = request.headers.get("referer") or f"/article/{article_id}"
    return RedirectResponse(url=redirect_url, status_code=303)
