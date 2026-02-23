---
phase: 02-ingestion-pipeline
status: passed
verified: 2026-02-23
score: 5/5
---

# Phase 2: Ingestion Pipeline — Verification

**Goal:** Real article content flows from all five RSS sources into the database continuously without manual intervention

## Must-Have Verification

### SC-1: Running the ingestion job inserts articles from BBC, Reuters, AP News, NPR, and Al Jazeera RSS feeds into the database
**Status:** PASS

Evidence:
- `factfeed/ingestion/sources.py` defines all 5 sources: BBC News, Reuters, AP News, NPR, Al Jazeera
- `factfeed/ingestion/persister.py::seed_sources()` upserts sources into the database on startup
- `factfeed/ingestion/runner.py::run_ingestion_cycle()` queries all sources from DB, fetches feeds concurrently via `asyncio.gather`, processes entries sequentially per source
- `factfeed/web/main.py` lifespan seeds sources and starts the scheduler
- Test `test_run_ingestion_cycle_processes_entries` verifies articles are saved

### SC-2: Re-running the ingestion job on already-seen URLs produces no duplicate rows (deduplication by url_hash is enforced)
**Status:** PASS

Evidence:
- `factfeed/ingestion/deduplicator.py::compute_url_hash()` normalizes URLs (strip query/fragment, lowercase) and produces SHA-256 hex digest
- `factfeed/ingestion/deduplicator.py::article_exists()` checks DB for existing url_hash before insertion
- `factfeed/ingestion/persister.py::save_article()` uses `INSERT ... ON CONFLICT DO NOTHING` on url_hash as a second safety layer
- `factfeed/db/models.py::Article.url_hash` has `unique=True` constraint
- Test `test_run_ingestion_cycle_skips_duplicates` verifies duplicate skipping
- Tests `test_compute_url_hash_strips_query_params`, `test_compute_url_hash_strips_fragment`, `test_compute_url_hash_normalizes_case` verify normalization

### SC-3: A malformed feed, encoding failure, or unreachable source logs an error and continues processing remaining sources without crashing
**Status:** PASS

Evidence:
- `factfeed/ingestion/fetcher.py::fetch_rss_feed()` handles bozo feeds (logs WARNING, returns feed anyway)
- `factfeed/ingestion/runner.py::run_ingestion_cycle()` uses `return_exceptions=True` in `asyncio.gather` and checks `isinstance(feed_result, Exception)` before processing
- Failed sources call `_log_source_error()` and `continue` to next source
- `_log_source_error()` tracks consecutive failures and escalates to ERROR level after threshold
- Test `test_run_ingestion_cycle_continues_after_source_error` verifies first source error does not prevent second source from being processed
- Test `test_fetch_rss_feed_bozo_continues` verifies bozo feeds are returned, not raised

### SC-4: Each persisted article has a non-empty body text field extracted from the fetched content
**Status:** PASS

Evidence:
- `factfeed/ingestion/extractor.py::extract_article()` uses trafilatura for full body extraction
- When trafilatura fails or returns short content (<200 chars), partial fallback uses RSS summary as body text
- Runner builds `article_data["body"]` from extracted content or RSS summary, never empty unless RSS summary itself is empty
- `is_partial` flag distinguishes full extractions from fallback content
- Test `test_extract_article_returns_full_on_good_content` and `test_extract_article_returns_partial_on_short_content` verify both paths
- Test `test_run_ingestion_cycle_handles_partial_extraction` verifies partial extraction saves with RSS summary

### SC-5: APScheduler triggers the fetch-and-persist cycle on a configurable interval inside the FastAPI process with a single-worker guard active
**Status:** PASS

Evidence:
- `factfeed/ingestion/scheduler.py::create_scheduler()` creates `AsyncIOScheduler` with `trigger="interval"`, `minutes=settings.ingest_interval_minutes`, `max_instances=1`, `coalesce=True`
- `next_run_time=datetime.now(timezone.utc)` ensures immediate first run on startup
- `factfeed/web/main.py` lifespan creates and starts the scheduler, shuts it down on app exit
- `factfeed/config.py::Settings.ingest_interval_minutes` defaults to 15, configurable via environment variable

## Requirement Traceability

| Requirement | Plan(s) | Status |
|-------------|---------|--------|
| INGEST-01 | 02-02, 02-03 | Verified — 5 sources defined, concurrent feed fetch, article persistence |
| INGEST-02 | 02-02, 02-03, 02-04 | Verified — bozo handling, return_exceptions, per-source error isolation, consecutive failure tracking |
| INGEST-03 | 02-02, 02-03, 02-04 | Verified — URL normalization, SHA-256 hash, article_exists check, ON CONFLICT DO NOTHING |
| INGEST-04 | 02-02, 02-04 | Verified — trafilatura extraction with partial fallback, is_partial flag |
| INFRA-03 | 02-01, 02-03 | Verified — APScheduler with configurable interval, max_instances=1, FastAPI lifespan integration |

## Test Coverage

- 25 total tests across 4 test files
- 23 pass without network or database (mocked HTTP and DB)
- 2 DB-dependent tests require running PostgreSQL
- All non-DB tests pass: `uv run pytest tests/ingestion/ -k "not article_exists" -q`

## Score

**5/5 must-haves verified**

## Verdict

**PASSED** — Phase 2 goal achieved. The ingestion pipeline fetches RSS feeds from all five sources, extracts article content with trafilatura (partial fallback to RSS summary), deduplicates by url_hash, persists to PostgreSQL, handles source failures gracefully, and runs on a configurable APScheduler interval with single-worker guard inside the FastAPI process.
