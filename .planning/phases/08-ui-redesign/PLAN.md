# Phase 8: UI Redesign & Localization Widget

## Context
User feedback indicates that the current UI, particularly the sentence highlighting, looks "childish" and unprofessional. Additionally, the localization features are not accessible via the UI (missing language switcher), and there is no way to filter articles by their dominant classification (Fact vs. Opinion).

## Goals
1.  **Professional Aesthetic**: Replace the "rainbow" background highlighting with a more subtle, readable design (e.g., underlining, markers, typography).
2.  **Language Control**: Add a visible language switcher widget.
3.  **Enhanced Discovery**: Add a filter to search results to show "Mostly Facts", "Mostly Opinions", etc.

## Requirements

### UI/UX
-   **Typography**: Switch article body text to a Serif font (e.g., Merriweather, Georgia) for better readability.
-   **Highlighting**: Remove background colors for sentences. Use:
    -   Underlines (solid/dotted) or
    -   Left-border markers on hover or
    -   Text color nuances (subtle).
    -   *Decision*: Use thin colored underlines that thicken on hover + tooltip.
-   **Header**: Add "EN | RU" toggle.
-   **Filters**: Add "Content Type" dropdown to search.

### Technical
-   **Routes**: Update `search` endpoint to handle `classification` parameter (e.g., `fact_heavy`, `opinion_heavy`).
-   **Templates**: Update `base.html` to preserve query parameters when switching languages.

## Implementation Plan

### Plan 8.1: UI Refinement and Language Switcher
**Goal**: Execute the visual overhaul and add widgets.

1.  **Language Switcher**:
    -   Update `base.html` to include a widget that links to `?lang=en` and `?lang=ru`, preserving other query params (q, sort, etc.).
2.  **Search Filters**:
    -   Update `search.py` to accept `classification: str`.
    -   Implement logic:
        -   `fact`: fact_pct >= 70
        -   `opinion`: opinion_pct >= 70 (or fact_pct <= 30)
        -   `mixed`: everything else
    -   Update `search.html` to include the dropdown.
3.  **CSS Overhaul**:
    -   Modify `style.css`:
        -   Import Serif font.
        -   Redefine `.sentence` classes to use `border-bottom` instead of `background-color`.
        -   Refine colors to be more "business-like" (e.g., muted teal for facts, brick red for opinions).
4.  **Article Layout**:
    -   Clean up `article.html` header metadata.

## Verification Strategy
-   **Visual**: Check article detail page. Text should be readable like a newspaper. Highlighting should be non-intrusive.
-   **Functional**: Click "RU", interface changes. Filter by "Mostly Facts", only green-bar articles appear.