"""Admin settings endpoints — PCR refresh interval and other app config."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.alert_manager import alert_manager

router = APIRouter(prefix="/admin/settings", tags=["admin"])

VALID_PCR_INTERVALS = {5, 10, 30, 60}


class PcrIntervalRequest(BaseModel):
    pcr_refresh_interval_minutes: int


@router.get("")
def get_settings():
    """Return current app settings."""
    return {
        "pcr_refresh_interval_minutes": alert_manager.get_pcr_interval_minutes(),
        "valid_intervals": sorted(VALID_PCR_INTERVALS),
    }


@router.post("")
def update_settings(body: PcrIntervalRequest):
    """Update app settings. Persists to DB and takes effect immediately."""
    mins = body.pcr_refresh_interval_minutes
    if mins not in VALID_PCR_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"pcr_refresh_interval_minutes must be one of {sorted(VALID_PCR_INTERVALS)}",
        )
    alert_manager.set_pcr_interval_minutes(mins)
    return {
        "ok": True,
        "pcr_refresh_interval_minutes": mins,
        "message": f"PCR refresh interval updated to {mins} minutes",
    }
