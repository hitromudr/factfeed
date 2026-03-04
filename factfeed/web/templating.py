"""Shared Jinja2 template environment with custom filters."""

from datetime import datetime

from babel.dates import format_date as babel_format_date
from markupsafe import Markup
from fastapi.templating import Jinja2Templates

import nh3

# Allowed HTML tags for article body content (safe subset)
_ALLOWED_TAGS = {"p", "br", "a", "em", "strong", "b", "i", "ul", "ol", "li", "blockquote", "h2", "h3", "h4"}
_ALLOWED_ATTRIBUTES = {"a": {"href", "title", "target", "rel"}}


def _sanitize_html(value: str) -> Markup:
    """Sanitize HTML, keeping only safe tags/attributes. Returns Markup (safe)."""
    if not value:
        return Markup("")
    clean = nh3.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer",
    )
    return Markup(clean)


def _localized_date(value: datetime, locale: str = "en") -> str:
    """Format a datetime with localized month names using Babel."""
    if not value:
        return ""
    return babel_format_date(value, format="d MMM yyyy", locale=locale)


def create_templates() -> Jinja2Templates:
    """Create a Jinja2Templates instance with custom filters."""
    t = Jinja2Templates(directory="factfeed/templates")
    t.env.filters["sanitize"] = _sanitize_html
    t.env.filters["locdate"] = _localized_date
    return t


templates = create_templates()
