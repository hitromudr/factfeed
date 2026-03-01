# Phase 10: Global News Sources & Multilingual NLP

## Context
FactFeed currently aggregates a small subset of primarily US/UK English-language news sources (NPR, BBC, Reuters). To provide a truly comprehensive view of global events and highlight how different regions mix facts with opinions, we need to ingest data from top-tier international providers across multiple languages.

However, adding non-English sources introduces a critical NLP challenge: our current classification model (`MoritzLaurer/deberta-v3-base-zeroshot-v2.0`) is optimized for English. If we feed it Spanish or Russian text, the fact/opinion classification accuracy will plummet.

## Goals
1.  **Multilingual NLP**: Upgrade the Zero-Shot classification model to a multilingual variant capable of understanding text in 100+ languages without prior translation.
2.  **Global Ingestion**: Expand `factfeed/ingestion/sources.py` to include a curated list of free, authoritative RSS feeds representing diverse geopolitical regions.

## Requirements

### Technical: Multilingual NLP (Plan 10.1)
-   **Model Upgrade**: Replace the current DeBERTa model with `MoritzLaurer/mdeberta-v3-base-zeroshot-v1.1-all-nli` (or similar multilingual NLI model).
-   **SpaCy Upgrade**: Ensure sentence segmentation (`factfeed.nlp.segmenter`) uses a multilingual pipeline (e.g., `xx_ent_wiki_sm` or `xx_sent_ud_sm`) instead of `en_core_web_sm` when processing non-English text, OR simply use a robust regex/punkt segmenter if spaCy models are too heavy.
-   **Performance Check**: Verify that inference time remains acceptable (batch sizes might need adjustment).

### Technical: Source Expansion (Plan 10.2)
-   **Add Sources**: Update `SOURCES` list in `factfeed/ingestion/sources.py` with the following targets:
    -   *Europe*: The Guardian (UK), Deutsche Welle (Germany - EN/RU), France 24 (France - EN), El País (Spain - ES).
    -   *Asia & Middle East*: NHK World (Japan), The Hindu (India), SCMP (Hong Kong), Al Jazeera (Arabic feed).
    -   *Latin America & Africa*: MercoPress (LatAm), AllAfrica.
    -   *CIS*: Meduza (RU), TASS (RU - for contrast).
-   **Deduplication**: Ensure the `url_hash` deduplication logic handles diverse URL structures from these new domains correctly.

## Implementation Plan

### Plan 10.1: Multilingual NLP Pipeline
1.  Update `factfeed/config.py`:
    -   Change default model string to the `mdeberta` variant.
2.  Update `factfeed/nlp/classifier.py`:
    -   Adjust the prompt/hypothesis if necessary. The multilingual model still accepts English hypotheses (e.g., "This text is stating a fact") and maps them to foreign premises correctly.
3.  Update `factfeed/nlp/segmenter.py`:
    -   Change the spaCy model dependency in `Makefile` and `pyproject.toml` from `en_core_web_sm` to a multilingual sentence boundary detector.

### Plan 10.2: Configure New Providers
1.  Update `factfeed/ingestion/sources.py`:
    -   Append the new RSS URLs to the configuration list.
2.  Test Extraction:
    -   Run a manual ingestion cycle (`python -m factfeed.ingestion.runner`) to ensure `trafilatura` successfully parses the article bodies from these new HTML structures. (Some sites like SCMP or El País might have hard paywalls blocking `trafilatura`).
3.  Database Seed:
    -   Execute `make migrate` / `make run` to ensure new sources are seeded into the database.

## Verification Strategy
-   **NLP Check**: Write a unit test in `tests/nlp/test_classifier.py` passing a Spanish and Russian sentence and asserting it returns a valid confidence score.
-   **Ingestion Check**: Monitor the logs for `source_complete` events. Verify that articles from `El País` (Spanish) and `Meduza` (Russian) appear in the database with non-empty `body` fields and `sentences` populated.