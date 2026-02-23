"""Unit tests for the attribution detection and unclear gate pre-filter."""

from factfeed.nlp.pre_filter import (
    PreFilterResult,
    is_attribution,
    is_unclear,
    pre_filter_sentence,
)


# ---------------------------------------------------------------------------
# Helper: parse text into a single sentence span
# ---------------------------------------------------------------------------

def _to_span(spacy_nlp, text):
    """Parse text and return the first sentence span."""
    doc = spacy_nlp(text)
    return list(doc.sents)[0]


# ===========================================================================
# Attribution detection tests (NLP-04)
# ===========================================================================


def test_attribution_verb_said(spacy_nlp):
    """'The CEO said the company is profitable.' -> mixed"""
    span = _to_span(spacy_nlp, "The CEO said the company is profitable.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "mixed"
    assert result.reason == "attribution"


def test_attribution_verb_claimed(spacy_nlp):
    """'Officials claimed the report was inaccurate.' -> mixed"""
    span = _to_span(spacy_nlp, "Officials claimed the report was inaccurate.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "mixed"
    assert result.reason == "attribution"


def test_attribution_according_to(spacy_nlp):
    """'According to the minister, taxes will decrease.' -> mixed"""
    span = _to_span(spacy_nlp, "According to the minister, taxes will decrease.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "mixed"
    assert result.reason == "attribution"


def test_attribution_told_reporters(spacy_nlp):
    """'The spokesperson told reporters that talks had failed.' -> mixed"""
    span = _to_span(spacy_nlp, "The spokesperson told reporters that talks had failed.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "mixed"
    assert result.reason == "attribution"


def test_no_attribution_plain_fact(spacy_nlp):
    """'Global temperatures rose by 1.2 degrees in 2025.' -> None (pass through)"""
    span = _to_span(spacy_nlp, "Global temperatures rose by 1.2 degrees in 2025.")
    result = pre_filter_sentence(span)
    # This is a short sentence (< 30 tokens) so it will be caught by unclear gate
    # The important thing is it's NOT caught by attribution
    assert not is_attribution(span)


def test_no_attribution_opinion(spacy_nlp):
    """'The policy is deeply flawed and should be reversed.' -> None (pass through)"""
    span = _to_span(spacy_nlp, "The policy is deeply flawed and should be reversed.")
    assert not is_attribution(span)


# ===========================================================================
# Unclear gate tests (NLP-03)
# ===========================================================================


def test_short_sentence_unclear(spacy_nlp):
    """Sentence with <30 spaCy tokens -> unclear"""
    span = _to_span(spacy_nlp, "Markets rose sharply.")
    assert is_unclear(span)
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "unclear"


def test_long_sentence_not_unclear(spacy_nlp):
    """Sentence with 30+ tokens -> not caught by unclear gate"""
    long_text = (
        "The comprehensive infrastructure investment programme announced by the "
        "government yesterday will allocate approximately fifteen billion dollars "
        "across regional development projects in twenty-four states over the next "
        "five fiscal years beginning in January."
    )
    span = _to_span(spacy_nlp, long_text)
    assert not is_unclear(span)


def test_satire_marker_in_text(spacy_nlp):
    """'This is satire and should not be taken seriously...' -> unclear"""
    # Need to make this 30+ tokens so it's not caught by the short check
    text = (
        "This article is clearly satire and should not be taken seriously by anyone "
        "who reads it because the claims made here are entirely fictional and meant "
        "purely for entertainment purposes only."
    )
    span = _to_span(spacy_nlp, text)
    assert is_unclear(span)


def test_breaking_news_stub(spacy_nlp):
    """'Breaking: Earthquake hits coastal city.' -> unclear"""
    span = _to_span(spacy_nlp, "Breaking: Earthquake hits coastal city.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "unclear"


def test_satire_source_name(spacy_nlp):
    """source_name='The Onion' -> unclear regardless of sentence length"""
    long_text = (
        "The comprehensive infrastructure investment programme announced by the "
        "government yesterday will allocate approximately fifteen billion dollars "
        "across regional development projects in twenty-four states over the next "
        "five fiscal years beginning in January."
    )
    span = _to_span(spacy_nlp, long_text)
    assert is_unclear(span, source_name="The Onion")


def test_developing_story(spacy_nlp):
    """'Developing story: details emerging from the scene.' -> unclear"""
    span = _to_span(spacy_nlp, "Developing story: details emerging from the scene.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "unclear"


# ===========================================================================
# Pre-filter priority tests
# ===========================================================================


def test_attribution_before_unclear(spacy_nlp):
    """Short attributed sentence -> mixed (not unclear), attribution takes priority."""
    span = _to_span(spacy_nlp, "He said OK.")
    result = pre_filter_sentence(span)
    assert result is not None
    assert result.label == "mixed"
    assert result.reason == "attribution"


def test_prefilter_returns_none_for_normal(spacy_nlp):
    """Long non-attributed, non-ambiguous sentence -> None"""
    long_text = (
        "The comprehensive infrastructure investment programme announced by the "
        "government yesterday will allocate approximately fifteen billion dollars "
        "across regional development projects in twenty-four states over the next "
        "five fiscal years beginning in January."
    )
    span = _to_span(spacy_nlp, long_text)
    result = pre_filter_sentence(span)
    assert result is None
