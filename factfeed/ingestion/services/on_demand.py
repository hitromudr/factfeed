"""
Service for on-demand article ingestion.

Used to prioritize fetching content for specific articles, e.g. when requested via UI.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article
from factfeed.ingestion.extractor import extract_article
from factfeed.ingestion.fetcher import fetch_article_page

log = structlog.get_logger()


async def ingest_article_on_demand(session: AsyncSession, article_id: int) -> bool:
    """
    Attempt to fetch and update content for a specific article immediately.

    Returns True if content was successfully updated to full content.
    Returns False if download failed or extraction resulted in partial content.
    """
    # 1. Fetch article record
    stmt = select(Article).where(Article.id == article_id)
    result = await session.execute(stmt)
    article = result.scalar_one_or_none()

    if not article:
        log.warning("on_demand_ingest_missing_article", article_id=article_id)
        return False

    # Optimization: if already full, skip
    if not article.is_partial and article.body:
        return True

    log.info("starting_on_demand_ingest", article_id=article_id, url=article.url)

    # 2. Fetch HTML (using curl_cffi via fetcher)
    # We pass None as client because fetch_article_page creates its own session
    html_bytes = await fetch_article_page(article.url, None)

    if not html_bytes:
        log.warning("on_demand_ingest_failed_download", article_id=article_id)
        return False

    # 3. Extract content
    # Pass current body as fallback summary if needed
    extracted = extract_article(html_bytes, article.url, "")

    if extracted["is_partial"]:
        log.info("on_demand_ingest_still_partial", article_id=article_id)
        return False

    # 4. Update Article
    if extracted.get("title"):
        article.title = extracted["title"]

    article.body = extracted["body"]
    article.body_html = extracted["body_html"]

    if extracted.get("author"):
        article.author = extracted["author"]

    if extracted.get("lead_image_url"):
        article.lead_image_url = extracted["lead_image_url"]

    article.is_partial = False

    await session.commit()

    log.info("on_demand_ingest_success", article_id=article_id)
    return True
