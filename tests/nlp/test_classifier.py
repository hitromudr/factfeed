"""Unit tests for the classifier, calibrator, and pipeline orchestrator."""

from unittest.mock import MagicMock

import pytest

from factfeed.nlp.calibrator import TemperatureScaler
from factfeed.nlp.classifier import (
    CANDIDATE_LABELS,
    HYPOTHESIS_TEMPLATE,
    classify_sentence,
)
from factfeed.nlp.pipeline import SentenceResult, classify_article

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_mock_pipeline(label="factual statement", score=0.85):
    """Create a mock zero-shot pipeline returning predictable results."""

    def mock_fn(text, labels, **kwargs):
        other_label = [l for l in labels if l != label][0]
        return {
            "labels": [label, other_label],
            "scores": [score, 1 - score],
            "sequence": text,
        }

    return mock_fn


# ===========================================================================
# Classifier tests
# ===========================================================================


def test_classify_sentence_fact():
    """Mock pipeline returns 'factual statement' -> label='fact'."""
    mock_pipe = make_mock_pipeline("factual statement", 0.85)
    result = classify_sentence("The GDP grew 2.5 percent.", mock_pipe)
    assert result["label"] == "fact"
    assert result["raw_confidence"] == pytest.approx(0.85)


def test_classify_sentence_opinion():
    """Mock pipeline returns 'opinion or commentary' -> label='opinion'."""
    mock_pipe = make_mock_pipeline("opinion or commentary", 0.9)
    result = classify_sentence("The policy is a disaster.", mock_pipe)
    assert result["label"] == "opinion"
    assert result["raw_confidence"] == pytest.approx(0.9)


def test_classify_sentence_uses_correct_template():
    """Pipeline is called with correct hypothesis template and multi_label=False."""
    mock_pipe = MagicMock(
        return_value={
            "labels": ["factual statement", "opinion or commentary"],
            "scores": [0.85, 0.15],
            "sequence": "test",
        }
    )
    classify_sentence("test", mock_pipe)
    mock_pipe.assert_called_once_with(
        "test",
        CANDIDATE_LABELS,
        hypothesis_template=HYPOTHESIS_TEMPLATE,
        multi_label=False,
    )


# ===========================================================================
# Calibrator tests
# ===========================================================================


def test_temperature_1_passthrough():
    """TemperatureScaler(1.0) returns the raw score unchanged."""
    scaler = TemperatureScaler(1.0)
    assert scaler.calibrate(0.8) == 0.8


def test_temperature_gt1_reduces_confidence():
    """Temperature > 1.0 reduces confidence (pulls toward 0.5)."""
    scaler = TemperatureScaler(2.0)
    assert scaler.calibrate(0.9) < 0.9


def test_temperature_lt1_increases_confidence():
    """Temperature < 1.0 increases confidence (pushes away from 0.5)."""
    scaler = TemperatureScaler(0.5)
    assert scaler.calibrate(0.6) > 0.6


def test_calibrate_bounds():
    """Calibrated scores stay in (0, 1) for edge inputs."""
    scaler = TemperatureScaler(2.0)
    low = scaler.calibrate(0.01)
    high = scaler.calibrate(0.99)
    assert 0.0 < low < 1.0
    assert 0.0 < high < 1.0


# ===========================================================================
# Pipeline tests (with mock)
# ===========================================================================


def test_classify_article_returns_sentence_results():
    """3-sentence paragraph -> list of 3 SentenceResult objects."""
    body = (
        "Global temperatures rose sharply in 2024. "
        "Scientists warned of cascading effects across ecosystems and economies. "
        "Governments pledged billions in new climate funding over the next decade."
    )
    mock_pipe = make_mock_pipeline()
    results = classify_article(body, mock_pipe)
    assert len(results) == 3
    for r in results:
        assert isinstance(r, SentenceResult)


def test_classify_article_prefilter_attribution():
    """Paragraph with 'The CEO said...' -> that sentence gets label='mixed' without calling mock."""
    body = (
        "The CEO said the company posted record profits this quarter. "
        "Revenue reached fourteen billion dollars in the three months ending in December according to the filing."
    )
    call_count = 0
    original_mock = make_mock_pipeline()

    def counting_mock(text, labels, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_mock(text, labels, **kwargs)

    results = classify_article(body, counting_mock)
    attributed = [r for r in results if r.label == "mixed"]
    assert len(attributed) >= 1
    # The attributed sentence should not have called the mock
    # (one sentence handled by pre-filter, other by mock)
    assert call_count < len(results)


def test_classify_article_prefilter_unclear():
    """Paragraph with short sentence -> that sentence gets label='unclear'."""
    body = (
        "The comprehensive infrastructure investment programme announced by the "
        "government yesterday will allocate approximately fifteen billion dollars "
        "across regional development projects in twenty-four states over the next "
        "five fiscal years beginning in January. More to follow."
    )
    mock_pipe = make_mock_pipeline()
    results = classify_article(body, mock_pipe)
    unclear = [r for r in results if r.label == "unclear"]
    assert len(unclear) >= 1


def test_classify_multilingual_sentences(mock_zs_pipeline):
    """Test that Spanish and Russian sentences can be classified."""
    from factfeed.nlp.classifier import classify_sentence

    spanish_text = "El gobierno anunció nuevas medidas."
    result_es = classify_sentence(spanish_text, mock_zs_pipeline)
    assert result_es["label"] in ["fact", "opinion"]
    assert 0.0 <= result_es["raw_confidence"] <= 1.0

    russian_text = "Фондовый рынок значительно упал."
    result_ru = classify_sentence(russian_text, mock_zs_pipeline)
    assert result_ru["label"] in ["fact", "opinion"]
    assert 0.0 <= result_ru["raw_confidence"] <= 1.0


import pytest


@pytest.mark.slow
def test_multilingual_real_model():
    """Verify that the real model successfully processes Spanish and Russian text."""
    from factfeed.nlp.classifier import classify_sentence, create_classifier

    pipeline = create_classifier()

    res_es = classify_sentence(
        "El presidente anunció nuevas políticas económicas.", pipeline
    )
    assert res_es["label"] in ["fact", "opinion"]
    assert 0.0 <= res_es["raw_confidence"] <= 1.0

    res_ru = classify_sentence("Акции компании упали на десять процентов.", pipeline)
    assert res_ru["label"] in ["fact", "opinion"]
    assert 0.0 <= res_ru["raw_confidence"] <= 1.0


def test_classify_article_confidence_clamped():
    """Mock returns 0.99 confidence -> pipeline result confidence <= 0.95."""
    body = (
        "The comprehensive infrastructure investment programme announced by the "
        "government yesterday will allocate approximately fifteen billion dollars "
        "across regional development projects in twenty-four states over the next "
        "five fiscal years beginning in January."
    )
    mock_pipe = make_mock_pipeline(score=0.99)
    results = classify_article(body, mock_pipe)
    for r in results:
        assert r.confidence <= 0.95


def test_classify_article_positions_sequential():
    """Positions are 0, 1, 2, ... in order."""
    body = "First sentence here. Second sentence here. Third sentence here."
    mock_pipe = make_mock_pipeline()
    results = classify_article(body, mock_pipe)
    positions = [r.position for r in results]
    assert positions == list(range(len(results)))


def test_classify_article_empty_body():
    """Empty string returns empty list."""
    mock_pipe = make_mock_pipeline()
    results = classify_article("", mock_pipe)
    assert results == []


def test_sentence_result_has_all_fields():
    """Each result has text, position, label, confidence."""
    body = "The unemployment rate is 3.7 percent as of November this year according to the latest official government data release."
    mock_pipe = make_mock_pipeline()
    results = classify_article(body, mock_pipe)
    for r in results:
        assert isinstance(r.text, str)
        assert len(r.text) > 0
        assert isinstance(r.position, int)
        assert r.label in {"fact", "opinion", "mixed", "unclear"}
        assert isinstance(r.confidence, float)
        assert 0.0 <= r.confidence <= 1.0
