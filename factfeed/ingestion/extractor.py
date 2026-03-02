"""Article body extraction with trafilatura and partial fallback."""

import re
from datetime import datetime, timezone

import structlog
import trafilatura
from dateutil import parser as dateutil_parser

log = structlog.get_logger()

MINIMUM_BODY_LENGTH = 200


def extract_article(html_bytes: bytes, url: str, rss_summary: str | None) -> dict:
    """Extract article content from pre-fetched HTML bytes.

    Returns a dict with body, body_html, author, published_at, lead_image_url,
    and is_partial.  Falls back to the RSS summary when trafilatura fails or
    returns thin content.
    """
    try:
        result = trafilatura.bare_extraction(
            html_bytes, url=url, include_images=True, favor_recall=True
        )

        body_text = (result.get("text") or "") if result else ""

        if result is not None and len(body_text) >= MINIMUM_BODY_LENGTH:
            # Full extraction succeeded
            body_html = trafilatura.extract(
                html_bytes,
                url=url,
                output_format="html",
                include_images=True,
                favor_recall=True,
            )
            if body_html is None:
                body_html = f"<p>{body_text}</p>"

            return {
                "body": body_text,
                "body_html": body_html,
                "author": result.get("author") or None,
                "published_at": result.get("date") or None,
                "lead_image_url": result.get("image") or None,
                "is_partial": False,
            }

        # Extraction returned None or body too short — partial fallback
        log.debug(
            "extraction_partial_fallback",
            url=url,
            reason="short_or_none",
            body_length=len(body_text),
        )
        return _partial_fallback(rss_summary)

    except Exception as exc:
        log.debug("extraction_exception_fallback", url=url, error=str(exc))
        return _partial_fallback(rss_summary)


def _partial_fallback(rss_summary: str | None) -> dict:
    """Return a partial extraction dict using the RSS summary."""
    summary = rss_summary or ""
    return {
        "body": summary,
        "body_html": f"<p>{summary}</p>",
        "author": None,
        "published_at": None,
        "lead_image_url": None,
        "is_partial": True,
    }


def parse_article_date(date_str: str | None) -> datetime | None:
    """Parse a date string into a timezone-aware datetime, or None on failure."""
    if date_str is None:
        return None
    try:
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, OverflowError):
        return None
