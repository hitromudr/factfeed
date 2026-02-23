---
phase: 01-database-foundation
plan: 01
subsystem: database
tags: [sqlalchemy, asyncpg, postgresql, pydantic-settings, alembic, fastapi, uv]

requires: []
provides:
  - factfeed Python package (flat layout, uv-managed) with all Phase 1 deps installed
  - pydantic-settings Settings class reading DATABASE_URL from .env
  - SQLAlchemy ORM models: Article (TSVECTOR Computed, url_hash unique), Sentence (CASCADE FK, label/confidence/position), Source
  - Async engine + async_sessionmaker in factfeed/db/session.py
affects:
  - 01-database-foundation
  - 02-ingestion-pipeline
  - 03-nlp-classifier
  - 04-api-layer
  - 05-frontend

tech-stack:
  added:
    - sqlalchemy==2.0.46 (ORM, 2.0 style async)
    - asyncpg==0.31.0 (async PostgreSQL driver)
    - alembic==1.18.4 (migration tool)
    - pydantic-settings==2.13.1 (env config)
    - fastapi==0.132.0 (web framework)
    - pytest==9.0.2 + pytest-asyncio==1.3.0 (test framework)
  patterns:
    - DeclarativeBase for ORM model definitions
    - Computed(persisted=True) for STORED generated columns
    - async_sessionmaker + AsyncSession for async DB access
    - pydantic-settings BaseSettings with env_file=".env"

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .env.example
    - factfeed/__init__.py
    - factfeed/config.py
    - factfeed/nlp/__init__.py
    - factfeed/ingestion/__init__.py
    - factfeed/web/__init__.py
    - factfeed/db/__init__.py
    - factfeed/db/models.py
    - factfeed/db/session.py
  modified: []

key-decisions:
  - "Flat layout: factfeed/ at repo root, not under src/ (per CONTEXT.md)"
  - "hatchling build backend (uv init default) replaced by explicit pyproject.toml with hatchling"
  - "search_vector uses SQLAlchemy Computed(persisted=True) with TSVECTOR — PostgreSQL computes it on INSERT/UPDATE, never in application code"
  - "GIN index named ix_articles_search_vector declared in __table_args__ for full-text search performance"
  - "Sentence stored as child table (not JSON blob) — required for per-sentence label/confidence querying"
  - "url_hash is String(64) (sha256 hex) with unique=True for article deduplication"
  - "Sentence.article_id FK has ondelete=CASCADE so deleting article cascades to sentences at DB level"

patterns-established:
  - "SQLAlchemy 2.0 style: async engine, async_sessionmaker, DeclarativeBase"
  - "Config via pydantic-settings Settings singleton imported as `from factfeed.config import settings`"
  - "DB models in factfeed/db/models.py, session factory in factfeed/db/session.py"

requirements-completed:
  - INFRA-01

duration: 5min
completed: 2026-02-23
---

# Phase 1 Plan 01: Project Scaffold and ORM Models Summary

**uv-managed factfeed Python package with pydantic-settings config and SQLAlchemy 2.0 ORM models (Article with TSVECTOR Computed column, Sentence child table with label/confidence, Source) plus async session factory**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-23T19:29:52Z
- **Completed:** 2026-02-23T19:34:42Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Initialized flat-layout factfeed Python package managed by uv with all Phase 1 dependencies (sqlalchemy, asyncpg, alembic, pydantic-settings, fastapi, pytest, pytest-asyncio)
- Defined three SQLAlchemy 2.0 ORM models: Article (with TSVECTOR STORED generated column + GIN index + url_hash unique), Sentence (child table with CASCADE FK, position, label, confidence), Source
- Created async engine and session factory in factfeed/db/session.py using create_async_engine and async_sessionmaker

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold** - `9444efa` (feat)
2. **Task 2: ORM models and async session factory** - `87fba31` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `pyproject.toml` - uv-managed project with all Phase 1 deps, hatchling build, asyncio_mode=auto
- `uv.lock` - locked dependency versions (48 packages)
- `.env.example` - five required environment variables (DATABASE_URL, DEBUG, POSTGRES_USER/PASSWORD/DB)
- `factfeed/__init__.py` - package marker
- `factfeed/config.py` - pydantic-settings Settings class with DATABASE_URL and DEBUG
- `factfeed/nlp/__init__.py` - submodule stub
- `factfeed/ingestion/__init__.py` - submodule stub
- `factfeed/web/__init__.py` - submodule stub
- `factfeed/db/__init__.py` - db subpackage marker
- `factfeed/db/models.py` - Article, Sentence, Source ORM models with all schema columns and constraints
- `factfeed/db/session.py` - create_async_engine + async_sessionmaker factory

## Decisions Made

- Used flat layout (factfeed/ at repo root) per CONTEXT.md — uv init created nested layout which was discarded
- search_vector declared as Computed(persisted=True) with TSVECTOR — PostgreSQL generates it, never written by application code
- GIN index declared in __table_args__ by name "ix_articles_search_vector" for full-text search
- Sentence as child table (not JSON) enables per-sentence querying of label, confidence, position
- url_hash String(64) with unique=True enables efficient deduplication on INSERT without SELECT first

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv init created nested src-layout project instead of flat layout**
- **Found during:** Task 1 (Project scaffold)
- **Issue:** `uv init --package factfeed` created `factfeed/` subdirectory with its own `pyproject.toml` and `src/` layout instead of flat layout at repo root
- **Fix:** Removed the nested `factfeed/` directory; manually created `pyproject.toml` at repo root with hatchling build backend and flat layout; ran `uv add` to install all deps
- **Files modified:** pyproject.toml (created at root instead of factfeed/)
- **Verification:** `uv run python -c "import factfeed"` exits 0
- **Committed in:** 9444efa (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — uv init layout mismatch)
**Impact on plan:** Required discarding uv's default nested layout in favour of manually authored pyproject.toml with flat layout. No scope creep.

## Issues Encountered

- uv init --package creates a nested subdirectory project by default; flat layout requires manual pyproject.toml authoring and `uv add` for deps.

## User Setup Required

None - no external service configuration required at this stage. Database connectivity will be tested in Plan 02 (Alembic migrations + Docker Compose).

## Next Phase Readiness

- factfeed package imports cleanly: `import factfeed`, `from factfeed.config import settings`, `from factfeed.db.models import Article, Sentence, Source, Base`, `from factfeed.db.session import engine, AsyncSessionLocal` all succeed
- All model schema constraints verified: Computed(persisted=True), url_hash unique, Sentence FK ondelete=CASCADE, label/confidence/position columns present
- Base.metadata.tables contains: sources, articles, sentences
- Ready for Plan 02: Alembic migration infrastructure and Docker Compose setup

---
*Phase: 01-database-foundation*
*Completed: 2026-02-23*
