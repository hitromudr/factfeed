---
phase: 04-web-interface
plan: 04
status: complete
started: 2026-02-24
completed: 2026-02-24
---

# Summary: Web Route Integration Tests

## What was built
Comprehensive integration test suite for all Phase 4 web routes using httpx.ASGITransport with dependency override for isolated DB sessions. 15 tests covering search, article detail, and cross-cutting concerns.

## Key files

### Created
- `tests/test_web_routes.py` — 15 integration tests for all web routes

## Test coverage
- Search page rendering and article display
- Keyword FTS via `plainto_tsquery`
- Source filter reduces results to matching source only
- Date filter (24h) excludes old articles
- Recency sort order verified by DOM position
- HTMX partial response (no DOCTYPE in HX-Request response)
- Article detail with sentence highlighting spans
- Opinion sentences in collapsed `<details>/<summary>` section
- Unclassified articles show body text with "Classification pending"
- 404 for nonexistent article IDs
- No set-cookie headers or login/sign-in text in any response
- Health endpoint still functional

## Decisions
- Used dependency override (`app.dependency_overrides[get_db]`) for DB session injection instead of mocking
- Seed data includes 3 articles across 2 sources with varied dates and sentence types
- DOM position comparison for sort order verification

## Self-Check: PASSED
- Test file exists with 251+ lines (requirement: min 80)
- Uses `ASGITransport` pattern for TestClient
- Tests cover all 12 Phase 4 requirement IDs
