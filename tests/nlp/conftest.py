"""
Shared NLP test fixtures.

Provides a session-scoped spaCy model and a mock zero-shot classification pipeline
so that NLP unit tests run quickly without downloading the transformer model.
"""

import pytest
import spacy


@pytest.fixture(scope="session")
def spacy_nlp():
    """Session-scoped spaCy multilingual model. Loaded once for all NLP tests."""
    return spacy.load("xx_sent_ud_sm")


@pytest.fixture
def mock_zs_pipeline():
    """Returns a callable mimicking HuggingFace zero-shot-classification pipeline output.

    Default behavior: returns "factual statement" with score 0.85.
    """

    def _pipeline(text, candidate_labels, **kwargs):
        top_label = "factual statement"
        top_score = 0.85
        other_labels = [l for l in candidate_labels if l != top_label]
        remaining_score = 1.0 - top_score
        return {
            "labels": [top_label] + other_labels,
            "scores": [top_score]
            + [remaining_score / max(len(other_labels), 1)] * len(other_labels),
            "sequence": text,
        }

    return _pipeline
