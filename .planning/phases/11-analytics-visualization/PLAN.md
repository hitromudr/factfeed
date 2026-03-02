# Phase 11: Analytics & Visualization

## Context
With the addition of 14+ global sources and multilingual processing, FactFeed now possesses a rich dataset of news coverage from around the world. However, users currently consume this only as a linear feed or search results.

To reveal deeper insights—such as which sources tend to be more opinionated versus factual, or which regions are currently dominating the news cycle—we need to aggregate this data and visualize it. This moves the product from a simple "reader" to an "intelligence tool."

## Goals
1.  **Source Transparency**: Visualize the fact/opinion ratio for each news source, helping users identify potential bias or reporting styles.
2.  **Global Perspective**: Visualize the geographic distribution of news coverage to highlight "blind spots" or hotspots.

## Requirements

### Data Model
-   **Source Metadata**: Extend the `Source` model to include `country_code` (ISO 3166-1 alpha-2, e.g., "US", "GB", "CN") and `region` (e.g., "Europe", "Asia").

### API
-   **Aggregation Endpoints**:
    -   `GET /api/v1/stats/sources`: Returns sentence classification counts grouped by source.
    -   `GET /api/v1/stats/geo`: Returns article counts grouped by country/region.

### UI/UX
-   **Analytics Dashboard**: A new top-level page (`/analytics`) accessible via the navigation bar.
-   **Charts**: Use **Chart.js** (lightweight, standard) for bar/pie charts.
-   **Map**: Use **jsVectorMap** (or similar lightweight SVG map) to show article volume by country.

## Implementation Plan

### Plan 11.1: Source Factuality Analytics
1.  **Backend**:
    -   Create `factfeed/web/routes/analytics.py`.
    -   Implement query to aggregate sentence labels (`fact`, `opinion`, `mixed`, `unclear`) grouped by `Source`.
    -   Calculate a "Factuality Score" (e.g., `facts / (facts + opinions)`).
2.  **Frontend**:
    -   Add "Analytics" link to `base.html` header.
    -   Create `analytics.html` template.
    -   Integrate **Chart.js**.
    -   Render a **Stacked Bar Chart**: X-axis = Source, Y-axis = Sentence Count, Color segments = Fact/Opinion/Unclear.

### Plan 11.2: Geographic Visualization
1.  **Database**:
    -   Modify `Source` model in `models.py`: Add `country_code` (String(2)) and `region` (String(50)).
    -   Create Alembic migration.
    -   Update `factfeed/ingestion/sources.py` to include these fields in the `SOURCES` list.
    -   Update `persister.py` to seed these new fields.
2.  **Backend**:
    -   Add endpoint to get article counts by `country_code`.
3.  **Frontend**:
    -   Integrate a vector map library (e.g., `jsvectormap`).
    -   Render a world map on `analytics.html` where countries are colored by article volume intensity.

## Verification Strategy
-   **Data Integrity**: Verify that `make run` correctly migrates the DB and updates existing sources with country codes.
-   **Visual Check**:
    -   Go to `/analytics`.
    -   Confirm the "Factuality" chart shows different ratios for e.g., *BBC* (mostly fact) vs *Al Jazeera Opinion* or *MercoPress*.
    -   Confirm the Map highlights the US, UK, Spain, Russia, China, etc., based on the active sources.
-   **Performance**: Ensure analytics queries are cached or fast enough (< 200ms) for the dashboard to load smoothly.