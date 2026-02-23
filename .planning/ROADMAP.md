# Roadmap: FactFeed

## Overview

FactFeed is built in five phases that follow a strict dependency chain. The database schema is established first because the GIN index, sentences child table, and url_hash column cannot be retrofitted cheaply. Ingestion is built second to produce real article data for the NLP layer to train against. The NLP classifier is built third and validated against a held-out evaluation set before the web layer touches its output — classifier accuracy is the highest-uncertainty component and determines the template data model. The web interface is built fourth, reading pre-classified data only. Final hardening verifies production failure modes (scheduler multi-worker safety, FTS at scale, model memory) that only manifest with the full integrated system.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Database Foundation** - Establish the PostgreSQL schema with all indexes, child tables, and columns required before any data is inserted (completed 2026-02-23)
- [x] **Phase 2: Ingestion Pipeline** - Fetch, deduplicate, and persist real article content from all five target RSS sources on a scheduled background job (completed 2026-02-23)
- [ ] **Phase 3: NLP Classification Pipeline** - Build and validate the hybrid fact/opinion/mixed/unclear classifier with calibrated confidence scores before the web layer depends on its output
- [ ] **Phase 4: Web Interface** - Deliver the searchable article reader with inline sentence highlighting, collapsible opinion sections, and full-text search filters
- [ ] **Phase 5: Polish and Hardening** - Verify production failure modes, run classifier accuracy tests, complete UAT, and rate-limit the search endpoint

## Phase Details

### Phase 1: Database Foundation
**Goal**: The PostgreSQL schema is correct and complete before any data enters it
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01
**Success Criteria** (what must be TRUE):
  1. `alembic upgrade head` runs cleanly against a fresh PostgreSQL 16 container and creates articles, sentences, and sources tables
  2. The articles table has a `tsvector GENERATED ALWAYS AS ... STORED` column with a GIN index present from migration zero
  3. The sentences table exists as a child of articles (not a JSON column on articles) with label, confidence, and position columns
  4. The articles table has a `url_hash` column with a unique constraint for deduplication
  5. Docker Compose brings up postgres, migrate, and app services in correct startup order
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffold + SQLAlchemy ORM models (Article, Sentence, Source) and async session factory
- [ ] 01-02-PLAN.md — Alembic async migration (hand-written initial schema) + Docker Compose startup ordering
- [ ] 01-03-PLAN.md — pytest smoke tests verifying schema structure and GENERATED column behavior

### Phase 2: Ingestion Pipeline
**Goal**: Real article content flows from all five RSS sources into the database continuously without manual intervention
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INFRA-03
**Success Criteria** (what must be TRUE):
  1. Running the ingestion job inserts articles from BBC, Reuters, AP News, NPR, and Al Jazeera RSS feeds into the database
  2. Re-running the ingestion job on already-seen URLs produces no duplicate rows (deduplication by url_hash is enforced)
  3. A malformed feed, encoding failure, or unreachable source logs an error and continues processing remaining sources without crashing
  4. Each persisted article has a non-empty body text field extracted from the fetched content
  5. APScheduler triggers the fetch-and-persist cycle on a configurable interval inside the FastAPI process with a single-worker guard active
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Schema migration (add is_partial, author, lead_image_url, body_html columns) + install Phase 2 dependencies + config
- [x] 02-02-PLAN.md — Core ingestion modules: RSS fetcher, article extractor (trafilatura), URL deduplicator, source definitions
- [x] 02-03-PLAN.md — Runner orchestrator, persister, structured logging, APScheduler integration, FastAPI lifespan
- [x] 02-04-PLAN.md — Ingestion pipeline test suite (unit + integration tests with mocked HTTP and DB)

### Phase 3: NLP Classification Pipeline
**Goal**: Every ingested article's sentences are classified as fact, opinion, mixed, or unclear with calibrated confidence scores that are accurate enough to display to users
**Depends on**: Phase 2
**Requirements**: NLP-01, NLP-02, NLP-03, NLP-04, NLP-05
**Success Criteria** (what must be TRUE):
  1. Calling the classification pipeline on an article body produces a list of sentence records, each with a label (fact/opinion/mixed/unclear) and a confidence score between 0.0 and 1.0
  2. Sentences containing attributed speech patterns ("The CEO said X") are routed through the attribution pre-filter and classified as mixed before the transformer runs
  3. Short or ambiguous sentences (under 30 tokens, satire markers, breaking news without context) receive an "unclear" label rather than a forced fact/opinion classification
  4. Unit tests for the classifier pass and demonstrate 80%+ accuracy on the held-out evaluation set (100+ sentences including hard cases)
  5. Classification results are written to the sentences child table in the database, not stored as JSON on the articles row
**Plans**: TBD

### Phase 4: Web Interface
**Goal**: Users can search the fact-classified article database and read articles with inline sentence highlighting showing exactly which content is factual versus opinion
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, SEARCH-01, SEARCH-02, SEARCH-03, SEARCH-04, INFRA-02, INFRA-04
**Success Criteria** (what must be TRUE):
  1. Typing a keyword into the search bar returns a list of matching articles ordered by fact-density ratio by default, with a toggle to switch to recency ordering
  2. Search results can be filtered by source and by date range (last 24h, 7 days, 30 days) and the correct subset of articles is returned
  3. Clicking an article shows its full text with sentences color-coded: green for fact, red for opinion, yellow for mixed or unclear
  4. Hovering over a highlighted sentence shows its confidence score (displayed as High/Medium/Low, not raw decimal)
  5. Opinion sentences are collapsed by default behind a "Show opinion content" control; expanding the control reveals them inline
  6. The interface is usable on a mobile viewport without horizontal scrolling and no user account or login is required to access any feature
**Plans**: TBD

### Phase 5: Polish and Hardening
**Goal**: The integrated system passes accuracy benchmarks, handles edge cases that only appear at production volume, and is safe to run continuously
**Depends on**: Phase 4
**Requirements**: INFRA-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. The classifier unit test suite runs against a labeled evaluation dataset and reports accuracy at or above the 80% target, with results logged to a test report
  2. Manual UAT on 10 real articles confirms inline highlighting is correct and the collapsible opinion control works as expected
  3. Automated API response tests cover the search and article detail endpoints and pass on a clean environment
  4. Running FastAPI with two Gunicorn workers does not cause the ingestion job to execute twice (APScheduler single-worker constraint is verified by test or guard)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Database Foundation | 3/3 | Complete   | 2026-02-23 |
| 2. Ingestion Pipeline | 4/4 | Complete   | 2026-02-23 |
| 3. NLP Classification Pipeline | 0/TBD | Not started | - |
| 4. Web Interface | 0/TBD | Not started | - |
| 5. Polish and Hardening | 0/TBD | Not started | - |
