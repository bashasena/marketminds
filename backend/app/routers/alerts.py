"""Volume alert registration endpoints."""

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
    """Return all symbols currently being watched server-side."""
    return {"alerts": alert_manager.list_symbols()}


@router.post("")
def add_alert(body: AlertRequest):
    """Register a symbol for Telegram notifications."""
    sym = body.sym.strip().upper()
    if not sym:
        raise HTTPException(status_code=422, detail="sym is required")
    alert_manager.add(sym=sym, name=body.name, current_ratio=body.current_ratio)
    return {"ok": True, "sym": sym, "watching": True}


@router.delete("/{sym}")
def remove_alert(sym: str):
    """Remove a symbol from the Telegram watchlist."""
    removed = alert_manager.remove(sym.upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"{sym.upper()} not in watchlist")
    return {"ok": True, "sym": sym.upper(), "watching": False}
