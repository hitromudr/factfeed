from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from factfeed.db.models import Article, Translation
from factfeed.nlp.translator import get_or_create_translation


@pytest.mark.asyncio
async def test_get_or_create_translation_cache_hit():
    """If translation exists in DB, use it and do not call API."""
    db = AsyncMock()
    # Mock result proxy
    mock_result = MagicMock()
    # Return existing translation
    cached = Translation(title="Привет", body="Мир")
    mock_result.scalar_one_or_none.return_value = cached
    db.execute.return_value = mock_result

    article = Article(id=1, title="Hello", body="World")

    # We patch the lower-level API call to ensure it's NOT called
    with patch("factfeed.nlp.translator.translate_text") as mock_api:
        await get_or_create_translation(db, article, "ru")

        assert article.translated_title == "Привет"
        assert article.translated_body == "Мир"
        # Original should be untouched
        assert article.title == "Hello"
        assert article.body == "World"
        mock_api.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_translation_cache_miss():
    """If translation missing, call API and save to DB."""
    db = AsyncMock()
    # Mock result proxy -> None (cache miss)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    article = Article(id=2, title="Hello", body="World")

    # Patch API to return translations
    with patch("factfeed.nlp.translator.translate_text") as mock_api:
        mock_api.side_effect = ["Привет", "Мир"]

        await get_or_create_translation(db, article, "ru")

        # Should call API twice (title, body)
        assert mock_api.call_count == 2
        # Should attempt to save to DB (select + insert)
        assert db.execute.call_count >= 2
        assert db.commit.called

        assert article.translated_title == "Привет"
        assert article.translated_body == "Мир"


@pytest.mark.asyncio
async def test_same_language_bypass():
    """Target language matches article language -> return original immediately."""
    db = AsyncMock()
    # Article explicitly marked as Spanish
    article = Article(id=3, title="Hola", body="Mundo", language="es")

    # Requesting Spanish translation for Spanish article
    res, _ = await get_or_create_translation(db, article, "es")

    assert res.title == "Hola"
    # Should not even query DB
    assert db.execute.called is False


@pytest.mark.asyncio
async def test_translate_different_language():
    """Target language differs from article language -> proceed with translation."""
    db = AsyncMock()

    # Mock cache miss
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    # Article in Spanish
    article = Article(id=4, title="Hola", body="Mundo", language="es")

    # Requesting English translation
    with patch("factfeed.nlp.translator.translate_text") as mock_api:
        mock_api.side_effect = ["Hello", "World"]

        await get_or_create_translation(db, article, "en")

        # Should verify translation happened
        assert mock_api.call_count == 2
        assert article.translated_title == "Hello"
        assert article.translated_body == "World"
