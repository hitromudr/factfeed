"""
DeBERTa zero-shot classification wrapper.

Wraps the HuggingFace zero-shot-classification pipeline with The Sorter's
label mapping (factual statement -> fact, opinion or commentary -> opinion).

The model is NOT loaded at module level. The factory function create_classifier()
returns a pipeline callable, and classify_sentence() accepts it as a parameter.
This prevents 3-10 second startup on every test import.
"""

from typing import Callable

CANDIDATE_LABELS = ["news", "opinion"]
HYPOTHESIS_TEMPLATE = "This text is {}."
LABEL_MAP = {"news": "fact", "opinion": "opinion"}


def create_classifier(
    model_name: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
) -> Callable:
    """Create a zero-shot classification pipeline.

    Returns the HuggingFace pipeline callable. Use this factory to defer
    model loading and allow tests to inject mocks.
    """
    from transformers import pipeline as hf_pipeline

    import torch

    device = 0 if torch.cuda.is_available() else -1
    return hf_pipeline("zero-shot-classification", model=model_name, device=device)


def is_gpu_pipeline(zs_pipeline: Callable) -> bool:
    """Check if the pipeline is running on GPU."""
    return zs_pipeline.device.type == "cuda"


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
