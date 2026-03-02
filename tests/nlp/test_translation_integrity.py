from unittest.mock import patch

import pytest
from sqlalchemy import select

from factfeed.db.models import Article, Source, Translation
from factfeed.nlp.translator import get_or_create_translation


@pytest.mark.asyncio
async def test_translation_length_consistency(db_session):
    """
    Verify that the translation process preserves the approximate length of the content.
    This ensures we aren't accidentally truncating articles during translation or storage.
    """
    # Setup source
    source = Source(name="Test Source", feed_url="http://test.com/rss")
    db_session.add(source)
    await db_session.flush()

    # Create a dummy article with substantial text
    # 50 repetitions of a 29-char string = ~1450 chars
    original_text = "This is a paragraph of text. " * 50
    original_title = "Original Title"

    article = Article(
        url="http://example.com/test",
        url_hash="hash_integrity_test",
        title=original_title,
        body=original_text,
        source_id=source.id,
    )
    db_session.add(article)
    await db_session.commit()

    # Mock the actual GoogleTranslator to return a predictable string of similar length.
    # In a real scenario, translation length varies, but usually stays within 0.7-1.5x.
    # We simulate a slightly longer translation (common for RU vs EN).
    def mock_translate_side_effect(text, **kwargs):
        return f"Perevod: {text}"

    # We patch the synchronous translate method of the library used inside the service
    with patch(
        "deep_translator.GoogleTranslator.translate",
        side_effect=mock_translate_side_effect,
    ):
        # Trigger translation
        translated_article = await get_or_create_translation(db_session, article, "ru")

        # Verify Title
        assert translated_article.title.startswith("Perevod: ")
        assert len(translated_article.title) > len(original_title)

        # Verify Body Length consistency
        # Our mock adds "Perevod: " (9 chars) to the text.
        expected_len = len(original_text) + 9
        assert len(translated_article.body) == expected_len

        # Check order of magnitude preservation (sanity check)
        ratio = len(translated_article.body) / len(original_text)
        assert 0.8 < ratio < 1.5, (
            f"Translation length ratio {ratio:.2f} indicates potential content loss or explosion"
        )

    # Verify persistence in the separate translations table
    stmt = select(Translation).where(
        Translation.article_id == article.id, Translation.language == "ru"
    )
    result = await db_session.execute(stmt)
    translation_record = result.scalar_one()

    # Ensure database record matches what was returned
    assert translation_record.body == translated_article.body
    assert len(translation_record.body) == expected_len
