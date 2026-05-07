"""Scheduled job: build snapshot and persist to PostgreSQL."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db import SessionLocal
from app.repositories.snapshot_repo import get_latest_snapshot, upsert_daily_snapshot, upsert_fii_dii_flow
from app.services.market_snapshot import build_snapshot
from app.services.us_market_snapshot import build_us_snapshot
from app.services.us_nasdaq_market_snapshot import build_us_nasdaq_snapshot

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def run_snapshot_pipeline(persist: bool = True, market: str = "in_nifty", full: bool = False) -> dict:
    """Scheduled jobs use ``full=False`` and honor SCHEDULED_* env toggles. Admin / hooks use ``full=True`` for a complete upstream build."""
    settings = get_settings()
    db = SessionLocal()
    try:
        row = get_latest_snapshot(db, market)
    finally:
        db.close()
    stored = row.payload if row else {}
    stored_opts = stored.get("options")
    stored_x = stored.get("x_sentiment_summary")
    stored_dbento = stored.get("databento_options")

    if full:
        ix = inse = uopt = True
    else:
        if market == "in_nifty":
            ix = settings.scheduled_snapshot_include_x
            inse = settings.scheduled_snapshot_include_nse_options
            uopt = True
        elif market == "us_broad":
            ix = settings.scheduled_us_snapshot_include_x
            uopt = settings.scheduled_us_snapshot_include_options
            inse = True
        elif market == "usa_nasdaq":
            ix = settings.scheduled_us_snapshot_include_x
            uopt = settings.scheduled_us_snapshot_include_options
            inse = True
        else:
            ix = inse = uopt = True

    if market == "us_broad":
        payload = build_us_snapshot(
            settings,
            include_x=ix,
            include_us_options=uopt,
            stored_options=stored_opts if not uopt else None,
            stored_databento_options=stored_dbento if not uopt else None,
            stored_x_summary=stored_x if not ix else None,
        )
    elif market == "usa_nasdaq":
        payload = build_us_nasdaq_snapshot(
            settings,
            include_x=ix,
            include_us_options=uopt,
            stored_options=stored_opts if not uopt else None,
            stored_databento_options=stored_dbento if not uopt else None,
            stored_x_summary=stored_x if not ix else None,
        )
    else:
        payload = build_snapshot(
            settings,
            include_x=ix,
            include_nse_options=inse,
            stored_options=stored_opts if not inse else None,
            stored_x_summary=stored_x if not ix else None,
        )
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
