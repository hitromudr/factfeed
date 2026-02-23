"""Article persistence with conflict-skip on url_hash."""

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Source

log = structlog.get_logger()


async def save_article(session: AsyncSession, article_data: dict) -> bool:
    """Insert an article, silently skipping duplicates via ON CONFLICT DO NOTHING.

    Returns True if the article was inserted, False if it was a duplicate.
    """
    stmt = (
        pg_insert(Article)
        .values(**article_data)
        .on_conflict_do_nothing(index_elements=["url_hash"])
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount == 1


async def seed_sources(session: AsyncSession, sources: list[dict]) -> None:
    """Upsert source definitions into the database.

    Uses ON CONFLICT DO NOTHING on feed_url so re-runs are idempotent.
    """
    for source in sources:
        stmt = (
            pg_insert(Source)
            .values(name=source["name"], feed_url=source["feed_url"])
            .on_conflict_do_nothing(index_elements=["feed_url"])
        )
        await session.execute(stmt)
    await session.commit()
    log.info("sources_seeded", count=len(sources))
