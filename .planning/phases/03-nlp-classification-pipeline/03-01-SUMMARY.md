---
phase: 03-nlp-classification-pipeline
plan: 01
subsystem: nlp
tags: [spacy, transformers, torch, scikit-learn, scipy, alembic, evaluation]

requires:
  - phase: 02-ingestion-pipeline
    provides: "Article and Sentence ORM models, pyproject.toml, Dockerfile"
provides:
  - "NLP dependencies installed and importable (spacy, transformers, torch, scikit-learn, scipy)"
  - "spaCy en_core_web_sm model available in Docker and local environments"
  - "Alembic migration 0003 adding UniqueConstraint on sentences(article_id, position)"
  - "120-sentence labeled evaluation dataset for accuracy measurement"
  - "NLP test infrastructure (conftest with mock pipeline and spaCy fixtures)"
affects: [03-02, 03-03, 03-04]

tech-stack:
  added: [spacy, transformers, torch, scikit-learn, scipy]
  patterns: [session-scoped-test-fixtures, mock-pipeline-for-nlp-tests]

key-files:
  created:
    - tests/nlp/eval_dataset.py
    - tests/nlp/conftest.py
    - tests/nlp/__init__.py
    - alembic/versions/0003_sentence_position_unique.py
  modified:
    - pyproject.toml
    - Dockerfile
    - factfeed/db/models.py

key-decisions:
  - "Evaluation dataset uses 120 original sentences in news prose style across 4 labels and 3 difficulty tiers"
  - "spaCy model download in Dockerfile placed after uv sync and before COPY of app code for layer cache optimization"
  - "UniqueConstraint on (article_id, position) matches delete-then-insert persistence pattern as safety net"

patterns-established:
  - "NLP test conftest: session-scoped spaCy model + mock zero-shot pipeline fixture"
  - "Evaluation dataset as Python module with typed dicts for easy import in tests"

requirements-completed: [NLP-05]

duration: 3 min
completed: 2026-02-23
---

# Phase 3 Plan 01: NLP Dependencies, Evaluation Dataset, and Test Infrastructure Summary

**NLP deps (spaCy, transformers, torch, scikit-learn, scipy) installed, 120-sentence eval dataset created, Alembic migration 0003 for sentence uniqueness, and NLP test fixtures established**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T21:13:00Z
- **Completed:** 2026-02-23T21:16:07Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- All five NLP dependencies added to pyproject.toml and verified importable
- Dockerfile updated with spaCy en_core_web_sm download (layer-cache-optimized placement)
- Alembic migration 0003 adds UniqueConstraint on sentences(article_id, position) with matching model __table_args__
- 120-sentence evaluation dataset with fact (36), opinion (39), mixed (20), unclear (25) across easy/hard/edge_case categories
- NLP test conftest provides session-scoped spaCy model and mock zero-shot pipeline fixture
- Added slow pytest marker to pyproject.toml for accuracy gate tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Install NLP dependencies and update Dockerfile** - `25572dc` (chore)
2. **Task 2: Create Alembic migration, evaluation dataset, test infrastructure** - `6188932` (feat)

## Files Created/Modified
- `pyproject.toml` - Added spacy, transformers, torch, scikit-learn, scipy deps + slow marker
- `Dockerfile` - Added spaCy en_core_web_sm model download after uv sync
- `alembic/versions/0003_sentence_position_unique.py` - UniqueConstraint migration
- `factfeed/db/models.py` - Sentence __table_args__ with UniqueConstraint
- `tests/nlp/__init__.py` - NLP test module init
- `tests/nlp/conftest.py` - Mock pipeline and spaCy fixtures
- `tests/nlp/eval_dataset.py` - 120 labeled evaluation sentences

## Decisions Made
- Evaluation dataset uses original sentences (not copied from articles) in BBC/Reuters/AP style
- 120 sentences across 4 label categories ensure meaningful accuracy measurement
- Session-scoped spaCy fixture prevents repeated 2-second model loads across test suite

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- NLP dependencies available for segmenter and classifier implementation
- Evaluation dataset ready for accuracy gate test in Plan 04
- Test infrastructure ready for unit tests in Plans 02 and 03

---
*Phase: 03-nlp-classification-pipeline*
*Completed: 2026-02-23*
