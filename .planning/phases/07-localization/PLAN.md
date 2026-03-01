# Phase 7: Localization

## Context
FactFeed is currently English-only. To expand its reach and usability for non-English speakers, we need to implement an internationalization (i18n) system. The first target language is Russian.

## Goals
1.  **Infrastructure**: Implement a robust i18n system using `Babel` and `gettext`.
2.  **Extraction**: Mark all user-facing strings in Jinja2 templates for translation.
3.  **Translation**: Provide a complete Russian translation for the UI.
4.  **Locale Detection**: Automatically detect user preference (Accept-Language header) or allow manual switching via query parameter.

## Requirements

### Technical
-   **Library**: `Babel` for extraction and compilation.
-   **Storage**: Standard `.po` / `.mo` files in `factfeed/translations`.
-   **Middleware**: Custom dependency/middleware in FastAPI to negotiate locale.
-   **Templates**: Jinja2 `extensions=['jinja2.ext.i18n']` enabled.

### UI/UX
-   **Language Switcher**: Add a simple toggle or link in the footer/header to switch languages manually.
-   **Coverage**:
    -   Navigation links.
    -   Search placeholders and buttons.
    -   Filter options (dropdowns).
    -   Article metadata labels (Source, Date, Author).
    -   Factometer labels (Facts, Opinions, Mixed).
    -   Error messages and "No results" states.

## Implementation Plan

### Plan 7.1: Implement i18n with Babel and Russian translation
**Goal**: Complete setup and translation.

1.  **Dependencies**: Add `babel` to `pyproject.toml`.
2.  **Configuration**:
    -   Create `babel.cfg` to tell Babel how to extract strings from Python and HTML files.
    -   Create `factfeed/web/i18n.py` to handle locale detection and `gettext` installation.
3.  **Template Markup**:
    -   Go through `base.html`, `search.html`, `_results.html`, `article.html`.
    -   Wrap text in `{{ _('Text') }}` blocks.
4.  **Integration**:
    -   Update `factfeed/web/main.py` (or `deps.py`) to inject the `gettext` function into templates based on the current request's locale.
5.  **Translation Cycle**:
    -   Run `pybabel extract`.
    -   Run `pybabel init -l ru`.
    -   Edit `messages.po` (AI translation).
    -   Run `pybabel compile`.
6.  **Verification**:
    -   Test `/?lang=ru` and `/?lang=en`.
    -   Verify `Accept-Language` header behavior.

## Verification Strategy
-   **Manual**: Open the site with a Russian browser locale or `?lang=ru` and check that all UI elements are translated.
-   **Automated**: Add a test case in `tests/test_web_routes.py` that requests the page with `Accept-Language: ru` and asserts presence of Cyrillic strings.