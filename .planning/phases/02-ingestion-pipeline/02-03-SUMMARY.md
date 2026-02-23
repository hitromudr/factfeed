---
phase: 02-ingestion-pipeline
plan: 03
subsystem: ingestion
tags: [apscheduler, fastapi, structlog, httpx, sqlalchemy, lifespan, postgresql-upsert]

requires:
  - phase: 02-ingestion-pipeline
    provides: Leaf modules (fetcher, extractor, deduplicator, sources) and Article model with ingestion columns
provides:
  - Article persistence with ON CONFLICT DO NOTHING (save_article, seed_sources)
  - Ingestion cycle orchestrator with concurrent feed fetch and sequential article processing (run_ingestion_cycle)
  - APScheduler with immediate first run and single-worker guard (create_scheduler)
  - structlog JSON logging configuration (configure_logging)
  - FastAPI app with lifespan integrating all ingestion components and /health endpoint
affects: [02-ingestion-pipeline, 04-web-interface]

tech-stack:
  added: []
  patterns: [FastAPI lifespan context manager, APScheduler asyncio scheduler, PostgreSQL INSERT ON CONFLICT DO NOTHING, shared httpx client via lifespan]

key-files:
  created:
    - factfeed/ingestion/persister.py
    - factfeed/ingestion/runner.py
    - factfeed/ingestion/scheduler.py
    - factfeed/ingestion/logging.py
    - factfeed/web/main.py
  modified: []

key-decisions:
  - "save_article uses INSERT ON CONFLICT DO NOTHING on url_hash for atomic dedup"
  - "Runner queries sources from DB (not SOURCES constant) so runtime URL changes take effect"
  - "httpx.Timeout: connect=5s (fail fast), read=30s (generous for slow news sites)"
  - "Source seeding happens before scheduler starts so source_id FK is always valid"
  - "Ingestion job closure captures session_factory and http_client from lifespan scope"

patterns-established:
  - "FastAPI lifespan manages httpx client, scheduler, and source seeding lifecycle"
  - "PostgreSQL upsert via sqlalchemy.dialects.postgresql.insert for idempotent operations"
  - "Per-source consecutive failure tracking with configurable threshold"

requirements-completed: [INGEST-01, INGEST-02, INGEST-03, INFRA-03]

duration: 5min
completed: 2026-02-23
---

# Plan 02-03: Runner Orchestrator, Persister, Logging, Scheduler, FastAPI Lifespan Summary

**End-to-end ingestion pipeline wired into FastAPI — APScheduler fires concurrent RSS fetches, sequential per-source article processing with dedup and persistence, JSON logging, and /health endpoint**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23
- **Completed:** 2026-02-23
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Built persister with INSERT ON CONFLICT DO NOTHING for atomic dedup and idempotent source seeding
- Built runner orchestrating concurrent feed fetch, sequential article processing with dedup check, extraction, persistence, and politeness delay
- Built APScheduler integration with immediate first run, configurable interval, max_instances=1, and coalesce
- Built structured logging with structlog JSON output and stdlib routing
- Built FastAPI app with lifespan managing source seeding, shared httpx client, and scheduler lifecycle

## Task Commits

1. **Task 1: Create persister, logging config, and runner orchestrator** - `bf1bfe4` (feat)
2. **Task 2: Create APScheduler integration and FastAPI lifespan** - `74e7efb` (feat)

## Files Created/Modified
- `factfeed/ingestion/persister.py` - save_article (ON CONFLICT DO NOTHING), seed_sources (upsert)
- `factfeed/ingestion/runner.py` - run_ingestion_cycle with concurrent feeds, sequential articles, dedup, extraction, persist
- `factfeed/ingestion/logging.py` - structlog JSON configuration with stdlib routing
- `factfeed/ingestion/scheduler.py` - APScheduler AsyncIOScheduler factory
- `factfeed/web/main.py` - FastAPI app with full lifespan and /health endpoint

## Decisions Made
- Runner queries sources from database (not the SOURCES constant) so feed URL updates in the DB take effect without code changes
- httpx timeout uses connect=5s / read=30s per research pitfall guidance on slow news sites
- save_article commits after each insert (not batched) to isolate failures per article

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full import chain verified: main.py -> scheduler -> runner -> fetcher/extractor/deduplicator/persister -> models/session
- Pipeline ready for test suite in Plan 02-04
- FastAPI app importable and configured for uvicorn startup

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-02-23*
