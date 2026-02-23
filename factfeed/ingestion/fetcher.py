"""RSS feed fetching and article page fetching with robots.txt compliance."""

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import feedparser
import structlog

log = structlog.get_logger()

# Module-level robots.txt cache keyed by origin (scheme://netloc)
_robots_cache: dict[str, RobotFileParser | None] = {}


async def fetch_rss_feed(
    source: dict, client: httpx.AsyncClient
) -> feedparser.FeedParserDict:
    """Fetch RSS XML via httpx and parse with feedparser.

    Handles bozo feeds gracefully — logs a warning but still returns the feed
    so the caller can check ``len(feed.entries)``.
    """
    response = await client.get(source["feed_url"])
    response.raise_for_status()

    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, response.content)

    if feed.bozo:
        log.warning(
            "bozo_feed",
            source=source.get("name", source["feed_url"]),
            bozo_exception=str(getattr(feed, "bozo_exception", "unknown")),
        )

    return feed


async def fetch_article_page(url: str, client: httpx.AsyncClient) -> bytes | None:
    """Fetch article HTML page, returning raw bytes or None on any failure.

    Does NOT retry — the runner handles retries at the source level.
    """
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.content
    except Exception as exc:
        log.warning("fetch_article_page_failed", url=url, error=str(exc))
        return None


async def can_fetch(url: str, user_agent: str, client: httpx.AsyncClient) -> bool:
    """Check robots.txt before fetching an article page.

    Caches the parsed robots.txt per domain. On fetch failure, caches None
    and returns True (allow).
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin not in _robots_cache:
        robots_url = f"{origin}/robots.txt"
        try:
            resp = await client.get(robots_url)
            resp.raise_for_status()
            rp = RobotFileParser()
            rp.parse(resp.text.splitlines())
            _robots_cache[origin] = rp
        except Exception:
            log.debug("robots_txt_fetch_failed", origin=origin)
            _robots_cache[origin] = None
            return True

    rp = _robots_cache[origin]
    if rp is None:
        return True

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, rp.can_fetch, user_agent, url)
