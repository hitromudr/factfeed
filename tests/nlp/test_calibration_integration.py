import pytest

from factfeed.nlp.calibrator import TemperatureScaler
from factfeed.nlp.pipeline import classify_article


# Mock pipeline that always returns a specific score for "fact"
def create_mock_pipeline(raw_score: float, label: str = "news"):
    def mock_pipeline(
        text, candidate_labels, hypothesis_template=None, multi_label=False
    ):
        # The real pipeline returns dict with 'labels' and 'scores' lists
        # usually sorted by score descending.
        other_label = "opinion" if label == "news" else "news"
        return {"labels": [label, other_label], "scores": [raw_score, 1.0 - raw_score]}

    return mock_pipeline


def test_calibration_integration_softening():
    """Test that T=2.0 softens a high confidence score."""
    raw_score = 0.99
    # With T=2.0:
    # logit = ln(0.99 / 0.01) ≈ 4.595
    # scaled = 4.595 / 2.0 ≈ 2.297
    # sigmoid(2.297) ≈ 0.908
    # Pipeline clamps to 0.95 max, but 0.908 is valid.

    pipeline = create_mock_pipeline(raw_score)
    calibrator = TemperatureScaler(temperature=2.0)

    # Use long sentence to bypass pre-filter short sentence check (>30 tokens)
    text = "This is a factual statement regarding the economic situation in the developing world which requires significant analysis and detailed reporting to fully understand the complex nuances involved in such a global scenario causing market fluctuations."
    results = classify_article(text, pipeline, calibrator=calibrator)

    assert len(results) == 1
    res = results[0]

    # Check that score is reduced from raw (raw would be clamped to 0.95)
    # 0.908 is less than 0.95
    assert res.confidence < 0.95
    assert res.confidence > 0.85


def test_calibration_integration_identity():
    """Test that T=1.0 keeps score (mostly) same, respecting clamping."""
    raw_score = 0.80
    pipeline = create_mock_pipeline(raw_score)
    calibrator = TemperatureScaler(temperature=1.0)

    text = "This is a factual statement regarding the economic situation in the developing world which requires significant analysis and detailed reporting to fully understand the complex nuances involved in such a global scenario causing market fluctuations."
    results = classify_article(text, pipeline, calibrator=calibrator)

    assert len(results) == 1
    # raw 0.80 should pass through unchanged (within float precision)
    assert abs(results[0].confidence - 0.80) < 1e-6


def test_calibration_clamping():
    """Test that extremely high calibrated scores are still clamped by pipeline."""
    # If we use T=0.1 on 0.99, it becomes essentially 1.0
    raw_score = 0.99
    pipeline = create_mock_pipeline(raw_score)
    calibrator = TemperatureScaler(temperature=0.1)  # Sharpening

    text = "This is a factual statement regarding the economic situation in the developing world which requires significant analysis and detailed reporting to fully understand the complex nuances involved in such a global scenario causing market fluctuations."
    results = classify_article(text, pipeline, calibrator=calibrator)

    # Should be clamped to 0.95 (pipeline limit)
    assert results[0].confidence == 0.95


def test_no_calibration():
    """Test pipeline behavior when calibrator is None."""
    raw_score = 0.99
    pipeline = create_mock_pipeline(raw_score)

    text = "This is a factual statement regarding the economic situation in the developing world which requires significant analysis and detailed reporting to fully understand the complex nuances involved in such a global scenario causing market fluctuations."
    results = classify_article(text, pipeline, calibrator=None)

    # Raw 0.99 clamped to 0.95
    assert results[0].confidence == 0.95
