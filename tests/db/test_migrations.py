"""
Migration smoke tests for Phase 1: Database Foundation.

These tests verify the physical PostgreSQL schema matches all Phase 1 success criteria:
1. articles, sentences, sources tables exist
2. search_vector is a GENERATED ALWAYS AS STORED tsvector column with GIN index
3. sentences is a child table (not JSON) with label, confidence, position columns
4. url_hash has a unique constraint for deduplication
5. Inserting an article populates search_vector automatically

Tests run against a real PostgreSQL database (factfeed_test).
SQLite cannot be used — GENERATED ALWAYS AS and GIN indexes are PostgreSQL-specific.
"""

import pytest
from sqlalchemy import insert, select, text

from factfeed.db.models import Article, Sentence, Source

# ---------------------------------------------------------------------------
# Table existence tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tables_exist(db_session):
    """All three required tables must exist in the database."""
    result = await db_session.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('articles', 'sentences', 'sources')
            ORDER BY table_name
        """)
    )
    tables = [row[0] for row in result.fetchall()]
    assert "articles" in tables, "articles table missing"
    assert "sentences" in tables, "sentences table missing"
    assert "sources" in tables, "sources table missing"


# ---------------------------------------------------------------------------
# search_vector GENERATED column tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_vector_is_generated_column(db_session):
    """search_vector must be a GENERATED ALWAYS AS ... STORED column."""
    result = await db_session.execute(
        text("""
            SELECT is_generated, generation_expression
            FROM information_schema.columns
            WHERE table_name = 'articles'
              AND column_name = 'search_vector'
        """)
    )
    row = result.fetchone()
    assert row is not None, "search_vector column does not exist on articles"
    assert row[0] == "ALWAYS", (
        f"search_vector must be GENERATED ALWAYS AS, got is_generated={row[0]!r}"
    )


@pytest.mark.asyncio
async def test_gin_index_exists(db_session):
    """GIN index ix_articles_search_vector must exist on articles.search_vector."""
    result = await db_session.execute(
        text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'articles'
              AND indexname = 'ix_articles_search_vector'
        """)
    )
    row = result.fetchone()
    assert row is not None, "GIN index ix_articles_search_vector not found on articles"
    assert "gin" in row[1].lower(), f"Expected GIN index, got: {row[1]}"


# ---------------------------------------------------------------------------
# url_hash unique constraint test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_url_hash_unique_constraint_exists(db_session):
    """url_hash must have a unique constraint on articles."""
    result = await db_session.execute(
        text("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'articles'
              AND constraint_type = 'UNIQUE'
        """)
    )
    constraints = [row[0] for row in result.fetchall()]
    assert any("url_hash" in c for c in constraints), (
        f"No UNIQUE constraint on url_hash found. Constraints: {constraints}"
    )


# ---------------------------------------------------------------------------
# sentences child table tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sentences_columns_exist(db_session):
    """sentences table must have article_id, position, text, label, confidence columns."""
    result = await db_session.execute(
        text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'sentences'
            ORDER BY column_name
        """)
    )
    columns = {row[0]: row[1] for row in result.fetchall()}
    assert "article_id" in columns, "article_id column missing from sentences"
    assert "position" in columns, "position column missing from sentences"
    assert "text" in columns, "text column missing from sentences"
    assert "label" in columns, "label column missing from sentences"
    assert "confidence" in columns, "confidence column missing from sentences"


@pytest.mark.asyncio
async def test_sentences_fk_to_articles(db_session):
    """sentences.article_id must be a foreign key referencing articles.id."""
    result = await db_session.execute(
        text("""
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            JOIN information_schema.referential_constraints AS rc
                ON rc.constraint_name = tc.constraint_name
            WHERE tc.table_name = 'sentences'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'article_id'
        """)
    )
    row = result.fetchone()
    assert row is not None, "sentences.article_id foreign key to articles not found"
    assert row[2] == "articles", f"FK references {row[2]!r}, expected 'articles'"
    assert row[3] == "CASCADE", f"FK delete rule is {row[3]!r}, expected CASCADE"


# ---------------------------------------------------------------------------
# Behavioral test: search_vector auto-populated on INSERT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_vector_auto_populated_on_insert(db_session):
    """Inserting an article must auto-populate search_vector without explicit assignment."""
    # Insert a source first (articles has source_id FK)
    source = Source(name="Test Source", feed_url="https://example.com/feed")
    db_session.add(source)
    await db_session.flush()  # Get source.id without committing

    # Insert article — do NOT set search_vector (it's GENERATED ALWAYS AS)
    article = Article(
        url="https://example.com/article/1",
        url_hash="a" * 64,
        title="Climate change drives record temperatures",
        body="Scientists report that global temperatures have hit record highs.",
        source_id=source.id,
    )
    db_session.add(article)
    await db_session.flush()  # Trigger PostgreSQL to compute search_vector

    # Re-query to get the server-computed value
    result = await db_session.execute(
        text("SELECT search_vector::text FROM articles WHERE id = :id"),
        {"id": article.id},
    )
    row = result.fetchone()
    assert row is not None, "Article not found after insert"
    assert row[0] is not None, "search_vector was not populated by PostgreSQL"
    assert len(row[0]) > 0, "search_vector is empty after insert"
    # The tsvector should contain lexemes from the title/body
    assert "climat" in row[0] or "temperatur" in row[0], (
        f"Expected tsvector lexemes in search_vector, got: {row[0][:200]}"
    )


@pytest.mark.asyncio
async def test_url_hash_unique_constraint_enforced(db_session):
    """Inserting two articles with the same url_hash must raise an IntegrityError."""
    import sqlalchemy.exc

    source = Source(name="Dup Test Source", feed_url="https://example-dup.com/feed")
    db_session.add(source)
    await db_session.flush()

    article1 = Article(
        url="https://example.com/article/dup",
        url_hash="b" * 64,
        title="First article",
        body="First body.",
        source_id=source.id,
    )
    db_session.add(article1)
    await db_session.flush()

    article2 = Article(
        url="https://example.com/article/dup-different-url",
        url_hash="b" * 64,  # Same url_hash — must be rejected
        title="Second article",
        body="Second body.",
        source_id=source.id,
    )
    db_session.add(article2)

    with pytest.raises(sqlalchemy.exc.IntegrityError, match="articles_url_hash_key"):
        await db_session.flush()
