# Phase 5: Polish and Hardening - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify the integrated system passes accuracy benchmarks, handles production edge cases, and is safe to run continuously. This phase adds no new features — it proves existing features work correctly under real conditions and hardens the system for continuous operation.

</domain>

<decisions>
## Implementation Decisions

### Accuracy test reporting
- Run classifier accuracy suite against the held-out evaluation dataset (100+ sentences from Phase 3)
- Output results to console with pass/fail summary and per-category breakdown (fact/opinion/mixed/unclear)
- Fail the test if overall accuracy drops below 80% threshold
- Save a test report artifact (text or JSON) so results are reviewable after the run

### UAT scope and pass criteria
- Select 10 real articles from the database (mix of sources — at least 3 different RSS sources represented)
- Prefer articles that have a mix of fact/opinion sentences (not all-fact or all-opinion)
- UAT checklist per article: (1) sentences are highlighted with correct colors, (2) confidence tooltips appear on hover, (3) collapsible opinion sections expand/collapse correctly, (4) search returns the article when querying its keywords
- Structured as a pytest-compatible test or script that can be re-run, not purely manual

### Rate limiting
- Per-IP rate limiting on the search endpoint only (article detail doesn't need it)
- Reasonable threshold — something like 30 requests/minute per IP
- Return HTTP 429 with a clear message when limited
- No authentication needed — IP-based is sufficient for v1

### Multi-worker safety
- Automated test that verifies APScheduler doesn't double-fire when multiple Gunicorn workers start
- The existing single-worker guard (from Phase 2) should be tested, not reimplemented
- Test approach: spin up the app config with workers > 1 and assert only one scheduler instance runs

### Claude's Discretion
- Exact rate limiter implementation (middleware vs dependency)
- UAT article selection strategy (random vs curated)
- Test report format details
- Whether to add a health check endpoint

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Keep it practical: the goal is confidence that the system works, not ceremony.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-polish-and-hardening*
*Context gathered: 2026-02-25*
