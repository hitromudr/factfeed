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


async def translate_text(text: str, target: str) -> str | None:
    """Translate a single text string asynchronously with a timeout.

    This function does NOT check the database cache; it is a direct wrapper
    around the translation API. Use get_or_create_translation for articles.
    Returns None on failure to avoid caching un-translated text.
    """
    if not text:
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
        return None
    except Exception as e:
        log.warning("translation_failed: error='%s', target='%s'", str(e), target)
        return None


async def get_or_create_translation(
    db: AsyncSession, article: Article, target_lang: str
) -> tuple[Article, Translation | None]:
    """Get translated title/body from DB or fetch from API and save.

    Updates the passed article object with 'translated_title' and 'translated_body'
    attributes (in memory) to avoid modifying the mapped 'title'/'body' fields
    and causing accidental DB overwrites.
    """
    # If target language is same as article language (defaulting to 'en'),
    # no translation needed.
    source_lang = getattr(article, "language", "en") or "en"
    if target_lang == source_lang:
        return article, None

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
            article.translated_title = translation.title
        if translation.body:
            article.translated_body = translation.body
        return article, translation

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

    # If translation tasks timeout, they return None to prevent caching.
    results = await asyncio.gather(*tasks)
    translated_title = results[0] or article.title  # Fallback to original if None
    translated_body = results[1] or article.body  # Fallback to original if None

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
            .returning(Translation)
        )
        translation_obj = None
        try:
            async with db._translation_lock:
                res = await db.execute(upsert_stmt)
                translation_obj = res.scalar_one_or_none()
                await db.commit()
        except Exception as e:
            log.error("translation_save_failed: %s", str(e))
            async with db._translation_lock:
                await db.rollback()

    # 4. Update in-memory object (Transient attributes)
    if translated_title:
        article.translated_title = translated_title
    if translated_body:
        article.translated_body = translated_body

    # If upsert didn't return an object (e.g. failed), fetch it to be safe
    if translation_obj is None:
        stmt = select(Translation).where(
            Translation.article_id == article.id, Translation.language == target_lang
        )
        translation_obj = (await db.execute(stmt)).scalar_one_or_none()

    return article, translation_obj
