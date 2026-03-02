from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from factfeed.services.analytics import (
    get_geographic_stats,
    get_source_factuality_stats,
)
from factfeed.web.deps import get_db

router = APIRouter()


@router.get("/stats/sources", response_model=list[dict[str, str | int | float]])
async def get_source_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate sentence labels grouped by source."""
    return await get_source_factuality_stats(db)


@router.get("/stats/geo", response_model=list[dict[str, str | int]])
async def get_geo_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate article counts grouped by country."""
    return await get_geographic_stats(db)
