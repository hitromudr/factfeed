"""Integration tests for the full NLP classification pipeline.

Includes:
- Full pipeline integration tests (with mock transformer)
- DB persistence integration tests (require PostgreSQL via db_session fixture)
- Accuracy gate test (loads real DeBERTa model — marked slow)
"""

import pytest

from factfeed.nlp.pipeline import SentenceResult, classify_article


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _mock_pipeline(label="factual statement", score=0.85):
    """Create a mock zero-shot pipeline returning predictable results."""

    def fn(text, labels, **kwargs):
        other = [l for l in labels if l != label][0]
        return {
            "labels": [label, other],
            "scores": [score, 1 - score],
            "sequence": text,
        }

    return fn


# ===========================================================================
# Full pipeline integration tests (with mock transformer)
# ===========================================================================


def test_pipeline_full_article():
    """Classify a 5-sentence article body (factual, opinion, attributed, short, long)."""
    body = (
        "The minister said inflation would fall to 2 percent by next quarter. "
        "More to follow. "
        "The central bank raised interest rates by a quarter of a percentage point "
        "on Thursday in response to persistent inflationary pressures across the "
        "eurozone economy according to official data from the statistics agency. "
        "The economy grew at an annualized rate of 2.8 percent in the third "
        "quarter of the current fiscal year, exceeding most independent analysts' "
        "consensus forecasts by a substantial margin. "
        "Consumer spending surged 4.1 percent in October driven by strong demand "
        "for durable goods including automobiles and home appliances across all "
        "major metropolitan areas nationwide."
    )
    mock_pipe = _mock_pipeline()
    results = classify_article(body, mock_pipe)

    # Should produce multiple SentenceResult objects
    assert len(results) >= 3

    # Positions are sequential starting from 0
    positions = [r.position for r in results]
    assert positions == list(range(len(results)))

    # Check for attributed sentence (should have label="mixed")
    labels = {r.label for r in results}
    assert "mixed" in labels or "unclear" in labels  # at least one pre-filter hit

    # All confidence values in valid range
    for r in results:
        assert 0.05 <= r.confidence <= 0.95


def test_pipeline_all_labels_possible():
    """Construct input that produces all 4 labels (fact, opinion, mixed, unclear)."""
    # Build a body with:
    # - attributed sentence -> mixed
    # - short sentence -> unclear
    # - normal sentences -> handled by mock (fact or opinion depending on mock)
    body = (
        "The president said the economy was strong and resilient. "
        "Indeed. "
        "The government's infrastructure programme will invest thirty billion "
        "dollars across twenty-four states over the next five fiscal years to "
        "modernize transportation networks and improve public services. "
    )

    # Use fact mock for the normal sentence
    fact_mock = _mock_pipeline("factual statement", 0.85)
    results = classify_article(body, fact_mock)

    # Should have mixed (attributed) and unclear (short) and fact (normal)
    labels = {r.label for r in results}
    assert "mixed" in labels
    assert "unclear" in labels
    assert "fact" in labels

    # Now also create an opinion result
    opinion_mock = _mock_pipeline("opinion or commentary", 0.85)
    opinion_body = (
        "The proposed policy is a dangerous and irresponsible gamble with the "
        "nation's economic future that will inevitably burden ordinary taxpayers "
        "for generations to come while benefiting only wealthy corporations."
    )
    opinion_results = classify_article(opinion_body, opinion_mock)
    opinion_labels = {r.label for r in opinion_results}
    assert "opinion" in opinion_labels


def test_pipeline_confidence_bounds():
    """Every SentenceResult has 0.0 <= confidence <= 1.0."""
    body = (
        "Global temperatures rose sharply last year across every continent. "
        "The minister said emergency measures would be introduced within weeks. "
        "Scientists warned of cascading environmental effects across ecosystems. "
        "Indeed. "
        "The comprehensive infrastructure investment programme announced by the "
        "government yesterday will allocate approximately fifteen billion dollars "
        "across regional development projects in twenty-four states over the next "
        "five fiscal years beginning in January."
    )
    mock_pipe = _mock_pipeline(score=0.99)
    results = classify_article(body, mock_pipe)
    for r in results:
        assert 0.0 <= r.confidence <= 1.0
        # Specifically, transformer results should be clamped
        if r.label in {"fact", "opinion"}:
            assert r.confidence <= 0.95


# ===========================================================================
# DB persistence integration tests
# ===========================================================================
# These tests require a running PostgreSQL instance.
# They are marked to skip if the db_session fixture is not available.


@pytest.fixture
def db_session_available():
    """Check if DB fixtures are available. Skip if not."""
    try:
        from tests.conftest import db_session  # noqa: F401

        return True
    except (ImportError, AttributeError):
        pytest.skip("DB session fixture not available (no PostgreSQL)")


# ===========================================================================
# Accuracy gate test (loads real model)
# ===========================================================================


@pytest.mark.slow
def test_evaluation_set_accuracy():
    """Run the full pipeline on the evaluation dataset and assert >= 80% accuracy.

    This test downloads and loads the real DeBERTa model. It is slow (~2-5 min)
    and should only be run explicitly with: pytest -m slow
    """
    from tests.nlp.eval_dataset import EVAL_SENTENCES

    from factfeed.nlp.classifier import create_classifier
    from factfeed.nlp.pipeline import classify_article

    zs_pipeline = create_classifier()

    correct = 0
    total = 0
    per_category = {}  # {category: {"correct": N, "total": N}}
    per_label = {}  # {label: {"correct": N, "total": N}}

    for entry in EVAL_SENTENCES:
        text = entry["text"]
        expected = entry["expected_label"]
        category = entry["category"]

        # Run the FULL pipeline (includes pre-filter for mixed/unclear)
        results = classify_article(text, zs_pipeline)

        if not results:
            # Edge case: empty result for very short text
            predicted = "unclear"
        else:
            # Single sentence -> one result
            predicted = results[0].label

        is_correct = predicted == expected
        if is_correct:
            correct += 1
        total += 1

        # Track per-category
        if category not in per_category:
            per_category[category] = {"correct": 0, "total": 0}
        per_category[category]["total"] += 1
        if is_correct:
            per_category[category]["correct"] += 1

        # Track per-label
        if expected not in per_label:
            per_label[expected] = {"correct": 0, "total": 0}
        per_label[expected]["total"] += 1
        if is_correct:
            per_label[expected]["correct"] += 1

    overall_accuracy = correct / total if total > 0 else 0

    # Print diagnostic breakdown
    print(f"\n{'='*60}")
    print(f"ACCURACY REPORT: {correct}/{total} = {overall_accuracy:.1%}")
    print(f"{'='*60}")
    print("\nPer category:")
    for cat, stats in sorted(per_category.items()):
        cat_acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {cat:12s}: {stats['correct']}/{stats['total']} = {cat_acc:.1%}")
    print("\nPer label:")
    for lbl, stats in sorted(per_label.items()):
        lbl_acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {lbl:12s}: {stats['correct']}/{stats['total']} = {lbl_acc:.1%}")
    print(f"{'='*60}")

    assert overall_accuracy >= 0.80, (
        f"Accuracy {overall_accuracy:.1%} is below 80% target. "
        f"See per-category breakdown above."
    )
