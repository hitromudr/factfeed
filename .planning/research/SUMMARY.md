# Project Research Summary

**Project:** FactFeed — News Aggregator with NLP Fact/Opinion Classification
**Domain:** Python news aggregation + sentence-level NLP classification web app
**Researched:** 2026-02-23
**Confidence:** MEDIUM

## Executive Summary

FactFeed is a server-rendered Python web application that fetches news articles from RSS feeds, classifies each sentence as fact, opinion, mixed, or unclear using a hybrid NLP pipeline, and presents inline color-coded highlights to users. The recommended implementation centers on FastAPI with Jinja2 templates, PostgreSQL with GIN-indexed full-text search, and a two-stage NLP classifier (fast rule-based pre-filter routing to a DeBERTa-v3 zero-shot transformer for ambiguous sentences only). All background scheduling runs via APScheduler inside the FastAPI process with a single-worker constraint. No frontend build step, no message queue, no user accounts — the architecture is intentionally lean for a 100-articles/day workload.

The most important architectural decision is the strict layering: ingestion writes to the database, NLP operates as a pure function that never touches the database, and the web layer only reads. This separation is not optional — it is what makes each layer independently testable, and the NLP classifier accuracy is too uncertain at design time to allow the web layer to depend on its internals. The zero-shot model (DeBERTa-v3-base-zeroshot-v2.0) is the right choice for zero-shot fact/opinion classification, beating BART-large-mnli by ~25% F1, but its softmax outputs are not reliable confidence scores and must be calibrated before display.

The dominant risk is in the NLP layer: zero-shot classifiers are sensitive to hypothesis wording, systematically overconfident on short text, and poor at handling attributed speech (the reporting verb problem). These are not edge cases — they describe the majority of news sentences. Build the evaluation set before the classifier, include attribution and hedged-claim sentences as mandatory hard cases, and treat hypothesis strings as versioned hyperparameters. Database schema decisions (GIN index, sentences child table, url_hash deduplication column) must all be made before data is ingested — retrofitting these is expensive.

---

## Key Findings

### Recommended Stack

The stack is well-defined and version-locked. Python 3.12 + FastAPI 0.132 + Pydantic v2 handles the web layer; SQLAlchemy 2.0 + asyncpg + Alembic manages the database layer with async-native queries. The NLP stack combines spaCy 3.8 (sentence segmentation and rule-based heuristics) with transformers 5.2 + torch 2.10 CPU-only for zero-shot classification. feedparser handles RSS parsing; APScheduler 3.11 runs the background fetch-and-classify cycle. All versions are current stable releases (Feb 2026). Docker deployment uses `python:3.12-slim` with a separate `migrate` container running Alembic before the app starts.

**Core technologies:**
- **FastAPI 0.132 + Jinja2 3.1**: Web framework and server-side templating — no JS build step, native async, Pydantic validation included
- **PostgreSQL 16 + SQLAlchemy 2.0 + asyncpg 0.31**: Async ORM with GIN-indexed full-text search — eliminates need for Elasticsearch at this scale
- **DeBERTa-v3-base-zeroshot-v2.0 + transformers 5.2**: Zero-shot fact/opinion classifier — 0.619 F1 macro across 28 NLI tasks, MIT licensed, 420 MB RAM on CPU
- **spaCy 3.8**: Sentence segmentation, POS tagging, NER for rule-based pre-filter — 3-5x faster than NLTK in production
- **APScheduler 3.11**: In-process background scheduling — sufficient for 100 articles/day without Redis/Celery overhead
- **feedparser 6.0.12**: RSS/Atom parsing with malformed feed tolerance — handles encoding degradation gracefully via bozo flag

**Critical version constraints:** SQLAlchemy 2.0-style `select()` queries are mandatory (not legacy `session.query()`); Pydantic v1 is incompatible with FastAPI 0.132; APScheduler 4.x is alpha and must not be used; transformers v5 (not v4) is the current release.

### Expected Features

The product thesis is sentence-level inline fact/opinion classification — no competitor (Google News, Ground News, AllSides, MBFC) operates at this granularity. All other features exist to support or surface this capability.

**Must have (table stakes):**
- RSS ingestion pipeline (5 sources: BBC, Reuters, AP, NPR, Al Jazeera) — without content the product does not exist
- NLP fact/opinion/mixed/unclear classification with 0.0–1.0 confidence per sentence — the entire product thesis
- Article storage with PostgreSQL FTS index — blocks search and retrieval
- Inline color-coded sentence highlighting (green/red/yellow) — the core UX that proves the concept
- Keyword search with source and date filters — users immediately expect these
- "Facts first" default sort order with recency toggle — demonstrates the product's point of view
- Collapsible opinion sections (default collapsed) — enforces facts-prioritized value without censorship
- Graceful error handling for paywalled content, encoding failures, low-confidence sentences — classifier errors must not break user trust

**Should have (competitive):**
- Confidence score display as relative bands (High/Medium/Low), not raw percentages — calibrated scores only
- Ambiguous/unclear sentence flagging with tooltip explanation — prevents users from thinking the tool is broken
- Static MBFC/AllSides source credibility badge in article viewer — low-complexity trust signal
- "Mixed" label as a fourth classification state — more honest than binary fact/opinion

**Defer (v2+):**
- Topic/category browsing — requires a separate topic classification NLP pass
- User feedback loop for misclassification corrections — requires accounts or session tracking
- Multi-language support — NLP model accuracy in non-English is significantly lower
- Email/push notifications — requires notification infrastructure
- Bias visualization/charts — requires accumulated historical data to be meaningful

**Anti-features to avoid (by design):**
- Personalized feed — contradicts FactFeed's no-filter-bubble mission and requires user data collection
- User accounts and authentication — out of scope for v1; use localStorage for preferences
- Automated claim truth verification — a different product; FactFeed classifies verifiability, not truth

### Architecture Approach

The architecture separates into four independent layers: External (RSS feeds, NewsAPI), Ingestion (APScheduler + feedparser + httpx + Deduplicator), NLP Pipeline (preprocessor → rules → zero-shot transformer → aggregator), and Web (FastAPI routes + Jinja2 templates querying PostgreSQL). The critical design rule is that NLP modules receive plain text and return structured data — they never import SQLAlchemy. Ingestion owns all database writes. The web layer only reads via SQLAlchemy sessions injected as FastAPI dependencies. This layering makes the NLP pipeline independently testable, which matters because classifier accuracy will need iteration.

**Major components:**
1. **APScheduler (AsyncIOScheduler)** — triggers periodic ingestion jobs inside FastAPI lifespan context manager; single-worker constraint mandatory
2. **NLP Pipeline (nlp/)** — pure function chain: `preprocessor.split()` → `rules.classify_batch()` → `zero_shot.classify_batch(ambiguous_only)` → `aggregator.merge()`; zero transformer calls for clearly-labeled sentences
3. **PostgreSQL (articles + sentences + sources tables)** — sentences as a child table (never JSON blob on article); `tsvector GENERATED ALWAYS AS ... STORED` column with GIN index from day one
4. **FastAPI Web Layer (web/routes/)** — reads pre-classified data from DB, renders Jinja2 templates; classification never happens in request path
5. **Jinja2 Templates (templates/)** — applies `.fact` / `.opinion` / `.mixed` / `.unclear` CSS classes per sentence; confidence score exposed via `data-confidence` attribute for JS hover

### Critical Pitfalls

1. **Zero-shot model overconfidence on short/ambiguous text** — Raw softmax scores are not calibrated confidence values; apply temperature scaling before display; cap displayed confidence at 0.6 for texts under 30 tokens; route headlines under 20 words to "unclear" rather than forcing a classification.

2. **Label hypothesis wording sensitivity** — Hypothesis phrasing changes classification outcomes significantly; build a 100+ sentence evaluation set before writing classifier code; test at least 5 phrasings per class; store hypothesis strings as named constants with version numbers, not magic strings.

3. **Attribution sentence misclassification** — "The CEO said profits are up 40%" has two semantic layers (factual attribution + unverifiable claim); build a dedicated attribution pattern detector (regex + spaCy dependency parsing) that pre-labels quoted/reported-speech sentences as "mixed" before the transformer runs.

4. **APScheduler duplicate job execution** — Running FastAPI with multiple Gunicorn workers spawns one scheduler per worker; each feeds fetch and classification job executes N times; use `--workers 1` always or move ingestion to a separate process with PostgreSQL advisory locking.

5. **Missing GIN index on articles FTS** — PostgreSQL FTS without a GIN index performs sequential scans; at 36,500 articles/year this becomes 2-8 second query times; the GIN index must be created at schema design time, not retrofitted after data is inserted.

---

## Implications for Roadmap

Based on the feature dependency chain (ingestion → storage → NLP → web display) and pitfall phase mapping, research points to a five-phase structure. Each phase delivers something independently testable before the next phase builds on it.

### Phase 1: Database Foundation and Project Setup

**Rationale:** Every subsequent phase depends on the correct schema. The sentences child table, url_hash deduplication column, and GIN-indexed tsvector column are all significantly harder to add retroactively. PostgreSQL schema decisions made wrong here compound through all later phases.

**Delivers:** Working PostgreSQL schema (articles, sentences, sources tables); Alembic migration setup; Docker Compose environment with postgres + migrate + app services; project skeleton with layered directory structure.

**Addresses:** Article storage (table stakes prerequisite); full-text search foundation.

**Avoids:** Missing GIN index pitfall; storing sentences as JSON blob anti-pattern; retrofitting deduplication column pain.

**Research flags:** Well-documented patterns (SQLAlchemy 2.0 migration setup, Alembic async config). Skip research-phase.

---

### Phase 2: Ingestion Pipeline

**Rationale:** No content, no product. The ingestion pipeline must be built and validated against all five target sources before the NLP layer can be meaningfully tested on real data. Encoding normalization and deduplication must be solved here, not discovered later.

**Delivers:** APScheduler-driven background fetch from BBC, Reuters, AP, NPR, Al Jazeera RSS; feedparser bozo-flag logging; UTF-8 encoding normalization via ftfy; URL-hash deduplication; article body extraction; database insert with all schema columns populated.

**Addresses:** RSS ingestion pipeline (P1 feature); graceful paywall/encoding error handling.

**Avoids:** RSS encoding silent data loss (bozo flag); APScheduler multi-worker duplicate execution (single-worker constraint); fetching full article HTML synchronously in async context.

**Research flags:** Each of the five target RSS sources has known encoding quirks. Needs real-feed testing during implementation but no additional research phase — feedparser documentation is complete.

---

### Phase 3: NLP Classification Pipeline

**Rationale:** The classifier is the entire product thesis and has the highest implementation uncertainty. It must be built, evaluated against a calibrated test set, and producing reliable confidence scores before the UI layer is built — otherwise the UI will be built on top of incorrect output and need to be rebuilt.

**Delivers:** Evaluation set (100+ sentences, 30%+ hard cases including attribution sentences); rule-based pre-filter (hedging words, attribution patterns, modal verbs via spaCy); attribution sentence detector (pre-labels quoted/reported speech as "mixed"); zero-shot DeBERTa-v3 wrapper for ambiguous-only sentences; result aggregator; temperature-scaled confidence output; pipeline unit tests with mocked transformer.

**Addresses:** Inline fact/opinion/mixed/unclear classification (P1); confidence score display (P1); collapsible opinion sections (P1).

**Avoids:** Overconfident scores displayed raw; label hypothesis sensitivity (must lock hypothesis strings with evaluation set before coding); attribution misclassification; classifying full article text through transformer (512-token limit); NLTK punkt segmentation failures on news patterns (use spaCy).

**Research flags:** Needs deeper research during planning. NLP accuracy is MEDIUM confidence — no domain-specific benchmark for news fact/opinion on these sources. Hypothesis wording experiments require iteration. Recommend a planning spike to design the evaluation set structure before writing classifier code.

---

### Phase 4: Web Interface

**Rationale:** The web layer reads pre-classified data. It cannot be meaningfully built until Phase 3 produces validated output. Building it after the classifier ensures the template data model matches actual NLP output structure.

**Delivers:** FastAPI routes for search and article detail; Jinja2 templates (base.html, search.html, article.html) with `.fact` / `.opinion` / `.mixed` / `.unclear` CSS classes; inline confidence display as High/Medium/Low bands (not raw percentages); collapsible opinion sections; "facts first" sort order with recency toggle; source and date filters; keyword search using PostgreSQL FTS; graceful paywall labeling.

**Addresses:** Article list view; inline highlighting; keyword search; source/date filters; facts-first ordering; collapsible opinions (all P1 features).

**Avoids:** Displaying raw softmax as percentage confidence (UX pitfall); classifier running in request path (synchronous blocking); confidence display misleading users.

**Research flags:** Standard FastAPI + Jinja2 patterns — well-documented. Skip research-phase.

---

### Phase 5: Polish, Testing, and Hardening

**Rationale:** The "looks done but isn't" checklist from PITFALLS.md documents concrete failure modes that only manifest under production conditions: multi-source deduplication, multi-worker scheduler behavior, FTS performance at scale, transformer memory under load. These must be verified explicitly before shipping.

**Delivers:** Load test with 10,000 synthetic articles verifying GIN index performance; multi-worker APScheduler duplicate-execution test; real-feed ingestion test across all 5 sources (encoding, bozo, empty body); confidence calibration validation (does "High confidence" correlate with actual accuracy on held-out set?); model preload at startup with health check endpoint; rate limiting on /search via slowapi; XSS protection (bleach on ingested content); static MBFC/AllSides source credibility badge.

**Addresses:** Graceful error handling hardening; source credibility metadata (P2 enhancement).

**Avoids:** FTS degradation at scale; transformer cold-start blocking first request; APScheduler silent multi-worker failure; RSS encoding data loss at production volume; search endpoint as denial-of-service vector.

**Research flags:** Security hardening (rate limiting, XSS) has standard patterns. Skip research-phase.

---

### Phase Ordering Rationale

- **Schema before ingestion:** The GIN index, url_hash column, and sentences child table must exist before any data is inserted. Retrofitting these is a maintenance-window operation on a live database.
- **Ingestion before NLP:** The classifier needs real article text from the actual five sources to validate; synthetic text will not reveal source-specific encoding or segmentation failures.
- **NLP before web:** The template data model (`{label, confidence, text}` per sentence) is defined by NLP output. Building the web layer before the classifier produces stable output means rebuilding it when output structure changes.
- **All four layers before hardening:** The production failure modes (multi-worker scheduling, FTS scale, model memory) can only be tested with the full integrated system.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 3 (NLP Pipeline):** Hypothesis wording experiments, evaluation set design, and confidence calibration are medium-confidence areas. Recommend a planning spike to define the evaluation set structure and document initial hypothesis candidates before writing code. The specific accuracy achievable on these five news sources is unknown until tested.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Database Foundation):** SQLAlchemy 2.0 + Alembic async setup is well-documented with official examples.
- **Phase 2 (Ingestion):** feedparser + APScheduler + httpx patterns are established. Real-feed testing is implementation work, not research.
- **Phase 4 (Web Interface):** FastAPI + Jinja2 is the recommended FastAPI documentation pattern. Standard template inheritance applies.
- **Phase 5 (Hardening):** Security and load testing patterns are standard. No novel research needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified against PyPI as of Feb 2026; version compatibility matrix verified against official docs; asyncpg/SQLAlchemy integration confirmed against official SQLAlchemy dialect docs |
| Features | MEDIUM | Competitor analysis HIGH confidence (official sites); NLP-specific UX patterns MEDIUM (academic sources, some peer-reviewed); sentence-level inline classification UX is a novel intersection with no direct precedent — no competitor does this |
| Architecture | MEDIUM | Layering patterns verified against FastAPI and HuggingFace official docs; specific deduplication hash and FTS stored-column patterns from MEDIUM-confidence secondary sources; Google News system design reference is MEDIUM |
| Pitfalls | MEDIUM | Critical technical pitfalls (APScheduler multi-worker, GIN index, transformer cold-start) verified against official docs; NLP overconfidence and hypothesis sensitivity backed by peer-reviewed research; RSS encoding issues from feedparser docs and GitHub issues |

**Overall confidence:** MEDIUM

### Gaps to Address

- **NLP accuracy on target sources (unresolved):** The DeBERTa-v3-base-zeroshot-v2.0 model achieves 0.619 F1 macro on general NLI benchmarks. Its accuracy on news fact/opinion classification for these five specific sources is unknown. The 80% accuracy target in the project brief may not be achievable with zero-shot alone. Mitigation: build the evaluation set in Phase 3 and measure before committing to the target; be prepared to add a fine-tuning step if zero-shot accuracy is insufficient.

- **Confidence calibration approach (unresolved):** Temperature scaling is well-documented for classification models but has not been validated for zero-shot NLI on news sentences specifically. Guo et al. (2017) is the reference paper; the scaling parameter must be fit on a held-out calibration set. This is doable but requires a labeled dataset that does not yet exist.

- **Near-duplicate article detection (deferred):** PITFALLS.md recommends two-stage deduplication (URL hash + content MinHash/SimHash). The roadmap defers near-duplicate detection to a later phase. Schema design in Phase 1 should add the `content_hash` column as a placeholder even if the near-dup logic is not implemented yet.

- **trafilatura dependency (implicit):** ARCHITECTURE.md references `trafilatura` for content extraction from article URLs but STACK.md does not list it. This needs to be confirmed and added to requirements during Phase 2 planning.

---

## Sources

### Primary (HIGH confidence)
- FastAPI 0.132 release notes and docs: https://github.com/fastapi/fastapi/releases
- FastAPI Templates docs: https://fastapi.tiangolo.com/advanced/templates/
- SQLAlchemy 2.0 async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLAlchemy PostgreSQL dialect: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- HuggingFace Transformers pipeline docs: https://huggingface.co/docs/transformers/main_classes/pipelines
- FastAPI Docker deployment: https://fastapi.tiangolo.com/deployment/docker/
- APScheduler FAQ (interprocess safety): https://apscheduler.readthedocs.io/en/3.x/faq.html
- feedparser character encoding docs: https://pythonhosted.org/feedparser/character-encoding.html
- PyPI: fastapi, sqlalchemy, asyncpg, alembic, transformers, torch, spacy, feedparser, httpx, apscheduler, pydantic-settings, jinja2, pytest (all version-confirmed)

### Secondary (MEDIUM confidence)
- MoritzLaurer/deberta-v3-base-zeroshot-v2.0 model card (F1 scores): https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0
- Guo et al. "On Calibration of Modern Neural Networks" (2017): https://arxiv.org/pdf/1706.04599
- Ground News About/Features: https://ground.news/about
- AllSides Balanced News: https://www.allsides.com/unbiased-balanced-news
- MBFC Methodology: https://mediabiasfactcheck.com/methodology/
- FastAPI best practices (project structure): https://github.com/zhanymkanov/fastapi-best-practices
- PostgreSQL FTS with GIN index: https://floredata.com/blog/postgresql-full-text-search-in-depth/
- asyncpg vs psycopg3 benchmark: https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/
- CHI 2025: Fact-Checkers Requirements for Explainable Fact-Checking: https://dl.acm.org/doi/full/10.1145/3706598.3713277

### Tertiary (LOW confidence)
- RSS duplicate detection methodology: http://www.xn--8ws00zhy3a.com/blog/2006/08/rss-dup-detection (2006 post, principle still valid)
- WebSearch: news aggregator table stakes features 2025 (multiple sources)
- WebSearch: NLP fact-opinion classification confidence scores 2025

---

*Research completed: 2026-02-23*
*Ready for roadmap: yes*
