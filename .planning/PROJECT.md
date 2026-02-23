# FactFeed

## What This Is

A news aggregator and search engine that separates factual content from opinions. FactFeed fetches articles from multiple sources, analyzes them with NLP to classify sentences as fact, opinion, or mixed, and presents results in a searchable web interface where facts are prioritized and opinions are clearly marked. Built for users who want news without bias.

## Core Value

Users can search and read news with clear, confidence-scored separation of facts from opinions — enabling them to form their own views from verified, objective content.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Fetch articles from 5+ news sources via RSS feeds and public APIs on a scheduled background job
- [ ] Classify sentences/paragraphs as fact (objective, verifiable), opinion (subjective, biased), or mixed using hybrid NLP (rule-based heuristics + zero-shot transformer model)
- [ ] Output structured JSON with tagged sections and confidence scores (0.0-1.0)
- [ ] Flag ambiguous content (quotes, satire, breaking news without context) as "unclear" with low confidence
- [ ] Store processed articles in PostgreSQL with full-text search indexing (FTS)
- [ ] Full-text search over facts database with filters: keyword, date, source, topic
- [ ] Web UI with search bar, results list (facts first, opinions collapsible), and article viewer
- [ ] Color-coded inline highlighting: green=fact, red=opinion, yellow=mixed, with confidence scores on hover
- [ ] Server-rendered Jinja2 templates via FastAPI (no separate frontend build)
- [ ] Handle API rate limits, invalid sources, and analysis failures gracefully
- [ ] No user data collection beyond optional local search history
- [ ] Unit tests for classifier accuracy (target 80%+ on sample datasets)
- [ ] Manual UAT on 10 articles; automated tests for API responses

### Out of Scope

- User accounts and authentication — no login needed for v1
- User feedback loop for misclassification corrections — v2
- Multi-language support — English only for v1
- Email/push notifications — v2
- Visualization/charts of source bias — v2
- Mobile app — web-first, responsive design sufficient
- OAuth or social login — not needed without accounts
- Real-time streaming of articles — scheduled batch processing is sufficient
- Paid APIs — free/open-source tools only

## Context

- Target sources for v1: BBC, Reuters, AP News, NPR, Al Jazeera (via RSS/public APIs)
- NewsAPI.org free tier as supplemental source (limited to 100 requests/day)
- NLP approach: Rule-based heuristics catch obvious cases (hedging words, subjective markers, attribution patterns), zero-shot transformer handles ambiguous content
- Zero-shot model candidates: DeBERTa-v3-base-mnli-fever-anli or facebook/bart-large-mnli (research needed for best fit)
- Performance target: handle 100+ articles/day ingestion and classification
- Deployment: local development first, then Docker for production

## Constraints

- **Budget**: Free/open-source tools only; no paid APIs (fallback to open RSS feeds)
- **Ethics**: Only fetch from public APIs and RSS feeds; no scraping without permission
- **Tech stack**: Python (FastAPI backend), PostgreSQL (storage + FTS), Jinja2 (server-rendered UI)
- **Performance**: Must handle 100+ articles/day; optimize templates for mobile viewports
- **Git**: Atomic commits per task

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid NLP (rules + zero-shot) | Rules are fast for obvious cases; zero-shot handles ambiguity without training data | — Pending |
| PostgreSQL FTS over ElasticSearch | Simpler infrastructure for v1; FTS5-equivalent built into PostgreSQL | — Pending |
| FastAPI + Jinja2 over React SPA | Keep entire stack in Python; no separate frontend build step; faster to ship | — Pending |
| Scheduled background fetching | Consistent article flow without manual intervention; cron-like job | — Pending |
| Color-coded highlights + scores | Both visual and numerical confidence display; colors for quick scanning, scores for detail | — Pending |

---
*Last updated: 2026-02-23 after initialization*
