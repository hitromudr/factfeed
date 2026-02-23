# Architecture Research

**Domain:** News aggregator with NLP fact/opinion classification pipeline
**Researched:** 2026-02-23
**Confidence:** MEDIUM (patterns drawn from multiple verified sources; specific choices verified against official FastAPI/HuggingFace docs)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         External Layer                            │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│   │  BBC RSS   │  │Reuters RSS │  │ NewsAPI.org│  (+ others)    │
│   └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                │
└─────────┼───────────────┼───────────────┼──────────────────────-┘
          │               │               │
          ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Ingestion Layer                              │
│   ┌──────────────────────────────────────────────────────┐       │
│   │  Scheduler (APScheduler / lifespan startup)           │       │
│   │  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  │       │
│   │  │ RSS Fetcher│  │ API Client   │  │ Deduplicator│  │       │
│   │  └─────┬──────┘  └──────┬───────┘  └──────┬──────┘  │       │
│   └────────┼───────────────┼────────────────-─┼──────────┘       │
└────────────┼───────────────┼──────────────────┼──────────────────┘
             │               │                  │
             ▼               ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                       NLP Pipeline Layer                          │
│   ┌──────────────────────────────────────────────────────┐       │
│   │  Article Preprocessor (sentence splitting, cleaning) │       │
│   └────────────────────────┬─────────────────────────────┘       │
│                            │                                      │
│                  ┌─────────┴──────────┐                          │
│                  ▼                    ▼                           │
│   ┌──────────────────────┐  ┌────────────────────────────┐       │
│   │ Rule-Based Classifier│  │ Zero-Shot Transformer       │       │
│   │ (hedging words,      │  │ (DeBERTa-v3 / BART-MNLI)   │       │
│   │  attribution markers)│  │ for ambiguous sentences     │       │
│   └──────────┬───────────┘  └─────────────┬──────────────┘       │
│              └──────────────┬─────────────┘                       │
│                             ▼                                      │
│   ┌──────────────────────────────────────────────────────┐       │
│   │  Result Aggregator (merge labels + confidence scores) │       │
│   └────────────────────────┬─────────────────────────────┘       │
└────────────────────────────┼─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Storage Layer                               │
│   ┌──────────────────────────────────────────────────────┐       │
│   │  PostgreSQL                                           │       │
│   │  ┌──────────────┐  ┌───────────────┐  ┌──────────┐  │       │
│   │  │ articles     │  │ sentences     │  │ sources  │  │       │
│   │  │ (metadata,   │  │ (text, label, │  │ (feed    │  │       │
│   │  │  url_hash,   │  │  confidence,  │  │  config) │  │       │
│   │  │  tsvector)   │  │  article_fk)  │  │          │  │       │
│   │  └──────────────┘  └───────────────┘  └──────────┘  │       │
│   └──────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Web Layer (FastAPI)                         │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│   │ Search Route │  │ Article Route│  │ Static/CSS/JS      │    │
│   │ (FTS query,  │  │ (render with │  │ (mounted at        │    │
│   │  filter args)│  │  highlights) │  │  /static/)         │    │
│   └──────┬───────┘  └──────┬───────┘  └────────────────────┘    │
│          └─────────────────┘                                      │
│                      │                                            │
│   ┌──────────────────▼───────────────────────────────────┐       │
│   │  Jinja2 Templates (base.html, search.html,            │       │
│   │                    article.html, _highlights.html)    │       │
│   └──────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    [ User's Browser ]
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Scheduler | Triggers periodic fetching jobs on a cron interval | APScheduler `AsyncIOScheduler` started in FastAPI lifespan |
| RSS Fetcher | Polls configured RSS feed URLs, parses feed items | `feedparser` library; handles per-feed rate limits and errors |
| API Client | Calls structured news APIs (e.g., NewsAPI.org) | `httpx` async client; respects daily quota limits |
| Deduplicator | Prevents storing the same article twice | SHA-256 of normalized URL stored as `url_hash`; UNIQUE constraint in DB |
| Article Preprocessor | Cleans raw HTML/text, splits into sentences | `trafilatura` (content extraction) + `spaCy` or `nltk` sentence splitter |
| Rule-Based Classifier | Fast first-pass labeling of obvious fact/opinion sentences | Python heuristics on hedging words, attribution phrases, modal verbs |
| Zero-Shot Transformer | Labels ambiguous sentences without fine-tuning | HuggingFace `pipeline("zero-shot-classification")` with DeBERTa-v3 or BART-MNLI |
| Result Aggregator | Merges rule-based and transformer outputs into final JSON payload | Pure Python logic; emits `label` + `confidence` per sentence |
| PostgreSQL | Persists articles, sentence-level analysis, source configs | SQLAlchemy ORM + Alembic migrations; `tsvector` column for FTS |
| FastAPI Web Layer | Handles HTTP requests, queries DB, returns rendered HTML | FastAPI routes + `TemplateResponse` returning Jinja2-rendered pages |
| Jinja2 Templates | Renders color-coded article views and search results | Template inheritance from `base.html`; inline styling driven by label class |

## Recommended Project Structure

```
factfeed/
├── main.py                   # FastAPI app factory, lifespan, mounts
├── config.py                 # Settings (pydantic-settings), env vars
├── db/
│   ├── session.py            # SQLAlchemy engine + session factory
│   ├── models.py             # ORM models: Article, Sentence, Source
│   └── migrations/           # Alembic migration scripts
│       └── versions/
├── ingestion/
│   ├── scheduler.py          # APScheduler setup, job registration
│   ├── fetcher.py            # RSS + API fetching logic
│   └── deduplication.py      # url_hash computation + DB check
├── nlp/
│   ├── pipeline.py           # Orchestrates preprocessor → rules → transformer
│   ├── preprocessor.py       # Text cleaning, sentence splitting
│   ├── rules.py              # Heuristic classifier (hedging, attribution)
│   └── zero_shot.py          # HuggingFace zero-shot classifier wrapper
├── web/
│   ├── routes/
│   │   ├── search.py         # GET /search — FTS query + filter handling
│   │   └── article.py        # GET /article/{id} — article + highlight render
│   └── deps.py               # FastAPI dependencies (DB session injection)
├── templates/
│   ├── base.html             # Shared layout, nav, CSS links
│   ├── search.html           # Search bar + results list
│   └── article.html          # Article body with inline highlights
└── static/
    ├── style.css             # Color coding: .fact, .opinion, .mixed classes
    └── app.js                # Hover-to-show confidence score (minimal JS)
```

### Structure Rationale

- **ingestion/**: Completely decoupled from the web layer. The scheduler triggers fetching; results are written directly to DB. The web layer never calls ingestion code.
- **nlp/**: Isolated pipeline that accepts raw text and returns structured output. No DB access inside NLP modules — keeps them testable in isolation.
- **web/**: FastAPI routes only read from DB and render templates. No business logic here.
- **db/models.py**: Single source of truth for schema. Both ingestion and web read from same models.
- **templates/ + static/**: Co-located for clarity. Jinja2 base/child pattern reduces duplication.

## Architectural Patterns

### Pattern 1: Pipeline as a Pure Function Chain

**What:** Each NLP stage (preprocess → rule-classify → zero-shot → aggregate) is a function that takes structured input and returns structured output. No side effects inside the pipeline.
**When to use:** Always for the NLP layer. Enables unit testing each stage independently with fixtures.
**Trade-offs:** Slightly more boilerplate than an all-in-one function; pays off immediately when debugging classifier accuracy.

**Example:**
```python
# nlp/pipeline.py
def run_pipeline(raw_text: str) -> list[SentenceResult]:
    sentences = preprocessor.split(raw_text)
    rule_results = rules.classify_batch(sentences)
    ambiguous = [s for s, r in zip(sentences, rule_results) if r.label == "unclear"]
    zs_results = zero_shot.classify_batch(ambiguous)
    return aggregator.merge(sentences, rule_results, zs_results)
```

### Pattern 2: Lifespan-Managed Scheduler

**What:** APScheduler `AsyncIOScheduler` is started and stopped inside FastAPI's `lifespan` context manager, not `@app.on_event` (deprecated). The scheduler runs in the same process as FastAPI.
**When to use:** For this project's scale (100+ articles/day). No separate worker process needed.
**Trade-offs:** Scheduler shares process memory with web server. Under Gunicorn multi-worker deployments, each worker spawns its own scheduler — use `--workers 1` in production or add a process-level lock. (HIGH confidence: verified in FastAPI docs and APScheduler GitHub discussions.)

**Example:**
```python
# main.py
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_ingestion, "interval", hours=1)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

### Pattern 3: Deduplication via URL Hash

**What:** Compute `sha256(normalize(url))` before any network I/O. Check DB for existing hash. Skip fetching and processing if already stored.
**When to use:** Before inserting any article. RSS feeds commonly re-emit recent items.
**Trade-offs:** URL normalization must be consistent (strip tracking params, lowercase scheme+host). Content-hash deduplication catches reposts on different URLs but is more expensive — defer to v2.

**Example:**
```python
# ingestion/deduplication.py
import hashlib

def url_hash(url: str) -> str:
    normalized = url.strip().lower().split("?")[0]  # strip query params
    return hashlib.sha256(normalized.encode()).hexdigest()
```

### Pattern 4: Hybrid NLP with Rule-First Routing

**What:** Apply cheap rule-based classification first. Only route sentences the rules cannot confidently label to the zero-shot transformer. The transformer is ~10-100x slower per sentence than rules.
**When to use:** Always. Zero-shot classification is a `ChunkPipeline` in HuggingFace Transformers — each sentence requires multiple model forward passes. Processing every sentence through the transformer would bottleneck ingestion. (HIGH confidence: verified against HuggingFace Transformers docs.)
**Trade-offs:** Rule quality determines how much transformer work is avoided. Rules must be maintained as language patterns evolve.

### Pattern 5: FTS with Stored tsvector

**What:** Add a `tsvector` column to the `articles` table, populated with a PostgreSQL trigger or computed on insert. Search uses `@@` operator against this column with a GIN index.
**When to use:** Always for PostgreSQL FTS. Computing `to_tsvector()` at query time is slower and prevents efficient indexing.
**Trade-offs:** Slightly more complex insert logic; query performance is an order of magnitude better.

**Example:**
```sql
-- In migration
ALTER TABLE articles ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))
    ) STORED;

CREATE INDEX articles_search_vector_idx ON articles USING GIN(search_vector);
```

## Data Flow

### Ingestion Flow (background, scheduled)

```
APScheduler triggers run_ingestion()
    ↓
For each configured source (RSS URL or API endpoint):
    RSS Fetcher / API Client → raw feed items
    ↓
For each item:
    url_hash computed → DB lookup (already seen? skip)
    ↓
HTTP GET article URL → raw HTML body
    ↓
trafilatura.extract() → clean article text
    ↓
NLP Pipeline:
    preprocessor.split() → list of sentences
    rules.classify_batch() → (label, confidence) per sentence
    zero_shot.classify_batch(ambiguous_only) → (label, confidence)
    aggregator.merge() → final SentenceResult list
    ↓
DB INSERT: Article row + Sentence rows (with labels, confidence)
```

### Search Request Flow (user-initiated)

```
Browser GET /search?q=inflation&source=bbc&from=2026-01-01
    ↓
FastAPI search route
    ↓
SQLAlchemy query:
    SELECT articles WHERE search_vector @@ plainto_tsquery('english', q)
    AND source_id IN (filter) AND published_at >= from_date
    ORDER BY ts_rank(search_vector, query) DESC
    ↓
Jinja2 TemplateResponse("search.html", context={"results": [...], "query": q})
    ↓
Browser renders HTML — fact sentences shown, opinion sentences collapsible
```

### Article Detail Flow

```
Browser GET /article/42
    ↓
FastAPI article route
    ↓
SQLAlchemy:
    SELECT article WHERE id=42
    SELECT sentences WHERE article_id=42 ORDER BY position
    ↓
Jinja2 TemplateResponse("article.html", context={"article": ..., "sentences": [...]})
    ↓
Template loops over sentences, applies CSS class .fact / .opinion / .mixed / .unclear
    per label; confidence score exposed via data-confidence attribute for JS hover
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| BBC/Reuters/AP/NPR/Al Jazeera RSS | `feedparser.parse(url)` on a schedule | No auth required; respect `ttl` field in feed if present |
| NewsAPI.org | `httpx` GET with `apiKey` header | Free tier: 100 requests/day; store quota-aware counter in DB or config |
| HuggingFace model (local) | `transformers.pipeline("zero-shot-classification", model="...")` | Model downloaded on first run to `~/.cache/huggingface`; consider pre-downloading in Docker build |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scheduler → Ingestion | Direct function call (same process) | No message queue needed at this scale |
| Ingestion → NLP | Function call: `run_pipeline(text)` returns structured list | NLP has no DB imports — receives and returns plain data |
| NLP → Storage | Ingestion layer owns DB writes; calls `db.save_article(article, sentences)` | NLP never touches SQLAlchemy |
| Web → Storage | SQLAlchemy session via FastAPI dependency injection (`Depends(get_db)`) | Session-per-request pattern; no shared state |
| Web → Templates | `TemplateResponse` with context dict | Templates only receive serializable data (dicts, strings, lists) |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Dev / 100 articles/day | Single process FastAPI + APScheduler in same process; SQLite can substitute PostgreSQL locally |
| 1k–10k articles/day | Keep monolith; add PostgreSQL connection pooling (pgBouncer or SQLAlchemy pool); cache FTS queries in Redis or lru_cache |
| 10k+ articles/day | Separate ingestion worker process; use Celery + Redis for job queue; offload zero-shot to dedicated GPU worker |

### Scaling Priorities

1. **First bottleneck:** Zero-shot transformer inference time. At 100 articles/day with ~20 ambiguous sentences/article, this is ~2,000 transformer inferences/day — fine for CPU. At 10x scale, batch the sentences and consider `batch_size` parameter in the HuggingFace pipeline.
2. **Second bottleneck:** PostgreSQL FTS under high search load. GIN index handles this well to 10k+ articles; beyond that, consider partitioning by date.

## Anti-Patterns

### Anti-Pattern 1: Running Zero-Shot Classification on Every Sentence

**What people do:** Pass all sentences from every article through the transformer pipeline unconditionally.
**Why it's wrong:** Zero-shot classification in HuggingFace Transformers uses `ChunkPipeline` — each sentence requires multiple forward passes (one per candidate label). At N labels and M sentences, inference is O(N*M) model calls. This creates an ingestion bottleneck within hours on CPU hardware.
**Do this instead:** Apply rule-based classifier first. Only route sentences the rules flag as "unclear" to the transformer. Target: transformer sees ≤30% of sentences.

### Anti-Pattern 2: Running the Scheduler in Multiple Gunicorn Workers

**What people do:** Deploy FastAPI under Gunicorn with `--workers 4`, each worker starts the APScheduler. Four workers means four schedulers, each fetching the same feeds.
**Why it's wrong:** Duplicate articles overwhelm deduplication, the deduplicator becomes a race condition under concurrent writes, and you hammer external RSS feeds unnecessarily.
**Do this instead:** Run with `--workers 1` for the process containing the scheduler. Or move ingestion to a separate standalone script/container triggered by a real cron job (OS cron, Docker cron, or Kubernetes CronJob).

### Anti-Pattern 3: Building FTS Queries with String Interpolation

**What people do:** `f"SELECT * FROM articles WHERE body LIKE '%{user_query}%'"` because FTS feels complex.
**Why it's wrong:** SQL injection vulnerability; `LIKE` does not use the GIN index; performance degrades linearly with table size.
**Do this instead:** Use `plainto_tsquery('english', :q)` with bound parameters via SQLAlchemy. The GIN index makes this O(log N).

### Anti-Pattern 4: Storing Sentence-Level Data as JSON in the Article Row

**What people do:** Store the NLP output as a JSON blob in an `analysis` column on the articles table, avoiding a separate sentences table.
**Why it's wrong:** Cannot query individual sentences (e.g., "show only fact sentences"), cannot filter by confidence score, cannot re-run classification on just unclear sentences. Makes the search feature impossible without loading every article.
**Do this instead:** Sentences as a child table with columns: `id`, `article_id` (FK), `position`, `text`, `label`, `confidence`. This enables flexible queries and future feature work.

### Anti-Pattern 5: Fetching Full Article HTML Inside the Scheduler Synchronously

**What people do:** Use `requests.get()` (synchronous) inside an async scheduler job, blocking the event loop.
**Why it's wrong:** Blocks FastAPI's async event loop during HTTP I/O, making the web server unresponsive while fetching.
**Do this instead:** Use `httpx.AsyncClient` with `await` for all outbound HTTP in async contexts. Or run the ingestion job as a thread-pool task via `asyncio.to_thread()` if mixing sync/async is unavoidable.

## Sources

- FastAPI Background Tasks official docs: https://fastapi.tiangolo.com/tutorial/background-tasks/ (HIGH confidence)
- FastAPI Templates official docs: https://fastapi.tiangolo.com/advanced/templates/ (HIGH confidence)
- HuggingFace Transformers: Zero-Shot Classification Pipeline and ChunkPipeline behavior: https://huggingface.co/docs/transformers/main_classes/pipelines (HIGH confidence)
- HuggingFace Zero-Shot Classification issue #19063 (batch_size behavior confirmed): https://github.com/huggingface/transformers/issues/19063 (HIGH confidence)
- Google News System Design overview (component structure validation): https://www.systemdesignhandbook.com/guides/google-news-system-design/ (MEDIUM confidence)
- FastAPI + APScheduler integration pattern: https://procodebase.com/article/mastering-background-tasks-and-scheduling-in-fastapi (MEDIUM confidence)
- FastAPI best practices (project structure): https://github.com/zhanymkanov/fastapi-best-practices (MEDIUM confidence)
- FastAPI + Jinja2 project structure: https://realpython.com/fastapi-jinja2-template/ (MEDIUM confidence)
- RSS deduplication via URL hash: https://www.alibaba.com/product-insights/call-for-help-stop-repeating-rss-feed-items-proven-deduplication-methods.html (MEDIUM confidence)
- PostgreSQL FTS with stored tsvector and GIN index: https://floredata.com/blog/postgresql-full-text-search-in-depth/ (MEDIUM confidence)

---
*Architecture research for: News aggregator with NLP fact/opinion classification pipeline (FactFeed)*
*Researched: 2026-02-23*
