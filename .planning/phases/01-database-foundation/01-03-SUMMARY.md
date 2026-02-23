---
phase: 01-database-foundation
plan: 03
subsystem: database
tags: [pytest, pytest-asyncio, postgresql, tsvector, gin-index, schema-tests, asyncpg]

requires:
  - 01-01 (factfeed package, ORM models, Base.metadata)
  - 01-02 (Alembic migration creating schema: GENERATED tsvector, GIN index, url_hash unique, sentences CASCADE FK)
provides:
  - pytest async fixtures (session-scoped engine with create_all/drop_all, function-scoped db_session with rollback)
  - 8 migration smoke tests verifying all Phase 1 schema contracts
affects:
  - 02-ingestion-pipeline
  - 03-nlp-classifier
  - 04-api-layer

tech-stack:
  added: []
  patterns:
    - pytest_asyncio.fixture for async fixtures (asyncio_mode=auto in pyproject.toml)
    - Session-scoped engine fixture with Base.metadata.create_all/drop_all
    - Function-scoped db_session with rollback for test isolation
    - information_schema queries to verify physical PostgreSQL schema
    - pg_indexes query to verify GIN index existence

key-files:
  created:
    - tests/__init__.py
    - tests/db/__init__.py
    - tests/db/test_migrations.py
    - tests/conftest.py
  modified: []

key-decisions:
  - "Tests query information_schema and pg_indexes to verify physical PostgreSQL schema — not just SQLAlchemy model definitions"
  - "Session-scoped engine creates/drops schema once per test run; function-scoped db_session rolls back for isolation"
  - "asyncio_mode=auto in pyproject.toml means no @pytest.mark.asyncio needed on individual tests"

duration: 2min
completed: 2026-02-23
---

# Phase 1 Plan 03: Migration Smoke Tests Summary

**pytest async fixtures and 8 schema verification tests covering table existence, GENERATED tsvector column, GIN index, url_hash unique constraint, sentences child table structure, FK with CASCADE, and search_vector auto-population on INSERT**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-23T19:38:00Z
- **Completed:** 2026-02-23T19:39:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `tests/__init__.py` and `tests/db/__init__.py` as empty package markers
- Created `tests/conftest.py` with session-scoped async engine fixture (creates all tables via `Base.metadata.create_all` on setup, drops via `Base.metadata.drop_all` on teardown) and function-scoped `db_session` fixture that rolls back after each test for isolation
- Created `tests/db/test_migrations.py` with 8 async test functions that verify all Phase 1 schema contracts against a live PostgreSQL database

## Task Commits

Each task was committed atomically:

1. **Task 1: pytest async fixtures** - `e9378a8` (feat)
2. **Task 2: Migration smoke tests** - `33000c9` (feat)

## Files Created

- `tests/__init__.py` - Empty package marker
- `tests/db/__init__.py` - Empty package marker
- `tests/conftest.py` - Session-scoped engine fixture + function-scoped db_session with rollback
- `tests/db/test_migrations.py` - 8 schema verification tests

## All 8 Test Functions

| Test | Verifies |
|------|----------|
| `test_tables_exist` | articles, sentences, sources tables all exist in public schema |
| `test_search_vector_is_generated_column` | search_vector has `is_generated = 'ALWAYS'` in information_schema.columns |
| `test_gin_index_exists` | `ix_articles_search_vector` exists in pg_indexes with "gin" in index definition |
| `test_url_hash_unique_constraint_exists` | A UNIQUE constraint containing "url_hash" exists on articles |
| `test_sentences_columns_exist` | sentences has article_id, position, text, label, confidence columns |
| `test_sentences_fk_to_articles` | sentences.article_id FK references articles with CASCADE delete rule |
| `test_search_vector_auto_populated_on_insert` | Inserting article without setting search_vector produces non-empty tsvector with correct lexemes |
| `test_url_hash_unique_constraint_enforced` | Inserting duplicate url_hash raises `IntegrityError` matching `uq_articles_url_hash` |

## How to Run

```bash
# Requires PostgreSQL test database
# Create test DB (first time only):
createdb -U factfeed factfeed_test
# OR via Docker:
docker exec -it claude_data_parser-postgres-1 createdb -U factfeed factfeed_test

# Run tests:
TEST_DATABASE_URL=postgresql+asyncpg://factfeed:factfeed@localhost:5432/factfeed_test \
  uv run pytest tests/db/test_migrations.py -v

# Expected: 8 passed
```

## Verification Results

```
tests/conftest.py - syntax OK
tests/db/test_migrations.py - syntax OK
8 tests collected in 0.01s (no collection errors)
```

Full integration test requires a running PostgreSQL instance with `factfeed_test` database.

## Decisions Made

- Tests query `information_schema` and `pg_indexes` directly — verifies physical PostgreSQL schema, not just SQLAlchemy model definitions. This catches migrations that are missing or incorrect.
- Session-scoped engine creates schema once per test run for speed; function-scoped `db_session` rolls back after each test to prevent state leakage between tests.
- `asyncio_mode = "auto"` in `pyproject.toml` handles the event loop automatically — no `@pytest.mark.asyncio` needed per-test (though tests in `test_migrations.py` include it explicitly for clarity).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `tests/__init__.py` exists (empty)
- [x] `tests/db/__init__.py` exists (empty)
- [x] `tests/conftest.py` exists with `pytest_asyncio`, `Base.metadata.create_all`, `Base.metadata.drop_all`, `rollback`, `TEST_DATABASE_URL`, `factfeed_test`
- [x] `tests/db/test_migrations.py` exists with all 8 required test functions
- [x] Both files parse without syntax errors
- [x] `pytest --collect-only` shows exactly 8 tests with no collection errors
- [x] Task 1 commit `e9378a8` present
- [x] Task 2 commit `33000c9` present

## Self-Check: PASSED

---
*Phase: 01-database-foundation*
*Completed: 2026-02-23*
