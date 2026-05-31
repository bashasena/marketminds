"""Volume alert watchlist endpoints — server-side, DB-backed."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.alert_manager import alert_manager

router = APIRouter(prefix="/volume/alerts", tags=["alerts"])


class AlertRequest(BaseModel):
    sym: str
    name: str
    current_ratio: float = 0.0


@router.get("")
def list_alerts():
    """Return all watched symbols with their latest PCR/volume snapshot."""
    return {"alerts": alert_manager.list_all()}


@router.post("")
def add_alert(body: AlertRequest):
    """Add a symbol to the server-side watchlist."""
    sym = body.sym.strip().upper()
    if not sym:
        raise HTTPException(status_code=422, detail="sym is required")
    entry = alert_manager.add(sym=sym, name=body.name, current_ratio=body.current_ratio)
    return {"ok": True, "sym": sym, "watching": True, "entry": entry}


@router.delete("/{sym}")
def remove_alert(sym: str):
    """Remove a symbol from the watchlist."""
    removed = alert_manager.remove(sym.upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"{sym.upper()} not in watchlist")
    return {"ok": True, "sym": sym.upper(), "watching": False}
