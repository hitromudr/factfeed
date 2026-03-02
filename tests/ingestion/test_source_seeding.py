import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Source
from factfeed.ingestion.persister import seed_sources


@pytest.mark.asyncio
async def test_seed_sources_initial(db_session: AsyncSession):
    """Test initial seeding of sources."""
    sources = [
        {
            "name": "Source A",
            "feed_url": "http://a.com/rss",
            "country_code": "US",
            "region": "North America",
        },
        {
            "name": "Source B",
            "feed_url": "http://b.com/rss",
            # No country/region initially
        },
    ]

    await seed_sources(db_session, sources)

    # Verify Source A
    stmt = select(Source).where(Source.name == "Source A")
    result = await db_session.execute(stmt)
    source_a = result.scalar_one()
    assert source_a.feed_url == "http://a.com/rss"
    assert source_a.country_code == "US"
    assert source_a.region == "North America"

    # Verify Source B
    stmt = select(Source).where(Source.name == "Source B")
    result = await db_session.execute(stmt)
    source_b = result.scalar_one()
    assert source_b.feed_url == "http://b.com/rss"
    assert source_b.country_code is None
    assert source_b.region is None


@pytest.mark.asyncio
async def test_seed_sources_update(db_session: AsyncSession):
    """Test that seeding updates existing records correctly."""
    # Initial seed
    initial_sources = [
        {
            "name": "Source A",
            "feed_url": "http://a.com/rss",
            "country_code": "US",
            "region": "North America",
        }
    ]
    await seed_sources(db_session, initial_sources)

    # Update seed with changed metadata
    updated_sources = [
        {
            "name": "Source A Renamed",  # Name change
            "feed_url": "http://a.com/rss",  # Same URL (key)
            "country_code": "CA",  # Changed country
            "region": "North America",
        }
    ]
    await seed_sources(db_session, updated_sources)

    stmt = select(Source).where(Source.feed_url == "http://a.com/rss")
    result = await db_session.execute(stmt)
    source = result.scalar_one()

    assert source.name == "Source A Renamed"
    assert source.country_code == "CA"
    assert source.region == "North America"
