# FactFeed

## What This Is

A news aggregator and search engine that separates factual content from opinions. FactFeed fetches articles from 5 RSS sources (BBC, Reuters, AP News, NPR, Al Jazeera), classifies every sentence as fact, opinion, mixed, or unclear using hybrid NLP (spaCy + DeBERTa zero-shot), and presents results in a searchable web interface with inline color-coded highlighting and collapsible opinion sections. Shipped as v1.0.

## Core Value

Users can search and read news with clear, confidence-scored separation of facts from opinions — enabling them to form their own views from verified, objective content.

## Requirements

### Validated

- ✓ Fetch articles from 5 RSS sources on a scheduled background job — v1.0
- ✓ Classify sentences as fact/opinion/mixed/unclear with hybrid NLP (rules + zero-shot) — v1.0
- ✓ Confidence scores (0.0–1.0) on every classified sentence — v1.0
- ✓ Flag ambiguous content as "unclear" with low confidence — v1.0
- ✓ Store articles and per-sentence classifications in PostgreSQL with FTS — v1.0
- ✓ Full-text search with source, date, and fact-density filters — v1.0
- ✓ Web UI with search bar, article list, and article detail viewer — v1.0
- ✓ Color-coded inline highlighting (green=fact, red=opinion, yellow=mixed) with confidence tooltips — v1.0
- ✓ Collapsible opinion sections (default collapsed) — v1.0
- ✓ Server-rendered Jinja2 templates via FastAPI — v1.0
- ✓ Graceful error handling for rate limits, invalid sources, fetch failures — v1.0
- ✓ No user data collection, no login required — v1.0
- ✓ Classifier accuracy 80%+ on evaluation dataset — v1.0
- ✓ Automated API tests + UAT on 10 articles — v1.0
- ✓ Rate limiting on search endpoint (30/min per IP) — v1.0
- ✓ Multi-worker APScheduler safety verified — v1.0

### Active

(None — next milestone needed)

### Out of Scope

- User accounts and authentication — no login needed; privacy-first design
- User feedback loop for misclassification corrections — v2
- Multi-language support — English only
- Email/push notifications — v2
- Visualization/charts of source bias — v2
- Mobile native app — web-first responsive design sufficient
- Real-time streaming — scheduled batch processing sufficient
- Paid APIs — free/open-source tools only
- Automated claim verification (true/false) — different product; FactFeed classifies verifiability, not veracity
- Source bias ratings computed by FactFeed — use established third-party ratings instead

## Context

Shipped v1.0 with ~4,000 lines of Python across 5 phases in 3 days.

**Tech stack:** Python 3.12, FastAPI, PostgreSQL 16, SQLAlchemy 2.0, Alembic, spaCy (en_core_web_sm), DeBERTa-v3-base-zeroshot-v2.0, APScheduler, trafilatura, HTMX, Jinja2.

**Architecture:** Monolithic FastAPI app with background scheduler. Articles flow through: RSS fetch → dedup → persist → NLP classify → sentences table → web display. Full-text search via PostgreSQL tsvector/GIN.

**Known tech debt (from v1.0 audit):**
- TemperatureScaler built but never instantiated — confidence calibration bypassed
- Source-level satire detection bypassed in batch classification
- No CSS @media breakpoints — responsive layout via flexbox only
- Jinja2Templates uses relative directory path

## Constraints

- **Budget**: Free/open-source tools only; no paid APIs
- **Ethics**: Only fetch from public RSS feeds; robots.txt respected
- **Tech stack**: Python (FastAPI), PostgreSQL (storage + FTS), Jinja2 (server-rendered UI)
- **Performance**: Handles 100+ articles/day ingestion and classification
- **Git**: Atomic commits per task

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid NLP (rules + zero-shot) | Rules are fast for obvious cases; zero-shot handles ambiguity without training data | ✓ Good — 80%+ accuracy achieved |
| DeBERTa-v3-base-zeroshot-v2.0 over BART-large-mnli | ~25% F1 improvement in benchmarks | ✓ Good — reliable zero-shot classification |
| PostgreSQL FTS over ElasticSearch | Simpler infrastructure for v1; GIN index built into PostgreSQL | ✓ Good — fast search with no extra services |
| FastAPI + Jinja2 over React SPA | Keep entire stack in Python; no separate frontend build step | ✓ Good — shipped in 3 days |
| Scheduled background fetching (APScheduler) | Consistent article flow without manual intervention | ✓ Good — 15-min intervals, max_instances=1 |
| Color-coded highlights + confidence tooltips | Both visual and numerical confidence display | ✓ Good — clear UX |
| Sentences as child table (not JSON blob) | Required for per-sentence querying, FTS, and fact-density sort | ✓ Good — enables correlated subqueries |
| HTMX for search interactivity | No JS framework needed; progressive enhancement | ✓ Good — live search with minimal code |
| slowapi for rate limiting | De-facto standard for FastAPI; per-IP, no auth needed | ✓ Good — simple 30/min on search |
| trafilatura for article extraction | Best open-source HTML-to-text with partial fallback | ✓ Good — handles diverse news sites |

---
*Last updated: 2026-02-25 after v1.0 milestone*
