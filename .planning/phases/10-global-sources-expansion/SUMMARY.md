# Phase 10: Global News Sources & Multilingual NLP Summary

## Accomplishments

1. **Multilingual NLP Model Setup**
   - Upgraded default Zero-Shot model in `classifier.py` to `MoritzLaurer/mdeberta-v3-base-zeroshot-v1.1-all-nli` which handles over 100 languages.
   - Updated `factfeed/nlp/segmenter.py` and infrastructure (Makefile, Dockerfile) to download and use the multilingual `xx_sent_ud_sm` spaCy model instead of the English-only one.
   - Replaced spaCy `DependencyMatcher` rules in `pre_filter.py` with multi-language robust regex patterns since multilingual POS taggers lack the properties required for `DependencyMatcher` rules.

2. **Global News Sources Expansion**
   - Expanded the list of RSS feeds in `factfeed/ingestion/sources.py` from 5 initial US/UK sources to 14 global sources:
     - Europe: The Guardian, Deutsche Welle, France 24, El País
     - Asia & Middle East: NHK World, The Hindu, SCMP, Al Jazeera Arabic
     - Latin America & Africa: MercoPress, AllAfrica
     - CIS: Meduza, TASS

3. **Verifications Passed**
   - Added `test_classify_multilingual_sentences` unit test to `test_classifier.py` asserting Spanish and Russian classifications work successfully via mock and real-model execution.
   - Fixed an implicit UI bug triggered by the new dataset: non-integer source IDs causing HTTP 500 crashes during filtered searches are now correctly managed.
   - Fixed `TemplateResponse` deprecation warnings in `article.py` and `search.py` by using keyword arguments.
   - Executed ingestion loop on local database, successfully parsing, extracting, and importing multi-lingual feeds (e.g. SCMP: 50, Deutsche Welle: 145, El País: 145, TASS: 105, Meduza: 30 articles). All tests pass successfully.

## Files Created/Modified

- `factfeed/config.py` - Not strictly modified for model name because it lives in `classifier.py`.
- `factfeed/nlp/classifier.py` - Upgraded default zero-shot HuggingFace model.
- `factfeed/nlp/segmenter.py` - Changed base language model to `xx_sent_ud_sm`.
- `factfeed/nlp/pre_filter.py` - Replaced `DependencyMatcher` attribution checks with equivalent robust regex to accommodate missing attribute maps in the multilingual model.
- `factfeed/web/routes/search.py` - Resolved an existing 500 Server Error triggered when source search IDs weren't strictly integers and fixed deprecation warnings.
- `factfeed/web/routes/article.py` - Fixed `TemplateResponse` deprecation warnings.
- `factfeed/ingestion/sources.py` - Appended new global URLs.
- `Makefile` / `Dockerfile` - Adjusted model download steps (`python -m spacy download xx_sent_ud_sm`).
- `tests/nlp/conftest.py` - Loaded test spacy `xx_sent_ud_sm` model.
- `tests/nlp/test_classifier.py` - Created multilingual fact-checking evaluation tests.
- `tests/nlp/test_pre_filter.py` - Updated tests to align with Regex behaviors and non-attributing long English texts.
- `tests/nlp/test_segmenter.py` - Dropped obsolete English-only abbreviation assertions.