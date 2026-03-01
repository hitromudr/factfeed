---
phase: 02-ingestion-pipeline
plan: 01
subsystem: database
tags: [alembic, sqlalchemy, feedparser, httpx, trafilatura, apscheduler, structlog, ftfy]

requires:
  - phase: 01-database-foundation
    provides: Article model, Alembic migration chain, Settings class
provides:
  - Article model with ingestion columns (is_partial, author, lead_image_url, body_html)
  - Alembic migration 0002 chaining after 0001
  - Settings with ingest_interval_minutes, user_agent, article_fetch_delay, consecutive_failure_threshold
  - All Phase 2 Python dependencies installed
affects: [02-ingestion-pipeline]

tech-stack:
  added: [feedparser, httpx, trafilatura, apscheduler, structlog, ftfy]
  patterns: [hand-written alembic migrations, pydantic-settings env var convention]

key-files:
  created:
    - alembic/versions/0002_article_ingestion_fields.py
  modified:
    - factfeed/db/models.py
    - factfeed/config.py
    - pyproject.toml

key-decisions:
  - "is_partial uses server_default='false' to avoid full table rewrite on existing rows"
  - "New columns placed after body, before published_at in model definition"

patterns-established:
  - "Hand-written Alembic migrations for schema changes (avoid autogenerate)"
  - "Ingestion config via pydantic-settings with uppercased env var names"

requirements-completed: [INGEST-04, INFRA-03]

duration: 3min
completed: 2026-02-23
---

# Plan 02-01: Schema Migration + Dependencies + Config Summary

**Article model extended with ingestion columns, migration 0002 created, six Python dependencies installed, and Settings expanded with poll interval and fetch config**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23
- **Completed:** 2026-02-23
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Installed feedparser, httpx, trafilatura, apscheduler, structlog, ftfy via uv
- Added is_partial, author, lead_image_url, body_html columns to Article model
- Created Alembic migration 0002 with proper chaining to 0001
- Expanded Settings with ingest_interval_minutes (15), user_agent, article_fetch_delay (1.5s), consecutive_failure_threshold (3)

## Task Commits

1. **Task 1: Install Phase 2 dependencies and update config** - `e1926dc` (feat)
2. **Task 2: Add ingestion columns and create migration 0002** - `30fb437` (feat)

## Files Created/Modified
- `pyproject.toml` - Added six new dependencies
- `factfeed/config.py` - Added ingestion settings to Settings class
- `factfeed/db/models.py` - Added four columns to Article model
- `alembic/versions/0002_article_ingestion_fields.py` - Hand-written migration adding ingestion columns

## Decisions Made
- Used server_default=sa.text("false") for is_partial to avoid table rewrite on existing rows
- Placed new columns after body, before published_at to maintain logical column ordering

## Deviations from Plan
None - plan executed exactly as written

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Article model ready for ingestion code to populate new columns
- Config ready for APScheduler and HTTP client configuration
- All libraries available for import in subsequent plans

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-02-23*
