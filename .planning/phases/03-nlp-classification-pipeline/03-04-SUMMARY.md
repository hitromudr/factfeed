---
phase: 03-nlp-classification-pipeline
plan: 04
subsystem: nlp
tags: [integration-testing, accuracy-gate, post-ingestion, fastapi-lifespan, config]

requires:
  - phase: 03-nlp-classification-pipeline
    provides: "Full NLP pipeline (segmenter, pre-filter, classifier, calibrator, persist)"
provides:
  - "Pipeline integration tests (3 mock tests + 1 accuracy gate)"
  - "Post-ingestion classification wired into FastAPI lifespan"
  - "NLP config options (nlp_enabled, nlp_batch_size)"
  - "Accuracy gate test against 120-sentence evaluation dataset"
affects: [04-web-interface, 05-polish-and-hardening]

tech-stack:
  added: []
  patterns: [post-ingestion-classification, nlp-config-toggle]

key-files:
  created:
    - tests/nlp/test_pipeline.py
  modified:
    - factfeed/config.py
    - factfeed/web/main.py

key-decisions:
  - "Classification runs as post-ingestion step (not inline with article fetching) to decouple failures"
  - "DeBERTa model loaded once at lifespan startup and reused across all classification calls"
  - "NLP disabled via config toggle (NLP_ENABLED=false) for dev/test environments"
  - "Accuracy gate test marked @pytest.mark.slow — only runs explicitly with -m slow"

patterns-established:
  - "Post-ingestion classification: query articles without sentences, classify in batches"
  - "Config-gated feature: nlp_enabled flag controls both model loading and classification execution"

requirements-completed: [NLP-01, NLP-02, NLP-03, NLP-04, NLP-05]

duration: 4 min
completed: 2026-02-23
---

# Phase 3 Plan 04: Integration Tests, Accuracy Gate, and Post-Ingestion Classification Wiring Summary

**Pipeline integration tests with mock transformer, accuracy gate against 120 evaluation sentences, and post-ingestion classification wired into FastAPI lifespan with configurable NLP toggle**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-23T21:24:10Z
- **Completed:** 2026-02-23T21:28:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- 3 pipeline integration tests validate full article classification, all 4 labels, and confidence bounds
- Accuracy gate test loads real DeBERTa model and measures accuracy against 120-sentence evaluation set
- Classification wired into FastAPI lifespan as post-ingestion step with batch processing
- NLP config toggle (nlp_enabled, nlp_batch_size) allows disabling classification in dev/test
- All 38 non-slow NLP tests pass in ~1 second

## Task Commits

Each task was committed atomically:

1. **Task 1: Write integration tests with accuracy gate** - `21585dc` (test)
2. **Task 2: Wire classification into post-ingestion flow** - `f8501e4` (feat)

## Files Created/Modified
- `tests/nlp/test_pipeline.py` - 3 integration tests + 1 accuracy gate test + DB persistence stubs
- `factfeed/config.py` - Added nlp_enabled (bool) and nlp_batch_size (int) settings
- `factfeed/web/main.py` - Load classifier at startup, run classification after ingestion

## Decisions Made
- Classification runs after ingestion completes (not inline) to isolate failures
- DeBERTa model loaded once at lifespan startup and reused for all scheduler runs
- Opinion test sentence rewritten to avoid "according to" triggering attribution pre-filter

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Opinion test sentence contained attribution phrase**
- **Found during:** Task 1 (test_pipeline_all_labels_possible)
- **Issue:** "according to independent fiscal analysts" triggered attribution pre-filter, producing "mixed" instead of "opinion"
- **Fix:** Rewrote sentence without attribution phrases to test pure opinion classification
- **Verification:** All integration tests pass
- **Committed in:** 21585dc (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test sentence corrected to avoid pre-filter interference. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete NLP pipeline operational: segmenter, pre-filter, classifier, calibrator, persistence
- Classification integrated into ingestion scheduler cycle
- Ready for Phase 4 (Web Interface) to read classified sentence data
- Accuracy gate test available for Phase 5 validation with `pytest -m slow`

---
*Phase: 03-nlp-classification-pipeline*
*Completed: 2026-02-23*
