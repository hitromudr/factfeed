---
phase: 05-polish-and-hardening
plan: 01
subsystem: infra
tags: [slowapi, rate-limiting, pytest, json-report, testing]

# Dependency graph
requires:
  - phase: 04-web-interface
    provides: FastAPI app with search and article detail routes
provides:
  - Per-IP rate limiting (30/minute) on search endpoints via slowapi
  - HTTP 429 responses on rate limit excess with proper exception handler
  - Rate limit test suite with mock DB (no PostgreSQL required)
  - Accuracy test saves machine-readable JSON report to reports/accuracy_report.json
  - Default pytest run excludes slow/uat tests via addopts
affects: [future-phases, ci-pipeline]

# Tech tracking
tech-stack:
  added: [slowapi==0.1.9, limits==5.8.0]
  patterns:
    - Limiter singleton in separate factfeed/web/limiter.py to avoid circular imports
    - Reset limiter._limiter.storage.reset() per test for isolation without PostgreSQL
    - Mock DB session using AsyncMock for route tests that need no real data

key-files:
  created:
    - factfeed/web/limiter.py
    - tests/test_rate_limit.py
    - reports/.gitkeep
  modified:
    - factfeed/web/main.py
    - factfeed/web/routes/search.py
    - tests/nlp/test_pipeline.py
    - pyproject.toml

key-decisions:
  - "Limiter singleton placed in factfeed/web/limiter.py (not main.py) to prevent circular import: main imports search_routes, search_routes imports limiter"
  - "Rate limit test isolation via limiter._limiter.storage.reset() — resets in-memory MemoryStorage without replacing the decorator-bound singleton"
  - "Rate limit tests use mock AsyncSession so they run without a PostgreSQL instance"
  - "addopts = \"-m 'not slow and not uat'\" ensures fast test suite by default, explicit flags needed for slow/uat runs"

patterns-established:
  - "Circular import avoidance: shared singletons go in their own module (e.g., web/limiter.py)"
  - "Rate limit test isolation: reset storage rather than replace singleton, since decorators bind at import time"
  - "Mock DB fixtures with AsyncMock for rate/integration tests that don't need real data"

requirements-completed: [INFRA-05]

# Metrics
duration: 6min
completed: 2026-02-25
---

# Phase 5 Plan 01: Polish and Hardening Summary

**slowapi per-IP rate limiting (30/min) on search endpoints with 429 responses, plus JSON accuracy report artifact from classifier evaluation test**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-25T13:43:16Z
- **Completed:** 2026-02-25T13:49:16Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Installed slowapi and wired `Limiter` singleton into FastAPI app with `RateLimitExceeded` exception handler
- Applied `@limiter.limit("30/minute")` to both `search_page` (GET /) and `search_endpoint` (GET /search)
- Added `addopts = "-m 'not slow and not uat'"` to pyproject.toml so default pytest run is fast
- Created rate limit test suite with 3 tests covering: under-limit (200), over-limit (429), article detail exempt
- Extended `test_evaluation_set_accuracy` to write `reports/accuracy_report.json` with overall, per-category, and per-label breakdowns

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire slowapi rate limiting into search endpoint** - `3ae918e` (feat)
2. **Task 2: Add rate limit tests and accuracy report artifact** - `a31f82c` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified
- `factfeed/web/limiter.py` - Limiter singleton (avoids circular import)
- `factfeed/web/main.py` - Imports limiter, wires app.state.limiter and RateLimitExceeded handler
- `factfeed/web/routes/search.py` - @limiter.limit("30/minute") on search_page and search_endpoint
- `pyproject.toml` - addopts to exclude slow/uat, added uat marker
- `uv.lock` - Updated with slowapi and limits packages
- `tests/test_rate_limit.py` - Rate limit behavior tests (200 under, 429 over, article detail exempt)
- `tests/nlp/test_pipeline.py` - Accuracy report JSON artifact write logic
- `reports/.gitkeep` - Output directory tracked in git

## Decisions Made
- Limiter singleton placed in `factfeed/web/limiter.py` not `main.py` to avoid circular import (main imports search routes, search routes import limiter)
- Rate limit test isolation via `limiter._limiter.storage.reset()` — decorators bind to the singleton at import time, so replacing `app.state.limiter` alone does not reset counters
- Rate limit tests use `AsyncMock` DB session so they run without PostgreSQL
- `addopts` uses single-quotes in TOML value: `"-m 'not slow and not uat'"` for correct pytest marker expression syntax

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Moved limiter singleton to separate module to resolve circular import**
- **Found during:** Task 1 (Wire slowapi rate limiting)
- **Issue:** Plan specified `from factfeed.web.main import limiter` in search.py, but main.py imports search_routes at module level, creating a circular import error: `ImportError: cannot import name 'limiter' from partially initialized module 'factfeed.web.main'`
- **Fix:** Created `factfeed/web/limiter.py` to hold the singleton; both `main.py` and `search.py` import from this new module
- **Files modified:** factfeed/web/limiter.py (created), factfeed/web/main.py, factfeed/web/routes/search.py
- **Verification:** `uv run python -c "from factfeed.web.main import limiter; print(type(limiter))"` prints `<class 'slowapi.extension.Limiter'>`
- **Committed in:** 3ae918e (Task 1 commit)

**2. [Rule 1 - Bug] Fixed rate limit state leakage between tests by resetting storage**
- **Found during:** Task 2 (Add rate limit tests)
- **Issue:** Plan suggested replacing `app.state.limiter` per test, but slowapi decorators (`@limiter.limit`) bind to the specific `limiter` object at import time — not to `app.state.limiter`. Replacing `app.state.limiter` had no effect on the decorator-bound limiter, causing the 429 test to fail when run after other tests (shared in-memory counter).
- **Fix:** Call `limiter._limiter.storage.reset()` in the fixture to clear in-memory MemoryStorage before each test
- **Files modified:** tests/test_rate_limit.py
- **Verification:** All 3 rate limit tests pass reliably in sequence
- **Committed in:** a31f82c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for correct operation. No scope creep.

## Issues Encountered
- None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Rate limiting is live on search endpoints; further limits can be added to other routes using the same pattern
- Accuracy report artifact is ready for CI integration (read `reports/accuracy_report.json` for pass/fail threshold)
- `addopts` excludes slow/uat tests by default; CI can run `pytest -m slow` separately for full accuracy gate

---
*Phase: 05-polish-and-hardening*
*Completed: 2026-02-25*

## Self-Check: PASSED

- factfeed/web/limiter.py: FOUND
- tests/test_rate_limit.py: FOUND
- reports/.gitkeep: FOUND
- 05-01-SUMMARY.md: FOUND
- Commit 3ae918e: FOUND
- Commit a31f82c: FOUND
