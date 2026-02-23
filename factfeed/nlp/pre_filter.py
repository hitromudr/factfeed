"""
Rule-based pre-filter for the hybrid classification pipeline.

Handles deterministic classification cases before the transformer runs:
- Attribution detection: routes "The CEO said..." sentences to "mixed"
- Unclear gate: routes short, ambiguous, satire, or breaking news sentences to "unclear"

Pre-filter returns None for sentences that need transformer classification.
Attribution check runs BEFORE unclear check (priority ordering).
"""

from dataclasses import dataclass
from typing import Literal, Optional

import spacy
from spacy.matcher import DependencyMatcher, PhraseMatcher
from spacy.tokens import Span

from factfeed.nlp.segmenter import get_nlp

Label = Literal["fact", "opinion", "mixed", "unclear"]


@dataclass
class PreFilterResult:
    """Result from the pre-filter when a sentence is classified without the transformer."""

    label: Label
    confidence: float
    reason: str  # "attribution", "short_sentence", "satire_marker", "breaking_news"


# ---------------------------------------------------------------------------
# Module-level matcher initialization (run once when module loads)
# ---------------------------------------------------------------------------

_nlp = get_nlp()

# Attribution verbs for DependencyMatcher
_ATTRIBUTION_VERBS = {
    "say", "tell", "claim", "state", "announce", "report", "allege",
    "argue", "warn", "explain", "note", "add", "confirm", "deny",
    "insist", "suggest", "indicate", "assert", "contend", "maintain",
    "remark", "declare",
}

# DependencyMatcher for attribution verbs with a subject
_dep_matcher = DependencyMatcher(_nlp.vocab)
_dep_pattern = [
    {
        "RIGHT_ID": "verb",
        "RIGHT_ATTRS": {"POS": "VERB", "LEMMA": {"IN": list(_ATTRIBUTION_VERBS)}},
    },
    {
        "LEFT_ID": "verb",
        "REL_OP": ">",
        "RIGHT_ID": "subject",
        "RIGHT_ATTRS": {"DEP": "nsubj"},
    },
]
_dep_matcher.add("ATTRIBUTION_VERB", [_dep_pattern])

# PhraseMatcher for attribution phrases
_phrase_matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
_ATTRIBUTION_PHRASES = [
    "according to",
    "told reporters",
    "sources said",
    "sources say",
    "officials said",
    "officials say",
    "a spokesperson said",
    "in a statement",
]
_phrase_patterns = list(_nlp.tokenizer.pipe(_ATTRIBUTION_PHRASES))
_phrase_matcher.add("ATTRIBUTION_PHRASE", _phrase_patterns)

# Satire markers
SATIRE_MARKERS = {
    "the onion", "babylon bee", "reductress", "the daily mash",
    "the beaverton", "world news daily report", "satire", "[satire]",
}

# Breaking news patterns
BREAKING_PATTERNS = ["breaking:", "breaking news:", "developing story:", "just in:"]


def is_attribution(sent_span: Span) -> bool:
    """Detect attributed speech patterns in a sentence span.

    Uses both dependency matching (verb + nsubj) and phrase matching
    to catch patterns like "The CEO said..." and "According to...".
    """
    doc = sent_span.as_doc()
    dep_matches = _dep_matcher(doc)
    if dep_matches:
        return True
    phrase_matches = _phrase_matcher(doc)
    if phrase_matches:
        return True
    return False


def is_unclear(sent_span: Span, source_name: str = "") -> bool:
    """Detect short, ambiguous, satire, or breaking news sentences.

    Returns True if ANY of the following checks pass:
    - Sentence has fewer than 30 spaCy tokens
    - Sentence text contains a satire marker (case-insensitive)
    - Sentence starts with a breaking news pattern (case-insensitive)
    - source_name matches a known satire source
    """
    # Short sentence check (spaCy token count)
    if len(sent_span) < 30:
        return True

    text_lower = sent_span.text.lower()

    # Satire marker in text
    for marker in SATIRE_MARKERS:
        if marker in text_lower:
            return True

    # Breaking news pattern at start
    for pattern in BREAKING_PATTERNS:
        if text_lower.startswith(pattern):
            return True

    # Satire source name
    if source_name and source_name.lower() in SATIRE_MARKERS:
        return True

    return False


def _get_unclear_reason(sent_span: Span, source_name: str = "") -> str:
    """Determine the specific reason a sentence is unclear."""
    if len(sent_span) < 30:
        return "short_sentence"

    text_lower = sent_span.text.lower()

    for marker in SATIRE_MARKERS:
        if marker in text_lower:
            return "satire_marker"

    for pattern in BREAKING_PATTERNS:
        if text_lower.startswith(pattern):
            return "breaking_news"

    if source_name and source_name.lower() in SATIRE_MARKERS:
        return "satire_marker"

    return "short_sentence"  # fallback


def pre_filter_sentence(sent_span: Span, source_name: str = "") -> Optional[PreFilterResult]:
    """Run pre-filter on a sentence span.

    Attribution check runs FIRST (priority). A 10-token sentence like
    "He said the deal is done." is classified as mixed (attribution),
    not unclear (short).

    Returns PreFilterResult if the sentence is handled, None if it
    needs transformer classification.
    """
    # Attribution check first (higher priority)
    if is_attribution(sent_span):
        return PreFilterResult("mixed", 0.6, "attribution")

    # Unclear check second
    if is_unclear(sent_span, source_name):
        reason = _get_unclear_reason(sent_span, source_name)
        return PreFilterResult("unclear", 0.1, reason)

    # Needs transformer classification
    return None
