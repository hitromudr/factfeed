"""Integration tests for search flow, filters, and sorting."""

import pytest

from factfeed.db.models import Article, Sentence, Source


@pytest.mark.asyncio
async def test_search_basic(client, db_session):
    """Test basic search functionality."""
    source = Source(name="Search Source", feed_url="http://test.com/search")
    db_session.add(source)
    await db_session.flush()

    article = Article(
        title="Python testing with pytest",
        url="http://test.com/search1",
        url_hash="hash_search1",
        body="Pytest makes testing easy and fun.",
        source_id=source.id,
        is_partial=False,
    )
    db_session.add(article)
    await db_session.commit()

    # Search for "pytest"
    response = await client.get("/search", params={"q": "pytest"})
    assert response.status_code == 200
    assert "Python testing with pytest" in response.text

    # Search for non-existent term
    response = await client.get("/search", params={"q": "cobra"})
    assert response.status_code == 200
    assert "Python testing with pytest" not in response.text
    assert "No articles found" in response.text


@pytest.mark.asyncio
async def test_search_filters_source(client, db_session):
    """Test filtering by source."""
    s1 = Source(name="Source A", feed_url="http://a.com")
    s2 = Source(name="Source B", feed_url="http://b.com")
    db_session.add_all([s1, s2])
    await db_session.flush()

    a1 = Article(
        title="Article from A",
        url="http://a.com/1",
        url_hash="h1",
        body="Body A",
        source_id=s1.id,
    )
    a2 = Article(
        title="Article from B",
        url="http://b.com/1",
        url_hash="h2",
        body="Body B",
        source_id=s2.id,
    )
    db_session.add_all([a1, a2])
    await db_session.commit()

    # Filter source A
    response = await client.get("/search", params={"source": str(s1.id)})
    assert "Article from A" in response.text
    assert "Article from B" not in response.text

    # Filter source B
    response = await client.get("/search", params={"source": str(s2.id)})
    assert "Article from A" not in response.text
    assert "Article from B" in response.text


@pytest.mark.asyncio
async def test_search_filters_classification(client, db_session):
    """Test filtering by classification (fact/opinion)."""
    source = Source(name="Src", feed_url="http://src.com")
    db_session.add(source)
    await db_session.flush()

    # Fact article (100% fact sentences)
    a_fact = Article(
        title="Factual News",
        url="http://src.com/fact",
        url_hash="fact",
        body="This is a fact.",
        source_id=source.id,
    )
    db_session.add(a_fact)
    await db_session.flush()
    db_session.add(
        Sentence(article_id=a_fact.id, position=0, text="This is a fact.", label="fact")
    )

    # Opinion article (100% opinion sentences)
    a_op = Article(
        title="Opinion Piece",
        url="http://src.com/op",
        url_hash="op",
        body="I think this is bad.",
        source_id=source.id,
    )
    db_session.add(a_op)
    await db_session.flush()
    db_session.add(
        Sentence(
            article_id=a_op.id, position=0, text="I think this is bad.", label="opinion"
        )
    )

    await db_session.commit()

    # Filter facts
    response = await client.get("/search", params={"classification": "fact"})
    assert "Factual News" in response.text
    assert "Opinion Piece" not in response.text

    # Filter opinions
    response = await client.get("/search", params={"classification": "opinion"})
    assert "Factual News" not in response.text
    assert "Opinion Piece" in response.text


@pytest.mark.asyncio
async def test_search_sort_order(client, db_session):
    """Test sorting results."""
    # We rely on DB-side sorting logic, so this test ensures the parameter is accepted
    # and results are returned without error. Precise order validation requires careful timestamps setup.
    source = Source(name="Src", feed_url="http://src.com")
    db_session.add(source)
    await db_session.flush()

    a1 = Article(
        title="First",
        url="u1",
        url_hash="h1",
        body="b1",
        source_id=source.id,
    )
    a2 = Article(
        title="Second",
        url="u2",
        url_hash="h2",
        body="b2",
        source_id=source.id,
    )
    db_session.add_all([a1, a2])
    await db_session.commit()

    # Sort by recent
    response = await client.get("/search", params={"sort": "recent"})
    assert response.status_code == 200
    assert "First" in response.text
    assert "Second" in response.text

    # Sort by facts
    response = await client.get("/search", params={"sort": "facts"})
    assert response.status_code == 200
