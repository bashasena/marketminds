"""Snapshot API routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.jobs.snapshot_job import run_snapshot_pipeline
from app.repositories.snapshot_repo import (
    get_latest_snapshot,
    get_snapshot_for_date,
    list_recent_snapshots,
    upsert_daily_snapshot,
    upsert_fii_dii_flow,
)
from app.services.market_snapshot import build_snapshot
from app.services.us_market_snapshot import build_us_snapshot

router = APIRouter(prefix="/snapshot", tags=["snapshot"])
IST = ZoneInfo("Asia/Kolkata")
VALID_MARKETS = frozenset({"in_nifty", "us_broad"})


@router.get("/today")
def snapshot_today(
    market: str = Query("in_nifty", description="in_nifty (India) | us_broad (USA)"),
    live: bool = Query(False, description="Force recompute from upstream sources"),
    persist: bool = Query(False, description="When true, save freshly built snapshot to DB"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"invalid market; use {sorted(VALID_MARKETS)}")
    today_ist = datetime.now(IST).date()
    if not live:
        row = get_snapshot_for_date(db, today_ist, market)
        if row is None:
            row = get_latest_snapshot(db, market)
        if row is not None:
            return row.payload
        # Do not run builders for normal reads — avoids slow fetches and nginx timeouts.
        raise HTTPException(status_code=404, detail="no_stored_snapshot")
    if market == "in_nifty":
        payload = build_snapshot(get_settings())
    else:
        payload = build_us_snapshot(get_settings())
    if persist:
        snap_date = date.fromisoformat(str(payload["snapshot_date"]))
        comp = payload.get("composite", {}).get("score_0_100")
        idx = payload.get("index", {})
        upsert_daily_snapshot(
            db,
            snap_date,
            payload,
            float(comp) if comp is not None else None,
            float(idx["close"]) if idx.get("close") is not None else None,
            float(idx["pct_change"]) if idx.get("pct_change") is not None else None,
            market_id=market,
        )
        fii = payload.get("fii_dii", {})
        if market == "in_nifty" and fii.get("as_of"):
            fd = date.fromisoformat(str(fii["as_of"]))
            upsert_fii_dii_flow(
                db,
                fd,
                float(fii["fii_net_crores"]) if fii.get("fii_net_crores") is not None else None,
                float(fii["dii_net_crores"]) if fii.get("dii_net_crores") is not None else None,
            )
    return payload


@router.get("/history")
def snapshot_history(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = list_recent_snapshots(db, days)
    return {
        "days": days,
        "count": len(rows),
        "items": [
            {
                "snapshot_date": str(r.snapshot_date),
                "composite_sentiment": r.composite_sentiment,
                "nifty_close": r.nifty_close,
                "nifty_pct_change": r.nifty_pct_change,
                "payload": r.payload,
            }
            for r in rows
        ],
    }


@router.post("/refresh")
def snapshot_refresh(
    market: str = Query("in_nifty", description="in_nifty | us_broad"),
) -> dict[str, Any]:
    """Manual / hook trigger: rebuild and persist."""
    if market not in VALID_MARKETS:
        raise HTTPException(status_code=400, detail=f"invalid market; use {sorted(VALID_MARKETS)}")
    payload = run_snapshot_pipeline(persist=True, market=market)
    return {"ok": True, "snapshot_date": payload.get("snapshot_date"), "market": market}
