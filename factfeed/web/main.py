"""FastAPI app with lifespan integrating scheduler, httpx client, and source seeding."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from factfeed.config import settings
from factfeed.db.session import AsyncSessionLocal
from factfeed.ingestion.logging import configure_logging
from factfeed.ingestion.persister import seed_sources
from factfeed.ingestion.runner import run_ingestion_cycle
from factfeed.ingestion.scheduler import create_scheduler
from factfeed.ingestion.sources import SOURCES


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: configure logging, seed sources, start scheduler."""
    configure_logging()

    # Seed sources into database
    async with AsyncSessionLocal() as session:
        await seed_sources(session, SOURCES)

    # Create shared HTTP client
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
        follow_redirects=True,
    ) as http_client:

        # Create and start scheduler
        async def ingestion_job():
            await run_ingestion_cycle(AsyncSessionLocal, http_client)

        scheduler = create_scheduler(ingestion_job)
        scheduler.start()
        yield
        scheduler.shutdown(wait=False)


app = FastAPI(title="FactFeed", lifespan=lifespan)


@app.get("/health")
async def health():
    """Basic liveness check."""
    return {"status": "ok"}
