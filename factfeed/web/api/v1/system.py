"""System monitoring endpoints."""

from fastapi import APIRouter

from factfeed.services.system_monitor import monitor

router = APIRouter()


@router.get("/status")
async def get_system_status():
    """Get real-time pipeline status."""
    return monitor.get_snapshot()
