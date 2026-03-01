"""
spaCy-based sentence segmentation for article body text.

Loads the xx_sent_ud_sm model once at module level and provides
a single entry point for splitting article bodies into sentence spans.
"""

import spacy
from spacy.tokens import Span

_nlp = spacy.load("xx_sent_ud_sm")


def get_nlp() -> spacy.Language:
    """Return the shared spaCy Language object.

    Used by pre_filter.py for DependencyMatcher/PhraseMatcher initialization.
    """
    return _nlp


def segment_article(body: str) -> list[Span]:
    """Parse body text into sentence spans.

    Parses the body ONCE and returns all sentence spans.
    Returns an empty list for empty or whitespace-only input.
    """
    if not body or not body.strip():
        return []
    doc = _nlp(body)
    return list(doc.sents)
