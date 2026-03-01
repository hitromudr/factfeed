# Roadmap: FactFeed

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-02-25)
- ✅ **v1.1 API & UI** — Phase 6 (shipped 2026-02-25)
- ✅ **v1.2 Localization** — Phase 7 (shipped 2026-03-01)
- ✅ **v1.3 Redesign & Translation** — Phases 8-9 (shipped 2026-03-01)
- ✅ **v1.4 Global Coverage** — Phase 10 (shipped 2026-03-01)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-02-25</summary>

- [x] Phase 1: Database Foundation (3/3 plans) — completed 2026-02-23
- [x] Phase 2: Ingestion Pipeline (4/4 plans) — completed 2026-02-23
- [x] Phase 3: NLP Classification Pipeline (4/4 plans) — completed 2026-02-23
- [x] Phase 4: Web Interface (4/4 plans) — completed 2026-02-24
- [x] Phase 5: Polish and Hardening (2/2 plans) — completed 2026-02-25

</details>

### Phase 6: API & UI Polish

**Goal:** Create a public API and improve frontend UX
**Depends on:** Phase 5
**Plans:** 2 plans

Plans:
- [x] Plan 6.1: REST API Implementation
- [x] Plan 6.2: Frontend UX Overhaul

### Phase 7: Localization

**Goal:** Support multiple languages (starting with Russian)
**Depends on:** Phase 6
**Plans:** 1 plan

Plans:
- [x] Plan 7.1: Implement i18n with Babel and Russian translation

### Phase 8: UI Redesign & Localization Widget

**Goal:** Professionalize the UI and add language switching
**Depends on:** Phase 7
**Plans:** 1 plan

Plans:
- [x] Plan 8.1: UI Refinement and Language Switcher

### Phase 9: Content Auto-Translation

**Goal:** Translate article content on the fly
**Depends on:** Phase 8
**Plans:** 1 plan

Plans:
- [x] Plan 9.1: Integrate translation service

### Phase 10: Global News Sources & Multilingual NLP

**Goal:** Expand ingestion to top global sources and upgrade NLP model for non-English texts.
**Depends on:** Phase 9
**Plans:** 2 plans

Plans:
- [x] Plan 10.1: Replace DeBERTa with `mDeBERTa-v3` for multilingual Zero-Shot classification.
- [x] Plan 10.2: Add 10+ new international RSS feeds (Guardian, DW, El País, Meduza, NHK) to `sources.py`.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Database Foundation | v1.0 | 3/3 | Complete | 2026-02-23 |
| 2. Ingestion Pipeline | v1.0 | 4/4 | Complete | 2026-02-23 |
| 3. NLP Classification Pipeline | v1.0 | 4/4 | Complete | 2026-02-23 |
| 4. Web Interface | v1.0 | 4/4 | Complete | 2026-02-24 |
| 5. Polish and Hardening | v1.0 | 2/2 | Complete | 2026-02-25 |
| 6. API & UI Polish | v1.1 | 2/2 | Complete | 2026-02-25 |
| 7. Localization | v1.2 | 1/1 | Complete | 2026-03-01 |
| 8. UI Redesign & Widget | v1.3 | 1/1 | Complete | 2026-03-01 |
| 9. Content Translation | v1.3 | 1/1 | Complete | 2026-03-01 |
| 10. Global Coverage | v1.4 | 2/2 | Complete | 2026-03-01 |