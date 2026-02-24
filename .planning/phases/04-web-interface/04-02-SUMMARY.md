---
phase: 04-web-interface
plan: 02
status: complete
started: 2026-02-24
completed: 2026-02-24
---

# Summary: Search Page with FTS, Filters, and Sort

## What was built
Complete search page with PostgreSQL full-text search via `plainto_tsquery`, composable source and date range filters, fact-density and recency sort ordering, and HTMX-powered live search that updates results without page reload. All filter controls preserve state across interactions via `hx-include`.

## Key files

### Created
- `factfeed/templates/search.html` — Search page with HTMX live search, filter dropdowns, sort toggles
- `factfeed/templates/_results.html` — HTMX partial for article result cards

### Modified
- `factfeed/web/routes/search.py` — Full FTS query with source, date, sort filters, fact-density subquery

## Decisions
- Used `plainto_tsquery` (not `to_tsquery`) for safe user input handling
- Fact-density sort uses correlated scalar subquery (count facts / total sentences) with `nullslast()` for unclassified articles
- All HTMX controls include all other filter params via `hx-include` to prevent state loss
- `hx-push-url="true"` on all controls for bookmarkable filter state

## Self-Check: PASSED
- `search_articles` function exports correctly
- search.html contains `hx-get` attributes
- `_results.html` contains `article-card` class
- FTS uses `plainto_tsquery`, not string interpolation
- `selectinload(Article.source)` prevents lazy-load in templates
