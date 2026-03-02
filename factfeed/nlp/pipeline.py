"""
Pipeline orchestrator: segmenter -> pre_filter -> classifier -> calibrator.

Chains all NLP layers to classify an article's sentences. The pipeline
handles pre-filter results (attribution, unclear) without invoking the
transformer, and clamps all confidence scores to [0.05, 0.95].
"""

import asyncio
from dataclasses import dataclass
from typing import Callable, Literal

from factfeed.nlp.calibrator import TemperatureScaler
from factfeed.nlp.classifier import classify_sentence
from factfeed.nlp.pre_filter import pre_filter_sentence
from factfeed.nlp.segmenter import segment_article


@dataclass
class SentenceResult:
    """Classification result for a single sentence."""

    text: str
    position: int
    label: Literal["fact", "opinion", "mixed", "unclear"]
    confidence: float  # 0.0-1.0, calibrated and clamped


def _clamp(value: float, low: float = 0.05, high: float = 0.95) -> float:
    """Clamp a value to [low, high] range."""
    return max(low, min(high, value))


def classify_article(
    body: str,
    zs_pipeline: Callable,
    calibrator: TemperatureScaler | None = None,
    source_name: str = "",
) -> list[SentenceResult]:
    """Classify all sentences in an article body.

    Pipeline: segment -> pre-filter -> classify -> calibrate -> clamp.

    Args:
        body: Article body text.
        zs_pipeline: HuggingFace zero-shot classification pipeline callable.
        calibrator: Optional temperature scaler for confidence calibration.
        source_name: Source name for satire detection in pre-filter.

    Returns:
        List of SentenceResult, one per sentence in order.
    """
    sentences = segment_article(body)
    results: list[SentenceResult] = []

    for position, sent_span in enumerate(sentences):
        # Try pre-filter first (cheap rule-based)
        pre_result = pre_filter_sentence(sent_span, source_name)

        if pre_result is not None:
            # Pre-filter handled this sentence
            confidence = _clamp(pre_result.confidence)
            results.append(
                SentenceResult(
                    text=sent_span.text,
                    position=position,
                    label=pre_result.label,
                    confidence=confidence,
                )
            )
        else:
            # Needs transformer classification
            cls_result = classify_sentence(sent_span.text, zs_pipeline)
            raw_confidence = cls_result["raw_confidence"]

            # Apply calibration if available
            if calibrator is not None:
                raw_confidence = calibrator.calibrate(raw_confidence)

            confidence = _clamp(raw_confidence)
            results.append(
                SentenceResult(
                    text=sent_span.text,
                    position=position,
                    label=cls_result["label"],
                    confidence=confidence,
                )
            )

    return results


async def classify_article_async(
    body: str,
    zs_pipeline: Callable,
    calibrator: TemperatureScaler | None = None,
    source_name: str = "",
) -> list[SentenceResult]:
    """Async wrapper for classify_article.

    Runs the CPU-bound transformer inference in a thread pool
    to avoid blocking the event loop.
    """
    return await asyncio.to_thread(
        classify_article, body, zs_pipeline, calibrator, source_name
    )


async def classify_unprocessed_articles(
    session_factory,
    zs_pipeline: Callable,
    calibrator: TemperatureScaler | None = None,
    batch_size: int = 10,
) -> int:
    """Classify articles that have no sentence rows yet.

    Queries articles with non-null body and no existing sentences,
    then classifies them in batches. Returns the number of articles classified.

    Classification failures are caught and logged without crashing.
    """
    from sqlalchemy import select

    from factfeed.db.models import Article, Sentence
    from factfeed.nlp.persist import persist_sentences

    async with session_factory() as session:
        # Find articles with no sentences
        subq = select(Sentence.article_id).distinct().scalar_subquery()
        stmt = (
            select(Article)
            .where(Article.body.isnot(None))
            .where(Article.body != "")
            .where(Article.id.notin_(subq))
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        articles = result.scalars().all()

    classified_count = 0
    for article in articles:
        try:
            results = await classify_article_async(
                article.body,
                zs_pipeline,
                calibrator,
                source_name="",
            )
            async with session_factory() as session:
                await persist_sentences(article.id, results, session)
            classified_count += 1
        except Exception:
            import structlog

            logger = structlog.get_logger()
            logger.error("classification_failed", article_id=article.id, exc_info=True)
            continue

    return classified_count
