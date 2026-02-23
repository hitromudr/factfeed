# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Users can search and read news with clear, confidence-scored separation of facts from opinions
**Current focus:** Phase 1 — Database Foundation

## Current Position

Phase: 1 of 5 (Database Foundation)
Plan: 1 of 3 in current phase
Status: In Progress
Last activity: 2026-02-23 — Completed 01-01-PLAN.md (project scaffold + ORM models)

Progress: [█░░░░░░░░░] 7%

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 5 min
- Total execution time: 0.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-database-foundation | 1/3 | 5 min | 5 min |

**Recent Trend:**
- Last 5 plans: 5 min
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase]: DeBERTa-v3-base-zeroshot-v2.0 selected over BART-large-mnli (~25% F1 improvement)
- [Pre-Phase]: Sentences stored in child table, not JSON blob on articles row — required for per-sentence querying
- [Pre-Phase]: APScheduler runs inside FastAPI process with single-worker constraint (--workers 1)
- [Pre-Phase]: GIN index and tsvector generated column must exist in initial Alembic migration — not retrofittable
- [Phase 01-database-foundation]: Flat layout: factfeed/ at repo root (not src/); uv init nested layout discarded
- [Phase 01-database-foundation]: search_vector uses SQLAlchemy Computed(persisted=True) with TSVECTOR — PostgreSQL computes it on INSERT/UPDATE
- [Phase 01-database-foundation]: Sentence stored as child table (not JSON blob) with label, confidence, position columns and CASCADE FK

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 3]: NLP accuracy on target sources is unknown; 80% accuracy target may require fine-tuning beyond zero-shot alone. Build evaluation set before writing classifier code.
- [Phase 3]: Temperature scaling for confidence calibration requires a labeled calibration set that does not yet exist.
- [Phase 2]: trafilatura for article body extraction may need to be added to stack — confirm during Phase 2 planning.

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 01-database-foundation/01-01-PLAN.md
Resume file: None
