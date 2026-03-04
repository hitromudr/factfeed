"""Article detail route with sentence highlighting and collapsible opinions."""

import asyncio
from typing import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article
from factfeed.db.session import AsyncSessionLocal
from factfeed.ingestion.services.on_demand import ingest_article_on_demand
from factfeed.nlp.translator import get_or_create_translation, translate_text
from factfeed.web.deps import get_db
from factfeed.web.i18n import get_locale, get_translator
from factfeed.web.templating import templates

router = APIRouter()


def _confidence_label(confidence: float | None) -> str:
    """Convert raw confidence float to High/Medium/Low display label."""
    if confidence is None:
        return "Unknown"
    if confidence >= 0.7:
        return "High"
    if confidence >= 0.4:
        return "Medium"
    return "Low"


async def _background_ingest_task(article_id: int, zs_pipeline=None, calibrator=None):
    """Background task to attempt fetching full content or classify if unclassified."""
    from sqlalchemy import func

    from factfeed.db.models import Sentence

    async with AsyncSessionLocal() as session:
        # Fetch article first
        stmt = (
            select(Article)
            .options(selectinload(Article.source))
            .where(Article.id == article_id)
        )
        result = await session.execute(stmt)
        article = result.scalar_one_or_none()

        if not article:
            return

        # Attempt to ingest full content if partial
        if article.is_partial:
            success = await ingest_article_on_demand(session, article_id)
            if not success:
                return  # If fetch failed, we still have no body, can't classify
            await session.refresh(article)

        # Check if sentences exist
        stmt_sents = select(func.count(Sentence.id)).where(
            Sentence.article_id == article.id
        )
        has_sents = (await session.execute(stmt_sents)).scalar() > 0

        # Classify immediately if we have a body but no sentences
        if not has_sents and article.body and zs_pipeline:
            try:
                from factfeed.nlp.persist import persist_sentences
                from factfeed.nlp.pipeline import classify_article_async

                source_name = article.source.name if article.source else ""
                results = await classify_article_async(
                    article.body, zs_pipeline, calibrator, source_name
                )
                await persist_sentences(article.id, results, session)
            except Exception:
                import structlog

                log = structlog.get_logger()
                log.error(
                    "background_classification_failed",
                    article_id=article_id,
                    exc_info=True,
                )


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

    # If article is partial or lacks sentences, trigger background task
    needs_processing = article.is_partial or not article.sentences
    if needs_processing:
        background_tasks.add_task(
            _background_ingest_task,
            article.id,
            getattr(request.app.state, "zs_pipeline", None),
            getattr(request.app.state, "calibrator", None),
        )

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

    # Calculate queue estimation if waiting for classification
    queue_info = None
    if not article.sentences and article.body:
        from sqlalchemy import func

        from factfeed.db.models import Sentence

        # Count unclassified articles ahead in the queue (ID < current)
        subq_classified = select(Sentence.article_id).distinct().scalar_subquery()
        stmt_queue = (
            select(func.count(Article.id))
            .where(Article.body.is_not(None))
            .where(Article.body != "")
            .where(Article.id.notin_(subq_classified))
            .where(Article.id < article.id)
        )
        position = (await db.execute(stmt_queue)).scalar() or 0
        position += 1  # 1-based rank

        # Rough estimate: ~2s per article on average
        est_seconds = position * 2
        if est_seconds >= 60:
            est_wait = f"~{(est_seconds + 59) // 60} min"
        else:
            est_wait = f"~{est_seconds} sec"
        queue_info = {"position": position, "est_wait": est_wait}

    return templates.TemplateResponse(
        request=request,
        name="article.html",
        context={
            "article": article,
            "sentences": article.sentences,
            "has_classification": has_classification,
            "confidence_label": _confidence_label,
            "similar_articles": similar_articles,
            "queue_info": queue_info,
            "_": trans,
            "locale": locale,
        },
    )


@router.get("/article/{article_id}/inline", response_class=HTMLResponse)
async def article_inline(
    request: Request,
    article_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    trans: Callable[[str], str] = Depends(get_translator),
    locale: str = Depends(get_locale),
):
    """Render inline article detail for search results."""
    stmt = (
        select(Article)
        .options(selectinload(Article.source), selectinload(Article.sentences))
        .where(Article.id == article_id)
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()

    if article is None:
        return HTMLResponse("Article not found", status_code=404)

    # If article is partial or lacks sentences, trigger background task
    needs_processing = article.is_partial or not article.sentences
    if needs_processing:
        background_tasks.add_task(
            _background_ingest_task,
            article.id,
            getattr(request.app.state, "zs_pipeline", None),
            getattr(request.app.state, "calibrator", None),
        )

    # Translate title immediately (using DB cache if available)
    if locale != "en":
        await get_or_create_translation(db, article, locale)

    # Add confidence labels to all sentences
    for s in article.sentences:
        s.confidence_label = _confidence_label(s.confidence)

    # Calculate queue estimation if waiting for classification
    queue_info = None
    if not article.sentences and article.body:
        from sqlalchemy import func

        from factfeed.db.models import Sentence

        # Count unclassified articles ahead in the queue (ID < current)
        subq_classified = select(Sentence.article_id).distinct().scalar_subquery()
        stmt_queue = (
            select(func.count(Article.id))
            .where(Article.body.is_not(None))
            .where(Article.body != "")
            .where(Article.id.notin_(subq_classified))
            .where(Article.id < article.id)
        )
        position = (await db.execute(stmt_queue)).scalar() or 0
        position += 1  # 1-based rank

        # Rough estimate: ~2s per article on average
        est_seconds = position * 2
        if est_seconds >= 60:
            est_wait = f"~{(est_seconds + 59) // 60} min"
        else:
            est_wait = f"~{est_seconds} sec"
        queue_info = {"position": position, "est_wait": est_wait}

    return templates.TemplateResponse(
        request=request,
        name="partials/_article_inline.html",
        context={
            "article": article,
            "sentences": article.sentences,
            "confidence_label": _confidence_label,
            "queue_info": queue_info,
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

        # Ensure title/body translation is cached/fetched
        _, translation_obj = await get_or_create_translation(db, article, locale)

        # Load from cache if available
        cached_sents = {}
        if translation_obj and translation_obj.sentences_data:
            cached_sents = translation_obj.sentences_data.copy()

        tasks = []
        task_indices = []

        for s in display_sentences:
            idx_str = str(s.position)
            if idx_str in cached_sents:
                s.text = cached_sents[idx_str]
            else:
                tasks.append(translate_text(s.text, locale))
                task_indices.append(idx_str)

        if tasks:
            translated_texts = await asyncio.gather(*tasks)
            # Update cache with new translations only if successful
            for idx_str, t_text in zip(task_indices, translated_texts):
                if t_text is not None:
                    cached_sents[idx_str] = t_text

                # Find the sentence object to update its text (use fallback if None)
                for s in display_sentences:
                    if str(s.position) == idx_str:
                        s.text = t_text if t_text is not None else s.text
                        break

            # Save the updated sentence cache to the database
            if translation_obj:
                translation_obj.sentences_data = cached_sents
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(translation_obj, "sentences_data")
                await db.commit()

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
    """Force sync article content from source and re-classify immediately."""
    # Force bypass the 'already full' check
    success = await ingest_article_on_demand(db, article_id, force=True)

    # Run classification synchronously so the user sees results immediately upon reload
    zs_pipeline = getattr(request.app.state, "zs_pipeline", None)
    calibrator = getattr(request.app.state, "calibrator", None)

    if success and zs_pipeline:
        stmt = (
            select(Article)
            .options(selectinload(Article.source))
            .where(Article.id == article_id)
        )
        article = (await db.execute(stmt)).scalar_one()

        if article.body:
            from factfeed.nlp.persist import persist_sentences
            from factfeed.nlp.pipeline import classify_article_async

            source_name = article.source.name if article.source else ""
            results = await classify_article_async(
                article.body, zs_pipeline, calibrator, source_name
            )
            await persist_sentences(article.id, results, db)

            # Clear sentence translation cache to force re-translation
            from sqlalchemy import update

            from factfeed.db.models import Translation

            await db.execute(
                update(Translation)
                .where(Translation.article_id == article.id)
                .values(sentences_data=None)
            )
            await db.commit()

    # Redirect back to the article page to refresh content.
    # Using referer to preserve query params like 'lang'.
    redirect_url = request.headers.get("referer") or f"/article/{article_id}"
    return RedirectResponse(url=redirect_url, status_code=303)
