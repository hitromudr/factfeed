"""Integration tests for UI article interactions (expand/collapse)."""

import pytest

from factfeed.db.models import Article, Source


@pytest.mark.asyncio
async def test_article_inline_expand(client, db_session):
    """Test retrieving the inline article wrapper (expand action)."""
    # Setup data
    source = Source(name="Test Source", feed_url="http://test.com/rss")
    db_session.add(source)
    await db_session.flush()

    article = Article(
        title="Test Article",
        url="http://test.com/1",
        url_hash="hash1",
        body="This is the body content.",
        source_id=source.id,
        is_partial=False,
    )
    db_session.add(article)
    await db_session.commit()

    # Test expanding an article
    # Default locale should be 'en'
    response = await client.get(f"/article/{article.id}/inline")

    assert response.status_code == 200
    html = response.text

    # Verify container structure
    assert 'class="article-inline-content"' in html
    assert f'id="article-content-{article.id}"' in html

    # Verify controls existence
    # Collapse button
    assert "toggleArticle" in html
    # Original link
    assert article.url in html

    # Since it is English and fully fetched, content should be rendered directly (no htmx lazy load)
    assert "This is the body content." in html

    # Verify classification pending status (since no sentences added)
    assert "Classification pending" in html


@pytest.mark.asyncio
async def test_article_inline_expand_partial(client, db_session):
    """Test inline expansion for a partial article (should show loader/syncing)."""
    source = Source(name="Test Source", feed_url="http://test.com/rss2")
    db_session.add(source)
    await db_session.flush()

    article = Article(
        title="Partial Article",
        url="http://test.com/2",
        url_hash="hash2",
        body="Summary only.",
        source_id=source.id,
        is_partial=True,
    )
    db_session.add(article)
    await db_session.commit()

    response = await client.get(f"/article/{article.id}/inline")

    assert response.status_code == 200
    html = response.text

    # Should show syncing state
    assert "Syncing full content from source..." in html
    assert "spinner" in html
    # Should have polling enabled
    assert f'hx-get="/article/{article.id}/content?teaser=false"' in html


@pytest.mark.asyncio
async def test_article_content_loading(client, db_session):
    """Test loading article content endpoint directly."""
    source = Source(name="Test Source", feed_url="http://test.com/rss3")
    db_session.add(source)
    await db_session.flush()

    article = Article(
        title="Test Content",
        url="http://test.com/3",
        url_hash="hash3",
        body="<p>Full article body here.</p>",
        source_id=source.id,
        is_partial=False,
    )
    db_session.add(article)
    await db_session.commit()

    response = await client.get(f"/article/{article.id}/content")

    assert response.status_code == 200
    assert "Full article body here." in response.text


@pytest.mark.asyncio
async def test_article_not_found(client):
    """Test inline expansion for non-existent article."""
    response = await client.get("/article/999999/inline")
    assert response.status_code == 404
    assert "Article not found" in response.text
