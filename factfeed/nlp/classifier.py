"""
DeBERTa zero-shot classification wrapper.

Wraps the HuggingFace zero-shot-classification pipeline with FactFeed's
label mapping (factual statement -> fact, opinion or commentary -> opinion).

The model is NOT loaded at module level. The factory function create_classifier()
returns a pipeline callable, and classify_sentence() accepts it as a parameter.
This prevents 3-10 second startup on every test import.
"""

from typing import Callable

CANDIDATE_LABELS = ["factual statement", "opinion or commentary"]
HYPOTHESIS_TEMPLATE = "This sentence is a {}."
LABEL_MAP = {"factual statement": "fact", "opinion or commentary": "opinion"}


def create_classifier(
    model_name: str = "MoritzLaurer/mdeberta-v3-base-zeroshot-v1.1-all-nli",
) -> Callable:
    """Create a zero-shot classification pipeline.

    Returns the HuggingFace pipeline callable. Use this factory to defer
    model loading and allow tests to inject mocks.
    """
    from transformers import pipeline as hf_pipeline

    return hf_pipeline("zero-shot-classification", model=model_name, device=-1)


def classify_sentence(text: str, zs_pipeline: Callable) -> dict:
    """Classify a single sentence using the zero-shot pipeline.

    Returns:
        {"label": "fact"|"opinion", "raw_confidence": float}
    """
    result = zs_pipeline(
        text,
        CANDIDATE_LABELS,
        hypothesis_template=HYPOTHESIS_TEMPLATE,
        multi_label=False,
    )
    top_label = result["labels"][0]
    top_score = result["scores"][0]
    return {"label": LABEL_MAP[top_label], "raw_confidence": top_score}
