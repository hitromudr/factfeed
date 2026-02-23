"""FactFeed NLP classification pipeline."""

from factfeed.nlp.pipeline import SentenceResult, classify_article, classify_article_async
from factfeed.nlp.persist import persist_sentences

__all__ = [
    "SentenceResult",
    "classify_article",
    "classify_article_async",
    "persist_sentences",
]
