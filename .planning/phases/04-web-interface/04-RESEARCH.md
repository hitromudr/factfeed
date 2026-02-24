# Phase 4: Web Interface - Research

**Researched:** 2026-02-24
**Domain:** Server-rendered web UI (FastAPI + Jinja2 + HTMX) with PostgreSQL FTS
**Confidence:** HIGH (core stack already decided and partially wired; patterns verified against official docs and FastAPI/HTMX documentation)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-01 | User sees article list with headline, source, date, and brief excerpt | Search route returns Article queryset with source join; Jinja2 template renders list; excerpt derived from `body[:200]` or stored summary |
| UI-02 | User can click an article to view full content with inline highlighting | Article detail route queries Article + Sentences ordered by position; Jinja2 template loops sentences applying label CSS classes |
| UI-03 | Article viewer shows color-coded inline highlighting: green=fact, red=opinion, yellow=mixed/unclear | CSS classes `.fact`, `.opinion`, `.mixed`, `.unclear` driven by `sentence.label`; applied in Jinja2 loop |
| UI-04 | User can hover over highlighted sentences to see confidence score as High/Medium/Low | `data-confidence` attribute on `<span>` elements; CSS tooltip shows mapped label (>=0.7 High, 0.4-0.69 Medium, <0.4 Low); no raw decimal shown |
| UI-05 | Opinion sentences are collapsed by default behind "Show opinion content" control | HTML `<details>`/`<summary>` tags for each opinion group, or CSS `display:none` with HTMX toggle; default collapsed without JS |
| UI-06 | Web interface is responsive and usable on mobile without horizontal scrolling | Mobile-first CSS with `max-width`, `flexbox`/`grid`, no fixed widths; `<meta name="viewport">` in base template |
| SEARCH-01 | User can search articles by keyword using PostgreSQL FTS with GIN index | `search_vector.match(q)` or `func.plainto_tsquery` with `@@` operator against existing `search_vector` tsvector column |
| SEARCH-02 | User can filter search results by news source | `Article.source_id == source_id` WHERE clause; source list populated from `sources` table |
| SEARCH-03 | User can filter search results by date/recency (last 24h, 7 days, 30 days) | `Article.published_at >= datetime.now() - timedelta(days=N)` WHERE clause; `from_` query param maps to timedelta |
| SEARCH-04 | Search results default to fact-density ordering with toggle to recency | Subquery JOIN on `sentences` table computes fact_count/total_count per article; toggle switches to `published_at DESC` |
| INFRA-02 | FastAPI backend serves web interface via Jinja2 server-rendered templates | `Jinja2Templates` + `StaticFiles` mount in existing `main.py`; `TemplateResponse` in web routes |
| INFRA-04 | No user data collection; no login or accounts required | No auth middleware; no session cookies; no analytics JS; state lives in URL query params only |
</phase_requirements>

---

## Summary

Phase 4 builds the entire user-facing web layer on top of a fully classified article database. The existing `factfeed/web/` module stub and the complete data model (Article, Sentence, Source) are ready. No schema changes are needed — this phase is pure web layer work.

The pre-decided stack (FastAPI + Jinja2 + HTMX + PostgreSQL FTS) is well-matched to all requirements. Jinja2 renders complete HTML server-side, HTMX handles search interactivity without page reloads, and vanilla CSS handles highlighting, tooltips, and mobile responsiveness. No frontend build pipeline, no React, no node_modules.

The most technically nuanced tasks are: (1) computing a fact-density ratio subquery for ordering, (2) building a composable SQLAlchemy query that combines FTS + source filter + date filter + sort order correctly, and (3) rendering inline sentence highlights with collapsible opinion sections using only HTML/CSS primitives.

**Primary recommendation:** Build web routes and templates first with a working FTS query (no ratio ordering yet), then layer in the fact-density subquery sort, then add HTMX interactivity for the search bar. This minimizes complexity at each stage.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.132.0 | Route handling, dependency injection, static file serving | Already installed; `TemplateResponse` is the FastAPI SSR primitive |
| Jinja2 | 3.1.6 | Server-side HTML templating | Already installed; FastAPI's official template engine |
| HTMX | 2.0.8 | Partial page updates without JavaScript | CDN-loaded (14KB); enables search-as-you-type and sort toggle without SPA overhead |
| SQLAlchemy | 2.0.46 | Async ORM queries, FTS via func namespace | Already installed; `func.plainto_tsquery`, `func.ts_rank`, subquery pattern for fact ratio |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Already installed; powers async SQLAlchemy engine |
| pydantic-settings | 2.13.1 | Typed query parameter models | Already installed; `Annotated[FilterParams, Query()]` pattern for search params |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python-multipart | bundled with fastapi[standard] | Form submission parsing | If search bar uses POST form; not needed for GET params |
| StaticFiles (Starlette) | bundled with FastAPI | Serve CSS, JS assets | Mount at `/static` in `main.py` |

### No New Installs Required

All required libraries are already in `pyproject.toml`. Phase 4 adds no new Python dependencies. HTMX is loaded from CDN in the base template (no npm).

**HTMX CDN tag:**
```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>
```

---

## Architecture Patterns

### Recommended Project Structure (additions for Phase 4)

```
factfeed/
├── web/
│   ├── __init__.py          # exists (empty)
│   ├── main.py              # exists (stub) — will be expanded with mounts
│   ├── routes/
│   │   ├── __init__.py      # new
│   │   ├── search.py        # new — GET / and GET /search
│   │   └── article.py       # new — GET /article/{id}
│   └── deps.py              # new — async DB session dependency
├── templates/
│   ├── base.html            # new — shared layout, nav, HTMX script
│   ├── search.html          # new — search bar + article list
│   ├── _results.html        # new — partial for HTMX swap
│   └── article.html         # new — article body with highlights
└── static/
    ├── style.css            # new — .fact, .opinion, .mixed, .unclear + tooltips + mobile
    └── (no app.js needed — HTMX handles interactions)
```

### Pattern 1: Jinja2 Template Setup in FastAPI

**What:** Mount `Jinja2Templates` and `StaticFiles` on app startup. Add both to the existing `main.py`.

```python
# factfeed/web/main.py (expanded)
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # factfeed/

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In app factory or main.py
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
```

**Template route pattern:**
```python
# factfeed/web/routes/search.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def search_page(request: Request, q: str = "", ...):
    results = await run_search(q, ...)
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={"results": results, "query": q},
    )
```

### Pattern 2: Typed Query Parameters with Pydantic (FastAPI 0.115.0+)

**What:** Group search params into a Pydantic model, use `Annotated[Model, Query()]` to auto-validate.

```python
from typing import Annotated, Literal
from pydantic import BaseModel
from fastapi import Query

class SearchParams(BaseModel):
    q: str = ""
    source: int | None = None          # source_id
    from_: Literal["24h", "7d", "30d"] | None = None
    sort: Literal["relevance", "recency", "facts"] = "facts"

@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    params: Annotated[SearchParams, Query()],
    session: AsyncSession = Depends(get_db),
):
    ...
```

### Pattern 3: Composable PostgreSQL FTS Query

**What:** Build a SQLAlchemy 2.0 `select()` that combines FTS, source filter, date filter, and sorting. Use `func` namespace for PostgreSQL-specific functions.

```python
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import TSVECTOR
from datetime import datetime, timedelta
from factfeed.db.models import Article, Sentence, Source

async def search_articles(session, params: SearchParams) -> list[Article]:
    # Base search condition
    query = func.plainto_tsquery("english", params.q)
    stmt = select(Article).join(Article.source)

    if params.q:
        stmt = stmt.where(
            Article.search_vector.bool_op("@@")(query)
        )

    if params.source:
        stmt = stmt.where(Article.source_id == params.source)

    if params.from_:
        delta = {"24h": 1, "7d": 7, "30d": 30}[params.from_]
        cutoff = datetime.utcnow() - timedelta(days=delta)
        stmt = stmt.where(Article.published_at >= cutoff)

    # Ordering
    if params.sort == "recency":
        stmt = stmt.order_by(Article.published_at.desc())
    elif params.sort == "relevance" and params.q:
        stmt = stmt.order_by(
            func.ts_rank(Article.search_vector, query).desc()
        )
    else:  # "facts" — default
        # Subquery: fact_count / total_sentence_count per article
        fact_ratio_sq = (
            select(
                Sentence.article_id,
                (
                    func.count(Sentence.id).filter(Sentence.label == "fact").cast(Float)
                    / func.nullif(func.count(Sentence.id), 0)
                ).label("fact_ratio"),
            )
            .group_by(Sentence.article_id)
            .subquery()
        )
        stmt = (
            stmt.outerjoin(fact_ratio_sq, Article.id == fact_ratio_sq.c.article_id)
            .order_by(fact_ratio_sq.c.fact_ratio.desc().nullslast())
        )

    result = await session.execute(stmt.limit(50))
    return result.scalars().all()
```

**Key note:** `func.count().filter()` is the SQL `COUNT(*) FILTER (WHERE ...)` clause, supported in PostgreSQL and by SQLAlchemy 2.0. Produces a single-pass aggregate without needing a subquery per label.

### Pattern 4: HTMX Active Search (Debounced)

**What:** Search input triggers server-side render of results partial on keyup with debounce. No JavaScript required beyond loading HTMX from CDN.

```html
<!-- templates/search.html (search bar portion) -->
<input
  type="text"
  name="q"
  value="{{ query }}"
  hx-get="/search"
  hx-target="#results"
  hx-swap="innerHTML"
  hx-trigger="keyup changed delay:400ms, search"
  hx-include="[name='source'],[name='from_'],[name='sort']"
  hx-push-url="true"
  placeholder="Search articles..."
/>
<div id="results">
  {% include "_results.html" %}
</div>
```

**Route returns partial on HTMX request:**
```python
@router.get("/search", response_class=HTMLResponse)
async def search(request: Request, params: Annotated[SearchParams, Query()], ...):
    results = await search_articles(session, params)
    # HTMX sends HX-Request: true header for partial updates
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="_results.html", context={"results": results}
        )
    return templates.TemplateResponse(
        request=request, name="search.html", context={"results": results, "params": params}
    )
```

### Pattern 5: Sort Toggle with Hidden Fields

**What:** Sort toggle button submits the search form with updated `sort` param. Use `hx-vals` to override the sort value without JavaScript-heavy state management.

```html
<!-- Sort toggle buttons -->
<button hx-get="/search"
        hx-vals='{"sort": "facts"}'
        hx-include="[name='q'],[name='source'],[name='from_']"
        hx-target="#results"
        hx-swap="innerHTML"
        hx-push-url="true">
  Facts First
</button>
<button hx-get="/search"
        hx-vals='{"sort": "recency"}'
        hx-include="[name='q'],[name='source'],[name='from_']"
        hx-target="#results"
        hx-swap="innerHTML"
        hx-push-url="true">
  Most Recent
</button>
```

### Pattern 6: Inline Sentence Highlighting

**What:** Jinja2 loop over sentences applies CSS class based on `sentence.label`. `data-confidence` attribute stores raw float (0.0-1.0) for tooltip display, but tooltip text shows High/Medium/Low (not decimal).

```html
<!-- templates/article.html (sentence rendering) -->
{% for sentence in sentences %}
  {% if sentence.label == "opinion" %}
    {# Opinion: inside collapsible section — handled by Pattern 7 #}
  {% else %}
    <span
      class="sentence {{ sentence.label }}"
      data-confidence="{{ sentence.confidence }}"
      title="{% if sentence.confidence >= 0.7 %}High{% elif sentence.confidence >= 0.4 %}Medium{% else %}Low{% endif %} confidence"
    >{{ sentence.text }}</span>
  {% endif %}
{% endfor %}
```

**CSS for highlighting and tooltip:**
```css
/* static/style.css */
.sentence { border-radius: 3px; padding: 0 2px; cursor: default; position: relative; }
.fact    { background-color: rgba(76, 175, 80, 0.25); }   /* green */
.opinion { background-color: rgba(244, 67, 54, 0.25); }   /* red */
.mixed   { background-color: rgba(255, 193, 7, 0.25); }   /* amber */
.unclear { background-color: rgba(255, 193, 7, 0.15); }   /* pale amber */

/* CSS-only tooltip via title attribute — or use data-tooltip + ::after pseudo-element */
.sentence[title]:hover::after {
  content: attr(title);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.8);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  white-space: nowrap;
  pointer-events: none;
  z-index: 100;
}
```

**Note:** `title` attribute gives browser-native tooltips (no JS). Custom `::after` pseudo-element gives styled tooltips (CSS only). Either is valid. The `::after` approach is more portable across mobile.

### Pattern 7: Collapsible Opinion Sections (HTML-native, No JS)

**What:** Native `<details>`/`<summary>` elements collapse opinion content without JavaScript. Default closed (`open` attribute absent). Works on all modern browsers and is accessible.

```html
<!-- templates/article.html (opinion section wrapper) -->
<details class="opinion-section">
  <summary class="opinion-toggle">Show opinion content ({{ opinion_count }} sentences)</summary>
  <div class="opinion-content">
    {% for sentence in opinion_sentences %}
      <span class="sentence opinion"
            data-confidence="{{ sentence.confidence }}"
            title="{% if sentence.confidence >= 0.7 %}High{% elif sentence.confidence >= 0.4 %}Medium{% else %}Low{% endif %} confidence">
        {{ sentence.text }}
      </span>
    {% endfor %}
  </div>
</details>
```

**Template logic to split sentences by label:**
```python
# In article route, split before passing to template
fact_sentences = [s for s in sentences if s.label == "fact"]
opinion_sentences = [s for s in sentences if s.label == "opinion"]
mixed_sentences = [s for s in sentences if s.label in ("mixed", "unclear")]
```

**Alternative approach:** Render all sentences in order with opinion spans wrapped in an inline `<details>` that groups consecutive opinion sentences. This preserves article reading order. Implementation is more complex but better for readability.

### Pattern 8: DB Session Dependency

**What:** FastAPI `Depends()` injects an async SQLAlchemy session per request.

```python
# factfeed/web/deps.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from factfeed.db.session import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

```python
# Used in routes
from fastapi import Depends
from factfeed.web.deps import get_db

@router.get("/article/{article_id}")
async def article_detail(
    article_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    ...
```

### Anti-Patterns to Avoid

- **Blocking DB calls in async routes:** All SQLAlchemy queries must use `await session.execute(...)`. Never call sync `session.query()` in an async route.
- **Raw string interpolation in FTS queries:** Use `func.plainto_tsquery("english", :q)` with bound params, never f-strings with user input.
- **Computing fact ratio with Python after fetching all sentences:** Pull the ratio from SQL in the ORDER BY subquery, not in Python after loading all sentence rows.
- **Using JavaScript for collapsible sections:** `<details>/<summary>` is native HTML; no HTMX or JS needed. HTMX should be reserved for server-side partial updates (search results).
- **Storing HTMX state in cookies or localStorage:** URL query params are the state store (bookmarkable, no tracking). `hx-push-url="true"` keeps URL in sync.
- **Hard-coding source names in templates:** Source list must be fetched from the `sources` table, not hard-coded, since sources are seeded from the DB.
- **Passing raw SQLAlchemy ORM objects directly to templates:** ORM objects may trigger lazy-loads in Jinja2. Prefer passing dicts or use eager loading (`selectinload`) for relationships.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Search debounce | Custom JS debounce function | HTMX `hx-trigger="keyup changed delay:400ms"` | Built into HTMX; zero JS needed |
| Partial HTML swap on search | Fetch API + manual DOM manipulation | HTMX `hx-target` + `hx-swap` | HTMX handles swap, history, race conditions |
| Collapsible sections | JavaScript toggle `classList.add('hidden')` | HTML `<details>/<summary>` | Native browser behavior; no JS; accessible |
| CSS tooltips | Floating tooltip component | CSS `position:absolute` + `::after` pseudo-element or `title` attribute | Pure CSS; no runtime overhead |
| Sort/filter state | localStorage or cookies | URL query params + `hx-push-url` | Bookmarkable, privacy-safe, server-driven |
| Mobile hamburger nav | React component or custom JS | Not needed — no complex nav in this app | Keep nav minimal (headline + link to about) |
| Fact ratio computation | Python loop over sentences | SQL `COUNT(*) FILTER (WHERE label='fact') / COUNT(*)` subquery | Single DB round-trip; ordered in DB |

**Key insight:** This stack is deliberately anti-SPA. Everything that a React app would compute client-side happens in the SQL query or the Jinja2 template. The browser receives pre-rendered HTML. HTMX handles the narrow slice of interactivity (live search, sort toggle) without surrendering the server-rendering advantage.

---

## Common Pitfalls

### Pitfall 1: Fact-Density Sort on Articles with No Sentences

**What goes wrong:** Articles that have been ingested but not yet classified have zero sentence rows. The `fact_ratio` subquery returns NULL for them. If sorted DESC with NULLS LAST, they sink to the bottom. If NULLS FIRST, they float to the top.
**Why it happens:** `classify_unprocessed_articles` runs async after ingestion; newly ingested articles may appear in search before classification completes.
**How to avoid:** Use `.nullslast()` in the ORDER BY so unclassified articles appear after classified ones. Also consider filtering to `is_partial=False` articles for the default view.
**Warning signs:** Search results show blank/no-highlight articles at the top.

### Pitfall 2: SQLAlchemy Lazy-Load in Jinja2 Template

**What goes wrong:** Jinja2 accesses `article.source.name` or `article.sentences` in a template, triggering SQLAlchemy lazy-loading outside the async session context. Results in `MissingGreenlet` error or `greenlet_spawn` exception.
**Why it happens:** The async session is closed by the time Jinja2 iterates relationships.
**How to avoid:** Use `selectinload(Article.source)` and `selectinload(Article.sentences)` in the query, or pass pre-extracted dicts to the template.
**Warning signs:** `MissingGreenlet` exception in template rendering.

### Pitfall 3: FTS Returns No Results for Partial Words

**What goes wrong:** User types "inflat" and gets no results even though "inflation" articles exist. `plainto_tsquery` does exact token matching, not prefix matching.
**Why it happens:** PostgreSQL FTS tokenizes "inflat" as a single token; "inflation" as another. They do not match under `@@`.
**How to avoid:** For MVP, document this limitation. For better UX, use `websearch_to_tsquery` (supports quoted phrases and negation) or append `:*` prefix-match syntax with `to_tsquery`. Simplest fix: `func.to_tsquery("english", params.q.strip() + ":*")` — but this only works for single words and needs sanitization.
**Warning signs:** Users report missing articles they can see when searching full words.

### Pitfall 4: Sort Toggle Loses Other Filter State

**What goes wrong:** Clicking "Most Recent" clears the keyword and source filter. User has to re-enter search query.
**Why it happens:** HTMX sort toggle buttons only include their own `hx-vals`, not other form fields, unless `hx-include` is specified.
**How to avoid:** All sort/filter buttons must include `hx-include="[name='q'],[name='source'],[name='from_']"` (or the enclosing form) so all params travel together.
**Warning signs:** Clicking sort button loses the search query from the URL.

### Pitfall 5: Confidence Display Shows Raw Float

**What goes wrong:** Hovering over a sentence shows "0.712381" instead of "High confidence". The requirements explicitly say confidence must be displayed as High/Medium/Low, not raw decimal.
**Why it happens:** Passing `sentence.confidence` directly to `title` attribute without mapping.
**How to avoid:** Map in Jinja2 template using a conditional: `≥0.7 → High`, `0.4-0.69 → Medium`, `<0.4 → Low`. Or add a Jinja2 custom filter.
**Warning signs:** Tooltip shows decimal number.

### Pitfall 6: `<details>` / `<summary>` Order vs. Article Flow

**What goes wrong:** Grouping all opinion sentences into one `<details>` block at the bottom breaks the natural article reading order. A sentence from paragraph 1 (opinion) and sentence from paragraph 8 (opinion) appear together, disconnected from their context.
**Why it happens:** Simple approach: collect all opinions into one block.
**How to avoid:** Two viable strategies:
  1. Render sentences in position order; wrap each consecutive opinion run in its own inline `<details>`. Preserves reading order.
  2. Accept the grouping and document it as the intended behavior (simplest implementation).
  For Phase 4 MVP, option 2 is acceptable.
**Warning signs:** Article is hard to follow because facts and opinions are separated rather than interspersed.

### Pitfall 7: Mobile Horizontal Scroll from Fixed-Width Elements

**What goes wrong:** Article text or code blocks exceed viewport width on mobile, requiring horizontal scroll.
**Why it happens:** `min-width` on containers, `white-space: nowrap` on spans, or table layouts with fixed columns.
**How to avoid:** Use `max-width: 100%` on all container elements; `word-wrap: break-word` on article body; `overflow-x: auto` on any pre/code blocks. Test at 375px viewport width (iPhone SE baseline).
**Warning signs:** Content bleeds past viewport edge on mobile.

---

## Code Examples

Verified patterns from official sources and project codebase:

### FTS with SQLAlchemy func Namespace

```python
# Source: SQLAlchemy 2.0 PostgreSQL dialect docs
# https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#full-text-search

from sqlalchemy import func, select
from factfeed.db.models import Article

# plainto_tsquery — safe for user input (treats all words as AND)
query_expr = func.plainto_tsquery("english", user_input)
stmt = select(Article).where(
    Article.search_vector.bool_op("@@")(query_expr)
)

# ts_rank for relevance ordering
stmt = stmt.order_by(
    func.ts_rank(Article.search_vector, query_expr).desc()
)
```

### Fact-Density Subquery

```python
# Source: SQLAlchemy 2.0 docs — subqueries + aggregate functions
# https://docs.sqlalchemy.org/en/20/tutorial/data_select.html

from sqlalchemy import Float, func, select
from factfeed.db.models import Article, Sentence

fact_ratio_sq = (
    select(
        Sentence.article_id,
        (
            func.count(Sentence.id).filter(Sentence.label == "fact").cast(Float)
            / func.nullif(func.count(Sentence.id), 0)
        ).label("fact_ratio"),
    )
    .group_by(Sentence.article_id)
    .subquery()
)

stmt = (
    select(Article)
    .outerjoin(fact_ratio_sq, Article.id == fact_ratio_sq.c.article_id)
    .order_by(fact_ratio_sq.c.fact_ratio.desc().nullslast())
)
```

### HTMX Active Search Input

```html
<!-- Source: https://htmx.org/examples/active-search/ -->
<input
  type="search"
  name="q"
  hx-get="/search"
  hx-target="#results"
  hx-swap="innerHTML"
  hx-trigger="keyup changed delay:400ms, search"
  hx-include="[name='source'],[name='from_'],[name='sort']"
  hx-push-url="true"
  placeholder="Search articles..."
/>
```

### Confidence to Label Mapping in Jinja2

```html
{# Jinja2 inline confidence label — no custom filter needed #}
{% set conf_label = "High" if sentence.confidence >= 0.7
                    else ("Medium" if sentence.confidence >= 0.4
                    else "Low") %}
<span class="sentence {{ sentence.label }}"
      title="{{ conf_label }} confidence">
  {{ sentence.text }}
</span>
```

### DB Session Dependency

```python
# Pattern from FastAPI official docs
# https://fastapi.tiangolo.com/tutorial/dependencies/

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from factfeed.db.session import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

### Router Registration in main.py

```python
# Expand factfeed/web/main.py to include routes + static mount
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from factfeed.web.routes import search, article

app.mount("/static", StaticFiles(directory="factfeed/static"), name="static")
app.include_router(search.router)
app.include_router(article.router)

templates = Jinja2Templates(directory="factfeed/templates")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` for lifespan | `@asynccontextmanager` lifespan param | FastAPI 0.93 (2023) | `on_event` is deprecated; already using new pattern |
| `session.query(Model)` SQLAlchemy 1.x | `select(Model)` SQLAlchemy 2.0 | SQLAlchemy 2.0 (2023) | Async-incompatible old API; project already uses 2.0 style |
| HTMX 1.x (`hx-*` namespace) | HTMX 2.0 (same API, IE11 dropped) | June 2024 | Breaking: IE11 support removed; modern browsers only |
| JavaScript SPAs (React) for search | HTMX + server-rendered partials | Growing trend 2023-2025 | Eliminates build pipeline; server is source of truth |
| `<div class="collapsible">` + JS toggle | Native `<details>`/`<summary>` | HTML5 (full browser support by 2021) | No JavaScript needed for disclosure widgets |

**Deprecated/outdated:**
- `@app.on_event`: Use `lifespan=` parameter instead (already done in project).
- SQLAlchemy 1.x `session.query()`: Project uses 2.0 `select()` style throughout.
- HTMX 1.x CDN URLs: Use `@2.0.8` or later from cdn.jsdelivr.net.

---

## Open Questions

1. **Consecutive opinion sentence grouping vs. single block**
   - What we know: `<details>/<summary>` provides collapsibility; grouping all opinions into one block is simpler to implement but breaks reading order
   - What's unclear: Whether users will notice or care about reading-order disruption for v1
   - Recommendation: Implement single block (all opinions grouped) for v1; note as a known UX limitation; refine in v2 based on user feedback

2. **Prefix search for partial keywords**
   - What we know: `plainto_tsquery` does not support prefix matching; `to_tsquery('english', 'inflat:*')` adds prefix match but requires sanitizing user input (no special characters)
   - What's unclear: How critical prefix matching is for the MVP use case
   - Recommendation: Use `websearch_to_tsquery` instead of `plainto_tsquery` — it handles user input more gracefully (ignores special chars, supports phrases with quotes) and is safer than `to_tsquery` for unsanitized input. Switch is a one-line change.

3. **Article excerpt generation for search list (UI-01)**
   - What we know: `Article.body` contains the full text; no stored excerpt/summary column in current schema
   - What's unclear: Whether to truncate body in Python (`body[:200]`) or compute in SQL (`LEFT(body, 200)`)
   - Recommendation: Truncate in Python in the Jinja2 template filter (`{{ article.body[:200] }}...`) or add a `truncate` Jinja2 filter. No schema change needed.

4. **Source list for filter dropdown**
   - What we know: Sources are in the `sources` table (name, feed_url, id); seeded at startup
   - What's unclear: Whether to query sources on every search request or cache them
   - Recommendation: Query source list once in the search route and pass to template. At 5 sources, this is negligible. No caching needed for v1.

---

## Sources

### Primary (HIGH confidence)

- FastAPI Templates official docs — https://fastapi.tiangolo.com/advanced/templates/ — `TemplateResponse`, `StaticFiles`, `Jinja2Templates` setup
- FastAPI Query Parameter Models — https://fastapi.tiangolo.com/tutorial/query-param-models/ — `Annotated[Model, Query()]` pattern with Pydantic
- SQLAlchemy 2.0 PostgreSQL FTS — https://docs.sqlalchemy.org/en/20/dialects/postgresql.html — `func.plainto_tsquery`, `func.ts_rank`, `match()`, `bool_op("@@")`
- SQLAlchemy 2.0 SELECT tutorial — https://docs.sqlalchemy.org/en/20/tutorial/data_select.html — subquery, label, join, order_by patterns
- HTMX 2.0 release — https://htmx.org/posts/2024-06-17-htmx-2-0-0-is-released/ — version confirmed stable, IE11 dropped
- HTMX active search example — https://htmx.org/examples/active-search/ — `hx-trigger="keyup changed delay:500ms"` pattern
- HTMX documentation — https://htmx.org/docs/ — `hx-get`, `hx-target`, `hx-swap`, `hx-push-url`, `hx-include`, `hx-vals` attributes

### Secondary (MEDIUM confidence)

- TestDriven.io HTMX + FastAPI — https://testdriven.io/blog/fastapi-htmx/ — HX-Request header detection, partial vs full response pattern
- HTMX URL-driven state — https://www.lorenstew.art/blog/bookmarkable-by-design-url-state-htmx/ — `hx-push-url` + `hx-include` for filter state preservation
- SQLAlchemy FTS blog — https://hamon.in/blog/sqlalchemy-and-full-text-searching-in-postgresql/ — `func` namespace FTS patterns verified against official docs
- HTML details/summary native collapsible — https://dev.to/jordanfinners/creating-a-collapsible-section-with-nothing-but-html-4ip9 — browser support confirmed universal

### Tertiary (LOW confidence)

- Miguel Grinberg nested queries — https://blog.miguelgrinberg.com/post/nested-queries-with-sqlalchemy-orm — subquery + JOIN for aggregate ratio pattern (style adapted for SQLAlchemy 2.0)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and used; no new dependencies
- Architecture: HIGH — Jinja2/FastAPI/HTMX patterns verified against official docs; FTS verified against SQLAlchemy docs
- Pitfalls: HIGH for lazy-load and parameter state issues (well-documented); MEDIUM for fact-density edge cases (reasoning from first principles)

**Research date:** 2026-02-24
**Valid until:** 2026-06-01 (stable libraries; HTMX 2.x is stable/finished)
