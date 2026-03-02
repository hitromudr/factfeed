"""Service layer for analytics and statistics aggregation."""

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.db.models import Article, Sentence, Source


async def get_source_factuality_stats(
    db: AsyncSession,
) -> list[dict[str, str | int | float]]:
    """
    Aggregate sentence labels grouped by source.

    Returns a list of dictionaries with counts for fact, opinion, mixed, unclear,
    and a calculated factuality score.
    """
    stmt = (
        select(
            Source.name,
            func.count(Sentence.id).label("total"),
            func.count(case((Sentence.label == "fact", 1))).label("facts"),
            func.count(case((Sentence.label == "opinion", 1))).label("opinions"),
            func.count(case((Sentence.label == "mixed", 1))).label("mixed"),
            func.count(case((Sentence.label == "unclear", 1))).label("unclear"),
        )
        .join(Article, Article.source_id == Source.id)
        .join(Sentence, Sentence.article_id == Article.id)
        .group_by(Source.id, Source.name)
        .order_by(Source.name)
    )

    result = await db.execute(stmt)
    rows = result.all()

    stats: list[dict[str, str | int | float]] = []
    for row in rows:
        name, total, facts, opinions, mixed, unclear = row

        # Calculate factuality score: facts / (facts + opinions)
        # We exclude 'mixed' and 'unclear' from the ratio as they are ambiguous
        denom = facts + opinions
        score = (facts / denom) if denom > 0 else 0.0

        stats.append(
            {
                "source": name,
                "total": total,
                "facts": facts,
                "opinions": opinions,
                "mixed": mixed,
                "unclear": unclear,
                "score": round(score, 2),
            }
        )

    # Sort by total sentences descending (most active sources first)
    stats.sort(key=lambda x: int(x["total"]), reverse=True)

    return stats


async def get_geographic_stats(db: AsyncSession) -> list[dict[str, str | int]]:
    """
    Aggregate article counts grouped by country code.
    """
    stmt = (
        select(
            Source.country_code,
            Source.region,
            func.count(Article.id).label("article_count"),
        )
        .join(Article, Article.source_id == Source.id)
        .where(Source.country_code.is_not(None))
        .group_by(Source.country_code, Source.region)
        .order_by(func.count(Article.id).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    stats: list[dict[str, str | int]] = []
    for row in rows:
        country_code, region, count = row
        stats.append(
            {
                "country": country_code,
                "region": region,
                "count": count,
            }
        )

    return stats
