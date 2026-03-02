from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from factfeed.db.models import Article, Source
from factfeed.web.api.v1.analytics import router as analytics_router
from factfeed.web.deps import get_db
from factfeed.web.routes.search import _attach_fact_scores, search_articles
from factfeed.web.schemas import ArticleDetailOut, ArticleOut, SourceOut

router = APIRouter()
router.include_router(analytics_router)


@router.get("/sources", response_model=List[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """Get list of available news sources."""
    result = await db.execute(select(Source).order_by(Source.name))
    return result.scalars().all()


@router.get("/search", response_model=List[ArticleOut])
async def search(
    q: str = "",
    source: Optional[int] = None,
    from_filter: Optional[str] = Query(None, alias="from"),
    sort: str = "facts",
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Search for articles with filtering and sorting."""
    # Reuse search logic from web routes
    articles = await search_articles(
        db, q=q, source=source, from_filter=from_filter, sort=sort, limit=limit
    )

    # Attach statistical fields (fact_count, etc.) required by schema
    await _attach_fact_scores(db, articles)

    return articles


@router.get("/articles/{article_id}", response_model=ArticleDetailOut)
async def get_article(
    article_id: int = Path(..., description="The ID of the article to retrieve"),
    db: AsyncSession = Depends(get_db),
):
    """Get full article details including classified sentences."""
    # Eager load source and sentences
    stmt = (
        select(Article)
        .options(selectinload(Article.source), selectinload(Article.sentences))
        .where(Article.id == article_id)
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Calculate stats for the summary fields
    await _attach_fact_scores(db, [article])

    return article
