# Requirements: FactFeed

**Defined:** 2026-02-23
**Core Value:** Users can search and read news with clear, confidence-scored separation of facts from opinions

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingestion

- [ ] **INGEST-01**: System fetches articles from 5 RSS sources (BBC, Reuters, AP, NPR, Al Jazeera) on a scheduled background job
- [ ] **INGEST-02**: System handles API rate limits, invalid sources, and fetch failures gracefully without crashing
- [ ] **INGEST-03**: System deduplicates articles by URL to prevent re-processing
- [ ] **INGEST-04**: System extracts article body text from fetched content for NLP processing

### NLP Classification

- [ ] **NLP-01**: System classifies each sentence as fact, opinion, mixed, or unclear using hybrid NLP (rule-based heuristics + zero-shot transformer)
- [ ] **NLP-02**: System assigns confidence score (0.0–1.0) to each classified sentence
- [ ] **NLP-03**: System flags ambiguous content (quotes, satire, breaking news without context) as "unclear" with low confidence
- [ ] **NLP-04**: System detects attributed speech patterns ("The CEO said X") and routes them through an attribution pre-filter before transformer classification
- [ ] **NLP-05**: System stores classification results as structured data (sentences child table, not JSON blob) for per-sentence querying

### Search & Filtering

- [ ] **SEARCH-01**: User can search articles by keyword using full-text search (PostgreSQL FTS with GIN index)
- [ ] **SEARCH-02**: User can filter search results by news source
- [ ] **SEARCH-03**: User can filter search results by date/recency (last 24h, 7 days, 30 days)
- [ ] **SEARCH-04**: Search results default to "facts first" ordering (by fact-density ratio) with toggle to recency

### Web Interface

- [ ] **UI-01**: User sees article list with headline, source, date, and brief excerpt
- [ ] **UI-02**: User can click an article to view full content with inline highlighting
- [ ] **UI-03**: Article viewer shows color-coded inline highlighting: green=fact, red=opinion, yellow=mixed/unclear
- [ ] **UI-04**: User can hover over highlighted sentences to see confidence score (0.0–1.0)
- [ ] **UI-05**: Opinion sections are collapsible (default collapsed) with "Show opinion content" expand control
- [ ] **UI-06**: Web interface is responsive and usable on mobile viewports

### Infrastructure

- [ ] **INFRA-01**: PostgreSQL database stores articles and per-sentence classification data
- [ ] **INFRA-02**: FastAPI backend serves web interface via Jinja2 server-rendered templates
- [ ] **INFRA-03**: Background scheduler (APScheduler) runs ingestion job on configurable interval
- [ ] **INFRA-04**: No user data collection; no login or accounts required
- [ ] **INFRA-05**: Unit tests for classifier accuracy (target 80%+ on evaluation dataset)
- [ ] **INFRA-06**: Automated API response tests and manual UAT on 10 articles

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhancements

- **ENH-01**: User feedback loop for marking misclassifications to improve model
- **ENH-02**: Multi-language support (Russian and others beyond English)
- **ENH-03**: Daily fact summary notifications via email or push
- **ENH-04**: Visualization charts showing opinion bias per source over time
- **ENH-05**: Topic/category browsing with topic classification NLP pass
- **ENH-06**: Source coverage breadth indicator (how many sources covered a story)
- **ENH-07**: Static MBFC/AllSides source credibility badges in article viewer
- **ENH-08**: NewsAPI.org supplemental feed integration
- **ENH-09**: Paywall content handling (excerpt + link + "paywall" label)

## Out of Scope

| Feature | Reason |
|---------|--------|
| User accounts and authentication | No login needed for v1; privacy-first design |
| Personalized/algorithmic feed | Creates filter bubbles; contradicts "no bias" mission |
| Real-time article streaming | Scheduled batch processing sufficient for 100+ articles/day |
| Automated claim verification (true/false) | Different product; FactFeed classifies verifiability, not veracity |
| Source bias ratings computed by FactFeed | Use established third-party ratings (MBFC/AllSides) instead |
| Social features (comments, sharing) | Requires moderation infrastructure; out of scope |
| Mobile native app | Web-first responsive design sufficient |
| Paid APIs | Budget constraint: free/open-source tools only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 2 | Pending |
| INGEST-02 | Phase 2 | Pending |
| INGEST-03 | Phase 2 | Pending |
| INGEST-04 | Phase 2 | Pending |
| NLP-01 | Phase 3 | Pending |
| NLP-02 | Phase 3 | Pending |
| NLP-03 | Phase 3 | Pending |
| NLP-04 | Phase 3 | Pending |
| NLP-05 | Phase 3 | Pending |
| SEARCH-01 | Phase 4 | Pending |
| SEARCH-02 | Phase 4 | Pending |
| SEARCH-03 | Phase 4 | Pending |
| SEARCH-04 | Phase 4 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| UI-06 | Phase 4 | Pending |
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 4 | Pending |
| INFRA-03 | Phase 2 | Pending |
| INFRA-04 | Phase 4 | Pending |
| INFRA-05 | Phase 5 | Pending |
| INFRA-06 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-23 after roadmap creation — all 25 requirements mapped*
