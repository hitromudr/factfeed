import hashlib
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from factfeed.db.models import Article, Sentence, Source
from factfeed.web.deps import get_db
from factfeed.web.main import app


@pytest_asyncio.fixture
async def api_client(db_session):
    """Create an httpx async test client for the API."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_api_data(db_session):
    """Seed test data for API tests."""
    # Create sources
    cnn = Source(name="CNN", feed_url="https://rss.cnn.com/rss/edition.rss")
    fox = Source(
        name="Fox News", feed_url="https://moxie.foxnews.com/feedburner/politics.xml"
    )
    db_session.add_all([cnn, fox])
    await db_session.flush()

    now = datetime.now(timezone.utc)

    # Article 1: CNN, fact-heavy
    art1 = Article(
        url="https://cnn.com/article-1",
        url_hash=hashlib.sha256(b"https://cnn.com/article-1").hexdigest(),
        title="Senate passes new bill",
        body="The Senate passed the bill on Tuesday. The vote was 60-40.",
        published_at=now - timedelta(hours=2),
        source_id=cnn.id,
    )
    # Article 2: Fox, opinion-heavy
    art2 = Article(
        url="https://foxnews.com/article-2",
        url_hash=hashlib.sha256(b"https://foxnews.com/article-2").hexdigest(),
        title="Why the new bill is a disaster",
        body="This legislation will ruin the economy. It is a terrible mistake.",
        published_at=now - timedelta(days=2),
        source_id=fox.id,
    )
    db_session.add_all([art1, art2])
    await db_session.flush()

    # Sentences
    s1 = Sentence(
        article_id=art1.id,
        position=0,
        text="The Senate passed the bill on Tuesday.",
        label="fact",
        confidence=0.95,
    )
    s2 = Sentence(
        article_id=art1.id,
        position=1,
        text="The vote was 60-40.",
        label="fact",
        confidence=0.98,
    )

    s3 = Sentence(
        article_id=art2.id,
        position=0,
        text="This legislation will ruin the economy.",
        label="opinion",
        confidence=0.85,
    )
    s4 = Sentence(
        article_id=art2.id,
        position=1,
        text="It is a terrible mistake.",
        label="opinion",
        confidence=0.90,
    )

    db_session.add_all([s1, s2, s3, s4])
    await db_session.commit()

    return {"cnn": cnn, "fox": fox, "art1": art1, "art2": art2}


@pytest.mark.asyncio
async def test_list_sources(api_client, seed_api_data):
    """GET /api/v1/sources returns list of sources."""
    resp = await api_client.get("/api/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    names = [s["name"] for s in data]
    assert "CNN" in names
    assert "Fox News" in names


@pytest.mark.asyncio
async def test_search_articles(api_client, seed_api_data):
    """GET /api/v1/search returns articles."""
    resp = await api_client.get("/api/v1/search")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2

    # Check structure
    first = data[0]
    assert "id" in first
    assert "title" in first
    assert "source" in first
    assert "fact_count" in first
    assert "fact_pct" in first


@pytest.mark.asyncio
async def test_search_filter_source(api_client, seed_api_data):
    """GET /api/v1/search?source=ID filters by source."""
    cnn_id = seed_api_data["cnn"].id
    resp = await api_client.get(f"/api/v1/search?source={cnn_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"]["name"] == "CNN"


@pytest.mark.asyncio
async def test_search_filter_text(api_client, seed_api_data):
    """GET /api/v1/search?q=Senate filters by text."""
    resp = await api_client.get("/api/v1/search?q=Senate")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "Senate" in data[0]["title"]


@pytest.mark.asyncio
async def test_get_article_detail(api_client, seed_api_data):
    """GET /api/v1/articles/{id} returns full details."""
    art_id = seed_api_data["art1"].id
    resp = await api_client.get(f"/api/v1/articles/{art_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == art_id
    assert data["title"] == "Senate passes new bill"
    assert "sentences" in data
    assert len(data["sentences"]) == 2
    assert data["sentences"][0]["label"] == "fact"


@pytest.mark.asyncio
async def test_get_article_not_found(api_client):
    """GET /api/v1/articles/{id} returns 404 for missing ID."""
    resp = await api_client.get("/api/v1/articles/999999")
    assert resp.status_code == 404
