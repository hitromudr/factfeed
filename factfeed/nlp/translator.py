"""
Translation service with database persistence.

Handles translating articles (title, body) and persisting results to
the 'translations' table to avoid repeated external API calls.
"""

import asyncio
import logging

from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Translation

log = logging.getLogger(__name__)


def get_translator_instance(target: str = "ru") -> GoogleTranslator:
    """Get a fresh translator instance for the target language."""
    return GoogleTranslator(source="auto", target=target)


async def translate_text(text: str, target: str) -> str:
    """Translate a single text string asynchronously with a timeout.

    This function does NOT check the database cache; it is a direct wrapper
    around the translation API. Use get_or_create_translation for articles.
    """
    if not text or target == "en":
        return text

    # Quick check for empty or whitespace-only strings
    if not text.strip():
        return text

    translator = get_translator_instance(target)
    try:
        loop = asyncio.get_running_loop()
        # deep-translator is synchronous, run in thread pool.
        # Wrap in wait_for to prevent infinite hanging if the API/proxy stalls.
        translated = await asyncio.wait_for(
            loop.run_in_executor(None, translator.translate, text), timeout=5.0
        )
        return translated or text
    except asyncio.TimeoutError:
        log.warning("translation_timeout: target='%s', text_len=%d", target, len(text))
        return text
    except Exception as e:
        log.warning("translation_failed: error='%s', target='%s'", str(e), target)
        return text


async def get_or_create_translation(
    db: AsyncSession, article: Article, target_lang: str
) -> Article:
    """Get translated title/body from DB or fetch from API and save.

    Updates the passed article object's title and body in-place (in memory)
    with the translated values.

    Note: This handles the Article title and body fields. It does NOT automatically
    handle the 'sentences' relationship list. Callers needing sentence-level
    translation must handle that separately (potentially using translate_text).
    """
    if target_lang == "en":
        return article

    # Ensure session-level locking to allow concurrent calls (e.g. asyncio.gather)
    if not hasattr(db, "_translation_lock"):
        db._translation_lock = asyncio.Lock()

    # 1. Check DB for existing translation
    async with db._translation_lock:
        stmt = select(Translation).where(
            Translation.article_id == article.id,
            Translation.language == target_lang,
        )
        result = await db.execute(stmt)
        translation = result.scalar_one_or_none()

    if translation:
        # Found cached translation
        if translation.title:
            article.title = translation.title
        if translation.body:
            article.body = translation.body
        return article

    # 2. Fetch from API (Cache Miss)
    tasks = []

    # Task 0: Title
    if article.title:
        tasks.append(translate_text(article.title, target_lang))
    else:
        tasks.append(asyncio.sleep(0, result=""))

    # Task 1: Body
    if article.body:
        tasks.append(translate_text(article.body, target_lang))
    else:
        tasks.append(asyncio.sleep(0, result=""))

    # If translation tasks timeout, they return the original text gracefully.
    results = await asyncio.gather(*tasks)
    translated_title = results[0]
    translated_body = results[1]

    # 3. Save to DB
    # We use upsert to be safe against race conditions
    if translated_title or translated_body:
        upsert_stmt = (
            pg_insert(Translation)
            .values(
                article_id=article.id,
                language=target_lang,
                title=translated_title,
                body=translated_body,
            )
            .on_conflict_do_update(
                index_elements=["article_id", "language"],
                set_={"title": translated_title, "body": translated_body},
            )
        )
        try:
            async with db._translation_lock:
                await db.execute(upsert_stmt)
                await db.commit()
        except Exception as e:
            log.error("translation_save_failed: %s", str(e))
            async with db._translation_lock:
                await db.rollback()

    # 4. Update in-memory object
    if translated_title:
        article.title = translated_title
    if translated_body:
        article.body = translated_body

    return article
