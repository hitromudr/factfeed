"""FastAPI app with lifespan integrating scheduler, httpx client, and source seeding."""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from factfeed.config import settings
from factfeed.web.limiter import limiter
from factfeed.web.routes import search as search_routes
from factfeed.web.routes import article as article_routes
from factfeed.db.session import AsyncSessionLocal
from factfeed.ingestion.logging import configure_logging
from factfeed.ingestion.persister import seed_sources
from factfeed.ingestion.runner import run_ingestion_cycle
from factfeed.ingestion.scheduler import create_scheduler
from factfeed.ingestion.sources import SOURCES

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: configure logging, seed sources, start scheduler."""
    configure_logging()

    # Seed sources into database
    async with AsyncSessionLocal() as session:
        await seed_sources(session, SOURCES)

    # Initialize NLP classifier (lazy — only if enabled)
    zs_pipeline = None
    calibrator = None
    if settings.nlp_enabled:
        try:
            from factfeed.nlp.classifier import create_classifier

            zs_pipeline = create_classifier()
            log.info("nlp_classifier_loaded", model="deberta-v3-base-zeroshot-v2.0")
        except Exception:
            log.warning("nlp_classifier_unavailable", exc_info=True)

    # Create shared HTTP client
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
        follow_redirects=True,
    ) as http_client:

        # Create and start scheduler
        async def ingestion_job():
            await run_ingestion_cycle(AsyncSessionLocal, http_client)

            # Post-ingestion classification
            if settings.nlp_enabled and zs_pipeline is not None:
                try:
                    from factfeed.nlp.pipeline import classify_unprocessed_articles

                    classified = await classify_unprocessed_articles(
                        AsyncSessionLocal,
                        zs_pipeline,
                        calibrator,
                        batch_size=settings.nlp_batch_size,
                    )
                    if classified > 0:
                        log.info("nlp_classification_complete", articles_classified=classified)
                except Exception:
                    log.error("nlp_classification_failed", exc_info=True)

        scheduler = create_scheduler(ingestion_job)
        scheduler.start()
        yield
        scheduler.shutdown(wait=False)


app = FastAPI(title="FactFeed", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Static files
_static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Route modules
app.include_router(search_routes.router)
app.include_router(article_routes.router)


@app.get("/health")
async def health():
    """Basic liveness check."""
    return {"status": "ok"}
