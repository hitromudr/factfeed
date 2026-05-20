# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**The Sorter (Сортировочная)** — news aggregator that classifies every sentence as fact/opinion/mixed/unclear using hybrid NLP (spaCy segmentation + mDeBERTa-v3 zero-shot classification with temperature-scaled confidence). Fetches from 14+ global RSS sources, stores in PostgreSQL with full-text search (GIN index on tsvector), serves via FastAPI + Jinja2/HTMX with auto-translation (EN→RU).

## Language

Отвечай по-русски. Technical terms and code identifiers remain in English.

## Commands

### Development

```bash
make install          # uv sync
make dev              # uvicorn on :8000 with hot reload (uses Docker Postgres on :5433)
make test             # creates test DB automatically, runs pytest
make lint             # ruff check
make format           # ruff check --fix + ruff format
```

### Single test

```bash
DATABASE_URL=postgresql+asyncpg://factfeed:factfeed@localhost:5433/factfeed_test \
TEST_DATABASE_URL=postgresql+asyncpg://factfeed:factfeed@localhost:5433/factfeed_test \
uv run pytest tests/nlp/test_classifier.py -x
```

### Test markers

- `slow` — loads real transformer model; excluded by default
- `uat` — requires seeded database; excluded by default
- Run with: `uv run pytest -m slow` or `uv run pytest -m uat`

### Docker & Database

```bash
make up / make start  # docker-compose up -d --build
make stop / make down # stop / remove containers
make logs             # follow logs
make migrate          # alembic upgrade head (against Docker Postgres on :5433)
make revision         # create new alembic migration (interactive)
make reset            # drop volumes + rebuild (destructive)
make db-shell         # psql into factfeed DB
```

### i18n (Babel)

```bash
make i18n-extract     # extract to .pot
make i18n-update      # update .po files
make i18n-compile     # compile .mo files
```

## Network & Ports

System proxy is configured. For local service calls, bypass it:

```bash
no_proxy='*' curl http://localhost:8002/
```

- `make dev` → localhost:8000 (host, hot reload)
- Docker app container → localhost:8002 (`network_mode: host`, NVIDIA GPU passthrough)
- Docker Postgres → localhost:5433 (mapped from container 5432)

## Architecture

Monolithic FastAPI app with background schedulers (APScheduler). Data flow:

```
RSS feeds → fetcher (curl_cffi + proxy rotation) → extractor (trafilatura)
  → deduplicator (url_hash) → Article table
  → segmenter (spaCy) → pre_filter (regex rules) → classifier (mDeBERTa zero-shot)
  → calibrator (TemperatureScaler) → Sentence table
  → translator (deep-translator, cached in Translation table)
  → Web UI (Jinja2 + HTMX) / REST API (/api/v1/)
```

### Key architectural decisions

- **Lifespan** (`factfeed/web/main.py`): app startup initializes APScheduler for periodic ingestion, loads spaCy/transformer models, creates shared httpx client. All of this is disabled in tests via `tests/conftest.py`.
- **NLP pipeline** (`factfeed/nlp/pipeline.py`): orchestrates segment → pre_filter → classify → calibrate. The classifier (`factfeed/nlp/classifier.py`) uses zero-shot mDeBERTa-v3 with dynamic batch sizes (GPU: 100, CPU: 5, configurable via `NLP_BATCH_SIZE_GPU`/`NLP_BATCH_SIZE_CPU`).
- **Session management**: `factfeed/db/session.py` exports `AsyncSessionLocal` factory; `factfeed/web/deps.py` provides `get_db` FastAPI dependency. Tests monkey-patch both to use a rollback-isolated session.
- **Translation**: cached per-article in `translations` table as JSON (`sentences_data`), keyed by `(article_id, language)`.
- **System monitor** (`factfeed/services/system_monitor.py`): in-memory singleton tracking pipeline status — not persisted.

### Useful env vars (`factfeed/config.py`)

- `NLP_ENABLED=false` — disable ML classification for fast dev/test cycles
- `NLP_CALIBRATION_TEMPERATURE` — temperature scaling factor (default: 2.0)
- `INGEST_INTERVAL_MINUTES` — ingestion scheduler period (default: 15)
- `DEBUG=true` — enable debug mode

### Database Schema (PostgreSQL 16)

- `sources` — RSS feed definitions (name, feed_url, country_code, region, language)
- `articles` — fetched articles (url_hash unique, body, search_vector GIN index)
- `sentences` — per-sentence NLP results (article_id, position, label, confidence); unique on (article_id, position)
- `translations` — cached translations (article_id, language, sentences_data JSON)

### Test Infrastructure

- Tests use a separate `factfeed_test` database (auto-created by `make test`)
- `tests/conftest.py` disables FastAPI lifespan and background tasks
- Each test gets a fresh session with rollback isolation
- `asyncio_mode = auto` — all async tests run automatically
- `pytest-asyncio` fixtures: `engine`, `db_session`, `client` (httpx AsyncClient)

## GSD Framework

The `.claude/get-shit-done/` directory contains the GSD project orchestration framework. Key commands:

- `/gsd:progress` — check project status and route to next action
- `/gsd:plan-phase <N>` — research and plan a phase
- `/gsd:execute-phase <N>` — execute a planned phase
- `/gsd:verify-work` — verify completed work
- `/gsd:resume-work` — resume from previous session
- `/gsd:debug` — systematic debugging

Planning artifacts live in `.planning/` (ROADMAP.md, STATE.md, phase-N/ directories).
