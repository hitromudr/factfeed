"""RSS feed fetching and article page fetching with robots.txt compliance."""

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
import structlog
from curl_cffi.requests import AsyncSession

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

    Uses curl_cffi to mimic browser TLS fingerprints, bypassing strict anti-bot protections (like TASS).
    Ignores the passed 'client' (httpx) for actual fetching, using a fresh AsyncSession with impersonation.
    Implements proxy rotation (Direct -> Riga -> Polka -> Turka -> Nitro) for retries.
    """
    # Proxies available via host networking
    proxies_list = [
        None,  # Direct first
        "http://riga:fgh4677jhrtjh67EG@127.0.0.1:3129",  # Riga
        "http://polka:fgh4677jhrtjh67EG@127.0.0.1:4129",  # Polka
        "http://turka:fgh4677jhrtjh67EG@127.0.0.1:5129",  # Turka
        "http://hitro:fgh4677jhrtjh67EG@127.0.0.1:6129",  # Hitro
    ]

    # Headers mimicking real Chrome
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Referer": "https://www.google.com/",
        "Sec-Ch-Ua": '"Google Chrome";v="120", "Not:A-Brand";v="8", "Chromium";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    last_exception = None

    for proxy in proxies_list:
        try:
            # Create a fresh session with browser impersonation for every request
            # impersonate="chrome120" handles the TLS fingerprinting
            async with AsyncSession(impersonate="chrome120", proxy=proxy) as s:
                response = await s.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.content

        except Exception as exc:
            last_exception = exc
            status = getattr(exc, "response", None) and getattr(
                exc.response, "status_code", "unknown"
            )
            proxy_name = proxy or "Direct"
            log.warning(
                "fetch_attempt_failed",
                url=url,
                proxy=proxy_name,
                error=str(exc),
                status=status,
            )
            # Continue to next proxy

    log.error(
        "fetch_article_page_failed_all_attempts",
        url=url,
        last_error=str(last_exception),
    )
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
