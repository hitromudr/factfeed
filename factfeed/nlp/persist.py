"""
Async DB persistence for sentence classifications.

Uses a delete-then-insert pattern for idempotent re-classification:
all existing sentences for an article are removed, then the new
classification results are bulk-inserted.
"""

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Sentence
from factfeed.nlp.pipeline import SentenceResult


async def persist_sentences(
    article_id: int,
    results: list[SentenceResult],
    session: AsyncSession,
) -> None:
    """Persist sentence classification results to the database.

    Deletes existing sentences for the article, then bulk-inserts
    the new results. This ensures re-classification is idempotent.

    Args:
        article_id: ID of the article these sentences belong to.
        results: List of SentenceResult from the classification pipeline.
        session: Async SQLAlchemy session (caller manages lifecycle).
    """
    # Delete existing sentences for this article
    await session.execute(delete(Sentence).where(Sentence.article_id == article_id))

    if not results:
        print(f"No sentences to persist for article {article_id}")
        await session.commit()
        return

    print(f"Persisting {len(results)} sentences for article {article_id}")

    # Bulk insert new sentences
    await session.execute(
        insert(Sentence),
        [
            {
                "article_id": article_id,
                "position": r.position,
                "text": r.text,
                "label": r.label,
                "confidence": r.confidence,
            }
            for r in results
        ],
    )
    await session.commit()
