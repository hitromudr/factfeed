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

    Uses ON CONFLICT DO UPDATE on feed_url so metadata (country/region) is kept up to date.
    """
    for source in sources:
        insert_stmt = pg_insert(Source).values(
            name=source["name"],
            feed_url=source["feed_url"],
            country_code=source.get("country_code"),
            region=source.get("region"),
        )
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["feed_url"],
            set_={
                "name": insert_stmt.excluded.name,
                "country_code": insert_stmt.excluded.country_code,
                "region": insert_stmt.excluded.region,
            },
        )
        await session.execute(stmt)
    await session.commit()
    log.info("sources_seeded", count=len(sources))
