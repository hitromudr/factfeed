import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Sentence, Source
from factfeed.services.analytics import (
    get_geographic_stats,
    get_source_factuality_stats,
)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Create an httpx async test client with the FastAPI app."""
    from factfeed.web.deps import get_db
    from factfeed.web.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_service_aggregation(db_session: AsyncSession):
    """Test that the analytics service correctly aggregates sentence labels."""
    # Setup test data
    source1 = Source(name="Test Source A", feed_url="http://a.com/rss")
    source2 = Source(name="Test Source B", feed_url="http://b.com/rss")
    db_session.add_all([source1, source2])
    await db_session.flush()

    article1 = Article(
        url="http://a.com/1",
        url_hash="hash1",
        title="Article 1",
        source_id=source1.id,
    )
    article2 = Article(
        url="http://b.com/1",
        url_hash="hash2",
        title="Article 2",
        source_id=source2.id,
    )
    db_session.add_all([article1, article2])
    await db_session.flush()

    # Source 1: 2 facts, 1 opinion
    s1_1 = Sentence(article_id=article1.id, position=1, text="Fact 1", label="fact")
    s1_2 = Sentence(article_id=article1.id, position=2, text="Fact 2", label="fact")
    s1_3 = Sentence(article_id=article1.id, position=3, text="Op 1", label="opinion")

    # Source 2: 0 facts, 2 opinions, 1 mixed
    s2_1 = Sentence(article_id=article2.id, position=1, text="Op 2", label="opinion")
    s2_2 = Sentence(article_id=article2.id, position=2, text="Op 3", label="opinion")
    s2_3 = Sentence(article_id=article2.id, position=3, text="Mix 1", label="mixed")

    db_session.add_all([s1_1, s1_2, s1_3, s2_1, s2_2, s2_3])
    await db_session.commit()

    # Execute Service
    stats = await get_source_factuality_stats(db_session)

    # Validate Source A
    # The service returns stats sorted by total sentences descending.
    # We find the specific source to verify values.
    res_a = next(s for s in stats if s["source"] == "Test Source A")
    assert res_a["total"] == 3
    assert res_a["facts"] == 2
    assert res_a["opinions"] == 1
    # Score = 2 / (2+1) = 0.666... -> rounded to 0.67
    assert res_a["score"] == 0.67

    # Validate Source B
    res_b = next(s for s in stats if s["source"] == "Test Source B")
    assert res_b["total"] == 3
    assert res_b["facts"] == 0
    assert res_b["opinions"] == 2
    assert res_b["mixed"] == 1
    # Score = 0 / (0+2) = 0.0
    assert res_b["score"] == 0.0


@pytest.mark.asyncio
async def test_analytics_api_endpoint(client, db_session: AsyncSession):
    """Test the JSON API endpoint for source stats."""
    source = Source(name="API Source", feed_url="http://api.com/rss")
    db_session.add(source)
    await db_session.flush()

    article = Article(
        url="http://api.com/1",
        url_hash="hash_api",
        title="API Article",
        source_id=source.id,
    )
    db_session.add(article)
    await db_session.flush()

    sent = Sentence(article_id=article.id, position=1, text="Fact", label="fact")
    db_session.add(sent)
    await db_session.commit()

    response = await client.get("/api/v1/stats/sources")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    item = next((d for d in data if d["source"] == "API Source"), None)
    assert item is not None
    assert item["facts"] == 1
    assert item["score"] == 1.0


@pytest.mark.asyncio
async def test_geographic_stats(db_session: AsyncSession):
    """Test aggregation of articles by country."""
    source_us = Source(
        name="US News",
        feed_url="http://us.com/rss",
        country_code="US",
        region="North America",
    )
    source_gb = Source(
        name="UK News",
        feed_url="http://uk.com/rss",
        country_code="GB",
        region="Europe",
    )
    db_session.add_all([source_us, source_gb])
    await db_session.flush()

    # 2 articles for US, 1 for GB
    a1 = Article(url="u1", url_hash="h1", title="T1", source_id=source_us.id)
    a2 = Article(url="u2", url_hash="h2", title="T2", source_id=source_us.id)
    a3 = Article(url="u3", url_hash="h3", title="T3", source_id=source_gb.id)
    db_session.add_all([a1, a2, a3])
    await db_session.commit()

    stats = await get_geographic_stats(db_session)

    us_stat = next(s for s in stats if s["country"] == "US")
    assert us_stat["count"] == 2
    assert us_stat["region"] == "North America"

    gb_stat = next(s for s in stats if s["country"] == "GB")
    assert gb_stat["count"] == 1


@pytest.mark.asyncio
async def test_geo_stats_api_endpoint(client, db_session: AsyncSession):
    """Test the JSON API endpoint for geo stats."""
    source = Source(
        name="FR News",
        feed_url="http://fr.com/rss",
        country_code="FR",
        region="Europe",
    )
    db_session.add(source)
    await db_session.flush()

    article = Article(
        url="u_fr", url_hash="h_fr", title="FR Title", source_id=source.id
    )
    db_session.add(article)
    await db_session.commit()

    response = await client.get("/api/v1/stats/geo")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    item = next((d for d in data if d["country"] == "FR"), None)
    assert item is not None
    assert item["count"] == 1


@pytest.mark.asyncio
async def test_analytics_ui_route(client):
    """Test that the analytics HTML page loads."""
    response = await client.get("/analytics")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Source Analytics" in response.text
    # Check for Chart.js canvas
    assert 'id="factualityChart"' in response.text
    # Check for Map container
    assert 'id="world-map"' in response.text
