"""Unit tests for article extraction and partial fallback."""

from datetime import datetime
from unittest.mock import patch

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


def test_extract_article_works_with_real_trafilatura_2x_document():
    """Regression guard for trafilatura 2.x API: bare_extraction now returns
    a Document object whose attributes are NOT dict-compatible (.get is absent
    on the object). Calling `extract_article` end-to-end with real HTML must
    still return a body string, not crash with AttributeError."""
    body_para = (
        "Reuters reports that NATO foreign ministers will meet in Brussels "
        "next week to discuss support for Ukraine. The meeting follows weeks "
        "of intensified shelling and a fresh round of sanctions targeting the "
        "energy sector. Several sources confirmed the agenda includes new "
        "weapons deliveries and longer-range artillery for Kyiv. "
    )
    html = (
        "<html><head><title>NATO talks</title></head>"
        "<body><article><h1>NATO talks</h1>"
        f"<p>{body_para * 4}</p></article></body></html>"
    ).encode("utf-8")
    result = extract_article(html, "https://example.com/nato", "rss summary")
    assert result["is_partial"] is False, "real long article must extract fully"
    assert len(result["body"]) >= MINIMUM_BODY_LENGTH
    assert "NATO" in result["body"]


def test_extract_article_strips_html_residue_from_body():
    """Trafilatura sometimes returns body with stray HTML markup (href fragments,
    bare closing tags, entities). _clean_text must remove them so NER and
    embedding don't ingest HTML noise."""
    from types import SimpleNamespace

    dirty = (
        'Article opening paragraph. <a href="https://example.com">link text</a> '
        'inside the body. Closing tag </p> leak. Entity: AT&amp;T. '
        + ("Continuing the real story " * 30)
    )
    fake_doc = SimpleNamespace(as_dict=lambda: {"text": dirty})
    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.return_value = fake_doc
        mock_traf.extract.return_value = "<p>html version</p>"
        result = extract_article(b"<html>x</html>", "https://example.com", "summary")
    assert "<a" not in result["body"], "bare <a tag leaked"
    assert "</p>" not in result["body"], "closing tag leaked"
    assert 'href="' not in result["body"], "href attribute leaked"
    assert "&amp;" not in result["body"], "HTML entity not decoded"
    assert "AT&T" in result["body"], "entity should be decoded, not removed"
    assert "Continuing the real story" in result["body"]


def test_extract_article_strips_markdown_image_syntax():
    """Trafilatura occasionally emits markdown images ![alt](url) inline.
    These must be removed entirely so neither alt text nor URL pollute NER."""
    from types import SimpleNamespace

    dirty = (
        "Real article opening. "
        "![photo of person](http://example.com/img.jpg) "
        "Real content continues. Read [related article](http://example.com/x) for more. "
        + ("Background paragraph filler. " * 20)
    )
    fake_doc = SimpleNamespace(as_dict=lambda: {"text": dirty})
    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.return_value = fake_doc
        mock_traf.extract.return_value = "<p>html</p>"
        result = extract_article(b"<html>x</html>", "https://example.com", "summary")
    assert "![photo" not in result["body"], "markdown image leaked"
    assert "img.jpg" not in result["body"], "image URL leaked"
    assert "(http://example.com/x)" not in result["body"], "link URL leaked"
    assert "related article" in result["body"], "markdown link text must remain"


def test_extract_article_mock_supports_both_dict_and_document_api():
    """Mocks may supply either a plain dict (legacy 1.x shape) or any object
    with .as_dict() — both must work. This protects test maintenance when
    mocks are tightened toward the 2.x reality."""
    from types import SimpleNamespace

    long_text = "B" * 300
    fake_doc = SimpleNamespace(
        as_dict=lambda: {
            "text": long_text,
            "author": "Doc Author",
            "date": "2026-05-22",
            "image": None,
        }
    )
    with patch("factfeed.ingestion.extractor.trafilatura") as mock_traf:
        mock_traf.bare_extraction.return_value = fake_doc
        mock_traf.extract.return_value = f"<p>{long_text}</p>"
        result = extract_article(b"<html>x</html>", "https://example.com", "summary")
    assert result["is_partial"] is False
    assert result["body"] == long_text
    assert result["author"] == "Doc Author"
    assert result["published_at"] == "2026-05-22"
