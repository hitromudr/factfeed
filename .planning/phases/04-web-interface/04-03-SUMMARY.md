---
phase: 04-web-interface
plan: 03
status: complete
started: 2026-02-24
completed: 2026-02-24
---

# Summary: Article Detail with Sentence Highlighting

## What was built
Article detail page at `/article/{id}` with inline sentence highlighting (green=fact, red=opinion, yellow=mixed/unclear), CSS tooltips showing High/Medium/Low confidence levels, and collapsible opinion sections using native HTML `<details>/<summary>` elements. Articles without classification show body text with "Classification pending" note.

## Key files

### Modified
- `factfeed/web/routes/article.py` — Article route with eager-loaded sentences, non_opinion/opinion split, HTTPException 404
- `factfeed/templates/article.html` — Inline highlighting with confidence tooltips, collapsible opinion section

## Decisions
- Confidence thresholds: >= 0.7 High, >= 0.4 Medium, < 0.4 Low (aligned with plan spec)
- Used HTTPException(404) instead of custom HTML error page for consistency with FastAPI conventions
- Native HTML `<details>` element for collapse/expand — no JavaScript needed, fully accessible
- Unclassified articles (no sentences) show plain body text with "Classification pending" note

## Self-Check: PASSED
- article.html contains `opinion-section` class
- selectinload used for both Article.source and Article.sentences
- Confidence shown as High/Medium/Low text, never raw decimal
- Opinion section uses `<details>` without `open` attribute (collapsed by default)
