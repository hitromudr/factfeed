"""URL normalization and SHA-256 hash for deduplication."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article


def compute_url_hash(url: str) -> str:
    """Normalize a URL and return its SHA-256 hex digest (64 chars).

    Normalization: lowercase scheme and netloc, keep path.
    Filters out common tracking query parameters (e.g., utm_*) and sorts the rest.
    """
    url = url.strip()
    parsed = urlparse(url)

    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_params = [
        (k, v) for k, v in query_params if not k.lower().startswith("utm_")
    ]
    filtered_params.sort()
    normalized_query = urlencode(filtered_params)

    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",  # params stripped
            normalized_query,
            "",  # fragment stripped
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def article_exists(url_hash: str, session: AsyncSession) -> bool:
    """Check whether an article with the given url_hash already exists."""
    result = await session.execute(
        select(Article.id).where(Article.url_hash == url_hash).limit(1)
    )
    return result.scalar_one_or_none() is not None
