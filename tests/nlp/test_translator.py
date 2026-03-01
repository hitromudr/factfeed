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

        assert article.title == "Привет"
        assert article.body == "Мир"
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

        assert article.title == "Привет"
        assert article.body == "Мир"


@pytest.mark.asyncio
async def test_english_bypass():
    """Target='en' returns original article immediately."""
    db = AsyncMock()
    article = Article(id=3, title="Hola", body="Mundo")

    res = await get_or_create_translation(db, article, "en")

    assert res.title == "Hola"
    # Should not even query DB
    assert db.execute.called is False
