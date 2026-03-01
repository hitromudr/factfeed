# Phase 9: Content Auto-Translation

## Context
FactFeed now ingests global news in multiple languages (EN, ES, RU, etc.) and supports a UI language switcher (EN/RU). However, currently:
1.  Translation relies on a volatile in-memory cache, meaning restarts wipe all translations, leading to slow page loads and potential rate limiting from the translation provider.
2.  Users reading an English article in "Russian mode" get a translation, but users reading a Russian article in "English mode" might not get a consistent experience if the directionality isn't handled correctly.

## Goals
1.  **Persistent Caching**: Store translations in the database to ensure instant load times for previously viewed articles and minimize external API calls.
2.  **Bidirectional Translation**: Ensure seamless reading of any content in the user's preferred language (e.g., Spanish article -> English UI).

## Requirements

### Technical
-   **Database**: New `translations` table to store `(article_id, language, title, body)`.
-   **Service Layer**: Upgrade `factfeed/nlp/translator.py` to check DB -> call API -> save DB.
-   **Concurrency**: Ensure translation requests don't block the main thread (continue using `run_in_executor`).

## Implementation Plan

### Plan 9.1: Database Persistence for Translations
1.  **Schema Update**:
    -   Modify `factfeed/db/models.py`: Add `Translation` model.
        -   `article_id` (FK)
        -   `language` (str, e.g., 'ru', 'en')
        -   `title` (text)
        -   `body` (text)
        -   Unique constraint on `(article_id, language)`.
    -   Generate Alembic migration.

2.  **Service Upgrade**:
    -   Rewrite `factfeed/nlp/translator.py`:
        -   Remove global `_translation_cache`.
        -   Add `get_or_create_translation(db, article, target_lang)` function.
        -   Logic:
            1. Check DB for existing row.
            2. If missing, call `deep_translator` (title + body).
            3. Save to DB.
            4. Return result.

3.  **Route Integration**:
    -   Update `factfeed/web/routes/article.py`:
        -   Inject `db` session into translation calls.
        -   Use the new async service method.
    -   Update `factfeed/web/routes/search.py`:
        -   Prefetch translations for search results if possible, or translate titles on the fly (caching them).

## Verification Strategy
-   **Manual**:
    1.  Open an English article in "RU" mode. Page loads, "Translating..." spinner appears, then Russian text.
    2.  Refresh page. Text should appear instantly (from DB) without spinner delay.
    3.  Check DB `translations` table to confirm row existence.
-   **Automated**:
    -   Test `get_or_create_translation` with a mock DB session and mock translator to verify caching logic.