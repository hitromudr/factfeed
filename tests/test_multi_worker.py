"""Multi-worker APScheduler safety tests.

Verifies deployment constraints that prevent duplicate ingestion execution:
  1. APScheduler job has max_instances=1 (intra-process overlap guard)
  2. APScheduler job has coalesce=True (catch-up flood prevention)
  3. docker-compose.yml app service uses --workers 1 (primary multi-process guard)

These tests do NOT start the scheduler — they only inspect configuration.
"""
from pathlib import Path

import pytest

from factfeed.ingestion.scheduler import create_scheduler


def _get_ingestion_job():
    """Create a scheduler with a no-op function and return the ingestion_cycle job."""
    scheduler = create_scheduler(lambda: None)
    try:
        job = scheduler.get_job("ingestion_cycle")
        return job
    finally:
        # Shut down is safe even on a non-started scheduler; suppress if it raises.
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass


def test_scheduler_max_instances_is_one():
    """APScheduler job has max_instances=1 to prevent overlapping runs within a single worker process."""
    job = _get_ingestion_job()
    assert job is not None, "ingestion_cycle job not found in scheduler"
    assert job.max_instances == 1, (
        f"Expected max_instances=1 but got {job.max_instances}. "
        "Multiple concurrent ingestion runs would duplicate articles."
    )


def test_scheduler_coalesce_enabled():
    """APScheduler job has coalesce=True to prevent catch-up flood if scheduler falls behind."""
    job = _get_ingestion_job()
    assert job is not None, "ingestion_cycle job not found in scheduler"
    assert job.coalesce is True, (
        f"Expected coalesce=True but got {job.coalesce}. "
        "Without coalescing, a scheduler that falls behind would fire many back-to-back runs."
    )


def test_docker_compose_single_worker():
    """docker-compose.yml app service is constrained to --workers 1.

    This is the PRIMARY multi-process guard: a single uvicorn worker means only
    one APScheduler instance ever exists, so the intra-process max_instances=1
    guard is sufficient to prevent duplicate ingestion runs.
    """
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    assert compose_path.exists(), f"docker-compose.yml not found at {compose_path}"

    content = compose_path.read_text()

    # Accept both YAML list form ("--workers", "1") and inline form (--workers 1)
    assert "--workers" in content and (
        '"1"' in content or "'1'" in content or "--workers 1" in content
    ), (
        "docker-compose.yml app service must use '--workers 1' to prevent multiple "
        "APScheduler instances from starting in separate uvicorn worker processes.\n"
        f"Checked: {compose_path}"
    )
