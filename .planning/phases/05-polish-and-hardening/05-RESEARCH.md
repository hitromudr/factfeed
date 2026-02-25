# Phase 5: Polish and Hardening - Research

**Researched:** 2026-02-25
**Domain:** Test hardening, rate limiting, multi-worker safety, accuracy benchmarking
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Accuracy test reporting
- Run classifier accuracy suite against the held-out evaluation dataset (100+ sentences from Phase 3)
- Output results to console with pass/fail summary and per-category breakdown (fact/opinion/mixed/unclear)
- Fail the test if overall accuracy drops below 80% threshold
- Save a test report artifact (text or JSON) so results are reviewable after the run

#### UAT scope and pass criteria
- Select 10 real articles from the database (mix of sources — at least 3 different RSS sources represented)
- Prefer articles that have a mix of fact/opinion sentences (not all-fact or all-opinion)
- UAT checklist per article: (1) sentences are highlighted with correct colors, (2) confidence tooltips appear on hover, (3) collapsible opinion sections expand/collapse correctly, (4) search returns the article when querying its keywords
- Structured as a pytest-compatible test or script that can be re-run, not purely manual

#### Rate limiting
- Per-IP rate limiting on the search endpoint only (article detail doesn't need it)
- Reasonable threshold — something like 30 requests/minute per IP
- Return HTTP 429 with a clear message when limited
- No authentication needed — IP-based is sufficient for v1

#### Multi-worker safety
- Automated test that verifies APScheduler doesn't double-fire when multiple Gunicorn workers start
- The existing single-worker guard (from Phase 2) should be tested, not reimplemented
- Test approach: spin up the app config with workers > 1 and assert only one scheduler instance runs

### Claude's Discretion
- Exact rate limiter implementation (middleware vs dependency)
- UAT article selection strategy (random vs curated)
- Test report format details
- Whether to add a health check endpoint

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-05 | Unit tests for classifier accuracy (target 80%+ on evaluation dataset) | `test_evaluation_set_accuracy()` already exists in `tests/nlp/test_pipeline.py` marked `@pytest.mark.slow`; needs: report artifact saved to disk, per-category JSON output, and the slow test invocation documented |
| INFRA-06 | Automated API response tests and manual UAT on 10 articles | API tests exist in `tests/test_web_routes.py`; UAT script needs to query the live DB for 10 mixed-content articles and run checks against the running app via httpx |
</phase_requirements>

---

## Summary

Phase 5 adds no new features. It proves correctness and hardens the system for continuous operation across four work streams: (1) classifier accuracy benchmarking with a saved report, (2) per-IP rate limiting on search, (3) a structured UAT script for 10 real articles, and (4) a test that confirms APScheduler only fires once even when the app boots with multiple workers.

The good news: much of the groundwork is already in place. `tests/nlp/test_pipeline.py` has a `@pytest.mark.slow` accuracy test (`test_evaluation_set_accuracy`) that runs against `EVAL_SENTENCES` (120 labeled examples) and asserts ≥ 80% accuracy. `tests/test_web_routes.py` has full API integration tests against the search and article routes. The Phase 4 implementation already includes a `/health` endpoint. What is missing is: (a) the accuracy report is only printed to console — no file artifact is saved; (b) UAT against a live database with real ingested articles does not yet exist; (c) slowapi rate limiting is not installed or wired into the search endpoint; (d) the multi-worker APScheduler test does not exist.

**Primary recommendation:** Wire the four work streams as separate plan files. Accept that the classifier accuracy run will be slow (2–5 minutes) and gate it behind `-m slow` with clear CI instructions. Use `slowapi` for rate limiting — it is the de-facto standard for FastAPI per-route IP limiting. Test multi-worker safety through config inspection and process isolation, not by actually launching Gunicorn in CI.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | >=0.1.9 | Per-IP rate limiting for FastAPI/Starlette | De-facto standard; wraps `limits` library; maintained; decorator-per-route pattern matches FastAPI style |
| limits | (transitive dep of slowapi) | Token-bucket / fixed-window counter backend | Handles in-memory or Redis backends; slowapi abstracts the API |
| sklearn.metrics | 1.8.0 (already installed) | `accuracy_score`, `classification_report` | Already in pyproject.toml; no new dependency needed |
| pytest | 9.0.2 (already installed) | Test runner; `@pytest.mark.slow` marker already configured in pyproject.toml | Already present |
| pytest-asyncio | 1.3.0 (already installed) | Async test support for httpx/FastAPI routes | Already present |
| httpx | >=0.28.1 (already installed) | `ASGITransport` test client for FastAPI; live HTTP for UAT script | Already in pyproject.toml |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | N/A | Write accuracy report artifact to disk | Use for the report file format — no extra dep |
| pathlib (stdlib) | N/A | Resolve report output path in a cross-platform way | Use in the accuracy test fixture |
| os (stdlib) | N/A | Check `WEB_CONCURRENCY` or `UVICORN_WORKERS` env var | Use in multi-worker guard detection test |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slowapi | fastapi-limiter (Redis) | fastapi-limiter requires Redis; overkill for v1 single-process deployment |
| slowapi | custom middleware (Starlette) | More code, more bugs; slowapi already tested in production |
| JSON report file | HTML report (pytest-html) | pytest-html adds a dep; JSON is lighter and machine-readable |

**Installation (new dependency only):**
```bash
uv add slowapi
```

---

## Architecture Patterns

### Recommended Project Structure (Phase 5 additions)

```
factfeed/
├── web/
│   ├── main.py              # Add: limiter init, error handler, state.limiter
│   └── routes/
│       └── search.py        # Add: @limiter.limit("30/minute") on search_page and search_endpoint
tests/
├── nlp/
│   └── test_pipeline.py     # Update: save JSON report artifact in test_evaluation_set_accuracy
├── test_web_routes.py        # Update: add 429 test for rate-limited search
├── test_rate_limit.py        # New: dedicated rate limit behavior tests
├── test_multi_worker.py      # New: APScheduler single-instance guard test
└── uat/
    └── test_uat_articles.py  # New: UAT script for 10 real DB articles
reports/
    └── .gitkeep              # New: output directory for accuracy report artifacts
```

### Pattern 1: slowapi Per-Route Rate Limiting

**What:** Decorator-based IP rate limiting on a FastAPI route. The `Limiter` singleton is created at module scope; the route receives `Request` (required); the exception handler returns HTTP 429.

**When to use:** Any public endpoint that needs abuse prevention without authentication.

**Example (from official slowapi docs):**
```python
# factfeed/web/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

```python
# factfeed/web/routes/search.py
from factfeed.web.main import limiter  # import the singleton

@router.get("/")
@limiter.limit("30/minute")
async def search_page(request: Request, ...):
    ...

@router.get("/search")
@limiter.limit("30/minute")
async def search_endpoint(request: Request, ...):
    ...
```

**Critical decorator order:** In FastAPI, the `@router.get(...)` decorator MUST appear BEFORE `@limiter.limit(...)` in the source file (i.e., route decorator is closer to `def`). This is the #1 pitfall.

**Testing a 429 with pytest:**
```python
# tests/test_rate_limit.py
async def test_rate_limit_429(client):
    """31 rapid requests to / should return 429 on the 31st."""
    for i in range(30):
        resp = await client.get("/", params={"q": "test"})
        assert resp.status_code == 200
    resp = await client.get("/", params={"q": "test"})
    assert resp.status_code == 429
```

Note: The in-memory storage used by slowapi persists across test invocations within the same process. Use a separate `Limiter` instance or reset storage between tests to prevent cross-test contamination.

### Pattern 2: Accuracy Report Artifact

**What:** After running `test_evaluation_set_accuracy`, save a JSON file to `reports/accuracy_report.json` with overall accuracy, per-category, and per-label breakdowns.

**When to use:** Required by INFRA-05 so results are reviewable after a CI run.

**Example:**
```python
import json
from pathlib import Path

report = {
    "overall_accuracy": overall_accuracy,
    "total": total,
    "correct": correct,
    "threshold": 0.80,
    "passed": overall_accuracy >= 0.80,
    "per_category": {cat: {"correct": s["correct"], "total": s["total"],
                            "accuracy": s["correct"]/s["total"]} for cat, s in per_category.items()},
    "per_label": {lbl: {"correct": s["correct"], "total": s["total"],
                         "accuracy": s["correct"]/s["total"]} for lbl, s in per_label.items()},
}
report_path = Path(__file__).resolve().parents[2] / "reports" / "accuracy_report.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2))
print(f"Report saved to {report_path}")
```

### Pattern 3: Multi-Worker APScheduler Safety Test

**What:** The CONTEXT.md requires testing that APScheduler does NOT double-fire when workers > 1. The existing architecture (uvicorn `--workers 1` in docker-compose; `max_instances=1` in scheduler) already enforces this. The test validates the guard code, not the running deployment.

**Constraint:** Actually launching Gunicorn in a test process would be slow, fragile, and require a live PostgreSQL connection. Instead: test the configuration properties that enforce single-instance behavior.

**Recommended approach:**
```python
# tests/test_multi_worker.py
from factfeed.ingestion.scheduler import create_scheduler

def test_scheduler_max_instances_is_one():
    """Scheduler job has max_instances=1 — the core multi-worker guard."""
    mock_fn = lambda: None
    scheduler = create_scheduler(mock_fn)
    job = scheduler.get_job("ingestion_cycle")
    assert job.max_instances == 1

def test_scheduler_coalesce_enabled():
    """Coalesce=True prevents catch-up flood on multiple delayed fires."""
    mock_fn = lambda: None
    scheduler = create_scheduler(mock_fn)
    job = scheduler.get_job("ingestion_cycle")
    assert job.coalesce is True

def test_docker_compose_uses_single_worker(tmp_path):
    """docker-compose.yml app command uses --workers 1."""
    import re
    compose = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    text = compose.read_text()
    # The app service command should contain --workers 1
    assert "--workers 1" in text or '"--workers", "1"' in text
```

### Pattern 4: UAT Script Against Live Database

**What:** A pytest-compatible script that queries the live database, finds 10 representative articles, and runs the CONTEXT.md UAT checklist programmatically.

**Important:** This requires a live database with real ingested content. It should be tagged with a custom marker (e.g., `@pytest.mark.uat`) and run separately from unit tests.

**Approach:**
1. Use `AsyncSessionLocal` directly (not the test `db_session` fixture) to query real ingested data
2. Assert that articles have sentences with `label in {"fact", "opinion", "mixed", "unclear"}`
3. For UI checks, use `httpx.AsyncClient` with `ASGITransport` to hit the article detail route and assert HTML structure (CSS classes, `<details>` element, confidence labels)
4. For search check: send a query with keywords from the article title and assert the article appears in results

### Anti-Patterns to Avoid

- **Circular import with limiter singleton:** Defining `limiter` in `routes/search.py` and importing from `main.py` creates a circular import. Define `limiter` in `main.py` (or a new `factfeed/web/limiter.py` module) and import it in routes.
- **Decorator order reversed:** `@limiter.limit(...)` placed above `@router.get(...)` causes silent failures (limit is never applied). Route decorator must be outermost (closest to function definition).
- **Rate limit state leaking across tests:** The in-memory `MemoryStorage` backend is module-level state. Tests that trigger rate limits will affect subsequent tests. Reset between tests or use separate limiter instances.
- **Launching Gunicorn in unit tests:** Launching a real multi-worker server to test APScheduler is fragile, slow, and requires DB connectivity. Test the configuration properties instead.
- **print() in slow tests loses output:** pytest swallows stdout by default. Use `-s` flag or configure `log_cli = true` in pyproject.toml, or write a file artifact rather than relying solely on stdout.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-IP rate limiting with 429 | Custom Starlette middleware with dict counter | slowapi + limits | Token-bucket logic, thread safety, sliding window, Redis support all handled |
| Accuracy breakdown table | Custom metrics loop | sklearn.metrics.classification_report | Already installed; handles per-class precision/recall/F1 in one call |
| HTTP test client for ASGI | Requests with real server | httpx.AsyncClient + ASGITransport | No real socket; test runs in-process; already used in test_web_routes.py |

**Key insight:** This phase should consume existing infrastructure (eval_dataset.py, test_web_routes.py, scheduler.py) rather than rebuild it. The pattern is: add what's missing at the edges (report artifact, rate limit decorator, worker guard test), not rework the core.

---

## Common Pitfalls

### Pitfall 1: slowapi Decorator Ordering
**What goes wrong:** Applying `@limiter.limit()` above `@router.get()` means FastAPI registers the route but the rate limit decorator never wraps it — requests are never limited.
**Why it happens:** Python decorator stacking applies bottom-up; the outermost decorator (first in file) is applied last. The limiter needs to wrap the already-registered route.
**How to avoid:** Always put route decorator (`@router.get(...)`) ABOVE limiter decorator (`@limiter.limit(...)`) in source file.
**Warning signs:** Rate limit tests pass 429 check but never actually return 429 in manual testing.

### Pitfall 2: Rate Limit In-Memory Storage Pollutes Tests
**What goes wrong:** Test A sends 30 requests; Test B sends 1 request; Test B gets 429 unexpectedly because the counter from Test A persists.
**Why it happens:** `Limiter(key_func=get_remote_address)` defaults to `MemoryStorage`, which is a module-level singleton.
**How to avoid:** Either (a) use a fresh `Limiter` instance per test via fixture that replaces `app.state.limiter`, or (b) order rate limit tests to run last, or (c) use a unique IP per test group by passing `X-Forwarded-For` header.
**Warning signs:** Rate limit tests pass in isolation but fail when run together.

### Pitfall 3: Accuracy Slow Test Runs in Normal CI
**What goes wrong:** The `@pytest.mark.slow` test loads the DeBERTa model (1.5GB), causing CI to timeout or exceed memory limits.
**Why it happens:** `pytest` runs all tests unless markers are used to filter.
**How to avoid:** Always invoke with `pytest -m slow` for the accuracy suite. Add `addopts = "-m not slow"` to `[tool.pytest.ini_options]` in `pyproject.toml` so the default run excludes slow tests automatically.
**Warning signs:** CI times out or runs out of memory on the test suite.

### Pitfall 4: UAT Test Requires Real Database Data
**What goes wrong:** UAT script runs in CI with an empty database (no real RSS articles ingested), failing all article content assertions.
**Why it happens:** CI databases are clean; UAT assumes real ingested content.
**How to avoid:** Mark UAT tests with `@pytest.mark.uat` and document that they require a seeded database. Do not run UAT in automated CI without a pre-seeded snapshot. The alternative is to seed the test database with representative fixture articles before the UAT run.
**Warning signs:** "0 articles found" or all assertions skipped because `len(articles) == 0`.

### Pitfall 5: APScheduler max_instances=1 is Not a Multi-Process Guard
**What goes wrong:** Developer concludes `max_instances=1` prevents duplicate execution across multiple Gunicorn workers.
**Why it happens:** `max_instances=1` only prevents a single APScheduler instance from running the same job concurrently. With N Gunicorn workers, N separate APScheduler instances are created — each will fire independently.
**How to avoid:** The architecture decision (committed in Phase 2) is to run with `--workers 1` always. The test should verify this deployment constraint is documented and enforced in docker-compose.yml, not assert that `max_instances=1` solves multi-process isolation.
**Warning signs:** Ingestion runs N times per cycle when deployed with N workers.

---

## Code Examples

### slowapi Setup in main.py
```python
# Source: https://slowapi.readthedocs.io/en/latest/
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="FactFeed", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Per-Route Limit on Search
```python
# Source: https://slowapi.readthedocs.io/en/latest/
# factfeed/web/routes/search.py
from factfeed.web.main import limiter

@router.get("/")
@limiter.limit("30/minute")
async def search_page(request: Request, q: str = "", ...):
    ...

@router.get("/search")
@limiter.limit("30/minute")
async def search_endpoint(request: Request, q: str = "", ...):
    ...
```

### Accuracy Report Save
```python
# Extend existing test_evaluation_set_accuracy in tests/nlp/test_pipeline.py
import json
from pathlib import Path

# After computing overall_accuracy, per_category, per_label:
report = {
    "overall_accuracy": round(overall_accuracy, 4),
    "total": total,
    "correct": correct,
    "threshold": 0.80,
    "passed": overall_accuracy >= 0.80,
    "per_category": {
        cat: {
            "correct": s["correct"],
            "total": s["total"],
            "accuracy": round(s["correct"] / s["total"], 4) if s["total"] > 0 else 0,
        }
        for cat, s in per_category.items()
    },
    "per_label": {
        lbl: {
            "correct": s["correct"],
            "total": s["total"],
            "accuracy": round(s["correct"] / s["total"], 4) if s["total"] > 0 else 0,
        }
        for lbl, s in per_label.items()
    },
}
report_dir = Path(__file__).resolve().parents[2] / "reports"
report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / "accuracy_report.json").write_text(json.dumps(report, indent=2))
```

### UAT Article Selection Query
```python
# tests/uat/test_uat_articles.py
from sqlalchemy import select, func
from factfeed.db.models import Article, Sentence, Source
from factfeed.db.session import AsyncSessionLocal

@pytest.mark.uat
@pytest.mark.asyncio
async def test_uat_10_articles():
    async with AsyncSessionLocal() as session:
        # Find articles with mixed labels (both fact and opinion sentences)
        stmt = (
            select(Article)
            .join(Article.source)
            .join(Article.sentences)
            .group_by(Article.id)
            .having(
                func.count(Sentence.id.filter(Sentence.label == "fact")) > 0,
                func.count(Sentence.id.filter(Sentence.label == "opinion")) > 0,
            )
            .limit(10)
        )
        articles = (await session.execute(stmt)).scalars().all()
    assert len(articles) >= 10, f"Only {len(articles)} mixed articles found — run ingestion first"
```

### pytest.ini_options Safeguard
```toml
# pyproject.toml — add to existing [tool.pytest.ini_options]
addopts = "-m 'not slow and not uat'"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual rate limiting middleware | slowapi decorator | ~2020 | Eliminates boilerplate; per-route granularity |
| pytest stdout accuracy reports | JSON report artifact | Current best practice | Machine-readable; survives CI log truncation |
| Multi-worker scheduler via shared job store | Single worker + APScheduler | APScheduler 3.x guidance | Avoids duplicate execution; simpler deployment |

**Deprecated/outdated:**
- `flask-limiter` patterns: Slowapi is a direct port of flask-limiter to Starlette/FastAPI; the API is identical but the integration mechanism differs (no Flask `current_app` context).

---

## Open Questions

1. **Should the UAT test query the live database or use fixture data?**
   - What we know: The CONTEXT.md says "structured as a pytest-compatible test or script that can be re-run" and "10 real articles from the database"
   - What's unclear: Whether the test runs in CI (clean DB) or only locally after ingestion
   - Recommendation: Mark `@pytest.mark.uat`, skip automatically in CI, document that it requires a pre-ingested database. Optionally: provide a fallback that seeds 10 representative fixture articles if the live count is < 10.

2. **Does the multi-worker test need to actually launch Gunicorn?**
   - What we know: CONTEXT.md says "spin up the app config with workers > 1 and assert only one scheduler instance runs"; the real guard is the `--workers 1` deployment constraint
   - What's unclear: Whether "spin up the app config" means inspecting configuration or launching a real process
   - Recommendation: Test the configuration (scheduler properties + docker-compose.yml) rather than launching processes. Document that the architectural guard is `--workers 1` and `max_instances=1` covers intra-process overlap. If a process-level test is required, use `subprocess.run` to launch uvicorn with `--workers 2` for 2 seconds and check that only one scheduler log entry appears — but this is fragile and slow.

---

## Sources

### Primary (HIGH confidence)
- slowapi official docs at https://slowapi.readthedocs.io/en/latest/ — installation, setup, per-route decoration, error handler
- slowapi GitHub README at https://github.com/laurentS/slowapi — key_func, decorator order warning
- APScheduler 3.x FAQ at https://apscheduler.readthedocs.io/en/3.x/faq.html — multi-worker guidance ("run scheduler in dedicated process")
- sklearn docs at https://scikit-learn.org/stable/modules/generated/sklearn.metrics.classification_report.html — classification_report API (already installed 1.8.0)
- FastAPI async tests docs at https://fastapi.tiangolo.com/advanced/async-tests/ — httpx ASGITransport pattern
- Existing codebase: `tests/nlp/test_pipeline.py` — `test_evaluation_set_accuracy` (fully implemented, needs report artifact only)
- Existing codebase: `tests/test_web_routes.py` — full API integration tests already passing
- Existing codebase: `factfeed/ingestion/scheduler.py` — `max_instances=1`, `coalesce=True` guard

### Secondary (MEDIUM confidence)
- WebSearch: slowapi per-IP 429 pattern (verified against official docs)
- WebSearch: pytest `addopts = "-m not slow"` pattern to exclude slow tests from default run

### Tertiary (LOW confidence)
- Multi-worker guard via config inspection rather than live process test — community pattern, not officially documented as "the" testing approach

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — slowapi is official, sklearn already installed, pytest already configured
- Architecture: HIGH — existing codebase patterns are well-established; new additions are minimal
- Pitfalls: HIGH — decorator order pitfall is documented in official slowapi docs; multi-worker pitfall is from APScheduler official FAQ

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (slowapi is stable; APScheduler 3.x is in maintenance mode)
