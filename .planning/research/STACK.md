# Stack Research

**Domain:** Python news aggregator with NLP fact/opinion classification
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH (core stack verified via PyPI/official docs; NLP model choice MEDIUM due to no domain-specific benchmark)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12+ | Runtime | Longer support window vs 3.11; better async performance; fewer async-related edge cases. FastAPI officially recommends 3.12+. |
| FastAPI | 0.132.0 | Web framework + API | Natively async, integrates Jinja2 and Pydantic out of the box, no separate frontend build step required. The mainstream Python web API choice for new projects as of 2025. |
| Pydantic v2 | 2.12.5 | Data validation and settings | Ships with FastAPI; v2 is 5-50x faster than v1 due to Rust core. Provides typed article/classification models and config validation. FastAPI has dropped Pydantic v1 support. |
| Jinja2 | 3.1.6 | Server-side HTML templating | The official FastAPI-recommended template engine; zero JS build step; renders inline fact/opinion color highlights on the server. Pallets-maintained, stable. |
| SQLAlchemy | 2.0.46 | ORM + async database layer | Version 2.0 style queries are mandatory (not legacy 1.x style); native asyncio support via `create_async_engine`; full PostgreSQL FTS support via `func.to_tsvector` / `func.to_tsquery`. |
| asyncpg | 0.31.0 | Async PostgreSQL driver | 5x faster than psycopg3 in benchmarks; production-stable; required by SQLAlchemy async when targeting PostgreSQL. Use as `postgresql+asyncpg://` connection string. |
| Alembic | 1.18.4 | Database migrations | The standard SQLAlchemy migration tool; supports async engines; essential for evolving the articles/classifications schema without data loss. |
| PostgreSQL | 16+ | Primary datastore + FTS | Built-in `tsvector`/`tsquery` FTS eliminates ElasticSearch dependency; GIN indexes make FTS queries fast; JSONB stores classification scores. |

### NLP Stack

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| transformers | 5.2.0 | Zero-shot classification pipeline | Hugging Face Transformers v5 unifies tokenizer backends and is the standard access layer for HuggingFace models. Use `pipeline("zero-shot-classification")`. |
| torch (CPU) | 2.10.0 | Inference backend for transformers | CPU-only install (`torch --index-url .../cpu`) keeps image size manageable; DeBERTa-v3-base needs only ~420 MB RAM at inference. GPU not required for 100 articles/day. |
| MoritzLaurer/deberta-v3-base-zeroshot-v2.0 | n/a (HF model) | Zero-shot fact/opinion classifier | Outperforms facebook/bart-large-mnli by ~25% (f1_macro 0.619 vs 0.497 across 28 tasks). MIT licensed. 200M params, ~420 MB RAM at inference. Suitable for CPU-only production at this scale. |
| spaCy | 3.8.11 | Rule-based NLP preprocessing | Sentence boundary detection, POS tagging, and named entity recognition for the heuristic layer (hedging words, attribution patterns, subjective markers). Faster than NLTK for production text processing. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| feedparser | 6.0.12 | RSS/Atom feed parsing | Parsing all RSS and Atom feeds from BBC, Reuters, AP, NPR, Al Jazeera. Handles malformed feeds gracefully. |
| httpx | 0.28.1 | Async HTTP client | Fetching NewsAPI.org and any non-RSS public APIs. Use `httpx.AsyncClient` with connection pooling. Supports both sync and async; integrates cleanly with FastAPI's async context. |
| APScheduler | 3.11.2 | Background job scheduling | Runs the periodic feed-fetch + classify pipeline without requiring Redis/RabbitMQ. Use `AsyncIOScheduler` to run inside the FastAPI event loop. Sufficient for 100+ articles/day batch load. |
| pydantic-settings | 2.13.1 | Environment/config management | Reads `.env` and environment variables into typed `BaseSettings` classes; handles DATABASE_URL, NewsAPI key, scheduler interval. Standard FastAPI config pattern. |
| pytest | 9.0.2 | Testing framework | Standard Python test runner; `pytest-asyncio` extension handles async FastAPI endpoint and SQLAlchemy session tests. |
| pytest-asyncio | 0.25+ | Async test support | Required to run `async def` test functions against FastAPI's async routes and SQLAlchemy async sessions. |
| httpx (TestClient) | 0.28.1 | Integration test HTTP client | FastAPI's `TestClient` wraps httpx; use `AsyncClient` for async endpoint testing without running a live server. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uvicorn | ASGI server | FastAPI's official runtime server; use `uvicorn[standard]` for websocket and performance extras. Installed via `fastapi[standard]`. |
| python-multipart | Form data parsing | Required by FastAPI for form submissions (search bar POST). Install alongside FastAPI. |
| aiosqlite | SQLite async driver | Use only in test fixtures for an in-memory test DB; never in production (PostgreSQL only). |
| Docker + docker-compose | Containerization | Deployment target; `python:3.12-slim` base image; separate `migrate` container runs Alembic before the app starts; healthcheck on PostgreSQL before app launches. |
| pre-commit + ruff | Linting/formatting | `ruff` replaces flake8 + black + isort in a single fast Rust-based tool; run via pre-commit hooks. |

---

## Installation

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Core web framework
pip install "fastapi[standard]" pydantic-settings alembic

# Database
pip install sqlalchemy asyncpg

# NLP
pip install spacy transformers
# CPU-only PyTorch (smaller install, sufficient for 100 articles/day)
pip install torch --index-url https://download.pytorch.org/whl/cpu
# Download spaCy English model
python -m spacy download en_core_web_sm

# Feed fetching
pip install feedparser httpx apscheduler

# Dev / test
pip install pytest pytest-asyncio aiosqlite

# Download the zero-shot model (first run only — cached to ~/.cache/huggingface)
# Done at runtime via: pipeline("zero-shot-classification", model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0")
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| asyncpg | psycopg3 | If you need a single driver that supports both sync and async (e.g., using Alembic sync migrations alongside async app code). psycopg3 is ~5x slower on reads but simpler to configure for mixed sync/async. |
| APScheduler 3.x | Celery + Redis | When you need distributed task queues, multiple workers across machines, or retry logic with dead-letter queues. Celery is overkill for single-node 100 articles/day. |
| httpx | aiohttp | aiohttp is ~10-15% faster for pure high-concurrency scraping scenarios. Choose it if you need >1000 concurrent HTTP connections. Unnecessary here. |
| DeBERTa-v3-base-zeroshot-v2.0 | facebook/bart-large-mnli | If model download size is a hard constraint (<1 GB total). BART is larger but more widely cited. DeBERTa-v3-base is measurably more accurate. |
| DeBERTa-v3-base (200M) | DeBERTa-v3-large (400M) | If you have GPU inference and need the highest possible zero-shot accuracy. The large model scores 0.676 vs 0.619 f1_macro but requires ~800 MB RAM and ~2x inference time. |
| spaCy | NLTK | If you are primarily doing linguistic research and need maximum algorithm transparency. spaCy is 3-5x faster and better maintained for production pipelines. |
| PostgreSQL FTS | Elasticsearch | If you later need faceted search, fuzzy matching, or >10M documents. PostgreSQL FTS with GIN indexes is sufficient for v1 at 100 articles/day. |
| feedparser | atoma | feedparser handles more malformed feeds and has broader format support (RSS 0.9x through 2.0, Atom 0.3/1.0, CDF). atoma is type-safe but more brittle with edge-case feeds from real news sources. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| SQLAlchemy 1.x-style queries (`session.query(Model)`) | Legacy API; not compatible with async engine; will be removed in SQLAlchemy 3.0. Many tutorials still show this pattern — do not follow them. | SQLAlchemy 2.0 `select()` style with `async_session` |
| Pydantic v1 (`from pydantic import BaseSettings`) | FastAPI has deprecated Pydantic v1 support. `BaseSettings` moved to `pydantic-settings` package in v2. | `from pydantic_settings import BaseSettings` |
| APScheduler 4.x alpha | APScheduler 4.0.0a6 is in alpha with breaking API changes; 3.11.2 is the stable production version. | APScheduler 3.11.2 |
| transformers v4 | v5 (released Feb 2026) consolidates tokenizer backends and is the current release. v4 installations will pull an outdated package. | transformers 5.2.0 |
| SQLite in production | No concurrent write safety for multi-process FastAPI; no native full-text search with GIN indexes; no JSON operators. | PostgreSQL 16+ |
| `requests` library | Blocking/synchronous; will stall FastAPI's async event loop when called in route handlers or APScheduler async jobs. | httpx with `AsyncClient` |
| FastAPI background tasks for scheduling | `BackgroundTasks` in FastAPI runs tasks after a response is sent; it is not a scheduler and has no interval/cron support. | APScheduler `AsyncIOScheduler` |
| VADER for fact/opinion classification | VADER is a sentiment lexicon (positive/negative polarity), not a fact/opinion classifier. Conflating sentiment with objectivity is a critical domain error. | Rule-based heuristics (hedging/attribution patterns) + DeBERTa zero-shot |

---

## Stack Patterns by Variant

**If running on a machine with < 4 GB RAM:**
- Use `MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33` instead of base
- DeBERTa-v3-xsmall is ~50 MB vs 420 MB at inference
- Accuracy will drop but still outperforms pure rule-based approaches

**If article volume grows to 10,000+/day:**
- Add Celery + Redis as the task queue
- Keep APScheduler only for the trigger; push actual classification jobs to Celery workers
- Consider GPU inference (a single T4 GPU reduces DeBERTa-v3-base inference from ~200ms to ~15ms per sentence)

**If you need to run migrations safely in Docker:**
- Add a separate `migrate` service in docker-compose that runs `alembic upgrade head`
- Use `depends_on: migrate: condition: service_completed_successfully` on the app service
- Never run Alembic from inside the FastAPI startup event; fails under multiple replicas

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI 0.132.0 | Pydantic v2.x | Pydantic v1 support deprecated in FastAPI; will be removed. |
| SQLAlchemy 2.0.46 | asyncpg 0.31.0 | Use `postgresql+asyncpg://` scheme; `create_async_engine()` is the entry point. |
| SQLAlchemy 2.0.46 | Alembic 1.18.4 | Alembic 1.x supports async engines via `run_sync`; configure in `env.py`. |
| transformers 5.2.0 | torch 2.10.0 | Transformers v5 requires PyTorch 2.x; torch 2.10.0 is stable as of Jan 2026. |
| APScheduler 3.11.2 | FastAPI 0.132.0 | Use `AsyncIOScheduler`; start/shutdown in FastAPI lifespan context manager (`@asynccontextmanager`). |
| pytest 9.0.2 | pytest-asyncio 0.25+ | pytest-asyncio 0.25 requires explicit `asyncio_mode = "auto"` in `pytest.ini` or `pyproject.toml`. |

---

## Sources

- FastAPI releases: https://github.com/fastapi/fastapi/releases — confirmed version 0.132.0 (Feb 2025) HIGH confidence
- FastAPI PyPI: https://pypi.org/project/fastapi/ — version confirmed
- SQLAlchemy PyPI: https://pypi.org/project/SQLAlchemy/ — 2.0.46 stable, 2.1.0b1 pre-release (Jan 2026) HIGH confidence
- asyncpg PyPI: https://pypi.org/project/asyncpg/ — 0.31.0 (Nov 2025) HIGH confidence
- Alembic PyPI: https://pypi.org/project/alembic/ — 1.18.4 (Feb 2026) HIGH confidence
- transformers PyPI: https://pypi.org/project/transformers/ — 5.2.0 (Feb 2026) HIGH confidence
- torch PyPI: https://pypi.org/project/torch/ — 2.10.0 (Jan 2026) HIGH confidence
- spaCy PyPI: https://pypi.org/project/spacy/ — 3.8.11 (Nov 2025) HIGH confidence
- feedparser PyPI: https://pypi.org/project/feedparser/ — 6.0.12 (Sep 2025) HIGH confidence
- httpx PyPI: https://pypi.org/project/httpx/ — 0.28.1 stable; 1.0.dev3 pre-release (Sep 2025) HIGH confidence
- APScheduler PyPI: https://pypi.org/project/APScheduler/ — 3.11.2 stable (Dec 2025); 4.0.0a6 alpha HIGH confidence
- pydantic-settings PyPI: https://pypi.org/project/pydantic-settings/ — 2.13.1 (Feb 2026) HIGH confidence
- Pydantic releases: https://github.com/pydantic/pydantic/releases — v2.12.5 (Nov 2025) HIGH confidence
- Jinja2 PyPI: https://pypi.org/project/Jinja2/ — 3.1.6 (Mar 2025) HIGH confidence
- pytest PyPI: https://pypi.org/project/pytest/ — 9.0.2 (Dec 2025) HIGH confidence
- DeBERTa-v3-base-zeroshot-v2.0 model card: https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0 — f1_macro 0.619, 200M params, MIT license MEDIUM confidence (general NLI benchmark, not fact/opinion specific)
- asyncpg vs psycopg3 benchmark: https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/ — asyncpg 5x faster MEDIUM confidence
- APScheduler vs Celery: https://procodebase.com/article/mastering-background-tasks-and-scheduling-in-fastapi — architecture guidance MEDIUM confidence
- FastAPI + PostgreSQL Docker: https://fastapi.tiangolo.com/deployment/docker/ — official docs HIGH confidence
- SQLAlchemy FTS: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html — PostgreSQL dialect docs HIGH confidence

---

*Stack research for: FactFeed — news aggregator with NLP fact/opinion classification*
*Researched: 2026-02-23*
