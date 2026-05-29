"""Verify that extract_article produces a real body from HTML alone (rss_summary=None).

This covers the G1 crawler path where rss_summary is never provided.
"""

from factfeed.ingestion.extractor import extract_article

_HTML = (
    b"<html><head><title>T</title></head><body><article>"
    + b"<p>" + b"Real article sentence with sufficient length. " * 12 + b"</p>"
    + b"</article></body></html>"
)


def test_extract_article_without_rss_summary_returns_body():
    out = extract_article(_HTML, "https://example.com/a", None)
    assert out.get("body")
    assert len(out["body"]) >= 200
    assert out.get("is_partial") is False
