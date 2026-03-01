# Phase 6: API & UI Polish

## Context
With the v1.0 MVP shipped, FactFeed has a functional ingestion pipeline, NLP classification, and basic search interface. The next step is to open up the data for consumption by other services via a REST API and to improve the user experience of the search interface to make the distinction between facts and opinions more intuitive.

## Goals
1.  **Public API**: Expose article search and details via a clean, documented JSON API.
2.  **Frontend Polish**: Improve the visual hierarchy, responsiveness, and data visualization of the web interface.
3.  **Decoupling**: Ensure the web frontend consumes data in a way that aligns with API patterns (though currently using SSR).

## Requirements

### API
-   **Endpoints**:
    -   `GET /api/v1/search`: Same filters as web (q, source, date), returns JSON list.
    -   `GET /api/v1/articles/{id}`: Full article details with sentence-level classification.
    -   `GET /api/v1/sources`: List of available sources.
-   **Security**: CORS enabled for public access (or configured via settings).
-   **Documentation**: Automatic OpenAPI docs (Swagger UI) at `/docs`.
-   **Versioning**: URL-based versioning (`/v1/`).

### UI/UX
-   **Visual Identity**: Modernize the CSS (cleaner typography, better spacing).
-   **Data Viz**: Replace text labels for "Fact Score" with a visual progress bar or gauge.
-   **Responsiveness**: Ensure search results and article details look good on mobile.
-   **Navigation**: Add clear links to API docs.

## Implementation Plan

### Plan 6.1: REST API Implementation
**Goal**: Create the `factfeed.web.api` module and expose endpoints.

1.  [x] **Schemas**: Create Pydantic models in `factfeed.web.schemas` mirroring the DB models but for public consumption.
    -   `SourceOut`, `SentenceOut`, `ArticleOut`, `ArticleDetailOut`.
2.  [x] **Router**: Create `factfeed.web.api.v1` router.
    -   Implement endpoints using the existing service logic (refactor if necessary to share logic between Web and API).
3.  [x] **Configuration**: Update `main.py` to mount the API router and configure CORS.
4.  [x] **Tests**: Add `tests/api/` to verify JSON responses.

### Plan 6.2: Frontend UX Overhaul
**Goal**: Update `factfeed/templates` and `factfeed/static/style.css`.

1.  [x] **Refactor CSS**: Split or organize CSS variables for theming.
2.  [x] **Component Design**:
    -   Redesign Article Card (search result).
    -   Redesign Article Detail (sentence highlighting).
    -   Implement "Factometer" visual component.
3.  [x] **Templates**: Update Jinja2 templates to use new classes and components.
4.  [ ] **Verification**: Manual UAT + check existing web tests pass.

## Verification Strategy
-   **API**: Run `uv run pytest tests/api` (new tests).
-   **UI**: Manual verification of `/` and `/search` pages. Check mobile view.