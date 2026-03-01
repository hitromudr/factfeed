"""Unit tests for the spaCy sentence segmenter."""

import spacy.tokens

from factfeed.nlp.segmenter import segment_article


def test_segment_single_sentence(spacy_nlp):
    """One sentence returns list of length 1."""
    result = segment_article("The market closed higher on Friday.")
    assert len(result) == 1


def test_segment_multiple_sentences(spacy_nlp):
    """Paragraph with 3 sentences returns correct count."""
    text = (
        "Global temperatures rose sharply last year. "
        "Scientists warned of cascading effects. "
        "Governments pledged new funding for research."
    )
    result = segment_article(text)
    assert len(result) == 3


def test_segment_preserves_text(spacy_nlp):
    """Joined sentence texts equal original minus whitespace differences."""
    text = "The economy grew 2.1 percent. Unemployment fell to a record low."
    result = segment_article(text)
    joined = " ".join(s.text for s in result)
    # Allow minor whitespace differences
    assert joined.replace("  ", " ").strip() == text.strip()


def test_segment_empty_string(spacy_nlp):
    """Empty string returns empty list."""
    result = segment_article("")
    assert result == []


def test_segment_whitespace_only(spacy_nlp):
    """Whitespace-only string returns empty list."""
    result = segment_article("   \n\t  ")
    assert result == []


def test_segment_returns_spans(spacy_nlp):
    """Each element is a spaCy Span object."""
    result = segment_article(
        "The report was published yesterday. Reactions were mixed."
    )
    for span in result:
        assert isinstance(span, spacy.tokens.Span)
