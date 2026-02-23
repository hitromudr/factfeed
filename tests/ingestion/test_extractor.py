"""Unit tests for article extraction and partial fallback."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from factfeed.ingestion.extractor import extract_article, parse_article_date, MINIMUM_BODY_LENGTH


def test_extract_article_returns_partial_on_none_html():
    """When trafilatura returns None, partial fallback uses rss_summary."""
    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.return_value = None
        result = extract_article(b"<html></html>", "https://example.com", "RSS summary text")

    assert result["is_partial"] is True
    assert result["body"] == "RSS summary text"
    assert result["author"] is None


def test_extract_article_returns_partial_on_short_content():
    """When trafilatura returns body shorter than MINIMUM_BODY_LENGTH, use partial fallback."""
    short_text = "Short body"
    assert len(short_text) < MINIMUM_BODY_LENGTH

    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.return_value = {"text": short_text}
        result = extract_article(b"<html>short</html>", "https://example.com", "Fallback summary")

    assert result["is_partial"] is True
    assert result["body"] == "Fallback summary"


def test_extract_article_returns_full_on_good_content():
    """When trafilatura returns sufficient body text, return full extraction."""
    long_text = "A" * 300
    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.return_value = {
            "text": long_text,
            "author": "Test Author",
            "date": "2025-01-15",
            "image": "https://example.com/img.jpg",
        }
        mock_traf.extract.return_value = f"<p>{long_text}</p>"
        result = extract_article(b"<html>long</html>", "https://example.com", "Summary")

    assert result["is_partial"] is False
    assert result["body"] == long_text
    assert result["author"] == "Test Author"
    assert result["published_at"] == "2025-01-15"
    assert result["lead_image_url"] == "https://example.com/img.jpg"
    assert "<p>" in result["body_html"]


def test_extract_article_returns_partial_on_exception():
    """When trafilatura raises, partial fallback is used."""
    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.side_effect = RuntimeError("extraction failed")
        result = extract_article(b"<html>error</html>", "https://example.com", "Error fallback")

    assert result["is_partial"] is True
    assert result["body"] == "Error fallback"


def test_parse_article_date_returns_datetime_for_iso():
    """ISO date string is parsed to a timezone-aware datetime."""
    dt = parse_article_date("2025-01-15T10:30:00Z")
    assert isinstance(dt, datetime)
    assert dt.year == 2025
    assert dt.month == 1
    assert dt.day == 15
    assert dt.tzinfo is not None


def test_parse_article_date_returns_none_for_none():
    """None input returns None."""
    assert parse_article_date(None) is None


def test_parse_article_date_returns_none_for_garbage():
    """Unparseable string returns None."""
    assert parse_article_date("not-a-date-at-all") is None
