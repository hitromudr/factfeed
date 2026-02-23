# Phase 2: Ingestion Pipeline - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Fetch, deduplicate, and persist real article content from all five target RSS sources (BBC, Reuters, AP News, NPR, Al Jazeera) on a scheduled background job. Scheduling runs inside the FastAPI process with a single-worker guard. Classification, search, and display are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Content extraction
- Follow each RSS entry's link and fetch the HTML page
- Use a readability-style extractor (newspaper3k, readability-lxml, or similar) to pull the main article text
- Preserve minimal HTML structure (paragraph tags, blockquotes) — not plain text, not full HTML
- When extraction fails or returns very little text, fall back to the RSS summary/description, store it, and flag the article as "partial"
- Extract metadata from the article page when available: author name, published date, lead image URL

### Feed error handling
- When a source is unreachable or returns an error: log the error and continue processing remaining sources
- When an individual article page fails to load or extract: store the RSS excerpt, flag as partial, and continue
- Set a descriptive User-Agent string (e.g., "FactFeed/1.0 RSS reader")
- Add a small delay between requests to the same domain
- Respect robots.txt
- Track consecutive failure counts per source; after N consecutive failures, escalate log level from WARNING to ERROR

### Scheduling behavior
- Poll all five sources every 15 minutes (single global interval, configurable via environment variable)
- Run an ingestion cycle immediately on application startup (don't wait for first interval)
- Fetch all five RSS feeds concurrently using async I/O
- Article page fetches within a source stay sequential for politeness
- APScheduler single-worker guard prevents duplicate job execution

### Logging & observability
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

</decisions>

<specifics>
## Specific Ideas

- Five target sources are fixed: BBC, Reuters, AP News, NPR, Al Jazeera
- Articles flagged as "partial" should be clearly distinguishable so Phase 3 (NLP) can decide whether to classify them
- Minimal HTML preservation is for Phase 4 display — NLP pipeline may strip tags for classification
- Polite fetching matters: these are established news organizations

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-ingestion-pipeline*
*Context gathered: 2026-02-23*
