"""APScheduler setup with immediate first run and single-worker guard."""

from datetime import datetime, timezone
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from factfeed.config import settings


def create_scheduler(ingestion_fn: Callable) -> AsyncIOScheduler:
    """Create an APScheduler instance that fires the ingestion cycle.

    - Runs immediately on startup (``next_run_time=now``)
    - Repeats every ``ingest_interval_minutes``
    - ``max_instances=1`` prevents overlapping runs (single-worker guard)
    - ``coalesce=True`` prevents catch-up flood if scheduler falls behind
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        ingestion_fn,
        trigger="interval",
        minutes=settings.ingest_interval_minutes,
        next_run_time=datetime.now(timezone.utc),  # Run immediately on start
        max_instances=1,
        coalesce=True,
        id="ingestion_cycle",
        name="Ingest RSS feeds",
    )
    return scheduler
