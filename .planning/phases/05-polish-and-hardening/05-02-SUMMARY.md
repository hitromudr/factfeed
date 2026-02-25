---
phase: 05-polish-and-hardening
plan: 02
subsystem: testing
tags: [apscheduler, pytest, uat, multi-worker, docker-compose, httpx]

# Dependency graph
requires:
  - phase: 04-web-interface
    provides: article detail route with sentence highlighting, confidence tooltips, collapsible opinions, and search endpoint
  - phase: 03-nlp-classification
    provides: NLP classifier producing fact/opinion/mixed/unclear sentence labels with confidence scores
provides:
  - Multi-worker APScheduler safety tests (scheduler max_instances=1, coalesce=True, docker-compose --workers 1)
  - UAT pytest script (tests/uat/test_uat_articles.py) covering all 4 Phase 4 UX checklist items on real ingested data
affects: [05-polish-and-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "UAT tests run against real DB (AsyncSessionLocal, not rollback test session); marked @pytest.mark.uat and excluded from default run"
    - "Multi-worker guard verified via configuration inspection (not runtime execution)"

key-files:
  created:
    - tests/test_multi_worker.py
    - tests/uat/__init__.py
    - tests/uat/test_uat_articles.py
  modified: []

key-decisions:
  - "UAT tests use AsyncSessionLocal (real DB) rather than the rollback test session — tests against actual ingested content"
  - "test_uat_search_finds_articles issues warnings on FTS miss rather than hard failures — some article titles contain only stop words"
  - "Multi-worker tests inspect scheduler configuration only; scheduler is never started in tests (shutdown suppressed safely)"
  - "uat_articles fixture requires 10 mixed articles AND 3+ distinct sources; skips gracefully otherwise"

patterns-established:
  - "UAT test module scope: uat_articles and uat_client fixtures are module-scoped to avoid repeated DB connections per test"
  - "Configuration inspection tests: verify deployment constraints without exercising runtime behavior"

requirements-completed: [INFRA-06]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 05 Plan 02: Multi-Worker Safety Tests and UAT Script Summary

**APScheduler safety tests (max_instances=1, coalesce=True, --workers 1) and 4-function UAT pytest script verifying sentence highlighting, confidence tooltips, collapsible opinions, and search discoverability on 10 real mixed articles**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T13:43:55Z
- **Completed:** 2026-02-25T13:46:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `tests/test_multi_worker.py` with 3 safety tests: scheduler max_instances=1, coalesce=True, and docker-compose --workers 1 constraint — all passing
- Created `tests/uat/test_uat_articles.py` with 4 UAT test functions covering every Phase 4 UX checklist item: sentence highlighting, confidence tooltips, collapsible opinions, and search discoverability
- UAT fixtures skip gracefully when database lacks 10 mixed articles or fewer than 3 distinct sources, with clear diagnostic messages

## Task Commits

Each task was committed atomically:

1. **Task 1: Create multi-worker APScheduler safety tests** - `f8159e7` (feat)
2. **Task 2: Create UAT script for 10 real articles** - `385935b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `tests/test_multi_worker.py` - 3 tests verifying intra-process and inter-process multi-worker safety constraints
- `tests/uat/__init__.py` - Python package marker for UAT test directory
- `tests/uat/test_uat_articles.py` - 4 @pytest.mark.uat test functions covering all Phase 4 UX checklist items

## Decisions Made
- UAT tests use `AsyncSessionLocal` (real production DB sessions) rather than the rollback test session fixture — the entire point of UAT is to test against actual ingested content
- `test_uat_search_finds_articles` issues warnings (not failures) on FTS misses since some article titles may consist entirely of stop words or not yet be FTS-indexed
- Multi-worker tests never start the scheduler — they only inspect the APScheduler job object's configuration attributes (`max_instances`, `coalesce`) via `scheduler.get_job()`
- `uat_articles` and `uat_client` fixtures are module-scoped to avoid repeated DB round-trips per test function

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — all three multi-worker tests passed on first run. UAT module import verified cleanly.

## User Setup Required
None - no external service configuration required beyond the already-documented requirement for a running PostgreSQL instance with ingested + NLP-classified articles.

## Next Phase Readiness
- Phase 05 complete: rate limiting (Plan 01) and multi-worker safety + UAT coverage (Plan 02) are both delivered
- To run UAT against real data: `uv run pytest tests/uat/ -m uat --override-ini="addopts=" -v`
- Multi-worker safety tests run as part of the standard (non-slow, non-UAT) test suite

---
*Phase: 05-polish-and-hardening*
*Completed: 2026-02-25*
