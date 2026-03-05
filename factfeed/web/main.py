"""FastAPI app with lifespan integrating scheduler, httpx client, and source seeding."""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from factfeed.config import settings
from factfeed.db.session import AsyncSessionLocal
from factfeed.ingestion.logging import configure_logging
from factfeed.ingestion.persister import seed_sources
from factfeed.ingestion.runner import run_ingestion_cycle
from factfeed.ingestion.scheduler import create_scheduler
from factfeed.ingestion.sources import SOURCES
from factfeed.web.api.v1.endpoints import router as api_v1_router
from factfeed.web.limiter import limiter
from factfeed.web.routes import analytics as analytics_routes
from factfeed.web.routes import article as article_routes
from factfeed.web.routes import search as search_routes
from factfeed.web.routes import system as system_routes

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
    nlp_on_gpu = False
    if settings.nlp_enabled:
        try:
            from factfeed.nlp.calibrator import TemperatureScaler
            from factfeed.nlp.classifier import create_classifier

            zs_pipeline = create_classifier()
            calibrator = TemperatureScaler(
                temperature=settings.nlp_calibration_temperature
            )
            from factfeed.nlp.classifier import is_gpu_pipeline

            nlp_on_gpu = is_gpu_pipeline(zs_pipeline)
            log.info(
                "nlp_classifier_loaded",
                model="deberta-v3-base-zeroshot-v2.0",
                device="cuda" if nlp_on_gpu else "cpu",
                temperature=settings.nlp_calibration_temperature,
            )
        except Exception:
            log.warning("nlp_classifier_unavailable", exc_info=True)

    app.state.zs_pipeline = zs_pipeline
    app.state.calibrator = calibrator

    # Create shared HTTP client
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
        follow_redirects=True,
    ) as http_client:
        # Ingestion job — runs every 15 minutes
        async def ingestion_job():
            await run_ingestion_cycle(AsyncSessionLocal, http_client)

        # Classification job — runs every 30 seconds, independent of ingestion
        async def classification_job():
            if not settings.nlp_enabled or zs_pipeline is None:
                return
            try:
                from factfeed.nlp.pipeline import classify_unprocessed_articles

                classified = await classify_unprocessed_articles(
                    AsyncSessionLocal,
                    zs_pipeline,
                    calibrator,
                    batch_size=settings.nlp_batch_size_gpu if nlp_on_gpu else settings.nlp_batch_size_cpu,
                )
                if classified > 0:
                    log.info(
                        "nlp_classification_complete",
                        articles_classified=classified,
                    )
            except Exception:
                log.error("nlp_classification_failed", exc_info=True)

        app.state.ingestion_job = ingestion_job
        scheduler = create_scheduler(ingestion_job)
        # Add classification as a separate job running every 30 seconds
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler.add_job(
            classification_job,
            trigger=IntervalTrigger(seconds=15),
            id="classification",
            name="Classify unprocessed articles",
            max_instances=1,
        )
        scheduler.start()
        yield
        scheduler.shutdown(wait=False)


app = FastAPI(title="The Sorter", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS (allow all origins for public API access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
_static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Route modules
app.include_router(search_routes.router)
app.include_router(article_routes.router)
app.include_router(analytics_routes.router)
app.include_router(system_routes.router, prefix="/system")
app.include_router(api_v1_router, prefix="/api/v1", tags=["api"])


@app.get("/health")
async def health():
    """Basic liveness check."""
    return {"status": "ok"}
