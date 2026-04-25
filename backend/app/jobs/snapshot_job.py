"""Scheduled job: build snapshot and persist to PostgreSQL."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db import SessionLocal
from app.repositories.snapshot_repo import upsert_daily_snapshot, upsert_fii_dii_flow
from app.services.market_snapshot import build_snapshot
from app.services.us_market_snapshot import build_us_snapshot

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def run_snapshot_pipeline(persist: bool = True, market: str = "in_nifty") -> dict:
    settings = get_settings()
    if market == "us_broad":
        payload = build_us_snapshot(settings)
    else:
        payload = build_snapshot(settings)
    snap_date = date.fromisoformat(str(payload["snapshot_date"]))
    comp = payload.get("composite", {}).get("score_0_100")
    nifty_close = payload.get("index", {}).get("close")
    nifty_pct = payload.get("index", {}).get("pct_change")
    fii = payload.get("fii_dii", {})
    fii_date = fii.get("as_of")
    if persist:
        db = SessionLocal()
        try:
            upsert_daily_snapshot(db, snap_date, payload, comp, nifty_close, nifty_pct, market_id=market)
            if market == "in_nifty" and fii_date:
                fd = date.fromisoformat(str(fii_date))
                upsert_fii_dii_flow(
                    db,
                    fd,
                    fii.get("fii_net_crores"),
                    fii.get("dii_net_crores"),
                    raw_note=None,
                )
        finally:
            db.close()
    logger.info("Snapshot pipeline OK date=%s market=%s persist=%s close=%s", snap_date, market, persist, nifty_close)
    return payload


def ist_now() -> datetime:
    return datetime.now(IST)
