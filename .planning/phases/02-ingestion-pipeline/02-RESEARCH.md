# Phase 2: Ingestion Pipeline - Research

**Researched:** 2026-02-23
**Domain:** RSS feed fetching, async HTTP, content extraction, deduplication, APScheduler, structured logging
**Confidence:** HIGH (core stack verified; content extraction library recommendation verified against benchmarks)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Phase Boundary:** Fetch, deduplicate, and persist real article content from all five target RSS sources (BBC, Reuters, AP News, NPR, Al Jazeera) on a scheduled background job. Scheduling runs inside the FastAPI process with a single-worker guard. Classification, search, and display are separate phases.

**Content extraction:**
- Follow each RSS entry's link and fetch the HTML page
- Use a readability-style extractor (newspaper3k, readability-lxml, or similar) to pull the main article text
- Preserve minimal HTML structure (paragraph tags, blockquotes) — not plain text, not full HTML
- When extraction fails or returns very little text, fall back to the RSS summary/description, store it, and flag the article as "partial"
- Extract metadata from the article page when available: author name, published date, lead image URL

**Feed error handling:**
- When a source is unreachable or returns an error: log the error and continue processing remaining sources
- When an individual article page fails to load or extract: store the RSS excerpt, flag as partial, and continue
- Set a descriptive User-Agent string (e.g., "FactFeed/1.0 RSS reader")
- Add a small delay between requests to the same domain
- Respect robots.txt
- Track consecutive failure counts per source; after N consecutive failures, escalate log level from WARNING to ERROR

**Scheduling behavior:**
- Poll all five sources every 15 minutes (single global interval, configurable via environment variable)
- Run an ingestion cycle immediately on application startup (don't wait for first interval)
- Fetch all five RSS feeds concurrently using async I/O
- Article page fetches within a source stay sequential for politeness
- APScheduler single-worker guard prevents duplicate job execution

**Logging & observability:**
- Structured JSON logging for all ingestion events
- Log a per-source summary after each cycle: articles found, new inserts, duplicates skipped, errors
- Cycle start/end and summaries at INFO level
- Individual article fetch/skip/insert at DEBUG level
- Errors and failures at WARNING/ERROR level
- Logs only for v1 — no separate stats table or metrics infrastructure

### Claude's Discretion

- Choice of readability extraction library (newspaper3k, readability-lxml, or other)
- Exact delay duration between article page fetches
- Consecutive failure threshold (N) for log level escalation
- Async HTTP client choice (httpx, aiohttp, etc.)
- Exact structure of the JSON log entries

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | System fetches articles from 5 RSS sources (BBC, Reuters, AP, NPR, Al Jazeera) on a scheduled background job | feedparser 6.0.12 for RSS parsing; APScheduler 3.11.2 AsyncIOScheduler for scheduling; httpx AsyncClient for concurrent feed fetching |
| INGEST-02 | System handles API rate limits, invalid sources, and fetch failures gracefully without crashing | Per-source try/except with bozo flag detection; consecutive failure counter; httpx timeout configuration; robots.txt via urllib.robotparser |
| INGEST-03 | System deduplicates articles by URL to prevent re-processing | sha256(normalized_url) stored as url_hash with UNIQUE constraint — already in schema from Phase 1 |
| INGEST-04 | System extracts article body text from fetched content for NLP processing | trafilatura 2.0.0 via bare_extraction(); partial flag on extraction failure; fallback to RSS summary field |
| INFRA-03 | Background scheduler (APScheduler) runs ingestion job on configurable interval | AsyncIOScheduler with next_run_time=datetime.now() for immediate startup run; max_instances=1 as single-worker guard; INGEST_INTERVAL_MINUTES env var |
</phase_requirements>

---

## Summary

Phase 2 builds the ingestion pipeline on top of the database foundation created in Phase 1. The schema already has the `articles`, `sentences`, and `sources` tables with `url_hash` UNIQUE constraint and GIN-indexed `search_vector` — no migrations are needed. The pipeline must: fetch five RSS feeds concurrently, follow each entry's link, extract article body and metadata, deduplicate by URL hash, and persist to the database on a 15-minute configurable schedule.

The standard stack is well-established for this domain. **trafilatura** is the clear winner for content extraction: it scores F1=0.958 vs readability-lxml at 0.922 and newspaper3k at 0.912 in the ScrapingHub benchmark. Newspaper3k has not been released since 2018. **httpx AsyncClient** is already in the project's design intent (referenced in STACK.md) and handles both RSS feed fetching and article page fetching cleanly. **feedparser** is the standard RSS parser and handles malformed feeds gracefully. **APScheduler 3.11.2 AsyncIOScheduler** runs inside the FastAPI lifespan with `max_instances=1` as the single-worker guard. **structlog** is the recommended library for structured JSON logging.

The critical integration pattern is: fetch feeds concurrently (asyncio.gather across sources), then fetch article pages within each source sequentially (politeness delay). trafilatura's `bare_extraction()` returns a Python dict with title, author, date, and body text — exactly what we need without format conversion overhead. The `output_format="html"` option on `extract()` preserves minimal paragraph/blockquote structure as required.

**Primary recommendation:** Use trafilatura 2.0.0 + httpx 0.28.1 + feedparser 6.0.12 + APScheduler 3.11.2 + structlog. This stack is current, well-maintained, and matches the project's existing async architecture.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedparser | 6.0.12 | RSS/Atom feed parsing | Handles malformed XML, bozo detection, normalizes date fields, supports all RSS variants including BBC/Reuters formats |
| httpx | 0.28.1 | Async HTTP client for both feed and article fetching | Already in STACK.md; `AsyncClient` with connection pooling; supports user-agent and timeout at client level; follow_redirects support |
| trafilatura | 2.0.0 | Article body extraction from raw HTML | F1=0.958 in benchmark (best of class); actively maintained; `bare_extraction()` returns Python dict with metadata; handles pre-fetched HTML directly |
| APScheduler | 3.11.2 | Background job scheduling inside FastAPI process | `AsyncIOScheduler` runs in asyncio event loop; `max_instances=1` prevents concurrent duplicate jobs; stable v3 (not v4 alpha) |
| structlog | 24.x | Structured JSON logging | JSON-native output for all log levels; `bind()` for per-source context; integrates with Python's stdlib logging |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| urllib.robotparser | stdlib | robots.txt compliance checking | Before fetching article pages for each domain; use RobotFileParser.can_fetch() |
| python-dateutil | stdlib/2.x | Date parsing fallback | When feedparser's published_parsed is None; parse ISO strings from article metadata |
| asyncio | stdlib | Concurrent RSS feed fetching | asyncio.gather() for parallel source fetches; asyncio.sleep() for politeness delay |
| hashlib | stdlib | URL hash for deduplication | sha256(normalized_url.encode()).hexdigest() — already used in deduplication pattern from Phase 1 architecture |
| ftfy | 6.x | Encoding repair for malformed feed text | When feedparser.bozo is True or text contains mojibake characters |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| trafilatura | readability-lxml | readability-lxml is simpler (one function) but F1=0.922 vs 0.958; doesn't return structured metadata (author, date, image) |
| trafilatura | newspaper3k | newspaper3k provides familiar interface but last released 2018; unmaintained; F1=0.912 |
| httpx | aiohttp | aiohttp is ~10-15% faster for high-concurrency; overkill here; httpx is already the project-intended client |
| structlog | Python stdlib logging with json formatter | stdlib logging works but structlog's `bind()` for request context and processor pipeline are significantly cleaner |

**Installation:**
```bash
uv add feedparser httpx trafilatura apscheduler structlog ftfy
```

---

## Architecture Patterns

### Recommended Project Structure

The `factfeed/ingestion/` directory already exists as a stub. Build the following structure inside it:

```
factfeed/
├── config.py                          # ADD: ingest_interval_minutes, sources list
├── ingestion/
│   ├── __init__.py                    # exists (stub)
│   ├── scheduler.py                   # NEW: AsyncIOScheduler setup + lifespan integration
│   ├── runner.py                      # NEW: run_ingestion_cycle() orchestrator
│   ├── fetcher.py                     # NEW: fetch_rss_feed(), fetch_article_page()
│   ├── extractor.py                   # NEW: extract_article_body(), extract_metadata()
│   ├── deduplicator.py                # NEW: compute_url_hash(), article_exists()
│   └── persister.py                   # NEW: save_article() with db session
├── web/
│   └── main.py                        # MODIFY: add scheduler lifespan, seed sources
tests/
├── conftest.py                        # exists — add shared fixtures for ingestion
├── ingestion/
│   ├── __init__.py                    # NEW
│   ├── test_fetcher.py                # NEW: unit tests for RSS parsing, HTTP mocking
│   ├── test_extractor.py              # NEW: unit tests for extraction and fallback
│   ├── test_deduplicator.py           # NEW: unit tests for hash computation
│   └── test_persister.py             # NEW: integration tests against test DB
```

### Pattern 1: Concurrent Feed Fetch, Sequential Article Fetch

**What:** Use `asyncio.gather()` to fetch all five RSS feeds in parallel, but within each source, fetch article pages sequentially with a configurable sleep delay.

**When to use:** Always. Parallel feed fetching keeps the 15-minute cycle fast. Sequential article fetching is the polite scraping pattern for established news sites.

**Example:**
```python
# factfeed/ingestion/runner.py
import asyncio
from factfeed.ingestion.fetcher import fetch_rss_feed, fetch_article_page

async def run_ingestion_cycle(sources: list[dict], http_client) -> dict:
    """Fetch all RSS feeds concurrently, then process articles per source."""
    results = await asyncio.gather(
        *[fetch_rss_feed(source, http_client) for source in sources],
        return_exceptions=True,
    )
    for source, feed_result in zip(sources, results):
        if isinstance(feed_result, Exception):
            log.error("feed_fetch_failed", source=source["name"], error=str(feed_result))
            continue
        await _process_source_entries(source, feed_result, http_client)
```

### Pattern 2: APScheduler Immediate Startup + Interval

**What:** Use `next_run_time=datetime.now(timezone.utc)` to trigger the first run immediately on scheduler start, then run every N minutes on interval.

**When to use:** Required — per user decision "run an ingestion cycle immediately on application startup."

**Example:**
```python
# factfeed/ingestion/scheduler.py
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from factfeed.config import settings

def create_scheduler(ingestion_fn) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        ingestion_fn,
        trigger="interval",
        minutes=settings.ingest_interval_minutes,
        next_run_time=datetime.now(timezone.utc),  # Run immediately on start
        max_instances=1,        # Single-worker guard — prevents duplicate execution
        coalesce=True,          # If missed, run once (not multiple catch-up runs)
        id="ingestion_cycle",
    )
    return scheduler
```

**FastAPI lifespan integration:**
```python
# factfeed/web/main.py
from contextlib import asynccontextmanager
import httpx
from factfeed.ingestion.scheduler import create_scheduler
from factfeed.ingestion.runner import run_ingestion_cycle

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        headers={"User-Agent": "FactFeed/1.0 RSS reader"},
        timeout=httpx.Timeout(10.0),
        follow_redirects=True,
    ) as http_client:
        scheduler = create_scheduler(lambda: run_ingestion_cycle(SOURCES, http_client))
        scheduler.start()
        yield
        scheduler.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)
```

### Pattern 3: trafilatura Extraction with Partial Fallback

**What:** Use `bare_extraction()` on pre-fetched HTML bytes to get body text and metadata. On extraction failure or thin content, fall back to RSS summary and set `is_partial=True`.

**When to use:** For every article page fetch. Do not pass URLs to trafilatura — always pre-fetch with httpx to control User-Agent and timeout.

**Example:**
```python
# factfeed/ingestion/extractor.py
from trafilatura import bare_extraction
from trafilatura.settings import use_config

MINIMUM_BODY_LENGTH = 200  # characters — below this, treat as extraction failure

def extract_article(html_bytes: bytes, url: str, rss_summary: str | None) -> dict:
    """Extract article body and metadata. Falls back to rss_summary on failure."""
    try:
        result = bare_extraction(
            html_bytes,
            url=url,
            include_images=True,
            favor_recall=True,   # Prefer more text for NLP — Phase 3 will filter
        )
        if result and len(result.get("text") or "") >= MINIMUM_BODY_LENGTH:
            return {
                "body": result["text"],
                "body_html": _to_minimal_html(result),
                "author": result.get("author"),
                "published_at": result.get("date"),
                "lead_image_url": _extract_lead_image(result),
                "is_partial": False,
            }
    except Exception:
        pass  # Fall through to partial fallback

    # Partial fallback: use RSS summary
    return {
        "body": rss_summary or "",
        "body_html": f"<p>{rss_summary or ''}</p>",
        "author": None,
        "published_at": None,
        "lead_image_url": None,
        "is_partial": True,
    }
```

### Pattern 4: URL Deduplication via SHA-256 Hash

**What:** Normalize the URL (strip query params, lowercase scheme+host), compute SHA-256 hex digest, check against `url_hash` UNIQUE constraint. The schema already enforces this at the database level.

**Example:**
```python
# factfeed/ingestion/deduplicator.py
import hashlib
from urllib.parse import urlparse, urlunparse

def compute_url_hash(url: str) -> str:
    """Normalize URL and return sha256 hex digest for deduplication."""
    parsed = urlparse(url.strip())
    # Lowercase scheme and host; strip query params and fragment
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        "",   # params
        "",   # query — strip tracking params
        "",   # fragment
    ))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

async def article_exists(url_hash: str, session) -> bool:
    """Check if article with this url_hash already exists in DB."""
    from sqlalchemy import select
    from factfeed.db.models import Article
    result = await session.execute(
        select(Article.id).where(Article.url_hash == url_hash).limit(1)
    )
    return result.scalar_one_or_none() is not None
```

### Pattern 5: Structured Logging with Per-Source Context

**What:** Use structlog to emit JSON-structured log events with bound context (source_name, cycle_id). Per-source summary at INFO; per-article events at DEBUG.

**Example:**
```python
# factfeed/ingestion/runner.py
import structlog
import uuid

log = structlog.get_logger()

async def run_ingestion_cycle(sources, http_client):
    cycle_id = str(uuid.uuid4())[:8]
    log.info("ingestion_cycle_start", cycle_id=cycle_id, source_count=len(sources))

    for source in sources:
        src_log = log.bind(source=source["name"], cycle_id=cycle_id)
        stats = {"found": 0, "inserted": 0, "skipped": 0, "errors": 0}
        # ... process source ...
        src_log.info("source_complete", **stats)

    log.info("ingestion_cycle_end", cycle_id=cycle_id)
```

### Pattern 6: Consecutive Failure Tracking

**What:** Track per-source consecutive failure counts in an in-memory dict. Escalate log level after threshold. Reset counter on success.

**When to use:** For every source fetch attempt.

**Example:**
```python
# factfeed/ingestion/runner.py
CONSECUTIVE_FAILURE_THRESHOLD = 3  # Claude's discretion: 3 consecutive failures → ERROR
_failure_counts: dict[str, int] = {}

def _log_source_error(source_name: str, error: str) -> None:
    _failure_counts[source_name] = _failure_counts.get(source_name, 0) + 1
    count = _failure_counts[source_name]
    if count >= CONSECUTIVE_FAILURE_THRESHOLD:
        log.error("source_consecutive_failures", source=source_name, count=count, error=error)
    else:
        log.warning("source_fetch_failed", source=source_name, count=count, error=error)

def _reset_failure_count(source_name: str) -> None:
    _failure_counts[source_name] = 0
```

### Pattern 7: feedparser + httpx Async Feed Fetching

**What:** Fetch RSS feed bytes with httpx AsyncClient, then pass bytes to `feedparser.parse()`. feedparser.parse() is synchronous but fast (CPU-bound XML parsing); run in thread pool for large feeds.

**Example:**
```python
# factfeed/ingestion/fetcher.py
import asyncio
import feedparser
import httpx

async def fetch_rss_feed(source: dict, client: httpx.AsyncClient) -> feedparser.FeedParserDict:
    """Fetch and parse an RSS feed. Returns feedparser dict."""
    response = await client.get(source["feed_url"])
    response.raise_for_status()

    # feedparser.parse() is synchronous — run in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, response.content)

    if feed.bozo:
        log.warning(
            "feed_bozo",
            source=source["name"],
            exception=str(feed.bozo_exception),
        )
    return feed

async def fetch_article_page(url: str, client: httpx.AsyncClient) -> bytes | None:
    """Fetch article HTML. Returns bytes or None on failure."""
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        log.warning("article_fetch_failed", url=url, error=str(e))
        return None
```

### Pattern 8: feedparser Date Normalization

**What:** feedparser returns `published_parsed` as a `time.struct_time` in UTC. Convert to `datetime` using `calendar.timegm()`.

**Example:**
```python
import calendar
from datetime import datetime, timezone

def parse_entry_date(entry) -> datetime | None:
    """Convert feedparser's published_parsed to a UTC-aware datetime."""
    if entry.get("published_parsed") and entry.published_parsed:
        ts = calendar.timegm(entry.published_parsed)  # treats tuple as UTC
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return None
```

### Pattern 9: robots.txt Compliance

**What:** Check robots.txt before fetching article pages using Python's stdlib `urllib.robotparser`. Cache the RobotFileParser per domain.

**Example:**
```python
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
import asyncio

_robots_cache: dict[str, RobotFileParser] = {}

async def can_fetch(url: str, user_agent: str = "FactFeed") -> bool:
    """Check robots.txt compliance for a URL. Returns True if allowed."""
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    if domain not in _robots_cache:
        rp = RobotFileParser()
        robots_url = f"{domain}/robots.txt"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, rp.set_url, robots_url)
        await loop.run_in_executor(None, rp.read)
        _robots_cache[domain] = rp

    return _robots_cache[domain].can_fetch(user_agent, url)
```

### Pattern 10: Source Seeding

**What:** The five sources must be seeded into the `sources` table before ingestion runs. Do this in the FastAPI lifespan before starting the scheduler, using upsert logic (insert if not exists by feed_url).

**Sources to seed:**
```python
# factfeed/ingestion/sources.py
SOURCES = [
    {"name": "BBC News",    "feed_url": "http://feeds.bbci.co.uk/news/rss.xml"},
    {"name": "Reuters",     "feed_url": "https://feeds.reuters.com/reuters/topNews"},
    {"name": "AP News",     "feed_url": "https://rsshub.app/apnews/topics/apf-topnews"},
    {"name": "NPR",         "feed_url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "Al Jazeera",  "feed_url": "https://www.aljazeera.com/xml/rss/all.xml"},
]
```

Note: Reuters and AP News do not have obvious stable first-party RSS endpoints. These URLs should be verified during implementation — they may require adjustment. (LOW confidence on exact feed URLs — HIGH confidence on BBC, NPR, Al Jazeera.)

### Anti-Patterns to Avoid

- **Blocking event loop with feedparser.parse() directly:** feedparser is synchronous CPU-bound work. Call via `run_in_executor()` or verify performance is acceptable for small feeds.
- **Creating httpx.AsyncClient per article:** Creates a new TCP connection for every request. Create one shared AsyncClient in the lifespan context.
- **Passing URLs to trafilatura.fetch_url():** trafilatura's own fetcher doesn't use our User-Agent or timeout. Always pre-fetch with httpx and pass bytes to `bare_extraction()`.
- **Using `datetime.now()` without timezone for APScheduler:** APScheduler configured with UTC timezone requires `datetime.now(timezone.utc)`. Naive datetime causes a ValueError.
- **Storing raw HTML as article body:** Phase 3 (NLP) expects clean text. Use trafilatura to extract main content only.
- **Missing `is_partial` column in schema:** The Article model needs this column. A migration is required.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSS/Atom feed parsing | Custom XML parser | feedparser 6.0.12 | Handles RSS 0.9x–2.0, Atom 0.3/1.0, bozo detection, date normalization, encoding quirks — 20+ years of edge cases |
| Article body extraction from HTML | HTML parser + heuristics | trafilatura 2.0.0 | Main content extraction is a research-grade problem; trafilatura has F1=0.958 on independent benchmarks |
| Async HTTP with connection pooling | aiohttp sessions manually | httpx.AsyncClient | Connection pooling, timeout, redirect, user-agent all configurable at client level; already in project stack |
| Background job scheduling | asyncio.create_task + while True loop | APScheduler AsyncIOScheduler | Handles missed jobs, coalescing, max_instances guard, graceful shutdown — hand-rolled loops have none of this |
| Structured log formatting | f-strings with json.dumps | structlog | Processor pipeline, bound context per logger, JSON renderer, stdlib integration, no per-call serialization boilerplate |
| URL normalization for deduplication | Custom URL string manipulation | urllib.parse (stdlib) | urlparse/urlunparse handles edge cases; consistent scheme normalization |
| robots.txt parsing | Custom HTTP GET + text parsing | urllib.robotparser (stdlib) | Already handles RFC 9309 crawl-delay, allow/disallow rules, wildcard patterns |

**Key insight:** Every item in this table represents months of edge-case handling. The biggest trap is article body extraction — naive approaches (BeautifulSoup + `find("article")`) work on ~60% of pages. trafilatura works on 95%+. The gap matters because Phase 3 (NLP) requires non-empty body text.

---

## Common Pitfalls

### Pitfall 1: Schema Missing `is_partial` and Metadata Columns

**What goes wrong:** The current `Article` model has `body`, `url_hash`, `title`, `published_at`, `source_id` but is missing `is_partial`, `author`, and `lead_image_url`. Phase 2 must add these columns or the partial-flag fallback and metadata extraction have nowhere to store data.

**Why it happens:** Phase 1 built a minimal viable schema. Phase 2 requirements (partial flag, author, image URL) were deferred to Phase 2 context.

**How to avoid:** Wave 0 of Phase 2 must include a migration adding these columns before any ingestion code runs.

**Warning signs:** Attempting to set `article.is_partial = True` raises AttributeError on the ORM model.

### Pitfall 2: feedparser `bozo=True` Does Not Mean Empty Feed

**What goes wrong:** Checking `if feed.bozo: continue` discards the entire feed when it might be partially parseable. BBC and AP News occasionally emit bozo feeds due to encoding issues.

**Why it happens:** The bozo flag means "not well-formed" — it does NOT mean "no entries parsed."

**How to avoid:** Log the bozo exception as WARNING, then continue processing whatever entries were parsed. Only skip if `len(feed.entries) == 0`.

**Reference:** feedparser docs — "bozo means degraded, not broken"

### Pitfall 3: APScheduler Multi-Worker Duplicate Jobs

**What goes wrong:** Running `uvicorn --workers N` with N > 1 causes N schedulers, each firing the ingestion job — N×articles inserted, N×RSS requests per cycle.

**Why it happens:** APScheduler 3.x is single-process; no inter-process coordination. Already documented in Phase 1 architecture research PITFALLS.md.

**How to avoid:** `max_instances=1` prevents concurrent job runs within one process. `--workers 1` in docker-compose (already set) prevents multi-process duplication. Document the single-worker constraint prominently.

### Pitfall 4: trafilatura Returns `None` Silently on Extraction Failure

**What goes wrong:** `bare_extraction()` returns `None` when the page has no extractable content (e.g., JavaScript-rendered SPA, login wall, 404 page that returned 200). Code that does `result["text"]` without None-checking raises TypeError.

**Why it happens:** trafilatura returns None instead of raising an exception on extraction failure. This is intentional API design.

**How to avoid:** Always check `if result is not None` before accessing result fields. Treat None as extraction failure and trigger the partial fallback.

### Pitfall 5: httpx Default Timeout is 5 Seconds — Too Short for Slow News Sites

**What goes wrong:** Some article pages (Reuters, Al Jazeera) take 5–10 seconds to respond, especially during high-traffic periods. httpx's 5-second default causes `httpx.TimeoutException` on valid pages.

**Why it happens:** httpx sets a 5-second network inactivity timeout by default.

**How to avoid:** Set `httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)` at AsyncClient construction. This is generous for reads while keeping connection timeout short to fail fast on unreachable hosts.

### Pitfall 6: feedparser `published_parsed` is `None` on Some Real Feeds

**What goes wrong:** AP News and NPR RSS feeds sometimes omit publication dates from entries. Code that does `calendar.timegm(entry.published_parsed)` without None-checking raises TypeError.

**Why it happens:** The `pubDate` element is optional in RSS 2.0.

**How to avoid:** Always check `if entry.get("published_parsed")` before converting. Fall back to `datetime.now(timezone.utc)` or leave `published_at=None` if the article page metadata also lacks a date.

### Pitfall 7: Large RSS Payloads Block the Event Loop

**What goes wrong:** `feedparser.parse()` is synchronous CPU-bound work. On large feeds (Reuters can return 100+ entries), parsing blocks the asyncio event loop for 200–500ms, making the web server unresponsive during that window.

**Why it happens:** feedparser has no async API.

**How to avoid:** Call `feedparser.parse()` via `asyncio.get_event_loop().run_in_executor(None, feedparser.parse, content)` to move it off the event loop thread.

### Pitfall 8: RSS Feed URLs for Reuters and AP News Are Unstable

**What goes wrong:** Reuters removed their official RSS feeds in 2020. AP News does not publish a well-known public RSS feed URL. Hardcoded URLs will fail.

**Why it happens:** Major news organizations have removed or obscured their RSS feeds to push users toward their apps.

**How to avoid:** Verify each of the five feed URLs during implementation before writing other code. Use RSSHub as a proxy for feeds that lack official endpoints. Store feed URLs in `sources` table so they can be updated without code changes.

**Note (LOW confidence):** The specific URLs for Reuters and AP News need validation during implementation. BBC, NPR, and Al Jazeera have stable known URLs (HIGH confidence).

---

## Code Examples

Verified patterns from official and cross-referenced sources:

### Complete httpx AsyncClient Setup

```python
# Source: https://www.python-httpx.org/advanced/clients/
import httpx

# Create a single long-lived client — share across all fetches in a session
http_client = httpx.AsyncClient(
    headers={"User-Agent": "FactFeed/1.0 RSS reader"},
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
    follow_redirects=True,
)
# Use as context manager in lifespan:
async with httpx.AsyncClient(...) as client:
    response = await client.get("https://example.com")
```

### feedparser with Pre-Fetched Bytes

```python
# Source: feedparser docs + community pattern (MEDIUM confidence)
import feedparser
import calendar
from datetime import datetime, timezone

response_bytes = await http_client.get(source["feed_url"])
feed = feedparser.parse(response_bytes.content)

if feed.bozo:
    log.warning("feed_bozo", source=source["name"], exception=str(feed.bozo_exception))
# Continue processing entries even if bozo=True

for entry in feed.entries:
    url = entry.get("link", "")
    title = entry.get("title", "")
    summary = entry.get("summary", "")

    # Date conversion
    pub_date = None
    if entry.get("published_parsed"):
        ts = calendar.timegm(entry.published_parsed)
        pub_date = datetime.fromtimestamp(ts, tz=timezone.utc)
```

### trafilatura Extraction from Pre-Fetched HTML

```python
# Source: https://trafilatura.readthedocs.io/en/latest/usage-python.html (HIGH confidence)
from trafilatura import bare_extraction

html_bytes = await http_client.get(article_url)

result = bare_extraction(
    html_bytes.content,
    url=article_url,
    include_images=True,
    favor_recall=True,
)

if result is None or len(result.get("text") or "") < 200:
    # Extraction failed — use partial fallback
    body_text = rss_summary
    is_partial = True
else:
    body_text = result["text"]
    author = result.get("author")       # str | None
    date = result.get("date")           # str | None (ISO format)
    image = result.get("image")         # str URL | None
    is_partial = False
```

### APScheduler with Immediate First Run

```python
# Source: APScheduler docs + community pattern (MEDIUM confidence verified)
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(
    func=run_ingestion_cycle,
    trigger="interval",
    minutes=settings.ingest_interval_minutes,  # env var, default 15
    next_run_time=datetime.now(timezone.utc),   # Runs immediately on scheduler.start()
    max_instances=1,    # Single-worker guard
    coalesce=True,      # Don't run multiple catch-up jobs if behind schedule
    id="ingestion_cycle",
    name="Ingest RSS feeds",
)
scheduler.start()
# On shutdown:
scheduler.shutdown(wait=False)
```

### structlog JSON Configuration

```python
# Source: https://www.structlog.org/en/stable/ (HIGH confidence)
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()

# Per-source context binding:
src_log = log.bind(source="BBC News", cycle_id="abc123")
src_log.info("source_complete", found=12, inserted=3, skipped=9, errors=0)
# Output: {"source": "BBC News", "cycle_id": "abc123", "found": 12, ...}
```

### SQLAlchemy Async Insert with Conflict Skip

```python
# Source: SQLAlchemy 2.0 docs (HIGH confidence — existing project pattern)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from factfeed.db.models import Article

async def save_article(session, article_data: dict) -> bool:
    """Insert article, skip on url_hash conflict. Returns True if inserted."""
    stmt = pg_insert(Article).values(**article_data)
    stmt = stmt.on_conflict_do_nothing(index_elements=["url_hash"])
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount == 1
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| newspaper3k for extraction | trafilatura 2.0.0 | 2019 (trafilatura released); 2018 (newspaper3k abandoned) | newspaper3k is unmaintained; trafilatura has better accuracy and active development |
| `@app.on_event("startup")` for scheduler | `lifespan` context manager | FastAPI 0.93+ | on_event deprecated; lifespan is the correct pattern for startup/shutdown resources |
| `requests` for HTTP | `httpx.AsyncClient` | 2020+ (httpx stable) | requests is sync-only; blocks FastAPI event loop; httpx is async-native |
| APScheduler 4.x (alpha) | APScheduler 3.11.2 (stable) | 4.x still alpha as of 2026 | 4.x has breaking API; 3.x is production stable |
| `datetime.now()` for timezone-aware APScheduler | `datetime.now(timezone.utc)` | N/A — always correct | APScheduler UTC config requires aware datetimes; naive raises ValueError |

**Deprecated/outdated:**
- newspaper3k: Last release 2018 — do not use
- APScheduler 4.x: Still alpha (4.0.0a6) — use 3.11.2

---

## Schema Migration Required (Wave 0)

Phase 2 requires adding three columns to the `articles` table that were not in the Phase 1 schema. These must be added before any ingestion code is written:

```python
# New Alembic migration: 0002_article_ingestion_fields.py
op.add_column("articles", sa.Column("author", sa.Text(), nullable=True))
op.add_column("articles", sa.Column("lead_image_url", sa.Text(), nullable=True))
op.add_column("articles", sa.Column("is_partial", sa.Boolean(), nullable=False, server_default="false"))
```

The SQLAlchemy `Article` model must also be updated with these three columns.

---

## Open Questions

1. **Reuters and AP News RSS Feed URLs**
   - What we know: Both are major news sources; both have reduced/hidden their public RSS feeds
   - What's unclear: Whether stable public RSS endpoints exist; RSSHub may be the only reliable option
   - Recommendation: Validate all five feed URLs manually during Wave 0 before writing fetcher code. Check RSSHub for Reuters/AP alternatives. Store URLs in `sources` table so non-code updates are possible.

2. **trafilatura HTML output format for "minimal HTML"**
   - What we know: `output_format="html"` produces cleaned HTML output; `bare_extraction()` returns `text` as plain text
   - What's unclear: Whether `output_format="html"` meets the "preserve paragraph tags, blockquotes" requirement — the exact HTML structure it produces
   - Recommendation: In Wave 1, test trafilatura's HTML output on one BBC article and confirm it contains `<p>` and `<blockquote>` tags. If not, use `output_format="xml"` and post-process to HTML. Store whatever format emerges in `body` column; note in code that Phase 4 uses this for display.

3. **Politeness delay duration**
   - What we know: User decision says "small delay between requests to the same domain" — Claude's discretion for exact duration
   - Recommendation: Use 1–2 seconds between article page fetches within a source (not between different sources). `await asyncio.sleep(1.5)` between each article fetch within a source loop. This is enough to avoid hammering; not so long that a 15-minute cycle risks running over on sources with 50+ new articles.

4. **Source seeding strategy — first run vs every startup**
   - What we know: Sources need to be in the `sources` table; five sources are fixed for v1
   - What's unclear: Whether to seed on every startup (idempotent upsert) or once via a migration
   - Recommendation: Seed in the FastAPI lifespan using `INSERT ... ON CONFLICT DO NOTHING` on `feed_url`. This is idempotent and requires no separate migration or management step.

---

## Sources

### Primary (HIGH confidence)
- trafilatura 2.0.0 docs — https://trafilatura.readthedocs.io/en/latest/ — extraction API, bare_extraction() parameters
- trafilatura evaluation — https://trafilatura.readthedocs.io/en/latest/evaluation.html — F1 score benchmarks
- httpx official docs — https://www.python-httpx.org/ — AsyncClient, timeout, headers
- APScheduler 3.11.2 docs — https://apscheduler.readthedocs.io/en/3.x/ — AsyncIOScheduler, add_job, max_instances
- feedparser 6.0.12 docs — https://feedparser.readthedocs.io/en/stable/ — bozo, entry fields, date parsing
- SQLAlchemy 2.0 PostgreSQL dialect — existing project STACK.md + prior Phase 1 research
- Python stdlib urllib.robotparser — https://docs.python.org/3/library/urllib.robotparser.html

### Secondary (MEDIUM confidence)
- ScrapingHub article extraction benchmark — https://github.com/scrapinghub/article-extraction-benchmark — F1 scores for trafilatura/readability-lxml/newspaper3k
- APScheduler next_run_time=datetime.now() pattern — https://jdhao.github.io/2024/11/02/python_apascheduler_start_job_immediately/ — immediate startup job
- structlog FastAPI integration — https://www.sheshbabu.com/posts/fastapi-structured-json-logging/ + https://www.angelospanag.me/blog/structured-logging-using-structlog-and-fastapi
- feedparser + httpx async pattern — community-verified; feedparser.parse(response.content) is the standard async workaround
- APScheduler single-worker guard — https://apscheduler.readthedocs.io/en/3.x/faq.html — official confirmation of single-process requirement

### Tertiary (LOW confidence)
- Specific RSS feed URLs for Reuters and AP News — need validation during implementation
- trafilatura "html" output format exact structure — needs manual verification on target sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against PyPI, official docs, and project existing STACK.md
- Architecture: HIGH — patterns follow official library APIs; APScheduler + FastAPI lifespan is a well-documented pattern
- trafilatura recommendation: HIGH — F1 benchmark from independent source (ScrapingHub); library actively maintained as of Dec 2024
- Feed URLs: LOW for Reuters/AP News — HIGH for BBC/NPR/Al Jazeera
- Pitfalls: HIGH — cross-referenced against existing PITFALLS.md research; library-specific gotchas verified against docs

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable ecosystem — 30 days; feed URL validation needed immediately)
